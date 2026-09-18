"""Melabeli berita yang belum diklasifikasi.

    python -m scripts.klasifikasi
    python -m scripts.klasifikasi --ulangi       # label ulang seluruh berita
    python -m scripts.klasifikasi --batas 100
"""

from __future__ import annotations

import argparse

from app.database import SessionLocal
from app.klasifikasi import PengklasifikasiLeksikon
from app.klasifikasi.jalankan import klasifikasi_berita_baru


def main() -> None:
    p = argparse.ArgumentParser(description="Pelabelan sentimen berita")
    p.add_argument("--batas", type=int, default=None, help="jumlah berita maksimum")
    p.add_argument("--ulangi", action="store_true", help="proses ulang berita yang sudah dilabeli")
    argumen = p.parse_args()

    model = PengklasifikasiLeksikon()
    with SessionLocal() as session:
        hasil = klasifikasi_berita_baru(session, model, batas=argumen.batas, ulangi=argumen.ulangi)

    print(f"Model   : {model.versi}")
    print(f"Hasil   : {hasil.ringkas()}")


if __name__ == "__main__":
    main()
