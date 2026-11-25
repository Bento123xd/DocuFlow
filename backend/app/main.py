"""Aplicação web da demonstração DocuFlow (Starlette + Pydantic).

O FastAPI é construído sobre o Starlette; as rotas daqui podem ser migradas
para FastAPI com poucas mudanças quando o ambiente permitir.
"""
from __future__ import annotations

import logging

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import clients, config, dashboard, db, doctypes, documents, exports, review
from .common import ApiError

log = logging.getLogger("docuflow")


async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse({"error": exc.message, "details": exc.details}, status_code=exc.status_code)


async def http_error_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        messages = {404: "Recurso não encontrado.", 405: "Operação não permitida."}
        return JSONResponse({"error": messages.get(exc.status_code, exc.detail)}, status_code=exc.status_code)
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


async def unexpected_error_handler(request: Request, exc: Exception):
    log.exception("Erro inesperado em %s", request.url.path)
    return JSONResponse({"error": "Erro interno inesperado. Tente novamente."}, status_code=500)


class SecurityHeadersMiddleware:
    """Cabeçalhos básicos. Não substitui uma avaliação de segurança de produção."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"referrer-policy", b"no-referrer"))
                headers.append((b"x-frame-options", b"SAMEORIGIN"))
            await send(message)

        await self.app(scope, receive, send_wrapper)


def _frontend_routes() -> list:
    dist = config.FRONTEND_DIST
    index = dist / "index.html"

    async def spa(request: Request):
        if not index.exists():
            return PlainTextResponse(
                "Interface não encontrada. Gere o build do frontend (veja o README).", status_code=503
            )
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    routes: list = []
    if (dist / "assets").exists():
        routes.append(Mount("/assets", StaticFiles(directory=dist / "assets"), name="assets"))
    routes.append(Route("/{path:path}", spa, methods=["GET"]))
    return routes


async def api_not_found(request: Request):
    raise ApiError(404, "Recurso não encontrado.")


def create_app() -> Starlette:
    db.init_schema()
    with db.session() as conn:
        doctypes.ensure_default_type(conn)
    api_routes = [
        *dashboard.routes,
        *clients.routes,
        *doctypes.routes,
        *documents.routes,
        *review.routes,
        *exports.routes,
        Route("/api/{path:path}", api_not_found, methods=["GET", "POST", "PUT", "PATCH", "DELETE"]),
    ]
    return Starlette(
        routes=[*api_routes, *_frontend_routes()],
        middleware=[Middleware(SecurityHeadersMiddleware)],
        exception_handlers={
            ApiError: api_error_handler,
            HTTPException: http_error_handler,
            Exception: unexpected_error_handler,
        },
    )


app = create_app()
