"""Validações determinísticas de formato.

Aqui só entram regras públicas e objetivas (dígitos verificadores de CPF/CNPJ,
formato de data e de valor monetário). Nenhuma regra fiscal é presumida.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

FIELD_KINDS: dict[str, str] = {
    "texto": "Texto",
    "cpf_cnpj": "CPF ou CNPJ",
    "data": "Data",
    "valor": "Valor (R$)",
    "numero": "Número / código",
}


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def cpf_check(digits: str) -> bool:
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(digits[i]) * (size + 1 - i) for i in range(size))
        dv = (total * 10) % 11 % 10
        if dv != int(digits[size]):
            return False
    return True


def cnpj_check(digits: str) -> bool:
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6] + weights1
    for weights, pos in ((weights1, 12), (weights2, 13)):
        total = sum(int(digits[i]) * w for i, w in enumerate(weights))
        rest = total % 11
        dv = 0 if rest < 2 else 11 - rest
        if dv != int(digits[pos]):
            return False
    return True


def format_cpf_cnpj(digits: str) -> str:
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return digits


_DATE_RE = re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\s*$")


def parse_date(value: str) -> date | None:
    m = _DATE_RE.match(value or "")
    if not m:
        return None
    d, mo, y = (int(g) for g in m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


_MONEY_BR = re.compile(r"^-?(\d{1,3}(\.\d{3})+|\d+)(,\d{1,2})?$")


def parse_money(value: str) -> Decimal | None:
    raw = (value or "").strip().replace("R$", "").replace(" ", "")
    if not raw:
        return None
    if _MONEY_BR.match(raw):
        normalized = raw.replace(".", "").replace(",", ".")
    elif re.match(r"^-?\d+\.\d{1,2}$", raw):  # 1234.56
        normalized = raw
    else:
        return None
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def format_money(amount: Decimal) -> str:
    q = f"{amount:,.2f}"  # 1,234.56
    return q.replace(",", "X").replace(".", ",").replace("X", ".")


def check_field(kind: str, value: str | None) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos). Erros impedem aprovação; avisos só alertam."""
    errors: list[str] = []
    warnings: list[str] = []
    if value is None or not value.strip():
        return errors, warnings
    if kind == "cpf_cnpj":
        digits = only_digits(value)
        if len(digits) == 11:
            if not cpf_check(digits):
                warnings.append("Dígito verificador do CPF não confere.")
        elif len(digits) == 14:
            if not cnpj_check(digits):
                warnings.append("Dígito verificador do CNPJ não confere.")
        else:
            errors.append("Informe 11 dígitos (CPF) ou 14 dígitos (CNPJ).")
    elif kind == "data":
        if parse_date(value) is None:
            errors.append("Data inválida. Use o formato DD/MM/AAAA.")
    elif kind == "valor":
        if parse_money(value) is None:
            errors.append("Valor inválido. Use o formato 1.234,56.")
    return errors, warnings


def normalize_field(kind: str, value: str | None) -> str | None:
    """Padroniza a apresentação quando o valor é válido; caso contrário mantém."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if kind == "cpf_cnpj":
        digits = only_digits(value)
        if len(digits) in (11, 14):
            return format_cpf_cnpj(digits)
    elif kind == "data":
        parsed = parse_date(value)
        if parsed:
            return parsed.strftime("%d/%m/%Y")
    elif kind == "valor":
        parsed = parse_money(value)
        if parsed is not None:
            return format_money(parsed)
    return value[:500]
