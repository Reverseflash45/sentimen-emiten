"""Perhitungan korelasi, ditulis sendiri tanpa SciPy.

Alasannya bukan menghindari pustaka, tapi supaya rumus yang dipakai terlihat
jelas dan bisa dipertanggungjawabkan saat sidang — termasuk cara menangani
nilai kembar pada Spearman.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class HasilKorelasi:
    koefisien: float
    n: int
    metode: str

    def kekuatan(self) -> str:
        a = abs(self.koefisien)
        if a < 0.2:
            return "sangat lemah"
        if a < 0.4:
            return "lemah"
        if a < 0.6:
            return "sedang"
        if a < 0.8:
            return "kuat"
        return "sangat kuat"


def _rerata(x: list[float]) -> float:
    return sum(x) / len(x)


def pearson(x: list[float], y: list[float]) -> HasilKorelasi:
    """Korelasi Pearson — mengukur hubungan linear."""
    if len(x) != len(y):
        raise ValueError("panjang kedua deret harus sama")
    n = len(x)
    if n < 3:
        raise ValueError("butuh minimal 3 pasang data")

    mx, my = _rerata(x), _rerata(y)
    pembilang = sum((a - mx) * (b - my) for a, b in zip(x, y))
    penyebut = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    if penyebut == 0:
        # salah satu deret konstan — korelasi tidak terdefinisi
        return HasilKorelasi(0.0, n, "pearson")
    return HasilKorelasi(pembilang / penyebut, n, "pearson")


def _peringkat(nilai: list[float]) -> list[float]:
    """Peringkat dengan nilai kembar diberi peringkat rata-rata."""
    urut = sorted(range(len(nilai)), key=lambda i: nilai[i])
    hasil = [0.0] * len(nilai)
    i = 0
    while i < len(urut):
        j = i
        while j + 1 < len(urut) and nilai[urut[j + 1]] == nilai[urut[i]]:
            j += 1
        rata = (i + j) / 2 + 1  # peringkat mulai dari 1
        for k in range(i, j + 1):
            hasil[urut[k]] = rata
        i = j + 1
    return hasil


def spearman(x: list[float], y: list[float]) -> HasilKorelasi:
    """Korelasi Spearman — hubungan monoton, tahan terhadap pencilan.

    Untuk data harga saham ini biasanya lebih jujur daripada Pearson, karena
    lonjakan satu hari tidak menyeret hasilnya.
    """
    hasil = pearson(_peringkat(x), _peringkat(y))
    return HasilKorelasi(hasil.koefisien, hasil.n, "spearman")


def imbal_hasil_harian(penutupan: list[float]) -> list[float]:
    """Imbal hasil harian: (harga_t - harga_t-1) / harga_t-1.

    Panjang hasil satu lebih pendek dari masukan.
    """
    hasil: list[float] = []
    for sebelum, sesudah in zip(penutupan, penutupan[1:]):
        hasil.append(0.0 if sebelum == 0 else (sesudah - sebelum) / sebelum)
    return hasil


def geser(deret: list[float], lag: int) -> list[float]:
    """Menggeser deret sebanyak `lag` langkah.

    Lag positif berarti deret ini mendahului: nilai hari ini dipasangkan dengan
    nilai deret lain `lag` hari kemudian. Dipakai untuk memeriksa apakah
    sentimen mendahului pergerakan harga atau justru mengikutinya.
    """
    if lag == 0:
        return list(deret)
    if lag > 0:
        return deret[:-lag] if lag < len(deret) else []
    return deret[-lag:]
