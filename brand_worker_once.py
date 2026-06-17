from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.brand_fetcher import BrandFetchError
from src.brand_service import run_brand_worker
from src.config import get_settings
from src import repository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("brand_worker_once")


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

    repository.log_event("INFO", "brand_worker", "GitHub Actions Brand worker basladi.")
    try:
        result = run_brand_worker()
        logger.info("Brand worker tamamlandi: %s", result)
        return 0
    except BrandFetchError as exc:
        logger.error("Brand verisi alinamadi: %s", exc)
        repository.log_event("ERROR", "brand_worker", "Brand verisi alinamadi.", detail=str(exc))
        return 1
    except Exception as exc:
        logger.exception("Brand worker hatasi")
        try:
            repository.log_event("ERROR", "brand_worker", "Brand worker hatasi", detail=str(exc))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
