"""Supabase uretim ayarlarini bilinen degerlerle doldurur."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import repository
from src.models import FilterRule

KEYWORDS = [
    "Payların Geri Alınmasına İlişkin Bildirim",
    "Sermaye Artırımı",
    "Sermaye Azaltımı",
    "Yeni İş İlişkisi",
    "SPK Onay",
    "Maddi duran varlık alımı",
    "Maddi duran varlık satışı",
    "Konkordato",
    "Temerrüt",
    "İhale sonucu",
]

SETTINGS = {
    "worker_aktif": "1",
    "cds_worker_aktif": "1",
    "brand_worker_aktif": "1",
    "cds_gonderim_saatleri": "09:00, 22:20, 22:30",
    "cds_calisma_saati": "09:00",
    "brand_gonderim_saatleri": "09:00, 22:20, 22:30",
    "brand_calisma_saati": "09:00",
    "brand_rapor_yili": "2026",
    "cds_telegram_chat_id": "-1003684878522",
    "cds_telegram_topic_id": "184",
    "brand_telegram_chat_id": "-1003684878522",
    "brand_telegram_topic_id": "184",
}


def main() -> int:
    for key, value in SETTINGS.items():
        repository.set_setting(key, value)

    existing = repository.list_filter_rules()
    if not existing:
        repository.save_filter_rule(
            rule_id=None,
            kural_adi="işlem gören tipe dönüşüm",
            aktif=True,
            sirket_kodlari=[],
            konu_oid_listesi=[],
            anahtar_kelimeler=KEYWORDS,
            haric_kelimeler=[],
            bildirim_sinifi=None,
            telegram_chat_id="-1003684878522",
            telegram_topic_id="184",
        )
        rules_added = 1
    else:
        rules_added = 0

    print(f"Ayarlar guncellendi: {len(SETTINGS)}")
    print(f"Filtre kurali eklendi: {rules_added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
