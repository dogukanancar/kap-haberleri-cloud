from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.brand_fetcher import BrandFetchError, fetch_turkiye125_report
from src.brand_snapshot import compare_report, load_snapshot
from src.brand_schedule import (
    GITHUB_CHECK_INTERVAL as BRAND_GITHUB_CHECK_INTERVAL,
    get_schedule_config as get_brand_schedule_config,
    save_schedule_settings as save_brand_schedule_settings,
)
from src.brand_service import run_brand_worker
from src.cds_fetcher import CdsFetchError, fetch_turkey_cds_5y
from src.cds_schedule import (
    GITHUB_CHECK_INTERVAL,
    get_schedule_config,
    save_schedule_settings,
)
from src.cds_service import run_cds_worker
from src.config import Settings, get_settings
from src.db import test_connection
from src.filters import find_matching_rules
from src.kap_fetcher import KapFetchError, fetch_recent_disclosures
from src import repository
from src.service import process_disclosures
from src import telegram_bot
from src.models import FilterRule
from src.workflow_schedule import WorkflowScheduleError, sync_workflow_schedule

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


def _sync_worker_workflow(
    settings: Settings,
    *,
    workflow_path: str,
    label: str,
    send_times: str,
) -> None:
    sync_workflow_schedule(
        token=settings.github_workflow_token,
        repository=settings.github_repository,
        branch=settings.github_branch,
        workflow_path=workflow_path,
        label=label,
        send_times=send_times,
    )


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
        topic_default = initial.get("telegram_topic_id", "")
        if not topic_default and _group_chat_id(telegram_chat_id):
            topic_default = "184"
        telegram_topic_id = st.text_input(
            "Telegram topic ID (grup icin zorunlu)",
            value=topic_default,
            placeholder="Ornek: 184",
            help="Forum grubunda konu ID. t.me/c/.../184 linkindeki son sayi.",
        )
        submitted = st.form_submit_button(submit_label, type="primary")
        if not submitted:
            return False
        if not kural_adi or not telegram_chat_id:
            st.error("Kural adi ve Telegram chat ID zorunlu.")
            return False
        if _group_chat_id(telegram_chat_id) and not telegram_topic_id.strip():
            st.error("Grup chat ID icin topic ID zorunlu (ornek: 184).")
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
        topic_note = f", topic {telegram_topic_id.strip()}" if telegram_topic_id.strip() else ""
        st.session_state["filter_save_info"] = (
            f"'{kural_adi}' {action}. "
            f"{len(parsed_companies)} sirket, "
            f"{len(parsed_keywords)} anahtar kelime{topic_note}."
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

    st.subheader("CDS bildirimi (ayri worker)")
    st.caption("KAP worker'indan bagimsiz. GitHub Actions CDS Worker ayarlara gore calisir.")

    schedule = get_schedule_config()
    schedule_col1, schedule_col2 = st.columns(2)
    schedule_col1.metric("Calisma saatleri (TR)", schedule.send_times_display or "-")
    schedule_col2.metric("Bugun tamamlanan", schedule.completed_display)
    st.caption(f"Worker kontrol araligi: {GITHUB_CHECK_INTERVAL}")

    cds_send_times = st.text_input(
        "Calisma saatleri (TR)",
        value=repository.get_setting(
            "cds_gonderim_saatleri",
            repository.get_setting("cds_calisma_saati", "18:00"),
        ),
        placeholder="18:00 veya 10:00,18:00",
        help="Europe/Istanbul saati. Her saat icin gunluk bir kez calisir.",
    )

    cds_worker_aktif = st.checkbox(
        "CDS worker aktif",
        value=repository.get_setting("cds_worker_aktif", "1") == "1",
        help="Kapaliysa CDS worker Telegram'a mesaj gondermez.",
    )
    cds_chat = st.text_input(
        "CDS chat ID",
        value=repository.get_setting("cds_telegram_chat_id", settings.default_telegram_chat_id or ""),
        help="Bos birakilirsa TELEGRAM_CHAT_ID kullanilir.",
    )
    cds_topic = st.text_input(
        "CDS topic ID (grup icin zorunlu)",
        value=repository.get_setting("cds_telegram_topic_id", ""),
        placeholder="Ornek: 184",
    )
    last_cds_date = repository.get_setting("son_cds_gonderim_tarihi", "-") or "-"
    last_cds_value = repository.get_setting("son_cds_degeri", "-") or "-"
    st.info(f"Son gonderim: {last_cds_date} | Son deger: {last_cds_value} bp")

    col_cds_a, col_cds_b, col_cds_c = st.columns(3)
    if col_cds_a.button("CDS ayarlarini kaydet", key="save_cds_settings"):
        try:
            _sync_worker_workflow(
                settings,
                workflow_path=".github/workflows/cds_worker.yml",
                label="CDS",
                send_times=cds_send_times.strip(),
            )
            save_schedule_settings(send_times=cds_send_times.strip())
        except ValueError as exc:
            st.error(str(exc))
        except WorkflowScheduleError as exc:
            st.error(f"CDS workflow guncellenemedi: {exc}")
        else:
            repository.set_setting("cds_worker_aktif", "1" if cds_worker_aktif else "0")
            repository.set_setting("cds_telegram_chat_id", cds_chat.strip())
            repository.set_setting("cds_telegram_topic_id", cds_topic.strip())
            st.success("CDS ayarlari kaydedildi.")
            st.rerun()
    if col_cds_b.button("CDS verisini test et", key="test_cds_fetch"):
        try:
            snapshot = fetch_turkey_cds_5y()
            st.success(f"CDS: {snapshot.value_bp:.2f} bp ({snapshot.as_of_date or '-'})")
        except CdsFetchError as exc:
            st.error(str(exc))
    if col_cds_c.button("CDS simdi gonder", key="force_cds_send"):
        if not settings.telegram_bot_token:
            st.error("TELEGRAM_BOT_TOKEN gerekli.")
        elif _group_chat_id(cds_chat.strip()) and not cds_topic.strip():
            st.error("Grup chat ID icin topic ID zorunlu.")
        else:
            try:
                _sync_worker_workflow(
                    settings,
                    workflow_path=".github/workflows/cds_worker.yml",
                    label="CDS",
                    send_times=cds_send_times.strip(),
                )
                save_schedule_settings(send_times=cds_send_times.strip())
            except ValueError as exc:
                st.error(str(exc))
            except WorkflowScheduleError as exc:
                st.error(f"CDS workflow guncellenemedi: {exc}")
            else:
                repository.set_setting("cds_worker_aktif", "1" if cds_worker_aktif else "0")
                repository.set_setting("cds_telegram_chat_id", cds_chat.strip())
                repository.set_setting("cds_telegram_topic_id", cds_topic.strip())
                try:
                    result = run_cds_worker(force=True)
                    if result.get("status") == "sent":
                        st.success(f"CDS gonderildi: {result['value_bp']:.2f} bp")
                    else:
                        st.warning(f"Gonderilmedi: {result.get('reason', 'bilinmiyor')}")
                except CdsFetchError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Hata: {exc}")

    st.subheader("Brandirectory Turkiye 125 (ayri worker)")
    st.caption(
        "KAP ve CDS worker'larindan bagimsiz. Gunluk kontrol yapar ve "
        "Telegram'a uyari mesaji gonderir (degisiklik olsun veya olmasin)."
    )

    brand_schedule = get_brand_schedule_config()
    brand_col1, brand_col2 = st.columns(2)
    brand_col1.metric("Calisma saatleri (TR)", brand_schedule.send_times_display or "-")
    brand_col2.metric("Bugun tamamlanan", brand_schedule.completed_display)
    st.caption(f"Worker kontrol araligi: {BRAND_GITHUB_CHECK_INTERVAL}")

    brand_send_times = st.text_input(
        "Calisma saatleri (TR)",
        value=repository.get_setting(
            "brand_gonderim_saatleri",
            repository.get_setting("brand_calisma_saati", "09:00"),
        ),
        placeholder="09:00 veya 09:00,18:00",
        key="brand_send_times",
        help="Europe/Istanbul saati. Her saat icin gunluk bir kez calisir.",
    )
    brand_year = st.number_input(
        "Rapor yili",
        min_value=2010,
        max_value=2035,
        value=int(repository.get_setting("brand_rapor_yili", "2026") or "2026"),
        key="brand_report_year",
    )

    brand_worker_aktif = st.checkbox(
        "Brand worker aktif",
        value=repository.get_setting("brand_worker_aktif", "1") == "1",
        key="brand_worker_aktif",
    )
    brand_chat = st.text_input(
        "Brand chat ID",
        value=repository.get_setting("brand_telegram_chat_id", settings.default_telegram_chat_id or ""),
        key="brand_chat",
    )
    brand_topic = st.text_input(
        "Brand topic ID (grup icin zorunlu)",
        value=repository.get_setting("brand_telegram_topic_id", ""),
        placeholder="Ornek: 184",
        key="brand_topic",
    )
    last_check = repository.get_setting("son_brand_kontrol_tarihi", "-") or "-"
    last_alert = repository.get_setting("son_brand_gonderim_tarihi", "-") or "-"
    st.info(f"Son kontrol: {last_check} | Son uyari: {last_alert}")

    col_brand_a, col_brand_b, col_brand_c = st.columns(3)
    if col_brand_a.button("Brand ayarlarini kaydet", key="save_brand_settings"):
        try:
            _sync_worker_workflow(
                settings,
                workflow_path=".github/workflows/brand_worker.yml",
                label="Brand",
                send_times=brand_send_times.strip(),
            )
            save_brand_schedule_settings(send_times=brand_send_times.strip())
        except ValueError as exc:
            st.error(str(exc))
        except WorkflowScheduleError as exc:
            st.error(f"Brand workflow guncellenemedi: {exc}")
        else:
            repository.set_setting("brand_worker_aktif", "1" if brand_worker_aktif else "0")
            repository.set_setting("brand_telegram_chat_id", brand_chat.strip())
            repository.set_setting("brand_telegram_topic_id", brand_topic.strip())
            repository.set_setting("brand_rapor_yili", str(int(brand_year)))
            st.success("Brand ayarlari kaydedildi.")
            st.rerun()
    if col_brand_b.button("Kontrol testi", key="test_brand_check"):
        try:
            report = fetch_turkiye125_report(year=int(brand_year))
            check = compare_report(report, load_snapshot())
            st.success(
                "Gunluk uyari gonderilir: "
                f"yeni rapor={'Var' if check.new_report else 'Yok'}, "
                f"siralama degisikligi={'Var' if check.ranking_changed else 'Yok'}"
                + (" (ilk kontrol)" if check.is_first_run else "")
            )
        except BrandFetchError as exc:
            st.error(str(exc))
    if col_brand_c.button("Brand simdi kontrol et", key="force_brand_send"):
        if not settings.telegram_bot_token:
            st.error("TELEGRAM_BOT_TOKEN gerekli.")
        elif _group_chat_id(brand_chat.strip()) and not brand_topic.strip():
            st.error("Grup chat ID icin topic ID zorunlu.")
        else:
            try:
                _sync_worker_workflow(
                    settings,
                    workflow_path=".github/workflows/brand_worker.yml",
                    label="Brand",
                    send_times=brand_send_times.strip(),
                )
                save_brand_schedule_settings(send_times=brand_send_times.strip())
            except ValueError as exc:
                st.error(str(exc))
            except WorkflowScheduleError as exc:
                st.error(f"Brand workflow guncellenemedi: {exc}")
            else:
                repository.set_setting("brand_worker_aktif", "1" if brand_worker_aktif else "0")
                repository.set_setting("brand_telegram_chat_id", brand_chat.strip())
                repository.set_setting("brand_telegram_topic_id", brand_topic.strip())
                repository.set_setting("brand_rapor_yili", str(int(brand_year)))
                try:
                    result = run_brand_worker(force=True)
                    if result.get("status") == "sent":
                        st.success(
                            "Uyari gonderildi: "
                            f"yeni rapor={'Var' if result.get('new_report') else 'Yok'}, "
                            f"siralama={'Var' if result.get('ranking_changed') else 'Yok'}"
                        )
                    else:
                        st.warning(f"Islem tamamlanmadi: {result.get('reason', 'bilinmiyor')}")
                except BrandFetchError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Hata: {exc}")

    st.subheader("Telegram test")
    st.caption("KAP filtre bildirimleri ve baglanti testi.")

    kap_worker_aktif = st.checkbox(
        "KAP worker aktif (GitHub Actions)",
        value=repository.get_setting("worker_aktif", "1") == "1",
        help="Kapaliysa GitHub Actions KAP taramasi calismaz. CDS ve Brand ayarlarindan bagimsiz.",
        key="kap_worker_aktif",
    )
    if st.button("KAP worker ayarini kaydet", key="save_kap_worker"):
        repository.set_setting("worker_aktif", "1" if kap_worker_aktif else "0")
        st.success("KAP worker ayari kaydedildi.")
        st.rerun()

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
        if default_topic:
            st.session_state.telegram_test_topic = default_topic
        elif _group_chat_id(default_chat):
            st.session_state.telegram_test_topic = "184"
        else:
            st.session_state.telegram_test_topic = ""
    if st.button("Test alanlarini kurallardan doldur"):
        fill_chat, fill_topic = _test_target_from_rules(
            all_rules,
            fallback_chat=settings.default_telegram_chat_id or "",
        )
        st.session_state.telegram_test_chat = fill_chat
        st.session_state.telegram_test_topic = fill_topic or (
            "184" if _group_chat_id(fill_chat) else ""
        )
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
        "Test topic ID (grup icin zorunlu)",
        key="telegram_test_topic",
        placeholder="Ornek: 184",
        help="Forum konusu: t.me/c/.../184 son sayi",
    )
    if st.button("Test mesaji gonder"):
        chat_value = str(st.session_state.get("telegram_test_chat", "")).strip()
        topic_value = str(st.session_state.get("telegram_test_topic", "")).strip()
        if not settings.telegram_bot_token or not chat_value:
            st.error("TELEGRAM_BOT_TOKEN ve chat ID gerekli.")
        elif _group_chat_id(chat_value) and not topic_value:
            st.error(
                "Grup chat ID kullaniyorsunuz; topic ID zorunlu (ornek: 184). "
                "Aksi halde mesaj Genel konuya duser."
            )
        else:
            topic_id = int(topic_value) if topic_value else None
            telegram_bot.send_message(
                settings.telegram_bot_token,
                chat_value,
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

    st.sidebar.info("Worker: GitHub Actions (5 dk)\nCDS + Brand: paneldeki saat/plana gore")

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
