"""Exportação.

1. CSV genérico da lista de documentos (com os campos revisados).
   NÃO é um formato SEDIF: serve apenas para conferência em planilha.

2. SEDIF: o exemplo de arquivo de importação ainda não foi fornecido pelo
   contador. Sem ele, nenhum layout, registro ou campo do SEDIF é reproduzido.
   O endpoint de status informa o que falta para essa etapa.
"""
from __future__ import annotations

import csv
import io
from datetime import date

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from . import db
from .common import STATUS_LABELS, ok
from .documents import _BASE_SELECT, build_filters, doc_code


def build_csv(params) -> str:
    with db.session() as conn:
        where, args = build_filters(params)
        rows = conn.execute(_BASE_SELECT + where + " ORDER BY d.received_at DESC, d.id DESC", args).fetchall()
        ids = [r["id"] for r in rows]
        fields_by_doc: dict[int, dict[str, str | None]] = {i: {} for i in ids}
        labels: list[str] = []
        if ids:
            q = f"SELECT document_id, label, value FROM document_fields WHERE document_id IN ({','.join('?' * len(ids))}) ORDER BY position"
            for f in conn.execute(q, ids):
                if f["label"] not in labels:
                    labels.append(f["label"])
                fields_by_doc[f["document_id"]][f["label"]] = f["value"]

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    writer.writerow(["Código", "Cliente", "Tipo documental", "Status", "Data de recebimento",
                     "Arquivo", "Dados de demonstração", *labels])
    for r in rows:
        received = date.fromisoformat(r["received_at"]).strftime("%d/%m/%Y")
        values = fields_by_doc.get(r["id"], {})
        writer.writerow([
            doc_code(r["id"]), r["client_name"], r["type_name"], STATUS_LABELS.get(r["status"], r["status"]),
            received, r["original_filename"], "Sim" if r["is_demo"] else "Não",
            *[(values.get(lbl) if values.get(lbl) is not None else ("Não identificado" if lbl in values else ""))
              for lbl in labels],
        ])
    return "﻿" + buf.getvalue()  # BOM para abrir acentuado no Excel


async def api_csv(request: Request):
    content = build_csv(request.query_params)
    filename = f"docuflow-documentos-{date.today().isoformat()}.csv"
    return Response(
        content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


SEDIF_STATUS = {
    "available": False,
    "summary": "Exportação SEDIF não implementada nesta demonstração.",
    "reason": "O exemplo de arquivo de importação do SEDIF ainda não foi fornecido. "
              "Sem esse material não é possível conhecer a estrutura do arquivo, os registros ou os campos, "
              "e nada foi presumido.",
    "missing": [
        "Exemplo real (com dados fictícios ou anonimizados) do arquivo que o contador importa no SEDIF.",
        "Lista dos documentos recebidos com maior frequência pelo escritório.",
        "Indicação de quais tipos documentais fornecem dados para o SEDIF.",
        "Validação, com o contador, de um arquivo gerado antes de qualquer uso real.",
    ],
    "not_included": [
        "Transmissão automática à SEFAZ, TED ou SEDIF.",
        "Geração de arquivo no layout SEDIF.",
        "Regras de cálculo, códigos de registro ou validações oficiais.",
    ],
}


async def api_sedif_status(request: Request):
    return ok(SEDIF_STATUS)


routes = [
    Route("/api/exports/documents.csv", api_csv, methods=["GET"]),
    Route("/api/exports/sedif/status", api_sedif_status, methods=["GET"]),
]
