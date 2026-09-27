"""Uji bagian bersama pelatihan/inferensi IndoBERT (tanpa torch)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.klasifikasi.basis import Pengklasifikasi, Prediksi
from app.klasifikasi.dataset import VERSI_ANOTASI, bagian_data, muat_label_emas, teks_target, teks_utama
from app.klasifikasi.jalankan import klasifikasi_berita_baru
from app.models import (
    AsalLabel, Base, Berita, BeritaEmiten, Emiten, Kredibilitas, LabelSentimen, Sentimen, SumberBerita,
)

WAKTU = datetime(2026, 9, 20, 8, 0, tzinfo=timezone.utc)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add_all([
        Emiten(kode="BBCA", nama="Bank Central Asia Tbk"),
        Emiten(kode="BMRI", nama="Bank Mandiri (Persero) Tbk"),
        SumberBerita(nama="Uji", domain="u.test", kredibilitas=Kredibilitas.TERVERIFIKASI_DEWAN_PERS),
    ])
    s.commit()
    yield s
    s.close()


def berita(db, judul, emiten_ids=(1,)):
    b = Berita(sumber_id=1, judul=judul, ringkasan="ringkas", url=f"https://u.test/{judul}",
               sidik_jari=judul, terbit_pada=WAKTU)
    db.add(b)
    db.flush()
    for e in emiten_ids:
        db.add(BeritaEmiten(berita_id=b.id, emiten_id=e, cara_cocok="kode", kutipan=f"…kutipan {e}…"))
    db.commit()
    return b


def label(db, b, sentimen, asal=AsalLabel.ANALIS, versi=VERSI_ANOTASI, emiten_id=1, menit=0):
    db.add(LabelSentimen(berita_id=b.id, emiten_id=emiten_id, sentimen=sentimen, keyakinan=1.0,
                         asal=asal, versi_model=versi, dibuat_pada=WAKTU + timedelta(minutes=menit)))
    db.commit()


def test_bagian_data_tetap_dan_proporsional():
    assert [bagian_data(i) for i in range(50)] == [bagian_data(i) for i in range(50)]
    hitung = Counter(bagian_data(i) for i in range(20_000))
    assert abs(hitung["latih"] / 20_000 - 0.70) < 0.02
    assert abs(hitung["validasi"] / 20_000 - 0.15) < 0.02
    assert abs(hitung["uji"] / 20_000 - 0.15) < 0.02


def test_teks_masukan():
    assert teks_utama("Laba naik", None) == "Laba naik."
    assert teks_target("BBCA", "Bank Central Asia Tbk", "…BCA mencatat laba…") == \
        "BBCA (Bank Central Asia Tbk). BCA mencatat laba"


def test_label_emas_hanya_dari_manusia_dan_yang_terbaru(db):
    b1 = berita(db, "a")
    label(db, b1, Sentimen.NEGATIF, asal=AsalLabel.MODEL, versi="leksikon-v1")
    b2 = berita(db, "b")
    label(db, b2, Sentimen.NETRAL, menit=1)
    label(db, b2, Sentimen.POSITIF, versi="-", menit=2)  # koreksi analis yang lebih baru
    data = muat_label_emas(db)
    assert len(data) == 1  # label model tidak ikut
    assert data[0].berita_id == b2.id
    assert data[0].sentimen == Sentimen.POSITIF
    assert data[0].target.startswith("BBCA (Bank Central Asia Tbk).")
    assert data[0].bagian == bagian_data(b2.id)


class ModelPerEmiten(Pengklasifikasi):
    versi = "uji-per-emiten"
    per_emiten = True

    def prediksi(self, teks):
        raise AssertionError("model per emiten harus dipanggil lewat prediksi_emiten")

    def prediksi_emiten(self, teks, target):
        return Prediksi(Sentimen.POSITIF if target.startswith("BBCA") else Sentimen.NEGATIF, 0.9)


def test_model_per_emiten_memberi_label_berbeda_per_emiten(db):
    berita(db, "BBCA untung, BMRI tertekan", emiten_ids=(1, 2))
    hasil = klasifikasi_berita_baru(db, ModelPerEmiten())
    assert hasil.label_dibuat == 2
    label_per_emiten = {l.emiten_id: l.sentimen for l in db.query(LabelSentimen).all()}
    assert label_per_emiten == {1: Sentimen.POSITIF, 2: Sentimen.NEGATIF}
