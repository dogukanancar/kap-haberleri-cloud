from __future__ import annotations

import json

from src.models import BrandEntry, BrandReport, BrandCheckResult
from src import repository

SNAPSHOT_KEY = "brand_son_snapshot"


def _entry_signature(entry: BrandEntry) -> dict[str, object]:
    return {
        "rank": entry.rank,
        "slug": entry.slug,
        "name": entry.name,
        "value": round(entry.brand_value_usd_m, 2),
    }


def build_snapshot(report: BrandReport) -> dict[str, object]:
    return {
        "publication_id": report.publication_id,
        "year": report.year,
        "title": report.title,
        "rankings": [_entry_signature(entry) for entry in report.entries],
    }


def load_snapshot() -> dict[str, object] | None:
    raw = repository.get_setting(SNAPSHOT_KEY, "").strip()
    if not raw:
        return None
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def save_snapshot(report: BrandReport) -> None:
    repository.set_setting(SNAPSHOT_KEY, json.dumps(build_snapshot(report), ensure_ascii=False))


def compare_report(report: BrandReport, previous: dict[str, object] | None) -> BrandCheckResult:
    if previous is None:
        return BrandCheckResult(
            is_first_run=True,
            new_report=False,
            ranking_changed=False,
            should_notify=False,
        )

    previous_publication_id = previous.get("publication_id")
    new_report = previous_publication_id != report.publication_id

    previous_rankings = previous.get("rankings") or []
    current_rankings = [_entry_signature(entry) for entry in report.entries]
    ranking_changed = list(previous_rankings) != list(current_rankings)

    return BrandCheckResult(
        is_first_run=False,
        new_report=bool(new_report),
        ranking_changed=ranking_changed,
        should_notify=bool(new_report or ranking_changed),
    )
