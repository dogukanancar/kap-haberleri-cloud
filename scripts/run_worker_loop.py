"""GitHub Actions icinde KAP+CDS+Brand turunu 10 dakikada bir tekrarlar.

Public repo'da `*/10` cron 4 saate yayiliyor. Bu dongu job'u ayakta tutar.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTERVAL_SEC = 10 * 60
DURATION_SEC = int(5.5 * 3600)
SCRIPTS = ("worker_once.py", "cds_worker_once.py", "brand_worker_once.py")


def main() -> int:
    deadline = time.monotonic() + DURATION_SEC
    round_no = 0
    while time.monotonic() < deadline:
        round_no += 1
        print(f"=== tur {round_no} ===", flush=True)
        for name in SCRIPTS:
            completed = subprocess.run(
                [sys.executable, str(ROOT / name)],
                cwd=ROOT,
            )
            print(f"{name} exit={completed.returncode}", flush=True)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        sleep_for = min(INTERVAL_SEC, remaining)
        print(f"{int(sleep_for)} sn bekleniyor...", flush=True)
        time.sleep(sleep_for)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
