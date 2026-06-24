"""GitHub Actions secretlarini .env dosyasindan gunceller."""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)

SECRET_KEYS = (
    "DATABASE_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


def _github_request(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **({} if body is None else {"Content-Type": "application/json"}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code}: {detail}") from exc


def _encrypt_secret(value: str, public_key_b64: str) -> str:
    from nacl import encoding, public

    public_key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder)
    sealed = public.SealedBox(public_key).encrypt(value.encode("utf-8"))
    return base64.b64encode(sealed).decode("utf-8")


def main() -> int:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        print("GITHUB_TOKEN .env icinde yok.", file=sys.stderr)
        return 1

    owner = "dogukanancar"
    repo = "kap-haberleri-cloud"
    key_info = _github_request(
        "GET",
        f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key",
        token,
    )

    updated = 0
    for secret_name in SECRET_KEYS:
        value = os.getenv(secret_name, "").strip()
        if not value:
            print(f"Atlandi (bos): {secret_name}")
            continue
        encrypted_value = _encrypt_secret(value, key_info["key"])
        _github_request(
            "PUT",
            f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}",
            token,
            {"encrypted_value": encrypted_value, "key_id": key_info["key_id"]},
        )
        print(f"GitHub secret guncellendi: {secret_name}")
        updated += 1

    if updated == 0:
        print("Guncellenecek secret bulunamadi.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
