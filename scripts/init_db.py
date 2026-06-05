from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from src.config import get_settings
from src.db import get_engine


def main() -> None:
    settings = get_settings()
    engine = get_engine()
    with engine.begin() as conn:
        for schema_name in ("001_schema.sql", "002_telegram_topic_id.sql"):
            sql = (ROOT / "sql" / schema_name).read_text(encoding="utf-8")
            statements = [part.strip() for part in sql.split(";") if part.strip()]
            for statement in statements:
                conn.execute(text(statement))

    print(f"Schema uygulandi: {settings.database_url.split('@')[-1]}")


if __name__ == "__main__":
    main()
