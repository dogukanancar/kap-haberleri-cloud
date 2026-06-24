"""Worker sagligini kontrol eder: son calisma, planli saatler, GitHub Actions."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)

from src import repository
from src.cds_schedule import evaluate_send_window as cds_window, get_schedule_config as cds_cfg
from src.brand_schedule import evaluate_send_window as brand_window, get_schedule_config as brand_cfg

IST = ZoneInfo("Europe/Istanbul")
GITHUB_REPO = "dogukanancar/kap-haberleri-cloud"
MAX_RUN_AGE = timedelta(minutes=12)


def _last_log_time(kaynak: str) -> datetime | None:
    for row in repository.list_logs(200):
        if row.get("kaynak") != kaynak:
            continue
        raw = row.get("olusturma_tarihi")
        if raw is None:
            continue
        if isinstance(raw, datetime):
            dt = raw
        else:
            dt = datetime.fromisoformat(str(raw))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    return None


def _github_last_run() -> tuple[datetime | None, str | None]:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/kap_worker.yml/runs?per_page=1"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "kap-health-check"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
    except urllib.error.URLError as exc:
        return None, f"GitHub API okunamadi: {exc}"

    runs = data.get("workflow_runs") or []
    if not runs:
        return None, "GitHub'da KAP Worker run kaydi yok."

    run = runs[0]
    created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")).astimezone(IST)
    conclusion = run.get("conclusion") or run.get("status")
    if conclusion != "success":
        return created, f"Son run basarisiz: {conclusion}"
    return created, None


def main() -> int:
    now = datetime.now(IST)
    print(f"Kontrol zamani (TR): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    problems: list[str] = []

    worker_last = _last_log_time("worker")
    if worker_last is None:
        problems.append("Hic worker logu yok.")
    else:
        age = now - worker_last
        print(f"Son KAP worker logu: {worker_last.strftime('%H:%M:%S')} ({int(age.total_seconds() // 60)} dk once)")
        if age > MAX_RUN_AGE:
            problems.append(
                f"KAP worker {int(age.total_seconds() // 60)} dakikadir calismamis "
                f"(limit {MAX_RUN_AGE.seconds // 60} dk). cron-job.org kontrol edin."
            )

    gh_time, gh_err = _github_last_run()
    if gh_time:
        print(f"Son GitHub KAP Worker: {gh_time.strftime('%H:%M:%S TR')}")
    if gh_err:
        problems.append(gh_err)
    elif gh_time and now - gh_time > MAX_RUN_AGE:
        problems.append(
            f"GitHub Actions {int((now - gh_time).total_seconds() // 60)} dakikadir tetiklenmemis."
        )

    cds = cds_cfg()
    brand = brand_cfg()
    print(f"CDS plan: {cds.send_times_display} | bugun tamamlanan: {cds.completed_display}")
    print(f"Brand plan: {brand.send_times_display} | bugun tamamlanan: {brand.completed_display}")

    cds_ok, cds_reason, cds_slot = cds_window()
    brand_ok, brand_reason, brand_slot = brand_window()
    print(f"CDS simdi gonderir mi: {cds_ok} ({cds_reason}{', slot='+cds_slot if cds_slot else ''})")
    print(f"Brand simdi gonderir mi: {brand_ok} ({brand_reason}{', slot='+brand_slot if brand_slot else ''})")

    for label, active_key in (
        ("KAP", "worker_aktif"),
        ("CDS", "cds_worker_aktif"),
        ("Brand", "brand_worker_aktif"),
    ):
        if repository.get_setting(active_key, "1") != "1":
            problems.append(f"{label} worker pasif ({active_key}=0).")

    if problems:
        print("\nSORUNLAR:")
        for item in problems:
            print(f"  - {item}")
        return 1

    print("\nSaglik kontrolu OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
