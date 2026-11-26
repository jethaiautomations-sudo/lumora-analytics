"""Reads integration settings from .streamlit/secrets.toml or environment variables."""
from __future__ import annotations

import os

import streamlit as st


def get_setting(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except Exception:  # no secrets.toml
        value = None
    value = value or os.environ.get(name)
    return str(value).strip() if value else None


def gsheet_id() -> str | None:
    return get_setting("GSHEET_ID")


def n8n_webhook_url() -> str | None:
    return get_setting("N8N_WEBHOOK_URL")


def anthropic_key() -> str | None:
    return get_setting("ANTHROPIC_API_KEY")


def openai_key() -> str | None:
    return get_setting("OPENAI_API_KEY")


def ai_provider() -> tuple[str, str, str | None] | None:
    """(provider, api_key, model) for whichever AI key is set; OpenAI first. None if neither."""
    if openai_key():
        return "openai", openai_key(), get_setting("OPENAI_MODEL")
    if anthropic_key():
        return "anthropic", anthropic_key(), None
    return None
