import React, { useEffect, useMemo, useState } from "react";
import { api, type DocumentDetail, type FieldValue, type Meta } from "../api";
import { fmtDate, fmtDateTime, fmtSize, href } from "../lib";
import {
  Button, ErrorBox, Icon, Loading, Modal, Notice, PageHeader, SourceTag, StatusBadge, useAsync, useToast,
} from "../ui";

const KIND_HINT: Record<string, string> = {
  texto: "Texto",
  cpf_cnpj: "CPF ou CNPJ",
  data: "DD/MM/AAAA",
  valor: "R$",
  numero: "Número ou código",
};

type Draft = Record<string, string>;

function draftFrom(doc: DocumentDetail): Draft {
  return Object.fromEntries(doc.fields.map((f) => [f.key, f.value ?? ""]));
}

export default function ReviewPage({ id, meta }: { id: number; meta: Meta | null }) {
  const toast = useToast();
  const docQ = useAsync(() => api.document(id), [id]);
  const clients = useAsync(() => api.clients(), []);
  const types = useAsync(() => api.docTypes(), []);
  const [draft, setDraft] = useState<Draft>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [modal, setModal] = useState<null | "approve" | "reject" | "type">(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [metaDraft, setMetaDraft] = useState({ client_id: "", type_id: "", received_at: "" });

  const doc = docQ.data;
  useEffect(() => {
    if (!doc) return;
    setDraft(draftFrom(doc));
    setMetaDraft({ client_id: String(doc.client.id), type_id: doc.type.id, received_at: doc.received_at });
  }, [doc]);

  const changedKeys = useMemo(
    () => (doc ? doc.fields.filter((f) => (f.value ?? "") !== (draft[f.key] ?? "")).map((f) => f.key) : []),
    [doc, draft],
  );
  const metaEditable = !!doc && !["aprovado", "em_processamento"].includes(doc.status);
  const metaChanged = !!doc && (metaDraft.client_id !== String(doc.client.id) || metaDraft.type_id !== doc.type.id
    || metaDraft.received_at !== doc.received_at);

  if (docQ.loading && !doc) return <Loading />;
  if (docQ.error || !doc) return <ErrorBox message={docQ.error || ""} onRetry={docQ.reload} />;

  const apply = (d: DocumentDetail) => docQ.setData(d);
  const payload = () => doc.fields.map((f) => ({ key: f.key, value: draft[f.key]?.trim() ? draft[f.key] : null }));

  async function run(label: string, fn: () => Promise<DocumentDetail>, success: string, close = true) {
    setBusy(label);
    setActionError(null);
    try {
      const d = await fn();
      apply(d);
      toast(d.status === "erro" && label === "process" ? "error" : "success", d.status === "erro" && label === "process"
        ? "O processamento terminou com erro. Veja os detalhes no documento." : success);
      if (close) setModal(null);
    } catch (e: any) {
      setActionError(e.message);
      if (!close || !modal) toast("error", e.message);
    } finally {
      setBusy(null);
    }
  }

  const saveMeta = () => {
    const data: Record<string, unknown> = {};
    if (metaDraft.client_id !== String(doc.client.id)) data.client_id = Number(metaDraft.client_id);
    if (metaDraft.received_at !== doc.received_at) data.received_at = metaDraft.received_at;
    if (metaDraft.type_id !== doc.type.id) data.type_id = metaDraft.type_id;
    run("meta", () => api.updateMeta(doc.id, data), data.type_id ? "Tipo alterado e campos extraídos novamente." : "Dados do documento salvos.");
  };

  const pendingNow = doc.fields.filter((f) => !draft[f.key]?.trim());
  const warnFields = doc.fields.filter((f) => f.warnings.length && (draft[f.key] ?? "") === (f.value ?? ""));
  const isImage = doc.mime.startsWith("image/");
  const isSimulated = doc.extraction_method === "simulado";

  return (
    <>
      <PageHeader
        back={{ href: href("/documentos"), label: "Documentos" }}
        title={<span className="title-with-badge">{doc.code}<StatusBadge status={doc.status} /></span>}
        subtitle={<>{doc.client.name}, recebido em {fmtDate(doc.received_at)}{doc.is_demo && <span className="tag-demo">dados fictícios</span>}</>}
      />

      <div className="review-grid">
        {/* ---------------- original */}
        <section className="panel viewer" aria-label="Documento original">
          <div className="viewer-bar">
            <div className="viewer-file">
              <Icon name="file" size={16} />
              <span title={doc.original_filename}>{doc.original_filename}</span>
              <span className="muted small">{fmtSize(doc.size_bytes)}</span>
            </div>
            <div className="viewer-actions">
              <a className="btn btn-ghost btn-sm" href={api.fileUrl(doc.id)} target="_blank" rel="noopener">
                <Icon name="open" size={15} /><span>Abrir</span>
              </a>
              <a className="btn btn-ghost btn-sm" href={api.fileUrl(doc.id, true)}>
                <Icon name="download" size={15} /><span>Baixar</span>
              </a>
            </div>
          </div>
          <div className="viewer-body">
            {doc.status === "erro" ? (
              <div className="viewer-error">
                <Icon name="alert" size={22} />
                <p>A pré-visualização não está disponível porque o arquivo não pôde ser lido.</p>
                <a href={api.fileUrl(doc.id, true)}>Baixar o arquivo original para verificar</a>
              </div>
            ) : isImage ? (
              <img src={api.fileUrl(doc.id)} alt={`Imagem do documento ${doc.code}`} />
            ) : (
              <iframe src={`${api.fileUrl(doc.id)}#view=FitH`} title={`Documento ${doc.code}`} />
            )}
          </div>
        </section>

        {/* ---------------- conferência */}
        <section className="panel check" aria-label="Conferência">
          <div className="check-section">
            <h2>Dados do documento</h2>
            <div className="meta-grid">
              <label className="form-field">
                <span>Cliente</span>
                <select disabled={!metaEditable} value={metaDraft.client_id}
                  onChange={(e) => setMetaDraft({ ...metaDraft, client_id: e.target.value })}>
                  {clients.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  {!clients.data && <option value={doc.client.id}>{doc.client.name}</option>}
                </select>
              </label>
              <label className="form-field">
                <span>Tipo de documento</span>
                <select disabled={!metaEditable} value={metaDraft.type_id}
                  onChange={(e) => setMetaDraft({ ...metaDraft, type_id: e.target.value })}>
                  {types.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                  {!types.data && <option value={doc.type.id}>{doc.type.name}</option>}
                </select>
              </label>
              <label className="form-field">
                <span>Recebido em</span>
                <input type="date" disabled={!metaEditable} value={metaDraft.received_at} max={meta?.today}
                  onChange={(e) => setMetaDraft({ ...metaDraft, received_at: e.target.value })} />
              </label>
            </div>
            {metaChanged && (
              <div className="inline-actions">
                <Button variant="ghost" onClick={() => setMetaDraft({ client_id: String(doc.client.id), type_id: doc.type.id, received_at: doc.received_at })}>Descartar</Button>
                <Button variant="secondary" busy={busy === "meta"}
                  onClick={() => (metaDraft.type_id !== doc.type.id && doc.status !== "recebido" ? setModal("type") : saveMeta())}>
                  Salvar dados do documento
                </Button>
              </div>
            )}
            {!metaEditable && doc.status === "aprovado" && (
              <p className="muted small">Documento aprovado. Reabra a revisão para alterar cliente, tipo ou data.</p>
            )}
          </div>

          {/* estado do processamento */}
          <div className="check-section">
            {doc.status === "recebido" && (
              <Notice kind="info" title="Documento ainda não processado">
                Execute o processamento para extrair os campos do tipo “{doc.type.name}”.
              </Notice>
            )}
            {doc.status === "erro" && (
              <Notice kind="error" title="Erro no processamento">{doc.error_message || "Erro não especificado."}</Notice>
            )}
            {doc.status === "rejeitado" && (
              <Notice kind="warning" title="Processamento rejeitado">{doc.rejection_reason}</Notice>
            )}
            {doc.status === "aprovado" && (
              <Notice kind="info" icon="check" title="Documento aprovado">
                Aprovado manualmente em {fmtDateTime(doc.reviewed_at)}. Os campos abaixo são os valores conferidos.
              </Notice>
            )}
            {isSimulated && (
              <Notice kind="simulated" title="Extração simulada">
                Os valores deste documento pré-carregado são dados fictícios de demonstração, não uma leitura real do arquivo.
                Use “Reprocessar” para executar a extração local sobre o arquivo.
              </Notice>
            )}
            {doc.extraction_method && !isSimulated && (
              <p className="method"><Icon name="info" size={14} /> Método: {doc.extraction_method_label}</p>
            )}
            {doc.extraction_note && <Notice kind="warning">{doc.extraction_note}</Notice>}
            {(doc.status === "recebido" || (doc.can_reprocess && doc.status !== "recebido")) && (
              <div className="inline-actions start">
                <Button variant={doc.status === "recebido" || doc.status === "erro" ? "primary" : "secondary"} icon="refresh"
                  busy={busy === "process"}
                  onClick={() => run("process", () => api.process(doc.id), "Extração concluída. Confira os campos.")}>
                  {doc.status === "recebido" ? "Processar documento" : "Reprocessar"}
                </Button>
                {doc.status === "aguardando_revisao" && (
                  <span className="muted small">Substitui os valores atuais por uma nova extração.</span>
                )}
              </div>
            )}
          </div>

          {/* campos */}
          {doc.fields.length > 0 && (
            <div className="check-section">
              <div className="section-head">
                <h2>Campos extraídos</h2>
                <span className="muted small">
                  {pendingNow.length ? `${pendingNow.length} não identificado${pendingNow.length > 1 ? "s" : ""}` : "Todos preenchidos"}
                </span>
              </div>
              <div className="ledger-fields">
                {doc.fields.map((f) => (
                  <FieldRow key={f.key} field={f} value={draft[f.key] ?? ""} editable={doc.can_edit}
                    changed={changedKeys.includes(f.key)}
                    onChange={(v) => setDraft({ ...draft, [f.key]: v })} />
                ))}
              </div>
              <p className="legend small">
                <SourceTag source="auto" /> lido do arquivo
                <SourceTag source="simulado" /> dado fictício
                <SourceTag source="manual" /> corrigido por pessoa
                <SourceTag source="nao_identificado" /> sem valor
              </p>
            </div>
          )}

          {/* ações */}
          {(doc.can_edit || doc.status === "aprovado" || doc.status === "rejeitado" || doc.status === "erro" || doc.status === "recebido") && (
            <div className="check-actions">
              {doc.can_edit && (
                <>
                  <Button variant="danger" onClick={() => { setActionError(null); setModal("reject"); }}>Rejeitar</Button>
                  <span className="spacer" />
                  {changedKeys.length > 0 && <span className="unsaved">{changedKeys.length} alteração(ões) não salva(s)</span>}
                  <Button variant="secondary" disabled={!changedKeys.length} busy={busy === "save"}
                    onClick={() => run("save", () => api.saveFields(doc.id, payload()), "Correções salvas.", false)}>
                    Salvar correções
                  </Button>
                  <Button variant="primary" icon="check" onClick={() => { setActionError(null); setModal("approve"); }}>Aprovar</Button>
                </>
              )}
              {(doc.status === "erro" || doc.status === "recebido") && (
                <Button variant="danger" onClick={() => { setActionError(null); setModal("reject"); }}>Rejeitar</Button>
              )}
              {(doc.status === "aprovado" || (doc.status === "rejeitado" && doc.fields.length > 0)) && (
                <Button variant="secondary" icon="refresh" busy={busy === "reopen"}
                  onClick={() => run("reopen", () => api.reopen(doc.id), "Documento devolvido para revisão.")}>
                  Reabrir revisão
                </Button>
              )}
            </div>
          )}

          <NotesAndHistory doc={doc} onUpdate={apply} />
        </section>
      </div>

      {modal === "approve" && (
        <ApproveModal doc={doc} pending={pendingNow} warnings={warnFields} error={actionError} busy={busy === "approve"}
          onClose={() => setModal(null)}
          onConfirm={(note) => run("approve", () => api.approve(doc.id, payload(), note), `${doc.code} aprovado.`)} />
      )}
      {modal === "reject" && (
        <RejectModal error={actionError} busy={busy === "reject"} onClose={() => setModal(null)}
          onConfirm={(reason) => run("reject", () => api.reject(doc.id, reason), `${doc.code} rejeitado.`)} />
      )}
      {modal === "type" && (
        <Modal title="Alterar tipo de documento" onClose={() => setModal(null)}
          footer={<>
            <Button variant="ghost" onClick={() => setModal(null)}>Cancelar</Button>
            <Button variant="primary" busy={busy === "meta"} onClick={saveMeta}>Alterar e extrair novamente</Button>
          </>}>
          <p>Cada tipo tem seus próprios campos. Ao alterar o tipo, os campos atuais e as correções feitas serão
            substituídos por uma nova extração.</p>
          {actionError && <Notice kind="error">{actionError}</Notice>}
        </Modal>
      )}
    </>
  );
}

function FieldRow({ field, value, editable, changed, onChange }: {
  field: FieldValue; value: string; editable: boolean; changed: boolean; onChange: (v: string) => void;
}) {
  const source = changed ? (value.trim() ? "manual" : "nao_identificado") : field.source;
  const id = `field-${field.key}`;
  const showServerChecks = !changed;
  return (
    <div className={`frow src-${source} ${field.errors.length && showServerChecks ? "has-error" : ""}`}>
      <div className="frow-head">
        <label htmlFor={id}>{field.label}</label>
        <SourceTag source={source} />
      </div>
      {editable ? (
        <div className="frow-input">
          <input id={id} value={value} placeholder="Não identificado" onChange={(e) => onChange(e.target.value)}
            inputMode={field.kind === "valor" || field.kind === "cpf_cnpj" ? "decimal" : undefined}
            aria-describedby={`${id}-hint`} />
          {value && (
            <button type="button" className="icon-btn" onClick={() => onChange("")} aria-label={`Limpar ${field.label}`}>
              <Icon name="x" size={14} />
            </button>
          )}
        </div>
      ) : (
        <div className={`frow-value ${value ? "" : "is-empty"}`} id={id}>{value || "Não identificado"}</div>
      )}
      <div className="frow-meta" id={`${id}-hint`}>
        <span className="muted">{KIND_HINT[field.kind]}</span>
        {field.evidence && !changed && field.source === "auto" && <span className="evidence" title={field.evidence}>Trecho: “{field.evidence}”</span>}
      </div>
      {showServerChecks && field.errors.map((e) => <p key={e} className="frow-error">{e}</p>)}
      {showServerChecks && field.warnings.map((w) => <p key={w} className="frow-warning">{w}</p>)}
    </div>
  );
}

function ApproveModal({ doc, pending, warnings, error, busy, onClose, onConfirm }: {
  doc: DocumentDetail; pending: FieldValue[]; warnings: FieldValue[]; error: string | null; busy: boolean;
  onClose: () => void; onConfirm: (note: string) => void;
}) {
  const [note, setNote] = useState("");
  return (
    <Modal title={`Aprovar ${doc.code}`} onClose={onClose}
      footer={<>
        <Button variant="ghost" onClick={onClose}>Voltar à conferência</Button>
        <Button variant="primary" icon="check" busy={busy} onClick={() => onConfirm(note)}>Confirmar aprovação</Button>
      </>}>
      <p>Ao aprovar, você confirma que conferiu os dados com o documento original. As correções não salvas serão gravadas junto.</p>
      {pending.length > 0 && (
        <Notice kind="warning" title="Campos sem valor">
          {pending.map((p) => p.label).join(", ")} ficará(ão) como “Não identificado”.
        </Notice>
      )}
      {warnings.length > 0 && (
        <Notice kind="warning" title="Avisos de validação">
          {warnings.map((w) => `${w.label}: ${w.warnings.join(" ")}`).join(" ")}
        </Notice>
      )}
      {error && <Notice kind="error" title="Não foi possível aprovar">{error}</Notice>}
      <label className="form-field mt">
        <span>Observação (opcional)</span>
        <textarea rows={3} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)}
          placeholder="Ex.: conferido com o cliente por telefone." />
      </label>
    </Modal>
  );
}

function RejectModal({ error, busy, onClose, onConfirm }: {
  error: string | null; busy: boolean; onClose: () => void; onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const invalid = reason.trim().length < 3;
  return (
    <Modal title="Rejeitar processamento" onClose={onClose}
      footer={<>
        <Button variant="ghost" onClick={onClose}>Cancelar</Button>
        <Button variant="danger" busy={busy} onClick={() => { setTouched(true); if (!invalid) onConfirm(reason.trim()); }}>
          Rejeitar documento
        </Button>
      </>}>
      <p>O documento sai da fila de revisão e o motivo fica registrado no histórico. Ele pode ser reprocessado depois.</p>
      <label className="form-field">
        <span>Motivo da rejeição</span>
        <textarea rows={3} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} onBlur={() => setTouched(true)}
          placeholder="Ex.: arquivo ilegível; solicitado novo envio ao cliente." aria-invalid={touched && invalid} />
        {touched && invalid && <em className="field-error">Descreva o motivo (mínimo de 3 caracteres).</em>}
      </label>
      {error && <Notice kind="error" title="Não foi possível rejeitar">{error}</Notice>}
    </Modal>
  );
}

function NotesAndHistory({ doc, onUpdate }: { doc: DocumentDetail; onUpdate: (d: DocumentDetail) => void }) {
  const toast = useToast();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    try {
      onUpdate(await api.addNote(doc.id, text.trim()));
      setText("");
      toast("success", "Observação registrada.");
    } catch (err: any) {
      toast("error", err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="check-section">
      <h2>Observações e histórico</h2>
      <form className="note-form" onSubmit={add}>
        <label className="sr-only" htmlFor="note">Nova observação</label>
        <textarea id="note" rows={2} maxLength={1000} value={text} onChange={(e) => setText(e.target.value)}
          placeholder="Registrar uma observação sobre este documento" />
        <Button type="submit" variant="secondary" icon="note" busy={busy} disabled={!text.trim()}>Registrar</Button>
      </form>
      <ol className="timeline">
        {doc.history.map((h) => (
          <li key={h.id} className={`tl-${h.action}`}>
            <span className={`tl-mark ${h.status_to ? `seg-${h.status_to}` : "seg-none"}`} aria-hidden="true" />
            <div>
              <div className="tl-head">
                <strong>{h.action_label}</strong>
                <time dateTime={h.at}>{fmtDateTime(h.at)}</time>
              </div>
              {h.detail && <p className={h.action === "observacao" ? "tl-note" : "tl-detail"}>{h.detail}</p>}
              <span className="muted small">{h.actor}</span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
