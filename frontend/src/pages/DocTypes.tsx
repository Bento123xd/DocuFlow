import React, { useState } from "react";
import { api, type DocType, type FieldKind } from "../api";
import { Button, EmptyState, ErrorBox, Icon, Loading, Modal, Notice, PageHeader, useAsync, useToast } from "../ui";

const KINDS: { id: FieldKind; label: string }[] = [
  { id: "texto", label: "Texto" },
  { id: "cpf_cnpj", label: "CPF ou CNPJ" },
  { id: "data", label: "Data" },
  { id: "valor", label: "Valor (R$)" },
  { id: "numero", label: "Número / código" },
];
const kindLabel = (k: string) => KINDS.find((x) => x.id === k)?.label || k;

type EditField = { label: string; kind: FieldKind; search: string };
type Editing = { id?: string; name: string; description: string; fields: EditField[]; isSystem: boolean };

export default function DocTypesPage() {
  const toast = useToast();
  const q = useAsync(() => api.docTypes(), []);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [deleting, setDeleting] = useState<DocType | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startNew = () => { setError(null); setEditing({ name: "", description: "", isSystem: false, fields: [{ label: "", kind: "texto", search: "" }] }); };
  const startEdit = (t: DocType) => {
    setError(null);
    setEditing({
      id: t.id, name: t.name, description: t.description || "", isSystem: t.is_system,
      fields: t.fields.map((f) => ({ label: f.label, kind: f.kind, search: f.search_labels.join("; ") })),
    });
  };

  const save = async () => {
    if (!editing) return;
    const fields = editing.fields.filter((f) => f.label.trim());
    if (editing.name.trim().length < 2) return setError("Informe o nome do tipo (mínimo de 2 caracteres).");
    if (!fields.length) return setError("Adicione pelo menos um campo.");
    const body = {
      name: editing.name.trim(),
      description: editing.description.trim() || null,
      fields: fields.map((f) => ({
        label: f.label.trim(), kind: f.kind,
        search_labels: f.search.split(";").map((s) => s.trim()).filter(Boolean),
      })),
    };
    setBusy(true);
    setError(null);
    try {
      if (editing.id) await api.updateDocType(editing.id, body);
      else await api.createDocType(body);
      toast("success", editing.id ? "Tipo documental atualizado." : "Tipo documental criado.");
      setEditing(null);
      q.reload();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!deleting) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteDocType(deleting.id);
      toast("success", `Tipo “${deleting.name}” excluído.`);
      setDeleting(null);
      q.reload();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const setField = (i: number, patch: Partial<EditField>) =>
    editing && setEditing({ ...editing, fields: editing.fields.map((f, j) => (j === i ? { ...f, ...patch } : f)) });

  return (
    <>
      <PageHeader title="Tipos de documento"
        subtitle="Defina os tipos documentais e os campos que a extração deve procurar em cada um."
        actions={<Button variant="primary" icon="plus" onClick={startNew}>Novo tipo</Button>} />

      <Notice kind="warning" title="Lista de documentos do escritório pendente">
        A lista dos documentos recebidos com maior frequência ainda não foi fornecida. Por isso só o tipo “Outro”
        está configurado, com campos genéricos. Cadastre os tipos reais depois de validá-los com o contador.
      </Notice>

      {q.loading && !q.data ? <Loading /> : q.error ? <ErrorBox message={q.error} onRetry={q.reload} /> : q.data?.length ? (
        <div className="types">
          {q.data.map((t) => (
            <section key={t.id} className="panel type-card">
              <div className="panel-head">
                <div>
                  <h2>{t.name}{t.is_system && <span className="tag-system">padrão</span>}</h2>
                  {t.description && <p className="muted small">{t.description}</p>}
                </div>
                <div className="row-actions">
                  <Button variant="ghost" onClick={() => startEdit(t)}>Editar</Button>
                  {!t.is_system && <Button variant="ghost" icon="trash" aria-label={`Excluir ${t.name}`} onClick={() => { setError(null); setDeleting(t); }} />}
                </div>
              </div>
              <table className="table compact">
                <thead><tr><th>Campo</th><th>Formato</th><th>Rótulos procurados no documento</th></tr></thead>
                <tbody>
                  {t.fields.map((f) => (
                    <tr key={f.key}>
                      <td>{f.label}</td>
                      <td>{kindLabel(f.kind)}</td>
                      <td className="muted">{f.search_labels.length ? f.search_labels.join("; ") : "Nenhum (somente preenchimento manual)"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="muted small type-foot">{t.document_count} documento(s) usam este tipo.</p>
            </section>
          ))}
        </div>
      ) : (
        <EmptyState icon="sliders" title="Nenhum tipo configurado" action={<Button variant="primary" onClick={startNew}>Novo tipo</Button>} />
      )}

      {editing && (
        <Modal title={editing.id ? `Editar “${editing.name}”` : "Novo tipo de documento"} width={760} onClose={() => setEditing(null)}
          footer={<>
            <Button variant="ghost" onClick={() => setEditing(null)}>Cancelar</Button>
            <Button variant="primary" busy={busy} onClick={save}>{editing.id ? "Salvar tipo" : "Criar tipo"}</Button>
          </>}>
          <div className="form-grid two">
            <label className="form-field">
              <span>Nome</span>
              <input value={editing.name} maxLength={80} onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                placeholder="Nome usado pelo escritório" />
            </label>
            <label className="form-field">
              <span>Descrição (opcional)</span>
              <input value={editing.description} maxLength={300} onChange={(e) => setEditing({ ...editing, description: e.target.value })} />
            </label>
          </div>
          <h3 className="mt">Campos</h3>
          <p className="muted small">Rótulos procurados: palavras que aparecem antes do valor no documento, separadas por ponto e vírgula. A extração lê o valor logo após o rótulo.</p>
          <div className="field-editor">
            {editing.fields.map((f, i) => (
              <div className="field-editor-row" key={i}>
                <label className="form-field"><span>Nome do campo</span>
                  <input value={f.label} maxLength={60} onChange={(e) => setField(i, { label: e.target.value })} /></label>
                <label className="form-field"><span>Formato</span>
                  <select value={f.kind} onChange={(e) => setField(i, { kind: e.target.value as FieldKind })}>
                    {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
                  </select></label>
                <label className="form-field grow"><span>Rótulos procurados</span>
                  <input value={f.search} onChange={(e) => setField(i, { search: e.target.value })} placeholder="Ex.: CNPJ; CPF" /></label>
                <button type="button" className="icon-btn" aria-label="Remover campo" disabled={editing.fields.length === 1}
                  onClick={() => setEditing({ ...editing, fields: editing.fields.filter((_, j) => j !== i) })}>
                  <Icon name="trash" size={16} />
                </button>
              </div>
            ))}
          </div>
          <Button variant="ghost" icon="plus" disabled={editing.fields.length >= 30}
            onClick={() => setEditing({ ...editing, fields: [...editing.fields, { label: "", kind: "texto", search: "" }] })}>
            Adicionar campo
          </Button>
          {editing.id && <p className="muted small mt">Documentos já processados mantêm os campos que tinham. A nova configuração vale para os próximos processamentos.</p>}
          {error && <div className="mt"><Notice kind="error">{error}</Notice></div>}
        </Modal>
      )}

      {deleting && (
        <Modal title={`Excluir “${deleting.name}”?`} onClose={() => setDeleting(null)}
          footer={<>
            <Button variant="ghost" onClick={() => setDeleting(null)}>Cancelar</Button>
            <Button variant="danger" busy={busy} onClick={remove}>Excluir tipo</Button>
          </>}>
          <p>O tipo e seus campos serão removidos. Tipos em uso por documentos não podem ser excluídos.</p>
          {error && <Notice kind="error">{error}</Notice>}
        </Modal>
      )}
    </>
  );
}
