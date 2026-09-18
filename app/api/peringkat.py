"""Ikhtisar seluruh emiten sekaligus (SRS UC-01).

Halaman per emiten menjawab "bagaimana emiten ini?". Yang tidak dijawabnya
adalah "emiten mana yang perlu dilihat hari ini?" — dan justru pertanyaan itu
yang muncul lebih dulu ketika ada 45 emiten dipantau. Endpoint ini menjawabnya
dengan satu tabel: skor sentimen rentang, jumlah berita, dan perubahan harga.

Skor di sini adalah rata-rata tertimbang skor harian pada rentang, bukan skor
satu hari terakhir. Satu hari terakhir mudah menyesatkan: emiten yang hari itu
kebetulan tidak diberitakan akan tampak netral, padahal sepekan sebelumnya
diberitakan negatif terus-menerus.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analitik.agregasi import hitung_skor_harian
from app.api.bantu import rentang
from app.database import get_session
from app.models import Emiten, HargaSaham
from app.schemas import BarisPeringkat, Peringkat

router = APIRouter(prefix="/api/peringkat", tags=["peringkat"])


def _harga(session: Session, emiten_id: int, mulai: date, sampai: date):
    """Harga penutupan pertama dan terakhir pada rentang."""
    baris = [
        h for h in session.scalars(
            select(HargaSaham)
            .where(HargaSaham.emiten_id == emiten_id)
            .order_by(HargaSaham.tanggal)
        )
        if h.penutupan is not None and mulai <= h.tanggal.date() <= sampai
    ]
    if not baris:
        return None, None
    awal, akhir = baris[0].penutupan, baris[-1].penutupan
    ubah = None if not awal else round(100.0 * (akhir - awal) / awal, 2)
    return akhir, ubah


@router.get("", response_model=Peringkat)
def peringkat(
    mulai: date | None = None,
    sampai: date | None = None,
    maks_emiten_per_berita: int | None = Query(None, ge=1, le=50),
    hanya_berberita: bool = Query(
        False, description="sembunyikan emiten yang belum punya berita berlabel"
    ),
    session: Session = Depends(get_session),
) -> Peringkat:
    awal, akhir = rentang(mulai, sampai)
    hasil: list[BarisPeringkat] = []

    for emiten in session.scalars(
        select(Emiten).where(Emiten.aktif.is_(True)).order_by(Emiten.kode)
    ):
        skor_harian = hitung_skor_harian(
            session, emiten.kode, awal, akhir,
            maks_emiten_per_berita=maks_emiten_per_berita,
        )
        jumlah = sum(s.jumlah_berita for s in skor_harian)
        if hanya_berberita and not jumlah:
            continue

        # rata-rata tertimbang jumlah berita: hari dengan banyak berita lebih
        # menentukan daripada hari dengan satu berita
        skor = (
            round(sum(s.skor * s.jumlah_berita for s in skor_harian) / jumlah, 4)
            if jumlah else None
        )
        harga, ubah = _harga(session, emiten.id, awal, akhir)

        hasil.append(
            BarisPeringkat(
                kode=emiten.kode,
                nama=emiten.nama,
                sektor=emiten.sektor,
                skor=skor,
                jumlah_berita=jumlah,
                jumlah_positif=sum(s.jumlah_positif for s in skor_harian),
                jumlah_negatif=sum(s.jumlah_negatif for s in skor_harian),
                harga_terakhir=harga,
                perubahan_harga=ubah,
            )
        )

    # yang punya berita lebih dulu, lalu skor terendah (paling perlu dilihat)
    hasil.sort(key=lambda b: (b.jumlah_berita == 0, b.skor if b.skor is not None else 0))
    return Peringkat(mulai=awal, sampai=akhir, baris=hasil)
