"""Modelos Pydantic de entrada e saída da API."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

FieldKind = Literal["texto", "cpf_cnpj", "data", "valor", "numero"]
FieldSource = Literal["auto", "simulado", "manual", "nao_identificado"]


# ---------- Clientes ----------
class ClientOut(BaseModel):
    id: int
    name: str
    document: str
    person_kind: Literal["PJ", "PF"]
    city: Optional[str] = None
    is_demo: bool
    document_count: int = 0
    pending_count: int = 0


class ClientRef(BaseModel):
    id: int
    name: str


# ---------- Tipos documentais ----------
class FieldDefIn(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    kind: FieldKind
    search_labels: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("label")
    @classmethod
    def _strip_label(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("rótulo vazio")
        return v

    @field_validator("search_labels")
    @classmethod
    def _clean_labels(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip()[:60] for s in v if s and s.strip()]
        return list(dict.fromkeys(cleaned))


class FieldDefOut(BaseModel):
    key: str
    label: str
    kind: FieldKind
    search_labels: list[str]
    position: int


class DocTypeIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)
    fields: list[FieldDefIn] = Field(min_length=1, max_length=30)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("fields")
    @classmethod
    def _unique_labels(cls, v: list[FieldDefIn]) -> list[FieldDefIn]:
        seen: set[str] = set()
        for f in v:
            low = f.label.lower()
            if low in seen:
                raise ValueError(f"campo “{f.label}” repetido")
            seen.add(low)
        return v


class DocTypeOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_system: bool
    fields: list[FieldDefOut]
    document_count: int = 0


class DocTypeRef(BaseModel):
    id: str
    name: str


# ---------- Documentos ----------
class FieldValueOut(BaseModel):
    key: str
    label: str
    kind: FieldKind
    value: Optional[str] = None
    source: FieldSource
    evidence: Optional[str] = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class HistoryOut(BaseModel):
    id: int
    at: str
    action: str
    action_label: str
    status_from: Optional[str] = None
    status_to: Optional[str] = None
    detail: Optional[str] = None
    actor: str


class DocumentSummary(BaseModel):
    id: int
    code: str
    client: ClientRef
    type: DocTypeRef
    original_filename: str
    mime: str
    size_bytes: int
    received_at: str
    uploaded_at: str
    status: str
    status_label: str
    pending_fields: int
    is_demo: bool


class DocumentDetail(DocumentSummary):
    extraction_method: Optional[str] = None
    extraction_method_label: Optional[str] = None
    extraction_note: Optional[str] = None
    error_message: Optional[str] = None
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[str] = None
    fields: list[FieldValueOut]
    history: list[HistoryOut]
    can_edit: bool
    can_reprocess: bool


class DocumentListOut(BaseModel):
    items: list[DocumentSummary]
    total: int


class DocumentMetaIn(BaseModel):
    client_id: Optional[int] = None
    type_id: Optional[str] = None
    received_at: Optional[date] = None


class FieldValueIn(BaseModel):
    key: str
    value: Optional[str] = Field(default=None, max_length=500)


class SaveFieldsIn(BaseModel):
    fields: list[FieldValueIn] = Field(max_length=60)


class ApproveIn(BaseModel):
    fields: Optional[list[FieldValueIn]] = Field(default=None, max_length=60)
    note: Optional[str] = Field(default=None, max_length=1000)


class RejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


# ---------- Painel ----------
class ActivityOut(BaseModel):
    id: int
    at: str
    action: str
    action_label: str
    detail: Optional[str] = None
    document_id: int
    document_code: str
    client_name: str
    status_to: Optional[str] = None


class DashboardOut(BaseModel):
    total: int
    by_status: dict[str, int]
    awaiting_review: int
    processed: int
    approved: int
    rejected: int
    with_problems: int
    errors: int
    with_unidentified: int
    received_last_7_days: int
    recent_activity: list[ActivityOut]
