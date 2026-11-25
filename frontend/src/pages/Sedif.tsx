import React from "react";
import { api } from "../api";
import { href } from "../lib";
import { ErrorBox, Icon, Loading, PageHeader, useAsync } from "../ui";

export default function SedifPage() {
  const q = useAsync(() => api.sedifStatus(), []);
  return (
    <>
      <PageHeader title="Exportação SEDIF" subtitle="Etapa prevista para depois da validação do formato com o escritório." />
      {q.loading && !q.data ? <Loading /> : q.error || !q.data ? <ErrorBox message={q.error || ""} onRetry={q.reload} /> : (
        <section className="panel sedif">
          <div className="sedif-state">
            <div className="sedif-icon"><Icon name="export" size={24} /></div>
            <div>
              <h2>{q.data.summary}</h2>
              <p>{q.data.reason}</p>
            </div>
          </div>
          <div className="sedif-cols">
            <div>
              <h3>Para habilitar esta etapa, precisamos de</h3>
              <ol className="steps">
                {q.data.missing.map((m) => <li key={m}>{m}</li>)}
              </ol>
            </div>
            <div>
              <h3>Fora do escopo desta demonstração</h3>
              <ul className="plain-list">
                {q.data.not_included.map((m) => <li key={m}><Icon name="x" size={14} />{m}</li>)}
              </ul>
            </div>
          </div>
          <p className="sedif-foot">
            Enquanto isso, os dados aprovados podem ser conferidos em planilha pela{" "}
            <a href={href("/documentos?status=aprovado")}>lista de documentos aprovados</a>, usando “Exportar CSV”.
            Esse arquivo é genérico e não deve ser importado no SEDIF.
          </p>
        </section>
      )}
    </>
  );
}
