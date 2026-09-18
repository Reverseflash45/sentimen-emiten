"""Sumber data harga saham.

Dua penyedia disediakan dengan sengaja:

- CSV — selalu bisa dipakai, tidak bergantung layanan luar, dan hasilnya bisa
  direproduksi persis oleh penguji. Untuk keperluan skripsi ini yang utama.
- yfinance — praktis untuk pengembangan sehari-hari, tapi tidak resmi dan
  sewaktu-waktu bisa berubah. Dipasang opsional supaya sistem tetap jalan
  tanpa paket itu.
"""

from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from dateutil import parser as dateparser


@dataclass(frozen=True)
class BarisHarga:
    tanggal: datetime
    pembukaan: float | None
    tertinggi: float | None
    terendah: float | None
    penutupan: float | None
    volume: int | None


class PenyediaHarga(ABC):
    """Antarmuka penyedia harga. Tambah penyedia baru dengan mewarisi kelas ini."""

    @abstractmethod
    def ambil(self, kode: str, mulai: date, sampai: date) -> list[BarisHarga]:
        """Mengembalikan harga harian satu emiten pada rentang tanggal."""


def _angka(nilai: str | None) -> float | None:
    if nilai is None:
        return None
    teks = str(nilai).strip().replace(".", "").replace(",", ".") if "," in str(nilai) else str(nilai).strip()
    if teks in ("", "-", "N/A", "null", "None"):
        return None
    try:
        return float(teks)
    except ValueError:
        return None


def _bulat(nilai: str | None) -> int | None:
    angka = _angka(nilai)
    return int(angka) if angka is not None else None


class PenyediaCsv(PenyediaHarga):
    """Membaca harga dari berkas CSV per emiten: `<folder>/<KODE>.csv`.

    Kolom yang dikenali (huruf besar/kecil bebas, sebagian boleh tidak ada):
    tanggal/date, pembukaan/open, tertinggi/high, terendah/low,
    penutupan/close, volume.
    """

    KOLOM = {
        "tanggal": ("tanggal", "date", "datetime", "waktu"),
        "pembukaan": ("pembukaan", "open", "buka"),
        "tertinggi": ("tertinggi", "high"),
        "terendah": ("terendah", "low"),
        "penutupan": ("penutupan", "close", "adj close", "tutup"),
        "volume": ("volume", "vol"),
    }

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)

    def _petakan_kolom(self, header: list[str]) -> dict[str, str]:
        tersedia = {h.strip().lower(): h for h in header}
        peta: dict[str, str] = {}
        for kunci, calon in self.KOLOM.items():
            for c in calon:
                if c in tersedia:
                    peta[kunci] = tersedia[c]
                    break
        if "tanggal" not in peta:
            raise ValueError(f"kolom tanggal tidak ditemukan; header: {header}")
        return peta

    def ambil(self, kode: str, mulai: date, sampai: date) -> list[BarisHarga]:
        berkas = self.folder / f"{kode.upper()}.csv"
        if not berkas.exists():
            return []

        hasil: list[BarisHarga] = []
        with berkas.open(newline="", encoding="utf-8-sig") as f:
            pembaca = csv.DictReader(f)
            if not pembaca.fieldnames:
                return []
            peta = self._petakan_kolom(list(pembaca.fieldnames))

            for baris in pembaca:
                mentah = (baris.get(peta["tanggal"]) or "").strip()
                if not mentah:
                    continue
                try:
                    tgl = dateparser.parse(mentah)
                except (ValueError, OverflowError, TypeError):
                    continue
                if tgl is None:
                    continue
                tgl = tgl.replace(tzinfo=tgl.tzinfo or timezone.utc)
                if not (mulai <= tgl.date() <= sampai):
                    continue

                hasil.append(
                    BarisHarga(
                        tanggal=tgl.astimezone(timezone.utc),
                        pembukaan=_angka(baris.get(peta.get("pembukaan", ""))),
                        tertinggi=_angka(baris.get(peta.get("tertinggi", ""))),
                        terendah=_angka(baris.get(peta.get("terendah", ""))),
                        penutupan=_angka(baris.get(peta.get("penutupan", ""))),
                        volume=_bulat(baris.get(peta.get("volume", ""))),
                    )
                )

        hasil.sort(key=lambda b: b.tanggal)
        return hasil


class PenyediaYFinance(PenyediaHarga):
    """Penyedia daring lewat paket yfinance. Kode emiten diberi akhiran `.JK`.

    Tidak resmi — pakai untuk pengembangan, bukan untuk angka yang dilaporkan.
    """

    def __init__(self) -> None:
        try:
            import yfinance  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "paket yfinance belum terpasang. Jalankan: pip install yfinance"
            ) from exc

    def ambil(self, kode: str, mulai: date, sampai: date) -> list[BarisHarga]:  # pragma: no cover
        import yfinance as yf

        data = yf.Ticker(f"{kode.upper()}.JK").history(
            start=mulai.isoformat(), end=sampai.isoformat(), auto_adjust=False
        )
        hasil: list[BarisHarga] = []
        for idx, baris in data.iterrows():
            tgl = idx.to_pydatetime()
            hasil.append(
                BarisHarga(
                    tanggal=tgl.astimezone(timezone.utc) if tgl.tzinfo else tgl.replace(tzinfo=timezone.utc),
                    pembukaan=float(baris.get("Open")) if baris.get("Open") == baris.get("Open") else None,
                    tertinggi=float(baris.get("High")) if baris.get("High") == baris.get("High") else None,
                    terendah=float(baris.get("Low")) if baris.get("Low") == baris.get("Low") else None,
                    penutupan=float(baris.get("Close")) if baris.get("Close") == baris.get("Close") else None,
                    volume=int(baris.get("Volume")) if baris.get("Volume") == baris.get("Volume") else None,
                )
            )
        return hasil
