import React, { useMemo, useState } from "react";
import { api, type DocQuery } from "../api";
import { fmtDate, href, navigate, plural, type Route } from "../lib";
import { EmptyState, ErrorBox, Icon, LinkButton, Loading, PageHeader, STATUS_LABELS, StatusBadge, useAsync } from "../ui";

const FILTER_KEYS = ["q", "client_id", "type_id", "status", "received_from", "received_to", "pending"] as const;

export default function DocumentsPage({ route }: { route: Route }) {
  const query: DocQuery = useMemo(() => {
    const q: DocQuery = {};
    FILTER_KEYS.forEach((k) => {
      const v = route.query.get(k);
      if (v) q[k] = v;
    });
    return q;
  }, [route.query.toString()]);

  const docs = useAsync(() => api.documents({ ...query, sort: "received_desc" }), [JSON.stringify(query)]);
  const clients = useAsync(() => api.clients(), []);
  const types = useAsync(() => api.docTypes(), []);
  const [search, setSearch] = useState(query.q || "");

  const setFilter = (key: keyof DocQuery, value: string) => {
    const next = new URLSearchParams(route.query);
    if (value) next.set(key, value);
    else next.delete(key);
    const s = next.toString();
    navigate(`/documentos${s ? `?${s}` : ""}`);
  };
  const activeFilters = FILTER_KEYS.filter((k) => query[k]).length;
  const statusValue = query.status || "";
  const isReviewQueue = statusValue === "aguardando_revisao";

  return (
    <>
      <PageHeader
        title={isReviewQueue ? "Fila de revisão" : "Documentos"}
        subtitle={isReviewQueue
          ? "Documentos com dados extraídos que aguardam conferência e aprovação."
          : "Consulte os documentos por cliente, tipo, status e data de recebimento."}
        actions={<>
          <a className="btn btn-secondary" href={api.csvUrl(query)} download>
            <Icon name="download" size={16} /><span>Exportar CSV</span>
          </a>
          <LinkButton href={href("/documentos/novo")} variant="primary" icon="upload">Enviar documento</LinkButton>
        </>}
      />

      <form className="filters" role="search" onSubmit={(e) => { e.preventDefault(); setFilter("q", search.trim()); }}>
        <label className="filter filter-search">
          <span className="sr-only">Buscar</span>
          <Icon name="search" size={16} />
          <input type="search" placeholder="Buscar por código, arquivo ou cliente" value={search}
            onChange={(e) => setSearch(e.target.value)}
            onBlur={() => search.trim() !== (query.q || "") && setFilter("q", search.trim())} />
        </label>
        <label className="filter">
          <span>Cliente</span>
          <select value={query.client_id || ""} onChange={(e) => setFilter("client_id", e.target.value)}>
            <option value="">Todos</option>
            {clients.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="filter">
          <span>Tipo</span>
          <select value={query.type_id || ""} onChange={(e) => setFilter("type_id", e.target.value)}>
            <option value="">Todos</option>
            {types.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
        <label className="filter">
          <span>Status</span>
          <select value={statusValue} onChange={(e) => setFilter("status", e.target.value)}>
            <option value="">Todos</option>
            {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            {statusValue.includes(",") && <option value={statusValue}>Seleção do painel</option>}
          </select>
        </label>
        <label className="filter">
          <span>Recebido de</span>
          <input type="date" value={query.received_from || ""} max={query.received_to || undefined}
            onChange={(e) => setFilter("received_from", e.target.value)} />
        </label>
        <label className="filter">
          <span>até</span>
          <input type="date" value={query.received_to || ""} min={query.received_from || undefined}
            onChange={(e) => setFilter("received_to", e.target.value)} />
        </label>
        {activeFilters > 0 && (
          <button type="button" className="btn btn-ghost filter-clear" onClick={() => { setSearch(""); navigate("/documentos"); }}>
            <Icon name="x" size={14} /><span>Limpar filtros</span>
          </button>
        )}
      </form>

      <section className="panel panel-flush">
        {docs.loading && !docs.data ? <Loading /> : docs.error ? (
          <ErrorBox message={docs.error} onRetry={docs.reload} />
        ) : docs.data && docs.data.items.length ? (
          <>
            <div className="table-meta">
              {plural(docs.data.total, "documento encontrado", "documentos encontrados")}
              {activeFilters > 0 && " com os filtros aplicados"}
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Código</th>
                    <th>Cliente</th>
                    <th>Tipo</th>
                    <th>Arquivo</th>
                    <th>Recebido em</th>
                    <th>Status</th>
                    <th className="num">Pendências</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.data.items.map((d) => (
                    <tr key={d.id} onClick={() => navigate(`/documentos/${d.id}`)} className="row-link">
                      <td><a className="code" href={href(`/documentos/${d.id}`)} onClick={(e) => e.stopPropagation()}>{d.code}</a></td>
                      <td>{d.client.name}</td>
                      <td>{d.type.name}</td>
                      <td className="cell-file">
                        <span title={d.original_filename}>{d.original_filename}</span>
                        {d.is_demo && <span className="tag-demo" title="Documento fictício pré-carregado">demo</span>}
                      </td>
                      <td className="nowrap">{fmtDate(d.received_at)}</td>
                      <td><StatusBadge status={d.status} /></td>
                      <td className="num">
                        {d.pending_fields > 0
                          ? <span className="pending" title="Campos não identificados">{d.pending_fields}</span>
                          : <span className="muted">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : activeFilters ? (
          <EmptyState icon="search" title="Nenhum documento com esses filtros"
            action={<button className="btn btn-secondary" onClick={() => { setSearch(""); navigate("/documentos"); }}>Limpar filtros</button>}>
            Ajuste ou limpe os filtros para ver outros documentos.
          </EmptyState>
        ) : (
          <EmptyState icon="file" title="Nenhum documento recebido"
            action={<LinkButton href={href("/documentos/novo")} variant="primary" icon="upload">Enviar documento</LinkButton>}>
            Envie um PDF ou imagem para iniciar o fluxo de extração e revisão.
          </EmptyState>
        )}
      </section>
      <p className="footnote"><Icon name="info" size={14} /> O CSV é uma exportação genérica para conferência em planilha. Não é o formato de importação do SEDIF.</p>
    </>
  );
}
