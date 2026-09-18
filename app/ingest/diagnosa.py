"""Diagnosa pemetaan: kenapa berita tidak terpetakan ke emiten.

Rasio pemetaan yang rendah bisa berarti dua hal yang sangat berbeda:

1. pencocokannya gagal padahal emitennya ada di cakupan — ini cacat yang harus
   diperbaiki;
2. beritanya memang membahas emiten di luar cakupan LQ45 — ini konsekuensi
   batasan cakupan (SRS 10.3), bukan cacat.

Tanpa memisahkan keduanya, angka "92 berita tanpa emiten" tidak bisa ditafsirkan
dan akan sulit dipertanggungjawabkan saat sidang. Modul ini memisahkannya dengan
mencari token yang berbentuk kode emiten pada judul berita yang tidak terpetakan,
lalu membandingkannya dengan daftar emiten yang dipantau.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Berita, BeritaEmiten, Emiten

# Singkatan empat huruf kapital yang lazim di berita pasar modal tapi bukan kode
# emiten. Tanpa daftar ini, "RUPS" dan "POJK" akan terhitung sebagai emiten.
BUKAN_KODE = {
    "IHSG", "RUPS", "POJK", "OJKS", "BUMN", "APBN", "APBD", "PPKM", "PPKB",
    "KPPU", "PSEL", "KDKM", "KDKMP", "UMKM", "IPOS", "ETIK", "SWOT", "IPO",
    "OBLI", "REPO", "ESOP", "MESOP", "EBIT", "EBIA", "ROIC", "ROAE", "CAGR",
    "YOUS", "YTDY", "QOQS", "MOMS", "USDS", "IDRS", "JPYS", "EURS",
    "ANALIS", "MARKET", "PERSEN", "LEVEL", "SAHAM", "INDEX", "INDEKS",
    "BANK", "TBKS", "SOAL", "JADI", "BARU", "LAGI", "INDO", "ASIA",
    "UMAS", "UMA", "BEI", "IDX", "OJK", "BPK", "KPK", "BTN", "DBS", "HSBC",
    "PPN", "PSE", "EGI", "SAL", "AKAN", "DARI", "PADA", "ATAS", "OLEH",
    "OPEC", "IMFS", "WTOS", "ASEAN", "NIKKEI", "KOSPI", "DJIA", "SNPS",
}

_KODE = re.compile(r"\b[A-Z]{4}\b")


@dataclass
class HasilDiagnosa:
    total_tanpa_emiten: int = 0
    menyebut_kode_dipantau: int = 0
    menyebut_kode_luar_cakupan: int = 0
    tanpa_kode_apa_pun: int = 0
    kode_luar_cakupan: Counter = field(default_factory=Counter)
    contoh_terlewat: list[tuple[int, str, list[str]]] = field(default_factory=list)

    @property
    def persen_luar_cakupan(self) -> float:
        if not self.total_tanpa_emiten:
            return 0.0
        return 100.0 * self.menyebut_kode_luar_cakupan / self.total_tanpa_emiten

    def ringkas(self) -> str:
        return (
            f"tanpa_emiten={self.total_tanpa_emiten} "
            f"luar_cakupan={self.menyebut_kode_luar_cakupan} "
            f"terlewat={self.menyebut_kode_dipantau} "
            f"tanpa_kode={self.tanpa_kode_apa_pun}"
        )


def kode_kandidat(teks: str) -> list[str]:
    """Token berbentuk kode emiten pada sebuah teks."""
    return [k for k in dict.fromkeys(_KODE.findall(teks or "")) if k not in BUKAN_KODE]


def diagnosa(session: Session, batas: int = 500) -> HasilDiagnosa:
    hasil = HasilDiagnosa()
    dipantau = {e.kode for e in session.scalars(select(Emiten))}

    terpetakan = select(BeritaEmiten.berita_id)
    berita = session.scalars(
        select(Berita)
        .where(Berita.id.not_in(terpetakan))
        .order_by(Berita.id.desc())
        .limit(batas)
    )

    for b in berita:
        hasil.total_tanpa_emiten += 1
        kandidat = kode_kandidat(b.judul)
        if not kandidat:
            hasil.tanpa_kode_apa_pun += 1
            continue

        di_cakupan = [k for k in kandidat if k in dipantau]
        if di_cakupan:
            # Ini yang perlu diperiksa: kodenya dipantau tapi tidak terpetakan.
            hasil.menyebut_kode_dipantau += 1
            if len(hasil.contoh_terlewat) < 15:
                hasil.contoh_terlewat.append((b.id, b.judul, di_cakupan))
            continue

        hasil.menyebut_kode_luar_cakupan += 1
        hasil.kode_luar_cakupan.update(kandidat)

    return hasil
