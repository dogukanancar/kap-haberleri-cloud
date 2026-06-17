from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)


def _apply_streamlit_secrets() -> None:
    try:
        import streamlit as st

        if not hasattr(st, "secrets"):
            return
        mapping = {
            "DATABASE_URL": "DATABASE_URL",
            "TELEGRAM_BOT_TOKEN": "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID": "TELEGRAM_CHAT_ID",
            "KAP_BASE_URL": "KAP_BASE_URL",
            "GITHUB_WORKFLOW_TOKEN": "GITHUB_WORKFLOW_TOKEN",
            "GITHUB_REPOSITORY": "GITHUB_REPOSITORY",
            "GITHUB_BRANCH": "GITHUB_BRANCH",
        }
        for secret_key, env_key in mapping.items():
            if secret_key in st.secrets:
                os.environ[env_key] = str(st.secrets[secret_key])
    except Exception:
        return


@dataclass(frozen=True)
class Settings:
    database_url: str
    telegram_bot_token: str | None
    default_telegram_chat_id: str | None
    kap_base_url: str
    github_workflow_token: str | None
    github_repository: str
    github_branch: str


def reload_settings() -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    _apply_streamlit_secrets()
    get_settings.cache_clear()
    from src.db import reset_engine

    reset_engine()


@lru_cache
def get_settings() -> Settings:
    _apply_streamlit_secrets()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("DATABASE_URL tanimli degil.")
    return Settings(
        database_url=database_url,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        default_telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        kap_base_url=os.getenv("KAP_BASE_URL", "https://www.kap.org.tr"),
        github_workflow_token=os.getenv("GITHUB_WORKFLOW_TOKEN") or None,
        github_repository=os.getenv("GITHUB_REPOSITORY", "dogukanancar/kap-haberleri-cloud"),
        github_branch=os.getenv("GITHUB_BRANCH", "main"),
    )
