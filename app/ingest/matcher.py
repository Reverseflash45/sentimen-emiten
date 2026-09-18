"""Pemetaan berita ke emiten (SRS 10.1 butir 2).

Dua cara pencocokan:
1. Kode emiten — dicari sebagai kata utuh, dan hanya diterima bila muncul dalam
   konteks pasar modal. Tanpa syarat ini, kode seperti "INCO" atau "ACES" akan
   salah tangkap pada kalimat berbahasa Inggris.
2. Nama perusahaan atau aliasnya.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingest.cleaner import normalisasi

# Kata yang menandakan teks memang membicarakan saham/emiten.
PETUNJUK_PASAR = (
    "saham", "emiten", "bursa", "idx", "bei", "ihsg", "tbk", "rups",
    "dividen", "laba", "rugi", "obligasi", "investor", "kode", "ticker",
)

# Kode yang juga merupakan kata umum — butuh petunjuk pasar di sekitarnya.
KODE_AMBIGU = {"INCO", "ACES", "AMAN", "BEST", "CARE", "CITY", "GOOD", "HERO",
               "HOME", "LIFE", "NATO", "PURE", "REAL", "SAME", "SOLA", "STAR",
               "TAPE", "TIME", "TRUE", "WOOD", "MAPI", "DATA", "IDEA"}


@dataclass(frozen=True)
class Kecocokan:
    kode: str
    cara: str        # "kode" atau "nama"
    kutipan: str     # potongan teks tempat kecocokan ditemukan


def _kutipan(teks: str, posisi: int, lebar: int = 90) -> str:
    awal = max(0, posisi - lebar // 2)
    akhir = min(len(teks), posisi + lebar // 2)
    potongan = teks[awal:akhir].strip()
    return ("…" if awal > 0 else "") + potongan + ("…" if akhir < len(teks) else "")


def ada_petunjuk_pasar(teks_normal: str) -> bool:
    return any(p in teks_normal for p in PETUNJUK_PASAR)


def cocokkan(
    teks: str,
    daftar_emiten: dict[str, list[str]],
) -> list[Kecocokan]:
    """Mencari emiten yang disebut dalam teks.

    `daftar_emiten` memetakan kode emiten ke daftar nama/alias-nya.
    Mengembalikan paling banyak satu kecocokan per emiten.
    """
    hasil: dict[str, Kecocokan] = {}
    normal = normalisasi(teks)
    punya_petunjuk = ada_petunjuk_pasar(normal)

    for kode, nama_list in daftar_emiten.items():
        # --- cocokkan lewat kode ---
        pola_kode = re.compile(rf"\b{re.escape(kode)}\b")
        m = pola_kode.search(teks)
        if m:
            perlu_petunjuk = kode.upper() in KODE_AMBIGU
            if not perlu_petunjuk or punya_petunjuk:
                hasil[kode] = Kecocokan(kode, "kode", _kutipan(teks, m.start()))
                continue

        # --- cocokkan lewat nama / alias ---
        for nama in nama_list:
            nama_normal = normalisasi(nama)
            if len(nama_normal) < 4:
                continue
            # Batas kata wajib. Tanpa ini "menghantam" memuat "antam", dan
            # sebuah berita serangan udara terpetakan ke Aneka Tambang — itu
            # betul-betul terjadi pada uji nyata.
            m = re.search(rf"\b{re.escape(nama_normal)}\b", normal)
            if m:
                hasil[kode] = Kecocokan(kode, "nama", _kutipan(normal, m.start()))
                break

    return sorted(hasil.values(), key=lambda k: k.kode)
