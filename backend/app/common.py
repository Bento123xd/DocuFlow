"""Utilidades compartilhadas: status, erros da API e leitura de corpo JSON."""
from __future__ import annotations

import json
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse


class Status(str, Enum):
    RECEBIDO = "recebido"
    EM_PROCESSAMENTO = "em_processamento"
    AGUARDANDO_REVISAO = "aguardando_revisao"
    APROVADO = "aprovado"
    REJEITADO = "rejeitado"
    ERRO = "erro"


STATUS_LABELS: dict[str, str] = {
    Status.RECEBIDO.value: "Recebido",
    Status.EM_PROCESSAMENTO.value: "Em processamento",
    Status.AGUARDANDO_REVISAO.value: "Aguardando revisão",
    Status.APROVADO.value: "Aprovado",
    Status.REJEITADO.value: "Rejeitado",
    Status.ERRO.value: "Erro",
}


class ApiError(Exception):
    """Erro com mensagem pronta para exibição ao usuário."""

    def __init__(self, status_code: int, message: str, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.details = details


M = TypeVar("M", bound=BaseModel)

_PYDANTIC_MSGS = {
    "missing": "campo obrigatório",
    "string_too_short": "texto muito curto",
    "string_too_long": "texto muito longo",
    "too_short": "itens insuficientes",
    "too_long": "itens demais",
    "enum": "valor não permitido",
    "literal_error": "valor não permitido",
    "int_parsing": "número inválido",
    "date_from_datetime_parsing": "data inválida",
    "date_parsing": "data inválida",
}


def _translate(err: dict[str, Any]) -> str:
    loc = ".".join(str(p) for p in err.get("loc", ()))
    if err.get("type") == "value_error":
        msg = str(err.get("ctx", {}).get("error", err.get("msg", "valor inválido")))
    else:
        msg = _PYDANTIC_MSGS.get(err.get("type", ""), err.get("msg", "valor inválido"))
    return f"{loc}: {msg}" if loc else msg


async def read_json(request: Request, model: type[M]) -> M:
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError(400, "O corpo da requisição não é um JSON válido.")
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        problems = [_translate(e) for e in exc.errors()]
        raise ApiError(422, "Dados inválidos: " + "; ".join(problems), problems)


def ok(data: Any, status_code: int = 200) -> JSONResponse:
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
    elif isinstance(data, list):
        data = [d.model_dump(mode="json") if isinstance(d, BaseModel) else d for d in data]
    return JSONResponse(data, status_code=status_code)


def path_int(request: Request, name: str) -> int:
    try:
        return int(request.path_params[name])
    except (KeyError, ValueError):
        raise ApiError(404, "Registro não encontrado.")
