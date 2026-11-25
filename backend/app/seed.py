"""Dados de demonstração — todos fictícios.

- Clientes e documentos inventados, marcados como demonstração (is_demo = 1).
- CPF/CNPJ com dígitos verificadores propositalmente INVÁLIDOS, para garantir
  que não correspondam a pessoas ou empresas reais.
- Os campos dos documentos pré-carregados são uma SIMULAÇÃO de extração
  (origem "simulado"). Documentos enviados pelo usuário passam pela extração
  local real (ver extraction.py).
"""
from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from . import config, db, doctypes, history
from .common import Status
from .demo_pdf import fictitious_document
from .validators import cnpj_check, cpf_check, only_digits

CLIENTS = [
    ("Comercial Aurora Ltda", "12.345.678/0001-00", "PJ", "Campinas/SP"),
    ("Oficina Serra Azul Ltda", "23.456.789/0001-10", "PJ", "Sorocaba/SP"),
    ("Clínica Bem-Viver Ltda", "34.567.891/0001-20", "PJ", "Ribeirão Preto/SP"),
    ("Marcos Vinícius Exemplo", "123.456.789-00", "PF", "Campinas/SP"),
    ("Padaria Trigo Bom ME", "45.678.912/0001-07", "PJ", "Jundiaí/SP"),
]

# chaves dos campos do tipo "Outro"
NOME, DOC, DATA, VALOR, NUM = "nome", "cpf_ou_cnpj", "data_do_documento", "valor", "numero_do_documento"


@dataclass
class DemoDoc:
    days_ago: int
    client: int  # índice em CLIENTS
    filename: str
    title: str
    values: dict[str, str | None]
    status: Status
    kind: str = "pdf"  # pdf | jpg | corrupt_pdf | corrupt_png
    description: str | None = None
    corrected: dict[str, str] = field(default_factory=dict)  # campo -> valor corrigido manualmente
    note: str | None = None
    reason: str | None = None  # rejeição ou erro


