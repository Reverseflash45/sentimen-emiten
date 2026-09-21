"""Menyalin seluruh isi basis data SQLite lokal ke PostgreSQL (mis. Supabase).

Jalankan sekali saat pindah ke server:
    python -m scripts.pindah_ke_postgres "postgresql://user:sandi@host:5432/postgres"

Asal data diambil dari `sentimen.db` di folder proyek (ubah dengan --asal).
Tabel di tujuan dibuat bila belum ada. Bila tujuan sudah berisi data, skrip
berhenti tanpa menulis apa pun — kecuali diberi --timpa, yang mengosongkan
tabel tujuan lebih dulu. Menolak diam-diam menggabungkan dua isi basis data
lebih aman daripada menghasilkan data ganda yang sulit dibersihkan.
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine, func, select, text

from app.database import _rapikan_url
from app.models import Base

UKURAN_BATCH = 1_000


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("tujuan", help="URL PostgreSQL tujuan (koneksi langsung, port 5432)")
    p.add_argument("--asal", default="sqlite:///./sentimen.db", help="URL basis data asal")
    p.add_argument("--timpa", action="store_true", help="kosongkan tabel tujuan sebelum menyalin")
    args = p.parse_args()

    asal = create_engine(args.asal)
    tujuan = create_engine(_rapikan_url(args.tujuan))
    tabel = Base.metadata.sorted_tables  # urutan aman untuk foreign key

    Base.metadata.create_all(tujuan)

    with asal.connect() as ka, tujuan.begin() as kt:
        terisi = [t.name for t in tabel if kt.scalar(select(func.count()).select_from(t))]
        if terisi and not args.timpa:
            raise SystemExit(f"Tujuan sudah berisi data di: {', '.join(terisi)}. Pakai --timpa untuk menimpa.")
        if args.timpa:
            for t in reversed(tabel):
                kt.execute(t.delete())

        for t in tabel:
            hasil = ka.execute(select(t))
            jumlah = 0
            while baris := hasil.fetchmany(UKURAN_BATCH):
                kt.execute(t.insert(), [dict(b._mapping) for b in baris])
                jumlah += len(baris)
            # Id disalin apa adanya, jadi penghitung id PostgreSQL harus
            # dimajukan — kalau tidak, baris baru berikutnya bentrok dengan id lama.
            if jumlah and "id" in t.c:
                kt.execute(
                    text(f"select setval(pg_get_serial_sequence('{t.name}', 'id'), (select max(id) from {t.name}))")
                )
            print(f"{t.name:<24} {jumlah:>7} baris")

    print("Selesai.")


if __name__ == "__main__":
    main()
