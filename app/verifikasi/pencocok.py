"""Mencocokkan berita dengan pengumuman resmi BEI (SRS UC-04).

Batas yang disadari sejak awal: pencocokan ini hanya bisa MENAIKKAN keyakinan,
tidak pernah membuktikan sebuah kabar salah. Tidak adanya pengumuman resmi bisa
berarti kabarnya belum diumumkan, bukan berarti kabarnya bohong. Karena itu:

- status TERKONFIRMASI_RESMI hanya diberi bila ada pengumuman yang cocok;
- status RUMOR_BELUM_TERKONFIRMASI hanya diberi bila berita itu sendiri memakai
  bahasa spekulatif ("dikabarkan", "santer", "disebut-sebut") DAN tidak ada
  pengumuman yang cocok;
- selain itu status dibiarkan BELUM_DIPERIKSA, bukan dipaksa jadi rumor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.verifikasi.sumber import PengumumanMentah

# jendela waktu: pengumuman resmi biasanya keluar bersamaan atau sesudah kabar
HARI_SEBELUM = 3
HARI_SESUDAH = 7

AMBANG_KEMIRIPAN = 0.18
MIN_KATA_SAMA = 2

KATA_SPEKULATIF = {
    "dikabarkan", "kabarnya", "rumor", "santer", "isu", "isunya",
    "disebut", "diduga", "dugaan", "konon", "beredar", "spekulasi",
    "belum", "dikonfirmasi", "diklaim", "katanya",
}

# kata yang terlalu umum di judul pengumuman maupun berita finansial
KATA_UMUM = {
    "dan", "yang", "di", "ke", "dari", "untuk", "pada", "dengan", "atas",
    "ini", "itu", "akan", "telah", "sudah", "oleh", "dalam", "adalah",
    "penyampaian", "laporan", "informasi", "keterbukaan", "pengumuman",
    "perseroan", "perusahaan", "tbk", "pt", "emiten", "saham", "bursa",
    "efek", "indonesia", "bei", "idx", "terkait", "mengenai", "tentang",
    "berita", "kabar", "hari", "tahun", "bulan", "resmi", "jadi", "usai",
}

_TOKEN = re.compile(r"[a-z0-9]+")


def kata_isi(teks: str) -> set[str]:
    """Kata bermakna dari sebuah judul: huruf kecil, tanpa kata umum dan
    tanpa kata sangat pendek."""
    return {
        k for k in _TOKEN.findall((teks or "").lower())
        if len(k) > 3 and k not in KATA_UMUM
    }


def kemiripan(judul_berita: str, judul_pengumuman: str) -> float:
    """Jaccard atas kata bermakna kedua judul.

    Jaccard dipilih, bukan kecocokan persis, karena judul berita hampir tidak
    pernah sama dengan judul pengumuman resmi — yang bisa diandalkan cuma
    irisan kata pentingnya (mis. "dividen", "akuisisi", "obligasi").
    """
    a, b = kata_isi(judul_berita), kata_isi(judul_pengumuman)
    if not a or not b:
        return 0.0
    irisan = a & b
    if len(irisan) < MIN_KATA_SAMA:
        return 0.0
    return len(irisan) / len(a | b)


def bahasa_spekulatif(teks: str) -> bool:
    kata = set(_TOKEN.findall((teks or "").lower()))
    return bool(kata & KATA_SPEKULATIF)


def waktu_utc(dt: datetime | None) -> datetime | None:
    """SQLite mengembalikan datetime tanpa zona waktu. Tanpa penyeragaman ini
    perbandingan tanggal akan melempar galat saat data berasal dari basis data
    tapi tidak saat berasal dari memori — kegagalan yang hanya muncul di
    produksi."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class Kecocokan:
    pengumuman: PengumumanMentah
    kemiripan: float
    kata_sama: list[str]


def cari_kecocokan(
    judul_berita: str,
    terbit_berita: datetime | None,
    pengumuman: list[PengumumanMentah],
    ambang: float = AMBANG_KEMIRIPAN,
) -> Kecocokan | None:
    """Pengumuman paling mirip yang masih berada dalam jendela waktu."""
    terbaik: Kecocokan | None = None
    acuan = waktu_utc(terbit_berita)

    for p in pengumuman:
        waktu = waktu_utc(p.terbit_pada)
        if acuan and waktu:
            if waktu < acuan - timedelta(days=HARI_SEBELUM):
                continue
            if waktu > acuan + timedelta(days=HARI_SESUDAH):
                continue
        nilai = kemiripan(judul_berita, p.judul)
        if nilai < ambang:
            continue
        if terbaik is None or nilai > terbaik.kemiripan:
            terbaik = Kecocokan(
                pengumuman=p,
                kemiripan=round(nilai, 4),
                kata_sama=sorted(kata_isi(judul_berita) & kata_isi(p.judul)),
            )
    return terbaik