def _d(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def _docs(today: date) -> list[DemoDoc]:
    t = lambda n: _d(today - timedelta(days=n))  # noqa: E731
    return [
        DemoDoc(0, 0, "recibo-manutencao-aurora.pdf", "Recibo de Prestação de Serviços",
                {NOME: "Comercial Aurora Ltda", DOC: "12.345.678/0001-00", DATA: t(1), VALOR: "1.250,00", NUM: "REC-2026/0418"},
                Status.AGUARDANDO_REVISAO,
                description="Serviços de manutenção preventiva em equipamentos de refrigeração."),
        DemoDoc(0, 2, "comprovante-pagamento-bemviver.pdf", "Comprovante de Pagamento",
                {NOME: None, DOC: "34.567.891/0001-20", DATA: t(0), VALOR: "780,40", NUM: None},
                Status.AGUARDANDO_REVISAO,
                description="Comprovante sem identificação do pagador e sem número de documento."),
        DemoDoc(1, 1, "fatura-servicos-serra-azul.pdf", "Fatura de Serviços",
                {NOME: "Oficina Serra Azul Ltda", DOC: "23.456.789/0001-10", DATA: t(2), VALOR: "3.912,75", NUM: "FAT-10233"},
                Status.AGUARDANDO_REVISAO,
                description="Revisão de frota: troca de óleo, filtros e alinhamento."),
        DemoDoc(1, 4, "foto-recibo-padaria.jpg", "Recibo (foto)",
                {NOME: "Padaria Trigo Bom ME", DOC: "45.678.912/0001-07", DATA: t(1), VALOR: None, NUM: None},
                Status.AGUARDANDO_REVISAO, kind="jpg"),
        DemoDoc(0, 1, "orcamento-pecas-serra-azul.pdf", "Orçamento de Peças",
                {}, Status.RECEBIDO,
                description="Documento recém-recebido, ainda não processado. Use “Processar documento” "
                            "para executar a extração local real sobre este arquivo fictício."),
        DemoDoc(2, 3, "recibo-aluguel-marcos.pdf", "Recibo de Aluguel",
                {NOME: "Marcos Vinícius Exemplo", DOC: "123.456.789-00", DATA: t(3), VALOR: "2.100,00", NUM: "AL-11/2026"},
                Status.APROVADO, note="Conferido com o contrato fictício do cliente."),
        DemoDoc(3, 0, "nota-compra-material-aurora.pdf", "Comprovante de Compra",
                {NOME: "Comercial Aurora Ltda", DOC: "12.345.678/0001-00", DATA: t(4), VALOR: "645,90", NUM: "CC-7781"},
                Status.APROVADO, corrected={VALOR: "654,90"}),
        DemoDoc(4, 1, "recibo-servico-terceiro.pdf", "Recibo de Prestação de Serviços",
                {NOME: "Oficina Serra Azul Ltda", DOC: "23.456.789/0001-10", DATA: t(5), VALOR: "450,00", NUM: "RPS-0091"},
                Status.APROVADO),
        DemoDoc(5, 2, "fatura-laboratorio-bemviver.pdf", "Fatura de Serviços",
                {NOME: "Clínica Bem-Viver Ltda", DOC: "34.567.891/0001-20", DATA: t(6), VALOR: "5.320,00", NUM: None},
                Status.APROVADO, note="Fatura sem número; aprovada mesmo assim, conforme orientação do contador (simulação)."),
        DemoDoc(6, 4, "recibo-fornecedor-padaria.pdf", "Recibo",
                {NOME: "Padaria Trigo Bom ME", DOC: "45.678.912/0001-07", DATA: t(7), VALOR: "318,00", NUM: "R-2231"},
                Status.REJEITADO, reason="Documento duplicado: o mesmo recibo já havia sido enviado pelo cliente."),
        DemoDoc(2, 0, "extrato-ilegivel-aurora.pdf", "", {}, Status.ERRO, kind="corrupt_pdf",
                reason="Não foi possível ler o PDF. O arquivo pode estar corrompido ou incompleto."),
        DemoDoc(8, 3, "foto-documento-marcos.png", "", {}, Status.ERRO, kind="corrupt_png",
                reason="Não foi possível abrir a imagem. O arquivo pode estar corrompido."),
        DemoDoc(10, 2, "recibo-consultoria-bemviver.pdf", "Recibo de Prestação de Serviços",
                {NOME: "Clínica Bem-Viver Ltda", DOC: "34.567.891/0001-20", DATA: t(11), VALOR: "1.800,00", NUM: "RPS-0412"},
                Status.APROVADO),
        DemoDoc(12, 0, "comprovante-energia-aurora.pdf", "Comprovante de Pagamento",
                {NOME: "Comercial Aurora Ltda", DOC: "12.345.678/0001-00", DATA: t(13), VALOR: "987,12", NUM: "CP-30018"},
                Status.APROVADO, corrected={NUM: "CP-30019"}),
        DemoDoc(15, 4, "recibo-equipamento-padaria.pdf", "Recibo",
                {NOME: "Padaria Trigo Bom ME", DOC: "45.678.912/0001-07", DATA: t(16), VALOR: "2.450,00", NUM: "R-2101"},
                Status.APROVADO),
    ]


def _file_bytes(doc: DemoDoc, client: tuple) -> bytes:
    if doc.kind == "jpg":
        return (config.DEMO_ASSETS_DIR / "foto-recibo-ficticio.jpg").read_bytes()
    if doc.kind == "corrupt_pdf":
        return b"%PDF-1.4\n% arquivo ficticio propositalmente incompleto para demonstrar erro\n1 0 obj\n<<"
    if doc.kind == "corrupt_png":
        return b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    v = doc.values
    labels = {NOME: "Razão Social" if client[2] == "PJ" else "Nome", DOC: "CNPJ" if client[2] == "PJ" else "CPF"}
    issuer = [(labels[NOME], v[NOME])] if v.get(NOME) else []
    if v.get(DOC):
        issuer.append((labels[DOC], v[DOC]))
    if not v:  # documento "Recebido" ainda sem extração: conteúdo completo no arquivo
        issuer = [("Razão Social", client[0]), ("CNPJ", client[1])]
        body = [("Número do documento", "ORC-2026-118"), ("Data de emissão", _d(date.today())), ("Valor total", "R$ 1.074,30")]
    else:
        body = []
        if v.get(NUM):
            body.append(("Número do documento", v[NUM]))
        if v.get(DATA):
            body.append(("Data de emissão", v[DATA]))
        if v.get(VALOR):
            body.append(("Valor total", f"R$ {doc.corrected.get(VALOR, v[VALOR])}"))
    if doc.corrected.get(NUM):
        body = [(k, doc.corrected[NUM] if k == "Número do documento" else val) for k, val in body]
    return fictitious_document(doc.title, issuer, body, doc.description)


def _assert_fictitious_ids() -> None:
    for _, number, kind, _ in CLIENTS:
        digits = only_digits(number)
        valid = cpf_check(digits) if kind == "PF" else cnpj_check(digits)
        assert not valid, f"Documento de demonstração {number} tem DV válido; use um número inválido."


def seed_if_empty() -> bool:
    """Cria clientes e documentos fictícios se o banco estiver vazio."""
    _assert_fictitious_ids()
    with db.session() as conn:
        doctypes.ensure_default_type(conn)
        if conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]:
            return False
        client_ids = []
        for name, number, kind, city in CLIENTS:
            cur = conn.execute(
                "INSERT INTO clients (name, document, person_kind, city, is_demo) VALUES (?, ?, ?, ?, 1)",
                (name, number, kind, city),
            )
            client_ids.append(cur.lastrowid)

        fields = doctypes.get_fields(conn, doctypes.DEFAULT_TYPE_ID)
        today = date.today()
        # mais antigos primeiro, para os códigos seguirem a ordem cronológica
        docs = sorted(_docs(today), key=lambda d: -d.days_ago)
        for i, doc in enumerate(docs):
            client = CLIENTS[doc.client]
            day = today - timedelta(days=doc.days_ago)
            start = datetime.combine(day, time(8, 5)) + timedelta(minutes=23 * i)
            if day == today and start > datetime.now():
                start = datetime.now() - timedelta(minutes=5 * (len(docs) - i))
            ts = lambda minutes: (start + timedelta(minutes=minutes)).astimezone().replace(microsecond=0).isoformat()  # noqa: E731

            ext = "." + doc.filename.rsplit(".", 1)[-1]
            mime = config.ALLOWED_EXTENSIONS[ext]
            content = _file_bytes(doc, client)
            stored = f"{uuid.uuid4().hex}{ext}"
            (config.STORAGE_DIR / stored).write_bytes(content)

            cur = conn.execute(
                "INSERT INTO documents (client_id, type_id, original_filename, stored_filename, mime, size_bytes,"
                " received_at, uploaded_at, status, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (client_ids[doc.client], doctypes.DEFAULT_TYPE_ID, doc.filename, stored, mime, len(content),
                 day.isoformat(), ts(0), Status.RECEBIDO.value),
            )
            doc_id = cur.lastrowid
            history.add(conn, doc_id, "recebido", f"Arquivo “{doc.filename}” recebido (dados de demonstração).",
                        status_to=Status.RECEBIDO.value, at=ts(0))
            if doc.status == Status.RECEBIDO:
                continue

            history.add(conn, doc_id, "processamento_iniciado", "Tipo documental: Outro",
                        Status.RECEBIDO.value, Status.EM_PROCESSAMENTO.value, at=ts(1))
            if doc.status == Status.ERRO:
                conn.execute("UPDATE documents SET status = ?, error_message = ? WHERE id = ?",
                             (Status.ERRO.value, doc.reason, doc_id))
                history.add(conn, doc_id, "erro", doc.reason, Status.EM_PROCESSAMENTO.value, Status.ERRO.value, at=ts(2))
                continue

            for pos, f in enumerate(fields):
                value = doc.values.get(f.key)
                conn.execute(
                    "INSERT INTO document_fields (document_id, key, label, kind, value, source, evidence, position)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (doc_id, f.key, f.label, f.kind, value, "simulado" if value else "nao_identificado",
                     None, pos),
                )
            found = sum(1 for f in fields if doc.values.get(f.key))
            conn.execute("UPDATE documents SET status = ?, extraction_method = 'simulado' WHERE id = ?",
                         (Status.AGUARDANDO_REVISAO.value, doc_id))
            history.add(conn, doc_id, "extracao_concluida",
                        f"{found} de {len(fields)} campos identificados. Método: Simulação — dados fictícios de demonstração.",
                        Status.EM_PROCESSAMENTO.value, Status.AGUARDANDO_REVISAO.value, at=ts(2))

            minute = 90
            if doc.corrected:
                labels = []
                for key, value in doc.corrected.items():
                    conn.execute("UPDATE document_fields SET value = ?, source = 'manual', evidence = NULL"
                                 " WHERE document_id = ? AND key = ?", (value, doc_id, key))
                    labels.append(next(f.label for f in fields if f.key == key))
                history.add(conn, doc_id, "campos_corrigidos", "Alterados: " + ", ".join(labels), at=ts(minute))
                minute += 2
            if doc.note:
                history.add(conn, doc_id, "observacao", doc.note, at=ts(minute))
                minute += 1
            if doc.status == Status.APROVADO:
                pending = [f.label for f in fields if not doc.values.get(f.key)]
                detail = "Aprovado após conferência humana."
                if pending:
                    detail += " Campos não identificados mantidos: " + ", ".join(pending) + "."
                conn.execute("UPDATE documents SET status = ?, reviewed_at = ? WHERE id = ?",
                             (Status.APROVADO.value, ts(minute), doc_id))
                history.add(conn, doc_id, "aprovado", detail, Status.AGUARDANDO_REVISAO.value,
                            Status.APROVADO.value, at=ts(minute))
            elif doc.status == Status.REJEITADO:
                conn.execute("UPDATE documents SET status = ?, reviewed_at = ?, rejection_reason = ? WHERE id = ?",
                             (Status.REJEITADO.value, ts(minute), doc.reason, doc_id))
                history.add(conn, doc_id, "rejeitado", doc.reason, Status.AGUARDANDO_REVISAO.value,
                            Status.REJEITADO.value, at=ts(minute))
    return True


def reset() -> None:
    """Apaga banco e arquivos de demonstração e recria tudo do zero."""
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    if config.STORAGE_DIR.exists():
        shutil.rmtree(config.STORAGE_DIR)
    db.init_schema()
    seed_if_empty()
