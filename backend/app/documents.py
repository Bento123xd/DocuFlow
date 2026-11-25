"""Documentos: recebimento (upload), consulta, arquivo original e processamento."""
from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from datetime import date
from pathlib import Path
from urllib.parse import quote

from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import FileResponse
from starlette.routing import Route

from . import clients, config, db, doctypes, extraction, history
from .common import STATUS_LABELS, ApiError, Status, ok, path_int, read_json
from .schemas import (
    ClientRef,
    DocTypeRef,
    DocumentDetail,
    DocumentListOut,
    DocumentMetaIn,
    DocumentSummary,
    FieldValueOut,
)
from .validators import check_field

log = logging.getLogger("docuflow.documents")

EDITABLE_STATUSES = {Status.AGUARDANDO_REVISAO.value}
REPROCESSABLE_STATUSES = {
    Status.RECEBIDO.value,
    Status.AGUARDANDO_REVISAO.value,
    Status.ERRO.value,
    Status.REJEITADO.value,
}

_MAGIC = {
    "application/pdf": (b"%PDF-",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}


def doc_code(doc_id: int) -> str:
    return f"DOC-{doc_id:05d}"


# ---------------------------------------------------------------- leitura
_BASE_SELECT = """
SELECT d.*, c.name AS client_name, t.name AS type_name,
       (SELECT COUNT(*) FROM document_fields f WHERE f.document_id = d.id AND f.value IS NULL) AS pending_fields
FROM documents d
JOIN clients c ON c.id = d.client_id
JOIN doc_types t ON t.id = d.type_id
"""


def _summary(row: sqlite3.Row) -> DocumentSummary:
    return DocumentSummary(
        id=row["id"],
        code=doc_code(row["id"]),
        client=ClientRef(id=row["client_id"], name=row["client_name"]),
        type=DocTypeRef(id=row["type_id"], name=row["type_name"]),
        original_filename=row["original_filename"],
        mime=row["mime"],
        size_bytes=row["size_bytes"],
        received_at=row["received_at"],
        uploaded_at=row["uploaded_at"],
        status=row["status"],
        status_label=STATUS_LABELS.get(row["status"], row["status"]),
        pending_fields=row["pending_fields"] or 0,
        is_demo=bool(row["is_demo"]),
    )


def get_row(conn: sqlite3.Connection, doc_id: int) -> sqlite3.Row:
    row = conn.execute(_BASE_SELECT + " WHERE d.id = ?", (doc_id,)).fetchone()
    if not row:
        raise ApiError(404, "Documento não encontrado.")
    return row


def get_fields(conn: sqlite3.Connection, doc_id: int) -> list[FieldValueOut]:
    rows = conn.execute(
        "SELECT * FROM document_fields WHERE document_id = ? ORDER BY position", (doc_id,)
    ).fetchall()
    out = []
    for r in rows:
        errors, warnings = check_field(r["kind"], r["value"])
        out.append(
            FieldValueOut(
                key=r["key"], label=r["label"], kind=r["kind"], value=r["value"],
                source=r["source"], evidence=r["evidence"], errors=errors, warnings=warnings,
            )
        )
    return out


def get_detail(conn: sqlite3.Connection, doc_id: int) -> DocumentDetail:
    row = get_row(conn, doc_id)
    base = _summary(row).model_dump()
    method = row["extraction_method"]
    return DocumentDetail(
        **base,
        extraction_method=method,
        extraction_method_label=extraction.METHOD_LABELS.get(method) if method else None,
        extraction_note=row["extraction_note"],
        error_message=row["error_message"],
        rejection_reason=row["rejection_reason"],
        reviewed_at=row["reviewed_at"],
        fields=get_fields(conn, doc_id),
        history=history.list_for(conn, doc_id),
        can_edit=row["status"] in EDITABLE_STATUSES,
        can_reprocess=row["status"] in REPROCESSABLE_STATUSES,
    )


def _iso_date(value: str | None, label: str) -> str | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ApiError(422, f"{label}: data inválida (use AAAA-MM-DD).")


def build_filters(params) -> tuple[str, list]:
    where: list[str] = []
    args: list = []
    if params.get("client_id"):
        try:
            args.append(int(params["client_id"]))
        except ValueError:
            raise ApiError(422, "Filtro de cliente inválido.")
        where.append("d.client_id = ?")
    if params.get("type_id"):
        where.append("d.type_id = ?")
        args.append(params["type_id"])
    if params.get("status"):
        statuses = [s for s in params["status"].split(",") if s in STATUS_LABELS]
        if statuses:
            where.append(f"d.status IN ({','.join('?' * len(statuses))})")
            args.extend(statuses)
    start = _iso_date(params.get("received_from"), "Data inicial")
    end = _iso_date(params.get("received_to"), "Data final")
    if start:
        where.append("d.received_at >= ?")
        args.append(start)
    if end:
        where.append("d.received_at <= ?")
        args.append(end)
    q = (params.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        code_id = re.sub(r"\D", "", q)
        clause = "(d.original_filename LIKE ? OR c.name LIKE ?"
        args.extend([like, like])
        if code_id:
            clause += " OR d.id = ?"
            args.append(int(code_id))
        where.append(clause + ")")
    if params.get("pending") == "1":
        where.append("EXISTS (SELECT 1 FROM document_fields f WHERE f.document_id = d.id AND f.value IS NULL)")
    return (" WHERE " + " AND ".join(where)) if where else "", args


_SORTS = {
    "received_desc": "d.received_at DESC, d.id DESC",
    "received_asc": "d.received_at ASC, d.id ASC",
    "uploaded_desc": "d.uploaded_at DESC, d.id DESC",
}


def list_documents(conn: sqlite3.Connection, params) -> DocumentListOut:
    where, args = build_filters(params)
    order = _SORTS.get(params.get("sort", ""), _SORTS["received_desc"])
    total = conn.execute(
        "SELECT COUNT(*) FROM documents d JOIN clients c ON c.id = d.client_id" + where, args
    ).fetchone()[0]
    try:
        limit = max(1, min(int(params.get("limit", 200)), 500))
        offset = max(0, int(params.get("offset", 0)))
    except ValueError:
        raise ApiError(422, "Paginação inválida.")
    rows = conn.execute(
        _BASE_SELECT + where + f" ORDER BY {order} LIMIT ? OFFSET ?", [*args, limit, offset]
    ).fetchall()
    return DocumentListOut(items=[_summary(r) for r in rows], total=total)


# ---------------------------------------------------------------- escrita
def set_status(
    conn: sqlite3.Connection, doc_id: int, new_status: Status, action: str,
    detail: str | None = None, **columns,
) -> None:
    old = conn.execute("SELECT status FROM documents WHERE id = ?", (doc_id,)).fetchone()["status"]
    sets = ["status = ?"] + [f"{k} = ?" for k in columns]
    conn.execute(
        f"UPDATE documents SET {', '.join(sets)} WHERE id = ?",
        [new_status.value, *columns.values(), doc_id],
    )
    history.add(conn, doc_id, action, detail, status_from=old, status_to=new_status.value)


def replace_fields(conn: sqlite3.Connection, doc_id: int, results: list[extraction.FieldResult]) -> None:
    conn.execute("DELETE FROM document_fields WHERE document_id = ?", (doc_id,))
    for pos, r in enumerate(results):
        conn.execute(
            "INSERT INTO document_fields (document_id, key, label, kind, value, source, evidence, position)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (doc_id, r.key, r.label, r.kind, r.value, r.source, r.evidence, pos),
        )


def process_document(doc_id: int) -> None:
    """Executa a extração e move o documento para revisão (ou para Erro)."""
    with db.session() as conn:
        row = get_row(conn, doc_id)
        if row["status"] not in REPROCESSABLE_STATUSES:
            raise ApiError(409, "Este documento não pode ser processado no status atual.")
        set_status(conn, doc_id, Status.EM_PROCESSAMENTO, "processamento_iniciado",
                   f"Tipo documental: {row['type_name']}", error_message=None, rejection_reason=None)
        fields = doctypes.get_fields(conn, row["type_id"])
        stored, mime = row["stored_filename"], row["mime"]

    path = config.STORAGE_DIR / stored
    try:
        if not path.exists():
            raise extraction.ExtractionError("O arquivo original não foi encontrado no armazenamento.")
        result = extraction.run(path, mime, fields)
    except extraction.ExtractionError as exc:
        with db.session() as conn:
            set_status(conn, doc_id, Status.ERRO, "erro", str(exc),
                       error_message=str(exc), extraction_method=None, extraction_note=None)
        return
    except Exception:
        log.exception("Erro inesperado ao processar documento %s", doc_id)
        msg = "Erro inesperado durante o processamento. Tente reprocessar o documento."
        with db.session() as conn:
            set_status(conn, doc_id, Status.ERRO, "erro", msg, error_message=msg)
        return

    found = sum(1 for f in result.fields if f.value is not None)
    with db.session() as conn:
        replace_fields(conn, doc_id, result.fields)
        detail = f"{found} de {len(result.fields)} campos identificados. Método: " \
                 f"{extraction.METHOD_LABELS.get(result.method, result.method)}."
        set_status(conn, doc_id, Status.AGUARDANDO_REVISAO, "extracao_concluida", detail,
                   extraction_method=result.method, extraction_note=result.note,
                   error_message=None, reviewed_at=None)


def _clean_filename(name: str) -> str:
    name = Path(name or "documento").name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip() or "documento"
    return name[-150:]


async def _read_upload(upload: UploadFile) -> bytes:
    data = bytearray()
    while chunk := await upload.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > config.MAX_UPLOAD_BYTES:
            raise ApiError(413, f"Arquivo maior que o limite de {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    return bytes(data)


# ---------------------------------------------------------------- rotas
async def api_list(request: Request):
    with db.session() as conn:
        return ok(list_documents(conn, request.query_params))


async def api_detail(request: Request):
    doc_id = path_int(request, "doc_id")
    with db.session() as conn:
        return ok(get_detail(conn, doc_id))


async def api_upload(request: Request):
    async with request.form(max_files=1, max_fields=10) as form:
        upload = form.get("file")
        if not isinstance(upload, UploadFile) or not upload.filename:
            raise ApiError(422, "Selecione um arquivo para enviar.")
        filename = _clean_filename(upload.filename)
        ext = Path(filename).suffix.lower()
        if ext not in config.ALLOWED_EXTENSIONS:
            raise ApiError(415, "Formato não aceito. Envie arquivos PDF, JPG, JPEG ou PNG.")
        mime = config.ALLOWED_EXTENSIONS[ext]
        content = await _read_upload(upload)
        client_raw = form.get("client_id")
        type_id = str(form.get("type_id") or doctypes.DEFAULT_TYPE_ID)
        received_raw = str(form.get("received_at") or date.today().isoformat())

    if not content:
        raise ApiError(422, "O arquivo enviado está vazio.")
    if not content.startswith(_MAGIC[mime]):
        raise ApiError(415, "O conteúdo do arquivo não corresponde à extensão informada "
                            f"({ext}). Verifique se o arquivo não está corrompido.")
    try:
        client_id = int(str(client_raw))
    except (TypeError, ValueError):
        raise ApiError(422, "Selecione o cliente ao qual o documento pertence.")
    received_at = _iso_date(received_raw, "Data de recebimento")
    if received_at and received_at > date.today().isoformat():
        raise ApiError(422, "A data de recebimento não pode estar no futuro.")

    stored = f"{uuid.uuid4().hex}{ext}"
    stored_path = config.STORAGE_DIR / stored
    try:
        with db.session() as conn:
            clients.ensure_exists(conn, client_id)
            doctypes.ensure_exists(conn, type_id)
            stored_path.write_bytes(content)
            cur = conn.execute(
                "INSERT INTO documents (client_id, type_id, original_filename, stored_filename, mime,"
                " size_bytes, received_at, uploaded_at, status, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (client_id, type_id, filename, stored, mime, len(content), received_at,
                 db.now_iso(), Status.RECEBIDO.value),
            )
            doc_id = cur.lastrowid
            history.add(conn, doc_id, "recebido", f"Arquivo “{filename}” enviado manualmente.",
                        status_to=Status.RECEBIDO.value)
    except Exception:
        stored_path.unlink(missing_ok=True)  # não deixa arquivo órfão no armazenamento
        raise

    await run_in_threadpool(process_document, doc_id)
    with db.session() as conn:
        return ok(get_detail(conn, doc_id), 201)


async def api_file(request: Request):
    doc_id = path_int(request, "doc_id")
    with db.session() as conn:
        row = get_row(conn, doc_id)
    path = config.STORAGE_DIR / row["stored_filename"]
    if not path.exists():
        raise ApiError(404, "O arquivo original não foi encontrado no armazenamento.")
    disposition = "attachment" if request.query_params.get("download") == "1" else "inline"
    return FileResponse(
        path,
        media_type=row["mime"],
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(row['original_filename'])}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


async def api_update_meta(request: Request):
    doc_id = path_int(request, "doc_id")
    data = await read_json(request, DocumentMetaIn)
    reprocess = False
    with db.session() as conn:
        row = get_row(conn, doc_id)
        if row["status"] in (Status.APROVADO.value, Status.EM_PROCESSAMENTO.value):
            raise ApiError(409, "Reabra a revisão para alterar os dados de um documento aprovado.")
        changes: list[str] = []
        if data.client_id is not None and data.client_id != row["client_id"]:
            client = clients.ensure_exists(conn, data.client_id)
            conn.execute("UPDATE documents SET client_id = ? WHERE id = ?", (data.client_id, doc_id))
            changes.append(f"Cliente: {row['client_name']} → {client['name']}")
        if data.received_at is not None and data.received_at.isoformat() != row["received_at"]:
            if data.received_at > date.today():
                raise ApiError(422, "A data de recebimento não pode estar no futuro.")
            conn.execute("UPDATE documents SET received_at = ? WHERE id = ?",
                         (data.received_at.isoformat(), doc_id))
            changes.append(f"Recebimento: {data.received_at.strftime('%d/%m/%Y')}")
        if changes:
            history.add(conn, doc_id, "dados_alterados", "; ".join(changes))
        if data.type_id is not None and data.type_id != row["type_id"]:
            new_type = doctypes.ensure_exists(conn, data.type_id)
            conn.execute("UPDATE documents SET type_id = ? WHERE id = ?", (data.type_id, doc_id))
            history.add(conn, doc_id, "tipo_alterado", f"{row['type_name']} → {new_type['name']}. "
                        "Os campos serão extraídos novamente.")
            reprocess = row["status"] != Status.RECEBIDO.value
    if reprocess:
        await run_in_threadpool(process_document, doc_id)
    with db.session() as conn:
        return ok(get_detail(conn, doc_id))


async def api_process(request: Request):
    doc_id = path_int(request, "doc_id")
    await run_in_threadpool(process_document, doc_id)
    with db.session() as conn:
        return ok(get_detail(conn, doc_id))


routes = [
    Route("/api/documents", api_list, methods=["GET"]),
    Route("/api/documents", api_upload, methods=["POST"]),
    Route("/api/documents/{doc_id}", api_detail, methods=["GET"]),
    Route("/api/documents/{doc_id}", api_update_meta, methods=["PATCH"]),
    Route("/api/documents/{doc_id}/file", api_file, methods=["GET"]),
    Route("/api/documents/{doc_id}/process", api_process, methods=["POST"]),
]
