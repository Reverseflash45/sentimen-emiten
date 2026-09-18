"""Menampilkan penyandingan sentimen dan harga satu emiten.

Jalankan:  python -m scripts.laporan_korelasi BBCA 2026-01-01 2026-09-30 [lag]
"""

from __future__ import annotations

import sys

from dateutil import parser as dateparser

from app.analitik.korelasi import sandingkan
from app.database import SessionLocal


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        return

    kode = sys.argv[1].upper()
    mulai = dateparser.parse(sys.argv[2]).date()
    sampai = dateparser.parse(sys.argv[3]).date()
    lag = int(sys.argv[4]) if len(sys.argv) > 4 else 0

    session = SessionLocal()
    try:
        hasil = sandingkan(session, kode, mulai, sampai, lag)
        print(f"\n{hasil.kode}  {mulai} s/d {sampai}  (lag {hasil.lag} hari)")
        print(f"hari beririsan : {len(hasil.titik)}")

        if hasil.catatan:
            print(f"catatan        : {hasil.catatan}")
        else:
            p, s = hasil.pearson, hasil.spearman
            print(f"Pearson        : {p.koefisien:+.4f}  ({p.kekuatan()}, n={p.n})")
            print(f"Spearman       : {s.koefisien:+.4f}  ({s.kekuatan()}, n={s.n})")

        if hasil.titik:
            print("\ntanggal      skor   penutupan  berita")
            for t in hasil.titik[-10:]:
                print(f"{t.tanggal}  {t.skor_sentimen:+.3f}  {t.penutupan:>9,.0f}  {t.jumlah_berita:>5}")

        print(
            "\nAngka di atas menunjukkan hubungan, bukan sebab-akibat, dan bukan "
            "rekomendasi membeli atau menjual efek."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
