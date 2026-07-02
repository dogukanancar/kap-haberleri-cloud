from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

from src.models import CdsSnapshot

logger = logging.getLogger(__name__)

ISTANBUL = ZoneInfo("Europe/Istanbul")
INVESTING_URL = "https://tr.investing.com/rates-bonds/turkey-cds-5-year-usd"
WGB_COUNTRY_URL = "https://www.worldgovernmentbonds.com/country/turkey/"
WGB_API_URL = "https://www.worldgovernmentbonds.com/wp-json/country/v1/main"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}


class CdsFetchError(Exception):
    """CDS verisi alinamadiginda firlatilir."""


def _parse_optional_float(raw: object) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


_RATING_AGENCIES = (
    "Standard & Poor's",
    "Moody's Investors Service",
    "Fitch Ratings",
    "DBRS",
)


def _parse_ratings_table(html: str) -> dict[str, str | None]:
    ratings = {agency: None for agency in _RATING_AGENCIES}
    if not html:
        return ratings

    for match in re.finditer(
        r"<td>([^<]+)</td>\s*<td[^>]*class=\"w3-center\"[^>]*>([^<]*)</td>",
        html,
        re.I | re.S,
    ):
        agency = match.group(1).strip()
        value = match.group(2).strip() or None
        if agency in ratings:
            ratings[agency] = value

    return ratings


def fetch_turkey_cds_5y(*, timeout: int = 30) -> CdsSnapshot:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    try:
        page = session.get(WGB_COUNTRY_URL, timeout=timeout)
        page.raise_for_status()
    except requests.RequestException as exc:
        raise CdsFetchError(f"CDS kaynak sayfasi alinamadi: {exc}") from exc

    match = re.search(r"jsGlobalVars\s*=\s*(\{.*?\});", page.text, re.S)
    if not match:
        raise CdsFetchError("CDS sayfa yapilandirmasi okunamadi.")

    try:
        global_vars = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise CdsFetchError("CDS sayfa yapilandirmasi gecersiz.") from exc

    try:
        response = session.post(
            WGB_API_URL,
            json={"GLOBALVAR": global_vars},
            headers={
                "Content-Type": "application/json",
                "Referer": WGB_COUNTRY_URL,
                "Origin": "https://www.worldgovernmentbonds.com",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise CdsFetchError(f"CDS API istegi basarisiz: {exc}") from exc
    except ValueError as exc:
        raise CdsFetchError("CDS API yaniti gecersiz JSON.") from exc

    if not payload.get("success"):
        message = payload.get("message") or "Bilinmeyen hata"
        raise CdsFetchError(f"CDS API basarisiz: {message}")

    value_bp = _parse_optional_float(payload.get("lastCds"))
    if value_bp is None:
        raise CdsFetchError("CDS degeri bulunamadi.")

    ratings = _parse_ratings_table(str(payload.get("ratingTable") or ""))

    return CdsSnapshot(
        value_bp=value_bp,
        bond_10y_pct=_parse_optional_float(payload.get("bond10y")),
        cb_rate_pct=_parse_optional_float(payload.get("cbRateNumber")),
        cb_rate_date=str(payload.get("cbRateDate") or "").strip() or None,
        rating_sp=ratings["Standard & Poor's"],
        rating_moodys=ratings["Moody's Investors Service"],
        rating_fitch=ratings["Fitch Ratings"],
        rating_dbrs=ratings["DBRS"],
        as_of_date=str(payload.get("lastDataValDesc") or "").strip() or None,
        as_of_time=str(payload.get("lastTimeValDesc") or "").strip() or None,
        wgb_url=WGB_COUNTRY_URL,
        investing_url=INVESTING_URL,
        fetched_at=datetime.now(timezone.utc),
    )
