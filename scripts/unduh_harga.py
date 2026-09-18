"""Mengunduh harga harian emiten lalu MENYIMPANNYA SEBAGAI CSV.

    python -m scripts.unduh_harga 2026-01-01 2026-09-30
    python -m scripts.unduh_harga 2026-01-01 2026-09-30 --kode BBCA BMRI TLKM

Butuh paket opsional:  pip install yfinance

Kenapa hasilnya ditulis ke CSV dan bukan langsung ke basis data:

Sumber daring bisa berubah, mengoreksi angka lama, atau hilang sama sekali.
Kalau penelitian bergantung pada pemanggilan langsung, angka yang dilaporkan
hari ini belum tentu bisa dihasilkan ulang bulan depan — dan pembaca tidak
punya cara memeriksanya. Berkas CSV yang tersimpan adalah data penelitian:
bisa dilampirkan ke laporan, bisa diperiksa orang lain, dan hasilnya sama
persis setiap kali diulang.

Jadi alurnya dua langkah, dan memang disengaja:
    python -m scripts.unduh_harga 2026-01-01 2026-09-30   # ambil, simpan CSV
    python -m scripts.impor_harga data/harga 2026-01-01 2026-09-30

Setelah CSV terkumpul, langkah pertama tidak perlu diulang.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Emiten

FOLDER_BAWAAN = Path("data/harga")
KOLOM = ["tanggal", "pembukaan", "tertinggi", "terendah", "penutupan", "volume"]


def tanggal(teks: str) -> date:
    return datetime.strptime(teks, "%Y-%m-%d").date()


def unduh_satu(kode: str, mulai: date, sampai: date, folder: Path) -> tuple[int, str]:
    """Mengunduh satu emiten. Mengembalikan (jumlah baris, pesan)."""
    import yfinance as yf

    simbol = f"{kode.upper()}.JK"
    bingkai = yf.download(
        simbol,
        start=mulai.isoformat(),
        end=sampai.isoformat(),
        progress=False,
        auto_adjust=False,
    )
    if bingkai is None or bingkai.empty:
        return 0, "tidak ada data"

    # yfinance mengembalikan kolom bertingkat bila diminta beberapa simbol;
    # diratakan supaya bentuknya sama untuk satu maupun banyak simbol
    if hasattr(bingkai.columns, "nlevels") and bingkai.columns.nlevels > 1:
        bingkai.columns = bingkai.columns.get_level_values(0)

    berkas = folder / f"{kode.upper()}.csv"
    with berkas.open("w", encoding="utf-8", newline="") as f:
        penulis = csv.writer(f)
        penulis.writerow(KOLOM)
        for indeks, baris in bingkai.iterrows():
            penulis.writerow([
                indeks.date().isoformat(),
                _angka(baris.get("Open")),
                _angka(baris.get("High")),
                _angka(baris.get("Low")),
                _angka(baris.get("Close")),
                _bulat(baris.get("Volume")),
            ])
    return len(bingkai), str(berkas)


def _angka(nilai) -> str:
    try:
        return "" if nilai is None else f"{float(nilai):.4f}"
    except (TypeError, ValueError):
        return ""


def _bulat(nilai) -> str:
    try:
        return "" if nilai is None else str(int(float(nilai)))
    except (TypeError, ValueError):
        return ""


def main() -> None:
    p = argparse.ArgumentParser(description="Unduh harga harian ke berkas CSV")
    p.add_argument("mulai")
    p.add_argument("sampai")
    p.add_argument("--kode", nargs="*", default=None,
                   help="kode emiten tertentu; bawaannya seluruh emiten aktif")
    p.add_argument("--folder", default=str(FOLDER_BAWAAN))
    a = p.parse_args()

    try:
        import yfinance  # noqa: F401
    except ImportError:
        print(
            "Paket yfinance belum terpasang. Jalankan:\n"
            "  pip install yfinance\n\n"
            "Atau unduh sendiri berkas CSV per emiten ke folder data/harga\n"
            "dengan kolom: tanggal, pembukaan, tertinggi, terendah, penutupan, volume",
            file=sys.stderr,
        )
        raise SystemExit(1)

    mulai, sampai = tanggal(a.mulai), tanggal(a.sampai)
    folder = Path(a.folder)
    folder.mkdir(parents=True, exist_ok=True)

    if a.kode:
        daftar = [k.upper() for k in a.kode]
    else:
        with SessionLocal() as session:
            daftar = [
                e.kode for e in session.scalars(
                    select(Emiten).where(Emiten.aktif.is_(True)).order_by(Emiten.kode)
                )
            ]

    print(f"{len(daftar)} emiten, {mulai} s/d {sampai}, tujuan {folder}\n")
    berhasil = gagal = 0
    for nomor, kode in enumerate(daftar, start=1):
        try:
            jumlah, pesan = unduh_satu(kode, mulai, sampai, folder)
        except Exception as e:  # noqa: BLE001 — satu emiten gagal, lanjut
            print(f"[{nomor}/{len(daftar)}] {kode:6} gagal  {type(e).__name__}", flush=True)
            gagal += 1
            continue
        if jumlah:
            print(f"[{nomor}/{len(daftar)}] {kode:6} {jumlah:4} baris  {pesan}", flush=True)
            berhasil += 1
        else:
            print(f"[{nomor}/{len(daftar)}] {kode:6} kosong", flush=True)
            gagal += 1

    print(f"\n{berhasil} berhasil, {gagal} gagal/kosong.")
    print("Lanjutkan dengan:")
    print(f"  python -m scripts.impor_harga {folder} {mulai} {sampai}")
    print("\nSimpan berkas CSV itu bersama laporan — itulah data harga penelitian ini.")


if __name__ == "__main__":
    main()
