from __future__ import annotations

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.cds_fetcher import CdsFetchError, fetch_turkey_cds_5y
from src.cds_schedule import evaluate_send_window, get_schedule_config, record_scheduled_send
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
        repository.get_setting("cds_telegram_chat_id", "").strip()
        or (settings.default_telegram_chat_id or "").strip()
    )
    topic_raw = repository.get_setting("cds_telegram_topic_id", "").strip()
    topic_id = int(topic_raw) if topic_raw else None
    return chat_id, topic_id


def run_cds_worker(*, force: bool = False) -> dict[str, str | float]:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN tanimli degil.")

    if repository.get_setting("cds_worker_aktif", "1") != "1":
        repository.log_event("INFO", "cds_worker", "CDS worker pasif.")
        return {"status": "skipped", "reason": "inactive"}

    can_send, reason, due_slot = evaluate_send_window(force=force)
    if not can_send:
        config = get_schedule_config()
        repository.log_event(
            "INFO",
            "cds_worker",
            "CDS gonderimi atlandi.",
            detail=(
                f"reason={reason}, plan={config.send_times_display}, "
                f"sent={len(config.sent_today)}/{config.daily_count}"
            ),
        )
        return {"status": "skipped", "reason": reason}

    chat_id, topic_id = _resolve_target()
    if not chat_id:
        repository.log_event("WARNING", "cds_worker", "CDS Telegram chat ID tanimli degil.")
        return {"status": "skipped", "reason": "missing_chat_id"}

    if chat_id.startswith("-100") and topic_id is None:
        repository.log_event(
            "WARNING",
            "cds_worker",
            "Grup chat ID var ama topic ID yok; Genel konuya gidebilir.",
        )

    repository.log_event("INFO", "cds_worker", "CDS verisi cekiliyor.")
    snapshot = fetch_turkey_cds_5y()

    telegram_bot.send_cds(
        settings.telegram_bot_token,
        chat_id,
        snapshot,
        message_thread_id=topic_id,
    )

    record_scheduled_send(None if force else due_slot)
    today = _today_istanbul()
    repository.set_setting("son_cds_degeri", f"{snapshot.value_bp:.2f}")
    repository.set_setting("son_cds_kontrol_zamani", datetime.now(timezone.utc).isoformat())
    repository.log_event(
        "INFO",
        "cds_worker",
        "CDS Telegram gonderildi.",
        detail=f"value_bp={snapshot.value_bp:.2f}, date={today}",
    )

    return {
        "status": "sent",
        "value_bp": snapshot.value_bp,
        "date": today,
    }
