// Formatação (pt-BR) e roteamento por hash.
import { useEffect, useState } from "react";

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const dt = new Date(iso);
  if (isNaN(dt.getTime())) return iso;
  return dt.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function fmtRelative(iso: string): string {
  const dt = new Date(iso);
  const diffMin = Math.round((Date.now() - dt.getTime()) / 60000);
  if (diffMin < 1) return "agora";
  if (diffMin < 60) return `há ${diffMin} min`;
  const h = Math.round(diffMin / 60);
  if (h < 24) return `há ${h} h`;
  const days = Math.round(h / 24);
  if (days === 1) return "ontem";
  if (days < 7) return `há ${days} dias`;
  return fmtDate(iso);
}

export function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} MB`;
}

export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

// ---------------- roteamento
export interface Route {
  path: string[];
  query: URLSearchParams;
}

function parseHash(): Route {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const [path, qs] = raw.split("?");
  return { path: path ? path.split("/").filter(Boolean) : [], query: new URLSearchParams(qs || "") };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(parseHash);
  useEffect(() => {
    const onChange = () => setRoute(parseHash());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

export function navigate(to: string) {
  window.location.hash = to.startsWith("#") ? to : `#${to}`;
}

export function href(to: string): string {
  return `#${to}`;
}
