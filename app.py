from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import Settings, get_settings
from src.db import test_connection
from src.filters import find_matching_rules
from src.kap_fetcher import KapFetchError, fetch_recent_disclosures
from src import repository
from src.service import process_disclosures
from src import telegram_bot
from src.models import FilterRule

st.set_page_config(page_title="KAP Haberleri Cloud", page_icon="☁️", layout="wide")


def _group_chat_id(chat_id: str | None) -> bool:
    return bool(chat_id and chat_id.strip().startswith("-100"))


def _test_target_from_rules(
    rules: list[FilterRule],
    *,
    fallback_chat: str = "",
) -> tuple[str, str]:
    active = [r for r in rules if r.aktif]
    for pool in (active, rules):
        for rule in pool:
            if _group_chat_id(rule.telegram_chat_id):
                return rule.telegram_chat_id, rule.telegram_topic_id or ""
    if active:
        return active[0].telegram_chat_id, active[0].telegram_topic_id or ""
    if rules:
        return rules[0].telegram_chat_id, rules[0].telegram_topic_id or ""
    return fallback_chat, ""


def _split_company_codes(value: str) -> list[str]:
    parts = re.split(r"[,;\n\r\t]+|\s+", value.strip())
    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        cleaned = part.strip().upper()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _split_keywords(value: str) -> list[str]:
    parts = re.split(r"[,;\n\r]+", value.strip())
    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        cleaned = part.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def page_dashboard() -> None:
    st.header("Dashboard")
    col1, col2, col3 = st.columns(3)
    col1.metric("Bugun gonderilen", repository.count_sent_today())
    col2.metric("Aktif kural", len(repository.list_filter_rules(active_only=True)))
    col3.metric("Son kontrol", repository.get_setting("son_kontrol_zamani", "-") or "-")

    st.subheader("Son gonderilen bildirimler")
    sent = repository.list_sent_disclosures(limit=20)
    if sent:
        st.dataframe(sent, use_container_width=True)
    else:
        st.info("Henuz gonderilen bildirim yok.")

    st.divider()
    _render_db_clear_section()
    st.divider()
    _render_db_maintenance_section()


def _render_db_clear_section() -> None:
    st.subheader("DB sil veya temizle")
    st.caption("Dikkat: Bu islemler geri alinamaz.")

    counts = repository.get_table_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gonderilen", counts["gonderilen_bildirimler"])
    c2.metric("Kurallar", counts["filtre_kurallari"])
    c3.metric("Loglar", counts["islem_loglari"])
    c4.metric("Ayarlar", counts["uygulama_ayarlari"])

    col_a, col_b, col_c = st.columns(3)
    if col_a.button("Gonderilen bildirimleri temizle", key="clear_sent"):
        deleted = repository.clear_sent_disclosures()
        st.success(f"{deleted} gonderilen bildirim silindi.")
        st.rerun()
    if col_b.button("Loglari temizle", key="clear_logs"):
        deleted = repository.clear_logs()
        st.success(f"{deleted} log kaydi silindi.")
        st.rerun()
    if col_c.button("Gecmisi + loglari temizle", key="clear_history"):
        result = repository.clear_all_data()
        st.success(
            f"Temizlendi: {result['gonderilen']} bildirim, {result['loglar']} log. "
            "Filtre kurallari korundu."
        )
        st.rerun()

    with st.expander("Tum gecmisi sil (onayli)"):
        st.warning(
            "Gonderim gecmisi ve loglar kalici olarak silinir. "
            "Filtre kurallari ve uygulama ayarlari korunur."
        )
        confirm = st.text_input(
            "Onaylamak icin TEMIZLE yazin",
            key="confirm_full_clear",
        )
        if st.button("Tum gecmisi sil", type="primary", key="clear_all"):
            confirm_normalized = confirm.strip().upper().replace("İ", "I")
            if confirm_normalized != "TEMIZLE":
                st.error("Onay metni hatali. TEMIZLE yazmalisiniz.")
            else:
                result = repository.clear_all_data()
                st.success(
                    f"Silindi: {result['gonderilen']} bildirim, {result['loglar']} log. "
                    "Filtre kurallari korundu."
                )
                st.rerun()


