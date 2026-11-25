cd "c:\Users\bento.avila\Downloads\docuflow-demo\docuflow-demo\backend"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py run.py# DocuFlow — demonstração (prova de conceito)

Demonstração do fluxo de documentos para escritórios de contabilidade:

**Recebimento → identificação → extração → revisão humana → organização → exportação demonstrativa.**

> Esta versão **não é um sistema fiscal de produção**. Usa apenas dados fictícios e não tem integração com SEFAZ, TED ou SEDIF.

---

## 1. Como executar

Requisito: **Python 3.10 ou superior**. O frontend já vem compilado em `frontend/dist`, então não é preciso Node.js para rodar.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Abra **http://127.0.0.1:8000** no navegador.

- Na primeira execução são criados clientes e documentos fictícios.
- `python run.py --reset` apaga os dados locais e recria a demonstração do zero.
- `python run.py --port 8080` usa outra porta.

### OCR de imagens (opcional)

PDFs com texto pesquisável são lidos sem nada extra. Para extrair dados de **imagens** (JPG/PNG) ou PDFs digitalizados:

1. Instale o programa Tesseract com o idioma português (`por`).
   - Windows: instalador do projeto UB Mannheim. Marque "Portuguese".
   - Ubuntu/Debian: `sudo apt install tesseract-ocr tesseract-ocr-por`.
   - macOS: `brew install tesseract tesseract-lang`.
2. `pip install pytesseract Pillow`

Sem o Tesseract, imagens são aceitas normalmente, mas todos os campos ficam como **"Não identificado"** para preenchimento manual. A tela de envio mostra o que está disponível no computador.

### Testes

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

Os testes usam um banco temporário e não alteram a demonstração.

### Recompilar o frontend (somente se alterar `frontend/src`)

```bash
cd frontend
npm install
npm run build      # gera frontend/dist
```

---

## 2. Roteiro para a apresentação ao contador

1. **Painel**: indicadores calculados a partir dos registros: recebidos, aguardando revisão, processados (aprovados e rejeitados) e com problemas (erro ou campos não identificados).
2. **Documentos**: lista com filtros por cliente, tipo, status e período de recebimento.
3. **Enviar documento**: use `amostras/exemplo-recibo-ficticio.pdf`, escolha um cliente e o tipo "Outro".
4. **Revisão**: o original fica ao lado dos campos extraídos. Cada campo mostra:
   - de onde veio o valor (extração local, simulado, editado ou não identificado);
   - o trecho do documento em que o valor foi encontrado.
5. Corrija um valor, salve e **aprove**. A aprovação só acontece pelo botão "Aprovar" e por uma confirmação. Datas e valores em formato inválido bloqueiam a aprovação.
6. **Rejeitar** exige um motivo. Aprovados e rejeitados podem ser **reabertos**. Observações e todas as ações ficam no **histórico**.
7. **DOC-00015**, com status "Recebido": clique em **Processar documento** para ver a extração real sobre um arquivo fictício.
8. **Exportação SEDIF**: explica o que falta para essa etapa (ver seção 4).

---

## 3. O que é real e o que é simulado

| Funcionalidade | Situação |
|---|---|
| Upload de PDF, JPG, JPEG e PNG (até 15 MB), com checagem de extensão e conteúdo | **Real** |
| Armazenamento local privado: arquivos servidos só pela API, com nomes aleatórios | **Real** (sem autenticação; ver limitações) |
| Leitura de texto de PDF (pypdf) e localização de campos por rótulos configuráveis | **Real, local**: regras simples, não é IA |
| OCR de imagens (Tesseract) | **Real e opcional**: depende da instalação local |
| Validação de CPF/CNPJ (dígito verificador), datas e valores | **Real**: regras públicas e objetivas |
| Revisão, correção, aprovação, rejeição, reabertura, observações e histórico | **Real** |
| Filtros, painel e lista | **Real**: calculados do banco |
| Campos dos documentos pré-carregados | **Simulados**: marcados como "Simulado" na tela |
| Clientes e documentos de demonstração | **Fictícios**: CPF/CNPJ com dígitos propositalmente inválidos |
| Exportação CSV | **Real, genérica**: para conferência em planilha. **Não é formato SEDIF** |
| Exportação SEDIF | **Não implementada**: falta o arquivo de exemplo |
| Classificação automática do tipo de documento | **Não implementada**: o tipo é escolhido pelo usuário |
| Envio a serviços externos de IA | **Não existe**: nada sai do computador |

