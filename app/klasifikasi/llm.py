"""Pengklasifikasi LLM zero-shot lewat Ollama (lokal, gratis).

Perannya dua, dan keduanya harus disebut terang di laporan:

1. **Metode pembanding.** LLM menilai sentimen tanpa dilatih pada data ini —
   hanya diberi pedoman anotasi yang sama persis dengan anotator manusia
   (app/klasifikasi/pedoman.py). Hasilnya diuji pada data uji berlabel manusia
   bersama leksikon, NB, SVM, dan IndoBERT.
2. **Pelabel data latih (label perak).** Labelnya dipakai sebagai data latih
   NB/SVM/IndoBERT, karena label manusia yang tersedia terlalu sedikit. Label
   perak TIDAK PERNAH dipakai sebagai data uji: data uji tetap label manusia
   yang dibuat tanpa melihat prediksi model mana pun.

Reprodusibilitas: nama model, temperature 0, dan seed tetap dicatat di versi
label, sehingga pelabelan bisa diulang orang lain dengan perintah yang sama.

Keyakinan diambil dari peluang token pertama jawaban (logprobs) bila Ollama
menyediakannya; bila tidak, keyakinan diisi 0,5 dan hal itu dicatat — angka
keyakinan buatan lebih buruk daripada tidak ada angka.
"""

from __future__ import annotations

import math
import os

import httpx

from app.klasifikasi.basis import Pengklasifikasi, Prediksi
from app.klasifikasi.pedoman import PEDOMAN
from app.models import Sentimen

MODEL_BAWAAN = "qwen2.5:7b"
ALAMAT_BAWAAN = "http://127.0.0.1:11434"
SEED = 42

# baris "x TIDAK RELEVAN" dibuang: menolak pemetaan adalah keputusan manusia
PEDOMAN_LLM = "\n".join(
    b for b in PEDOMAN.strip().splitlines()
    if not b.lstrip().startswith("x TIDAK RELEVAN") and "Tidak dijadikan label" not in b
    and "(mis. \"bank mandiri\"" not in b
)

SISTEM = (
    "Kamu adalah anotator sentimen berita pasar modal Indonesia. Ikuti pedoman berikut dengan ketat.\n\n"
    + PEDOMAN_LLM
    + "\n\nJawab HANYA dengan satu kata huruf kecil: positif, netral, atau negatif."
)


def pesan_pengguna(teks: str, target: str) -> str:
    return f"Berita: {teks}\n\nEmiten yang dinilai: {target}\n\nSentimen terhadap emiten ini:"


def baca_jawaban(isi: str) -> Sentimen | None:
    kata = isi.strip().lower().strip(".:\"' \n")
    for s in Sentimen:
        if kata.startswith(s.value):
            return s
    return None


class PengklasifikasiLLM(Pengklasifikasi):
    per_emiten = True

    def __init__(self, model: str | None = None, alamat: str | None = None, batas_waktu: float = 120) -> None:
        self.model = model or os.environ.get("MODEL_LLM") or MODEL_BAWAAN
        self.alamat = (alamat or os.environ.get("OLLAMA_HOST") or ALAMAT_BAWAAN).rstrip("/")
        self.versi = f"llm-{self.model.replace(':', '-')}"
        self.klien = httpx.Client(timeout=batas_waktu)
        self.ada_logprobs: bool | None = None

    def prediksi(self, teks: str) -> Prediksi:
        return self.prediksi_emiten(teks, "")

    def prediksi_emiten(self, teks: str, target: str) -> Prediksi:
        r = self.klien.post(f"{self.alamat}/api/chat", json={
            "model": self.model,
            "stream": False,
            "messages": [{"role": "system", "content": SISTEM},
                         {"role": "user", "content": pesan_pengguna(teks, target)}],
            "options": {"temperature": 0, "seed": SEED, "num_predict": 4, "num_ctx": 2048},
            "logprobs": True,
            "top_logprobs": 10,
            "keep_alive": "10m",
        })
        r.raise_for_status()
        data = r.json()
        sentimen = baca_jawaban(data["message"]["content"])
        if sentimen is None:
            # jawaban di luar tiga kelas: pilih netral sesuai pedoman ("ragu → netral")
            return Prediksi(sentimen=Sentimen.NETRAL, keyakinan=0.0,
                            penjelasan=f"jawaban tak dikenal: {data['message']['content'][:40]!r}")
        return Prediksi(sentimen=sentimen, keyakinan=self._keyakinan(data, sentimen))

    def _keyakinan(self, data: dict, sentimen: Sentimen) -> float:
        """Peluang kelas terpilih dari token pertama, dinormalkan atas tiga kelas."""
        lp = data.get("logprobs") or []
        if not lp:
            self.ada_logprobs = False
            return 0.5
        self.ada_logprobs = True
        pertama = lp[0]
        calon = pertama.get("top_logprobs") or [pertama]
        massa = {s: 0.0 for s in Sentimen}
        for c in calon:
            tok = (c.get("token") or "").strip().lower()
            if not tok:
                continue
            for s in Sentimen:
                if s.value.startswith(tok) or tok.startswith(s.value[: len(tok)]) and len(tok) >= 2:
                    massa[s] += math.exp(c.get("logprob", -99))
                    break
        total = sum(massa.values())
        return round(massa[sentimen] / total, 4) if total > 0 else 0.5

    def prediksi_emiten_banyak(self, pasangan: list[tuple[str, str]]) -> list[Prediksi]:
        return [self.prediksi_emiten(t, s) for t, s in pasangan]

    def lepas(self) -> None:
        """Mengosongkan VRAM — model 7B memakai ±5 GB, dan pelatihan IndoBERT
        setelahnya butuh GPU yang sama."""
        try:
            self.klien.post(f"{self.alamat}/api/generate", json={"model": self.model, "keep_alive": 0})
        except httpx.HTTPError:
            pass