def _render_db_maintenance_section() -> None:
    st.subheader("DB Bakim")
    st.caption("Neon PostgreSQL ANALYZE bakimi.")

    counts = repository.get_table_counts()
    st.write(
        f"Toplam kayit: **{sum(counts.values())}** "
        f"({counts['gonderilen_bildirimler']} bildirim, "
        f"{counts['islem_loglari']} log, "
        f"{counts['filtre_kurallari']} kural)"
    )

    log_days = st.number_input(
        "Eski log saklama suresi (gun)",
        min_value=7,
        max_value=365,
        value=90,
        step=1,
    )
    if st.button("Eski loglari temizle", key="purge_logs"):
        deleted = repository.purge_old_logs(days=int(log_days))
        st.success(f"{deleted} eski log kaydi silindi.")
        st.rerun()

    if st.button("Veritabani bakimini calistir", key="run_maintenance"):
        with st.spinner("Bakim yapiliyor..."):
            try:
                steps = repository.run_db_maintenance()
                st.success(f"Bakim tamamlandi ({len(steps)} adim).")
                with st.expander("Yapilan islemler"):
                    st.code("\n".join(steps))
            except Exception as exc:
                st.error(f"Bakim hatasi: {exc}")


def _join_csv(values: list[str]) -> str:
    return ", ".join(values)


def _bildirim_sinifi_index(value: str | None) -> int:
    options = ["", "ODA", "FR", "DG", "FON"]
    normalized = (value or "").upper()
    return options.index(normalized) if normalized in options else 0


def _render_filter_form(
    *,
    form_key: str,
    settings: Settings,
    submit_label: str,
    rule_id: int | None = None,
    initial: dict | None = None,
) -> bool:
    initial = initial or {}
    with st.form(form_key):
        kural_adi = st.text_input(
            "Kural adi",
            value=initial.get("kural_adi", ""),
            placeholder="Ornek: Halka arz",
        )
        aktif = st.checkbox("Aktif", value=initial.get("aktif", True))
        sirket_kodlari = st.text_area(
            "Sirket kodlari (virgulle)",
            value=initial.get("sirket_kodlari", ""),
            placeholder="THYAO, AKBNK",
            height=100,
        )
        anahtar_kelimeler = st.text_input(
            "Anahtar kelimeler (virgulle ayirin)",
            value=initial.get("anahtar_kelimeler", ""),
            placeholder="sermaye artirimi, halka arz",
            help="Bosluklu ifadeler tek kelime sayilir. Ornek: sermaye artirimi",
        )
        haric_kelimeler = st.text_input(
            "Haric kelimeler (virgulle ayirin)",
            value=initial.get("haric_kelimeler", ""),
        )
        bildirim_sinifi = st.selectbox(
            "Bildirim sinifi (opsiyonel)",
            ["", "ODA", "FR", "DG", "FON"],
            index=_bildirim_sinifi_index(initial.get("bildirim_sinifi")),
            format_func=lambda x: x or "Tumu",
        )
        telegram_chat_id = st.text_input(
            "Telegram chat ID",
            value=initial.get("telegram_chat_id", settings.default_telegram_chat_id or ""),
            help="Grup icin -100... ile baslar.",
        )
        telegram_topic_id = st.text_input(
            "Telegram topic ID (opsiyonel)",
            value=initial.get("telegram_topic_id", ""),
            placeholder="184",
            help="Forum grubunda konu ID. t.me/c/.../184 linkindeki son sayi.",
        )
        submitted = st.form_submit_button(submit_label, type="primary")
        if not submitted:
            return False
        if not kural_adi or not telegram_chat_id:
            st.error("Kural adi ve Telegram chat ID zorunlu.")
            return False

        parsed_companies = _split_company_codes(sirket_kodlari)
        parsed_keywords = _split_keywords(anahtar_kelimeler)
        parsed_excludes = _split_keywords(haric_kelimeler)
        if sirket_kodlari.strip() and not parsed_companies:
            st.error("Sirket kodlari okunamadi. Virgul veya satir ile ayirin.")
            return False

        try:
            repository.save_filter_rule(
                rule_id=rule_id,
                kural_adi=kural_adi,
                aktif=aktif,
                sirket_kodlari=parsed_companies,
                konu_oid_listesi=[],
                anahtar_kelimeler=parsed_keywords,
                haric_kelimeler=parsed_excludes,
                bildirim_sinifi=bildirim_sinifi or None,
                telegram_chat_id=telegram_chat_id,
                telegram_topic_id=telegram_topic_id.strip() or None,
            )
        except Exception as exc:
            st.error(f"Kayit basarisiz: {exc}")
            return False

        action = "guncellendi" if rule_id else "kaydedildi"
        st.session_state["filter_save_info"] = (
            f"'{kural_adi}' {action}. "
            f"{len(parsed_companies)} sirket, "
            f"{len(parsed_keywords)} anahtar kelime."
        )
        return True


