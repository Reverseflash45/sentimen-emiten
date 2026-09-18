"""Uji pengayaan pemetaan lewat badan artikel.

Tanpa jaringan: halaman artikel disajikan lewat transport httpx tiruan, dan
pemeriksaan robots.txt dimatikan sesuai kebutuhan tiap uji.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ingest import pengaya
from app.ingest.pengaya import ekstrak_teks, perkaya_pemetaan
from app.models import (
    Base,
    Berita,
    BeritaEmiten,
    Emiten,
    Kredibilitas,
    PengayaanBerita,
    SumberBerita,
)

WAKTU = datetime(2026, 9, 14, 6, 0, tzinfo=timezone.utc)

HALAMAN = """
<html><head><title>abaikan</title>
<script>var x = "BBCA palsu di dalam script";</script></head>
<body>
<nav>Menu BBRI navigasi</nav>
<p>JAKARTA, KONTAN.CO.ID - Delapan blok migas dilelang pemerintah tahun ini.</p>
<p>Saham Medco Energi Internasional Tbk menjadi salah satu yang disebut analis
sebagai penerima manfaat dari lelang tersebut.</p>
<footer>Hak cipta</footer>
</body></html>
"""


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False, future=True)()
    s.add(Emiten(kode="MEDC", nama="Medco Energi Internasional Tbk", sektor="Energi",
                 alias="Medco Energi|Medco"))
    s.add(Emiten(kode="BBCA", nama="Bank Central Asia Tbk", alias="BCA"))
    s.add(SumberBerita(nama="Uji", domain="uji.test", kredibilitas=Kredibilitas.PORTAL_UMUM))
    s.commit()
    yield s
    s.close()


def _berita(session, judul: str, url: str, ringkasan: str = "") -> Berita:
    b = Berita(sumber_id=1, judul=judul, ringkasan=ringkasan, url=url,
               sidik_jari=url, terbit_pada=WAKTU, sudah_diklasifikasi=True)
    session.add(b)
    session.commit()
    return b


def _klien(html: str = HALAMAN, status: int = 200) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(status, text=html))
    )


@pytest.fixture()
def robots_izinkan(monkeypatch):
    monkeypatch.setattr(pengaya.robots, "boleh_diambil", lambda url: True)
    monkeypatch.setattr(pengaya.robots, "jeda_crawl", lambda url: 0.0)


# ---------------------------------------------------------------- ekstraksi


def test_ekstrak_membuang_script_dan_navigasi():
    teks = ekstrak_teks(HALAMAN)
    assert "Medco Energi" in teks
    assert "script" not in teks.lower()
    assert "navigasi" not in teks.lower()


def test_ekstrak_html_kosong():
    assert ekstrak_teks("") == ""


def test_ekstrak_tanpa_paragraf_jatuh_ke_seluruh_teks():
    assert "Medco" in ekstrak_teks("<html><body><div>Saham Medco naik</div></body></html>")


# ------------------------------------------------------------------ pipeline


def test_emiten_ditemukan_di_badan_artikel(db, robots_izinkan):
    """Judulnya tidak menyebut emiten; nama emiten hanya ada di isi artikel."""
    b = _berita(db, "Daftar Lengkap 8 Blok Migas Dilelang", "http://uji.test/1")
    with _klien() as klien:
        hasil = perkaya_pemetaan(db, klien=klien, jeda=False)

    assert hasil.terpetakan == 1
    kaitan = list(db.scalars(select(BeritaEmiten).where(BeritaEmiten.berita_id == b.id)))
    assert [k.emiten_id for k in kaitan] == [1]  # MEDC
    assert kaitan[0].kutipan


def test_berita_perlu_dilabeli_ulang_setelah_dapat_emiten(db, robots_izinkan):
    b = _berita(db, "Daftar Lengkap 8 Blok Migas Dilelang", "http://uji.test/2")
    with _klien() as klien:
        perkaya_pemetaan(db, klien=klien, jeda=False)
    db.refresh(b)
    assert b.sudah_diklasifikasi is False


def test_berita_yang_sudah_terpetakan_dilewati(db, robots_izinkan):
    b = _berita(db, "Saham BBCA naik", "http://uji.test/3")
    db.add(BeritaEmiten(berita_id=b.id, emiten_id=2, cara_cocok="kode"))
    db.commit()

    with _klien() as klien:
        hasil = perkaya_pemetaan(db, klien=klien, jeda=False)
    assert hasil.diperiksa == 0


def test_robots_menolak_tidak_mengambil_halaman(db, monkeypatch):
    monkeypatch.setattr(pengaya.robots, "boleh_diambil", lambda url: False)
    _berita(db, "Daftar Lengkap 8 Blok Migas Dilelang", "http://uji.test/4")

    with _klien() as klien:
        hasil = perkaya_pemetaan(db, klien=klien, jeda=False)
    assert hasil.dilewati_robots == 1
    assert hasil.diambil == 0
    assert list(db.scalars(select(BeritaEmiten))) == []


def test_galat_satu_artikel_tidak_menghentikan_sisanya(db, robots_izinkan):
    _berita(db, "Artikel gagal", "http://uji.test/gagal")
    _berita(db, "Artikel berhasil", "http://uji.test/ok")

    def tanggapi(r: httpx.Request) -> httpx.Response:
        if "gagal" in str(r.url):
            return httpx.Response(500, text="rusak")
        return httpx.Response(200, text=HALAMAN)

    with httpx.Client(transport=httpx.MockTransport(tanggapi)) as klien:
        hasil = perkaya_pemetaan(db, klien=klien, jeda=False)

    assert hasil.diperiksa == 2
    assert len(hasil.gagal) == 1
    assert hasil.terpetakan == 1


def test_batas_menghormati_jumlah_maksimum(db, robots_izinkan):
    for i in range(5):
        _berita(db, f"Berita {i}", f"http://uji.test/b{i}")
    with _klien() as klien:
        hasil = perkaya_pemetaan(db, batas=2, klien=klien, jeda=False)
    assert hasil.diperiksa == 2


def test_isi_artikel_tidak_disimpan(db, robots_izinkan):
    """NF-09: halaman dipakai untuk mencocokkan lalu dibuang. Yang tersimpan
    hanya kutipan pendek, bukan seluruh badan artikel."""
    b = _berita(db, "Daftar Lengkap 8 Blok Migas Dilelang", "http://uji.test/5")
    with _klien() as klien:
        perkaya_pemetaan(db, klien=klien, jeda=False)

    db.refresh(b)
    assert b.ringkasan in (None, "")
    kutipan = db.scalar(select(BeritaEmiten)).kutipan
    assert len(kutipan) < 200
    assert "Hak cipta" not in kutipan


def test_lapor_dipanggil_per_artikel(db, robots_izinkan):
    """Proses ini bisa berjalan beberapa menit; laporan jalan wajib ada supaya
    proses lambat bisa dibedakan dari proses yang menggantung."""
    _berita(db, "Daftar Lengkap 8 Blok Migas Dilelang", "http://uji.test/l1")
    _berita(db, "Berita tanpa emiten sama sekali", "http://uji.test/l2")

    pesan: list[str] = []
    with _klien() as klien:
        perkaya_pemetaan(db, klien=klien, jeda=False, lapor=pesan.append)

    assert any("2 berita belum diperkaya" in p for p in pesan)
    assert sum(1 for p in pesan if p.startswith("[")) == 2
    assert any("cocok" in p and "MEDC" in p for p in pesan)


# --------------------------------------------- penandaan agar tidak diulang


def test_artikel_nihil_tidak_diambil_dua_kali(db, robots_izinkan):
    """Hasil nihil pun sebuah jawaban. Mengambilnya lagi tiap siklus hanya
    membebani portal dan membuat siklus tidak pernah selesai."""
    _berita(db, "Berita tanpa emiten sama sekali", "http://uji.test/n1")

    with _klien(html="<html><body><p>Tidak ada emiten di sini</p></body></html>") as klien:
        pertama = perkaya_pemetaan(db, klien=klien, jeda=False)
        kedua = perkaya_pemetaan(db, klien=klien, jeda=False)

    assert pertama.diambil == 1
    assert kedua.diperiksa == 0

    catatan = db.scalar(select(PengayaanBerita))
    assert catatan.jumlah_kaitan == 0
    assert catatan.berhasil_diambil is True


def test_artikel_gagal_diambil_masih_dicoba_lagi(db, robots_izinkan):
    """Kegagalan jaringan bisa bersifat sesaat, jadi bukan jawaban akhir."""
    _berita(db, "Artikel gagal", "http://uji.test/g1")

    with _klien(status=500) as klien:
        perkaya_pemetaan(db, klien=klien, jeda=False)
        kedua = perkaya_pemetaan(db, klien=klien, jeda=False)

    assert kedua.diperiksa == 1
    assert db.scalar(select(PengayaanBerita)).berhasil_diambil is False


def test_ulangi_memaksa_pengambilan_ulang(db, robots_izinkan):
    """Dipakai setelah daftar emiten diperluas: artikel yang tadinya nihil bisa
    jadi cocok dengan emiten yang baru ditambahkan."""
    _berita(db, "Berita tanpa emiten sama sekali", "http://uji.test/n2")

    with _klien(html="<html><body><p>kosong</p></body></html>") as klien:
        perkaya_pemetaan(db, klien=klien, jeda=False)
        kedua = perkaya_pemetaan(db, klien=klien, jeda=False, ulangi=True)

    assert kedua.diperiksa == 1


def test_sisa_dilaporkan_saat_batas_tercapai(db, robots_izinkan):
    for i in range(5):
        _berita(db, f"Berita {i}", f"http://uji.test/s{i}")
    with _klien() as klien:
        hasil = perkaya_pemetaan(db, batas=2, klien=klien, jeda=False)
    assert hasil.diperiksa == 2
    assert hasil.sisa == 3


def test_perkaya_sampai_habis_menghabiskan_sisa(db, robots_izinkan):
    from app.ingest.pengaya import perkaya_sampai_habis

    for i in range(7):
        _berita(db, f"Berita {i}", f"http://uji.test/h{i}")

    with _klien(html="<html><body><p>kosong</p></body></html>") as klien:
        hasil = perkaya_sampai_habis(db, batas_per_putaran=3, klien=klien, jeda=False)

    assert hasil.diperiksa == 7
    assert hasil.sisa == 0


def test_perkaya_sampai_habis_berhenti_saat_kosong(db, robots_izinkan):
    from app.ingest.pengaya import perkaya_sampai_habis

    with _klien() as klien:
        hasil = perkaya_sampai_habis(db, klien=klien, jeda=False)
    assert hasil.diperiksa == 0


def test_ulangi_hanya_pada_putaran_pertama(db, robots_izinkan):
    """Tanpa pembatasan ini, --semua --ulangi akan mengambil artikel yang sama
    berulang-ulang sampai batas putaran."""
    from app.ingest.pengaya import perkaya_sampai_habis

    _berita(db, "Berita tanpa emiten", "http://uji.test/u1")
    with _klien(html="<html><body><p>kosong</p></body></html>") as klien:
        perkaya_sampai_habis(db, batas_per_putaran=1, klien=klien, jeda=False)
        hasil = perkaya_sampai_habis(
            db, batas_per_putaran=1, klien=klien, jeda=False, ulangi=True
        )
    assert hasil.diperiksa == 1


# ------------------------------------------- penyaringan blok rekomendasi

HALAMAN_REKOMENDASI = """
<html><body>
<p>Serangan udara ke sebuah sekolah di Iran menewaskan puluhan orang menurut PBB.</p>
<div class="berita-terkait">
  <p>Harga Nikel Naik, Simak Prospek Aneka Tambang Tbk Pekan Ini di Bursa</p>
