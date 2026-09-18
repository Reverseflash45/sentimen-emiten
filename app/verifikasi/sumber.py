"""Sumber pengumuman keterbukaan informasi BEI (SRS UC-04).

Dua implementasi disediakan dengan alasan yang berbeda:

- `SumberCsv` membaca berkas hasil unduhan manual dari situs BEI. Ini yang
  dipakai untuk penelitian: datanya tetap, bisa dilampirkan, dan hasilnya bisa
  diulang orang lain persis sama.
- `SumberIdx` mengambil langsung dari endpoint BEI. Lebih praktis untuk
  operasional harian, tapi bentuk responsnya bisa berubah sewaktu-waktu dan
  akses bisa ditolak. Karena itu ia BUKAN sumber utama, dan kegagalannya tidak
  dianggap fatal.

Keduanya mengembalikan bentuk yang sama, jadi bagian lain sistem tidak perlu
tahu pengumuman itu datang dari mana.
"""

from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dateutil import parser as dateparser

from app.config import settings

ENDPOINT_IDX = "https://www.idx.co.id/primary/ListedCompany/GetAnnouncement"


@dataclass
class PengumumanMentah:
    kode_emiten: str
    judul: str
    url: str
    terbit_pada: datetime | None


def _tanggal(nilai: str | None) -> datetime | None:
    if not nilai:
        return None
    try:
        dt = dateparser.parse(str(nilai))
    except (ValueError, OverflowError, TypeError):
        return None
    if dt is None:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class SumberKeterbukaan(ABC):
    nama: str = "-"

    @abstractmethod
    def ambil(self, kode: str, mulai: datetime, sampai: datetime) -> list[PengumumanMentah]:
        """Pengumuman satu emiten pada rentang waktu tertentu."""


# --------------------------------------------------------------------------- CSV


KOLOM_KODE = ("kode", "kode_emiten", "code", "ticker")
KOLOM_JUDUL = ("judul", "perihal", "title", "subject")
KOLOM_URL = ("url", "tautan", "link")
KOLOM_TANGGAL = ("tanggal", "terbit", "date", "published")


def _kolom(baris: dict[str, str], nama: tuple[str, ...]) -> str:
    peta = {(k or "").strip().lower(): v for k, v in baris.items()}
    for n in nama:
        if n in peta and peta[n]:
            return str(peta[n]).strip()
    return ""


class SumberCsv(SumberKeterbukaan):
    """Membaca pengumuman dari berkas CSV hasil unduhan manual.

    Kolomnya dikenali dalam bahasa Indonesia maupun Inggris, sama seperti
    berkas harga, supaya tidak ada langkah menyunting berkas sebelum dipakai.
    """

    nama = "csv"

    def __init__(self, berkas: str | Path) -> None:
        self.berkas = Path(berkas)

    def semua(self) -> list[PengumumanMentah]:
        if not self.berkas.exists():
            raise FileNotFoundError(f"berkas keterbukaan tidak ditemukan: {self.berkas}")
        hasil: list[PengumumanMentah] = []
        with self.berkas.open(encoding="utf-8-sig", newline="") as f:
            for baris in csv.DictReader(f):
                kode = _kolom(baris, KOLOM_KODE).upper()
                judul = _kolom(baris, KOLOM_JUDUL)
                if not kode or not judul:
                    continue
                hasil.append(
                    PengumumanMentah(
                        kode_emiten=kode,
                        judul=judul,
                        url=_kolom(baris, KOLOM_URL),
                        terbit_pada=_tanggal(_kolom(baris, KOLOM_TANGGAL)),
                    )
                )
        return hasil

    def ambil(self, kode: str, mulai: datetime, sampai: datetime) -> list[PengumumanMentah]:
        kode = kode.upper()
        keluar: list[PengumumanMentah] = []
        for p in self.semua():
            if p.kode_emiten != kode:
                continue
            if p.terbit_pada and not (mulai <= p.terbit_pada <= sampai):
                continue
            keluar.append(p)
        return keluar


# --------------------------------------------------------------------------- IDX


class SumberIdx(SumberKeterbukaan):
    """Pengambilan langsung dari BEI.

    Situs BEI tidak menyediakan API publik yang dijanjikan stabil, jadi bentuk
    respons di sini bisa berubah. Karena itu parsingnya dibuat longgar: kunci
    yang tidak dikenal dilewati, dan kegagalan dilempar sebagai galat biasa
    supaya pemanggil bisa memutuskan untuk melanjutkan dengan sumber lain.
    """

    nama = "idx"

    def __init__(self, klien: httpx.Client | None = None) -> None:
        self.klien = klien

    def _get(self, params: dict) -> dict:
        kepala = {
            "User-Agent": settings.user_agent,
            "Accept": "application/json",
            "Referer": "https://www.idx.co.id/",
        }
        if self.klien is not None:
            r = self.klien.get(ENDPOINT_IDX, params=params, headers=kepala, timeout=20.0)
        else:
            r = httpx.get(
                ENDPOINT_IDX, params=params, headers=kepala, timeout=20.0, follow_redirects=True
            )
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _petik(item: dict) -> PengumumanMentah | None:
        """Mengambil field yang dibutuhkan dari satu item, apa pun penamaannya."""
        rendah = {str(k).lower(): v for k, v in item.items()}

        def cari(*kunci: str) -> str:
            for k in kunci:
                nilai = rendah.get(k)
                if nilai:
                    return str(nilai).strip()
            return ""

        judul = cari("judulpengumuman", "judul", "title", "perihal", "subject")
        kode = cari("kodeemiten", "kode", "code", "emiten").upper()
        if not judul or not kode:
            return None
        url = cari("attachmenturl", "url", "link", "filepath")
        if url and url.startswith("/"):
            url = f"https://www.idx.co.id{url}"
        return PengumumanMentah(
            kode_emiten=kode.split(",")[0].strip(),
            judul=judul,
            url=url,
            terbit_pada=_tanggal(cari("publishdate", "tanggal", "date", "created")),
        )

    def ambil(self, kode: str, mulai: datetime, sampai: datetime) -> list[PengumumanMentah]:
        data = self._get(
            {
                "kodeEmiten": kode.upper(),
                "indexFrom": 0,
                "pageSize": 100,
                "dateFrom": mulai.strftime("%Y%m%d"),
                "dateTo": sampai.strftime("%Y%m%d"),
                "lang": "id",
            }
        )
        isi = data.get("Replies") or data.get("Items") or data.get("data") or []
        hasil: list[PengumumanMentah] = []
        for item in isi:
            if not isinstance(item, dict):
                continue
            p = self._petik(item)
            if p is None:
                continue
            if p.terbit_pada and not (mulai <= p.terbit_pada <= sampai):
                continue
            hasil.append(p)
        return hasil
