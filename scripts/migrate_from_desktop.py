"""Desktop SQL Server -> Supabase ayar ve filtre aktarimi."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = Path(r"C:\Kap Haberleri")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text

SETTING_PREFIXES = (
    "worker_",
    "cds_",
    "brand_",
    "son_cds_",
    "son_brand_",
)


def _desktop_engine():
    import os
    from dotenv import load_dotenv

    load_dotenv(DESKTOP / ".env", override=True)
    driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    server = os.getenv("DB_SERVER", "")
    database = os.getenv("DB_NAME", "KapHaberleri")
    if not server:
        raise RuntimeError("Desktop DB_SERVER tanimli degil.")
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
        "Trusted_Connection=yes",
        "TrustServerCertificate=yes",
    ]
    conn_str = quote_plus(";".join(parts))
    return create_engine(f"mssql+pyodbc:///?odbc_connect={conn_str}", future=True)


def _cloud_engine():
    import os
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("Cloud DATABASE_URL tanimli degil.")
    return create_engine(database_url, pool_pre_ping=True, future=True)


def main() -> int:
    desktop = _desktop_engine()
    cloud = _cloud_engine()

    with desktop.connect() as src, cloud.begin() as dst:
        rules = src.execute(
            text(
                """
                SELECT kural_adi, aktif, sirket_kodlari, konu_oid_listesi,
                       anahtar_kelimeler, haric_kelimeler, bildirim_sinifi,
                       telegram_chat_id, telegram_topic_id
                FROM dbo.filtre_kurallari
                ORDER BY id
                """
            )
        ).mappings().all()

        dst.execute(text("DELETE FROM filtre_kurallari"))
        for rule in rules:
            dst.execute(
                text(
                    """
                    INSERT INTO filtre_kurallari (
                        kural_adi, aktif, sirket_kodlari, konu_oid_listesi,
                        anahtar_kelimeler, haric_kelimeler, bildirim_sinifi,
                        telegram_chat_id, telegram_topic_id
                    )
                    VALUES (
                        :kural_adi, :aktif, :sirket_kodlari, :konu_oid_listesi,
                        :anahtar_kelimeler, :haric_kelimeler, :bildirim_sinifi,
                        :telegram_chat_id, :telegram_topic_id
                    )
                    """
                ),
                dict(rule),
            )

        settings = src.execute(
            text(
                """
                SELECT anahtar, deger FROM dbo.uygulama_ayarlari
                WHERE anahtar LIKE 'worker_%'
                   OR anahtar LIKE 'cds_%'
                   OR anahtar LIKE 'brand_%'
                   OR anahtar LIKE 'son_cds_%'
                   OR anahtar LIKE 'son_brand_%'
                ORDER BY anahtar
                """
            )
        ).mappings().all()

        for row in settings:
            dst.execute(
                text(
                    """
                    INSERT INTO uygulama_ayarlari (anahtar, deger, guncelleme_tarihi)
                    VALUES (:anahtar, :deger, NOW())
                    ON CONFLICT (anahtar) DO UPDATE
                    SET deger = EXCLUDED.deger, guncelleme_tarihi = NOW()
                    """
                ),
                {"anahtar": row["anahtar"], "deger": row["deger"] or ""},
            )

    print(f"Aktarildi: {len(rules)} filtre kurali, {len(settings)} ayar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
