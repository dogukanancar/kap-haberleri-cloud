"""PostgreSQL (Supabase) veritabani bakim — index, istatistik, durum raporlari."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from src.db import get_engine, get_session

INDEX_HEALTH_SQL = """
    SELECT
        ui.relname AS tablo,
        ui.indexrelname AS idx,
        ROUND((pg_relation_size(ui.indexrelid) / 1024.0 / 1024.0)::numeric, 2) AS boyut_mb,
        ui.idx_scan AS tarama_sayisi,
        COALESCE(pst.n_dead_tup, 0)::bigint AS olu_satir,
        CASE
            WHEN ui.idx_scan = 0 AND pg_relation_size(ui.indexrelid) > 1048576 THEN 'kullanilmiyor'
            WHEN COALESCE(pst.n_dead_tup, 0) > GREATEST(COALESCE(pst.n_live_tup, 0) * 0.2, 1000)
                THEN 'vacuum'
            WHEN COALESCE(pst.n_dead_tup, 0) > 100 THEN 'analyze'
            ELSE 'iyi'
        END AS durum
    FROM pg_stat_user_indexes ui
    LEFT JOIN pg_stat_user_tables pst ON ui.relid = pst.relid
    WHERE ui.schemaname = 'public'
    ORDER BY pg_relation_size(ui.indexrelid) DESC
"""

TABLE_SIZE_SQL = """
    SELECT
        relname AS tablo,
        COALESCE(n_live_tup, 0)::bigint AS satir,
        ROUND((pg_total_relation_size(relid) / 1024.0 / 1024.0)::numeric, 2) AS boyut_mb
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(relid) DESC
"""

DB_SIZE_SQL = """
    SELECT
        current_database() AS veritabani,
        ROUND((pg_database_size(current_database()) / 1024.0 / 1024.0)::numeric, 2) AS boyut_mb
"""

TABLE_DETAIL_SQL = """
    SELECT
        relname AS tablo,
        ROUND((pg_relation_size(relid) / 1024.0 / 1024.0)::numeric, 2) AS veri_mb,
        ROUND((pg_indexes_size(relid) / 1024.0 / 1024.0)::numeric, 2) AS index_mb,
        ROUND((pg_total_relation_size(relid) / 1024.0 / 1024.0)::numeric, 2) AS toplam_mb
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(relid) DESC
"""

INDEX_LIST_SQL = """
    SELECT
        t.relname AS tablo,
        i.relname AS idx,
        am.amname AS tip,
        pg_get_indexdef(i.oid) AS tanim
    FROM pg_class t
    JOIN pg_index ix ON t.oid = ix.indrelid
    JOIN pg_class i ON i.oid = ix.indexrelid
    JOIN pg_am am ON i.relam = am.oid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'public' AND t.relkind = 'r'
    ORDER BY t.relname, i.relname
"""

PERFORMANCE_INDEX_SQL = [
    """
    CREATE INDEX IF NOT EXISTS ix_gonderilen_gonderim_tarihi
        ON gonderilen_bildirimler (gonderim_tarihi DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_log_tarih
        ON islem_loglari (olusturma_tarihi DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_filtre_aktif
        ON filtre_kurallari (aktif) WHERE aktif = TRUE
    """,
]

MAINTENANCE_TABLES = (
    "gonderilen_bildirimler",
    "filtre_kurallari",
    "islem_loglari",
    "uygulama_ayarlari",
)


def _fetch_all(sql: str) -> list[dict[str, Any]]:
    with get_session() as session:
        rows = session.execute(text(sql)).mappings().all()
    return [dict(row) for row in rows]


def _autocommit_execute(statements: list[str]) -> tuple[list[str], list[str]]:
    conn = get_engine().raw_connection()
    conn.set_isolation_level(0)
    cur = conn.cursor()
    detay: list[str] = []
    hatalar: list[str] = []
    try:
        for statement in statements:
            try:
                cur.execute(statement)
                detay.append(statement)
            except Exception as exc:
                hatalar.append(f"{statement}: {exc}")
    finally:
        cur.close()
        conn.close()
    return detay, hatalar


def ensure_performance_indexes() -> list[str]:
    before = {row["idx"] for row in _fetch_all(INDEX_LIST_SQL)}
    with get_session() as session:
        for statement in PERFORMANCE_INDEX_SQL:
            session.execute(text(statement))
    after = {row["idx"] for row in _fetch_all(INDEX_LIST_SQL)}
    return sorted(after - before)


def get_fragmentation_report() -> list[dict[str, Any]]:
    return _fetch_all(INDEX_HEALTH_SQL)


def get_table_sizes() -> list[dict[str, Any]]:
    return _fetch_all(TABLE_SIZE_SQL)


def get_db_file_sizes() -> list[dict[str, Any]]:
    summary = _fetch_all(DB_SIZE_SQL)
    details = _fetch_all(TABLE_DETAIL_SQL)
    rows: list[dict[str, Any]] = []
    for item in summary:
        rows.append(
            {
                "dosya": item["veritabani"],
                "tip": "DATABASE",
                "boyut_mb": item["boyut_mb"],
                "kullanilan_mb": item["boyut_mb"],
            }
        )
    for item in details:
        rows.append(
            {
                "dosya": item["tablo"],
                "tip": "TABLE",
                "boyut_mb": item["toplam_mb"],
                "kullanilan_mb": item["veri_mb"],
            }
        )
    return rows


def list_indexes() -> list[dict[str, Any]]:
    rows = _fetch_all(INDEX_LIST_SQL)
    return [
        {
            "tablo": row["tablo"],
            "idx": row["idx"],
            "tip": row["tip"],
            "kolonlar": row["tanim"],
        }
        for row in rows
    ]


def run_index_maintenance(
    *,
    min_frag: float = 5.0,
    rebuild_threshold: float = 30.0,
    fullscan_stats: bool = True,
) -> dict[str, Any]:
    report = get_fragmentation_report()
    statements: list[str] = []
    processed_tables: set[str] = set()

    for row in report:
        durum = row.get("durum")
        tablo = row["tablo"]
        idx = row["idx"]
        olu_satir = int(row.get("olu_satir") or 0)

        if durum == "vacuum" and tablo not in processed_tables:
            statements.append(f"VACUUM ANALYZE {tablo}")
            processed_tables.add(tablo)
        elif durum == "analyze" and tablo not in processed_tables:
            statements.append(f"ANALYZE {tablo}")
            processed_tables.add(tablo)

        if durum == "kullanilmiyor" and rebuild_threshold <= 25:
            statements.append(f"REINDEX INDEX CONCURRENTLY {idx}")

        if olu_satir >= int(min_frag * 200) and tablo not in processed_tables:
            statements.append(f"VACUUM ANALYZE {tablo}")
            processed_tables.add(tablo)

    if fullscan_stats:
        for tablo in MAINTENANCE_TABLES:
            if tablo not in processed_tables:
                statements.append(f"ANALYZE {tablo}")

    seen: set[str] = set()
    unique: list[str] = []
    for statement in statements:
        if statement not in seen:
            seen.add(statement)
            unique.append(statement)

    detay, hatalar = _autocommit_execute(unique)
    return {"islem": len(detay), "hatalar": hatalar, "detay": detay}


def shrink_database() -> list[str]:
    statements = [f"VACUUM ANALYZE {tablo}" for tablo in MAINTENANCE_TABLES]
    detay, hatalar = _autocommit_execute(statements)
    mesajlar = [s.replace("VACUUM ANALYZE ", "") for s in detay]
    mesajlar.extend(hatalar)
    return mesajlar
