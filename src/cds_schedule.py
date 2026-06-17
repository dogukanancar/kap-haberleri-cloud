from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from src import repository

ISTANBUL = ZoneInfo("Europe/Istanbul")
TIME_PATTERN = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
GITHUB_CHECK_INTERVAL = "Her 5 dakika (cron-job.org + GitHub Actions)"
SEND_WINDOW = timedelta(minutes=15)


@dataclass(frozen=True)
class CdsScheduleConfig:
    send_times: tuple[str, ...]
    completed_today: tuple[str, ...]
    today: str

    @property
    def send_times_display(self) -> str:
        return ", ".join(self.send_times)

    @property
    def completed_display(self) -> str:
        return ", ".join(self.completed_today) if self.completed_today else "-"


def _today_istanbul() -> str:
    return datetime.now(ISTANBUL).date().isoformat()


def _normalize_time(value: str) -> str:
    match = TIME_PATTERN.match(value.strip())
    if not match:
        raise ValueError(f"Gecersiz saat formati: {value!r} (ornek: 18:00)")
    hour = int(match.group(1))
    minute = int(match.group(2))
    return f"{hour:02d}:{minute:02d}"


def parse_send_times(raw: str) -> list[str]:
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        raise ValueError("En az bir gonderim saati gerekli.")
    normalized = [_normalize_time(part) for part in parts]
    return sorted(set(normalized))


def get_schedule_config() -> CdsScheduleConfig:
    times_raw = repository.get_setting("cds_gonderim_saatleri", "").strip()
    if not times_raw:
        times_raw = repository.get_setting("cds_calisma_saati", "18:00")
    send_times = parse_send_times(times_raw)

    today = _today_istanbul()
    stored_date = repository.get_setting("cds_bugun_gonderim_tarihi", "")
    completed_today: list[str] = []
    if stored_date == today:
        try:
            loaded = json.loads(repository.get_setting("cds_bugun_gonderilen_saatler", "[]") or "[]")
            if isinstance(loaded, list):
                completed_today = [
                    str(item) for item in loaded if str(item) in send_times
                ]
        except json.JSONDecodeError:
            completed_today = []

    return CdsScheduleConfig(
        send_times=tuple(send_times),
        completed_today=tuple(completed_today),
        today=today,
    )


def save_schedule_settings(*, send_times: str) -> CdsScheduleConfig:
    selected_times = parse_send_times(send_times)
    repository.set_setting("cds_gonderim_saatleri", ", ".join(selected_times))
    repository.set_setting("cds_calisma_saati", selected_times[0])
    return get_schedule_config()


def _time_from_slot(slot: str) -> time:
    hour, minute = slot.split(":")
    return time(hour=int(hour), minute=int(minute))


def find_due_slot(config: CdsScheduleConfig, now: datetime | None = None) -> str | None:
    current = now or datetime.now(ISTANBUL)
    if current.tzinfo is None:
        current = current.replace(tzinfo=ISTANBUL)
    else:
        current = current.astimezone(ISTANBUL)

    due_slot: str | None = None
    for slot in config.send_times:
        if slot in config.completed_today:
            continue
        slot_time = _time_from_slot(slot)
        slot_at = current.replace(
            hour=slot_time.hour,
            minute=slot_time.minute,
            second=0,
            microsecond=0,
        )
        if timedelta(0) <= current - slot_at < SEND_WINDOW:
            due_slot = slot
    return due_slot


def evaluate_send_window(*, force: bool = False) -> tuple[bool, str, str | None]:
    if force:
        return True, "forced", None

    config = get_schedule_config()
    due_slot = find_due_slot(config)
    if due_slot is None:
        return False, "not_scheduled_time", None

    return True, "scheduled", due_slot


def record_scheduled_send(slot: str) -> None:
    config = get_schedule_config()
    today = _today_istanbul()
    completed_today = list(config.completed_today)
    if slot not in completed_today:
        completed_today.append(slot)

    repository.set_setting("cds_bugun_gonderim_tarihi", today)
    repository.set_setting(
        "cds_bugun_gonderilen_saatler",
        json.dumps(completed_today, ensure_ascii=False),
    )
    repository.set_setting("son_cds_gonderim_tarihi", today)
