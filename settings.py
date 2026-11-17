"""Reads configuration values from environment variables (scheduled jobs) or Streamlit secrets (the website)."""

import os


def get(key: str, default: str = "") -> str:
    value = os.environ.get(key)
    if value:
        return value
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default


def email_ready() -> bool:
    """True when everything needed for daily emails has been configured."""
    return all(get(k) for k in ("SMTP_USER", "SMTP_PASSWORD", "GH_TOKEN", "GH_REPO", "DATA_KEY"))


APP_URL_DEFAULT = "https://stockanalysisclaude.streamlit.app"
