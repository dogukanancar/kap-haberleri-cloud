from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cds_fetcher import CdsFetchError
from src.cds_service import run_cds_worker
from src.config import get_settings
from src import repository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cds_worker_once")


def _validate_env() -> None:
    import os

    missing = [key for key in ("DATABASE_URL", "TELEGRAM_BOT_TOKEN") if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Eksik ortam degiskeni: {', '.join(missing)}")
    get_settings()


def main() -> int:
    try:
        _validate_env()
    except Exception as exc:
        logger.error("Ortam dogrulama hatasi: %s", exc)
        return 1

    repository.log_event("INFO", "cds_worker", "GitHub Actions CDS worker basladi.")
    try:
        result = run_cds_worker()
        logger.info("CDS worker tamamlandi: %s", result)
        return 0
    except CdsFetchError as exc:
        logger.error("CDS verisi alinamadi: %s", exc)
        repository.log_event("ERROR", "cds_worker", "CDS verisi alinamadi.", detail=str(exc))
        return 1
    except Exception as exc:
        logger.exception("CDS worker hatasi")
        try:
            repository.log_event("ERROR", "cds_worker", "CDS worker hatasi", detail=str(exc))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
