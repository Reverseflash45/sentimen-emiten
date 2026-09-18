"""Uji baseline pengklasifikasi leksikon dan pipeline pelabelan."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.klasifikasi import PengklasifikasiLeksikon
from app.klasifikasi.jalankan import klasifikasi_berita_baru
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

WAKTU = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)


@pytest.fixture()
def model():
    return PengklasifikasiLeksikon()


def test_kalimat_positif(model):
    p = model.prediksi("Laba bersih BBCA tumbuh dan sahamnya menguat")
    assert p.sentimen is Sentimen.POSITIF
    assert p.keyakinan > 0


def test_kalimat_negatif(model):
    p = model.prediksi("Emiten merugi, sahamnya anjlok setelah kena sanksi")
    assert p.sentimen is Sentimen.NEGATIF


def test_kalimat_netral(model):
    p = model.prediksi("Perseroan menggelar rapat umum pemegang saham tahunan")
    assert p.sentimen is Sentimen.NETRAL


def test_negasi_membalik_arah(model):
    """'tidak rugi' tidak boleh dibaca sebagai berita negatif."""
    negatif = model.prediksi("Perseroan rugi besar tahun ini")
    ingkar = model.prediksi("Perseroan tidak rugi tahun ini")
    assert negatif.sentimen is Sentimen.NEGATIF
    assert ingkar.sentimen is not Sentimen.NEGATIF


def test_keyakinan_dibatasi(model):
    p = model.prediksi("laba untung menguat melonjak meroket rekor surplus dividen")
    assert 0.0 <= p.keyakinan <= 0.95


def test_penjelasan_berisi_kata_pemicu(model):
    p = model.prediksi("sahamnya anjlok")
    assert p.penjelasan and "anjlok" in p.penjelasan


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add(Emiten(kode="BBCA", nama="Bank Central Asia Tbk"))
    s.add(Emiten(kode="TLKM", nama="Telkom Indonesia Tbk"))
    s.add(SumberBerita(nama="Uji", domain="uji.test", kredibilitas=Kredibilitas.PORTAL_UMUM))
    s.commit()
    yield s
    s.close()


def _berita(session, judul: str, emiten_ids: list[int], url: str) -> Berita:
    b = Berita(sumber_id=1, judul=judul, url=url, sidik_jari=url, terbit_pada=WAKTU)
    session.add(b)
    session.flush()
    for eid in emiten_ids:
        session.add(BeritaEmiten(berita_id=b.id, emiten_id=eid, cara_cocok="kode"))
    session.commit()
    return b


def test_pipeline_membuat_label_per_emiten(db, model):
    _berita(db, "Laba BBCA tumbuh, TLKM ikut menguat", [1, 2], "http://a.test/1")
    hasil = klasifikasi_berita_baru(db, model)

    assert hasil.berita_diproses == 1
    assert hasil.label_dibuat == 2  # satu label untuk tiap emiten
    labels = list(db.scalars(select(LabelSentimen)))
    assert {l.emiten_id for l in labels} == {1, 2}
    assert all(l.asal is AsalLabel.MODEL for l in labels)
    assert all(l.versi_model == model.versi for l in labels)


def test_berita_tanpa_emiten_dilewati(db, model):
    _berita(db, "Berita umum tanpa emiten", [], "http://a.test/2")
    hasil = klasifikasi_berita_baru(db, model)
    assert hasil.dilewati_tanpa_emiten == 1
    assert hasil.label_dibuat == 0
    # tetap ditandai selesai supaya tidak diproses berulang tiap siklus
    assert db.scalar(select(Berita)).sudah_diklasifikasi is True


def test_tidak_melabeli_dua_kali(db, model):
    _berita(db, "Laba BBCA tumbuh", [1], "http://a.test/3")
    klasifikasi_berita_baru(db, model)
    kedua = klasifikasi_berita_baru(db, model)
    assert kedua.berita_diproses == 0
    assert db.scalar(select(LabelSentimen.id)) is not None


def test_ulangi_tidak_menggandakan_label_versi_sama(db, model):
    _berita(db, "Laba BBCA tumbuh", [1], "http://a.test/4")
    klasifikasi_berita_baru(db, model)
    klasifikasi_berita_baru(db, model, ulangi=True)
    jumlah = len(list(db.scalars(select(LabelSentimen))))
    assert jumlah == 1


def test_versi_model_berbeda_menambah_label_baru(db, model):
    """Pergantian versi model harus menyimpan label baru, bukan menimpa —
    supaya hasil dua versi bisa dibandingkan."""
    _berita(db, "Laba BBCA tumbuh", [1], "http://a.test/5")
    klasifikasi_berita_baru(db, model)

    model_baru = PengklasifikasiLeksikon()
    model_baru.versi = "leksikon-v2"
    klasifikasi_berita_baru(db, model_baru, ulangi=True)

    versi = {l.versi_model for l in db.scalars(select(LabelSentimen))}
    assert versi == {"leksikon-v1", "leksikon-v2"}
