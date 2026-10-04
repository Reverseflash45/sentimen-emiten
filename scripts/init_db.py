"""Membuat tabel dan menyelaraskan data emiten serta sumber berita.

Jalankan:  python -m scripts.init_db
           python -m scripts.init_db --hanya-skema   # migrasi skema saja
Aman diulang — data yang sudah ada diperbarui, bukan diduplikasi.

`create_all` hanya membuat tabel yang belum ada; ia tidak menambah kolom pada
tabel lama maupun nilai baru pada tipe ENUM PostgreSQL. Perubahan semacam itu
ditangani `selaraskan_skema`, dengan perintah yang aman dijalankan berulang.

Penting: nama, sektor, dan alias emiten yang sudah ada IKUT DIPERBARUI dari
`data/lq45.py`. Sebelumnya baris yang sudah ada dilewati begitu saja, sehingga
perbaikan alias di berkas itu tidak pernah sampai ke basis data — pencocokan
tetap memakai alias lama tanpa tanda apa pun bahwa perbaikannya tidak berlaku.
Kesalahan seperti itu sulit disadari justru karena berkas sumbernya terlihat
sudah benar.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Base, Emiten, Kredibilitas, SumberBerita
from data.lq45 import EMITEN_AWAL, SUMBER_AWAL, SUMBER_NONAKTIF


@dataclass
class HasilSelaras:
    baru: int = 0
    diperbarui: int = 0
    alias_berubah: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.alias_berubah is None:
            self.alias_berubah = []


def selaraskan_emiten(session: Session) -> HasilSelaras:
    hasil = HasilSelaras()
    for kode, nama, sektor, alias in EMITEN_AWAL:
        ada = session.scalar(select(Emiten).where(Emiten.kode == kode))
        if ada is None:
            session.add(Emiten(kode=kode, nama=nama, sektor=sektor, alias=alias))
            hasil.baru += 1
            continue
        if (ada.nama, ada.sektor, ada.alias) == (nama, sektor, alias):
            continue
        if ada.alias != alias:
            hasil.alias_berubah.append(f"{kode}  {ada.alias!r} -> {alias!r}")
        ada.nama, ada.sektor, ada.alias = nama, sektor, alias
        hasil.diperbarui += 1
    return hasil


def selaraskan_sumber(session: Session) -> HasilSelaras:
    hasil = HasilSelaras()
    for nama, domain, rss, kredibilitas in SUMBER_AWAL:
        ada = session.scalar(select(SumberBerita).where(SumberBerita.domain == domain))
        if ada is None:
            session.add(
                SumberBerita(
                    nama=nama, domain=domain, url_rss=rss,
                    kredibilitas=Kredibilitas(kredibilitas),
                )
            )
            hasil.baru += 1
            continue
        # sumber yang muncul kembali di SUMBER_AWAL dianggap diaktifkan lagi
        if (ada.nama, ada.url_rss, ada.kredibilitas, ada.aktif) == (
            nama, rss, Kredibilitas(kredibilitas), True
        ):
            continue
        ada.nama = nama
        ada.url_rss = rss
        ada.kredibilitas = Kredibilitas(kredibilitas)
        ada.aktif = True
        hasil.diperbarui += 1
    return hasil


def nonaktifkan_emiten_luar_daftar(session: Session) -> list[str]:
    """Menonaktifkan emiten yang tidak lagi ada di EMITEN_AWAL.

    Barisnya TIDAK dihapus. Berita dan harga yang sudah terkumpul untuk emiten
    itu tetap punya arti sebagai catatan periode sebelumnya, dan menghapusnya
    berarti membuang data yang tidak bisa diambil ulang. Yang berubah hanya
    satu: emiten nonaktif tidak lagi ikut dicocokkan pada siklus berikutnya.
    """
    dipantau = {kode for kode, *_ in EMITEN_AWAL}
    pesan: list[str] = []
    for emiten in session.scalars(select(Emiten).where(Emiten.aktif.is_(True))):
        if emiten.kode in dipantau:
            continue
        emiten.aktif = False
        pesan.append(f"{emiten.kode} — di luar komposisi LQ45 periode ini")
    return pesan


def nonaktifkan_sumber(session: Session) -> list[str]:
    """Sumber yang dinonaktifkan tidak dihapus — beritanya yang sudah terkumpul
    tetap perlu barisnya untuk diketahui kredibilitasnya."""
    pesan: list[str] = []
    for domain, alasan in SUMBER_NONAKTIF:
        sumber = session.scalar(select(SumberBerita).where(SumberBerita.domain == domain))
        if sumber is None or not sumber.aktif:
            continue
        sumber.aktif = False
        pesan.append(f"{sumber.nama} — {alasan}")
    return pesan


def selaraskan_skema() -> list[str]:
    """Perubahan skema yang tidak bisa dilakukan create_all."""
    pesan: list[str] = []
    Base.metadata.create_all(engine)
    kolom_watchlist = {k["name"] for k in inspect(engine).get_columns("watchlist")}
    kolom_pengguna = {k["name"] for k in inspect(engine).get_columns("pengguna")}
    with engine.begin() as kon:
        if engine.dialect.name == "postgresql":
            # SQLAlchemy menyimpan NAMA anggota enum (ADMIN), bukan nilainya
            ada = kon.execute(text(
                "select 1 from pg_enum e join pg_type t on t.oid = e.enumtypid "
                "where t.typname = 'peran' and e.enumlabel = 'ADMIN'"
            )).first()
            if ada is None:
                kon.execute(text("ALTER TYPE peran ADD VALUE IF NOT EXISTS 'ADMIN'"))
                pesan.append("enum peran: + ADMIN")
        if "ambang" not in kolom_watchlist:
            kon.execute(text("ALTER TABLE watchlist ADD COLUMN ambang FLOAT NOT NULL DEFAULT 0.3"))
            pesan.append("watchlist: + kolom ambang")
        if "kirim_email" not in kolom_pengguna:
            kon.execute(text("ALTER TABLE pengguna ADD COLUMN kirim_email BOOLEAN NOT NULL DEFAULT FALSE"))
            pesan.append("pengguna: + kolom kirim_email")
    return pesan


def main() -> None:
    p = argparse.ArgumentParser(description="Membuat tabel dan menyelaraskan data awal")
    p.add_argument("--hanya-skema", action="store_true",
                   help="hanya migrasi skema; daftar emiten dan sumber tidak disentuh")
    a = p.parse_args()

    for baris in selaraskan_skema():
        print(f"Skema   : {baris}")
    if a.hanya_skema:
        return
    with SessionLocal() as session:
        emiten = selaraskan_emiten(session)
        sumber = selaraskan_sumber(session)
        emiten_mati = nonaktifkan_emiten_luar_daftar(session)
        dimatikan = nonaktifkan_sumber(session)
        session.commit()

        for baris in emiten.alias_berubah:
            print(f"Alias   : {baris}")
        for baris in emiten_mati:
            print(f"Nonaktif: {baris}")
        for baris in dimatikan:
            print(f"Nonaktif: {baris}")

        total_emiten = len(list(session.scalars(select(Emiten))))
        emiten_aktif = len(list(session.scalars(
            select(Emiten).where(Emiten.aktif.is_(True))
        )))
        total_sumber = len(list(session.scalars(select(SumberBerita))))
        total_aktif = len(list(session.scalars(
            select(SumberBerita).where(SumberBerita.aktif.is_(True))
        )))

        print(f"Emiten  : +{emiten.baru} baru, {emiten.diperbarui} diperbarui, "
              f"{emiten_aktif} aktif dari {total_emiten}")
        print(f"Sumber  : +{sumber.baru} baru, {sumber.diperbarui} diperbarui, "
              f"{total_aktif} aktif dari {total_sumber}")

        if emiten_mati:
            print(
                f"\n{len(emiten_mati)} emiten dinonaktifkan. Berita dan harganya\n"
                "tetap tersimpan, tapi tidak lagi ikut dicocokkan."
            )
        if emiten.alias_berubah or emiten_mati:
            print(
                "\nDaftar emiten berubah. Pemetaan lama dibuat memakai daftar lama:\n"
                "  python -m scripts.bersihkan_pemetaan --lihat"
            )
        print("Basis data siap.")


if __name__ == "__main__":
    main()
