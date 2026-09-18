"""Siklus pengumpulan berita: ambil → simpan → petakan ke emiten.

Kegagalan pada satu sumber dicatat lalu dilewati, tidak menghentikan sumber
lain (NF-03).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.matcher import cocokkan
from app.ingest.rss import ArtikelMentah, ambil_feed
from app.models import Berita, BeritaEmiten, Emiten, LogPengumpulan, SumberBerita


@dataclass
class HasilSiklus:
    ditemukan: int = 0
    baru: int = 0
    duplikat: int = 0
    terpetakan: int = 0
    tanpa_emiten: int = 0
    gagal: list[str] = field(default_factory=list)

    def ringkas(self) -> str:
        return (
            f"ditemukan={self.ditemukan} baru={self.baru} duplikat={self.duplikat} "
            f"terpetakan={self.terpetakan} tanpa_emiten={self.tanpa_emiten} "
            f"sumber_gagal={len(self.gagal)}"
        )


def peta_emiten(session: Session) -> dict[str, list[str]]:
    """Kode emiten → daftar nama dan aliasnya."""
    hasil: dict[str, list[str]] = {}
    for e in session.scalars(select(Emiten).where(Emiten.aktif.is_(True))):
        hasil[e.kode] = [e.nama, *e.daftar_alias()]
    return hasil


def simpan_artikel(
    session: Session,
    sumber: SumberBerita,
    artikel: ArtikelMentah,
    daftar_emiten: dict[str, list[str]],
    hasil: HasilSiklus,
) -> None:
    """Menyimpan satu artikel bila belum ada, lalu memetakannya ke emiten."""
    sudah_ada = session.scalar(
        select(Berita).where(
            (Berita.url == artikel.url) | (Berita.sidik_jari == artikel.sidik_jari)
        )
    )
    if sudah_ada:
        hasil.duplikat += 1
        return

    berita = Berita(
        sumber_id=sumber.id,
        judul=artikel.judul,
        ringkasan=artikel.ringkasan or None,
        url=artikel.url,
        sidik_jari=artikel.sidik_jari,
        terbit_pada=artikel.terbit_pada,
    )
    session.add(berita)
    session.flush()  # perlu id untuk relasi

    teks = f"{artikel.judul}. {artikel.ringkasan or ''}"
    kecocokan = cocokkan(teks, daftar_emiten)
    if not kecocokan:
        hasil.tanpa_emiten += 1
    for k in kecocokan:
        emiten = session.scalar(select(Emiten).where(Emiten.kode == k.kode))
        if emiten is None:
            continue
        session.add(
            BeritaEmiten(
                berita_id=berita.id,
                emiten_id=emiten.id,
                cara_cocok=k.cara,
                kutipan=k.kutipan,
            )
        )
        hasil.terpetakan += 1

    hasil.baru += 1


def jalankan_siklus(session: Session, batas_per_sumber: int | None = None) -> HasilSiklus:
    """Menjalankan satu siklus pengumpulan untuk semua sumber aktif."""
    hasil = HasilSiklus()
    daftar_emiten = peta_emiten(session)
    sumber_aktif = list(
        session.scalars(
            select(SumberBerita).where(
                SumberBerita.aktif.is_(True), SumberBerita.url_rss.is_not(None)
            )
        )
    )

    for sumber in sumber_aktif:
        log = LogPengumpulan(sumber_id=sumber.id)
        session.add(log)
        session.flush()
        try:
            artikel = ambil_feed(sumber.url_rss, batas_per_sumber)
            log.jumlah_ditemukan = len(artikel)
            hasil.ditemukan += len(artikel)

            sebelum = hasil.baru
            for a in artikel:
                simpan_artikel(session, sumber, a, daftar_emiten, hasil)
            log.jumlah_baru = hasil.baru - sebelum
            log.berhasil = True
        except Exception as exc:  # noqa: BLE001 — sengaja luas, satu sumber tidak boleh menjatuhkan siklus
            log.berhasil = False
            log.pesan = f"{type(exc).__name__}: {exc}"
            hasil.gagal.append(f"{sumber.nama}: {exc}")
        finally:
            log.selesai_pada = datetime.now(timezone.utc)
            session.commit()

    return hasil
