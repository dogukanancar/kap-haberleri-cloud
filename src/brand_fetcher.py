from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import unescape

import requests

from src.models import BrandEntry, BrandReport

ADMIN_API = "https://admin.brandirectory.com"
REPORT_PAGE_URL = "https://brandirectory.com/reports/turkiye/{year}"
BRAND_PAGE_URL = "https://brandirectory.com/brands/{slug}"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}


class BrandFetchError(Exception):
    """Brandirectory verisi alinamadiginda firlatilir."""


def _strip_html(raw: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_float(raw: object) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_int(raw: object) -> int | None:
    value = _parse_float(raw)
    return int(value) if value is not None else None


def _request_json(path: str, *, timeout: int = 60) -> dict:
    response = requests.get(
        f"{ADMIN_API}{path}",
        headers=DEFAULT_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "success" and "data" not in payload:
        message = payload.get("message") or "Bilinmeyen hata"
        raise BrandFetchError(f"Brandirectory API basarisiz: {message}")
    return payload


def _find_publication_id(*, year: int) -> int:
    payload = _request_json("/api/publications")
    publications = payload.get("data", [])
    matches: list[dict] = []
    for publication in publications:
        series = publication.get("series") or {}
        if series.get("slug") != "turkiye":
            continue
        haystack = " ".join(
            str(publication.get(key) or "")
            for key in ("title", "slug", "subtitle")
        ).lower()
        if str(year) in haystack:
            matches.append(publication)

    if not matches:
        raise BrandFetchError(f"{year} yili icin Turkiye raporu bulunamadi.")

    matches.sort(key=lambda item: item.get("released_at") or "", reverse=True)
    return int(matches[0]["id"])


def _map_brand_entry(raw: dict) -> BrandEntry:
    previous = raw.get("previous_details") or {}
    logo = raw.get("logo") or {}
    return BrandEntry(
        rank=int(raw["rank"]),
        name=str(raw.get("name") or "-"),
        slug=str(raw.get("slug") or ""),
        brand_value_usd_m=_parse_float(raw.get("brand_value")) or 0.0,
        brand_rating=str(raw.get("brand_rating") or "").strip() or None,
        bsi=_parse_float(raw.get("bsi")),
        enterprise_value_usd_m=_parse_float(raw.get("enterprise_value")),
        previous_rank=_parse_int(previous.get("rank")),
        previous_value_usd_m=_parse_float(previous.get("brand_value")),
        logo_url=str(logo.get("url") or "").strip() or None,
    )


def fetch_turkiye125_report(*, year: int = 2026, timeout: int = 60) -> BrandReport:
    publication_id = _find_publication_id(year=year)
    payload = _request_json(f"/api/publications/{publication_id}", timeout=timeout)
    data = payload.get("data") or {}

    rankings = data.get("rankings") or []
    if not rankings:
        raise BrandFetchError("Rapor siralamasi bulunamadi.")

    brand_rows = rankings[0].get("brand_details") or []
    if not brand_rows:
        raise BrandFetchError("Rapor sirket listesi bos.")

    entries = sorted(
        (_map_brand_entry(row) for row in brand_rows),
        key=lambda item: item.rank,
    )

    reports = data.get("reports") or []
    turkish_report = None
    for report in reports:
        language = report.get("language") or {}
        if language.get("code") == "tr":
            turkish_report = report
            break
    if turkish_report is None and reports:
        turkish_report = reports[0]

    overview_html = str((turkish_report or {}).get("extract") or "")
    overview_text = _strip_html(overview_html)

    return BrandReport(
        publication_id=publication_id,
        year=year,
        title=str(data.get("title") or f"Turkiye 125 {year}"),
        subtitle=str(data.get("subtitle") or ""),
        overview=overview_text,
        report_url=REPORT_PAGE_URL.format(year=year),
        released_at=str(data.get("released_at") or "").strip() or None,
        entries=tuple(entries),
        fetched_at=datetime.now(timezone.utc),
    )
