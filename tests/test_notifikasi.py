"""Uji notifikasi perubahan sentimen watchlist (SRS FR-6, UC-02)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.analitik.notifikasi import periksa_watchlist, ukur_perubahan
from app.auth.keamanan import hash_kata_sandi
from app.database import get_session
from app.main import app
from app.models import (
    AsalLabel,
    Base,
    Berita,
    BeritaEmiten,
    Emiten,
    Kredibilitas,
    LabelSentimen,
    Notifikasi,
    Pengguna,
    Peran,
    Sentimen,
    SumberBerita,
    Watchlist,
)

HARI_INI = date(2026, 9, 28)


@pytest.fixture()
def Sesi():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    pembuat = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with pembuat() as s:
        s.add(Emiten(kode="BBCA", nama="Bank Central Asia Tbk"))
        s.add(SumberBerita(nama="Uji", domain="u.test", kredibilitas=Kredibilitas.TERVERIFIKASI_DEWAN_PERS))
        for email in ("satu@uji.test", "dua@uji.test"):
            s.add(Pengguna(email=email, nama=email, peran=Peran.PENGGUNA,
                           kata_sandi_hash=hash_kata_sandi("rahasia123")))
        s.commit()
    return pembuat


def isi_berita(s, hari_lalu: int, sentimen: Sentimen, nomor: int):
    waktu = datetime.combine(HARI_INI - timedelta(days=hari_lalu), time(3), tzinfo=timezone.utc)
    b = Berita(sumber_id=1, judul=f"b{nomor}", url=f"https://u.test/{nomor}", sidik_jari=f"s{nomor}",
               terbit_pada=waktu, sudah_diklasifikasi=True)
    s.add(b)
    s.flush()
    s.add(BeritaEmiten(berita_id=b.id, emiten_id=1, cara_cocok="kode"))
    s.add(LabelSentimen(berita_id=b.id, emiten_id=1, sentimen=sentimen, keyakinan=1.0,
                        asal=AsalLabel.MODEL, versi_model="uji"))


def sentimen_berbalik(s):
    """Pekan lalu negatif semua, pekan ini positif semua."""
    n = 0
    for hari in (8, 10, 12):
        n += 1
        isi_berita(s, hari, Sentimen.NEGATIF, n)
    for hari in (1, 3, 5):
        n += 1
        isi_berita(s, hari, Sentimen.POSITIF, n)
    s.commit()


def test_perubahan_tajam_memicu_satu_notifikasi(Sesi):
    with Sesi() as s:
        sentimen_berbalik(s)
        s.add(Watchlist(pengguna_id=1, emiten_id=1, ambang=0.3))
        s.commit()

        baru = periksa_watchlist(s, HARI_INI)
        s.commit()
        assert len(baru) == 1
        n = baru[0]
        assert (n.skor_sebelum, n.skor_sesudah, n.jumlah_berita) == (-1.0, 1.0, 3)
        assert "BBCA naik" in n.pesan

        # siklus berikutnya (tiap 4 jam) dan hari-hari sesudahnya dalam pekan
        # yang sama tidak mengulang peringatan untuk pergeseran yang sama
        assert periksa_watchlist(s, HARI_INI) == []
        assert periksa_watchlist(s, HARI_INI + timedelta(days=2)) == []


def test_perubahan_di_bawah_ambang_diam(Sesi):
    with Sesi() as s:
        sentimen_berbalik(s)
        s.add(Watchlist(pengguna_id=1, emiten_id=1, ambang=1.0))  # selisihnya 2,0 — tetap lolos
        s.add(Watchlist(pengguna_id=2, emiten_id=1, ambang=0.3))
        s.commit()
        # ambang dibandingkan per pengguna
        assert len(periksa_watchlist(s, HARI_INI)) == 2

    with Sesi() as s:
        s.execute(Notifikasi.__table__.delete())
        w = s.scalar(select(Watchlist).where(Watchlist.pengguna_id == 1))
        w.ambang = 2.5  # lebih besar dari selisih terbesar yang mungkin
        s.commit()
        assert [n.pengguna_id for n in periksa_watchlist(s, HARI_INI)] == [2]


def test_satu_berita_tidak_cukup_untuk_disebut_perubahan(Sesi):
    with Sesi() as s:
        isi_berita(s, 9, Sentimen.NEGATIF, 1)          # hanya satu berita pekan lalu
        for i, hari in enumerate((1, 2, 3), start=2):
            isi_berita(s, hari, Sentimen.POSITIF, i)
        s.add(Watchlist(pengguna_id=1, emiten_id=1, ambang=0.3))
        s.commit()
        assert ukur_perubahan(s, "BBCA", HARI_INI) is None
        assert periksa_watchlist(s, HARI_INI) == []


def test_api_notifikasi_milik_sendiri_dan_bisa_ditandai_dibaca(Sesi):
    with Sesi() as s:
        sentimen_berbalik(s)
        s.add(Watchlist(pengguna_id=1, emiten_id=1, ambang=0.3))
        s.commit()
        periksa_watchlist(s, HARI_INI)
        s.commit()

    def sesi_uji():
        s = Sesi()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = sesi_uji
    try:
        with TestClient(app) as k:
            def kepala(email):
                t = k.post("/api/auth/masuk", json={"email": email, "kata_sandi": "rahasia123"}).json()["token"]
                return {"Authorization": f"Bearer {t}"}

            satu, dua = kepala("satu@uji.test"), kepala("dua@uji.test")
            d = k.get("/api/notifikasi", headers=satu).json()
            assert d["belum_dibaca"] == 1
            assert d["item"][0]["kode"] == "BBCA"
            assert k.get("/api/notifikasi", headers=dua).json() == {"belum_dibaca": 0, "item": []}

            assert k.post("/api/notifikasi/baca", headers=satu).json() == {"ditandai": 1}
            d = k.get("/api/notifikasi", headers=satu).json()
            assert d["belum_dibaca"] == 0 and d["item"][0]["dibaca"] is True
            assert k.get("/api/notifikasi").status_code == 401
    finally:
        app.dependency_overrides.clear()


class SmtpTiruan:
    terkirim: list = []

    def __init__(self, host, port, timeout=None):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, user, sandi):
        pass

    def send_message(self, pesan):
        SmtpTiruan.terkirim.append(pesan)


def test_email_hanya_untuk_yang_menyalakan_dan_diam_tanpa_smtp(Sesi, monkeypatch):
    from app.analitik import surel

    with Sesi() as s:
        sentimen_berbalik(s)
        s.add(Watchlist(pengguna_id=1, emiten_id=1, ambang=0.3))
        s.add(Watchlist(pengguna_id=2, emiten_id=1, ambang=0.3))
        s.get(Pengguna, 1).kirim_email = True  # pengguna 2 tidak menyalakan email
        s.commit()
        baru = periksa_watchlist(s, HARI_INI)
        s.commit()
        assert len(baru) == 2

        for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
            monkeypatch.delenv(k, raising=False)
        assert surel.kirim_notifikasi(s, baru) == "nonaktif (SMTP belum diatur)"

        SmtpTiruan.terkirim = []
        monkeypatch.setattr(surel.smtplib, "SMTP", SmtpTiruan)
        konfig = surel.KonfigSmtp("smtp.uji", 587, "bot@uji.test", "rahasia", "Bot <bot@uji.test>")
        assert surel.kirim_notifikasi(s, baru, konfig) == "1 terkirim, 0 gagal"
        (pesan,) = SmtpTiruan.terkirim
        assert pesan["To"] == "satu@uji.test"
        assert "BBCA" in pesan["Subject"]
        assert "bukan rekomendasi" in pesan.get_content()
