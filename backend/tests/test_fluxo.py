"""Testes do fluxo principal da demonstração.

Executar (na pasta backend):  pip install -r requirements-dev.txt && python -m pytest -q
Usa um banco temporário: não altera os dados da demonstração.
"""
from __future__ import annotations

import os
import tempfile

import pytest

os.environ["DOCUFLOW_DATA_DIR"] = tempfile.mkdtemp(prefix="docuflow-test-")
os.environ["DOCUFLOW_OCR"] = "0"  # resultados determinísticos, independentes do Tesseract

from starlette.testclient import TestClient  # noqa: E402

from app import seed  # noqa: E402
from app.demo_pdf import fictitious_document  # noqa: E402
from app.main import app  # noqa: E402
from app.validators import check_field, cnpj_check, cpf_check, normalize_field  # noqa: E402


@pytest.fixture(scope="module")
def client():
    seed.reset()
    return TestClient(app)


def _pdf() -> bytes:
    return fictitious_document(
        "Recibo", [("Razão Social", "Teste Ltda"), ("CNPJ", "11.222.333/0001-00")],
        [("Valor total", "R$ 99,90"), ("Data de emissão", "01/11/2026")],
    )


def test_painel_calculado_dos_dados(client):
    d = client.get("/api/dashboard").json()
    assert d["total"] == sum(d["by_status"].values()) == 15
    assert d["awaiting_review"] == d["by_status"]["aguardando_revisao"]
    assert d["processed"] == d["approved"] + d["rejected"]


def test_upload_extrai_e_aguarda_revisao(client):
    r = client.post("/api/documents", files={"file": ("t.pdf", _pdf(), "application/pdf")},
                    data={"client_id": "1", "type_id": "outro", "received_at": "2026-11-20"})
    assert r.status_code == 201
    doc = r.json()
    assert doc["status"] == "aguardando_revisao"
    fields = {f["key"]: f for f in doc["fields"]}
    assert fields["valor"]["value"] == "99,90" and fields["valor"]["source"] == "auto"
    assert fields["numero_do_documento"]["value"] is None  # não está no arquivo: não inventa
    assert fields["numero_do_documento"]["source"] == "nao_identificado"


@pytest.mark.parametrize("name,content,expected", [
    ("x.txt", b"abc", 415),
    ("x.pdf", b"nao-e-pdf", 415),
    ("x.pdf", b"", 422),
])
def test_upload_rejeita_arquivos_invalidos(client, name, content, expected):
    r = client.post("/api/documents", files={"file": (name, content, "application/octet-stream")}, data={"client_id": "1"})
    assert r.status_code == expected
    assert r.json()["error"]


def test_aprovacao_exige_acao_e_campos_validos(client):
    doc = client.post("/api/documents", files={"file": ("t.pdf", _pdf(), "application/pdf")},
                      data={"client_id": "2"}).json()
    i = doc["id"]
    bad = client.post(f"/api/documents/{i}/approve", json={"fields": [{"key": "data_do_documento", "value": "31/02/2026"}]})
    assert bad.status_code == 422
    assert client.get(f"/api/documents/{i}").json()["status"] == "aguardando_revisao"
    ok = client.post(f"/api/documents/{i}/approve", json={"fields": [{"key": "valor", "value": "1234,5"}], "note": "ok"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "aprovado"
    assert {f["key"]: f for f in body["fields"]}["valor"] == {**{f["key"]: f for f in body["fields"]}["valor"],
                                                            "value": "1.234,50", "source": "manual"}
    assert client.post(f"/api/documents/{i}/approve", json={}).status_code == 409


def test_rejeitar_reabrir_e_observacao(client):
    doc = client.post("/api/documents", files={"file": ("t.pdf", _pdf(), "application/pdf")},
                      data={"client_id": "3"}).json()
    i = doc["id"]
    assert client.post(f"/api/documents/{i}/reject", json={"reason": "x"}).status_code == 422
    assert client.post(f"/api/documents/{i}/reject", json={"reason": "Ilegível"}).json()["status"] == "rejeitado"
    assert client.post(f"/api/documents/{i}/reopen").json()["status"] == "aguardando_revisao"
    hist = client.post(f"/api/documents/{i}/notes", json={"text": "Cliente avisado"}).json()["history"]
    assert hist[0]["action"] == "observacao"


def test_arquivo_corrompido_vai_para_erro(client):
    errored = client.get("/api/documents?status=erro").json()["items"][0]
    r = client.post(f"/api/documents/{errored['id']}/process").json()
    assert r["status"] == "erro" and r["error_message"]


def test_filtros_e_csv(client):
    assert client.get("/api/documents?client_id=1&status=aprovado").json()["total"] >= 1
    r = client.get("/api/exports/documents.csv?status=aprovado")
    assert r.status_code == 200 and "Código;Cliente" in r.text


def test_sedif_nao_gera_arquivo(client):
    s = client.get("/api/exports/sedif/status").json()
    assert s["available"] is False and s["missing"]


def test_tipo_outro_obrigatorio(client):
    assert client.delete("/api/doc-types/outro").status_code == 409
    dup = client.post("/api/doc-types", json={"name": "T", "fields": [{"label": "A", "kind": "texto"},
                                                                     {"label": "a", "kind": "texto"}]})
    assert dup.status_code == 422


def test_validadores():
    # Sem números reais: para uma base qualquer, exatamente 1 dos 100 pares de DV deve ser válido.
    assert sum(cpf_check(f"123456789{dv:02d}") for dv in range(100)) == 1
    assert sum(cnpj_check(f"123456780001{dv:02d}") for dv in range(100)) == 1
    assert not cpf_check("11111111111") and not cnpj_check("12345678000100")
    assert normalize_field("valor", "1234.5") == "1.234,50"
    assert check_field("data", "32/01/2026")[0]
    assert check_field("cpf_cnpj", "123")[0]


def test_dados_demo_tem_dv_invalido():
    seed._assert_fictitious_ids()
