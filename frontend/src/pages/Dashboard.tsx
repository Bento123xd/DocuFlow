import React from "react";
import { api, type StatusId } from "../api";
import { fmtDate, fmtRelative, href, plural } from "../lib";
import { EmptyState, ErrorBox, Icon, LinkButton, Loading, PageHeader, STATUS_LABELS, StatusBadge, useAsync } from "../ui";

const ORDER: StatusId[] = ["recebido", "em_processamento", "aguardando_revisao", "aprovado", "rejeitado", "erro"];

export default function DashboardPage() {
  const stats = useAsync(() => api.dashboard(), []);
  const attention = useAsync(
    () => api.documents({ status: "aguardando_revisao,erro,recebido", sort: "received_desc" }),
    [],
  );

  if (stats.loading && !stats.data) return <Loading />;
  if (stats.error || !stats.data) return <ErrorBox message={stats.error || ""} onRetry={stats.reload} />;
  const s = stats.data;

  return (
    <>
      <PageHeader
        title="Painel"
        subtitle="Situação atual dos documentos recebidos, calculada a partir dos registros da demonstração."
        actions={<LinkButton href={href("/documentos/novo")} variant="primary" icon="upload">Enviar documento</LinkButton>}
      />

      <section className="ledger" aria-label="Resumo">
        <a className="ledger-cell" href={href("/documentos")}>
          <span className="ledger-label">Documentos recebidos</span>
          <span className="ledger-value">{s.total}</span>
          <span className="ledger-note">{plural(s.received_last_7_days, "recebido", "recebidos")} nos últimos 7 dias</span>
        </a>
        <a className="ledger-cell" href={href("/documentos?status=aguardando_revisao")}>
          <span className="ledger-label">Aguardando revisão</span>
          <span className="ledger-value tone-amber">{s.awaiting_review}</span>
          <span className="ledger-note">Dependem de conferência humana</span>
        </a>
        <a className="ledger-cell" href={href("/documentos?status=aprovado,rejeitado")}>
          <span className="ledger-label">Processados</span>
          <span className="ledger-value tone-green">{s.processed}</span>
          <span className="ledger-note">{plural(s.approved, "aprovado", "aprovados")}, {plural(s.rejected, "rejeitado", "rejeitados")}</span>
        </a>
        <a className="ledger-cell" href={href("/documentos?status=erro")}>
          <span className="ledger-label">Com problemas</span>
          <span className="ledger-value tone-red">{s.with_problems}</span>
          <span className="ledger-note">
            {plural(s.errors, "com erro", "com erro")}, {s.with_unidentified} com campos não identificados
          </span>
        </a>
      </section>

      {s.total > 0 && (
        <section className="panel">
          <div className="panel-head"><h2>Distribuição por status</h2></div>
          <div className="dist-bar" role="img" aria-label="Distribuição dos documentos por status">
            {ORDER.filter((k) => s.by_status[k] > 0).map((k) => (
              <a key={k} href={href(`/documentos?status=${k}`)} className={`dist-seg seg-${k}`}
                style={{ flexGrow: s.by_status[k] }} title={`${STATUS_LABELS[k]}: ${s.by_status[k]}`} />
            ))}
          </div>
          <ul className="dist-legend">
            {ORDER.map((k) => (
              <li key={k}>
                <a href={href(`/documentos?status=${k}`)}>
                  <span className={`dot seg-${k}`} aria-hidden="true" />
                  {STATUS_LABELS[k]}
                  <strong>{s.by_status[k]}</strong>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="two-col">
        <section className="panel">
          <div className="panel-head">
            <h2>Precisam de atenção</h2>
            <a className="panel-link" href={href("/documentos?status=aguardando_revisao,erro,recebido")}>Ver todos</a>
          </div>
          {attention.loading && !attention.data ? <Loading /> : attention.error ? (
            <ErrorBox message={attention.error} onRetry={attention.reload} />
          ) : attention.data && attention.data.items.length ? (
            <ul className="attention">
              {attention.data.items.slice(0, 7).map((d) => (
                <li key={d.id}>
                  <a href={href(`/documentos/${d.id}`)}>
                    <div className="attention-main">
                      <span className="attention-title">{d.client.name}</span>
                      <span className="muted"><span className="code">{d.code}</span> {d.original_filename}</span>
                    </div>
                    <div className="attention-side">
                      <StatusBadge status={d.status} />
                      <span className="muted small">
                        {d.pending_fields > 0 ? plural(d.pending_fields, "campo pendente", "campos pendentes") : `Recebido em ${fmtDate(d.received_at)}`}
                      </span>
                    </div>
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon="check" title="Nada pendente">Todos os documentos foram revisados.</EmptyState>
          )}
        </section>

        <section className="panel">
          <div className="panel-head"><h2>Atividade recente</h2></div>
          {s.recent_activity.length ? (
            <ol className="activity">
              {s.recent_activity.map((a) => (
                <li key={a.id}>
                  <span className={`activity-mark ${a.status_to ? `seg-${a.status_to}` : "seg-none"}`} aria-hidden="true" />
                  <div>
                    <div className="activity-line">
                      <a href={href(`/documentos/${a.document_id}`)}>{a.document_code}</a>
                      <span>{a.action_label}</span>
                    </div>
                    <div className="muted small">{a.client_name}, {fmtRelative(a.at)}</div>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState icon="note" title="Sem atividade ainda">As ações sobre documentos aparecem aqui.</EmptyState>
          )}
        </section>
      </div>

      <p className="footnote"><Icon name="info" size={14} /> Números calculados em tempo real a partir dos registros desta demonstração. Nenhum dado é real.</p>
    </>
  );
}
