"""Indicadores do painel, sempre calculados a partir do banco."""
from __future__ import annotations

from datetime import date, timedelta

from starlette.requests import Request
from starlette.routing import Route

from . import db
from .common import STATUS_LABELS, Status, ok
from .documents import doc_code
from .history import ACTION_LABELS
from .schemas import ActivityOut, DashboardOut

S = Status


def compute(conn) -> DashboardOut:
    by_status = {k: 0 for k in STATUS_LABELS}
    for r in conn.execute("SELECT status, COUNT(*) AS n FROM documents GROUP BY status"):
        by_status[r["status"]] = r["n"]
    total = sum(by_status.values())

    # Documentos ainda em aberto que possuem campos "Não identificado"
    with_unidentified = conn.execute(
        """SELECT COUNT(DISTINCT d.id) FROM documents d JOIN document_fields f ON f.document_id = d.id
           WHERE f.value IS NULL AND d.status IN (?, ?)""",
        (S.AGUARDANDO_REVISAO.value, S.RECEBIDO.value),
    ).fetchone()[0]

    week_ago = (date.today() - timedelta(days=6)).isoformat()
    last7 = conn.execute("SELECT COUNT(*) FROM documents WHERE received_at >= ?", (week_ago,)).fetchone()[0]

    rows = conn.execute(
        """SELECT h.*, c.name AS client_name FROM history h
           JOIN documents d ON d.id = h.document_id JOIN clients c ON c.id = d.client_id
           WHERE h.action != 'processamento_iniciado'
           ORDER BY h.at DESC, h.id DESC LIMIT 10"""
    ).fetchall()
    activity = [
        ActivityOut(
            id=r["id"], at=r["at"], action=r["action"], action_label=ACTION_LABELS.get(r["action"], r["action"]),
            detail=r["detail"], document_id=r["document_id"], document_code=doc_code(r["document_id"]),
            client_name=r["client_name"], status_to=r["status_to"],
        )
        for r in rows
    ]
    approved = by_status[S.APROVADO.value]
    rejected = by_status[S.REJEITADO.value]
    errors = by_status[S.ERRO.value]
    return DashboardOut(
        total=total,
        by_status=by_status,
        awaiting_review=by_status[S.AGUARDANDO_REVISAO.value],
        processed=approved + rejected,
        approved=approved,
        rejected=rejected,
        with_problems=errors + with_unidentified,
        errors=errors,
        with_unidentified=with_unidentified,
        received_last_7_days=last7,
        recent_activity=activity,
    )


async def api_dashboard(request: Request):
    with db.session() as conn:
        return ok(compute(conn))


async def api_meta(request: Request):
    from . import config, extraction

    ocr, lang = extraction.ocr_status()
    try:
        import pypdf  # noqa: F401
        pdf_text = True
    except ImportError:
        pdf_text = False
    return ok({
        "statuses": [{"id": k, "label": v} for k, v in STATUS_LABELS.items()],
        "capabilities": {"pdf_text": pdf_text, "ocr": ocr, "ocr_lang": lang or None},
        "max_upload_mb": config.MAX_UPLOAD_BYTES // (1024 * 1024),
        "today": date.today().isoformat(),
    })


routes = [
    Route("/api/dashboard", api_dashboard, methods=["GET"]),
    Route("/api/meta", api_meta, methods=["GET"]),
]
