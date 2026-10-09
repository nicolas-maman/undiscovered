"""Submitting results through the volunteer's own GitHub account.

The token comes from the GitHub command-line tool (``gh auth login`` once)
or from the ``GITHUB_TOKEN`` variable. It is used only to talk to GitHub.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import requests

API = "https://api.github.com"


class NoGitHubLogin(RuntimeError):
    pass


def token() -> str:
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    gh = shutil.which("gh")
    if gh:
        out = subprocess.run([gh, "auth", "token"], capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    raise NoGitHubLogin("No GitHub login found. Install the GitHub command-line tool "
                        "(https://cli.github.com) and run: gh auth login")


def _headers(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def create_gist(tok: str, filename: str, content: str, description: str) -> str:
    """A secret gist: not listed anywhere, readable by anyone with its address."""
    resp = requests.post(f"{API}/gists", headers=_headers(tok), timeout=60, json={
        "description": description, "public": False, "files": {filename: {"content": content}}})
    resp.raise_for_status()
    return resp.json()["html_url"]


def open_issue(tok: str, repo: str, title: str, body: str, labels: list[str]) -> str:
    resp = requests.post(f"{API}/repos/{repo}/issues", headers=_headers(tok), timeout=60,
                         json={"title": title, "body": body, "labels": labels})
    resp.raise_for_status()
    return resp.json()["html_url"]
