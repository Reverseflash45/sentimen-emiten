"""Pengambilan berita dari RSS/Atom portal finansial (SRS 10.1 butir 1).

Parsing memakai pustaka bawaan Python. RSS 2.0 dan Atom sama-sama ditangani
karena portal Indonesia memakai keduanya.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from dateutil import parser as dateparser

from app.config import settings
from app.ingest import robots
from app.ingest.cleaner import bersihkan, sidik_jari

NS = {"atom": "http://www.w3.org/2005/Atom", "dc": "http://purl.org/dc/elements/1.1/"}


@dataclass
class ArtikelMentah:
    judul: str
    ringkasan: str
    url: str
    terbit_pada: datetime | None
    sidik_jari: str


def _teks(elemen: ET.Element | None) -> str:
    if elemen is None:
        return ""
    return "".join(elemen.itertext()).strip()


def _tanggal(nilai: str) -> datetime | None:
    if not nilai:
        return None
    try:
        dt = dateparser.parse(nilai)
    except (ValueError, OverflowError, TypeError):
        return None
    if dt is None:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _tautan_atom(entry: ET.Element) -> str:
    """Atom menaruh URL di atribut href, bukan di isi elemen."""
    for link in entry.findall("atom:link", NS):
        rel = link.get("rel", "alternate")
        if rel == "alternate" and link.get("href"):
            return link.get("href", "")
    link = entry.find("atom:link", NS)
    return link.get("href", "") if link is not None else ""


def parse_feed(isi: bytes | str) -> list[ArtikelMentah]:
    """Mem-parse isi RSS/Atom menjadi daftar artikel.

    Dipisah dari pengambilan jaringan supaya bisa diuji tanpa koneksi.
    """
    if isinstance(isi, str):
        isi = isi.encode("utf-8")
    try:
        root = ET.fromstring(isi)
    except ET.ParseError as exc:
        raise ValueError(f"feed tidak bisa di-parse: {exc}") from exc

    entri = root.findall(".//item") or root.findall(".//atom:entry", NS)
    hasil: list[ArtikelMentah] = []

    for e in entri:
        atom = e.tag.endswith("entry")
        judul = bersihkan(_teks(e.find("atom:title", NS) if atom else e.find("title")))
        tautan = _tautan_atom(e) if atom else _teks(e.find("link"))
        if not judul or not tautan:
            continue

        if atom:
            ringkasan = _teks(e.find("atom:summary", NS)) or _teks(e.find("atom:content", NS))
            mentah_tgl = _teks(e.find("atom:published", NS)) or _teks(e.find("atom:updated", NS))
        else:
            ringkasan = _teks(e.find("description"))
            mentah_tgl = _teks(e.find("pubDate")) or _teks(e.find("dc:date", NS))

        ringkasan = bersihkan(ringkasan)
        hasil.append(
            ArtikelMentah(
                judul=judul,
                ringkasan=ringkasan,
                url=tautan.split("?")[0].strip(),
                terbit_pada=_tanggal(mentah_tgl),
                sidik_jari=sidik_jari(judul, ringkasan),
            )
        )

    return hasil


def ambil_feed(url_rss: str, batas: int | None = None) -> list[ArtikelMentah]:
    """Mengambil lalu mem-parse satu feed.

    Melempar RuntimeError bila robots.txt melarang, supaya pemanggil bisa
    mencatatnya di log tanpa menghentikan sumber lain.
    """
    if not robots.boleh_diambil(url_rss):
        raise RuntimeError(f"robots.txt melarang pengambilan: {url_rss}")

    r = httpx.get(
        url_rss,
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": settings.user_agent},
    )
    r.raise_for_status()

    artikel = parse_feed(r.content)
    time.sleep(robots.jeda_crawl(url_rss))
    return artikel[: (batas or settings.max_items_per_source)]
