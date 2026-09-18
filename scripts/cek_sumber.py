"""Memeriksa satu per satu apakah RSS tiap sumber masih hidup dan diizinkan.

Jalankan:  python -m scripts.cek_sumber
Lakukan ini dulu sebelum pengumpulan penuh — URL RSS portal sering berubah.
"""

from __future__ import annotations

from sqlalchemy import select

from app.database import SessionLocal
from app.ingest import robots
from app.ingest.rss import ambil_feed
from app.models import SumberBerita


def main() -> None:
    session = SessionLocal()
    try:
        sumber = list(session.scalars(select(SumberBerita)))
        if not sumber:
            print("Belum ada sumber. Jalankan: python -m scripts.init_db")
            return

        for s in sumber:
            if not s.aktif:
                print(f"  -  {s.nama:<20} dinonaktifkan, dilewati")
                continue
            if not s.url_rss:
                print(f"  –  {s.nama:<20} tidak punya URL RSS")
                continue
            izin = robots.boleh_diambil(s.url_rss)
            if not izin:
                print(f"  ✕  {s.nama:<20} ditolak robots.txt")
                continue
            try:
                artikel = ambil_feed(s.url_rss, batas=3)
                contoh = artikel[0].judul[:60] if artikel else "(feed kosong)"
                print(f"  ✓  {s.nama:<20} {len(artikel)} item — {contoh}")
            except Exception as exc:  # noqa: BLE001
                print(f"  ✕  {s.nama:<20} {type(exc).__name__}: {exc}")
        aktif = [s for s in sumber if s.aktif]
        print(f"\n{len(aktif)} sumber aktif dari {len(sumber)} terdaftar.")
        print("Kandidat pengganti bisa diuji dengan: python -m scripts.cek_kandidat")
    finally:
        session.close()


if __name__ == "__main__":
    main()
