"""Menjelaskan kenapa berita tidak terpetakan ke emiten.

    python -m scripts.diagnosa_pemetaan

Memisahkan dua sebab yang sangat berbeda: pencocokan yang gagal (cacat, harus
diperbaiki) dan berita tentang emiten di luar cakupan LQ45 (konsekuensi batasan
cakupan, bukan cacat). Tanpa pemisahan ini, angka berita tanpa emiten tidak bisa
ditafsirkan.
"""

from __future__ import annotations

import argparse

from app.database import SessionLocal
from app.ingest.diagnosa import diagnosa


def main() -> None:
    p = argparse.ArgumentParser(description="Diagnosa pemetaan berita ke emiten")
    p.add_argument("--batas", type=int, default=500, help="berita terakhir yang diperiksa")
    a = p.parse_args()

    with SessionLocal() as session:
        h = diagnosa(session, batas=a.batas)

    if not h.total_tanpa_emiten:
        print("Semua berita sudah terpetakan ke emiten.")
        return

    print(f"Berita tanpa emiten yang diperiksa : {h.total_tanpa_emiten}")
    print(f"  membahas emiten di luar cakupan  : {h.menyebut_kode_luar_cakupan} "
          f"({h.persen_luar_cakupan:.1f}%)")
    print(f"  tidak menyebut kode apa pun      : {h.tanpa_kode_apa_pun}")
    print(f"  menyebut kode yang DIPANTAU      : {h.menyebut_kode_dipantau}  <-- perlu diperiksa")

    if h.kode_luar_cakupan:
        print("\nKode di luar cakupan yang paling sering muncul:")
        for kode, jumlah in h.kode_luar_cakupan.most_common(15):
            print(f"  {kode}  {jumlah}x")
        print(
            "\nKode di atas bukan kesalahan sistem — cakupan penelitian dibatasi\n"
            "LQ45 (SRS 10.3). Tapi kalau ada kode besar yang seharusnya masuk LQ45\n"
            "periode ini, daftar di data/lq45.py memang perlu diperbarui dari\n"
            "pengumuman resmi BEI."
        )

    if h.contoh_terlewat:
        print("\nBerita yang menyebut emiten dipantau tapi tidak terpetakan:")
        for berita_id, judul, kode in h.contoh_terlewat:
            print(f"  #{berita_id} [{', '.join(kode)}] {judul[:70]}")
        print(
            "\nIni yang perlu ditindaklanjuti. Kemungkinan sebabnya: kode ada di\n"
            "KODE_AMBIGU tapi teksnya tidak memuat petunjuk pasar, atau halaman\n"
            "artikelnya belum diambil (jalankan scripts.petakan_ulang)."
        )
    else:
        print("\nTidak ada berita yang menyebut emiten dipantau tapi gagal dipetakan.")


if __name__ == "__main__":
    main()
