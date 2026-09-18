"""Uji endpoint API dengan basis data sementara di memori.

Tidak ada panggilan jaringan: basis data SQLite in-memory dipasang lewat
override dependency `get_session`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.keamanan import hash_kata_sandi
from app.database import get_session
from app.main import app
from app.models import (
    AsalLabel,
    Peran,
    Pengguna,
    Base,
    Berita,
    BeritaEmiten,
    Emiten,
    HargaSaham,
    Kredibilitas,
    LabelSentimen,
    Sentimen,
    StatusVerifikasi,
    SumberBerita,
)

AWAL = datetime(2026, 9, 1, 3, 0, tzinfo=timezone.utc)


@pytest.fixture()
def klien():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Sesi = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    with Sesi() as s:
        s.add(Emiten(kode="BBCA", nama="Bank Central Asia Tbk", sektor="Keuangan",
                     alias="BCA|Bank BCA"))
        s.add(Emiten(kode="TLKM", nama="Telkom Indonesia Tbk", sektor="Infrastruktur"))
        s.add(SumberBerita(nama="Portal Uji", domain="uji.test",
                           kredibilitas=Kredibilitas.TERVERIFIKASI_DEWAN_PERS))
        s.add(Pengguna(email="analis@uji.test", nama="Analis Uji",
                       kata_sandi_hash=hash_kata_sandi("rahasia123"),
                       peran=Peran.ANALIS))
        s.add(Pengguna(email="biasa@uji.test", nama="Pengguna Uji",
                       kata_sandi_hash=hash_kata_sandi("rahasia123"),
                       peran=Peran.PENGGUNA))
        s.commit()

        # 10 hari berita + harga, supaya korelasi bisa dihitung
        for i in range(10):
            waktu = AWAL + timedelta(days=i)
            b = Berita(
                sumber_id=1,
                judul=f"Kabar BBCA hari ke-{i}",
                ringkasan="ringkasan uji",
                url=f"http://uji.test/{i}",
                sidik_jari=f"sj{i}",
                terbit_pada=waktu,
                sudah_diklasifikasi=True,
            )
            s.add(b)
            s.flush()
            s.add(BeritaEmiten(berita_id=b.id, emiten_id=1, cara_cocok="kode"))
            s.add(
                LabelSentimen(
                    berita_id=b.id,
                    emiten_id=1,
                    sentimen=Sentimen.POSITIF if i % 2 == 0 else Sentimen.NEGATIF,
                    keyakinan=0.8,
                    asal=AsalLabel.MODEL,
                    versi_model="leksikon-v1",
                )
            )
            s.add(
                HargaSaham(
                    emiten_id=1,
                    tanggal=waktu,
                    penutupan=9000 + (60 * i if i % 2 == 0 else -40 * i),
                    volume=1_000_000 + i,
                )
            )
        s.commit()

    def sesi_uji():
        s = Sesi()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = sesi_uji
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


RENTANG = {"mulai": "2026-09-01", "sampai": "2026-09-30"}


def _kepala(klien, email: str) -> dict:
    """Header Authorization untuk akun uji."""
    token = klien.post(
        "/api/auth/masuk", json={"email": email, "kata_sandi": "rahasia123"}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def analis(klien):
    return _kepala(klien, "analis@uji.test")


@pytest.fixture()
def biasa(klien):
    return _kepala(klien, "biasa@uji.test")


def test_sehat(klien):
    assert klien.get("/api/sehat").json() == {"status": "ok"}


def test_daftar_emiten(klien):
    data = klien.get("/api/emiten").json()
    assert [e["kode"] for e in data] == ["BBCA", "TLKM"]


def test_cari_emiten_berdasarkan_nama(klien):
    data = klien.get("/api/emiten", params={"q": "telkom"}).json()
    assert len(data) == 1 and data[0]["kode"] == "TLKM"


def test_detail_emiten(klien):
    d = klien.get("/api/emiten/bbca").json()
    assert d["kode"] == "BBCA"
    assert d["jumlah_berita"] == 10
    assert d["alias"] == ["BCA", "Bank BCA"]
    assert d["harga_terakhir"] is not None


def test_emiten_tidak_ada(klien):
    r = klien.get("/api/emiten/XXXX")
    assert r.status_code == 404


def test_deret_sentimen(klien):
    d = klien.get("/api/emiten/BBCA/sentimen", params=RENTANG).json()
    assert len(d["titik"]) == 10
    assert d["titik"][0]["jumlah_berita"] == 1
    assert -1.0 <= d["titik"][0]["skor"] <= 1.0


def test_deret_harga(klien):
    d = klien.get("/api/emiten/BBCA/harga", params=RENTANG).json()
    assert len(d["titik"]) == 10
    assert d["titik"][0]["penutupan"] == 9000


def test_korelasi_terhitung(klien):
    d = klien.get("/api/emiten/BBCA/korelasi", params=RENTANG).json()
    assert d["hari_beririsan"] == 10
    assert d["pearson"]["metode"] == "pearson"
    assert d["spearman"]["metode"] == "spearman"
    assert "bukan sebab-akibat" in d["peringatan"]


def test_korelasi_kurang_data_memberi_catatan(klien):
    """Emiten tanpa data tidak boleh membuat endpoint gagal."""
    d = klien.get("/api/emiten/TLKM/korelasi", params=RENTANG).json()
    assert d["pearson"] is None
    assert d["catatan"]


def test_rentang_terbalik_ditolak(klien):
    r = klien.get(
        "/api/emiten/BBCA/sentimen", params={"mulai": "2026-09-30", "sampai": "2026-09-01"}
    )
    assert r.status_code == 400


def test_daftar_berita_dan_label(klien):
    data = klien.get("/api/berita", params={"kode": "BBCA", "limit": 5}).json()
    assert len(data) == 5
    assert data[0]["label"]["asal"] == "model"
    assert data[0]["emiten"] == ["BBCA"]


def test_saring_berita_berdasarkan_sentimen(klien):
    data = klien.get("/api/berita", params={"kode": "BBCA", "sentimen": "negatif"}).json()
    assert data and all(b["label"]["sentimen"] == "negatif" for b in data)


def test_koreksi_analis_mengalahkan_label_model(klien, analis):
    id_berita = klien.get("/api/berita", params={"kode": "BBCA", "limit": 1}).json()[0]["id"]
    r = klien.post(
        f"/api/berita/{id_berita}/koreksi",
        json={"kode_emiten": "BBCA", "sentimen": "netral"},
        headers=analis,
    )
    assert r.status_code == 200
    assert r.json()["label"]["sentimen"] == "netral"
    assert r.json()["label"]["asal"] == "analis"

    # label model tetap ada — koreksi tidak menimpanya
    lagi = klien.get(f"/api/berita/{id_berita}").json()
    assert lagi["label"]["asal"] == "analis"


def test_koreksi_emiten_tak_terkait_ditolak(klien, analis):
    id_berita = klien.get("/api/berita", params={"kode": "BBCA", "limit": 1}).json()[0]["id"]
    r = klien.post(
        f"/api/berita/{id_berita}/koreksi",
        json={"kode_emiten": "TLKM", "sentimen": "positif"},
        headers=analis,
    )
    assert r.status_code == 400


def test_ubah_status_verifikasi(klien, analis):
    id_berita = klien.get("/api/berita", params={"kode": "BBCA", "limit": 1}).json()[0]["id"]
    r = klien.post(
        f"/api/berita/{id_berita}/verifikasi",
        json={"status": StatusVerifikasi.TERKONFIRMASI_RESMI.value},
        headers=analis,
    )
    assert r.status_code == 200
    assert r.json()["status_verifikasi"] == "terkonfirmasi_resmi"

    tersaring = klien.get(
        "/api/berita", params={"kode": "BBCA", "status": "terkonfirmasi_resmi"}
    ).json()
    assert len(tersaring) == 1


def test_ringkasan(klien):
    d = klien.get("/api/ringkasan").json()
    assert d["jumlah_emiten"] == 2
    assert d["jumlah_berita"] == 10
    assert d["jumlah_berlabel"] == 10
    assert d["emiten_teraktif"][0]["kode"] == "BBCA"


def test_daftar_sumber(klien):
    d = klien.get("/api/sumber").json()
    assert d[0]["kredibilitas"] == "terverifikasi_dewan_pers"


def test_dasbor_tersaji(klien):
    r = klien.get("/")
    assert r.status_code == 200
    assert "Sentimen Emiten" in r.text


# ------------------------------------------------ endpoint verifikasi (UC-04)


def test_keterbukaan_kosong_bukan_galat(klien):
    assert klien.get("/api/emiten/BBCA/keterbukaan").json() == []


def test_jejak_verifikasi_tercatat_saat_diubah_manual(klien, analis):
    id_berita = klien.get("/api/berita", params={"kode": "BBCA", "limit": 1}).json()[0]["id"]
    klien.post(
        f"/api/berita/{id_berita}/verifikasi",
        json={"status": "rumor_belum_terkonfirmasi"},
        headers=analis,
    )
    jejak = klien.get(f"/api/berita/{id_berita}/jejak").json()
    assert len(jejak) == 1
    assert jejak[0]["otomatis"] is False
    assert jejak[0]["status"] == "rumor_belum_terkonfirmasi"
    assert jejak[0]["pengumuman"] is None


def test_jejak_berita_tidak_ada(klien):
    assert klien.get("/api/berita/99999/jejak").status_code == 404


def test_keterbukaan_terisi_setelah_verifikasi(klien):
    """Endpoint keterbukaan menampilkan pengumuman yang dipakai sebagai dasar."""
    from datetime import datetime, timezone

    from app.verifikasi.jalankan import jalankan_verifikasi
    from app.verifikasi.sumber import PengumumanMentah

    class SumberPalsu:
        nama = "palsu"

        def ambil(self, kode, mulai, sampai):
            if kode != "BBCA":
                return []
            return [
                PengumumanMentah(
                    "BBCA",
                    "Pembagian Dividen Interim Perseroan",
                    "http://idx/api-1",
                    datetime(2026, 9, 5, tzinfo=timezone.utc),
                )
            ]

    sesi = next(app.dependency_overrides[get_session]())
    jalankan_verifikasi(sesi, SumberPalsu(), hari=100000)
    sesi.close()

    data = klien.get("/api/emiten/BBCA/keterbukaan").json()
    assert len(data) == 1 and data[0]["url"] == "http://idx/api-1"


# ---------------------------------------------- autentikasi & peran (UC-02/05)


def test_masuk_berhasil(klien):
    r = klien.post(
        "/api/auth/masuk", json={"email": "analis@uji.test", "kata_sandi": "rahasia123"}
    )
    assert r.status_code == 200
    assert r.json()["tipe"] == "bearer"


def test_masuk_sandi_salah(klien):
    r = klien.post(
        "/api/auth/masuk", json={"email": "analis@uji.test", "kata_sandi": "salah"}
    )
    assert r.status_code == 401


def test_pesan_galat_sama_untuk_email_tak_terdaftar(klien):
    """Pesan yang berbeda akan membocorkan email mana yang punya akun."""
    a = klien.post("/api/auth/masuk", json={"email": "analis@uji.test", "kata_sandi": "salah"})
    b = klien.post("/api/auth/masuk", json={"email": "hantu@uji.test", "kata_sandi": "salah"})
    assert a.json()["detail"] == b.json()["detail"]


def test_saya_butuh_token(klien):
    assert klien.get("/api/auth/saya").status_code == 401


def test_saya_dengan_token(klien, analis):
    d = klien.get("/api/auth/saya", headers=analis).json()
    assert d["email"] == "analis@uji.test" and d["peran"] == "analis"


def test_token_palsu_ditolak(klien):
    r = klien.get("/api/auth/saya", headers={"Authorization": "Bearer abc.def"})
    assert r.status_code == 401


def test_koreksi_tanpa_token_ditolak(klien):
    id_berita = klien.get("/api/berita", params={"kode": "BBCA", "limit": 1}).json()[0]["id"]
    r = klien.post(
        f"/api/berita/{id_berita}/koreksi", json={"kode_emiten": "BBCA", "sentimen": "netral"}
    )
    assert r.status_code == 401


def test_koreksi_oleh_pengguna_biasa_ditolak(klien, biasa):
    """Pengguna biasa boleh melihat, tidak boleh mengubah label."""
    id_berita = klien.get("/api/berita", params={"kode": "BBCA", "limit": 1}).json()[0]["id"]
    r = klien.post(
        f"/api/berita/{id_berita}/koreksi",
        json={"kode_emiten": "BBCA", "sentimen": "netral"},
        headers=biasa,
    )
    assert r.status_code == 403


# ------------------------------------------------------------ watchlist (UC-02)


def test_watchlist_butuh_token(klien):
    assert klien.get("/api/watchlist").status_code == 401


def test_tambah_dan_lihat_watchlist(klien, biasa):
    r = klien.post("/api/watchlist", json={"kode_emiten": "bbca", "catatan": "pantau dividen"},
                   headers=biasa)
    assert r.status_code == 201
    assert r.json()["kode"] == "BBCA"

    daftar = klien.get("/api/watchlist", headers=biasa).json()
    assert len(daftar) == 1
    assert daftar[0]["catatan"] == "pantau dividen"
    assert daftar[0]["harga_terakhir"] is not None


def test_tambah_dua_kali_memperbarui_catatan(klien, biasa):
    klien.post("/api/watchlist", json={"kode_emiten": "BBCA", "catatan": "awal"}, headers=biasa)
    klien.post("/api/watchlist", json={"kode_emiten": "BBCA", "catatan": "revisi"}, headers=biasa)
    daftar = klien.get("/api/watchlist", headers=biasa).json()
    assert len(daftar) == 1 and daftar[0]["catatan"] == "revisi"


def test_watchlist_terpisah_antar_pengguna(klien, analis, biasa):
    """Watchlist satu pengguna tidak boleh bocor ke pengguna lain."""
    klien.post("/api/watchlist", json={"kode_emiten": "BBCA"}, headers=biasa)
    assert klien.get("/api/watchlist", headers=analis).json() == []


def test_hapus_watchlist(klien, biasa):
    klien.post("/api/watchlist", json={"kode_emiten": "TLKM"}, headers=biasa)
    assert klien.delete("/api/watchlist/TLKM", headers=biasa).status_code == 200
    assert klien.get("/api/watchlist", headers=biasa).json() == []


def test_hapus_yang_tidak_ada(klien, biasa):
    assert klien.delete("/api/watchlist/TLKM", headers=biasa).status_code == 404


def test_tambah_emiten_tak_dikenal(klien, biasa):
    r = klien.post("/api/watchlist", json={"kode_emiten": "XXXX"}, headers=biasa)
    assert r.status_code == 404


# ------------------------------------------------------ ikhtisar (peringkat)


def test_peringkat_memuat_semua_emiten_aktif(klien):
    d = klien.get("/api/peringkat", params=RENTANG).json()
    assert {b["kode"] for b in d["baris"]} == {"BBCA", "TLKM"}


def test_peringkat_hanya_berberita(klien):
    d = klien.get(
        "/api/peringkat", params={**RENTANG, "hanya_berberita": "true"}
    ).json()
    assert [b["kode"] for b in d["baris"]] == ["BBCA"]


def test_peringkat_menghitung_skor_dan_perubahan_harga(klien):
    d = klien.get("/api/peringkat", params=RENTANG).json()
    bbca = next(b for b in d["baris"] if b["kode"] == "BBCA")
    assert bbca["jumlah_berita"] == 10
    assert bbca["jumlah_positif"] + bbca["jumlah_negatif"] == 10
    assert bbca["skor"] is not None
    assert bbca["perubahan_harga"] is not None
    tlkm = next(b for b in d["baris"] if b["kode"] == "TLKM")
    assert tlkm["skor"] is None and tlkm["jumlah_berita"] == 0


def test_peringkat_emiten_tanpa_berita_diurutkan_belakangan(klien):
    d = klien.get("/api/peringkat", params=RENTANG).json()
    assert d["baris"][-1]["kode"] == "TLKM"


def test_ringkasan_hanya_menghitung_emiten_aktif(klien):
    """Emiten yang sudah keluar komposisi tidak lagi dipantau, jadi memasukkannya
    ke ringkasan melaporkan cakupan lebih besar daripada yang berjalan."""
    from sqlalchemy import select as pilih

    from app.models import Emiten as E

    sesi = next(app.dependency_overrides[get_session]())
    lama = E(kode="ZZZZ", nama="Emiten Periode Lalu Tbk", aktif=False)
    sesi.add(lama)
    sesi.commit()
    sesi.close()

    assert klien.get("/api/ringkasan").json()["jumlah_emiten"] == 2
    assert klien.get("/api/peringkat", params=RENTANG).json()["baris"][0]["kode"] != "ZZZZ"


# ---------------------------------------------------- rentang data & batas


def test_rentang_data_melaporkan_berita_dan_harga_terpisah(klien):
    """Data harga bisa mundur berbulan-bulan sementara sentimen baru terkumpul;
    keduanya harus dilaporkan apa adanya, bukan digabung jadi satu angka."""
    d = klien.get("/api/rentang-data").json()
    assert d["berita_mulai"] == "2026-09-01"
    assert d["harga_mulai"] == "2026-09-01"
    assert d["mulai"] == "2026-09-01"
    assert d["sampai"] is not None


def test_rentang_panjang_diterima(klien):
    """Tombol 'seluruh data' tidak boleh tertolak oleh batas rentang."""
    r = klien.get(
        "/api/emiten/BBCA/sentimen",
        params={"mulai": "2024-01-01", "sampai": "2026-09-30"},
    )
    assert r.status_code == 200


def test_rentang_sangat_panjang_tetap_ditolak(klien):
    r = klien.get(
        "/api/emiten/BBCA/sentimen",
        params={"mulai": "2010-01-01", "sampai": "2026-09-30"},
    )
    assert r.status_code == 400
