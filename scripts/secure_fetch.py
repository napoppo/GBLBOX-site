"""Allowlisted HTTPS fetch helpers for maintainer scripts."""

from __future__ import annotations

from urllib.parse import urlparse

import requests

ALLOWED_URL_PREFIXES = (
    "https://raw.githubusercontent.com/PokeMiners/",
    "https://raw.githubusercontent.com/pvpoke/",
    "https://raw.githubusercontent.com/PokeAPI/",
)

DEFAULT_HEADERS = {"User-Agent": "GBLBOX-data-tools/1.0"}


def assert_allowlisted_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"Only HTTPS URLs are allowed: {url}")
    if not any(url.startswith(prefix) for prefix in ALLOWED_URL_PREFIXES):
        raise ValueError(f"URL is not allowlisted: {url}")


def fetch_bytes(url: str, *, timeout: int = 30) -> bytes:
    assert_allowlisted_url(url)
    response = requests.get(url, timeout=timeout, headers=DEFAULT_HEADERS)
    response.raise_for_status()
    return response.content


def download_file(url: str, destination: str, *, timeout: int = 30) -> None:
    data = fetch_bytes(url, timeout=timeout)
    with open(destination, "wb") as handle:
        handle.write(data)
