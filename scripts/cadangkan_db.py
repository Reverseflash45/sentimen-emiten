"""Mencadangkan basis data PostgreSQL ke folder lokal.

    python -m scripts.cadangkan_db
    python -m scripts.cadangkan_db --folder D:/cadangan --simpan 12

Kenapa perlu: berita yang sudah lewat dari RSS tidak bisa diambil ulang. Bila
basis data hilang — proyek Supabase gratis dijeda, terhapus, atau rusak — data
penelitiannya ikut hilang permanen, dan CSV harga di repo tidak cukup untuk
menggantinya.

Kenapa lokal, bukan di repo: cadangan memuat email dan hash kata sandi akun.
Repositori ini publik, dan artefak GitHub Actions pada repo publik bisa diunduh
orang lain.

Memakai pg_dump format custom (-Fc) untuk skema public saja — tabel milik
Supabase sendiri (auth, storage) tidak perlu dan tidak bisa dipulihkan ke
server lain. Memulihkan:  pg_restore --no-owner -d <URL tujuan> berkas.dump
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from app.config import settings

FOLDER_BAWAAN = Path.home() / "Documents" / "Cadangan-Sentimen-Emiten"


def url_libpq(url: str) -> str:
    """postgresql+psycopg://... -> postgresql://... (pg_dump tidak kenal dialek SQLAlchemy)."""
    skema, sisa = url.split("://", 1)
    return f"{skema.split('+')[0]}://{sisa}"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--folder", type=Path, default=FOLDER_BAWAAN)
    p.add_argument("--simpan", type=int, default=6, help="jumlah cadangan terbaru yang dipertahankan")
    a = p.parse_args()

    if not settings.database_url.startswith("postgresql"):
        sys.exit("DATABASE_URL bukan PostgreSQL — untuk SQLite cukup salin berkas .db-nya.")
    pg_dump = shutil.which("pg_dump")
    if pg_dump is None:
        sys.exit("pg_dump tidak ditemukan. Pasang PostgreSQL client tools, lalu ulangi.")

    a.folder.mkdir(parents=True, exist_ok=True)
    berkas = a.folder / f"sentimen-{datetime.now():%Y%m%d-%H%M}.dump"
    hasil = subprocess.run(
        [pg_dump, "--format=custom", "--schema=public", "--no-owner", "--no-privileges",
         f"--file={berkas}", url_libpq(settings.database_url)],
        capture_output=True, text=True, env={**os.environ, "PGCONNECT_TIMEOUT": "30"},
    )
    if hasil.returncode != 0:
        berkas.unlink(missing_ok=True)
        sys.exit(f"pg_dump gagal:\n{hasil.stderr.strip()[:2000]}")
    print(f"Tersimpan: {berkas} ({berkas.stat().st_size / 1e6:.1f} MB)")

    lama = sorted(a.folder.glob("sentimen-*.dump"))[: -a.simpan]
    for f in lama:
        f.unlink()
        print(f"Dihapus (lebih dari {a.simpan} cadangan): {f.name}")


if __name__ == "__main__":
    main()
