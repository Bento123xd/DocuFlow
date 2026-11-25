"""Gera as imagens fictícias usadas na demonstração (requer Pillow).

Uso: python scripts/gerar_imagens_ficticias.py
Os arquivos já gerados acompanham o projeto; este script só é necessário
para recriá-los.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts", "/Library/Fonts"]


def font(size, bold=False):
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "arialbd.ttf" if bold else "arial.ttf"]
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def receipt(path, title, rows, footer_note, size=(900, 1200), tilt=0):
    img = Image.new("RGB", size, (252, 251, 247))
    d = ImageDraw.Draw(img)
    d.rectangle([30, 30, size[0] - 30, 90], fill=(236, 236, 232), outline=(170, 170, 165))
    d.text((48, 48), "DOCUMENTO FICTÍCIO — DEMONSTRAÇÃO DOCUFLOW", font=font(22, True), fill=(80, 80, 80))
    d.text((48, 130), title, font=font(40, True), fill=(20, 20, 20))
    y = 220
    for label, value in rows:
        d.text((48, y), f"{label}: {value}", font=font(28), fill=(25, 25, 25))
        y += 62
    d.line([48, y + 10, size[0] - 48, y + 10], fill=(160, 160, 160), width=2)
    d.text((48, y + 40), footer_note, font=font(20), fill=(110, 110, 110))
    d.text((48, size[1] - 80), "Dados fictícios. CPF/CNPJ com dígitos propositalmente inválidos.",
           font=font(20), fill=(120, 120, 120))
    if tilt:
        img = img.rotate(tilt, expand=True, fillcolor=(210, 210, 205))
    return img


def main():
    assets = ROOT / "backend" / "demo_assets"
    samples = ROOT / "amostras"
    assets.mkdir(parents=True, exist_ok=True)
    samples.mkdir(parents=True, exist_ok=True)

    receipt(assets / "foto-recibo-ficticio.jpg", "Recibo",
            [("Nome", "Padaria Trigo Bom ME"), ("CNPJ", "45.678.912/0001-07"),
             ("Data", "24/11/2026"), ("Referente a", "Fornecimento de pães — novembro")],
            "Valor ilegível na foto original (simulação).", tilt=1.2
            ).save(assets / "foto-recibo-ficticio.jpg", quality=85)

    receipt(samples / "exemplo-comprovante-ficticio.png", "Comprovante de pagamento",
            [("Nome", "Oficina Serra Azul Ltda"), ("CNPJ", "23.456.789/0001-10"),
             ("Data de emissão", "20/11/2026"), ("Número do documento", "CP-55120"),
             ("Valor total", "R$ 3.480,90")],
            "Imagem para testar o envio. Requer OCR local (Tesseract) para extração."
            ).save(samples / "exemplo-comprovante-ficticio.png")
    print("Imagens geradas.")


if __name__ == "__main__":
    main()
