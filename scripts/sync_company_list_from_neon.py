"""Neon'daki sirket kodlarini Supabase filtre kuralina yazar (mevcut kural korunur)."""
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


def _loads(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(x).strip().upper() for x in data if str(x).strip()]


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    cloud_url = os.getenv("DATABASE_URL", "").strip()
    if not cloud_url:
        print("DATABASE_URL .env icinde yok.", file=sys.stderr)
        return 1

    try:
        with create_engine(
            NEON_URL, connect_args={"connect_timeout": 10}, future=True
        ).connect() as neon:
            neon_rules = neon.execute(
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
    except Exception as exc:
        print(f"Neon okunamadi: {exc}", file=sys.stderr)
        return 1

    if not neon_rules:
        print("Neon'da filtre kurali yok.", file=sys.stderr)
        return 1

    source = max(neon_rules, key=lambda r: len(_loads(r["sirket_kodlari"])))
    codes = _loads(source["sirket_kodlari"])
    if not codes:
        print("Neon'da sirket kodu bulunamadi.", file=sys.stderr)
        return 1

    with create_engine(cloud_url, pool_pre_ping=True, future=True).begin() as cloud:
        cloud_rules = cloud.execute(
            text("SELECT id, kural_adi FROM filtre_kurallari ORDER BY id")
        ).mappings().all()
        if not cloud_rules:
            cloud.execute(
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
                {
                    **dict(source),
                    "sirket_kodlari": json.dumps(codes, ensure_ascii=False),
                    "konu_oid_listesi": source["konu_oid_listesi"] or "[]",
                    "anahtar_kelimeler": source["anahtar_kelimeler"] or "[]",
                    "haric_kelimeler": source["haric_kelimeler"] or "[]",
                },
            )
            print(f"Yeni kural eklendi: {len(codes)} sirket")
            return 0

        target_id = cloud_rules[0]["id"]
        cloud.execute(
            text(
                """
                UPDATE filtre_kurallari
                SET sirket_kodlari = :sirket_kodlari,
                    konu_oid_listesi = :konu_oid_listesi,
                    anahtar_kelimeler = :anahtar_kelimeler,
                    haric_kelimeler = :haric_kelimeler,
                    bildirim_sinifi = :bildirim_sinifi,
                    telegram_chat_id = :telegram_chat_id,
                    telegram_topic_id = :telegram_topic_id,
                    aktif = :aktif,
                    guncelleme_tarihi = NOW()
                WHERE id = :id
                """
            ),
            {
                "id": target_id,
                "sirket_kodlari": json.dumps(codes, ensure_ascii=False),
                "konu_oid_listesi": source["konu_oid_listesi"] or "[]",
                "anahtar_kelimeler": source["anahtar_kelimeler"] or "[]",
                "haric_kelimeler": source["haric_kelimeler"] or "[]",
                "bildirim_sinifi": source["bildirim_sinifi"],
                "telegram_chat_id": source["telegram_chat_id"],
                "telegram_topic_id": source["telegram_topic_id"],
                "aktif": source["aktif"],
            },
        )

    print(
        f"Supabase kural #{target_id} guncellendi: {len(codes)} sirket "
        f"(kaynak Neon: {source['kural_adi']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
