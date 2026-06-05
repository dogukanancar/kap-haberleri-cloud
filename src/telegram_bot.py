from __future__ import annotations

import html
import logging

import requests

from src.models import Disclosure

logger = logging.getLogger(__name__)


def format_disclosure_message(
    disclosure: Disclosure,
    *,
    anahtar_kelime: str | None = None,
) -> str:
    keyword = html.escape(anahtar_kelime or disclosure.subject or "-")
    konu = html.escape(disclosure.subject or "-")
    ozet = html.escape(disclosure.summary or disclosure.title or "-")
    sirket = html.escape(disclosure.company_code or disclosure.company_name or "-")
    kap_url = html.escape(disclosure.url)

    return "\n".join(
        [
            f"<b>Anahtar Kelime :</b> {keyword}",
            f"<b>Konu :</b> {konu}",
            f"<b>Özet :</b> {ozet}",
            f"<b>İlgili Şirketler :</b> {sirket}",
            f'<b>Kap Link :</b> <a href="{kap_url}">{kap_url}</a>',
        ]
    )


def send_message(
    token: str,
    chat_id: str,
    text: str,
    *,
    message_thread_id: int | None = None,
    disable_preview: bool = True,
    timeout: int = 20,
) -> None:
    payload: dict[str, object] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_preview,
    }
    if message_thread_id is not None:
        payload["message_thread_id"] = message_thread_id
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()


def send_disclosure(
    token: str,
    chat_id: str,
    disclosure: Disclosure,
    *,
    anahtar_kelime: str | None = None,
    message_thread_id: int | None = None,
) -> None:
    message = format_disclosure_message(disclosure, anahtar_kelime=anahtar_kelime)
    send_message(token, chat_id, message, message_thread_id=message_thread_id)
