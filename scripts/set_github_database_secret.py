"""GitHub Actions DATABASE_URL secret gunceller."""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read_database_url() -> str:
    env_path = ROOT / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(".env icinde DATABASE_URL bulunamadi.")


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
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def main() -> int:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        print("GITHUB_TOKEN ortam degiskeni yok.", file=sys.stderr)
        return 1

    try:
        from nacl import encoding, public
    except ImportError:
        print("pynacl eksik. Calistirin: pip install pynacl", file=sys.stderr)
        return 1

    owner = "dogukanancar"
    repo = "kap-haberleri-cloud"
    secret_name = "DATABASE_URL"
    database_url = _read_database_url()

    key_info = _github_request(
        "GET",
        f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key",
        token,
    )
    public_key = public.PublicKey(key_info["key"].encode("utf-8"), encoding.Base64Encoder)
    sealed = public.SealedBox(public_key).encrypt(database_url.encode("utf-8"))
    encrypted_value = base64.b64encode(sealed).decode("utf-8")

    _github_request(
        "PUT",
        f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}",
        token,
        {"encrypted_value": encrypted_value, "key_id": key_info["key_id"]},
    )
    print(f"GitHub secret guncellendi: {secret_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