def page_filters(settings: Settings) -> None:
    st.header("Filtre Kurallari")
    rules = repository.list_filter_rules()

    if "edit_rule_id" not in st.session_state:
        st.session_state.edit_rule_id = None
    if "new_rule_expanded" not in st.session_state:
        st.session_state.new_rule_expanded = not rules

    save_info = st.session_state.pop("filter_save_info", None)
    if save_info:
        st.success(save_info)

    with st.expander(
        "Yeni kural ekle",
        expanded=st.session_state.new_rule_expanded and st.session_state.edit_rule_id is None,
    ):
        if _render_filter_form(
            form_key="new_rule_form",
            settings=settings,
            submit_label="Kaydet",
        ):
            st.session_state.new_rule_expanded = False
            st.rerun()

    st.subheader(f"Mevcut kurallar ({len(rules)})")
    if not rules:
        st.info("Henuz kural yok.")

    for rule in rules:
        with st.container(border=True):
            st.write(f"**{rule.kural_adi}** ({'Aktif' if rule.aktif else 'Pasif'})")
            topic_label = f", Topic: {rule.telegram_topic_id}" if rule.telegram_topic_id else ""
            st.caption(f"Chat: {rule.telegram_chat_id}{topic_label}")
            st.caption(f"Kelimeler: {', '.join(rule.anahtar_kelimeler) or '-'}")
            if rule.sirket_kodlari:
                st.caption(f"Sirket sayisi: {len(rule.sirket_kodlari)}")
                with st.expander("Sirket kodlarini goster"):
                    st.write(_join_csv(rule.sirket_kodlari))
            else:
                st.caption("Sirketler: Tum sirketler")

            col_edit, col_delete = st.columns(2)
            if col_edit.button("Duzenle", key=f"edit_{rule.id}"):
                st.session_state.edit_rule_id = rule.id
                st.rerun()
            if col_delete.button("Sil", key=f"delete_{rule.id}"):
                repository.delete_filter_rule(rule.id)
                if st.session_state.edit_rule_id == rule.id:
                    st.session_state.edit_rule_id = None
                st.rerun()

            if st.session_state.edit_rule_id == rule.id:
                st.divider()
                st.markdown("**Kurali duzenle**")
                if _render_filter_form(
                    form_key=f"edit_rule_form_{rule.id}",
                    settings=settings,
                    submit_label="Guncelle",
                    rule_id=rule.id,
                    initial={
                        "kural_adi": rule.kural_adi,
                        "aktif": rule.aktif,
                        "sirket_kodlari": _join_csv(rule.sirket_kodlari),
                        "anahtar_kelimeler": _join_csv(rule.anahtar_kelimeler),
                        "haric_kelimeler": _join_csv(rule.haric_kelimeler),
                        "bildirim_sinifi": rule.bildirim_sinifi,
                        "telegram_chat_id": rule.telegram_chat_id,
                        "telegram_topic_id": rule.telegram_topic_id or "",
                    },
                ):
                    st.session_state.edit_rule_id = None
                    st.rerun()
                if st.button("Iptal", key=f"cancel_{rule.id}"):
                    st.session_state.edit_rule_id = None
                    st.rerun()


def page_manual_check() -> None:
    st.header("Manuel Kontrol")
    days = st.slider("Kac gunluk bildirim taransin?", 1, 7, 1)

    if st.button("KAP'tan cek ve isle", type="primary"):
        with st.spinner("KAP sorgulaniyor..."):
            try:
                disclosures = fetch_recent_disclosures(days=days)
                result = process_disclosures(disclosures)
            except KapFetchError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Beklenmeyen hata: {exc}")
            else:
                st.success(
                    f"Tamamlandi: {result['checked']} bildirim tarandi, "
                    f"{result['sent']} gonderildi, {result['skipped']} atlandi."
                )

    st.subheader("Onizleme (gonderilmez)")
    if st.button("Kurallara gore onizle"):
        try:
            disclosures = fetch_recent_disclosures(days=days)
            rules = repository.list_filter_rules(active_only=True)
            if not rules:
                st.warning("Aktif kural yok.")
            else:
                matched_rows = []
                for disclosure in disclosures:
                    matching = find_matching_rules(disclosure, rules)
                    if matching:
                        matched_rows.append(
                            {
                                "kural": ", ".join(r.kural_adi for r in matching),
                                "sirket": disclosure.company_code,
                                "konu": disclosure.subject,
                                "ozet": disclosure.summary or disclosure.title,
                                "url": disclosure.url,
                            }
                        )
                st.info(f"{len(disclosures)} bildirim tarandi, {len(matched_rows)} kural eslesmesi.")
                if matched_rows:
                    st.dataframe(matched_rows[:50], use_container_width=True)
                else:
                    st.warning("Hic eslesme yok. Anahtar kelime veya sirket kodlarini kontrol edin.")
        except KapFetchError as exc:
            st.error(str(exc))

    if st.button("Sadece listele"):
        try:
            disclosures = fetch_recent_disclosures(days=days)
        except KapFetchError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Beklenmeyen hata: {exc}")
        else:
            rows = [
                {
                    "index": d.disclosure_index,
                    "sirket": d.company_name or d.company_code,
                    "konu": d.subject,
                    "tarih": d.publish_time.strftime("%d.%m.%Y %H:%M"),
                    "url": d.url,
                }
                for d in disclosures[:50]
            ]
            st.dataframe(rows, use_container_width=True)


