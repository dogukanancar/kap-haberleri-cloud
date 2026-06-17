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


@dataclass(frozen=True)
class CdsSnapshot:
    value_bp: float
    default_prob_pct: float | None
    as_of_date: str | None
    as_of_time: str | None
    wgb_url: str
    investing_url: str
    fetched_at: datetime


@dataclass(frozen=True)
class BrandEntry:
    rank: int
    name: str
    slug: str
    brand_value_usd_m: float
    brand_rating: str | None
    bsi: float | None
    enterprise_value_usd_m: float | None
    previous_rank: int | None
    previous_value_usd_m: float | None
    logo_url: str | None


@dataclass(frozen=True)
class BrandReport:
    publication_id: int
    year: int
    title: str
    subtitle: str
    overview: str
    report_url: str
    released_at: str | None
    entries: tuple[BrandEntry, ...]
    fetched_at: datetime


@dataclass(frozen=True)
class BrandCheckResult:
    is_first_run: bool
    new_report: bool
    ranking_changed: bool
    should_notify: bool


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
    telegram_topic_id: str | None = None
