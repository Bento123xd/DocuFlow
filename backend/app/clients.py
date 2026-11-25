"""Clientes fictícios da demonstração (somente leitura).

O cadastro real de clientes está fora do escopo desta versão.
"""
from __future__ import annotations

import sqlite3

from starlette.requests import Request
from starlette.routing import Route

from . import db
from .common import ApiError, Status, ok
from .schemas import ClientOut


def list_clients(conn: sqlite3.Connection) -> list[ClientOut]:
    rows = conn.execute(
        """
        SELECT c.*,
               COUNT(d.id) AS document_count,
               SUM(CASE WHEN d.status = ? THEN 1 ELSE 0 END) AS pending_count
        FROM clients c LEFT JOIN documents d ON d.client_id = c.id
        GROUP BY c.id ORDER BY c.name
        """,
        (Status.AGUARDANDO_REVISAO.value,),
    ).fetchall()
    return [
        ClientOut(
            id=r["id"],
            name=r["name"],
            document=r["document"],
            person_kind=r["person_kind"],
            city=r["city"],
            is_demo=bool(r["is_demo"]),
            document_count=r["document_count"] or 0,
            pending_count=r["pending_count"] or 0,
        )
        for r in rows
    ]


def ensure_exists(conn: sqlite3.Connection, client_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not row:
        raise ApiError(422, "Cliente não encontrado. Selecione um cliente da lista.")
    return row


async def api_list(request: Request):
    with db.session() as conn:
        return ok(list_clients(conn))


routes = [Route("/api/clients", api_list, methods=["GET"])]
