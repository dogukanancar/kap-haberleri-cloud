"""PostgreSQL (Supabase) semasini sifirdan kurar veya eksik parcalari tamamlar (idempotent)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from src.config import get_settings
from src.db import get_engine, get_session, reset_engine
from src import repository

SCHEMA_FILE = "001_schema.sql"


def _split_statements(sql: str) -> list[str]:
    statements: list[str] = []
    for part in sql.split(";"):
        stripped = part.strip()
        if stripped:
            statements.append(stripped)
    return statements


def _verify_schema() -> None:
    reset_engine()
    counts = repository.get_table_counts()
    with get_session() as session:
        index_count = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname IN (
                      'ix_gonderilen_gonderim_tarihi',
                      'ix_log_tarih',
                      'ix_filtre_aktif'
                  )
                """
            )
        ).scalar_one()
    print("Tablo kayit sayilari:")
    for table, count in counts.items():
        print(f"  {table}: {count}")
    print(f"Performans indexleri: {index_count}/3")


def main() -> int:
    settings = get_settings()
    schema_path = ROOT / "sql" / SCHEMA_FILE
    if not schema_path.is_file():
        print(f"HATA: {schema_path} bulunamadi.")
        return 1

    engine = get_engine()
    sql = schema_path.read_text(encoding="utf-8")
    statements = _split_statements(sql)

    print(f"Uygulaniyor: {SCHEMA_FILE} ({len(statements)} ifade)")
    try:
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
    except Exception as exc:
        print(f"HATA: {exc}")
        return 1

    host = settings.database_url.split("@")[-1]
    print(f"\nSchema tamamlandi: {host}")
    try:
        _verify_schema()
    except Exception as exc:
        print(f"Dogrulama uyarisi: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
