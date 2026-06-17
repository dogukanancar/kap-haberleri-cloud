from __future__ import annotations

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.brand_fetcher import fetch_turkiye125_report
from src.brand_schedule import evaluate_send_window, get_schedule_config, record_scheduled_send
from src.brand_snapshot import compare_report, load_snapshot, save_snapshot
from src.config import get_settings
from src import repository
from src import telegram_bot

logger = logging.getLogger(__name__)

ISTANBUL = ZoneInfo("Europe/Istanbul")


def _today_istanbul() -> str:
    return datetime.now(ISTANBUL).date().isoformat()


def _resolve_target() -> tuple[str, int | None]:
    settings = get_settings()
    chat_id = (
        repository.get_setting("brand_telegram_chat_id", "").strip()
        or (settings.default_telegram_chat_id or "").strip()
    )
    topic_raw = repository.get_setting("brand_telegram_topic_id", "").strip()
    topic_id = int(topic_raw) if topic_raw else None
    return chat_id, topic_id


def _report_year() -> int:
    return max(2000, int(repository.get_setting("brand_rapor_yili", "2026") or "2026"))


def _mark_checked(today: str) -> None:
    repository.set_setting("son_brand_kontrol_tarihi", today)
    repository.set_setting("son_brand_kontrol_zamani", datetime.now(timezone.utc).isoformat())


def run_brand_worker(*, force: bool = False) -> dict[str, str | bool | int]:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN tanimli degil.")

    if repository.get_setting("brand_worker_aktif", "1") != "1":
        repository.log_event("INFO", "brand_worker", "Brand worker pasif.")
        return {"status": "skipped", "reason": "inactive"}

    today = _today_istanbul()
    can_send, reason, due_slot = evaluate_send_window(force=force)
    if not can_send:
        config = get_schedule_config()
        repository.log_event(
            "INFO",
            "brand_worker",
            "Brand kontrolu atlandi.",
            detail=(
                f"reason={reason}, plan={config.send_times_display}, "
                f"completed={config.completed_display}"
            ),
        )
        return {"status": "skipped", "reason": reason}

    chat_id, topic_id = _resolve_target()
    if not chat_id:
        repository.log_event("WARNING", "brand_worker", "Brand Telegram chat ID tanimli degil.")
        return {"status": "skipped", "reason": "missing_chat_id"}

    if chat_id.startswith("-100") and topic_id is None:
        repository.log_event(
            "WARNING",
            "brand_worker",
            "Grup chat ID var ama topic ID yok; Genel konuya gidebilir.",
        )

    report = fetch_turkiye125_report(year=_report_year())
    previous = load_snapshot()
    result = compare_report(report, previous)

    save_snapshot(report)

    telegram_bot.send_brand_alert(
        settings.telegram_bot_token,
        chat_id,
        report,
        new_report=result.new_report,
        ranking_changed=result.ranking_changed,
        check_date=today,
        message_thread_id=topic_id,
    )
    _mark_checked(today)
    if not force and due_slot:
        record_scheduled_send(due_slot)
    repository.set_setting("son_brand_gonderim_tarihi", today)
    repository.log_event(
        "INFO",
        "brand_worker",
        "Brand uyari mesaji gonderildi.",
        detail=(
            f"first_run={result.is_first_run}, "
            f"new_report={result.new_report}, "
            f"ranking_changed={result.ranking_changed}, "
            f"publication_id={report.publication_id}"
        ),
    )

    return {
        "status": "sent",
        "new_report": result.new_report,
        "ranking_changed": result.ranking_changed,
        "companies_total": len(report.entries),
        "date": today,
        "first_run": result.is_first_run,
    }
