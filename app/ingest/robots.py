"""Kepatuhan robots.txt (NF-09).

Setiap domain diperiksa sekali lalu disimpan di memori selama proses berjalan.
Bila robots.txt tidak bisa diambil, sikap yang diambil adalah menolak —
lebih baik melewatkan satu sumber daripada mengambil yang tidak diizinkan.
"""

from __future__ import annotations

import urllib.robotparser as robotparser
from urllib.parse import urlparse

import httpx

from app.config import settings

_cache: dict[str, robotparser.RobotFileParser | None] = {}


def _ambil_parser(domain: str) -> robotparser.RobotFileParser | None:
    if domain in _cache:
        return _cache[domain]

    parser = robotparser.RobotFileParser()
    url = f"https://{domain}/robots.txt"
    try:
        r = httpx.get(
            url,
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": settings.user_agent},
        )
        if r.status_code >= 400:
            # Tidak ada robots.txt berarti tidak ada larangan.
            parser.parse([])
        else:
            parser.parse(r.text.splitlines())
    except Exception:
        parser = None  # gagal diambil — tandai supaya akses ditolak

    _cache[domain] = parser
    return parser


def boleh_diambil(url: str) -> bool:
    """Apakah URL ini boleh diambil menurut robots.txt domainnya."""
    domain = urlparse(url).netloc
    if not domain:
        return False
    parser = _ambil_parser(domain)
    if parser is None:
        return False
    return parser.can_fetch(settings.user_agent, url)


def jeda_crawl(url: str) -> float:
    """Jeda yang diminta portal, atau nilai bawaan bila tidak disebutkan."""
    domain = urlparse(url).netloc
    parser = _ambil_parser(domain)
    if parser is None:
        return settings.crawl_delay
    try:
        d = parser.crawl_delay(settings.user_agent)
        return max(float(d), settings.crawl_delay) if d else settings.crawl_delay
    except Exception:
        return settings.crawl_delay


def bersihkan_cache() -> None:
    _cache.clear()
