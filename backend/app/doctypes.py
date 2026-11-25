"""Configuração dos tipos documentais e dos campos de cada tipo.

A lista de documentos frequentes do escritório ainda não foi recebida. Por isso
apenas o tipo "Outro" vem configurado; novos tipos são cadastrados pela tela de
configuração quando forem validados com o contador.
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata

from starlette.requests import Request
from starlette.routing import Route

from . import db
from .common import ApiError, ok, read_json
from .schemas import DocTypeIn, DocTypeOut, FieldDefIn, FieldDefOut

DEFAULT_TYPE_ID = "outro"

# Campos genéricos citados nas instruções do projeto (não são campos fiscais).
DEFAULT_FIELDS: list[FieldDefIn] = [
    FieldDefIn(label="Nome", kind="texto", search_labels=["Nome", "Razão Social", "Emitente"]),
    FieldDefIn(label="CPF ou CNPJ", kind="cpf_cnpj", search_labels=["CNPJ", "CPF"]),
    FieldDefIn(label="Data do documento", kind="data", search_labels=["Data de emissão", "Data do documento", "Data"]),
    FieldDefIn(label="Valor", kind="valor", search_labels=["Valor total", "Total", "Valor"]),
    FieldDefIn(label="Número do documento", kind="numero", search_labels=["Número do documento", "Número", "Nº"]),
]


def slugify(text: str) -> str:
    base = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-zA-Z0-9]+", "_", base).strip("_").lower()
    return base or "campo"


def _field_rows(conn: sqlite3.Connection, type_id: str) -> list[FieldDefOut]:
    rows = conn.execute(
        "SELECT * FROM doc_type_fields WHERE type_id = ? ORDER BY position", (type_id,)
    ).fetchall()
    return [
        FieldDefOut(
            key=r["key"],
            label=r["label"],
            kind=r["kind"],
            search_labels=json.loads(r["search_labels"] or "[]"),
            position=r["position"],
        )
        for r in rows
    ]


def get_fields(conn: sqlite3.Connection, type_id: str) -> list[FieldDefOut]:
    return _field_rows(conn, type_id)


def _to_out(conn: sqlite3.Connection, row: sqlite3.Row) -> DocTypeOut:
    count = conn.execute("SELECT COUNT(*) FROM documents WHERE type_id = ?", (row["id"],)).fetchone()[0]
    return DocTypeOut(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        is_system=bool(row["is_system"]),
        fields=_field_rows(conn, row["id"]),
        document_count=count,
    )


def list_types(conn: sqlite3.Connection) -> list[DocTypeOut]:
    rows = conn.execute("SELECT * FROM doc_types ORDER BY is_system ASC, name").fetchall()
    return [_to_out(conn, r) for r in rows]


def ensure_exists(conn: sqlite3.Connection, type_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM doc_types WHERE id = ?", (type_id,)).fetchone()
    if not row:
        raise ApiError(422, "Tipo documental não encontrado.")
    return row


def _write_fields(conn: sqlite3.Connection, type_id: str, fields: list[FieldDefIn]) -> None:
    conn.execute("DELETE FROM doc_type_fields WHERE type_id = ?", (type_id,))
    used: set[str] = set()
    for pos, f in enumerate(fields):
        key = slugify(f.label)
        candidate, n = key, 2
        while candidate in used:
            candidate = f"{key}_{n}"
            n += 1
        used.add(candidate)
        conn.execute(
            "INSERT INTO doc_type_fields (type_id, key, label, kind, search_labels, position)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (type_id, candidate, f.label, f.kind, json.dumps(f.search_labels, ensure_ascii=False), pos),
        )


def _check_name_free(conn: sqlite3.Connection, name: str, except_id: str | None = None) -> None:
    row = conn.execute(
        "SELECT id FROM doc_types WHERE lower(name) = lower(?) AND id != ?", (name, except_id or "")
    ).fetchone()
    if row:
        raise ApiError(409, f"Já existe um tipo documental chamado “{name}”.")


def create_type(conn: sqlite3.Connection, data: DocTypeIn, is_system: bool = False, type_id: str | None = None) -> str:
    _check_name_free(conn, data.name)
    base = type_id or slugify(data.name)
    candidate, n = base, 2
    while conn.execute("SELECT 1 FROM doc_types WHERE id = ?", (candidate,)).fetchone():
        candidate = f"{base}_{n}"
        n += 1
    conn.execute(
        "INSERT INTO doc_types (id, name, description, is_system, created_at) VALUES (?, ?, ?, ?, ?)",
        (candidate, data.name, data.description, 1 if is_system else 0, db.now_iso()),
    )
    _write_fields(conn, candidate, data.fields)
    return candidate


def ensure_default_type(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM doc_types WHERE id = ?", (DEFAULT_TYPE_ID,)).fetchone():
        return
    create_type(
        conn,
        DocTypeIn(
            name="Outro",
            description="Tipo genérico para documentos ainda não classificados. "
            "Os tipos específicos do escritório serão configurados após o recebimento da lista do contador.",
            fields=DEFAULT_FIELDS,
        ),
        is_system=True,
        type_id=DEFAULT_TYPE_ID,
    )


# ---------- Rotas ----------
async def api_list(request: Request):
    with db.session() as conn:
        return ok(list_types(conn))


async def api_create(request: Request):
    data = await read_json(request, DocTypeIn)
    with db.session() as conn:
        new_id = create_type(conn, data)
        return ok(_to_out(conn, ensure_exists(conn, new_id)), 201)


async def api_update(request: Request):
    type_id = request.path_params["type_id"]
    data = await read_json(request, DocTypeIn)
    with db.session() as conn:
        row = conn.execute("SELECT * FROM doc_types WHERE id = ?", (type_id,)).fetchone()
        if not row:
            raise ApiError(404, "Tipo documental não encontrado.")
        _check_name_free(conn, data.name, except_id=type_id)
        conn.execute(
            "UPDATE doc_types SET name = ?, description = ? WHERE id = ?",
            (data.name, data.description, type_id),
        )
        _write_fields(conn, type_id, data.fields)
        return ok(_to_out(conn, ensure_exists(conn, type_id)))


async def api_delete(request: Request):
    type_id = request.path_params["type_id"]
    with db.session() as conn:
        row = conn.execute("SELECT * FROM doc_types WHERE id = ?", (type_id,)).fetchone()
        if not row:
            raise ApiError(404, "Tipo documental não encontrado.")
        if row["is_system"]:
            raise ApiError(409, "O tipo “Outro” é obrigatório e não pode ser excluído.")
        used = conn.execute("SELECT COUNT(*) FROM documents WHERE type_id = ?", (type_id,)).fetchone()[0]
        if used:
            raise ApiError(409, f"Este tipo está em uso por {used} documento(s) e não pode ser excluído.")
        conn.execute("DELETE FROM doc_types WHERE id = ?", (type_id,))
        return ok({"deleted": type_id})


routes = [
    Route("/api/doc-types", api_list, methods=["GET"]),
    Route("/api/doc-types", api_create, methods=["POST"]),
    Route("/api/doc-types/{type_id}", api_update, methods=["PUT"]),
    Route("/api/doc-types/{type_id}", api_delete, methods=["DELETE"]),
]
