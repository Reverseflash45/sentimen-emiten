"""Mengunduh harga harian emiten lalu MENYIMPANNYA SEBAGAI CSV.

    python -m scripts.unduh_harga 2026-01-01 2026-09-30
    python -m scripts.unduh_harga 2026-01-01 2026-09-30 --kode BBCA BMRI TLKM
    python -m scripts.unduh_harga 2026-01-01 2026-09-30 --indeks   # + IHSG ke data/indeks/IHSG.csv

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
import math
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Emiten

FOLDER_BAWAAN = Path("data/harga")
#: IHSG dipisah dari harga emiten supaya impor_harga tidak menganggapnya emiten;
#: dipakai event study sebagai return pasar (scripts/analisis_lanjutan.py)
BERKAS_IHSG = Path("data/indeks/IHSG.csv")
KOLOM = ["tanggal", "pembukaan", "tertinggi", "terendah", "penutupan", "volume"]


def tanggal(teks: str) -> date:
    return datetime.strptime(teks, "%Y-%m-%d").date()


def unduh_satu(kode: str, mulai: date, sampai: date, folder: Path) -> tuple[int, str]:
    """Mengunduh satu emiten. Mengembalikan (jumlah baris, pesan)."""
    return unduh_simbol(f"{kode.upper()}.JK", mulai, sampai, folder / f"{kode.upper()}.csv")


def unduh_simbol(simbol: str, mulai: date, sampai: date, berkas: Path) -> tuple[int, str]:
    import yfinance as yf

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

    berkas.parent.mkdir(parents=True, exist_ok=True)
    with berkas.open("w", encoding="utf-8", newline="") as f:
        # akhir baris LF eksplisit: bawaan modul csv adalah CRLF, yang membuat
        # setiap unduhan di Linux (GitHub Actions) mengubah seluruh berkas
        # walau angkanya sama
        penulis = csv.writer(f, lineterminator="\n")
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
    """Sel kosong untuk nilai yang tidak ada.

    yfinance mengisi hari yang belum selesai diproses dengan NaN, bukan
    mengosongkannya. Tanpa pemeriksaan ini NaN tertulis sebagai teks "nan",
    lalu terimpor ke basis data sebagai angka dan merusak setiap perhitungan
    yang menyentuhnya.
    """
    try:
        angka = float(nilai)
    except (TypeError, ValueError):
        return ""
    return f"{angka:.4f}" if math.isfinite(angka) else ""


def _bulat(nilai) -> str:
    try:
        angka = float(nilai)
    except (TypeError, ValueError):
        return ""
    return str(int(angka)) if math.isfinite(angka) else ""


def main() -> None:
    p = argparse.ArgumentParser(description="Unduh harga harian ke berkas CSV")
    p.add_argument("mulai")
    p.add_argument("sampai")
    p.add_argument("--kode", nargs="*", default=None,
                   help="kode emiten tertentu; bawaannya seluruh emiten aktif")
    p.add_argument("--folder", default=str(FOLDER_BAWAAN))
    p.add_argument("--indeks", action="store_true", help=f"ikut unduh IHSG (^JKSE) ke {BERKAS_IHSG}")
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

    if a.indeks:
        try:
            jumlah, pesan = unduh_simbol("^JKSE", mulai, sampai, BERKAS_IHSG)
            print(f"IHSG   {jumlah:4} baris  {pesan}", flush=True)
        except Exception as e:  # noqa: BLE001 — indeks gagal tidak boleh menghentikan emiten
            print(f"IHSG   gagal  {type(e).__name__}", flush=True)

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
