import React, { useRef, useState } from "react";
import { api, type Meta } from "../api";
import { fmtSize, href, navigate } from "../lib";
import { Button, ErrorBox, Icon, Loading, Notice, PageHeader, useAsync, useToast } from "../ui";

const ACCEPT = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";
const EXT_OK = /\.(pdf|jpe?g|png)$/i;

export default function UploadPage({ meta }: { meta: Meta | null }) {
  const toast = useToast();
  const clients = useAsync(() => api.clients(), []);
  const types = useAsync(() => api.docTypes(), []);
  const [file, setFile] = useState<File | null>(null);
  const [clientId, setClientId] = useState("");
  const [typeId, setTypeId] = useState("outro");
  const [receivedAt, setReceivedAt] = useState(meta?.today || new Date().toISOString().slice(0, 10));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const maxMb = meta?.max_upload_mb || 15;

  const pick = (f: File | undefined | null) => {
    if (!f) return;
    const next = { ...errors };
    delete next.file;
    if (!EXT_OK.test(f.name)) next.file = "Formato não aceito. Envie PDF, JPG, JPEG ou PNG.";
    else if (f.size > maxMb * 1024 * 1024) next.file = `O arquivo tem ${fmtSize(f.size)}; o limite é ${maxMb} MB.`;
    setErrors(next);
    setFile(next.file ? null : f);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!file) next.file = errors.file || "Selecione o arquivo do documento.";
    if (!clientId) next.client = "Selecione o cliente.";
    if (!receivedAt) next.date = "Informe a data de recebimento.";
    else if (meta && receivedAt > meta.today) next.date = "A data de recebimento não pode estar no futuro.";
    setErrors(next);
    setServerError(null);
    if (Object.keys(next).length) return;
    const form = new FormData();
    form.append("file", file as File);
    form.append("client_id", clientId);
    form.append("type_id", typeId);
    form.append("received_at", receivedAt);
    setBusy(true);
    try {
      const doc = await api.upload(form);
      if (doc.status === "erro") toast("error", `${doc.code} recebido, mas o processamento falhou.`);
      else toast("success", `${doc.code} recebido e enviado para revisão.`);
      navigate(`/documentos/${doc.id}`);
    } catch (err: any) {
      setServerError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (clients.loading || types.loading) return <Loading />;
  if (clients.error || types.error) return <ErrorBox message={clients.error || types.error || ""} onRetry={() => { clients.reload(); types.reload(); }} />;
  const onlyOther = (types.data?.length || 0) <= 1;
  const caps = meta?.capabilities;

  return (
    <>
      <PageHeader title="Enviar documento" back={{ href: href("/documentos"), label: "Documentos" }}
        subtitle="O arquivo fica armazenado localmente nesta demonstração e não é enviado a serviços externos." />

      <form className="upload-grid" onSubmit={submit} noValidate>
        <section className="panel">
          <div
            className={`dropzone ${dragging ? "is-drag" : ""} ${errors.file ? "has-error" : ""} ${file ? "has-file" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files?.[0]); }}
          >
            <input ref={inputRef} id="file" type="file" accept={ACCEPT} className="sr-only"
              onChange={(e) => pick(e.target.files?.[0])} aria-describedby="file-help" />
            {file ? (
              <div className="file-chosen">
                <Icon name="file" size={28} />
                <div>
                  <strong>{file.name}</strong>
                  <span className="muted">{fmtSize(file.size)}</span>
                </div>
                <button type="button" className="btn btn-ghost" onClick={() => { setFile(null); if (inputRef.current) inputRef.current.value = ""; }}>
                  Trocar arquivo
                </button>
              </div>
            ) : (
              <label htmlFor="file" className="dropzone-label">
                <Icon name="upload" size={28} />
                <strong>Arraste o arquivo para cá ou clique para selecionar</strong>
                <span id="file-help" className="muted">PDF, JPG, JPEG ou PNG, até {maxMb} MB</span>
              </label>
            )}
          </div>
          {errors.file && <p className="field-error" role="alert">{errors.file}</p>}

          <div className="form-grid">
            <label className="form-field">
              <span>Cliente</span>
              <select value={clientId} onChange={(e) => setClientId(e.target.value)} aria-invalid={!!errors.client}>
                <option value="">Selecione…</option>
                {clients.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              {errors.client && <em className="field-error">{errors.client}</em>}
            </label>
            <label className="form-field">
              <span>Tipo de documento</span>
              <select value={typeId} onChange={(e) => setTypeId(e.target.value)}>
                {types.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
              {onlyOther && <em className="field-help">Único tipo configurado até o recebimento da lista do escritório.</em>}
            </label>
            <label className="form-field">
              <span>Data de recebimento</span>
              <input type="date" value={receivedAt} max={meta?.today} onChange={(e) => setReceivedAt(e.target.value)} aria-invalid={!!errors.date} />
              {errors.date && <em className="field-error">{errors.date}</em>}
            </label>
          </div>

          {serverError && <div className="mt"><Notice kind="error" title="O envio não foi concluído">{serverError}</Notice></div>}

          <div className="form-actions">
            <a className="btn btn-ghost" href={href("/documentos")}>Cancelar</a>
            <Button type="submit" variant="primary" icon="upload" busy={busy}>{busy ? "Enviando e processando…" : "Enviar e processar"}</Button>
          </div>
        </section>

        <aside className="panel aside-help">
          <h2>O que acontece depois do envio</h2>
          <ol className="steps">
            <li>O documento é registrado como <strong>Recebido</strong>.</li>
            <li>A extração tenta localizar os campos do tipo escolhido no texto do arquivo.</li>
            <li>O documento vai para <strong>Aguardando revisão</strong>. Nada é aprovado sem sua confirmação.</li>
          </ol>
          <h3>Capacidade de leitura neste computador</h3>
          <ul className="caps">
            <li className={caps?.pdf_text ? "ok" : "off"}>
              <Icon name={caps?.pdf_text ? "check" : "x"} size={14} />
              PDF com texto pesquisável: {caps?.pdf_text ? "leitura local disponível" : "biblioteca pypdf não instalada"}
            </li>
            <li className={caps?.ocr ? "ok" : "off"}>
              <Icon name={caps?.ocr ? "check" : "x"} size={14} />
              Imagens e PDFs digitalizados: {caps?.ocr ? "OCR local (Tesseract) disponível" : "OCR não instalado; campos ficarão para preenchimento manual"}
            </li>
          </ul>
          <p className="muted small">Campos não encontrados aparecem como “Não identificado”. O sistema não preenche valores que não estejam no documento.</p>
        </aside>
      </form>
    </>
  );
}
