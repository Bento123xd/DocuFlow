"""Gerador mínimo de PDFs fictícios para a demonstração (sem dependências).

Produz PDFs com texto pesquisável, marcados como "DOCUMENTO FICTÍCIO".
"""
from __future__ import annotations

W, H = 595, 842  # A4 em pontos


def _esc(text: str) -> bytes:
    raw = text.encode("cp1252", errors="replace")
    out = bytearray()
    for b in raw:
        if b in (0x28, 0x29, 0x5C):  # ( ) \
            out += b"\\" + bytes([b])
        elif b < 32 or b > 126:
            out += f"\\{b:03o}".encode()
        else:
            out.append(b)
    return bytes(out)


class _Page:
    def __init__(self) -> None:
        self.ops: list[bytes] = []

    def text(self, x: float, y: float, s: str, size: float = 11, bold: bool = False, gray: float = 0.0) -> None:
        font = b"F2" if bold else b"F1"
        self.ops.append(
            b"%.2f g BT /%s %.1f Tf %.1f %.1f Td (%s) Tj ET" % (gray, font, size, x, y, _esc(s))
        )

    def rect(self, x: float, y: float, w: float, h: float, stroke_gray: float = 0.6, fill_gray: float | None = None) -> None:
        if fill_gray is not None:
            self.ops.append(b"%.2f g %.1f %.1f %.1f %.1f re f" % (fill_gray, x, y, w, h))
        self.ops.append(b"%.2f G 0.8 w %.1f %.1f %.1f %.1f re S" % (stroke_gray, x, y, w, h))

    def line(self, x1: float, y1: float, x2: float, y2: float, gray: float = 0.75) -> None:
        self.ops.append(b"%.2f G 0.6 w %.1f %.1f m %.1f %.1f l S" % (gray, x1, y1, x2, y2))

    def watermark(self, s: str) -> None:
        # texto diagonal claro
        self.ops.append(b"0.92 g BT /F2 64 Tf 0.819 0.574 -0.574 0.819 120 260 Tm (%s) Tj ET" % _esc(s))


def build_pdf(page: _Page) -> bytes:
    content = b"\n".join(page.ops)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Contents 6 0 R "
        b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> >>" % (W, H),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def fictitious_document(title: str, issuer: list[tuple[str, str]], body: list[tuple[str, str]],
                        description: str | None = None) -> bytes:
    """Monta um documento fictício simples: cabeçalho, bloco do emitente e campos."""
    p = _Page()
    p.watermark("DEMONSTRAÇÃO")
    p.rect(40, 790, W - 80, 26, stroke_gray=0.55, fill_gray=0.95)
    p.text(52, 799, "DOCUMENTO FICTÍCIO — GERADO PARA DEMONSTRAÇÃO DO DOCUFLOW — SEM VALIDADE", 8.5, bold=True, gray=0.3)
    p.text(40, 745, title, 18, bold=True)
    y = 712
    p.line(40, y + 14, W - 40, y + 14)
    for label, value in issuer:
        p.text(40, y, f"{label}:", 10.5, bold=True, gray=0.25)
        p.text(170, y, value, 10.5)
        y -= 20
    y -= 8
    p.line(40, y + 12, W - 40, y + 12)
    y -= 14
    for label, value in body:
        p.text(40, y, f"{label}:", 11, bold=True, gray=0.25)
        p.text(170, y, value, 11)
        y -= 24
    if description:
        y -= 6
        p.text(40, y, "Descrição:", 11, bold=True, gray=0.25)
        y -= 18
        for chunk in _wrap(description, 88):
            p.text(40, y, chunk, 10.5, gray=0.15)
            y -= 15
    p.line(40, 80, W - 40, 80)
    p.text(40, 64, "Este arquivo contém apenas dados fictícios criados para a demonstração DocuFlow.", 8.5, gray=0.4)
    p.text(40, 52, "CPF/CNPJ fictícios com dígitos verificadores propositalmente inválidos.", 8.5, gray=0.4)
    return build_pdf(p)


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines
