// Cliente da API do backend DocuFlow (mesma origem).

export type StatusId =
  | "recebido"
  | "em_processamento"
  | "aguardando_revisao"
  | "aprovado"
  | "rejeitado"
  | "erro";

export type FieldKind = "texto" | "cpf_cnpj" | "data" | "valor" | "numero";
export type FieldSource = "auto" | "simulado" | "manual" | "nao_identificado";

export interface Client {
  id: number;
  name: string;
  document: string;
  person_kind: "PJ" | "PF";
  city: string | null;
  is_demo: boolean;
  document_count: number;
  pending_count: number;
}

export interface FieldDef {
  key: string;
  label: string;
  kind: FieldKind;
  search_labels: string[];
  position: number;
}

export interface DocType {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  fields: FieldDef[];
  document_count: number;
}

export interface DocumentSummary {
  id: number;
  code: string;
  client: { id: number; name: string };
  type: { id: string; name: string };
  original_filename: string;
  mime: string;
  size_bytes: number;
  received_at: string;
  uploaded_at: string;
  status: StatusId;
  status_label: string;
  pending_fields: number;
  is_demo: boolean;
}

export interface FieldValue {
  key: string;
  label: string;
  kind: FieldKind;
  value: string | null;
  source: FieldSource;
  evidence: string | null;
  errors: string[];
  warnings: string[];
}

export interface HistoryEntry {
  id: number;
  at: string;
  action: string;
  action_label: string;
  status_from: StatusId | null;
  status_to: StatusId | null;
  detail: string | null;
  actor: string;
}

export interface DocumentDetail extends DocumentSummary {
  extraction_method: string | null;
  extraction_method_label: string | null;
  extraction_note: string | null;
  error_message: string | null;
  rejection_reason: string | null;
  reviewed_at: string | null;
  fields: FieldValue[];
  history: HistoryEntry[];
  can_edit: boolean;
  can_reprocess: boolean;
}

export interface Activity {
  id: number;
  at: string;
  action: string;
  action_label: string;
  detail: string | null;
  document_id: number;
  document_code: string;
  client_name: string;
  status_to: StatusId | null;
}

export interface Dashboard {
  total: number;
  by_status: Record<StatusId, number>;
  awaiting_review: number;
  processed: number;
  approved: number;
  rejected: number;
  with_problems: number;
  errors: number;
  with_unidentified: number;
  received_last_7_days: number;
  recent_activity: Activity[];
}

export interface Meta {
  statuses: { id: StatusId; label: string }[];
  capabilities: { pdf_text: boolean; ocr: boolean; ocr_lang: string | null };
  max_upload_mb: number;
  today: string;
}

export interface SedifStatus {
  available: boolean;
  summary: string;
  reason: string;
  missing: string[];
  not_included: string[];
}

export class ApiError extends Error {
  status: number;
  details: unknown;
  constructor(status: number, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Sem conexão com o servidor da demonstração. Verifique se ele está em execução.");
  }
  const isJson = (res.headers.get("content-type") || "").includes("application/json");
  const body = isJson ? await res.json() : null;
  if (!res.ok) {
    const message = (body && body.error) || `Falha na operação (código ${res.status}).`;
    throw new ApiError(res.status, message, body?.details);
  }
  return body as T;
}

const json = (method: string, data?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: data === undefined ? undefined : JSON.stringify(data),
});

export type DocQuery = Partial<{
  client_id: string;
  type_id: string;
  status: string;
  received_from: string;
  received_to: string;
  q: string;
  pending: string;
  sort: string;
}>;

export function queryString(q: DocQuery): string {
  const p = new URLSearchParams();
  Object.entries(q).forEach(([k, v]) => {
    if (v) p.set(k, v);
  });
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const api = {
  meta: () => request<Meta>("/api/meta"),
  dashboard: () => request<Dashboard>("/api/dashboard"),
  clients: () => request<Client[]>("/api/clients"),
  docTypes: () => request<DocType[]>("/api/doc-types"),
  createDocType: (data: unknown) => request<DocType>("/api/doc-types", json("POST", data)),
  updateDocType: (id: string, data: unknown) => request<DocType>(`/api/doc-types/${id}`, json("PUT", data)),
  deleteDocType: (id: string) => request<{ deleted: string }>(`/api/doc-types/${id}`, { method: "DELETE" }),
  documents: (q: DocQuery) => request<{ items: DocumentSummary[]; total: number }>(`/api/documents${queryString(q)}`),
  document: (id: number) => request<DocumentDetail>(`/api/documents/${id}`),
  upload: (form: FormData) => request<DocumentDetail>("/api/documents", { method: "POST", body: form }),
  updateMeta: (id: number, data: unknown) => request<DocumentDetail>(`/api/documents/${id}`, json("PATCH", data)),
  process: (id: number) => request<DocumentDetail>(`/api/documents/${id}/process`, { method: "POST" }),
  saveFields: (id: number, fields: { key: string; value: string | null }[]) =>
    request<DocumentDetail>(`/api/documents/${id}/fields`, json("PUT", { fields })),
  approve: (id: number, fields: { key: string; value: string | null }[], note?: string) =>
    request<DocumentDetail>(`/api/documents/${id}/approve`, json("POST", { fields, note: note || null })),
  reject: (id: number, reason: string) => request<DocumentDetail>(`/api/documents/${id}/reject`, json("POST", { reason })),
  reopen: (id: number) => request<DocumentDetail>(`/api/documents/${id}/reopen`, { method: "POST" }),
  addNote: (id: number, text: string) => request<DocumentDetail>(`/api/documents/${id}/notes`, json("POST", { text })),
  sedifStatus: () => request<SedifStatus>("/api/exports/sedif/status"),
  fileUrl: (id: number, download = false) => `/api/documents/${id}/file${download ? "?download=1" : ""}`,
  csvUrl: (q: DocQuery) => `/api/exports/documents.csv${queryString(q)}`,
};
