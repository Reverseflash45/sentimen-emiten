"""Mengimpor harga saham dari berkas CSV ke basis data.

Siapkan satu berkas per emiten di folder data/harga, misalnya BBCA.csv.
Jalankan:  python -m scripts.impor_harga data/harga 2026-01-01 2026-09-30

Berkas CSV adalah data penelitiannya, jadi basis data mengikuti isinya:
tanggal baru ditambahkan, dan tanggal yang sudah ada diperbarui bila
angkanya berbeda. Tanpa pembaruan ini, harga yang sempat tersimpan kosong
atau NaN — misalnya diunduh sebelum penyedia selesai memproses hari itu —
tidak pernah tergantikan walau CSV-nya sudah benar keesokan harinya.
"""

from __future__ import annotations

import math
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


KOLOM = ("pembukaan", "tertinggi", "terendah", "penutupan", "volume")


def _sama(lama, baru) -> bool:
    """NaN tidak sama dengan apa pun, termasuk dirinya — jadi diperlakukan
    sebagai nilai kosong yang perlu diganti."""
    if isinstance(lama, float) and not math.isfinite(lama):
        lama = None
    return lama == baru


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
        total_baru = total_diperbarui = 0
        for emiten in session.scalars(select(Emiten).where(Emiten.aktif.is_(True))):
            baris = penyedia.ambil(emiten.kode, mulai, sampai)
            if not baris:
                continue
            # Satu kueri per emiten, bukan satu per baris: ke basis data jarak jauh
            # (Supabase) cara lama butuh belasan ribu perjalanan pulang-pergi.
            sudah = {
                _utc(h.tanggal): h
                for h in session.scalars(
                    select(HargaSaham).where(
                        HargaSaham.emiten_id == emiten.id,
                        HargaSaham.tanggal >= baris[0].tanggal,
                        HargaSaham.tanggal <= baris[-1].tanggal,
                    )
                )
            }
            baru = diperbarui = 0
            for b in baris:
                lama = sudah.get(_utc(b.tanggal))
                if lama is not None:
                    beda = [k for k in KOLOM if not _sama(getattr(lama, k), getattr(b, k))]
                    for k in beda:
                        setattr(lama, k, getattr(b, k))
                    diperbarui += bool(beda)
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
            if baru or diperbarui:
                print(f"  {emiten.kode:<6} +{baru} baris, {diperbarui} diperbarui")
            total_baru += baru
            total_diperbarui += diperbarui
        print(f"Selesai. {total_baru} baris harga ditambahkan, {total_diperbarui} diperbarui.")
    finally:
        session.close()
if __name__ == "__main__":
    main()
