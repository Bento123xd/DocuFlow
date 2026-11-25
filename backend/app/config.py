"""Configuração central da demonstração DocuFlow.

Todos os caminhos podem ser alterados por variáveis de ambiente, para que os
dados de demonstração fiquem fora do código-fonte.
"""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

DATA_DIR = Path(os.environ.get("DOCUFLOW_DATA_DIR", BACKEND_DIR / "data"))
# Armazenamento privado: os arquivos só são entregues pela API
# (/api/documents/{id}/file), nunca por uma pasta pública.
STORAGE_DIR = DATA_DIR / "storage"
DB_PATH = DATA_DIR / "docuflow.db"

FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"
DEMO_ASSETS_DIR = BACKEND_DIR / "demo_assets"

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB

# Extensão -> tipo MIME aceito
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

# OCR local (Tesseract) é opcional. DOCUFLOW_OCR=0 desativa mesmo se instalado.
OCR_ENABLED = os.environ.get("DOCUFLOW_OCR", "1") != "0"

# Sem autenticação nesta demonstração: todas as ações são registradas
# em nome de um usuário genérico.
ACTOR = "Usuário da demonstração"

HOST = os.environ.get("DOCUFLOW_HOST", "127.0.0.1")
PORT = int(os.environ.get("DOCUFLOW_PORT", "8000"))
