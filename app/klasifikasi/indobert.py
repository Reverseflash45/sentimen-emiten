"""Pengklasifikasi IndoBERT hasil fine-tuning (lihat scripts/latih_indobert.py).

Pustaka torch/transformers diimpor saat kelas ini dipakai, bukan saat modul
dimuat: server web (Vercel) tidak memasangnya dan tidak memerlukannya, karena
pelabelan dijalankan oleh penjadwal, bukan oleh API.

Lokasi model bisa berupa folder lokal atau id Hugging Face Hub, diatur lewat
variabel lingkungan MODEL_INDOBERT (bawaan: model/indobert-sentimen).
"""

from __future__ import annotations

import os

from app.klasifikasi.basis import Pengklasifikasi, Prediksi
from app.models import Sentimen

LOKASI_BAWAAN = "model/indobert-sentimen"
PANJANG_MAKS = 192


class PengklasifikasiIndoBERT(Pengklasifikasi):
    versi = "indobert-v1"
    per_emiten = True

    def __init__(self, lokasi: str | None = None, ukuran_batch: int = 32) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self.lokasi = lokasi or os.environ.get("MODEL_INDOBERT") or LOKASI_BAWAAN
        self.perangkat = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(self.lokasi)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.lokasi).to(self.perangkat).eval()
        self.ukuran_batch = ukuran_batch
        # urutan kelas dibaca dari konfigurasi model, bukan diasumsikan
        self.kelas = [Sentimen(self.model.config.id2label[i]) for i in range(self.model.config.num_labels)]

    def prediksi(self, teks: str) -> Prediksi:
        return self.prediksi_emiten(teks, "")

    def prediksi_emiten(self, teks: str, target: str) -> Prediksi:
        return self.prediksi_emiten_banyak([(teks, target)])[0]

    def prediksi_emiten_banyak(self, pasangan: list[tuple[str, str]]) -> list[Prediksi]:
        hasil: list[Prediksi] = []
        torch = self._torch
        for i in range(0, len(pasangan), self.ukuran_batch):
            potong = pasangan[i : i + self.ukuran_batch]
            masukan = self.tokenizer(
                [t for t, _ in potong], [s for _, s in potong],  # selalu berpasangan, sama seperti saat dilatih
                truncation="longest_first", max_length=PANJANG_MAKS, padding=True, return_tensors="pt",
            ).to(self.perangkat)
            with torch.inference_mode():
                peluang = torch.softmax(self.model(**masukan).logits.float(), dim=-1).cpu()
            for p in peluang:
                j = int(p.argmax())
                hasil.append(Prediksi(sentimen=self.kelas[j], keyakinan=float(p[j])))
        return hasil
