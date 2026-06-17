from __future__ import annotations

import base64
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

TIME_PATTERN = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
ISTANBUL = ZoneInfo("Europe/Istanbul")
UTC = ZoneInfo("UTC")


class WorkflowScheduleError(RuntimeError):
    pass


def _parse_times(send_times: str) -> list[str]:
    values: list[str] = []
    for part in send_times.split(","):
        value = part.strip()
        if not value:
            continue
        match = TIME_PATTERN.match(value)
        if not match:
            raise WorkflowScheduleError(f"Gecersiz saat formati: {value!r}")
        values.append(f"{int(match.group(1)):02d}:{int(match.group(2)):02d}")
    if not values:
        raise WorkflowScheduleError("En az bir saat gerekli.")
    return sorted(set(values))


def _cron_lines_for_istanbul(send_times: list[str]) -> list[str]:
    lines: list[str] = []
    for send_time in send_times:
        hour, minute = (int(part) for part in send_time.split(":"))
        local_dt = datetime(2026, 1, 1, hour, minute, tzinfo=ISTANBUL)
        utc_dt = local_dt.astimezone(UTC)
        lines.append(f'    - cron: "{utc_dt.minute} {utc_dt.hour} * * *"')
    return lines


def _replace_schedule_block(content: str, label: str, send_times: list[str]) -> str:
    lines = content.splitlines()
    try:
        schedule_index = next(i for i, line in enumerate(lines) if line.strip() == "schedule:")
        dispatch_index = next(
            i for i in range(schedule_index + 1, len(lines))
            if lines[i].strip() == "workflow_dispatch:"
        )
    except StopIteration as exc:
        raise WorkflowScheduleError("Workflow schedule blogu bulunamadi.") from exc

    replacement = [
        "  schedule:",
        f"    # Europe/Istanbul: {', '.join(send_times)}",
        *_cron_lines_for_istanbul(send_times),
    ]
    updated = lines[:schedule_index] + replacement + lines[dispatch_index:]
    return "\n".join(updated) + "\n"


def sync_workflow_schedule(
    *,
    token: str | None,
    repository: str,
    branch: str,
    workflow_path: str,
    label: str,
    send_times: str,
) -> list[str]:
    if not token:
        raise WorkflowScheduleError("GITHUB_WORKFLOW_TOKEN tanimli degil.")

    parsed_times = _parse_times(send_times)
    api_url = f"https://api.github.com/repos/{repository}/contents/{workflow_path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {"ref": branch}
    response = requests.get(api_url, headers=headers, params=params, timeout=30)
    if response.status_code >= 400:
        raise WorkflowScheduleError(f"Workflow okunamadi: {response.status_code} {response.text}")

    payload = response.json()
    current_content = base64.b64decode(payload["content"]).decode("utf-8")
    next_content = _replace_schedule_block(current_content, label, parsed_times)
    if next_content == current_content:
        return parsed_times

    encoded = base64.b64encode(next_content.encode("utf-8")).decode("ascii")
    update_response = requests.put(
        api_url,
        headers=headers,
        json={
            "message": f"{label} workflow saatlerini guncelle.",
            "content": encoded,
            "sha": payload["sha"],
            "branch": branch,
        },
        timeout=30,
    )
    if update_response.status_code >= 400:
        raise WorkflowScheduleError(
            f"Workflow guncellenemedi: {update_response.status_code} {update_response.text}"
        )
    return parsed_times


def dispatch_workflow(
    *,
    token: str | None,
    repository: str,
    branch: str,
    workflow_path: str,
) -> None:
    if not token:
        raise WorkflowScheduleError("GITHUB_WORKFLOW_TOKEN tanimli degil.")

    api_url = f"https://api.github.com/repos/{repository}/actions/workflows/{workflow_path}/dispatches"
    response = requests.post(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"ref": branch},
        timeout=30,
    )
    if response.status_code >= 400:
        raise WorkflowScheduleError(
            f"Workflow tetiklenemedi: {response.status_code} {response.text}"
        )
