"""Notifikasi perubahan sentimen untuk pengguna yang sedang masuk (SRS FR-6).

Notifikasi dibuat oleh siklus terjadwal (lihat app/analitik/notifikasi.py),
bukan saat dasbor dibuka — endpoint ini hanya membaca dan menandai dibaca.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.dependensi import pengguna_aktif
from app.database import get_session
from app.models import Emiten, Notifikasi, Pengguna
from app.schemas import DaftarNotifikasi, ItemNotifikasi

router = APIRouter(prefix="/api/notifikasi", tags=["notifikasi"])


@router.get("", response_model=DaftarNotifikasi)
def daftar(
    limit: int = Query(20, ge=1, le=100),
    pengguna: Pengguna = Depends(pengguna_aktif),
    session: Session = Depends(get_session),
) -> DaftarNotifikasi:
    belum = session.scalar(
        select(func.count(Notifikasi.id)).where(
            Notifikasi.pengguna_id == pengguna.id, Notifikasi.dibaca.is_(False)
        )
    )
    baris = session.execute(
        select(Notifikasi, Emiten)
        .join(Emiten, Emiten.id == Notifikasi.emiten_id)
        .where(Notifikasi.pengguna_id == pengguna.id)
        .order_by(Notifikasi.dibuat_pada.desc(), Notifikasi.id.desc())
        .limit(limit)
    ).all()
    return DaftarNotifikasi(
        belum_dibaca=belum or 0,
        item=[
            ItemNotifikasi(
                id=n.id, kode=e.kode, nama=e.nama, tanggal=n.tanggal,
                skor_sebelum=n.skor_sebelum, skor_sesudah=n.skor_sesudah,
                jumlah_berita=n.jumlah_berita, pesan=n.pesan, dibaca=n.dibaca,
                dibuat_pada=n.dibuat_pada,
            )
            for n, e in baris
        ],
    )


@router.post("/baca")
def tandai_dibaca(
    pengguna: Pengguna = Depends(pengguna_aktif),
    session: Session = Depends(get_session),
) -> dict:
    """Menandai seluruh notifikasi milik pengguna ini sudah dibaca."""
    hasil = session.execute(
        update(Notifikasi)
        .where(Notifikasi.pengguna_id == pengguna.id, Notifikasi.dibaca.is_(False))
        .values(dibaca=True)
    )
    session.commit()
    return {"ditandai": hasil.rowcount}
