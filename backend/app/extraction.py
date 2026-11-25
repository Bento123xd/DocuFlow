"""Extração de dados — 100% local, sem envio a serviços externos.

Etapas:
1. Obter o texto do arquivo:
   - PDF com texto pesquisável: leitura direta do texto (pypdf);
   - imagem ou PDF digitalizado: OCR local com Tesseract, se instalado.
2. Localizar valores com regras simples e configuráveis por campo:
   procura os "rótulos de busca" do campo (ex.: "CNPJ", "Valor total") e lê o
   valor logo após o rótulo, conforme o tipo do campo (CPF/CNPJ, data, valor...).
3. O que não for encontrado fica como "Não identificado" (valor nulo).

Nenhum valor é inventado: só é preenchido o que aparece no texto do documento.
Todo resultado é uma sugestão e exige conferência humana.
"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import config
from .schemas import FieldDefOut
from .validators import format_cpf_cnpj, normalize_field, only_digits, parse_date, parse_money

log = logging.getLogger("docuflow.extraction")

METHOD_LABELS: dict[str, str] = {
    "pdf_texto": "Leitura do texto do PDF + regras de localização (local)",
    "ocr_local": "OCR local (Tesseract) + regras de localização",
    "sem_texto": "Sem texto legível — campos para preenchimento manual",
    "ocr_indisponivel": "OCR não disponível neste ambiente — campos para preenchimento manual",
    "simulado": "Simulação — dados fictícios de demonstração",
}


class ExtractionError(Exception):
    """Falha de leitura do arquivo (arquivo corrompido, protegido etc.)."""


@dataclass
class FieldResult:
    key: str
    label: str
    kind: str
    value: str | None
    source: str  # auto | nao_identificado
    evidence: str | None = None


@dataclass
class ExtractionResult:
    method: str
    note: str | None
    fields: list[FieldResult] = field(default_factory=list)


# ---------------------------------------------------------------- texto
@lru_cache(maxsize=1)
def ocr_status() -> tuple[bool, str]:
    """(disponível, idioma). Verificado uma vez por execução."""
    if not config.OCR_ENABLED:
        return False, ""
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401

        pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages(config="")
        return True, "por" if "por" in langs else "eng"
    except Exception:  # pragma: no cover - depende do ambiente
        return False, ""


def _ocr_image_bytes(data: bytes) -> str:
    import pytesseract
    from PIL import Image

    _, lang = ocr_status()
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        return pytesseract.image_to_string(img, lang=lang)


def read_text(path: Path, mime: str) -> tuple[str, str, str | None]:
    """Retorna (texto, método, observação)."""
    if mime == "application/pdf":
        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
        except ImportError:
            return "", "sem_texto", "Biblioteca de leitura de PDF (pypdf) não instalada."
        try:
            reader = PdfReader(str(path))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    raise ExtractionError("O PDF está protegido por senha e não pode ser lido.")
            pages = reader.pages[:20]
            text = "\n".join((p.extract_text() or "") for p in pages)
        except ExtractionError:
            raise
        except (PdfReadError, Exception) as exc:  # pypdf lança tipos variados
            log.info("Falha ao ler PDF %s: %s", path.name, exc)
            raise ExtractionError("Não foi possível ler o PDF. O arquivo pode estar corrompido ou incompleto.")
        if text.strip():
            note = "Somente as 20 primeiras páginas foram lidas." if len(reader.pages) > 20 else None
            return text, "pdf_texto", note
        available, _ = ocr_status()
        if not available:
            return "", "sem_texto", (
                "O PDF não contém texto pesquisável (provavelmente é digitalizado) "
                "e o OCR local não está disponível. Preencha os campos manualmente."
            )
        chunks: list[str] = []
        for page in pages:
            for image in getattr(page, "images", []):
                try:
                    chunks.append(_ocr_image_bytes(image.data))
                except Exception:
                    continue
        text = "\n".join(chunks)
        if text.strip():
            return text, "ocr_local", None
        return "", "sem_texto", "Não foi encontrado texto legível no PDF. Preencha os campos manualmente."

    # Imagens
    available, _ = ocr_status()
    if not available:
        _verify_image(path)
        return "", "ocr_indisponivel", (
            "O OCR local (Tesseract) não está instalado neste ambiente, então nenhum dado foi "
            "lido da imagem. Preencha os campos manualmente."
        )
    try:
        text = _ocr_image_bytes(path.read_bytes())
    except Exception as exc:
        log.info("Falha no OCR de %s: %s", path.name, exc)
        raise ExtractionError("Não foi possível ler a imagem. O arquivo pode estar corrompido.")
    if not text.strip():
        return "", "sem_texto", "O OCR não encontrou texto legível na imagem. Preencha os campos manualmente."
    return text, "ocr_local", "Texto obtido por OCR: confira com atenção, pode haver erros de leitura."


def _verify_image(path: Path) -> None:
    try:
        from PIL import Image
    except ImportError:
        return
    try:
        with Image.open(path) as img:
            img.verify()
    except Exception:
        raise ExtractionError("Não foi possível abrir a imagem. O arquivo pode estar corrompido.")


# ---------------------------------------------------------------- regras
def _fold_char(c: str) -> str:
    if c in "º°ª":
        return "o" if c != "ª" else "a"
    decomposed = unicodedata.normalize("NFKD", c)
    return (decomposed[0] if decomposed else c).lower()


def fold(text: str) -> str:
    """Remove acentos e passa a minúsculas preservando o comprimento."""
    return "".join(_fold_char(c) for c in text)


CNPJ_RE = re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)")
CPF_RE = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
DATE_RE = re.compile(r"(?<!\d)\d{1,2}[/.-]\d{1,2}[/.-]\d{4}(?!\d)")
MONEY_RE = re.compile(r"R\$\s*-?\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*-?\d+,\d{2}")
MONEY_LOOSE_RE = re.compile(r"(?<![\d.,])-?\d{1,3}(?:\.\d{3})*,\d{2}(?![\d,])")
NUMBER_RE = re.compile(r"^[\s:#.\-–]*([A-Za-z]{0,4}[\s\-]?\d[\d./\-]{0,29})")


def _find_by_kind(kind: str, segment: str) -> str | None:
    if kind == "cpf_cnpj":
        for rx in (CNPJ_RE, CPF_RE):
            m = rx.search(segment)
            if m:
                return format_cpf_cnpj(only_digits(m.group()))
        return None
    if kind == "data":
        for m in DATE_RE.finditer(segment):
            if parse_date(m.group()):
                return normalize_field("data", m.group())
        return None
    if kind == "valor":
        for rx in (MONEY_RE, MONEY_LOOSE_RE):
            m = rx.search(segment)
            if m and parse_money(m.group()) is not None:
                return normalize_field("valor", m.group())
        return None
    if kind == "numero":
        m = NUMBER_RE.match(segment)
        return m.group(1).strip(" .-") if m else None
    # texto
    value = segment.strip(" \t:-–|")
    if not value or not re.search(r"[A-Za-zÀ-ÿ]", value):
        return None
    return value[:120]


def _label_regex(label: str) -> re.Pattern[str]:
    folded = re.escape(fold(label.strip()))
    return re.compile(r"(?<![a-z0-9])" + folded + r"(?![a-z0-9])")


def _search_with_labels(fdef: FieldDefOut, lines: list[str], folded: list[str]) -> tuple[str, str] | None:
    for label in fdef.search_labels:
        rx = _label_regex(label)
        for i, fl in enumerate(folded):
            m = rx.search(fl)
            if not m:
                continue
            segment = lines[i][m.end():]
            value = _find_by_kind(fdef.kind, segment)
            if value is None and not segment.strip(" \t:-–"):
                # rótulo sozinho na linha: tenta a próxima linha não vazia
                for j in range(i + 1, min(i + 3, len(lines))):
                    if lines[j].strip():
                        value = _find_by_kind(fdef.kind, lines[j])
                        break
            if value is not None:
                return value, lines[i].strip()[:160]
    return None


_UNIQUE_FALLBACK = {"cpf_cnpj": (CNPJ_RE, CPF_RE), "data": (DATE_RE,), "valor": (MONEY_RE,)}


def _search_unique_pattern(kind: str, text: str) -> tuple[str, str] | None:
    """Sem rótulo: aceita apenas se houver UM único valor desse tipo no texto."""
    regexes = _UNIQUE_FALLBACK.get(kind)
    if not regexes:
        return None
    found: set[str] = set()
    for rx in regexes:
        for m in rx.finditer(text):
            v = _find_by_kind(kind, m.group())
            if v:
                found.add(v)
        if found:
            break
    if len(found) == 1:
        return found.pop(), "Único valor desse formato encontrado no documento"
    return None


def extract_fields(text: str, fields: list[FieldDefOut]) -> list[FieldResult]:
    lines = [ln for ln in text.splitlines()]
    folded = [fold(ln) for ln in lines]
    results: list[FieldResult] = []
    for f in fields:
        hit = _search_with_labels(f, lines, folded) if text else None
        if hit is None and text:
            hit = _search_unique_pattern(f.kind, text)
        if hit:
            results.append(FieldResult(f.key, f.label, f.kind, hit[0], "auto", hit[1]))
        else:
            results.append(FieldResult(f.key, f.label, f.kind, None, "nao_identificado", None))
    return results


def run(path: Path, mime: str, fields: list[FieldDefOut]) -> ExtractionResult:
    """Executa a extração completa. Lança ExtractionError se o arquivo for ilegível."""
    text, method, note = read_text(path, mime)
    return ExtractionResult(method=method, note=note, fields=extract_fields(text, fields))
