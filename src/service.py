from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from src.config import get_settings
from src.filters import find_matching_rules, get_matched_keyword
from src.kap_fetcher import fetch_recent_disclosures
from src.models import Disclosure
from src import repository
from src import telegram_bot

logger = logging.getLogger(__name__)


def process_disclosures(disclosures: list[Disclosure]) -> dict[str, int]:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN tanimli degil.")

    rules = repository.list_filter_rules(active_only=True)
    if not rules:
        repository.log_event("WARNING", "service", "Aktif filtre kurali bulunamadi.")
        return {"checked": len(disclosures), "sent": 0, "skipped": len(disclosures)}

    sent_count = 0
    skipped_count = 0

    for disclosure in disclosures:
        matching_rules = find_matching_rules(disclosure, rules)
        if not matching_rules:
            skipped_count += 1
            continue

        for rule in matching_rules:
            if repository.is_disclosure_sent(disclosure.disclosure_index, rule.telegram_chat_id):
                continue

            try:
                topic_id = (
                    int(rule.telegram_topic_id)
                    if rule.telegram_topic_id and rule.telegram_topic_id.strip()
                    else None
                )
                telegram_bot.send_disclosure(
                    settings.telegram_bot_token,
                    rule.telegram_chat_id,
                    disclosure,
                    anahtar_kelime=get_matched_keyword(disclosure, rule),
                    message_thread_id=topic_id,
                )
                repository.mark_disclosure_sent(
                    disclosure_index=disclosure.disclosure_index,
                    sirket_kodu=disclosure.company_code,
                    sirket_adi=disclosure.company_name,
                    konu=disclosure.subject,
                    baslik=disclosure.title,
                    yayin_tarihi=disclosure.publish_time,
                    kap_url=disclosure.url,
                    telegram_chat_id=rule.telegram_chat_id,
                    filtre_kural_id=rule.id,
                )
                sent_count += 1
                repository.log_event(
                    "INFO",
                    "telegram",
                    f"Bildirim gonderildi: {disclosure.disclosure_index}",
                    detail=disclosure.url,
                )
                time.sleep(0.08)
            except Exception as exc:
                repository.log_event(
                    "ERROR",
                    "telegram",
                    f"Gonderim hatasi: {disclosure.disclosure_index}",
                    detail=str(exc),
                )
                logger.exception("Telegram gonderim hatasi")

    repository.set_setting("son_kontrol_zamani", datetime.now(timezone.utc).isoformat())
    return {
        "checked": len(disclosures),
        "sent": sent_count,
        "skipped": skipped_count,
    }


def run_worker_cycle(days: int = 1) -> dict[str, int]:
    repository.log_event("INFO", "worker", "KAP kontrolu basladi.")
    disclosures = fetch_recent_disclosures(days=days)
    result = process_disclosures(disclosures)
    repository.log_event(
        "INFO",
        "worker",
        "KAP kontrolu tamamlandi.",
        detail=f"checked={result['checked']}, sent={result['sent']}, skipped={result['skipped']}",
    )
    return result
