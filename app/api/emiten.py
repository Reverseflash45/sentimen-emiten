"""Endpoint emiten: daftar, detail, deret sentimen, deret harga, korelasi."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analitik.agregasi import hitung_skor_harian
from app.analitik.korelasi import sandingkan
from app.api.bantu import ambil_emiten, rentang
from app.database import get_session
from app.models import BeritaEmiten, Emiten, HargaSaham, KeterbukaanInformasi
from app.schemas import (
    DeretHarga,
    DeretSentimen,
    EmitenDetail,
    EmitenRingkas,
    HasilKorelasi,
    Korelasi,
    PengumumanRingkas,
    TitikHarga,
    TitikSentimen,
)

router = APIRouter(prefix="/api/emiten", tags=["emiten"])


@router.get("", response_model=list[EmitenRingkas])
def daftar_emiten(
    q: str | None = Query(None, description="cari berdasarkan kode atau nama"),
    sektor: str | None = None,
    session: Session = Depends(get_session),
) -> list[EmitenRingkas]:
    kueri = select(Emiten).where(Emiten.aktif.is_(True))
    if q:
        pola = f"%{q.lower()}%"
        kueri = kueri.where(
            func.lower(Emiten.kode).like(pola) | func.lower(Emiten.nama).like(pola)
        )
    if sektor:
        kueri = kueri.where(func.lower(Emiten.sektor) == sektor.lower())
    return [
        EmitenRingkas(kode=e.kode, nama=e.nama, sektor=e.sektor)
        for e in session.scalars(kueri.order_by(Emiten.kode))
    ]


@router.get("/{kode}", response_model=EmitenDetail)
def detail_emiten(kode: str, session: Session = Depends(get_session)) -> EmitenDetail:
    emiten = ambil_emiten(session, kode)
    jumlah = session.scalar(
        select(func.count(BeritaEmiten.id)).where(BeritaEmiten.emiten_id == emiten.id)
    )
    terakhir = session.scalar(
        select(HargaSaham)
        .where(HargaSaham.emiten_id == emiten.id)
        .order_by(HargaSaham.tanggal.desc())
        .limit(1)
    )
    return EmitenDetail(
        kode=emiten.kode,
        nama=emiten.nama,
        sektor=emiten.sektor,
        alias=emiten.daftar_alias(),
        jumlah_berita=jumlah or 0,
        harga_terakhir=terakhir.penutupan if terakhir else None,
        tanggal_harga_terakhir=terakhir.tanggal.date() if terakhir else None,
    )


@router.get("/{kode}/sentimen", response_model=DeretSentimen)
def deret_sentimen(
    kode: str,
    mulai: date | None = None,
    sampai: date | None = None,
    session: Session = Depends(get_session),
) -> DeretSentimen:
    emiten = ambil_emiten(session, kode)
    awal, akhir = rentang(mulai, sampai)
    skor = hitung_skor_harian(session, emiten.kode, awal, akhir)
    return DeretSentimen(
        kode=emiten.kode,
        mulai=awal,
        sampai=akhir,
        titik=[
            TitikSentimen(
                tanggal=s.tanggal,
                skor=s.skor,
                jumlah_berita=s.jumlah_berita,
                jumlah_positif=s.jumlah_positif,
                jumlah_netral=s.jumlah_netral,
                jumlah_negatif=s.jumlah_negatif,
            )
            for s in skor
        ],
    )


@router.get("/{kode}/harga", response_model=DeretHarga)
def deret_harga(
    kode: str,
    mulai: date | None = None,
    sampai: date | None = None,
    session: Session = Depends(get_session),
) -> DeretHarga:
    emiten = ambil_emiten(session, kode)
    awal, akhir = rentang(mulai, sampai)
    baris = session.scalars(
        select(HargaSaham)
        .where(HargaSaham.emiten_id == emiten.id)
        .order_by(HargaSaham.tanggal)
    )
    titik = [
        TitikHarga(tanggal=h.tanggal.date(), penutupan=h.penutupan, volume=h.volume)
        for h in baris
        if awal <= h.tanggal.date() <= akhir
    ]
    return DeretHarga(kode=emiten.kode, mulai=awal, sampai=akhir, titik=titik)


@router.get("/{kode}/korelasi", response_model=HasilKorelasi)
def korelasi(
    kode: str,
    mulai: date | None = None,
    sampai: date | None = None,
    lag: int = Query(0, ge=0, le=10, description="lag hari; sentimen mendahului harga"),
    maks_emiten_per_berita: int | None = Query(
        None, ge=1, le=50,
        description="buang berita yang menyebut lebih banyak emiten dari ini "
                    "(uji kepekaan terhadap artikel rekap pasar)",
    ),
    session: Session = Depends(get_session),
) -> HasilKorelasi:
    emiten = ambil_emiten(session, kode)
    awal, akhir = rentang(mulai, sampai)
    hasil = sandingkan(
        session, emiten.kode, awal, akhir, lag=lag,
        maks_emiten_per_berita=maks_emiten_per_berita,
    )

    def bungkus(k) -> Korelasi | None:
        if k is None:
            return None
        return Korelasi(
            metode=k.metode,
            koefisien=round(k.koefisien, 4),
            n=k.n,
            kekuatan=k.kekuatan(),
        )

    return HasilKorelasi(
        kode=emiten.kode,
        mulai=awal,
        sampai=akhir,
        lag=lag,
        hari_beririsan=len(hasil.titik),
        pearson=bungkus(hasil.pearson),
        spearman=bungkus(hasil.spearman),
        catatan=hasil.catatan,
        maks_emiten_per_berita=maks_emiten_per_berita,
    )


@router.get("/{kode}/keterbukaan", response_model=list[PengumumanRingkas])
def keterbukaan(
    kode: str,
    limit: int = Query(30, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[PengumumanRingkas]:
    """Pengumuman resmi BEI yang tersimpan untuk emiten ini (SRS UC-04)."""
    emiten = ambil_emiten(session, kode)
    baris = session.scalars(
        select(KeterbukaanInformasi)
        .where(KeterbukaanInformasi.emiten_id == emiten.id)
        .order_by(KeterbukaanInformasi.terbit_pada.desc().nullslast())
        .limit(limit)
    )
    return [
        PengumumanRingkas(id=k.id, judul=k.judul, url=k.url, terbit_pada=k.terbit_pada)
        for k in baris
    ]
