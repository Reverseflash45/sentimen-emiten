"""Mengambil badan artikel untuk berita yang belum terpetakan ke emiten.

    python -m scripts.petakan_ulang
    python -m scripts.petakan_ulang --batas 100

Dijalankan setelah `scripts.collect`. Dipisah dari pengumpulan supaya siklus
pengumpulan tetap cepat dan pengambilan halaman — yang lebih berat dan harus
menghormati crawl-delay — bisa dijadwalkan sendiri.

Setelah ini jalankan `scripts.klasifikasi` lagi: berita yang baru dapat emiten
ditandai perlu dilabeli ulang.
"""

from __future__ import annotations

import argparse
import sys

from app.database import SessionLocal
from app.ingest.pengaya import perkaya_pemetaan, perkaya_sampai_habis


def main() -> None:
    p = argparse.ArgumentParser(description="Pengayaan pemetaan berita ke emiten")
    p.add_argument("--batas", type=int, default=None, help="jumlah artikel maksimum")
    p.add_argument("--tanpa-jeda", action="store_true",
                   help="lewati crawl-delay (hanya untuk uji di mesin sendiri)")
    p.add_argument("--semua", action="store_true",
                   help="ulangi otomatis sampai tidak ada sisa")
    p.add_argument("--ulangi", action="store_true",
                   help="ambil ulang artikel yang sudah pernah dicoba "
                        "(pakai setelah daftar emiten diperluas)")
    a = p.parse_args()

    def lapor(pesan: str) -> None:
        print(pesan, flush=True)

    with SessionLocal() as session:
        if a.semua:
            hasil = perkaya_sampai_habis(
                session, batas_per_putaran=a.batas, jeda=not a.tanpa_jeda,
                lapor=lapor, ulangi=a.ulangi,
            )
        else:
            hasil = perkaya_pemetaan(
                session, batas=a.batas, jeda=not a.tanpa_jeda, lapor=lapor,
                ulangi=a.ulangi,
            )

    print(f"\nHasil : {hasil.ringkas()}")
    for g in hasil.gagal[:10]:
        print(f"  gagal: {g}", file=sys.stderr)
    if len(hasil.gagal) > 10:
        print(f"  ... {len(hasil.gagal) - 10} kegagalan lain", file=sys.stderr)

    if hasil.terpetakan:
        print("\nJalankan `python -m scripts.klasifikasi` untuk melabeli berita baru ini.")
    if hasil.sisa:
        print(f"Masih ada {hasil.sisa} berita. Jalankan lagi perintah yang sama.")
    elif not hasil.diperiksa:
        print(
            "Semua berita sudah pernah diperkaya. Yang tetap tanpa emiten memang\n"
            "tidak menyebut emiten yang dipantau — lihat: "
            "python -m scripts.diagnosa_pemetaan"
        )


if __name__ == "__main__":
    main()
