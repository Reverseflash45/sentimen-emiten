"""Menampilkan pemetaan berita-emiten beserta kutipan buktinya.

    python -m scripts.periksa_pemetaan
    python -m scripts.periksa_pemetaan --kode ANTM
    python -m scripts.periksa_pemetaan --cara nama --jumlah 40

Dipakai untuk memeriksa PRESISI pemetaan dengan mata sendiri. Rasio pemetaan
yang tinggi tidak ada gunanya kalau sebagiannya salah: satu pemetaan keliru
menyuntikkan sentimen yang salah ke skor sebuah emiten, dan setelah teragregasi
kesalahan itu tidak kelihatan lagi.

Ambil sampel acak, periksa satu per satu, lalu catat berapa yang benar. Angka
itu adalah presisi pemetaan — dan itu angka yang pantas masuk laporan, bukan
klaim "pemetaan bekerja dengan baik".

Emiten yang sudah keluar dari komposisi LQ45 tidak ikut ditampilkan secara
bawaan. Pemetaan ke emiten itu bukan kesalahan — beritanya memang menyebutnya,
dan pemetaannya dibuat ketika emiten itu masih dipantau — tapi ia di luar
cakupan periode yang sedang diteliti, jadi tidak boleh ikut dihitung saat
mengukur presisi. Pakai --termasuk-nonaktif untuk melihatnya.
"""

from __future__ import annotations

import argparse
import random

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Berita, BeritaEmiten, Emiten


def main() -> None:
    p = argparse.ArgumentParser(description="Periksa presisi pemetaan berita-emiten")
    p.add_argument("--kode", default=None, help="batasi ke satu emiten")
    p.add_argument("--cara", choices=["kode", "nama"], default=None,
                   help="batasi ke cara pencocokan tertentu")
    p.add_argument("--jumlah", type=int, default=20, help="banyak sampel (bawaan 20)")
    p.add_argument("--termasuk-nonaktif", action="store_true",
                   help="ikut tampilkan pemetaan ke emiten yang sudah keluar "
                        "dari komposisi LQ45 periode ini")
    p.add_argument("--acak", action="store_true",
                   help="ambil sampel acak, bukan yang terbaru — lebih layak "
                        "dipakai untuk mengukur presisi")
    a = p.parse_args()

    with SessionLocal() as session:
        kueri = (
            select(BeritaEmiten, Berita, Emiten)
            .join(Berita, Berita.id == BeritaEmiten.berita_id)
            .join(Emiten, Emiten.id == BeritaEmiten.emiten_id)
        )
        if a.kode:
            kueri = kueri.where(Emiten.kode == a.kode.upper())
        if a.cara:
            kueri = kueri.where(BeritaEmiten.cara_cocok == a.cara)
        if not a.termasuk_nonaktif:
            # Pemetaan ke emiten yang sudah keluar komposisi TIDAK salah — berita
            # itu memang menyebutnya, dan pemetaannya dibuat ketika emiten itu
            # masih dipantau. Tapi ia di luar cakupan periode ini, jadi tidak
            # boleh ikut dihitung saat mengukur presisi.
            kueri = kueri.where(Emiten.aktif.is_(True))

        baris = list(session.execute(kueri).all())
        if not baris:
            print("Belum ada pemetaan yang cocok dengan saringan itu.")
            return

        total = len(baris)
        sampel = random.sample(baris, min(a.jumlah, total)) if a.acak else baris[-a.jumlah:]

        for kaitan, berita, emiten in sampel:
            tanda = "" if emiten.aktif else "  (NONAKTIF — di luar LQ45 periode ini)"
            print(f"\n[{emiten.kode}] lewat {kaitan.cara_cocok}{tanda}")
            print(f"  judul   : {berita.judul[:100]}")
            print(f"  kutipan : {(kaitan.kutipan or '(tidak ada)')[:140]}")
            print(f"  tautan  : {berita.url}")

        print(f"\n{len(sampel)} sampel dari {total} pemetaan"
              + ("" if a.termasuk_nonaktif else " (emiten aktif saja)") + ".")
        print(
            "Periksa tiap kutipan: apakah berita itu memang membahas emiten\n"
            "tersebut? Kutipan yang isinya judul artikel lain menandakan blok\n"
            "rekomendasi ikut terbaca — laporkan agar penyaringnya diperbaiki."
        )


if __name__ == "__main__":
    main()
