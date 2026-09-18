"""Uji kepekaan korelasi terhadap artikel rekap pasar.

    python -m scripts.uji_kepekaan BBCA 2026-01-01 2026-09-30

Menghitung korelasi beberapa kali dengan batas jumlah emiten per berita yang
berbeda, lalu menampilkannya berdampingan.

Kenapa ini penting: artikel rekap pasar ("ANALIS MARKET", "Saham Bank Jadi
Pemberat", "Asing Jual Saham Tambang") menyebut banyak emiten sekaligus dan
nadanya tentang indeks, bukan tentang satu perusahaan. Kalau korelasi hanya
muncul ketika artikel semacam itu diikutkan, yang terukur sebenarnya adalah
pergerakan IHSG — bukan sentimen per emiten.

Hasil yang stabil di semua batas adalah temuan yang kuat. Hasil yang runtuh
begitu rekap dibuang juga temuan — temuan bahwa sinyalnya berasal dari sana.
Keduanya layak dilaporkan; yang tidak layak adalah memilih satu setelan karena
angkanya paling enak dilihat.
"""

from __future__ import annotations

import sys
from datetime import date, datetime

from app.analitik.korelasi import sandingkan
from app.database import SessionLocal

BATAS_UJI: list[int | None] = [1, 2, 3, 5, None]


def tanggal(teks: str) -> date:
    return datetime.strptime(teks, "%Y-%m-%d").date()


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        raise SystemExit(1)

    kode = sys.argv[1].upper()
    mulai, sampai = tanggal(sys.argv[2]), tanggal(sys.argv[3])
    lag = int(sys.argv[4]) if len(sys.argv) > 4 else 0

    print(f"{kode}  {mulai} s/d {sampai}  (lag {lag} hari)\n")
    print(f"{'maks emiten/berita':>20}  {'hari':>5}  {'Pearson':>9}  {'Spearman':>9}  n")
    print("-" * 62)

    with SessionLocal() as session:
        for batas in BATAS_UJI:
            h = sandingkan(session, kode, mulai, sampai, lag=lag,
                           maks_emiten_per_berita=batas)
            label = "tanpa batas" if batas is None else str(batas)
            if h.pearson is None:
                print(f"{label:>20}  {len(h.titik):>5}  {'—':>9}  {'—':>9}  "
                      f"({h.catatan})")
                continue
            print(
                f"{label:>20}  {len(h.titik):>5}  "
                f"{h.pearson.koefisien:>+9.4f}  {h.spearman.koefisien:>+9.4f}  "
                f"{h.pearson.n}"
            )

    print(
        "\nBaris 1 = hanya berita yang membahas satu emiten saja.\n"
        "Baris terakhir = seluruh berita, termasuk rekap pasar.\n\n"
        "Laporkan seluruh baris ini, bukan salah satunya. Korelasi yang hanya\n"
        "muncul di baris bawah menandakan sinyalnya berasal dari artikel rekap,\n"
        "yang berarti yang terukur adalah pergerakan indeks."
    )


if __name__ == "__main__":
    main()
