"""Siklus verifikasi: simpan pengumuman resmi lalu nilai ulang status berita.

Aturan yang dipegang:
- Keputusan analis tidak ditimpa. Berita yang statusnya sudah bukan
  BELUM_DIPERIKSA dilewati, kecuali dipaksa lewat `paksa=True`.
- Setiap perubahan status mencatat alasannya di tabel `verifikasi_berita`,
  termasuk pengumuman mana yang dipakai dan seberapa mirip judulnya. Tanpa
  jejak ini analis tidak punya cara memeriksa apakah sistemnya keliru.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Berita,
    BeritaEmiten,
    Emiten,
    KeterbukaanInformasi,
    StatusVerifikasi,
    VerifikasiBerita,
)
from app.verifikasi.pencocok import bahasa_spekulatif, cari_kecocokan, waktu_utc
from app.verifikasi.sumber import PengumumanMentah, SumberKeterbukaan


@dataclass
class HasilVerifikasi:
    pengumuman_baru: int = 0
    berita_diperiksa: int = 0
    terkonfirmasi: int = 0
    ditandai_rumor: int = 0
    dibiarkan: int = 0
    gagal: list[str] = field(default_factory=list)

    def ringkas(self) -> str:
        return (
            f"pengumuman_baru={self.pengumuman_baru} diperiksa={self.berita_diperiksa} "
            f"terkonfirmasi={self.terkonfirmasi} rumor={self.ditandai_rumor} "
            f"dibiarkan={self.dibiarkan} gagal={len(self.gagal)}"
        )


def simpan_pengumuman(
    session: Session, emiten: Emiten, daftar: list[PengumumanMentah]
) -> list[KeterbukaanInformasi]:
    """Menyimpan pengumuman yang belum ada, dikenali dari URL-nya."""
    tersimpan: list[KeterbukaanInformasi] = []
    for p in daftar:
        url = p.url or f"idx://{emiten.kode}/{abs(hash(p.judul))}"
        ada = session.scalar(
            select(KeterbukaanInformasi).where(KeterbukaanInformasi.url == url)
        )
        if ada is not None:
            tersimpan.append(ada)
            continue
        baru = KeterbukaanInformasi(
            emiten_id=emiten.id, judul=p.judul, url=url, terbit_pada=p.terbit_pada
        )
        session.add(baru)
        session.flush()
        tersimpan.append(baru)
    return tersimpan


def _ke_mentah(k: KeterbukaanInformasi, kode: str) -> PengumumanMentah:
    return PengumumanMentah(kode, k.judul, k.url, k.terbit_pada)


def verifikasi_emiten(
    session: Session,
    emiten: Emiten,
    sumber: SumberKeterbukaan,
    mulai: datetime,
    sampai: datetime,
    paksa: bool = False,
) -> HasilVerifikasi:
    hasil = HasilVerifikasi()

    mentah = sumber.ambil(emiten.kode, mulai, sampai)
    sebelum = len(list(session.scalars(
        select(KeterbukaanInformasi).where(KeterbukaanInformasi.emiten_id == emiten.id)
    )))
    tersimpan = simpan_pengumuman(session, emiten, mentah)
    sesudah = len(list(session.scalars(
        select(KeterbukaanInformasi).where(KeterbukaanInformasi.emiten_id == emiten.id)
    )))
    hasil.pengumuman_baru = sesudah - sebelum

    semua = list(session.scalars(
        select(KeterbukaanInformasi).where(KeterbukaanInformasi.emiten_id == emiten.id)
    ))
    kandidat = [_ke_mentah(k, emiten.kode) for k in semua]
    peta_id = {k.url: k.id for k in semua}

    berita_terkait = session.execute(
        select(Berita)
        .join(BeritaEmiten, BeritaEmiten.berita_id == Berita.id)
        .where(BeritaEmiten.emiten_id == emiten.id)
    ).scalars()

    for berita in berita_terkait:
        waktu = waktu_utc(berita.terbit_pada or berita.diambil_pada)
        if waktu and not (mulai <= waktu <= sampai):
            continue
        if berita.status_verifikasi is not StatusVerifikasi.BELUM_DIPERIKSA and not paksa:
            continue

        hasil.berita_diperiksa += 1
        cocok = cari_kecocokan(berita.judul, berita.terbit_pada, kandidat)

        if cocok is not None:
            berita.status_verifikasi = StatusVerifikasi.TERKONFIRMASI_RESMI
            hasil.terkonfirmasi += 1
            catat(
                session,
                berita.id,
                peta_id.get(cocok.pengumuman.url),
                StatusVerifikasi.TERKONFIRMASI_RESMI,
                cocok.kemiripan,
                "cocok dengan pengumuman resmi; kata sama: " + ", ".join(cocok.kata_sama),
            )
            continue

        teks = f"{berita.judul} {berita.ringkasan or ''}"
        if bahasa_spekulatif(teks):
            berita.status_verifikasi = StatusVerifikasi.RUMOR_BELUM_TERKONFIRMASI
            hasil.ditandai_rumor += 1
            catat(
                session,
                berita.id,
                None,
                StatusVerifikasi.RUMOR_BELUM_TERKONFIRMASI,
                0.0,
                "bahasa spekulatif dan tidak ada pengumuman resmi yang cocok",
            )
        else:
            # tidak ada bukti ke arah mana pun — biarkan analis yang menilai
            hasil.dibiarkan += 1

    session.commit()
    return hasil


def catat(
    session: Session,
    berita_id: int,
    keterbukaan_id: int | None,
    status: StatusVerifikasi,
    kemiripan: float,
    alasan: str,
) -> None:
    ada = session.scalar(
        select(VerifikasiBerita).where(
            VerifikasiBerita.berita_id == berita_id,
            VerifikasiBerita.keterbukaan_id == keterbukaan_id,
        )
    )
    if ada is not None:
        ada.status = status
        ada.kemiripan = kemiripan
        ada.alasan = alasan
        return
    session.add(
        VerifikasiBerita(
            berita_id=berita_id,
            keterbukaan_id=keterbukaan_id,
            status=status,
            kemiripan=kemiripan,
            alasan=alasan,
            otomatis=True,
        )
    )


def jalankan_verifikasi(
    session: Session,
    sumber: SumberKeterbukaan,
    hari: int = 30,
    kode: str | None = None,
    paksa: bool = False,
) -> HasilVerifikasi:
    """Menjalankan verifikasi untuk satu emiten atau seluruh emiten aktif.

    Kegagalan pada satu emiten dicatat lalu dilewati, mengikuti pola yang sama
    dengan siklus pengumpulan berita (NF-03).
    """
    sampai = datetime.now(timezone.utc)
    mulai = sampai - timedelta(days=hari)

    kueri = select(Emiten).where(Emiten.aktif.is_(True))
    if kode:
        kueri = kueri.where(Emiten.kode == kode.upper())

    total = HasilVerifikasi()
    for emiten in session.scalars(kueri):
        try:
            bagian = verifikasi_emiten(session, emiten, sumber, mulai, sampai, paksa=paksa)
        except Exception as e:  # noqa: BLE001 — satu emiten gagal, lanjut ke berikutnya
            session.rollback()
            total.gagal.append(f"{emiten.kode}: {e}")
            continue
        total.pengumuman_baru += bagian.pengumuman_baru
        total.berita_diperiksa += bagian.berita_diperiksa
        total.terkonfirmasi += bagian.terkonfirmasi
        total.ditandai_rumor += bagian.ditandai_rumor
        total.dibiarkan += bagian.dibiarkan
    return total
