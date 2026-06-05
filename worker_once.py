from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import repository
from src.service import run_worker_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker_once")


def main() -> int:
    worker_active = repository.get_setting("worker_aktif", "1") == "1"
    if not worker_active:
        logger.info("Worker pasif (worker_aktif=0). Cikiliyor.")
        return 0

    repository.log_event("INFO", "worker", "GitHub Actions worker basladi.")
    try:
        result = run_worker_cycle(days=1)
        logger.info(
            "Tamamlandi: checked=%s sent=%s skipped=%s",
            result["checked"],
            result["sent"],
            result["skipped"],
        )
        return 0
    except Exception as exc:
        logger.exception("Worker hatasi")
        repository.log_event("ERROR", "worker", "Worker hatasi", detail=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
