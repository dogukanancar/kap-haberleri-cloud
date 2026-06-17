from __future__ import annotations

import html
import logging

import requests

from src.models import BrandReport, CdsSnapshot, Disclosure

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


def format_cds_message(snapshot: CdsSnapshot) -> str:
    value_text = f"{snapshot.value_bp:.2f} bp"
    lines = [
        "<b>🇹🇷 Türkiye CDS (5Y USD)</b>",
        "",
        f"<b>Değer:</b> {html.escape(value_text)}",
    ]
    if snapshot.default_prob_pct is not None:
        lines.append(
            f"<b>Varsayılan olasılığı:</b> {html.escape(f'{snapshot.default_prob_pct:.2f} %')}"
        )
    if snapshot.as_of_date:
        when = snapshot.as_of_date
        if snapshot.as_of_time:
            when = f"{snapshot.as_of_date} ({snapshot.as_of_time})"
        lines.append(f"<b>Tarih:</b> {html.escape(when)}")

    wgb_url = html.escape(snapshot.wgb_url)
    investing_url = html.escape(snapshot.investing_url)
    lines.extend(
        [
            "",
            "<b>Kaynak:</b>",
            f'<a href="{wgb_url}">World Government Bonds</a>',
            f'<a href="{investing_url}">Investing.com</a>',
        ]
    )
    return "\n".join(lines)


def format_brand_alert_message(
    report: BrandReport,
    *,
    new_report: bool,
    ranking_changed: bool,
    check_date: str,
) -> str:
    report_url = html.escape(report.report_url)
    return "\n".join(
        [
            f"<b>🇹🇷 {html.escape(report.title)}</b>",
            "",
            f"<b>Kontrol:</b> {html.escape(check_date)}",
            f"<b>Yeni rapor:</b> {'Var' if new_report else 'Yok'}",
            f"<b>Sıralamada değişiklik:</b> {'Var' if ranking_changed else 'Yok'}",
            "",
            f'<b>Kaynak:</b> <a href="{report_url}">Brandirectory</a>',
        ]
    )


def send_brand_alert(
    token: str,
    chat_id: str,
    report: BrandReport,
    *,
    new_report: bool,
    ranking_changed: bool,
    check_date: str,
    message_thread_id: int | None = None,
) -> None:
    send_message(
        token,
        chat_id,
        format_brand_alert_message(
            report,
            new_report=new_report,
            ranking_changed=ranking_changed,
            check_date=check_date,
        ),
        message_thread_id=message_thread_id,
    )


def send_cds(
    token: str,
    chat_id: str,
    snapshot: CdsSnapshot,
    *,
    message_thread_id: int | None = None,
) -> None:
    message = format_cds_message(snapshot)
    send_message(token, chat_id, message, message_thread_id=message_thread_id)


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
