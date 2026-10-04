"""Uji pembanding klasik TF-IDF + Naive Bayes / SVM (SRS 10.2)."""

from __future__ import annotations

import pytest

pytest.importorskip("sklearn")
joblib = pytest.importorskip("joblib")

from app.klasifikasi.dataset import Contoh, teks_target  # noqa: E402
from app.klasifikasi.klasik import (  # noqa: E402
    KISI,
    PengklasifikasiKlasik,
    latih,
    lokasi_model,
    masukan,
)
from app.models import Sentimen  # noqa: E402

POLA = {
    Sentimen.POSITIF: ["laba melonjak tajam", "dividen naik", "saham menguat net buy asing"],
    Sentimen.NEGATIF: ["rugi membengkak", "saham anjlok net sell asing", "laba turun tajam"],
    Sentimen.NETRAL: ["rapat umum pemegang saham digelar", "jadwal pembagian kupon", "emiten umumkan agenda"],
}


def _contoh(bagian: str, ulang: int) -> list[Contoh]:
    hasil = []
    nomor = 0
    for sentimen, kalimat in POLA.items():
        for _ in range(ulang):
            for k in kalimat:
                nomor += 1
                hasil.append(Contoh(
                    berita_id=nomor, kode="BBCA", teks=f"Berita {nomor}: {k}",
                    target=teks_target("BBCA", "Bank Central Asia Tbk", k),
                    sentimen=sentimen, bagian=bagian,
                ))
    return hasil


@pytest.mark.parametrize("jenis", ["nb", "svm"])
def test_belajar_membedakan_tiga_kelas(jenis):
    hasil = latih(jenis, _contoh("latih", 3), _contoh("validasi", 1))
    model = PengklasifikasiKlasik(jenis, pipeline=hasil.pipeline)

    tebak = model.prediksi_emiten_banyak([
        ("Laba BBCA melonjak tajam", "BBCA (Bank Central Asia Tbk)."),
        ("Saham BBCA anjlok net sell asing", "BBCA (Bank Central Asia Tbk)."),
    ])
    assert [p.sentimen for p in tebak] == [Sentimen.POSITIF, Sentimen.NEGATIF]
    assert all(0 < p.keyakinan <= 1 for p in tebak)


@pytest.mark.parametrize("jenis", ["nb", "svm"])
def test_hiperparameter_dipilih_dari_kisi_dan_semua_percobaan_dicatat(jenis):
    hasil = latih(jenis, _contoh("latih", 2), _contoh("validasi", 1))
    assert hasil.param in KISI[jenis]
    assert len(hasil.percobaan) == len(KISI[jenis])
    assert hasil.f1_validasi == max(f1 for _, f1 in hasil.percobaan)


def test_masukan_sama_dengan_pasangan_kalimat_indobert():
    # model klasik harus membaca informasi yang sama dengan IndoBERT,
    # supaya selisih kinerja mencerminkan metode, bukan masukan
    assert masukan("Judul. Ringkasan", "BBCA (Bank Central Asia Tbk). kutipan") == \
        "Judul. Ringkasan BBCA (Bank Central Asia Tbk). kutipan"


def test_simpan_dan_muat_ulang_menghasilkan_tebakan_sama(tmp_path):
    hasil = latih("svm", _contoh("latih", 2), _contoh("validasi", 1))
    jalur = lokasi_model("svm", tmp_path)
    joblib.dump({"pipeline": hasil.pipeline, "metrik": {}}, jalur)

    asli = PengklasifikasiKlasik("svm", pipeline=hasil.pipeline)
    dimuat = PengklasifikasiKlasik("svm", lokasi=jalur)
    pasangan = [("dividen naik", "BBCA"), ("rugi membengkak", "BBCA")]
    assert asli.prediksi_emiten_banyak(pasangan) == dimuat.prediksi_emiten_banyak(pasangan)
    assert dimuat.versi == "svm-tfidf-v1"


def test_model_belum_dilatih_memberi_petunjuk(tmp_path):
    with pytest.raises(FileNotFoundError, match="latih_klasik"):
        PengklasifikasiKlasik("nb", lokasi=tmp_path / "tidak-ada.joblib")
