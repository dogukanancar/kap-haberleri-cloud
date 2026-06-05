from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests

from src.config import get_settings
from src.models import Disclosure

logger = logging.getLogger(__name__)

ISTANBUL = ZoneInfo("Europe/Istanbul")
KAP_QUERY_URL = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
    "Origin": "https://www.kap.org.tr",
    "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
}


class KapFetchError(Exception):
    """KAP verisi alinamadiginda firlatilir."""


def _format_kap_date(value: date) -> str:
    return value.isoformat()


def _parse_publish_time(raw: Any) -> datetime:
    if raw is None:
        return datetime.now(tz=ISTANBUL)
    if isinstance(raw, (int, float)):
        ts = raw / 1000 if raw > 10_000_000_000 else raw
        return datetime.fromtimestamp(ts, tz=ISTANBUL)
    text = str(raw).strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=ISTANBUL)
        except ValueError:
            continue
    return datetime.now(tz=ISTANBUL)


def _build_url(disclosure_index: int | str) -> str:
    base = get_settings().kap_base_url.rstrip("/")
    return f"{base}/tr/Bildirim/{disclosure_index}"


def _map_disclosure(item: dict[str, Any]) -> Disclosure:
    disclosure_index = int(item.get("disclosureIndex") or item.get("index") or 0)
    company_code = item.get("stockCodes") or item.get("stockCode") or item.get("member")
    company_name = item.get("kapTitle") or item.get("companyTitle") or item.get("memberTitle")
    subject = item.get("subject") or item.get("disclosureSubject")
    summary = item.get("summary") or item.get("disclosureSummary") or item.get("abstract")
    title = item.get("title") or summary or subject
    publish_raw = (
        item.get("publishDate")
        or item.get("time")
        or item.get("disclosureDate")
        or item.get("publishDateTime")
    )
    return Disclosure(
        disclosure_index=disclosure_index,
        company_code=str(company_code).strip() if company_code else None,
        company_name=str(company_name).strip() if company_name else None,
        subject=str(subject).strip() if subject else None,
        title=str(title).strip() if title else None,
        publish_time=_parse_publish_time(publish_raw),
        url=_build_url(disclosure_index),
        disclosure_class=item.get("disclosureClass") or item.get("class"),
        summary=str(summary).strip() if summary else None,
        subject_oid=item.get("subjectOid") or item.get("disclosureSubjectOid"),
    )


def _build_payload(
    from_date: date,
    to_date: date,
    *,
    subject_oids: list[str] | None = None,
    disclosure_class: str | None = None,
    company_oids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "fromDate": _format_kap_date(from_date),
        "toDate": _format_kap_date(to_date),
        "memberType": "",
        "mkkMemberOidList": company_oids or [],
        "inactiveMkkMemberOidList": [],
        "disclosureClass": disclosure_class or "",
        "subjectList": subject_oids or [],
        "isLate": "",
        "mainSector": "",
        "sector": "",
        "subSector": "",
        "marketOid": "",
        "index": "",
        "bdkReview": "",
        "bdkMemberOidList": [],
        "year": "",
        "term": "",
        "ruleType": "",
        "period": "",
        "fromSrc": False,
        "srcCategory": "",
        "disclosureIndexList": [],
    }


def _post_query(payload: dict[str, Any], timeout: tuple[int, int]) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = requests.post(
                KAP_QUERY_URL,
                json=payload,
                headers=DEFAULT_HEADERS,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            logger.warning("Beklenmeyen KAP yaniti: %s", type(data))
            return []
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("KAP sorgusu basarisiz (deneme %s/3): %s", attempt, exc)
            if attempt < 3:
                time.sleep(attempt * 2)
    raise KapFetchError(
        "KAP sitesinden veri alinamadi. Internet baglantinizi kontrol edip tekrar deneyin."
    ) from last_error


def fetch_disclosures(
    from_date: date | None = None,
    to_date: date | None = None,
    *,
    subject_oids: list[str] | None = None,
    disclosure_class: str | None = None,
    company_oids: list[str] | None = None,
    timeout: tuple[int, int] = (10, 90),
) -> list[Disclosure]:
    today = datetime.now(tz=ISTANBUL).date()
    from_date = from_date or today
    to_date = to_date or today

    payload = _build_payload(
        from_date,
        to_date,
        subject_oids=subject_oids,
        disclosure_class=disclosure_class,
        company_oids=company_oids,
    )
    rows = _post_query(payload, timeout=timeout)

    disclosures = [_map_disclosure(item) for item in rows if item.get("disclosureIndex")]
    disclosures.sort(key=lambda d: d.publish_time, reverse=True)
    return disclosures


def fetch_recent_disclosures(days: int = 1) -> list[Disclosure]:
    today = datetime.now(tz=ISTANBUL).date()
    if days <= 1:
        return fetch_disclosures(from_date=today, to_date=today)

    seen: dict[int, Disclosure] = {}
    for offset in range(days):
        target = today - timedelta(days=offset)
        for disclosure in fetch_disclosures(from_date=target, to_date=target):
            seen[disclosure.disclosure_index] = disclosure

    disclosures = list(seen.values())
    disclosures.sort(key=lambda d: d.publish_time, reverse=True)
    return disclosures
