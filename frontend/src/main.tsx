import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, type Meta } from "./api";
import { href, useRoute } from "./lib";
import { EmptyState, Icon, LinkButton, ToastProvider } from "./ui";
import DashboardPage from "./pages/Dashboard";
import DocumentsPage from "./pages/Documents";
import UploadPage from "./pages/Upload";
import ReviewPage from "./pages/Review";
import ClientsPage from "./pages/Clients";
import DocTypesPage from "./pages/DocTypes";
import SedifPage from "./pages/Sedif";
import "./styles.css";

function App() {
  const route = useRoute();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [pending, setPending] = useState<number | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const routeKey = route.path.join("/") + "?" + route.query.toString();

  useEffect(() => { api.meta().then(setMeta).catch(() => setMeta(null)); }, []);
  useEffect(() => {
    setMenuOpen(false);
    api.dashboard().then((d) => setPending(d.awaiting_review)).catch(() => setPending(null));
    window.scrollTo(0, 0);
  }, [routeKey]);
  useEffect(() => {
    const titles: Record<string, string> = {
      "": "Painel", documentos: "Documentos", clientes: "Clientes", tipos: "Tipos de documento", sedif: "Exportação SEDIF",
    };
    document.title = `${titles[route.path[0] || ""] || "DocuFlow"} | DocuFlow (demonstração)`;
  }, [routeKey]);

  const [section, sub] = route.path;
  const isQueue = section === "documentos" && route.query.get("status") === "aguardando_revisao" && !sub;

  let page: React.ReactNode;
  if (!section || section === "painel") page = <DashboardPage />;
  else if (section === "documentos" && sub === "novo") page = <UploadPage meta={meta} />;
  else if (section === "documentos" && sub && /^\d+$/.test(sub)) page = <ReviewPage key={sub} id={Number(sub)} meta={meta} />;
  else if (section === "documentos" && !sub) page = <DocumentsPage route={route} />;
  else if (section === "clientes") page = <ClientsPage />;
  else if (section === "tipos") page = <DocTypesPage />;
  else if (section === "sedif") page = <SedifPage />;
  else page = (
    <EmptyState icon="search" title="Página não encontrada" action={<LinkButton href={href("/")} variant="primary">Ir para o painel</LinkButton>}>
      O endereço acessado não existe nesta demonstração.
    </EmptyState>
  );

  const nav = [
    { to: "/", icon: "dashboard", label: "Painel", active: !section || section === "painel" },
    { to: "/documentos", icon: "file", label: "Documentos", active: section === "documentos" && !isQueue },
    { to: "/documentos?status=aguardando_revisao", icon: "review", label: "Revisão", active: isQueue, badge: pending },
    { to: "/clientes", icon: "building", label: "Clientes", active: section === "clientes" },
    { to: "/sedif", icon: "export", label: "Exportação SEDIF", active: section === "sedif" },
  ];

  return (
    <div className={`shell ${menuOpen ? "menu-open" : ""}`}>
      <a className="skip-link" href="#conteudo">Ir para o conteúdo</a>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><span /><span /><span /></span>
          <span className="brand-name">DocuFlow</span>
          <button className="icon-btn menu-btn" aria-label={menuOpen ? "Fechar menu" : "Abrir menu"} aria-expanded={menuOpen}
            onClick={() => setMenuOpen(!menuOpen)}>
            <Icon name={menuOpen ? "x" : "menu"} />
          </button>
        </div>
        <nav className="nav" aria-label="Navegação principal">
          {nav.map((n) => (
            <a key={n.label} href={href(n.to)} className={n.active ? "active" : ""} aria-current={n.active ? "page" : undefined}>
              <Icon name={n.icon} />
              <span>{n.label}</span>
              {n.badge ? <span className="nav-badge" aria-label={`${n.badge} aguardando`}>{n.badge}</span> : null}
            </a>
          ))}
          <div className="nav-group">Configuração</div>
          <a href={href("/tipos")} className={section === "tipos" ? "active" : ""} aria-current={section === "tipos" ? "page" : undefined}>
            <Icon name="sliders" />
            <span>Tipos de documento</span>
          </a>
        </nav>
        <div className="sidebar-foot">
          <strong>Escritório Demonstração</strong>
          <span>Dados fictícios. Sem integração com SEFAZ, TED ou SEDIF.</span>
        </div>
      </aside>
      <div className="main">
        <div className="demo-bar" role="note">
          <Icon name="info" size={15} />
          <span>Ambiente de demonstração com dados fictícios. Não é um sistema fiscal pronto para produção.</span>
        </div>
        <main id="conteudo" className="content">{page}</main>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <ToastProvider>
    <App />
  </ToastProvider>,
);
