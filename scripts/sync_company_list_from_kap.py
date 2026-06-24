"""KAP BIST sirket kodlarini filtre kuralina yazar."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import repository
from src.kap_fetcher import fetch_bist_stock_codes
def main() -> int:
    codes = fetch_bist_stock_codes()
    if not codes:
        print("KAP'dan sirket kodu alinamadi.", file=sys.stderr)
        return 1

    rules = repository.list_filter_rules()
    if not rules:
        repository.save_filter_rule(
            rule_id=None,
            kural_adi="işlem gören tipe dönüşüm",
            aktif=True,
            sirket_kodlari=codes,
            konu_oid_listesi=[],
            anahtar_kelimeler=[],
            haric_kelimeler=[],
            bildirim_sinifi=None,
            telegram_chat_id="-1003684878522",
            telegram_topic_id="184",
        )
        print(f"Yeni kural eklendi: {len(codes)} sirket")
        return 0

    rule = rules[0]
    repository.save_filter_rule(
        rule_id=rule.id,
        kural_adi=rule.kural_adi,
        aktif=rule.aktif,
        sirket_kodlari=codes,
        konu_oid_listesi=rule.konu_oid_listesi,
        anahtar_kelimeler=rule.anahtar_kelimeler,
        haric_kelimeler=rule.haric_kelimeler,
        bildirim_sinifi=rule.bildirim_sinifi,
        telegram_chat_id=rule.telegram_chat_id,
        telegram_topic_id=rule.telegram_topic_id,
    )
    print(f"Kural #{rule.id} guncellendi: {len(codes)} sirket")
    print(f"Ornek: {', '.join(codes[:8])} ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
