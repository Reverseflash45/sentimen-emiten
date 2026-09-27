"""Mengimpor harga saham dari berkas CSV ke basis data.

Siapkan satu berkas per emiten di folder data/harga, misalnya BBCA.csv.
Jalankan:  python -m scripts.impor_harga data/harga 2026-01-01 2026-09-30
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone

from dateutil import parser as dateparser
from sqlalchemy import select

from app.database import SessionLocal
from app.harga.provider import PenyediaCsv
from app.models import Emiten, HargaSaham


def _utc(t: datetime) -> datetime:
    """SQLite mengembalikan datetime tanpa zona, PostgreSQL dengan zona."""
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)


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
            # Satu kueri per emiten, bukan satu per baris: ke basis data jarak jauh
            # (Supabase) cara lama butuh belasan ribu perjalanan pulang-pergi.
            sudah = {
                _utc(t)
                for t in session.scalars(
                    select(HargaSaham.tanggal).where(
                        HargaSaham.emiten_id == emiten.id,
                        HargaSaham.tanggal >= baris[0].tanggal,
                        HargaSaham.tanggal <= baris[-1].tanggal,
                    )
                )
            }
            baru = 0
            for b in baris:
                if _utc(b.tanggal) in sudah:
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
