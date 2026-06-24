"""GitHub Actions KAP Worker workflow'unu .env icindeki GITHUB_TOKEN ile tetikler."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)

OWNER = "dogukanancar"
REPO = "kap-haberleri-cloud"
WORKFLOW = "kap_worker.yml"
REF = "main"


def main() -> int:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        print("GITHUB_TOKEN .env icinde yok.", file=sys.stderr)
        return 1

    url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{WORKFLOW}/dispatches"
    req = urllib.request.Request(
        url,
        data=json.dumps({"ref": REF}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 204:
                print("KAP Worker tetiklendi (CDS + Brand dahil). Actions sekmesinden takip edin.")
                return 0
            print(f"Beklenmeyen yanit: {resp.status}", file=sys.stderr)
            return 1
    except urllib.error.HTTPError as exc:
        print(f"Hata HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
