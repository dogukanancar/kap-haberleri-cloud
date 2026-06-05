from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text

from src.db import get_session
from src.models import FilterRule


def _loads_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(data, list):
        return [str(item).strip() for item in data if str(item).strip()]
    return []


def _dumps_json_list(values: list[str]) -> str | None:
    cleaned = [value.strip() for value in values if value and value.strip()]
    return json.dumps(cleaned, ensure_ascii=False) if cleaned else None


def log_event(level: str, source: str, message: str, detail: str | None = None) -> None:
    with get_session() as session:
        session.execute(
            text(
                """
                INSERT INTO islem_loglari (seviye, kaynak, mesaj, detay)
                VALUES (:seviye, :kaynak, :mesaj, :detay)
                """
            ),
            {
                "seviye": level,
                "kaynak": source,
                "mesaj": message,
                "detay": detail,
            },
        )


def get_setting(key: str, default: str = "") -> str:
    with get_session() as session:
        row = session.execute(
            text("SELECT deger FROM uygulama_ayarlari WHERE anahtar = :anahtar"),
            {"anahtar": key},
        ).first()
        return row.deger if row else default


def set_setting(key: str, value: str) -> None:
    with get_session() as session:
        session.execute(
            text(
                """
                INSERT INTO uygulama_ayarlari (anahtar, deger, guncelleme_tarihi)
                VALUES (:anahtar, :deger, NOW())
                ON CONFLICT (anahtar) DO UPDATE
                SET deger = EXCLUDED.deger, guncelleme_tarihi = NOW()
                """
            ),
            {"anahtar": key, "deger": value},
        )


def list_filter_rules(active_only: bool = False) -> list[FilterRule]:
    query = """
        SELECT id, kural_adi, aktif, sirket_kodlari, konu_oid_listesi,
               anahtar_kelimeler, haric_kelimeler, bildirim_sinifi, telegram_chat_id
        FROM filtre_kurallari
    """
    if active_only:
        query += " WHERE aktif = TRUE"
    query += " ORDER BY id"

    with get_session() as session:
        rows = session.execute(text(query)).mappings().all()

    return [
        FilterRule(
            id=row["id"],
            kural_adi=row["kural_adi"],
            aktif=bool(row["aktif"]),
            sirket_kodlari=_loads_json_list(row["sirket_kodlari"]),
            konu_oid_listesi=_loads_json_list(row["konu_oid_listesi"]),
            anahtar_kelimeler=_loads_json_list(row["anahtar_kelimeler"]),
            haric_kelimeler=_loads_json_list(row["haric_kelimeler"]),
            bildirim_sinifi=row["bildirim_sinifi"],
            telegram_chat_id=row["telegram_chat_id"],
        )
        for row in rows
    ]


def save_filter_rule(
    *,
    rule_id: int | None,
    kural_adi: str,
    aktif: bool,
    sirket_kodlari: list[str],
    konu_oid_listesi: list[str],
    anahtar_kelimeler: list[str],
    haric_kelimeler: list[str],
    bildirim_sinifi: str | None,
    telegram_chat_id: str,
) -> None:
    params = {
        "kural_adi": kural_adi,
        "aktif": bool(aktif),
        "sirket_kodlari": _dumps_json_list(sirket_kodlari),
        "konu_oid_listesi": _dumps_json_list(konu_oid_listesi),
        "anahtar_kelimeler": _dumps_json_list(anahtar_kelimeler),
        "haric_kelimeler": _dumps_json_list(haric_kelimeler),
        "bildirim_sinifi": bildirim_sinifi or None,
        "telegram_chat_id": telegram_chat_id,
    }

    with get_session() as session:
        if rule_id:
            session.execute(
                text(
                    """
                    UPDATE filtre_kurallari
                    SET kural_adi = :kural_adi,
                        aktif = :aktif,
                        sirket_kodlari = :sirket_kodlari,
                        konu_oid_listesi = :konu_oid_listesi,
                        anahtar_kelimeler = :anahtar_kelimeler,
                        haric_kelimeler = :haric_kelimeler,
                        bildirim_sinifi = :bildirim_sinifi,
                        telegram_chat_id = :telegram_chat_id,
                        guncelleme_tarihi = NOW()
                    WHERE id = :id
                    """
                ),
                {**params, "id": rule_id},
            )
        else:
            session.execute(
                text(
                    """
                    INSERT INTO filtre_kurallari (
                        kural_adi, aktif, sirket_kodlari, konu_oid_listesi,
                        anahtar_kelimeler, haric_kelimeler, bildirim_sinifi, telegram_chat_id
                    )
                    VALUES (
                        :kural_adi, :aktif, :sirket_kodlari, :konu_oid_listesi,
                        :anahtar_kelimeler, :haric_kelimeler, :bildirim_sinifi, :telegram_chat_id
                    )
                    """
                ),
                params,
            )


def delete_filter_rule(rule_id: int) -> None:
    with get_session() as session:
        session.execute(
            text("DELETE FROM filtre_kurallari WHERE id = :id"),
            {"id": rule_id},
        )


def is_disclosure_sent(disclosure_index: int, chat_id: str) -> bool:
    with get_session() as session:
        row = session.execute(
            text(
                """
                SELECT 1
                FROM gonderilen_bildirimler
                WHERE disclosure_index = :disclosure_index
                  AND telegram_chat_id = :chat_id
                """
            ),
            {"disclosure_index": disclosure_index, "chat_id": chat_id},
        ).first()
    return row is not None


