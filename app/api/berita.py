"""Endpoint berita: daftar berlabel, koreksi analis, status verifikasi."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analitik.agregasi import _label_terpilih
from app.api.bantu import ambil_emiten
from app.auth.dependensi import wajib_analis
from app.database import get_session
from app.models import (
    AsalLabel,
    Pengguna,
    Berita,
    BeritaEmiten,
    Emiten,
    KeterbukaanInformasi,
    LabelSentimen,
    Sentimen,
    StatusVerifikasi,
    SumberBerita,
    VerifikasiBerita,
)
from app.schemas import (
    BeritaRingkas,
    JejakVerifikasi,
    KoreksiLabel,
    LabelRingkas,
    PengumumanRingkas,
    UbahVerifikasi,
)

router = APIRouter(prefix="/api/berita", tags=["berita"])


def _awal_hari(t: date) -> datetime:
    return datetime.combine(t, time.min, tzinfo=timezone.utc)


def _akhir_hari(t: date) -> datetime:
    return datetime.combine(t, time.max, tzinfo=timezone.utc)


def _rakit(
    session: Session,
    berita: Berita,
    sumber: SumberBerita,
    emiten_fokus: Emiten | None,
) -> BeritaRingkas:
    kaitan = list(
        session.execute(
            select(BeritaEmiten, Emiten)
            .join(Emiten, Emiten.id == BeritaEmiten.emiten_id)
            .where(BeritaEmiten.berita_id == berita.id)
        ).all()
    )
    kode_terkait = [e.kode for _, e in kaitan]

    # label ditampilkan untuk emiten yang sedang difokuskan; bila tidak ada
    # fokus, pakai emiten pertama yang punya label
    id_fokus = emiten_fokus.id if emiten_fokus else None
    labels = list(session.scalars(select(LabelSentimen).where(LabelSentimen.berita_id == berita.id)))
    if id_fokus is not None:
        labels = [l for l in labels if l.emiten_id == id_fokus]
    terpilih = _label_terpilih(labels)

    return BeritaRingkas(
        id=berita.id,
        judul=berita.judul,
        url=berita.url,
        sumber=sumber.nama,
        kredibilitas=sumber.kredibilitas,
        terbit_pada=berita.terbit_pada,
        status_verifikasi=berita.status_verifikasi,
        emiten=kode_terkait,
        label=(
            LabelRingkas(
                sentimen=terpilih.sentimen,
                keyakinan=terpilih.keyakinan,
                asal=terpilih.asal,
                versi_model=terpilih.versi_model,
            )
            if terpilih
            else None
        ),
    )


@router.get("", response_model=list[BeritaRingkas])
def daftar_berita(
    kode: str | None = Query(None, description="filter berdasarkan kode emiten"),
    status: StatusVerifikasi | None = None,
    sentimen: Sentimen | None = None,
    mulai: date | None = None,
    sampai: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> list[BeritaRingkas]:
    emiten = ambil_emiten(session, kode) if kode else None

    kueri = select(Berita, SumberBerita).join(SumberBerita, SumberBerita.id == Berita.sumber_id)
    if emiten is not None:
        kueri = kueri.join(BeritaEmiten, BeritaEmiten.berita_id == Berita.id).where(
            BeritaEmiten.emiten_id == emiten.id
        )
    if status is not None:
        kueri = kueri.where(Berita.status_verifikasi == status)
    if mulai is not None:
        kueri = kueri.where(Berita.terbit_pada >= _awal_hari(mulai))
    if sampai is not None:
        kueri = kueri.where(Berita.terbit_pada <= _akhir_hari(sampai))

    kueri = kueri.order_by(Berita.terbit_pada.desc().nullslast(), Berita.id.desc())

    hasil: list[BeritaRingkas] = []
    # filter sentimen dilakukan setelah label terpilih dihitung, karena "label
    # terpilih" bergantung pada aturan analis-menang yang tidak bisa diungkapkan
    # sebagai satu klausa WHERE
    lewati = offset
    for berita, sumber in session.execute(kueri.limit(limit + offset + 200)).all():
        item = _rakit(session, berita, sumber, emiten)
        if sentimen is not None and (item.label is None or item.label.sentimen != sentimen):
            continue
        if lewati > 0:
            lewati -= 1
            continue
        hasil.append(item)
        if len(hasil) >= limit:
            break
    return hasil


@router.get("/{berita_id}", response_model=BeritaRingkas)
def detail_berita(berita_id: int, session: Session = Depends(get_session)) -> BeritaRingkas:
    baris = session.execute(
        select(Berita, SumberBerita)
        .join(SumberBerita, SumberBerita.id == Berita.sumber_id)
        .where(Berita.id == berita_id)
    ).first()
    if baris is None:
        raise HTTPException(404, "berita tidak ditemukan")
    berita, sumber = baris
    return _rakit(session, berita, sumber, None)


@router.post("/{berita_id}/koreksi", response_model=BeritaRingkas)
def koreksi_label(
    berita_id: int,
    badan: KoreksiLabel,
    analis: Pengguna = Depends(wajib_analis),
    session: Session = Depends(get_session),
) -> BeritaRingkas:
    """Koreksi manual analis (SRS UC-05).

    Label model TIDAK ditimpa. Koreksi disimpan sebagai label baru dengan asal
    ANALIS, sehingga selisih antara model dan analis tetap bisa dihitung dan
    dipakai sebagai data pelatihan ulang.
    """
    baris = session.execute(
        select(Berita, SumberBerita)
        .join(SumberBerita, SumberBerita.id == Berita.sumber_id)
        .where(Berita.id == berita_id)
    ).first()
    if baris is None:
        raise HTTPException(404, "berita tidak ditemukan")
    berita, sumber = baris

    emiten = ambil_emiten(session, badan.kode_emiten)
    terkait = session.scalar(
        select(BeritaEmiten).where(
            BeritaEmiten.berita_id == berita.id, BeritaEmiten.emiten_id == emiten.id
        )
    )
    if terkait is None:
        raise HTTPException(400, f"berita ini tidak terkait emiten {emiten.kode}")

    lama = session.scalar(
        select(LabelSentimen).where(
            LabelSentimen.berita_id == berita.id,
            LabelSentimen.emiten_id == emiten.id,
            LabelSentimen.asal == AsalLabel.ANALIS,
            LabelSentimen.versi_model == "-",
        )
    )
    if lama is not None:
        lama.sentimen = badan.sentimen
        lama.keyakinan = 1.0
    else:
        session.add(
            LabelSentimen(
                berita_id=berita.id,
                emiten_id=emiten.id,
                sentimen=badan.sentimen,
                keyakinan=1.0,
                asal=AsalLabel.ANALIS,
            )
        )
    session.commit()
    return _rakit(session, berita, sumber, emiten)


@router.post("/{berita_id}/verifikasi", response_model=BeritaRingkas)
def ubah_verifikasi(
    berita_id: int,
    badan: UbahVerifikasi,
    analis: Pengguna = Depends(wajib_analis),
    session: Session = Depends(get_session),
) -> BeritaRingkas:
    """Menandai berita terkonfirmasi resmi atau masih rumor (SRS UC-04)."""
    baris = session.execute(
        select(Berita, SumberBerita)
        .join(SumberBerita, SumberBerita.id == Berita.sumber_id)
        .where(Berita.id == berita_id)
    ).first()
    if baris is None:
        raise HTTPException(404, "berita tidak ditemukan")
    berita, sumber = baris
    berita.status_verifikasi = badan.status
    # keputusan manual ikut dicatat, supaya jejaknya sejajar dengan yang otomatis
    session.add(
        VerifikasiBerita(
            berita_id=berita.id,
            keterbukaan_id=None,
            status=badan.status,
            kemiripan=0.0,
            alasan=f"ditetapkan manual oleh {analis.nama}",
            otomatis=False,
        )
    )
    session.commit()
    return _rakit(session, berita, sumber, None)


@router.get("/{berita_id}/jejak", response_model=list[JejakVerifikasi])
def jejak_verifikasi(
    berita_id: int, session: Session = Depends(get_session)
) -> list[JejakVerifikasi]:
    """Riwayat kenapa berita ini diberi status verifikasinya (SRS UC-04)."""
    if session.scalar(select(Berita.id).where(Berita.id == berita_id)) is None:
        raise HTTPException(404, "berita tidak ditemukan")

    keluar: list[JejakVerifikasi] = []
    for v in session.scalars(
        select(VerifikasiBerita)
        .where(VerifikasiBerita.berita_id == berita_id)
        .order_by(VerifikasiBerita.dibuat_pada.desc())
    ):
        pengumuman = None
        if v.keterbukaan_id:
            k = session.get(KeterbukaanInformasi, v.keterbukaan_id)
            if k is not None:
                pengumuman = PengumumanRingkas(
                    id=k.id, judul=k.judul, url=k.url, terbit_pada=k.terbit_pada
                )
        keluar.append(
            JejakVerifikasi(
                status=v.status,
                kemiripan=v.kemiripan,
                alasan=v.alasan,
                otomatis=v.otomatis,
                dibuat_pada=v.dibuat_pada,
                pengumuman=pengumuman,
            )
        )
    return keluar