---

## 4. Materiais pendentes e decisões tomadas

Os materiais citados nas instruções **não foram recebidos**:

- **Exemplo de arquivo de importação do SEDIF.** Por isso a área SEDIF não reproduz formato, registros, campos nem regras e não gera arquivo. Ela apenas lista o que falta.
- **Lista de documentos mais frequentes do escritório.** Por isso existe só o tipo **"Outro"**, com os campos genéricos citados nas instruções (Nome, CPF/CNPJ, Data, Valor, Número). Novos tipos e campos podem ser cadastrados em **Configuração → Tipos de documento**.

Para avançar, é preciso:

1. O arquivo de exemplo do SEDIF, com dados fictícios ou anonimizados.
2. A lista de documentos frequentes.
3. A indicação de quais tipos de documento alimentam o SEDIF.
4. A validação, com o contador, de um arquivo gerado antes de qualquer uso real.

---

## 5. Arquitetura

As instruções pediam preferencialmente FastAPI, Next.js e PostgreSQL. No ambiente em que a demonstração foi construída não havia acesso à instalação desses pacotes. Por isso foi usada a solução mais simples que funciona de ponta a ponta e pode ser testada:

| Camada | Usado | Observação |
|---|---|---|
| Backend | **Starlette + Pydantic + Uvicorn** | O FastAPI é construído sobre o Starlette. As rotas e modelos Pydantic migram com poucas mudanças. |
| Frontend | **React + TypeScript**, compilado com esbuild | Sem Next.js. É uma página única servida pelo próprio backend. |
| Banco | **SQLite** (arquivo local) | O SQL está concentrado nos módulos de repositório, o que facilita a troca por PostgreSQL. |
| Armazenamento | Pasta local `backend/data/storage` | Fora de qualquer pasta pública. |

```
backend/
  run.py                 inicia o servidor (e cria os dados de demonstração)
  app/
    main.py              aplicação, rotas, erros, cabeçalhos
    config.py            caminhos e limites (variáveis DOCUFLOW_*)
    db.py                esquema SQLite e transações
    schemas.py           modelos Pydantic (entrada e saída)
    documents.py         documentos: upload, consulta, arquivo, processamento
    clients.py           clientes fictícios (somente leitura)
    extraction.py        extração local: texto de PDF / OCR + regras por campo
    review.py            revisão: correção, aprovação, rejeição, reabertura, observações
    exports.py           CSV genérico e status da etapa SEDIF
    doctypes.py          configuração de tipos de documento e campos
    dashboard.py         indicadores do painel
    history.py           histórico de processamento
    validators.py        CPF/CNPJ, datas, valores
    seed.py, demo_pdf.py dados e arquivos fictícios
  tests/test_fluxo.py
frontend/
  src/                   código TypeScript/React (páginas em src/pages)
  dist/                  build pronto, servido pelo backend
amostras/                arquivos fictícios para testar o envio
scripts/                 gerador das imagens fictícias
```

Variáveis de ambiente opcionais: `DOCUFLOW_DATA_DIR`, `DOCUFLOW_HOST`, `DOCUFLOW_PORT` e `DOCUFLOW_OCR=0` (desliga o OCR).

---

## 6. Limitações conhecidas

- **Sem autenticação nem controle de acesso.** O servidor escuta apenas em `127.0.0.1` (este computador). Não exponha a demonstração em rede.
- **Não há alegação de conformidade com a LGPD nem de segurança de produção.** Não há criptografia em repouso, trilha de auditoria assinada nem política de retenção.
- A extração é baseada em rótulos e padrões. Ela funciona bem em documentos com rótulos claros ("CNPJ:", "Valor total:") e mal em layouts livres. Sempre exige conferência humana.
- O OCR depende da qualidade da imagem e da instalação do Tesseract.
- PDFs são lidos até a 20ª página.
- Não há integração real com WhatsApp, automação de navegador, transmissão de declarações nem cobrança.
- O tipo de documento é escolhido manualmente. Não há classificação automática.
- A verificação de tipos com `npm run typecheck` requer `npm install`. O build foi validado, mas a checagem completa de tipos não pôde ser executada no ambiente de desenvolvimento por falta das definições `@types/react`.
- Fonte da interface: Source Sans 3, incluída localmente (licença SIL OFL, em `frontend/public/fonts`).
