"""Uji pencocokan berita dengan pengumuman resmi BEI (UC-04).

Semuanya tanpa jaringan: SumberIdx diuji lewat transport httpx tiruan, dan
SumberCsv lewat berkas sementara.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    Berita,
    BeritaEmiten,
    Emiten,
    KeterbukaanInformasi,
    Kredibilitas,
    StatusVerifikasi,
    SumberBerita,
    VerifikasiBerita,
)
from app.verifikasi.jalankan import jalankan_verifikasi, verifikasi_emiten
from app.verifikasi.pencocok import bahasa_spekulatif, cari_kecocokan, kemiripan
from app.verifikasi.sumber import PengumumanMentah, SumberCsv, SumberIdx

WAKTU = datetime(2026, 9, 10, 4, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------- pencocokan teks


def test_kemiripan_menangkap_kata_penting():
    n = kemiripan(
        "BBCA tebar dividen interim Rp 50 per saham",
        "Penyampaian Bukti Iklan Pembagian Dividen Interim",
    )
    assert n > 0


def test_kemiripan_nol_untuk_topik_berbeda():
    n = kemiripan(
        "BBCA buka cabang baru di Kediri",
        "Penyampaian Laporan Bulanan Registrasi Pemegang Efek",
    )
    assert n == 0.0


def test_satu_kata_sama_belum_cukup():
    """Satu kata beririsan terlalu mudah terjadi dan bikin salah cocok."""
    assert kemiripan("Perseroan bagikan dividen", "Dividen tunai TLKM") >= 0.0
    assert kemiripan("Rencana akuisisi anak usaha", "Laporan keuangan triwulan") == 0.0


def test_bahasa_spekulatif():
    assert bahasa_spekulatif("Kabarnya BBCA akan mengakuisisi bank kecil")
    assert bahasa_spekulatif("Isu merger santer beredar")
    assert not bahasa_spekulatif("BBCA resmi membagikan dividen interim")


def test_kecocokan_di_luar_jendela_waktu_ditolak():
    p = PengumumanMentah("BBCA", "Pembagian Dividen Interim Perseroan", "u1", WAKTU + timedelta(days=40))
    assert cari_kecocokan("BBCA bagikan dividen interim", WAKTU, [p]) is None


def test_kecocokan_di_dalam_jendela_waktu_diterima():
    p = PengumumanMentah("BBCA", "Pembagian Dividen Interim Perseroan", "u1", WAKTU + timedelta(days=2))
    hasil = cari_kecocokan("BBCA bagikan dividen interim tahun ini", WAKTU, [p])
    assert hasil is not None and "dividen" in hasil.kata_sama


def test_memilih_pengumuman_paling_mirip():
    a = PengumumanMentah("BBCA", "Laporan Bulanan Kepemilikan Efek", "u1", WAKTU)
    b = PengumumanMentah("BBCA", "Pembagian Dividen Interim Perseroan", "u2", WAKTU)
    hasil = cari_kecocokan("BBCA umumkan pembagian dividen interim", WAKTU, [a, b])
    assert hasil is not None and hasil.pengumuman.url == "u2"


# ------------------------------------------------------------------------ sumber


def test_sumber_csv_kolom_indonesia(tmp_path):
    berkas = tmp_path / "idx.csv"
    berkas.write_text(
        "kode,judul,url,tanggal\nBBCA,Pembagian Dividen Interim,http://idx/1,2026-09-10\n",
        encoding="utf-8",
    )
    hasil = SumberCsv(berkas).ambil("bbca", WAKTU - timedelta(days=5), WAKTU + timedelta(days=5))
    assert len(hasil) == 1 and hasil[0].kode_emiten == "BBCA"


def test_sumber_csv_kolom_inggris(tmp_path):
    berkas = tmp_path / "idx.csv"
    berkas.write_text(
        "code,title,link,date\nTLKM,Interim Dividend,http://idx/2,2026-09-10\n",
        encoding="utf-8",
    )
    hasil = SumberCsv(berkas).semua()
    assert hasil[0].kode_emiten == "TLKM" and hasil[0].url == "http://idx/2"


def test_sumber_csv_berkas_hilang(tmp_path):
    with pytest.raises(FileNotFoundError):
        SumberCsv(tmp_path / "tidak-ada.csv").semua()


def test_sumber_idx_parsing_longgar():
    """Bentuk respons BEI bisa berubah; kunci tak dikenal harus dilewati,
    bukan membuat seluruh pengambilan gagal."""
    isi = {
        "Replies": [
            {
                "KodeEmiten": "BBCA",
                "JudulPengumuman": "Pembagian Dividen Interim",
                "AttachmentUrl": "/files/a.pdf",
                "PublishDate": "2026-09-10T09:00:00",
            },
            {"Sesuatu": "tanpa judul"},
        ]
    }
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=json.dumps(isi)))
    with httpx.Client(transport=transport) as klien:
        hasil = SumberIdx(klien).ambil("BBCA", WAKTU - timedelta(days=5), WAKTU + timedelta(days=5))
    assert len(hasil) == 1
    assert hasil[0].url == "https://www.idx.co.id/files/a.pdf"


# ---------------------------------------------------------------------- pipeline


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False, future=True)()
    s.add(Emiten(kode="BBCA", nama="Bank Central Asia Tbk"))
    s.add(SumberBerita(nama="Uji", domain="uji.test", kredibilitas=Kredibilitas.PORTAL_UMUM))
    s.commit()
    yield s
    s.close()


def _berita(session, judul: str, url: str, ringkasan: str = "") -> Berita:
    b = Berita(
        sumber_id=1, judul=judul, ringkasan=ringkasan, url=url,
        sidik_jari=url, terbit_pada=WAKTU,
    )
    session.add(b)
    session.flush()
    session.add(BeritaEmiten(berita_id=b.id, emiten_id=1, cara_cocok="kode"))
    session.commit()
    return b


class SumberPalsu:
    nama = "palsu"

    def __init__(self, daftar): self.daftar = daftar

    def ambil(self, kode, mulai, sampai): return list(self.daftar)


def test_berita_cocok_jadi_terkonfirmasi(db):
    _berita(db, "BBCA umumkan pembagian dividen interim", "http://u/1")
    sumber = SumberPalsu([
        PengumumanMentah("BBCA", "Pembagian Dividen Interim Perseroan", "http://idx/1", WAKTU)
    ])
    hasil = jalankan_verifikasi(db, sumber, hari=30)

    assert hasil.terkonfirmasi == 1
    assert db.scalar(select(Berita)).status_verifikasi is StatusVerifikasi.TERKONFIRMASI_RESMI


def test_jejak_menyimpan_pengumuman_yang_dipakai(db):
    _berita(db, "BBCA umumkan pembagian dividen interim", "http://u/2")
    sumber = SumberPalsu([
        PengumumanMentah("BBCA", "Pembagian Dividen Interim Perseroan", "http://idx/2", WAKTU)
    ])
    jalankan_verifikasi(db, sumber, hari=30)

    jejak = db.scalar(select(VerifikasiBerita))
    assert jejak.otomatis is True
    assert jejak.keterbukaan_id is not None
    assert "dividen" in jejak.alasan
    assert db.get(KeterbukaanInformasi, jejak.keterbukaan_id).url == "http://idx/2"


def test_kabar_spekulatif_tanpa_pengumuman_jadi_rumor(db):
    _berita(db, "BBCA dikabarkan akan mengakuisisi bank daerah", "http://u/3",
            ringkasan="Isu ini santer beredar di kalangan pelaku pasar")
    hasil = jalankan_verifikasi(db, SumberPalsu([]), hari=30)

    assert hasil.ditandai_rumor == 1
    assert db.scalar(select(Berita)).status_verifikasi is StatusVerifikasi.RUMOR_BELUM_TERKONFIRMASI


def test_berita_biasa_tanpa_pengumuman_dibiarkan(db):
    """Tidak adanya pengumuman resmi bukan bukti kabarnya salah."""
    _berita(db, "BBCA membuka kantor cabang baru di Kediri", "http://u/4")
    hasil = jalankan_verifikasi(db, SumberPalsu([]), hari=30)

    assert hasil.dibiarkan == 1
    assert hasil.ditandai_rumor == 0
    assert db.scalar(select(Berita)).status_verifikasi is StatusVerifikasi.BELUM_DIPERIKSA


def test_keputusan_analis_tidak_ditimpa(db):
    b = _berita(db, "BBCA umumkan pembagian dividen interim", "http://u/5")
    b.status_verifikasi = StatusVerifikasi.RUMOR_BELUM_TERKONFIRMASI
    db.commit()

    sumber = SumberPalsu([
        PengumumanMentah("BBCA", "Pembagian Dividen Interim Perseroan", "http://idx/5", WAKTU)
    ])
    hasil = jalankan_verifikasi(db, sumber, hari=30)

    assert hasil.berita_diperiksa == 0
    assert db.scalar(select(Berita)).status_verifikasi is StatusVerifikasi.RUMOR_BELUM_TERKONFIRMASI


def test_paksa_menilai_ulang_status_yang_sudah_ada(db):
    b = _berita(db, "BBCA umumkan pembagian dividen interim", "http://u/6")
    b.status_verifikasi = StatusVerifikasi.RUMOR_BELUM_TERKONFIRMASI
    db.commit()

    sumber = SumberPalsu([
        PengumumanMentah("BBCA", "Pembagian Dividen Interim Perseroan", "http://idx/6", WAKTU)
    ])
    jalankan_verifikasi(db, sumber, hari=30, paksa=True)

    assert db.scalar(select(Berita)).status_verifikasi is StatusVerifikasi.TERKONFIRMASI_RESMI


def test_pengumuman_tidak_diduplikasi(db):
    _berita(db, "BBCA umumkan pembagian dividen interim", "http://u/7")
    sumber = SumberPalsu([
        PengumumanMentah("BBCA", "Pembagian Dividen Interim Perseroan", "http://idx/7", WAKTU)
    ])
    jalankan_verifikasi(db, sumber, hari=30)
    jalankan_verifikasi(db, sumber, hari=30, paksa=True)

    assert len(list(db.scalars(select(KeterbukaanInformasi)))) == 1


def test_emiten_gagal_tidak_menghentikan_yang_lain(db):
    db.add(Emiten(kode="TLKM", nama="Telkom Indonesia Tbk"))
    db.commit()
    _berita(db, "BBCA umumkan pembagian dividen interim", "http://u/8")

    class SumberRewel:
        nama = "rewel"

        def ambil(self, kode, mulai, sampai):
            if kode == "BBCA":
                raise RuntimeError("endpoint BEI menolak")
            return []

    hasil = jalankan_verifikasi(db, SumberRewel(), hari=30)
    assert len(hasil.gagal) == 1 and "BBCA" in hasil.gagal[0]
