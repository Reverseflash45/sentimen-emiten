"""Uji pipeline penyimpanan tanpa menyentuh jaringan."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ingest.cleaner import sidik_jari
from app.ingest.pipeline import HasilSiklus, peta_emiten, simpan_artikel
from app.ingest.rss import ArtikelMentah
from app.models import Base, Berita, BeritaEmiten, Emiten, SumberBerita


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add(Emiten(kode="BBCA", nama="Bank Central Asia Tbk", alias="BCA"))
    s.add(Emiten(kode="GOTO", nama="GoTo Gojek Tokopedia Tbk", alias="GoTo"))
    s.add(SumberBerita(nama="Uji", domain="uji.test", url_rss="https://uji.test/rss"))
    s.commit()
    yield s
    s.close()


def artikel(judul: str, ringkasan: str = "", url: str = "https://uji.test/1") -> ArtikelMentah:
    return ArtikelMentah(
        judul=judul,
        ringkasan=ringkasan,
        url=url,
        terbit_pada=None,
        sidik_jari=sidik_jari(judul, ringkasan),
    )


def test_menyimpan_berita_dan_memetakan_emiten(session):
    sumber = session.scalar(select(SumberBerita))
    hasil = HasilSiklus()
    simpan_artikel(
        session, sumber, artikel("Saham BBCA menguat", "Bursa hijau"), peta_emiten(session), hasil
    )
    session.commit()

    assert hasil.baru == 1
    assert hasil.terpetakan == 1
    assert session.scalar(select(Berita)).judul == "Saham BBCA menguat"
    assert session.scalar(select(BeritaEmiten)).cara_cocok == "kode"


def test_url_sama_tidak_disimpan_dua_kali(session):
    sumber = session.scalar(select(SumberBerita))
    hasil = HasilSiklus()
    a = artikel("Saham BBCA menguat")
    simpan_artikel(session, sumber, a, peta_emiten(session), hasil)
    session.commit()
    simpan_artikel(session, sumber, a, peta_emiten(session), hasil)
    session.commit()

    assert hasil.baru == 1
    assert hasil.duplikat == 1
    assert len(list(session.scalars(select(Berita)))) == 1


def test_artikel_sindikasi_dikenali_lewat_sidik_jari(session):
    """Judul sama, URL berbeda — tetap dianggap satu berita."""
    sumber = session.scalar(select(SumberBerita))
    hasil = HasilSiklus()
    simpan_artikel(
        session, sumber, artikel("Laba BBCA naik", url="https://uji.test/a"),
        peta_emiten(session), hasil,
    )
    session.commit()
    simpan_artikel(
        session, sumber, artikel("Laba BBCA naik", url="https://lain.test/b"),
        peta_emiten(session), hasil,
    )
    session.commit()

    assert hasil.duplikat == 1
    assert len(list(session.scalars(select(Berita)))) == 1


def test_berita_tanpa_emiten_tetap_disimpan(session):
    sumber = session.scalar(select(SumberBerita))
    hasil = HasilSiklus()
    simpan_artikel(
        session, sumber, artikel("IHSG dibuka menguat"), peta_emiten(session), hasil
    )
    session.commit()

    assert hasil.baru == 1
    assert hasil.tanpa_emiten == 1
    assert len(list(session.scalars(select(BeritaEmiten)))) == 0


def test_satu_berita_dua_emiten(session):
    sumber = session.scalar(select(SumberBerita))
    hasil = HasilSiklus()
    simpan_artikel(
        session, sumber, artikel("Saham BBCA dan GOTO kompak menguat"),
        peta_emiten(session), hasil,
    )
    session.commit()

    assert hasil.terpetakan == 2
    assert len(list(session.scalars(select(BeritaEmiten)))) == 2
