"""Uji penyelarasan data awal.

Yang diuji di sini bukan pengisian pertama kali — itu jarang salah — melainkan
penyelarasan BERULANG. Versi sebelumnya melewati baris yang sudah ada, sehingga
perbaikan alias di `data/lq45.py` tidak pernah sampai ke basis data dan
pencocokan diam-diam tetap memakai alias lama.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, Emiten, Kredibilitas, SumberBerita
from data.lq45 import EMITEN_AWAL, SUMBER_AWAL
from scripts.init_db import nonaktifkan_sumber, selaraskan_emiten, selaraskan_sumber


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False, future=True)()
    yield s
    s.close()


def test_pengisian_pertama(db):
    hasil = selaraskan_emiten(db)
    db.commit()
    assert hasil.baru == len(EMITEN_AWAL)
    assert hasil.diperbarui == 0


def test_dijalankan_dua_kali_tidak_menggandakan(db):
    selaraskan_emiten(db)
    db.commit()
    kedua = selaraskan_emiten(db)
    db.commit()
    assert kedua.baru == 0 and kedua.diperbarui == 0
    assert len(list(db.scalars(select(Emiten)))) == len(EMITEN_AWAL)


def test_alias_lama_diperbarui(db):
    """Inti perbaikannya: alias yang sudah telanjur tersimpan harus ikut
    diperbaiki, bukan dibiarkan."""
    kode, nama, sektor, _ = EMITEN_AWAL[0]
    db.add(Emiten(kode=kode, nama=nama, sektor=sektor, alias="Alias|Usang"))
    db.commit()

    hasil = selaraskan_emiten(db)
    db.commit()

    assert hasil.diperbarui == 1
    assert any(kode in b for b in hasil.alias_berubah)
    assert db.scalar(select(Emiten).where(Emiten.kode == kode)).alias != "Alias|Usang"


def test_nama_dan_sektor_ikut_diperbarui(db):
    kode, _, _, alias = EMITEN_AWAL[0]
    db.add(Emiten(kode=kode, nama="Nama Lama", sektor="Sektor Lama", alias=alias))
    db.commit()

    selaraskan_emiten(db)
    db.commit()

    e = db.scalar(select(Emiten).where(Emiten.kode == kode))
    assert e.nama == EMITEN_AWAL[0][1]
    assert e.sektor == EMITEN_AWAL[0][2]


def test_perubahan_nama_saja_tidak_dilaporkan_sebagai_alias(db):
    kode, _, sektor, alias = EMITEN_AWAL[0]
    db.add(Emiten(kode=kode, nama="Nama Lama", sektor=sektor, alias=alias))
    db.commit()
    hasil = selaraskan_emiten(db)
    assert hasil.diperbarui == 1
    assert hasil.alias_berubah == []


def test_sumber_diperbarui_dan_diaktifkan_kembali(db):
    nama, domain, rss, kredibilitas = SUMBER_AWAL[0]
    db.add(SumberBerita(nama=nama, domain=domain, url_rss="https://lama/rss",
                        kredibilitas=Kredibilitas(kredibilitas), aktif=False))
    db.commit()

    hasil = selaraskan_sumber(db)
    db.commit()

    s = db.scalar(select(SumberBerita).where(SumberBerita.domain == domain))
    assert hasil.diperbarui == 1
    assert s.url_rss == rss
    assert s.aktif is True


def test_nonaktifkan_sumber_hanya_sekali(db):
    selaraskan_sumber(db)
    db.commit()
    pertama = nonaktifkan_sumber(db)
    db.commit()
    kedua = nonaktifkan_sumber(db)
    assert kedua == []
    assert isinstance(pertama, list)


def test_emiten_di_luar_daftar_dinonaktifkan_bukan_dihapus(db):
    """Berita dan harga emiten yang keluar LQ45 tetap punya arti sebagai catatan
    periode sebelumnya, dan tidak bisa diambil ulang kalau dibuang."""
    from scripts.init_db import nonaktifkan_emiten_luar_daftar

    selaraskan_emiten(db)
    db.add(Emiten(kode="ZZZZ", nama="Emiten Periode Lalu Tbk", sektor="Lain"))
    db.commit()

    pesan = nonaktifkan_emiten_luar_daftar(db)
    db.commit()

    assert len(pesan) == 1 and "ZZZZ" in pesan[0]
    lama = db.scalar(select(Emiten).where(Emiten.kode == "ZZZZ"))
    assert lama is not None          # tidak dihapus
    assert lama.aktif is False       # tapi tidak lagi dicocokkan


def test_emiten_dalam_daftar_tidak_ikut_dinonaktifkan(db):
    from scripts.init_db import nonaktifkan_emiten_luar_daftar

    selaraskan_emiten(db)
    db.commit()
    assert nonaktifkan_emiten_luar_daftar(db) == []


def test_nonaktifkan_emiten_hanya_sekali(db):
    from scripts.init_db import nonaktifkan_emiten_luar_daftar

    selaraskan_emiten(db)
    db.add(Emiten(kode="ZZZZ", nama="Emiten Periode Lalu Tbk"))
    db.commit()
    nonaktifkan_emiten_luar_daftar(db)
    db.commit()
    assert nonaktifkan_emiten_luar_daftar(db) == []
