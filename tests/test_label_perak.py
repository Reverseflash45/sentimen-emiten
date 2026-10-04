"""Uji label perak LLM: pemisahan dari data uji, prioritas label manusia,
pembacaan jawaban Ollama, dan Cohen's kappa."""

from __future__ import annotations

import json

import httpx
import pytest

from app.klasifikasi.dataset import bagian_data, muat_data_latih, versi_llm_terbaru
from app.klasifikasi.llm import PengklasifikasiLLM, baca_jawaban
from app.models import AsalLabel, Sentimen
from tests.test_dataset_ml import berita, db, label  # noqa: F401 — fixture dipakai ulang

PERAK = "llm-qwen2.5-7b"


def berita_di_bagian(db, bagian: str, mulai: int = 0):  # noqa: F811
    """Membuat berita sampai id-nya jatuh di bagian yang diminta."""
    for i in range(mulai, mulai + 200):
        b = berita(db, f"berita-{bagian}-{i}")
        if bagian_data(b.id) == bagian:
            return b
    raise AssertionError("tidak menemukan id di bagian itu")


def test_label_perak_tidak_pernah_masuk_data_uji(db):  # noqa: F811
    uji = berita_di_bagian(db, "uji")
    latih = berita_di_bagian(db, "latih", 300)
    label(db, uji, Sentimen.POSITIF, asal=AsalLabel.MODEL, versi=PERAK)
    label(db, latih, Sentimen.NEGATIF, asal=AsalLabel.MODEL, versi=PERAK)

    data = muat_data_latih(db, PERAK)
    assert [(c.berita_id, c.asal) for c in data] == [(latih.id, "perak")]
    assert all(c.bagian != "uji" for c in data)


def test_label_manusia_mengalahkan_label_perak(db):  # noqa: F811
    b = berita_di_bagian(db, "latih")
    label(db, b, Sentimen.NEGATIF, asal=AsalLabel.MODEL, versi=PERAK)
    label(db, b, Sentimen.POSITIF)  # anotasi manusia

    data = muat_data_latih(db, PERAK)
    assert [(c.sentimen, c.asal) for c in data] == [(Sentimen.POSITIF, "anotasi")]


def test_tanpa_perak_hanya_label_manusia(db):  # noqa: F811
    b = berita_di_bagian(db, "latih")
    label(db, b, Sentimen.NEGATIF, asal=AsalLabel.MODEL, versi=PERAK)
    assert muat_data_latih(db, None) == []
    assert versi_llm_terbaru(db) == PERAK


@pytest.mark.parametrize("jawaban, harapan", [
    ("positif", Sentimen.POSITIF), (" Negatif.", Sentimen.NEGATIF), ("netral\n", Sentimen.NETRAL),
    ("tidak tahu", None),
])
def test_baca_jawaban(jawaban, harapan):
    assert baca_jawaban(jawaban) == harapan


def _llm_tiruan(isi: str, logprobs=None) -> PengklasifikasiLLM:
    terkirim = {}

    def tangani(permintaan: httpx.Request) -> httpx.Response:
        terkirim.update(json.loads(permintaan.content))
        badan = {"message": {"role": "assistant", "content": isi}}
        if logprobs is not None:
            badan["logprobs"] = logprobs
        return httpx.Response(200, json=badan)

    llm = PengklasifikasiLLM("qwen2.5:7b", alamat="http://ollama.test")
    llm.klien = httpx.Client(transport=httpx.MockTransport(tangani))
    llm.terkirim = terkirim
    return llm


def test_keyakinan_dari_logprobs_dinormalkan_atas_tiga_kelas():
    import math

    llm = _llm_tiruan("positif", logprobs=[{"token": "pos", "logprob": math.log(0.6), "top_logprobs": [
        {"token": "pos", "logprob": math.log(0.6)},
        {"token": "net", "logprob": math.log(0.3)},
        {"token": "neg", "logprob": math.log(0.1)},
    ]}])
    pr = llm.prediksi_emiten("Laba BBCA naik", "BBCA (Bank Central Asia Tbk).")
    assert pr.sentimen == Sentimen.POSITIF
    assert pr.keyakinan == pytest.approx(0.6, abs=1e-3)
    # determinisme: suhu 0 dan seed tetap dikirim ke Ollama
    assert llm.terkirim["options"]["temperature"] == 0
    assert "seed" in llm.terkirim["options"]
    assert llm.versi == "llm-qwen2.5-7b"


def test_tanpa_logprobs_keyakinan_netral_dan_jawaban_aneh_jadi_netral():
    llm = _llm_tiruan("positif")
    assert llm.prediksi_emiten("x", "y").keyakinan == 0.5
    aneh = _llm_tiruan("saya tidak yakin").prediksi_emiten("x", "y")
    assert (aneh.sentimen, aneh.keyakinan) == (Sentimen.NETRAL, 0.0)


def test_pedoman_llm_sama_dengan_pedoman_manusia_tanpa_opsi_tidak_relevan():
    from app.klasifikasi.llm import SISTEM
    from app.klasifikasi.pedoman import PEDOMAN

    assert "1 POSITIF" in SISTEM and "3 NEGATIF" in SISTEM
    assert "TIDAK RELEVAN" not in SISTEM
    for baris in ("laba/pendapatan naik", "Ragu antara netral dan yang lain"):
        assert baris in PEDOMAN and baris in SISTEM


def test_kappa():
    from scripts.evaluasi_model import metrik

    benar = ["positif", "negatif", "netral", "positif"]
    assert metrik(benar, benar)["kappa"] == pytest.approx(1.0)
    # selalu menebak satu kelas: akurasi bisa lumayan, tetapi kappa 0
    assert metrik(benar, ["positif"] * 4)["kappa"] == pytest.approx(0.0)


def test_csv_anotator_kedua_simpan_dan_muat(tmp_path, monkeypatch):
    import scripts.label_anotator2 as a2

    monkeypatch.setattr(a2, "BERKAS", tmp_path / "anotator_2.csv")
    a2.simpan({(10, 1): ("BBCA", "positif", "2026-10-04T00:00:00+00:00"),
               (11, 2): ("BMRI", "tidak_relevan", "2026-10-04T00:01:00+00:00")})
    assert a2.muat() == {(10, 1): "positif", (11, 2): "tidak_relevan"}
    # waktu pencatatan asli dipertahankan saat disimpan ulang
    assert a2.muat_baris()[(10, 1)][2] == "2026-10-04T00:00:00+00:00"
