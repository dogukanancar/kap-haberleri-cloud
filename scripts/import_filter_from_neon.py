"""Neon'daki filtre kurallarini Supabase'e aktarir (sirket kodlari dahil)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NEON_URL = (
    "postgresql://neondb_owner:npg_kv4gEQjF7XlD@"
    "ep-shiny-rice-a2tpndqc.eu-central-1.aws.neon.tech/neondb?sslmode=require"
)


def _engine(url: str):
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10}, future=True)


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    cloud_url = os.getenv("DATABASE_URL", "").strip()
    if not cloud_url:
        print("DATABASE_URL .env icinde yok.", file=sys.stderr)
        return 1

    neon = _engine(NEON_URL)
    cloud = _engine(cloud_url)

    with neon.connect() as src:
        rules = src.execute(
            text(
                """
                SELECT id, kural_adi, aktif, sirket_kodlari, konu_oid_listesi,
                       anahtar_kelimeler, haric_kelimeler, bildirim_sinifi,
                       telegram_chat_id, telegram_topic_id
                FROM filtre_kurallari
                ORDER BY id
                """
            )
        ).mappings().all()

    if not rules:
        print("Neon'da filtre kurali yok.", file=sys.stderr)
        return 1

    with cloud.begin() as dst:
        dst.execute(
            text(
                "UPDATE gonderilen_bildirimler SET filtre_kural_id = NULL "
                "WHERE filtre_kural_id IS NOT NULL"
            )
        )
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

    for rule in rules:
        codes = json.loads(rule["sirket_kodlari"] or "[]")
        print(f"{rule['kural_adi']}: {len(codes)} sirket, aktif={rule['aktif']}")

    print(f"Toplam {len(rules)} kural Supabase'e aktarildi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
