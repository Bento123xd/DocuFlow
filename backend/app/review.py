"""Revisão humana: correção de campos, aprovação, rejeição e observações.

Um documento só passa a "Aprovado" por ação explícita do usuário.
"""
from __future__ import annotations

import sqlite3

from starlette.requests import Request
from starlette.routing import Route

from . import db, history
from .common import ApiError, Status, ok, path_int, read_json
from .documents import get_detail, get_row, set_status
from .schemas import ApproveIn, FieldValueIn, NoteIn, RejectIn, SaveFieldsIn
from .validators import check_field, normalize_field


def _require_review(row: sqlite3.Row) -> None:
    if row["status"] != Status.AGUARDANDO_REVISAO.value:
        raise ApiError(409, "Somente documentos com status “Aguardando revisão” podem ser revisados.")


def save_fields(conn: sqlite3.Connection, doc_id: int, values: list[FieldValueIn]) -> list[str]:
    """Grava os valores informados. Retorna os rótulos dos campos alterados."""
    current = {
        r["key"]: r
        for r in conn.execute("SELECT * FROM document_fields WHERE document_id = ?", (doc_id,)).fetchall()
    }
    changed: list[str] = []
    for item in values:
        row = current.get(item.key)
        if row is None:
            raise ApiError(422, f"Campo desconhecido: {item.key}.")
        new_value = normalize_field(row["kind"], item.value)
        if new_value == row["value"]:
            continue
        source = "manual" if new_value is not None else "nao_identificado"
        conn.execute(
            "UPDATE document_fields SET value = ?, source = ?, evidence = NULL WHERE id = ?",
            (new_value, source, row["id"]),
        )
        changed.append(row["label"])
    if changed:
        history.add(conn, doc_id, "campos_corrigidos", "Alterados: " + ", ".join(changed))
    return changed


def _blocking_errors(conn: sqlite3.Connection, doc_id: int) -> list[str]:
    problems = []
    for r in conn.execute("SELECT * FROM document_fields WHERE document_id = ? ORDER BY position", (doc_id,)):
        errors, _ = check_field(r["kind"], r["value"])
        problems.extend(f"{r['label']}: {e}" for e in errors)
    return problems


async def api_save_fields(request: Request):
    doc_id = path_int(request, "doc_id")
    data = await read_json(request, SaveFieldsIn)
    with db.session() as conn:
        _require_review(get_row(conn, doc_id))
        save_fields(conn, doc_id, data.fields)
        return ok(get_detail(conn, doc_id))


async def api_approve(request: Request):
    doc_id = path_int(request, "doc_id")
    data = await read_json(request, ApproveIn)
    with db.session() as conn:
        _require_review(get_row(conn, doc_id))
        if data.fields:
            save_fields(conn, doc_id, data.fields)
        problems = _blocking_errors(conn, doc_id)
        if problems:
            raise ApiError(422, "Corrija os campos antes de aprovar: " + "; ".join(problems), problems)
        pending = conn.execute(
            "SELECT label FROM document_fields WHERE document_id = ? AND value IS NULL ORDER BY position",
            (doc_id,),
        ).fetchall()
        detail = "Aprovado após conferência humana."
        if pending:
            detail += " Campos não identificados mantidos: " + ", ".join(p["label"] for p in pending) + "."
        if data.note and data.note.strip():
            history.add(conn, doc_id, "observacao", data.note.strip())
        set_status(conn, doc_id, Status.APROVADO, "aprovado", detail, reviewed_at=db.now_iso())
    with db.session() as conn:
        return ok(get_detail(conn, doc_id))


async def api_reject(request: Request):
    doc_id = path_int(request, "doc_id")
    data = await read_json(request, RejectIn)
    with db.session() as conn:
        row = get_row(conn, doc_id)
        if row["status"] not in (Status.AGUARDANDO_REVISAO.value, Status.ERRO.value, Status.RECEBIDO.value):
            raise ApiError(409, "Este documento não pode ser rejeitado no status atual.")
        reason = data.reason.strip()
        set_status(conn, doc_id, Status.REJEITADO, "rejeitado", reason,
                   rejection_reason=reason, reviewed_at=db.now_iso())
        return ok(get_detail(conn, doc_id))


async def api_reopen(request: Request):
    doc_id = path_int(request, "doc_id")
    with db.session() as conn:
        row = get_row(conn, doc_id)
        if row["status"] not in (Status.APROVADO.value, Status.REJEITADO.value):
            raise ApiError(409, "Somente documentos aprovados ou rejeitados podem ser reabertos.")
        has_fields = conn.execute(
            "SELECT COUNT(*) FROM document_fields WHERE document_id = ?", (doc_id,)
        ).fetchone()[0]
        if not has_fields:
            raise ApiError(409, "Este documento não tem dados extraídos. Use “Reprocessar”.")
        set_status(conn, doc_id, Status.AGUARDANDO_REVISAO, "reaberto",
                   "Documento devolvido para revisão.", reviewed_at=None, rejection_reason=None)
        return ok(get_detail(conn, doc_id))


async def api_note(request: Request):
    doc_id = path_int(request, "doc_id")
    data = await read_json(request, NoteIn)
    with db.session() as conn:
        get_row(conn, doc_id)
        history.add(conn, doc_id, "observacao", data.text.strip())
        return ok(get_detail(conn, doc_id), 201)


routes = [
    Route("/api/documents/{doc_id}/fields", api_save_fields, methods=["PUT"]),
    Route("/api/documents/{doc_id}/approve", api_approve, methods=["POST"]),
    Route("/api/documents/{doc_id}/reject", api_reject, methods=["POST"]),
    Route("/api/documents/{doc_id}/reopen", api_reopen, methods=["POST"]),
    Route("/api/documents/{doc_id}/notes", api_note, methods=["POST"]),
]
