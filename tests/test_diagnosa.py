"""Uji diagnosa pemetaan dan bobot dilusi berita multi-emiten."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.analitik.agregasi import bobot_dilusi, hitung_skor_harian
from app.ingest.diagnosa import diagnosa, kode_kandidat
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

WAKTU = datetime(2026, 9, 18, 6, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------ kode kandidat


def test_mengenali_kode_emiten_di_judul():
    assert kode_kandidat("Beli Jumbo Saham BKSL, Porsi Samuel Sekuritas Naik") == ["BKSL"]


def test_singkatan_umum_bukan_kode():
    """Tanpa penyaringan ini, RUPS dan IHSG akan terhitung sebagai emiten."""
    assert kode_kandidat("Tanpa RUPS, IHSG Ditutup Melemah") == []
    assert kode_kandidat("OJK Terbitkan 2 POJK Baru") == []


def test_kode_tidak_digandakan():
    assert kode_kandidat("BBCA naik, BBCA turun, lalu BBCA datar") == ["BBCA"]


def test_judul_tanpa_kode():
    assert kode_kandidat("Belanja Pemerintah Tembus Rp 2.295 Triliun") == []


# ------------------------------------------------------------------ diagnosa


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False, future=True)()
    s.add(Emiten(kode="BBCA", nama="Bank Central Asia Tbk"))
    s.add(Emiten(kode="TLKM", nama="Telkom Indonesia Tbk"))
    s.add(SumberBerita(nama="Uji", domain="uji.test",
                       kredibilitas=Kredibilitas.TERVERIFIKASI_DEWAN_PERS))
    s.commit()
    yield s
    s.close()


def _berita(session, judul: str, url: str, emiten_ids: list[int] | None = None) -> Berita:
    b = Berita(sumber_id=1, judul=judul, url=url, sidik_jari=url, terbit_pada=WAKTU)
    session.add(b)
    session.flush()
    for eid in emiten_ids or []:
        session.add(BeritaEmiten(berita_id=b.id, emiten_id=eid, cara_cocok="kode"))
    session.commit()
    return b


def test_memisahkan_luar_cakupan_dari_kegagalan(db):
    _berita(db, "Beli Jumbo Saham BKSL, Porsi Naik", "http://u/1")          # luar cakupan
    _berita(db, "Pola Transaksi Saham ASPI Masuk UMA", "http://u/2")        # luar cakupan
    _berita(db, "Saham BBCA Ditutup Menguat", "http://u/3")                 # TERLEWAT
    _berita(db, "Belanja Pemerintah Tembus Rp 2.295 Triliun", "http://u/4")  # tanpa kode

    h = diagnosa(db)
    assert h.total_tanpa_emiten == 4
    assert h.menyebut_kode_luar_cakupan == 2
    assert h.menyebut_kode_dipantau == 1
    assert h.tanpa_kode_apa_pun == 1
    assert h.kode_luar_cakupan.most_common(2) == [("BKSL", 1), ("ASPI", 1)] or set(
        h.kode_luar_cakupan
    ) == {"BKSL", "ASPI"}


def test_berita_terpetakan_tidak_ikut_didiagnosa(db):
    _berita(db, "Saham BBCA Menguat", "http://u/5", emiten_ids=[1])
    assert diagnosa(db).total_tanpa_emiten == 0


def test_contoh_terlewat_menyertakan_kodenya(db):
    _berita(db, "Saham BBCA dan TLKM Kompak Menguat", "http://u/6")
    h = diagnosa(db)
    assert len(h.contoh_terlewat) == 1
    _, _, kode = h.contoh_terlewat[0]
    assert set(kode) == {"BBCA", "TLKM"}


def test_persen_luar_cakupan_nol_saat_kosong(db):
    assert diagnosa(db).persen_luar_cakupan == 0.0


# ------------------------------------------------------------- bobot dilusi


def test_bobot_dilusi():
    assert bobot_dilusi(1) == 1.0
    assert bobot_dilusi(5) == pytest.approx(0.2)
    assert bobot_dilusi(0) == 1.0   # tidak boleh bagi nol


def test_artikel_rekap_pasar_tidak_menggeser_skor_sekuat_berita_khusus(db):
    """Satu artikel rekap yang menyebut dua emiten tidak boleh menyumbang bobot
    penuh ke keduanya, sementara berita khusus satu emiten tetap penuh."""
    rekap = _berita(db, "ANALIS MARKET: IHSG Bearish", "http://u/r", emiten_ids=[1, 2])
    khusus = _berita(db, "BBCA bagikan dividen", "http://u/k", emiten_ids=[1])

    db.add(LabelSentimen(berita_id=rekap.id, emiten_id=1, sentimen=Sentimen.NEGATIF,
                         keyakinan=1.0, asal=AsalLabel.MODEL, versi_model="v1"))
    db.add(LabelSentimen(berita_id=khusus.id, emiten_id=1, sentimen=Sentimen.POSITIF,
                         keyakinan=1.0, asal=AsalLabel.MODEL, versi_model="v1"))
    db.commit()

    skor = hitung_skor_harian(db, "BBCA", WAKTU.date(), WAKTU.date())
    assert len(skor) == 1
    # berita khusus berbobot 1.0 (positif), rekap berbobot 0.5 (negatif)
    # skor = (1*1.0 + -1*0.5) / 1.5 = +0.3333
    assert skor[0].skor == pytest.approx(0.3333, abs=1e-4)


def test_tanpa_dilusi_hasilnya_akan_netral(db):
    """Pembanding: kalau bobotnya sama, kedua berita saling menghapus dan skornya
    nol — itu yang terjadi sebelum aturan dilusi ada."""
    rekap = _berita(db, "ANALIS MARKET: IHSG Bearish", "http://u/r2", emiten_ids=[1])
    khusus = _berita(db, "BBCA bagikan dividen", "http://u/k2", emiten_ids=[1])
    db.add(LabelSentimen(berita_id=rekap.id, emiten_id=1, sentimen=Sentimen.NEGATIF,
                         keyakinan=1.0, asal=AsalLabel.MODEL, versi_model="v1"))
    db.add(LabelSentimen(berita_id=khusus.id, emiten_id=1, sentimen=Sentimen.POSITIF,
                         keyakinan=1.0, asal=AsalLabel.MODEL, versi_model="v1"))
    db.commit()

    skor = hitung_skor_harian(db, "BBCA", WAKTU.date(), WAKTU.date())
    assert skor[0].skor == pytest.approx(0.0)


# ------------------------------------------ penyaringan artikel rekap pasar


def test_batas_emiten_membuang_artikel_rekap(db):
    """Uji kepekaan: artikel yang menyebut banyak emiten bisa dikeluarkan untuk
    melihat apakah sinyalnya bertahan tanpa rekap pasar."""
    rekap = _berita(db, "ANALIS MARKET: IHSG Bearish", "http://u/r3", emiten_ids=[1, 2])
    khusus = _berita(db, "BBCA bagikan dividen", "http://u/k3", emiten_ids=[1])
    db.add(LabelSentimen(berita_id=rekap.id, emiten_id=1, sentimen=Sentimen.NEGATIF,
                         keyakinan=1.0, asal=AsalLabel.MODEL, versi_model="v1"))
    db.add(LabelSentimen(berita_id=khusus.id, emiten_id=1, sentimen=Sentimen.POSITIF,
                         keyakinan=1.0, asal=AsalLabel.MODEL, versi_model="v1"))
    db.commit()

    semua = hitung_skor_harian(db, "BBCA", WAKTU.date(), WAKTU.date())
    tanpa_rekap = hitung_skor_harian(
        db, "BBCA", WAKTU.date(), WAKTU.date(), maks_emiten_per_berita=1
    )

    assert semua[0].jumlah_berita == 2
    assert tanpa_rekap[0].jumlah_berita == 1
    # tanpa rekap negatif, tinggal berita positif saja
    assert tanpa_rekap[0].skor == pytest.approx(1.0)


def test_batas_longgar_tidak_membuang_apa_pun(db):
    rekap = _berita(db, "Rekap", "http://u/r4", emiten_ids=[1, 2])
    db.add(LabelSentimen(berita_id=rekap.id, emiten_id=1, sentimen=Sentimen.POSITIF,
                         keyakinan=1.0, asal=AsalLabel.MODEL, versi_model="v1"))
    db.commit()
    hasil = hitung_skor_harian(
        db, "BBCA", WAKTU.date(), WAKTU.date(), maks_emiten_per_berita=5
    )
    assert hasil[0].jumlah_berita == 1
