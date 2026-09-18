"""Endpoint ringkasan dan daftar sumber — isi halaman depan dasbor."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Berita, BeritaEmiten, Emiten, HargaSaham, LabelSentimen, SumberBerita
from app.schemas import RentangData, Ringkasan, SumberRingkas

router = APIRouter(prefix="/api", tags=["sistem"])


@router.get("/sehat")
def sehat() -> dict:
    return {"status": "ok"}


@router.get("/sumber", response_model=list[SumberRingkas])
def daftar_sumber(session: Session = Depends(get_session)) -> list[SumberRingkas]:
    return [
        SumberRingkas(
            id=s.id,
            nama=s.nama,
            domain=s.domain,
            kredibilitas=s.kredibilitas,
            aktif=s.aktif,
        )
        for s in session.scalars(select(SumberBerita).order_by(SumberBerita.nama))
    ]


@router.get("/ringkasan", response_model=Ringkasan)
def ringkasan(session: Session = Depends(get_session)) -> Ringkasan:
    teraktif = session.execute(
        select(Emiten.kode, Emiten.nama, func.count(BeritaEmiten.id).label("jumlah"))
        .join(BeritaEmiten, BeritaEmiten.emiten_id == Emiten.id)
        .where(Emiten.aktif.is_(True))
        .group_by(Emiten.id)
        .order_by(func.count(BeritaEmiten.id).desc())
        .limit(8)
    ).all()

    return Ringkasan(
        # hanya yang aktif: emiten dan sumber nonaktif tidak lagi dipantau,
        # jadi memasukkannya ke ringkasan akan melaporkan cakupan yang lebih
        # besar daripada yang sebenarnya berjalan
        jumlah_emiten=session.scalar(
            select(func.count(Emiten.id)).where(Emiten.aktif.is_(True))
        ) or 0,
        jumlah_sumber=session.scalar(
            select(func.count(SumberBerita.id)).where(SumberBerita.aktif.is_(True))
        ) or 0,
        jumlah_berita=session.scalar(select(func.count(Berita.id))) or 0,
        jumlah_berlabel=session.scalar(
            select(func.count(func.distinct(LabelSentimen.berita_id)))
        ) or 0,
        jumlah_belum_diklasifikasi=session.scalar(
            select(func.count(Berita.id)).where(Berita.sudah_diklasifikasi.is_(False))
        ) or 0,
        berita_terakhir=session.scalar(select(func.max(Berita.terbit_pada))),
        emiten_teraktif=[
            {"kode": k, "nama": n, "jumlah_berita": j} for k, n, j in teraktif
        ],
    )


@router.get("/rentang-data", response_model=RentangData)
def rentang_data(session: Session = Depends(get_session)) -> RentangData:
    """Tanggal paling awal dan paling akhir yang benar-benar ada datanya.

    Dipakai tombol "seluruh data" di dasbor. Rentangnya dihitung dari isi basis
    data, bukan ditebak: data harga bisa mundur berbulan-bulan sementara data
    sentimen baru mulai terkumpul, dan keduanya perlu dilaporkan apa adanya.
    """
    berita_awal = session.scalar(select(func.min(Berita.terbit_pada)))
    berita_akhir = session.scalar(select(func.max(Berita.terbit_pada)))
    harga_awal = session.scalar(select(func.min(HargaSaham.tanggal)))
    harga_akhir = session.scalar(select(func.max(HargaSaham.tanggal)))

    semua_awal = [d for d in (berita_awal, harga_awal) if d]
    semua_akhir = [d for d in (berita_akhir, harga_akhir) if d]

    return RentangData(
        berita_mulai=berita_awal.date() if berita_awal else None,
        berita_sampai=berita_akhir.date() if berita_akhir else None,
        harga_mulai=harga_awal.date() if harga_awal else None,
        harga_sampai=harga_akhir.date() if harga_akhir else None,
        mulai=min(semua_awal).date() if semua_awal else None,
        sampai=max(semua_akhir).date() if semua_akhir else None,
    )
