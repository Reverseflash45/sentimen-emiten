"""Penyandingan deret sentimen dengan pergerakan harga (SRS 10.1 butir 7).

Sistem hanya menyajikan hubungan korelatif dan tidak melakukan prediksi harga
(SRS 10.3). Modul ini sengaja tidak menyediakan fungsi apa pun yang mengeluarkan
ramalan harga.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analitik.agregasi import SkorHarian, hitung_skor_harian
from app.analitik.statistik import HasilKorelasi, imbal_hasil_harian, pearson, spearman
from app.models import Emiten, HargaSaham


@dataclass
class TitikGabungan:
    tanggal: date
    skor_sentimen: float
    penutupan: float
    jumlah_berita: int


@dataclass
class HasilPenyandingan:
    kode: str
    titik: list[TitikGabungan]
    pearson: HasilKorelasi | None
    spearman: HasilKorelasi | None
    lag: int
    catatan: str | None = None
    maks_emiten_per_berita: int | None = None


def ambil_harga(session: Session, kode: str, mulai: date, sampai: date) -> dict[date, float]:
    emiten = session.scalar(select(Emiten).where(Emiten.kode == kode.upper()))
    if emiten is None:
        return {}
    hasil: dict[date, float] = {}
    for h in session.scalars(
        select(HargaSaham).where(HargaSaham.emiten_id == emiten.id).order_by(HargaSaham.tanggal)
    ):
        if h.penutupan is None:
            continue
        tgl = h.tanggal.date()
        if mulai <= tgl <= sampai:
            hasil[tgl] = h.penutupan
    return hasil


def gabungkan(skor: list[SkorHarian], harga: dict[date, float]) -> list[TitikGabungan]:
    """Menggabungkan pada tanggal yang punya kedua data.

    Hari bursa libur tidak punya harga, jadi tanggal itu dilewati — bukan diisi
    nol, karena nol akan terbaca sebagai harga turun ke titik tersebut.
    """
    titik: list[TitikGabungan] = []
    for s in skor:
        tutup = harga.get(s.tanggal)
        if tutup is None:
            continue
        titik.append(TitikGabungan(s.tanggal, s.skor, tutup, s.jumlah_berita))
    return titik


def sandingkan(
    session: Session,
    kode: str,
    mulai: date,
    sampai: date,
    lag: int = 0,
    maks_emiten_per_berita: int | None = None,
) -> HasilPenyandingan:
    """Menyandingkan sentimen dengan imbal hasil harian.

    `lag` positif berarti sentimen hari ini dibandingkan dengan imbal hasil
    `lag` hari berikutnya — dipakai untuk memeriksa apakah sentimen mendahului
    pergerakan harga.
    """
    skor = hitung_skor_harian(
        session, kode, mulai, sampai, maks_emiten_per_berita=maks_emiten_per_berita
    )
    harga = ambil_harga(session, kode, mulai, sampai)
    titik = gabungkan(skor, harga)

    if len(titik) < 4:
        return HasilPenyandingan(
            kode.upper(), titik, None, None, lag,
            catatan="data belum cukup untuk menghitung korelasi (minimal 4 hari beririsan)",
        )

    sentimen = [t.skor_sentimen for t in titik]
    imbal = imbal_hasil_harian([t.penutupan for t in titik])
    # imbal hasil lebih pendek satu, sejajarkan dengan sentimen hari sebelumnya
    sentimen = sentimen[:-1]

    if lag > 0:
        if lag >= len(imbal):
            return HasilPenyandingan(
                kode.upper(), titik, None, None, lag,
                catatan=f"lag {lag} hari melebihi panjang data",
            )
        sentimen = sentimen[:-lag]
        imbal = imbal[lag:]

    if len(sentimen) < 3:
        return HasilPenyandingan(
            kode.upper(), titik, None, None, lag,
            catatan="data belum cukup setelah pergeseran lag",
        )

    return HasilPenyandingan(
        kode.upper(), titik, pearson(sentimen, imbal), spearman(sentimen, imbal), lag,
        maks_emiten_per_berita=maks_emiten_per_berita,
    )
