"""Inicia a demonstração DocuFlow.

    python run.py            # inicia (cria dados fictícios na primeira execução)
    python run.py --reset    # apaga os dados locais e recria a demonstração
"""
from __future__ import annotations

import argparse
import logging

import uvicorn

from app import config, db, seed


def main() -> None:
    parser = argparse.ArgumentParser(description="DocuFlow — demonstração local")
    parser.add_argument("--reset", action="store_true", help="apaga os dados locais e recria a demonstração")
    parser.add_argument("--host", default=config.HOST)
    parser.add_argument("--port", type=int, default=config.PORT)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.reset:
        seed.reset()
        print("Dados de demonstração recriados.")
    else:
        db.init_schema()
        if seed.seed_if_empty():
            print("Dados de demonstração criados.")

    from app.extraction import ocr_status

    ocr, lang = ocr_status()
    print(f"OCR local: {'disponível (' + lang + ')' if ocr else 'não disponível — imagens exigirão preenchimento manual'}")
    print(f"DocuFlow (demonstração) em http://{args.host}:{args.port}")
    from app.main import app

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
