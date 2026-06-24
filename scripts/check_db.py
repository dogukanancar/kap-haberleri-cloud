from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import test_connection
from src import repository


def main() -> int:
    try:
        info = test_connection()
        counts = repository.get_table_counts()
    except Exception as exc:
        print(f"BAGLANTI HATASI: {exc}")
        print()
        print("Kontrol listesi:")
        print("- .env icinde DATABASE_URL Supabase URI mi?")
        print("- Sifrede @ # gibi karakter varsa URL-encode edin")
        print("- init_db icin Direct connection, calisma icin Session pooler deneyin")
        return 1

    print(f"Baglanti OK: {info}")
    for table, count in counts.items():
        print(f"  {table}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
