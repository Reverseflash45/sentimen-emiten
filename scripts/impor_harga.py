"""Mengimpor harga saham dari berkas CSV ke basis data.

Siapkan satu berkas per emiten di folder data/harga, misalnya BBCA.csv.
Jalankan:  python -m scripts.impor_harga data/harga 2026-01-01 2026-09-30
"""

from __future__ import annotations

import sys
from datetime import date

from dateutil import parser as dateparser
from sqlalchemy import select

from app.database import SessionLocal
from app.harga.provider import PenyediaCsv
from app.models import Emiten, HargaSaham


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        return

    folder, mulai_s, sampai_s = sys.argv[1], sys.argv[2], sys.argv[3]
    mulai: date = dateparser.parse(mulai_s).date()
    sampai: date = dateparser.parse(sampai_s).date()

    penyedia = PenyediaCsv(folder)
    session = SessionLocal()
    try:
        total_baru = 0
        for emiten in session.scalars(select(Emiten).where(Emiten.aktif.is_(True))):
            baris = penyedia.ambil(emiten.kode, mulai, sampai)
            if not baris:
                continue
            baru = 0
            for b in baris:
                sudah = session.scalar(
                    select(HargaSaham).where(
                        HargaSaham.emiten_id == emiten.id, HargaSaham.tanggal == b.tanggal
                    )
                )
                if sudah:
                    continue
                session.add(
                    HargaSaham(
                        emiten_id=emiten.id,
                        tanggal=b.tanggal,
                        pembukaan=b.pembukaan,
                        tertinggi=b.tertinggi,
                        terendah=b.terendah,
                        penutupan=b.penutupan,
                        volume=b.volume,
                    )
                )
                baru += 1
            session.commit()
            if baru:
                print(f"  {emiten.kode:<6} +{baru} baris")
            total_baru += baru
        print(f"Selesai. {total_baru} baris harga ditambahkan.")
    finally:
        session.close()
if __name__ == "__main__":
    main()
