"""Pembersihan dan normalisasi teks berita (SRS 10.1 butir 3)."""

from __future__ import annotations

import hashlib
import re
import unicodedata

from bs4 import BeautifulSoup

# Pola pembuka berita: "JAKARTA, KONTAN.CO.ID -", "Bisnis.com, JAKARTA —", dst.
_PEMBUKA = re.compile(
    r"^\s*[A-Z][A-Za-z\.\s]{0,40},?\s*[A-Z][A-Za-z0-9\.\-]{0,30}(\.CO\.ID|\.COM|\.ID)?\s*[-–—:]\s*",
    re.IGNORECASE,
)
_SPASI = re.compile(r"\s+")
_URL = re.compile(r"https?://\S+")


def buang_html(teks: str) -> str:
    """Membuang tag HTML yang sering ikut di ringkasan RSS."""
    if not teks:
        return ""
    return BeautifulSoup(teks, "lxml").get_text(" ")


def bersihkan(teks: str | None) -> str:
    """Membersihkan satu potong teks: HTML, URL, pembuka redaksi, spasi ganda."""
    if not teks:
        return ""
    t = unicodedata.normalize("NFKC", teks)
    t = buang_html(t)
    t = _URL.sub(" ", t)
    t = _PEMBUKA.sub("", t)
    t = t.replace("\xa0", " ")
    return _SPASI.sub(" ", t).strip()


def normalisasi(teks: str) -> str:
    """Bentuk huruf kecil tanpa tanda baca — dipakai untuk pencocokan, bukan untuk disimpan."""
    t = bersihkan(teks).lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return _SPASI.sub(" ", t).strip()


def sidik_jari(judul: str, ringkasan: str | None = None) -> str:
    """Sidik jari isi berita.

    Dipakai untuk mengenali artikel yang sama yang disindikasi ulang oleh
    beberapa portal dengan URL berbeda.
    """
    bahan = normalisasi(judul) + "|" + normalisasi(ringkasan or "")[:280]
    return hashlib.sha256(bahan.encode("utf-8")).hexdigest()[:40]
