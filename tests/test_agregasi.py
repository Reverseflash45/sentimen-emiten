"""Uji agregasi skor sentimen harian."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.analitik.agregasi import hitung_skor_harian
from app.models import (
    AsalLabel,
    Base,
    Berita,
    BeritaEmiten,
    Emiten,
    Kredibilitas,
    LabelSentimen,
    Sentimen,
    SumberBerita,
)

HARI = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add(Emiten(kode="BBCA", nama="Bank Central Asia Tbk"))
    s.add(SumberBerita(nama="Tepercaya", domain="a.test",
                       kredibilitas=Kredibilitas.TERVERIFIKASI_DEWAN_PERS))
    s.add(SumberBerita(nama="Abal", domain="b.test",
                       kredibilitas=Kredibilitas.TIDAK_TERVERIFIKASI))
    s.commit()
    yield s
    s.close()


def tambah(db, judul, sentimen, keyakinan=1.0, sumber_id=1, geser_hari=0,
           asal=AsalLabel.MODEL, urutan=0):
    berita = Berita(
        sumber_id=sumber_id, judul=judul, url=f"https://x.test/{judul}",
        sidik_jari=judul, terbit_pada=HARI + timedelta(days=geser_hari),
    )
    db.add(berita)
    db.flush()
    db.add(BeritaEmiten(berita_id=berita.id, emiten_id=1, cara_cocok="kode"))
    db.add(LabelSentimen(
        berita_id=berita.id, emiten_id=1, sentimen=sentimen,
        keyakinan=keyakinan, asal=asal,
        versi_model=f"v{urutan}",
        dibuat_pada=HARI + timedelta(minutes=urutan),
    ))
    db.commit()
    return berita


def test_satu_berita_positif(db):
    tambah(db, "laba naik", Sentimen.POSITIF)
    hasil = hitung_skor_harian(db, "BBCA", date(2026, 9, 1), date(2026, 9, 30))
    assert len(hasil) == 1
    assert hasil[0].skor == 1.0
    assert hasil[0].jumlah_positif == 1


def test_positif_dan_negatif_saling_meniadakan(db):
    tambah(db, "laba naik", Sentimen.POSITIF)
    tambah(db, "rugi besar", Sentimen.NEGATIF)
    hasil = hitung_skor_harian(db, "BBCA", date(2026, 9, 1), date(2026, 9, 30))
    assert hasil[0].skor == 0.0
    assert hasil[0].jumlah_berita == 2


def test_keyakinan_rendah_berpengaruh_lebih_kecil(db):
    tambah(db, "jelas positif", Sentimen.POSITIF, keyakinan=1.0)
    tambah(db, "ragu negatif", Sentimen.NEGATIF, keyakinan=0.2)
    hasil = hitung_skor_harian(db, "BBCA", date(2026, 9, 1), date(2026, 9, 30))
    assert hasil[0].skor > 0.5   # yang yakin menang


def test_sumber_tak_terverifikasi_ditimbang_lebih_rendah(db):
    tambah(db, "positif tepercaya", Sentimen.POSITIF, sumber_id=1)
    tambah(db, "negatif abal", Sentimen.NEGATIF, sumber_id=2)
    hasil = hitung_skor_harian(db, "BBCA", date(2026, 9, 1), date(2026, 9, 30))
    assert hasil[0].skor > 0     # 1.0 lawan 0.4


def test_koreksi_analis_mengalahkan_label_model(db):
    berita = tambah(db, "ambigu", Sentimen.POSITIF, urutan=1)
    db.add(LabelSentimen(
        berita_id=berita.id, emiten_id=1, sentimen=Sentimen.NEGATIF,
        keyakinan=0.3, asal=AsalLabel.ANALIS, versi_model="analis",
        dibuat_pada=HARI,
    ))
    db.commit()
    hasil = hitung_skor_harian(db, "BBCA", date(2026, 9, 1), date(2026, 9, 30))
    # label analis dipakai meski keyakinannya rendah dan dibuat lebih dulu
    assert hasil[0].skor == -1.0


def test_berita_tanpa_label_tidak_dihitung(db):
    berita = Berita(sumber_id=1, judul="belum diklasifikasi",
                    url="https://x.test/z", sidik_jari="z", terbit_pada=HARI)
    db.add(berita)
    db.flush()
    db.add(BeritaEmiten(berita_id=berita.id, emiten_id=1, cara_cocok="kode"))
    db.commit()
    assert hitung_skor_harian(db, "BBCA", date(2026, 9, 1), date(2026, 9, 30)) == []


def test_dikelompokkan_per_tanggal(db):
    tambah(db, "hari satu", Sentimen.POSITIF, geser_hari=0)
    tambah(db, "hari dua", Sentimen.NEGATIF, geser_hari=1)
    hasil = hitung_skor_harian(db, "BBCA", date(2026, 9, 1), date(2026, 9, 30))
    assert [h.tanggal for h in hasil] == [date(2026, 9, 10), date(2026, 9, 11)]


def test_di_luar_rentang_tidak_ikut(db):
    tambah(db, "jauh", Sentimen.POSITIF, geser_hari=60)
    assert hitung_skor_harian(db, "BBCA", date(2026, 9, 1), date(2026, 9, 30)) == []


def test_emiten_tidak_dikenal(db):
    assert hitung_skor_harian(db, "XXXX", date(2026, 9, 1), date(2026, 9, 30)) == []
