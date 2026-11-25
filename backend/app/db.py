"""Acesso ao banco SQLite da demonstração.

O acesso fica concentrado aqui e nos módulos de repositório, para que a troca
por PostgreSQL no futuro afete poucas partes do código.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    document    TEXT NOT NULL,
    person_kind TEXT NOT NULL CHECK (person_kind IN ('PJ', 'PF')),
    city        TEXT,
    is_demo     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS doc_types (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    is_system   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS doc_type_fields (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    type_id       TEXT NOT NULL REFERENCES doc_types(id) ON DELETE CASCADE,
    key           TEXT NOT NULL,
    label         TEXT NOT NULL,
    kind          TEXT NOT NULL,
    search_labels TEXT NOT NULL DEFAULT '[]',
    position      INTEGER NOT NULL,
    UNIQUE (type_id, key)
);

CREATE TABLE IF NOT EXISTS documents (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id         INTEGER NOT NULL REFERENCES clients(id),
    type_id           TEXT NOT NULL REFERENCES doc_types(id),
    original_filename TEXT NOT NULL,
    stored_filename   TEXT NOT NULL,
    mime              TEXT NOT NULL,
    size_bytes        INTEGER NOT NULL,
    received_at       TEXT NOT NULL,
    uploaded_at       TEXT NOT NULL,
    status            TEXT NOT NULL,
    extraction_method TEXT,
    extraction_note   TEXT,
    error_message     TEXT,
    rejection_reason  TEXT,
    reviewed_at       TEXT,
    is_demo           INTEGER NOT NULL DEFAULT 0
);

-- Campos extraídos: cópia dos campos do tipo no momento da extração,
-- para que mudanças na configuração não alterem documentos já revisados.
CREATE TABLE IF NOT EXISTS document_fields (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    label       TEXT NOT NULL,
    kind        TEXT NOT NULL,
    value       TEXT,
    source      TEXT NOT NULL,
    evidence    TEXT,
    position    INTEGER NOT NULL,
    UNIQUE (document_id, key)
);

CREATE TABLE IF NOT EXISTS history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    at          TEXT NOT NULL,
    action      TEXT NOT NULL,
    status_from TEXT,
    status_to   TEXT,
    detail      TEXT,
    actor       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_client ON documents(client_id);
CREATE INDEX IF NOT EXISTS idx_history_document ON history(document_id);
CREATE INDEX IF NOT EXISTS idx_history_at ON history(at);
"""


def now_iso() -> str:
    """Data/hora local com fuso, em ISO 8601, sem microssegundos."""
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    """Abre uma conexão com transação: confirma no sucesso, desfaz no erro."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with session() as conn:
        conn.executescript(SCHEMA)