def mark_disclosure_sent(
    *,
    disclosure_index: int,
    sirket_kodu: str | None,
    sirket_adi: str | None,
    konu: str | None,
    baslik: str | None,
    yayin_tarihi: datetime,
    kap_url: str,
    telegram_chat_id: str,
    filtre_kural_id: int | None,
) -> None:
    with get_session() as session:
        session.execute(
            text(
                """
                INSERT INTO gonderilen_bildirimler (
                    disclosure_index, sirket_kodu, sirket_adi, konu, baslik,
                    yayin_tarihi, kap_url, telegram_chat_id, filtre_kural_id
                )
                VALUES (
                    :disclosure_index, :sirket_kodu, :sirket_adi, :konu, :baslik,
                    :yayin_tarihi, :kap_url, :telegram_chat_id, :filtre_kural_id
                )
                """
            ),
            {
                "disclosure_index": disclosure_index,
                "sirket_kodu": sirket_kodu,
                "sirket_adi": sirket_adi,
                "konu": konu,
                "baslik": baslik,
                "yayin_tarihi": yayin_tarihi,
                "kap_url": kap_url,
                "telegram_chat_id": telegram_chat_id,
                "filtre_kural_id": filtre_kural_id,
            },
        )


def list_sent_disclosures(limit: int = 100) -> list[dict[str, Any]]:
    with get_session() as session:
        rows = session.execute(
            text(
                """
                SELECT disclosure_index, sirket_kodu, sirket_adi, konu, baslik,
                       yayin_tarihi, kap_url, telegram_chat_id, gonderim_tarihi
                FROM gonderilen_bildirimler
                ORDER BY gonderim_tarihi DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return [dict(row) for row in rows]


def list_logs(limit: int = 100) -> list[dict[str, Any]]:
    with get_session() as session:
        rows = session.execute(
            text(
                """
                SELECT seviye, kaynak, mesaj, detay, olusturma_tarihi
                FROM islem_loglari
                ORDER BY olusturma_tarihi DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return [dict(row) for row in rows]


def count_sent_today() -> int:
    with get_session() as session:
        row = session.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM gonderilen_bildirimler
                WHERE gonderim_tarihi::date = (NOW() AT TIME ZONE 'utc')::date
                """
            )
        ).one()
    return int(row.cnt)


def get_table_counts() -> dict[str, int]:
    queries = {
        "gonderilen_bildirimler": "SELECT COUNT(*) AS cnt FROM gonderilen_bildirimler",
        "filtre_kurallari": "SELECT COUNT(*) AS cnt FROM filtre_kurallari",
        "islem_loglari": "SELECT COUNT(*) AS cnt FROM islem_loglari",
        "uygulama_ayarlari": "SELECT COUNT(*) AS cnt FROM uygulama_ayarlari",
    }
    counts: dict[str, int] = {}
    with get_session() as session:
        for table, query in queries.items():
            row = session.execute(text(query)).one()
            counts[table] = int(row.cnt)
    return counts


def clear_sent_disclosures(*, write_log: bool = True) -> int:
    with get_session() as session:
        row = session.execute(text("SELECT COUNT(*) AS cnt FROM gonderilen_bildirimler")).one()
        deleted = int(row.cnt)
        session.execute(text("DELETE FROM gonderilen_bildirimler"))
    if write_log and deleted:
        log_event("INFO", "db", "Gonderilen bildirimler temizlendi.", detail=str(deleted))
    return deleted


def clear_logs() -> int:
    with get_session() as session:
        row = session.execute(text("SELECT COUNT(*) AS cnt FROM islem_loglari")).one()
        deleted = int(row.cnt)
        session.execute(text("DELETE FROM islem_loglari"))
    return deleted


def clear_filter_rules(*, write_log: bool = True) -> int:
    with get_session() as session:
        row = session.execute(text("SELECT COUNT(*) AS cnt FROM filtre_kurallari")).one()
        deleted = int(row.cnt)
        session.execute(text("DELETE FROM gonderilen_bildirimler"))
        session.execute(text("DELETE FROM filtre_kurallari"))
    if write_log and deleted:
        log_event("WARNING", "db", "Filtre kurallari silindi.", detail=str(deleted))
    return deleted


def clear_all_data() -> dict[str, int]:
    with get_session() as session:
        sent_row = session.execute(text("SELECT COUNT(*) AS cnt FROM gonderilen_bildirimler")).one()
        log_row = session.execute(text("SELECT COUNT(*) AS cnt FROM islem_loglari")).one()
        session.execute(text("DELETE FROM gonderilen_bildirimler"))
        session.execute(text("DELETE FROM islem_loglari"))

    return {
        "gonderilen": int(sent_row.cnt),
        "loglar": int(log_row.cnt),
    }


def purge_old_logs(days: int = 90) -> int:
    with get_session() as session:
        row = session.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM islem_loglari
                WHERE olusturma_tarihi < NOW() - MAKE_INTERVAL(days => :days)
                """
            ),
            {"days": days},
        ).one()
        deleted = int(row.cnt)
        session.execute(
            text(
                """
                DELETE FROM islem_loglari
                WHERE olusturma_tarihi < NOW() - MAKE_INTERVAL(days => :days)
                """
            ),
            {"days": days},
        )
    if deleted:
        log_event("INFO", "db", f"{days} gunden eski loglar silindi.", detail=str(deleted))
    return deleted


def run_db_maintenance() -> list[str]:
    statements = [
        "ANALYZE gonderilen_bildirimler",
        "ANALYZE filtre_kurallari",
        "ANALYZE islem_loglari",
        "ANALYZE uygulama_ayarlari",
    ]
    completed: list[str] = []
    with get_session() as session:
        for statement in statements:
            session.execute(text(statement))
            completed.append(statement)
    log_event("INFO", "db", "Veritabani bakimi tamamlandi.", detail="; ".join(completed))
    return completed
