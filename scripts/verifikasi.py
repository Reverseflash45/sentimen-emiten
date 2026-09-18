"""Menjalankan verifikasi berita terhadap pengumuman resmi BEI (UC-04).

Sumber CSV (dianjurkan untuk penelitian — datanya tetap dan bisa dilampirkan):

    python -m scripts.verifikasi --csv data/keterbukaan/idx.csv
    python -m scripts.verifikasi --csv data/keterbukaan/idx.csv --kode BBCA --hari 90

Sumber langsung dari situs BEI (praktis, tapi bentuk responsnya bisa berubah):

    python -m scripts.verifikasi --idx --hari 30

Tambahkan --paksa untuk menilai ulang berita yang statusnya sudah ditetapkan.
Tanpa itu, keputusan analis tidak diganggu.
"""

from __future__ import annotations

import argparse
import sys

from app.database import SessionLocal
from app.verifikasi.jalankan import jalankan_verifikasi
from app.verifikasi.sumber import SumberCsv, SumberIdx


def main() -> None:
    p = argparse.ArgumentParser(description="Verifikasi berita ke keterbukaan informasi BEI")
    kelompok = p.add_mutually_exclusive_group(required=True)
    kelompok.add_argument("--csv", help="berkas CSV pengumuman hasil unduhan manual")
    kelompok.add_argument("--idx", action="store_true", help="ambil langsung dari situs BEI")
    p.add_argument("--kode", default=None, help="batasi ke satu emiten")
    p.add_argument("--hari", type=int, default=30, help="rentang ke belakang (bawaan 30)")
    p.add_argument("--paksa", action="store_true", help="nilai ulang status yang sudah ditetapkan")
    a = p.parse_args()

    sumber = SumberIdx() if a.idx else SumberCsv(a.csv)

    with SessionLocal() as session:
        hasil = jalankan_verifikasi(
            session, sumber, hari=a.hari, kode=a.kode, paksa=a.paksa
        )

    print(f"Sumber  : {sumber.nama}")
    print(f"Hasil   : {hasil.ringkas()}")
    for g in hasil.gagal:
        print(f"  gagal : {g}", file=sys.stderr)

    if hasil.berita_diperiksa and not (hasil.terkonfirmasi or hasil.ditandai_rumor):
        print(
            "\nTidak ada yang berubah. Ini wajar: tidak adanya pengumuman resmi "
            "bukan berarti kabarnya salah, jadi status dibiarkan apa adanya."
        )


if __name__ == "__main__":
    main()
