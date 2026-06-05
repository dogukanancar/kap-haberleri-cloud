from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Disclosure:
    disclosure_index: int
    company_code: str | None
    company_name: str | None
    subject: str | None
    title: str | None
    publish_time: datetime
    url: str
    disclosure_class: str | None = None
    summary: str | None = None
    subject_oid: str | None = None


@dataclass
class FilterRule:
    id: int
    kural_adi: str
    aktif: bool
    sirket_kodlari: list[str]
    konu_oid_listesi: list[str]
    anahtar_kelimeler: list[str]
    haric_kelimeler: list[str]
    bildirim_sinifi: str | None
    telegram_chat_id: str