def page_settings(settings: Settings) -> None:
    st.header("Ayarlar")
    parsed = urlparse(settings.database_url)
    st.write(f"Veritabani: `Neon PostgreSQL` / `{parsed.path.lstrip('/') or 'postgres'}`")
    st.caption("Otomatik tarama: GitHub Actions (her 5 dakika)")

    try:
        conn_info = test_connection()
        st.success(f"Veritabani baglantisi OK: {conn_info}")
    except Exception as exc:
        st.error(f"Veritabani baglantisi basarisiz: {exc}")

    worker_aktif = st.checkbox(
        "Worker aktif (GitHub Actions)",
        value=repository.get_setting("worker_aktif", "1") == "1",
        help="Kapaliysa GitHub Actions worker calismaz.",
    )

    if st.button("Ayarlari kaydet"):
        repository.set_setting("worker_aktif", "1" if worker_aktif else "0")
        st.success("Ayarlar kaydedildi.")

    st.subheader("Telegram test")
    all_rules = repository.list_filter_rules()
    active_rules = [r for r in all_rules if r.aktif]
    if not active_rules:
        st.warning(
            "Aktif filtre kurali yok. Worker mesaj gondermez. "
            "Filtreler sayfasinda kurallari **Aktif** isaretleyin."
        )
    default_chat, default_topic = _test_target_from_rules(
        all_rules,
        fallback_chat=settings.default_telegram_chat_id or "",
    )
    if "telegram_test_chat" not in st.session_state:
        st.session_state.telegram_test_chat = default_chat
    if "telegram_test_topic" not in st.session_state:
        st.session_state.telegram_test_topic = default_topic
    if st.button("Test alanlarini kurallardan doldur"):
        fill_chat, fill_topic = _test_target_from_rules(
            all_rules,
            fallback_chat=settings.default_telegram_chat_id or "",
        )
        st.session_state.telegram_test_chat = fill_chat
        st.session_state.telegram_test_topic = fill_topic
        st.rerun()
    st.caption(
        "Test, asagidaki alanlara gider. Grup: -1003684878522, topic: 184"
    )
    test_chat = st.text_input(
        "Test chat ID",
        key="telegram_test_chat",
        help="Grup chat ID (-100 ile baslar). Kisisel ID kullanmayin.",
    )
    test_topic = st.text_input(
        "Test topic ID (opsiyonel)",
        key="telegram_test_topic",
        placeholder="184",
        help="Forum konusu: t.me/c/.../184 son sayi",
    )
    if st.button("Test mesaji gonder"):
        if not settings.telegram_bot_token or not test_chat:
            st.error("TELEGRAM_BOT_TOKEN ve chat ID gerekli.")
        elif _group_chat_id(test_chat) and not test_topic.strip():
            st.error(
                "Grup chat ID kullaniyorsunuz; topic ID zorunlu (ornek: 184). "
                "Aksi halde mesaj Genel konuya duser."
            )
        else:
            topic_id = int(test_topic.strip()) if test_topic.strip() else None
            telegram_bot.send_message(
                settings.telegram_bot_token,
                test_chat,
                "<b>KAP Haberleri Cloud</b>\nTest mesaji basarili.",
                message_thread_id=topic_id,
            )
            st.success("Test mesaji gonderildi.")

    st.subheader("Son loglar")
    logs = repository.list_logs(limit=30)
    if logs:
        st.dataframe(logs, use_container_width=True)


def main() -> None:
    from src.config import reload_settings

    reload_settings()
    settings = get_settings()

    st.title("KAP Haberleri Cloud")
    st.caption("Streamlit Cloud + GitHub Actions + Neon PostgreSQL")

    st.sidebar.info("Worker: GitHub Actions (5 dk)")

    page = st.sidebar.radio(
        "Menu",
        ["Dashboard", "Filtreler", "Manuel Kontrol", "Ayarlar"],
    )

    if page == "Dashboard":
        page_dashboard()
    elif page == "Filtreler":
        page_filters(settings)
    elif page == "Manuel Kontrol":
        page_manual_check()
    else:
        page_settings(settings)


if __name__ == "__main__":
    main()
