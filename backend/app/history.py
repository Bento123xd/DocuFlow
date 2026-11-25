"""Histórico de processamento (trilha de auditoria simples da demonstração)."""
from __future__ import annotations

import sqlite3

from . import config
from .db import now_iso
from .schemas import HistoryOut

ACTION_LABELS: dict[str, str] = {
    "recebido": "Documento recebido",
    "processamento_iniciado": "Processamento iniciado",
    "extracao_concluida": "Extração concluída",
    "erro": "Erro no processamento",
    "campos_corrigidos": "Campos corrigidos",
    "dados_alterados": "Dados do documento alterados",
    "tipo_alterado": "Tipo documental alterado",
    "aprovado": "Documento aprovado",
    "rejeitado": "Processamento rejeitado",
    "reaberto": "Revisão reaberta",
    "observacao": "Observação registrada",
}


def add(
    conn: sqlite3.Connection,
    document_id: int,
    action: str,
    detail: str | None = None,
    status_from: str | None = None,
    status_to: str | None = None,
    at: str | None = None,
    actor: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO history (document_id, at, action, status_from, status_to, detail, actor)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (document_id, at or now_iso(), action, status_from, status_to, detail, actor or config.ACTOR),
    )


def _row_to_out(row: sqlite3.Row) -> HistoryOut:
    return HistoryOut(
        id=row["id"],
        at=row["at"],
        action=row["action"],
        action_label=ACTION_LABELS.get(row["action"], row["action"]),
        status_from=row["status_from"],
        status_to=row["status_to"],
        detail=row["detail"],
        actor=row["actor"],
    )


def list_for(conn: sqlite3.Connection, document_id: int) -> list[HistoryOut]:
    rows = conn.execute(
        "SELECT * FROM history WHERE document_id = ? ORDER BY at DESC, id DESC", (document_id,)
    ).fetchall()
    return [_row_to_out(r) for r in rows]
