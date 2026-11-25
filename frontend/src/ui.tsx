// Componentes de interface compartilhados.
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { FieldSource, StatusId } from "./api";

// ---------------- ícones (traço simples, 24x24)
const PATHS: Record<string, string> = {
  dashboard: "M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z",
  file: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6",
  review: "M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9",
  building: "M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16M16 9h3a1 1 0 0 1 1 1v11M2 21h20M8 7h4M8 11h4M8 15h4",
  sliders: "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4",
  export: "M12 3v12M7 8l5-5 5 5M5 15v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4",
  upload: "M12 16V4M7 9l5-5 5 5M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3",
  download: "M12 4v12M7 11l5 5 5-5M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
  x: "M6 6l12 12M18 6L6 18",
  alert: "M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  check: "M5 12l5 5L20 7",
  refresh: "M20 11a8 8 0 0 0-14.9-3M4 4v4h4M4 13a8 8 0 0 0 14.9 3M20 20v-4h-4",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5M12 8h.01",
  back: "M15 18l-6-6 6-6",
  plus: "M12 5v14M5 12h14",
  trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13M9 7V4h6v3",
  note: "M4 5h16v11H8l-4 4zM8 9h8M8 12h5",
  open: "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
  menu: "M4 6h16M4 12h16M4 18h16",
};

export function Icon({ name, size = 18, className }: { name: keyof typeof PATHS | string; size?: number; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name] || ""} />
    </svg>
  );
}

// ---------------- status e origem dos campos
export const STATUS_LABELS: Record<StatusId, string> = {
  recebido: "Recebido",
  em_processamento: "Em processamento",
  aguardando_revisao: "Aguardando revisão",
  aprovado: "Aprovado",
  rejeitado: "Rejeitado",
  erro: "Erro",
};

export function StatusBadge({ status }: { status: StatusId }) {
  return <span className={`status status-${status}`}>{STATUS_LABELS[status] || status}</span>;
}

export const SOURCE_LABELS: Record<FieldSource, string> = {
  auto: "Extração local",
  simulado: "Simulado",
  manual: "Editado",
  nao_identificado: "Não identificado",
};

export function SourceTag({ source }: { source: FieldSource }) {
  return <span className={`source source-${source}`}>{SOURCE_LABELS[source]}</span>;
}

// ---------------- botões
type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  icon?: string;
  busy?: boolean;
};

export function Button({ variant = "secondary", icon, busy, children, className = "", disabled, ...rest }: ButtonProps) {
  return (
    <button className={`btn btn-${variant} ${className}`} disabled={disabled || busy} aria-busy={busy || undefined} {...rest}>
      {busy ? <span className="spinner" aria-hidden="true" /> : icon ? <Icon name={icon} size={16} /> : null}
      {children && <span>{children}</span>}
    </button>
  );
}

export function LinkButton({ href, variant = "secondary", icon, children, ...rest }:
  React.AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: string; icon?: string }) {
  return (
    <a href={href} className={`btn btn-${variant}`} {...rest}>
      {icon && <Icon name={icon} size={16} />}
      <span>{children}</span>
    </a>
  );
}

// ---------------- avisos (toast)
type Toast = { id: number; kind: "success" | "error" | "info"; text: string };
const ToastCtx = createContext<(kind: Toast["kind"], text: string) => void>(() => {});

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const counter = useRef(0);
  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = ++counter.current;
    setItems((cur) => [...cur, { id, kind, text }]);
    setTimeout(() => setItems((cur) => cur.filter((t) => t.id !== id)), kind === "error" ? 7000 : 4000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <Icon name={t.kind === "success" ? "check" : t.kind === "error" ? "alert" : "info"} size={16} />
            <span>{t.text}</span>
            <button className="toast-close" aria-label="Fechar aviso" onClick={() => setItems((c) => c.filter((x) => x.id !== t.id))}>
              <Icon name="x" size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);

// ---------------- modal
export function Modal({ title, onClose, children, footer, width = 520 }: {
  title: string; onClose: () => void; children: React.ReactNode; footer?: React.ReactNode; width?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const first = ref.current?.querySelector<HTMLElement>("input, textarea, select, button:not(.modal-close)");
    first?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} style={{ maxWidth: width }} ref={ref}>
        <header className="modal-head">
          <h2>{title}</h2>
          <button className="modal-close icon-btn" onClick={onClose} aria-label="Fechar"><Icon name="x" /></button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </div>
    </div>
  );
}

// ---------------- estados
export function EmptyState({ icon = "file", title, children, action }: {
  icon?: string; title: string; children?: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon"><Icon name={icon} size={22} /></div>
      <h3>{title}</h3>
      {children && <div className="empty-text">{children}</div>}
      {action && <div className="empty-action">{action}</div>}
    </div>
  );
}

export function Loading({ label = "Carregando…" }: { label?: string }) {
  return <div className="loading"><span className="spinner" aria-hidden="true" />{label}</div>;
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="notice notice-error" role="alert">
      <Icon name="alert" size={18} />
      <div className="notice-body">
        <strong>Não foi possível carregar os dados.</strong>
        <span>{message}</span>
      </div>
      {onRetry && <Button variant="ghost" icon="refresh" onClick={onRetry}>Tentar novamente</Button>}
    </div>
  );
}

export function Notice({ kind = "info", title, children, icon }: {
  kind?: "info" | "warning" | "error" | "simulated"; title?: string; children: React.ReactNode; icon?: string;
}) {
  return (
    <div className={`notice notice-${kind}`}>
      <Icon name={icon || (kind === "info" || kind === "simulated" ? "info" : "alert")} size={18} />
      <div className="notice-body">
        {title && <strong>{title}</strong>}
        <span>{children}</span>
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions, back }: {
  title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; back?: { href: string; label: string };
}) {
  return (
    <header className="page-head">
      <div>
        {back && <a className="back-link" href={back.href}><Icon name="back" size={16} />{back.label}</a>}
        <h1>{title}</h1>
        {subtitle && <p className="page-sub">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

// ---------------- carregamento assíncrono
export function useAsync<T>(fn: () => Promise<T>, deps: React.DependencyList) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fn()
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e?.message || "Erro desconhecido."))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, loading, reload: () => setTick((t) => t + 1), setData };
}
