"""Saves email subscriptions as one encrypted file on a separate branch of the GitHub repository.

The file is encrypted with DATA_KEY, so email addresses and holdings are unreadable even if the repository is public.
It lives on its own branch so that saving a subscription never restarts the website.
"""

from __future__ import annotations

import base64
import hashlib
import json

import requests
from cryptography.fernet import Fernet, InvalidToken

import settings

BRANCH = "subscriptions"
PATH = "subscriptions.enc"
API = "https://api.github.com"


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.get("DATA_KEY").encode()).digest())
    return Fernet(key)


def _request(method: str, url: str, **kwargs):
    headers = {"Authorization": f"Bearer {settings.get('GH_TOKEN')}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    return requests.request(method, url, headers=headers, timeout=20, **kwargs)


def _file_url() -> str:
    return f"{API}/repos/{settings.get('GH_REPO')}/contents/{PATH}"


def load() -> tuple[dict, str | None]:
    """Returns ({email: record}, version id of the stored file)."""
    r = _request("GET", _file_url(), params={"ref": BRANCH})
    if r.status_code == 404:
        return {}, None
    r.raise_for_status()
    body = r.json()
    try:
        data = json.loads(_fernet().decrypt(base64.b64decode(body["content"])))
    except InvalidToken as e:
        raise RuntimeError("DATA_KEY does not match the key the subscriptions were saved with") from e
    return data, body["sha"]


def _ensure_branch():
    repo = settings.get("GH_REPO")
    if _request("GET", f"{API}/repos/{repo}/branches/{BRANCH}").status_code == 200:
        return
    info = _request("GET", f"{API}/repos/{repo}")
    info.raise_for_status()
    default = info.json()["default_branch"]
    head = _request("GET", f"{API}/repos/{repo}/git/ref/heads/{default}")
    head.raise_for_status()
    made = _request("POST", f"{API}/repos/{repo}/git/refs",
                    json={"ref": f"refs/heads/{BRANCH}", "sha": head.json()["object"]["sha"]})
    if made.status_code not in (201, 422):  # 422 = someone else just created it
        made.raise_for_status()


def save(data: dict, sha: str | None) -> bool:
    """Returns False if the file changed since it was loaded (caller should reload and retry)."""
    if sha is None:
        _ensure_branch()
    payload = {"message": "Update subscriptions", "branch": BRANCH,
               "content": base64.b64encode(_fernet().encrypt(json.dumps(data).encode())).decode()}
    if sha:
        payload["sha"] = sha
    r = _request("PUT", _file_url(), json=payload)
    if r.status_code in (409, 422):
        return False
    r.raise_for_status()
    return True


def change(fn) -> None:
    """Load, apply fn(data), save; retried if two people save at the same moment."""
    for _ in range(4):
        data, sha = load()
        fn(data)
        if save(data, sha):
            return
    raise RuntimeError("Could not save the subscription; please try again")


def upsert(email: str, record: dict) -> None:
    change(lambda data: data.__setitem__(email.lower(), record))


def remove_token(token: str) -> bool:
    removed = []

    def fn(data):
        for email in [e for e, rec in data.items() if rec.get("token") == token]:
            removed.append(email)
            del data[email]

    change(fn)
    return bool(removed)
