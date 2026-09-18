"""Uji penyandingan sentimen dan harga."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.analitik.agregasi import SkorHarian
from app.analitik.korelasi import gabungkan, sandingkan
from app.models import (
    Base,
    Berita,
    BeritaEmiten,
    Emiten,
    HargaSaham,
    Kredibilitas,
    LabelSentimen,
    Sentimen,
    SumberBerita,
)

MULAI = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add(Emiten(kode="BBCA", nama="Bank Central Asia Tbk"))
    s.add(SumberBerita(nama="Uji", domain="u.test",
                       kredibilitas=Kredibilitas.TERVERIFIKASI_DEWAN_PERS))
    s.commit()
    yield s
    s.close()


def isi(db, harian: list[tuple[Sentimen, float]]):
    """harian = daftar (sentimen, harga penutupan) per hari berturut-turut."""
    for i, (sent, tutup) in enumerate(harian):
        waktu = MULAI + timedelta(days=i)
        berita = Berita(sumber_id=1, judul=f"berita {i}", url=f"https://u.test/{i}",
                        sidik_jari=f"f{i}", terbit_pada=waktu)
        db.add(berita)
        db.flush()
        db.add(BeritaEmiten(berita_id=berita.id, emiten_id=1, cara_cocok="kode"))
        db.add(LabelSentimen(berita_id=berita.id, emiten_id=1, sentimen=sent,
                             keyakinan=1.0, dibuat_pada=waktu))
        db.add(HargaSaham(emiten_id=1, tanggal=waktu, penutupan=tutup))
    db.commit()


def test_gabung_hanya_tanggal_yang_punya_kedua_data():
    skor = [SkorHarian(date(2026, 9, 1), 0.5, 1, 1, 0, 0),
            SkorHarian(date(2026, 9, 2), -0.5, 1, 0, 0, 1)]
    harga = {date(2026, 9, 1): 100.0}  # 2 September libur bursa
    titik = gabungkan(skor, harga)
    assert len(titik) == 1
    assert titik[0].tanggal == date(2026, 9, 1)


def test_sentimen_naik_bersama_harga_memberi_korelasi_positif(db):
    isi(db, [
        (Sentimen.NEGATIF, 100.0),
        (Sentimen.NEGATIF, 98.0),
        (Sentimen.NETRAL, 99.0),
        (Sentimen.POSITIF, 103.0),
        (Sentimen.POSITIF, 108.0),
        (Sentimen.POSITIF, 114.0),
    ])
    hasil = sandingkan(db, "BBCA", date(2026, 9, 1), date(2026, 9, 30))
    assert hasil.catatan is None
    assert hasil.pearson.koefisien > 0.5
    assert hasil.spearman is not None


def test_data_terlalu_sedikit_memberi_catatan_bukan_error(db):
    isi(db, [(Sentimen.POSITIF, 100.0), (Sentimen.POSITIF, 101.0)])
    hasil = sandingkan(db, "BBCA", date(2026, 9, 1), date(2026, 9, 30))
    assert hasil.pearson is None
    assert "belum cukup" in hasil.catatan


def test_lag_melebihi_data_ditolak_dengan_catatan(db):
    isi(db, [
        (Sentimen.POSITIF, 100.0), (Sentimen.POSITIF, 101.0),
        (Sentimen.NETRAL, 102.0), (Sentimen.NEGATIF, 99.0),
        (Sentimen.NEGATIF, 97.0),
    ])
    hasil = sandingkan(db, "BBCA", date(2026, 9, 1), date(2026, 9, 30), lag=99)
    assert hasil.pearson is None
    assert "lag" in hasil.catatan


def test_emiten_tanpa_data_aman(db):
    hasil = sandingkan(db, "BBCA", date(2026, 9, 1), date(2026, 9, 30))
    assert hasil.titik == []
    assert hasil.pearson is None
