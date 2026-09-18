"""Watchlist pengguna (SRS UC-02).

Setiap permintaan hanya menyentuh watchlist milik pengguna yang sedang masuk —
id pengguna diambil dari token, tidak pernah dari parameter permintaan.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analitik.agregasi import hitung_skor_harian
from app.api.bantu import ambil_emiten
from app.auth.dependensi import pengguna_aktif
from app.database import get_session
from app.models import Berita, BeritaEmiten, Emiten, HargaSaham, Pengguna, Watchlist
from app.schemas import ItemWatchlist, TambahWatchlist

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

HARI_RINGKASAN = 7


def _rakit(session: Session, w: Watchlist, emiten: Emiten) -> ItemWatchlist:
    sampai = date.today()
    mulai = sampai - timedelta(days=HARI_RINGKASAN)

    skor = hitung_skor_harian(session, emiten.kode, mulai, sampai)
    terakhir = skor[-1] if skor else None

    jumlah = session.scalar(
        select(func.count(Berita.id))
        .join(BeritaEmiten, BeritaEmiten.berita_id == Berita.id)
        .where(BeritaEmiten.emiten_id == emiten.id, Berita.terbit_pada.is_not(None))
    )

    harga = session.scalar(
        select(HargaSaham)
        .where(HargaSaham.emiten_id == emiten.id)
        .order_by(HargaSaham.tanggal.desc())
        .limit(1)
    )

    return ItemWatchlist(
        kode=emiten.kode,
        nama=emiten.nama,
        sektor=emiten.sektor,
        catatan=w.catatan,
        skor_terakhir=terakhir.skor if terakhir else None,
        tanggal_skor=terakhir.tanggal if terakhir else None,
        berita_7_hari=sum(s.jumlah_berita for s in skor),
        harga_terakhir=harga.penutupan if harga else None,
    )


@router.get("", response_model=list[ItemWatchlist])
def daftar(
    pengguna: Pengguna = Depends(pengguna_aktif),
    session: Session = Depends(get_session),
) -> list[ItemWatchlist]:
    baris = session.execute(
        select(Watchlist, Emiten)
        .join(Emiten, Emiten.id == Watchlist.emiten_id)
        .where(Watchlist.pengguna_id == pengguna.id)
        .order_by(Emiten.kode)
    ).all()
    return [_rakit(session, w, e) for w, e in baris]


@router.post("", response_model=ItemWatchlist, status_code=status.HTTP_201_CREATED)
def tambah(
    badan: TambahWatchlist,
    pengguna: Pengguna = Depends(pengguna_aktif),
    session: Session = Depends(get_session),
) -> ItemWatchlist:
    emiten = ambil_emiten(session, badan.kode_emiten)
    ada = session.scalar(
        select(Watchlist).where(
            Watchlist.pengguna_id == pengguna.id, Watchlist.emiten_id == emiten.id
        )
    )
    if ada is not None:
        # menambahkan yang sudah ada bukan galat — catatannya saja yang diperbarui
        if badan.catatan is not None:
            ada.catatan = badan.catatan
            session.commit()
        return _rakit(session, ada, emiten)

    baru = Watchlist(pengguna_id=pengguna.id, emiten_id=emiten.id, catatan=badan.catatan)
    session.add(baru)
    session.commit()
    return _rakit(session, baru, emiten)


@router.delete("/{kode}")
def hapus(
    kode: str,
    pengguna: Pengguna = Depends(pengguna_aktif),
    session: Session = Depends(get_session),
) -> dict:
    emiten = ambil_emiten(session, kode)
    baris = session.scalar(
        select(Watchlist).where(
            Watchlist.pengguna_id == pengguna.id, Watchlist.emiten_id == emiten.id
        )
    )
    if baris is None:
        raise HTTPException(404, f"{emiten.kode} tidak ada di watchlist")
    session.delete(baris)
    session.commit()
    return {"dihapus": emiten.kode}
