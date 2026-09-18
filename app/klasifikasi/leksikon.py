"""Baseline pengklasifikasi berbasis leksikon kata finansial Indonesia.

Ini BUKAN model akhir. Fungsinya dua:
1. membuat seluruh alur (kumpulkan → label → agregasi → korelasi) bisa
   dijalankan dan diuji sekarang, sebelum IndoBERT siap;
2. menjadi pembanding dasar. Sebuah model transformer baru layak dipakai kalau
   akurasinya mengalahkan baseline sesederhana ini — kalau tidak, ada yang
   salah pada pelatihannya.

Keterbatasan yang disadari: tidak memahami sarkasme, konteks kalimat panjang,
maupun kalimat majemuk. Negasi ditangani seadanya lewat kata ingkar terdekat.
"""

from __future__ import annotations

import re

from app.klasifikasi.basis import Pengklasifikasi, Prediksi
from app.models import Sentimen

KATA_POSITIF: dict[str, float] = {
    "laba": 1.0, "untung": 1.0, "keuntungan": 1.0, "cuan": 0.8,
    "naik": 0.8, "menguat": 1.0, "penguatan": 1.0, "melonjak": 1.2,
    "meroket": 1.2, "rebound": 1.0, "tumbuh": 1.0, "pertumbuhan": 1.0,
    "meningkat": 0.9, "peningkatan": 0.9, "ekspansi": 0.9, "dividen": 0.9,
    "surplus": 1.0, "rekor": 0.9, "tertinggi": 0.7, "optimistis": 0.8,
    "optimis": 0.8, "positif": 0.8, "akuisisi": 0.6, "kontrak": 0.5,
    "kerjasama": 0.5, "kemitraan": 0.5, "melampaui": 0.9, "solid": 0.8,
    "efisiensi": 0.6, "buyback": 0.6, "ekspor": 0.4, "investasi": 0.4,
}

KATA_NEGATIF: dict[str, float] = {
    "rugi": 1.0, "kerugian": 1.0, "merugi": 1.0, "turun": 0.8,
    "melemah": 1.0, "pelemahan": 1.0, "anjlok": 1.2, "ambles": 1.2,
    "merosot": 1.1, "terkoreksi": 0.8, "koreksi": 0.6, "tergerus": 0.9,
    "defisit": 1.0, "gagal": 0.9, "pailit": 1.4, "bangkrut": 1.4,
    "phk": 1.1, "sanksi": 1.0, "denda": 0.9, "gugatan": 0.9,
    "penyelidikan": 0.9, "suspensi": 1.2, "disuspensi": 1.2, "delisting": 1.3,
    "utang": 0.4, "beban": 0.4, "tekanan": 0.6, "negatif": 0.8,
    "terendah": 0.7, "penurunan": 0.9, "wanprestasi": 1.2, "restrukturisasi": 0.6,
}

KATA_INGKAR = {"tidak", "tak", "bukan", "belum", "tanpa", "gagal", "batal"}

_TOKEN = re.compile(r"[a-z0-9]+")

# di bawah ambang ini teks dianggap netral
AMBANG = 0.5


class PengklasifikasiLeksikon(Pengklasifikasi):
    versi = "leksikon-v1"

    def __init__(self, ambang: float = AMBANG) -> None:
        self.ambang = ambang

    def prediksi(self, teks: str) -> Prediksi:
        token = _TOKEN.findall((teks or "").lower())
        skor = 0.0
        pemicu: list[str] = []

        for i, kata in enumerate(token):
            bobot = KATA_POSITIF.get(kata)
            arah = 1.0
            if bobot is None:
                bobot = KATA_NEGATIF.get(kata)
                arah = -1.0
            if bobot is None:
                continue

            # negasi: satu atau dua kata sebelum kata sentimen
            konteks = token[max(0, i - 2) : i]
            if any(k in KATA_INGKAR for k in konteks):
                arah = -arah
                pemicu.append(f"!{kata}")
            else:
                pemicu.append(kata)
            skor += arah * bobot

        if skor > self.ambang:
            sentimen = Sentimen.POSITIF
        elif skor < -self.ambang:
            sentimen = Sentimen.NEGATIF
        else:
            sentimen = Sentimen.NETRAL

        # keyakinan dipetakan dari besarnya skor, dibatasi 0.95 supaya baseline
        # tidak pernah terlihat sepasti model terlatih
        keyakinan = min(0.95, abs(skor) / 3.0) if sentimen is not Sentimen.NETRAL else 0.5
        return Prediksi(sentimen, round(keyakinan, 3), ", ".join(pemicu) or None)
