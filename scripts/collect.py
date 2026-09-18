"""Menjalankan satu siklus pengumpulan berita.

Jalankan:  python -m scripts.collect
Untuk berkala, panggil lewat Task Scheduler (Windows) atau cron.
"""

from __future__ import annotations

from app.database import SessionLocal
from app.ingest.pipeline import jalankan_siklus


def main() -> None:
    session = SessionLocal()
    try:
        hasil = jalankan_siklus(session)
        print(hasil.ringkas())
        for pesan in hasil.gagal:
            print(f"  gagal: {pesan}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
