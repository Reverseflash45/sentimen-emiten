"""Satu siklus lengkap: kumpulkan berita, petakan, labeli.

    python -m scripts.siklus_harian

Dirancang untuk dijalankan penjadwal, bukan manusia. Karena itu:
- keluarannya bertanda waktu dan ditulis ke berkas log, bukan hanya ke layar;
- aman dijalankan berkali-kali sehari — berita yang sudah ada dikenali duplikat
  dan artikel yang sudah diperkaya tidak diambil ulang;
- kegagalan satu tahap dicatat lalu tahap berikutnya tetap jalan, karena
  kehilangan satu hari data tidak bisa ditambal di kemudian hari;
- kode keluar bukan nol bila ada tahap yang gagal, supaya penjadwal bisa
  menandainya.

Kenapa ini penting untuk penelitiannya: RSS hanya menyimpan puluhan artikel
terakhir. Berita hari ini yang tidak terkumpul hari ini hilang selamanya, dan
deret waktu sentimen hanya bisa tumbuh ke depan — tidak bisa diisi mundur.
Setiap hari yang terlewat adalah lubang permanen di data.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from app.analitik.notifikasi import periksa_watchlist
from app.analitik.surel import kirim_notifikasi
from app.database import SessionLocal
from app.ingest.pengaya import perkaya_sampai_habis
from app.ingest.pipeline import jalankan_siklus
from app.klasifikasi import PengklasifikasiLeksikon
from app.klasifikasi.jalankan import klasifikasi_berita_baru
from data.lq45 import status_periode

FOLDER_LOG = Path("data/log")


def model_produksi(catat):
    """IndoBERT bila MODEL_INDOBERT diatur dan bisa dimuat; selain itu leksikon.

    Gagal memuat IndoBERT (pustaka belum terpasang, model tak terunduh) tidak
    boleh menghentikan pelabelan: berita tetap dilabeli leksikon dan
    kegagalannya tercatat, supaya tidak ada hari tanpa label.
    """
    if os.environ.get("MODEL_INDOBERT"):
        try:
            from app.klasifikasi.indobert import PengklasifikasiIndoBERT
            return PengklasifikasiIndoBERT()
        except Exception as e:  # noqa: BLE001
            catat(f"klasifikasi: IndoBERT gagal dimuat ({type(e).__name__}: {e}); memakai leksikon")
    return PengklasifikasiLeksikon()


class Pencatat:
    """Menulis ke layar dan ke berkas log sekaligus."""

    def __init__(self, berkas: Path | None) -> None:
        self.berkas = berkas
        if berkas is not None:
            berkas.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, pesan: str) -> None:
        waktu = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        baris = f"{waktu}  {pesan}"
        print(baris, flush=True)
        if self.berkas is not None:
            with self.berkas.open("a", encoding="utf-8") as f:
                f.write(baris + "\n")


def main() -> None:
    p = argparse.ArgumentParser(description="Siklus harian pengumpulan sentimen")
    p.add_argument("--tanpa-pengayaan", action="store_true",
                   help="lewati pengambilan badan artikel (lebih cepat, hasil lebih sedikit)")
    p.add_argument("--batas-pengayaan", type=int, default=60,
                   help="artikel maksimum yang diambil per siklus (bawaan 60)")
    p.add_argument("--log", default=str(FOLDER_LOG / "siklus.log"),
                   help="berkas log; kosongkan dengan --log ''")
    a = p.parse_args()

    catat = Pencatat(Path(a.log) if a.log else None)
    catat("=== siklus mulai ===")
    periode = status_periode()
    if periode["status"] != "berlaku":
        # tidak menggagalkan siklus — pengumpulan tetap harus jalan — tetapi
        # tercatat di setiap log sampai data/lq45.py diperbarui
        kapan = "sudah lewat" if periode["sisa_hari"] < 0 else f"{periode['sisa_hari']} hari lagi"
        catat(f"PERINGATAN : komposisi LQ45 di data/lq45.py berlaku s/d {periode['akhir']} ({kapan}). "
              "Perbarui dari pengumuman resmi BEI.")
    gagal: list[str] = []

    # 1. kumpulkan berita baru
    try:
        with SessionLocal() as session:
            hasil = jalankan_siklus(session)
        catat(f"kumpulkan : {hasil.ringkas()}")
        for pesan in hasil.gagal:
            catat(f"  sumber gagal: {pesan.splitlines()[0]}")
    except Exception:
        gagal.append("kumpulkan")
        catat("kumpulkan : GAGAL\n" + traceback.format_exc())

    # 2. cari emiten di badan artikel yang belum terpetakan
    if not a.tanpa_pengayaan:
        try:
            with SessionLocal() as session:
                hasil = perkaya_sampai_habis(
                    session, batas_per_putaran=a.batas_pengayaan, jeda=True
                )
            catat(f"pengayaan : {hasil.ringkas()}")
        except Exception:
            gagal.append("pengayaan")
            catat("pengayaan : GAGAL\n" + traceback.format_exc())

    # 3. labeli berita yang belum punya label
    try:
        model = model_produksi(catat)
        with SessionLocal() as session:
            hasil = klasifikasi_berita_baru(session, model)
        catat(f"klasifikasi: {model.versi} {hasil.ringkas()}")
    except Exception:
        gagal.append("klasifikasi")
        catat("klasifikasi: GAGAL\n" + traceback.format_exc())

    # 4. notifikasi watchlist — setelah label baru ada, supaya ikut terhitung
    try:
        with SessionLocal() as session:
            baru = periksa_watchlist(session)
            session.commit()
            catat(f"notifikasi : {len(baru)} baru")
            if baru:
                catat(f"email      : {kirim_notifikasi(session, baru)}")
    except Exception:
        gagal.append("notifikasi")
        catat("notifikasi : GAGAL\n" + traceback.format_exc())

    if gagal:
        catat(f"=== siklus selesai dengan kegagalan: {', '.join(gagal)} ===")
        sys.exit(1)
    catat("=== siklus selesai ===")


if __name__ == "__main__":
    main()