</div>
<p>Baca juga: Saham Medco Energi melesat 5 persen pada perdagangan hari ini</p>
<ul class="populer">
  <li><a href="#">Bank Central Asia Tbk Rilis Laporan Keuangan Kuartal III Tahun Ini</a></li>
</ul>
<p>Dewan Keamanan PBB dijadwalkan menggelar sidang darurat pada pekan depan ini.</p>
</body></html>
"""


def test_blok_berita_terkait_tidak_ikut_terbaca():
    """Berita perang tidak boleh terpetakan ke emiten tambang hanya karena ada
    tautan rekomendasi di sampingnya."""
    teks = ekstrak_teks(HALAMAN_REKOMENDASI)
    assert "Aneka Tambang" not in teks
    assert "Bank Central Asia" not in teks
    assert "Dewan Keamanan PBB" in teks


def test_sisipan_baca_juga_dibuang():
    teks = ekstrak_teks(HALAMAN_REKOMENDASI)
    assert "Medco" not in teks


def test_paragraf_pendek_dibuang():
    """Teaser dan keterangan gambar hampir selalu pendek."""
    html = "<html><body><p>BBCA</p><p>" + "kalimat panjang " * 5 + "</p></body></html>"
    assert "BBCA" not in ekstrak_teks(html)


def test_paragraf_yang_didominasi_tautan_dibuang():
    html = (
        "<html><body><p><a href='#'>Telkom Indonesia Tbk Umumkan Dividen Interim</a></p>"
        "</body></html>"
    )
    assert "Telkom" not in ekstrak_teks(html)


def test_isi_artikel_yang_sah_tetap_terbaca(db, robots_izinkan):
    """Penyaring tidak boleh sampai membuang kalimat artikel yang benar."""
    _berita(db, "Blok migas dilelang", "http://uji.test/p1")
    with _klien() as klien:
        hasil = perkaya_pemetaan(db, klien=klien, jeda=False)
    assert hasil.terpetakan == 1


def test_sisipan_baca_juga_di_tengah_paragraf_dipotong():
    """Kontan menyisipkan 'Baca Juga:' di tengah kalimat. Bentuk inilah yang
    memetakan berita kurs rupiah ke EXCL pada uji nyata."""
    html = (
        "<html><body><p>Rupiah tertekan tujuh hari beruntun hingga menyentuh "
        "Rp 17.900 per dolar AS. Baca Juga: XLSMART (EXCL) Pasang Strategi Demi "
        "Hadapi Era Suku Bunga Tinggi</p></body></html>"
    )
    teks = ekstrak_teks(html)
    assert "Rupiah tertekan" in teks
    assert "EXCL" not in teks
    assert "XLSMART" not in teks


def test_kalimat_sebelum_sisipan_tetap_utuh():
    """Pemotongan tidak boleh ikut membuang kalimat artikel yang sah."""
    html = (
        "<html><body><p>Perseroan membukukan laba bersih yang tumbuh dua digit "
        "sepanjang semester pertama tahun ini. Simak juga: artikel lain yang "
        "tidak relevan</p></body></html>"
    )
    teks = ekstrak_teks(html)
    assert "laba bersih yang tumbuh dua digit" in teks
    assert "tidak relevan" not in teks
