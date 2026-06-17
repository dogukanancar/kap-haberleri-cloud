from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from src import repository

ISTANBUL = ZoneInfo("Europe/Istanbul")
TIME_PATTERN = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
GITHUB_CHECK_INTERVAL = "Saat basi (GitHub Actions)"


@dataclass(frozen=True)
class CdsScheduleConfig:
    send_times: tuple[str, ...]
    daily_count: int
    sent_today: tuple[str, ...]
    today: str

    @property
    def remaining_today(self) -> int:
        return max(0, self.daily_count - len(self.sent_today))

    @property
    def send_times_display(self) -> str:
        return ", ".join(self.send_times)


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
    daily_count = max(1, int(repository.get_setting("cds_gunluk_gonderim_sayisi", "1") or "1"))
    times_raw = repository.get_setting("cds_gonderim_saatleri", "").strip()
    if not times_raw:
        times_raw = repository.get_setting("cds_calisma_saati", "18:00")
    send_times = parse_send_times(times_raw)[:daily_count]

    today = _today_istanbul()
    stored_date = repository.get_setting("cds_bugun_gonderim_tarihi", "")
    sent_today: list[str] = []
    if stored_date == today:
        try:
            loaded = json.loads(repository.get_setting("cds_bugun_gonderilen_saatler", "[]") or "[]")
            if isinstance(loaded, list):
                sent_today = [str(item) for item in loaded]
        except json.JSONDecodeError:
            sent_today = []

    return CdsScheduleConfig(
        send_times=tuple(send_times),
        daily_count=daily_count,
        sent_today=tuple(sent_today),
        today=today,
    )


def save_schedule_settings(*, send_times: str, daily_count: int) -> CdsScheduleConfig:
    if daily_count < 1 or daily_count > 10:
        raise ValueError("Gunluk gonderim sayisi 1-10 arasinda olmali.")
    parsed_times = parse_send_times(send_times)
    if len(parsed_times) < daily_count:
        raise ValueError(
            f"Gunluk gonderim sayisi {daily_count} ama yalnizca {len(parsed_times)} saat girildi."
        )
    selected_times = parsed_times[:daily_count]
    repository.set_setting("cds_gunluk_gonderim_sayisi", str(daily_count))
    repository.set_setting("cds_gonderim_saatleri", ", ".join(selected_times))
    repository.set_setting("cds_calisma_saati", selected_times[0])
    return get_schedule_config()


def _time_from_slot(slot: str) -> time:
    hour, minute = slot.split(":")
    return time(hour=int(hour), minute=int(minute))


def find_due_slot(config: CdsScheduleConfig, now: datetime | None = None) -> str | None:
    if len(config.sent_today) >= config.daily_count:
        return None
    current = now or datetime.now(ISTANBUL)
    if current.tzinfo is None:
        current = current.replace(tzinfo=ISTANBUL)
    else:
        current = current.astimezone(ISTANBUL)

    for slot in config.send_times:
        if slot in config.sent_today:
            continue
        if current.time() >= _time_from_slot(slot):
            return slot
    return None


def evaluate_send_window(*, force: bool = False) -> tuple[bool, str, str | None]:
    config = get_schedule_config()
    if force:
        return True, "forced", None

    if len(config.sent_today) >= config.daily_count:
        return False, "daily_limit_reached", None

    due_slot = find_due_slot(config)
    if due_slot is None:
        return False, "not_scheduled_time", None

    return True, "scheduled", due_slot


def record_scheduled_send(slot: str | None) -> None:
    config = get_schedule_config()
    today = _today_istanbul()
    sent_today = list(config.sent_today)

    if slot:
        if slot not in sent_today:
            sent_today.append(slot)
    elif len(sent_today) < config.daily_count:
        sent_today.append("manual")

    repository.set_setting("cds_bugun_gonderim_tarihi", today)
    repository.set_setting("cds_bugun_gonderilen_saatler", json.dumps(sent_today, ensure_ascii=False))
    repository.set_setting("son_cds_gonderim_tarihi", today)
