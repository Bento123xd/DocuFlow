import React from "react";
import { api } from "../api";
import { href } from "../lib";
import { EmptyState, ErrorBox, Icon, Loading, PageHeader, useAsync } from "../ui";

export default function ClientsPage() {
  const q = useAsync(() => api.clients(), []);
  return (
    <>
      <PageHeader title="Clientes" subtitle="Empresas e pessoas fictícias usadas nesta demonstração." />
      <section className="panel panel-flush">
        {q.loading && !q.data ? <Loading /> : q.error ? <ErrorBox message={q.error} onRetry={q.reload} /> : q.data?.length ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>Pessoa</th>
                  <th>CPF / CNPJ (fictício)</th>
                  <th>Cidade</th>
                  <th className="num">Documentos</th>
                  <th className="num">Aguardando revisão</th>
                </tr>
              </thead>
              <tbody>
                {q.data.map((c) => (
                  <tr key={c.id}>
                    <td><a href={href(`/documentos?client_id=${c.id}`)}>{c.name}</a></td>
                    <td>{c.person_kind === "PJ" ? "Jurídica" : "Física"}</td>
                    <td className="tnum">{c.document}</td>
                    <td>{c.city || "—"}</td>
                    <td className="num">{c.document_count}</td>
                    <td className="num">
                      {c.pending_count > 0
                        ? <a href={href(`/documentos?client_id=${c.id}&status=aguardando_revisao`)} className="pending">{c.pending_count}</a>
                        : <span className="muted">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="building" title="Nenhum cliente de demonstração">Reinicie a demonstração com <code>python run.py --reset</code>.</EmptyState>
        )}
      </section>
      <p className="footnote"><Icon name="info" size={14} /> O cadastro de clientes reais não faz parte desta demonstração. Os números de CPF/CNPJ são inventados e têm dígitos verificadores propositalmente inválidos.</p>
    </>
  );
}
