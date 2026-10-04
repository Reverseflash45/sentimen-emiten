"""Anotator kedua: label pembanding untuk mengukur kesepakatan antar-manusia.

    python -m scripts.label_anotator2 --target 100

Dijalankan oleh orang LAIN dari anotator utama, pada pasangan bagian uji yang
sudah dilabeli anotator utama. Tampilan dan pedomannya sama persis dengan
scripts/label_manual.py, dan label anotator utama tidak pernah ditampilkan.

Label disimpan di data/anotasi/anotator_2.csv, BUKAN di basis data: label ini
hanya untuk mengukur kesepakatan (scripts/kesepakatan_anotator.py), dan tidak
boleh menimpa label emas, data latih, maupun angka di dasbor.

Kenapa perlu: label emas dari satu orang bisa saja konsisten tapi keliru.
Cohen's kappa antar-dua anotator menunjukkan seberapa jelas tugas pelabelan
ini bagi manusia — sekaligus batas atas wajar bagi model mana pun.
"""

from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.klasifikasi.dataset import VERSI_ANOTASI, bagian_data
from app.klasifikasi.pedoman import PEDOMAN
from app.models import AsalLabel, Berita, BeritaEmiten, Emiten, LabelSentimen, SumberBerita
from scripts.label_manual import WARNA, _w, baca_tombol, tampilkan_pasangan, urutan_acak

BERKAS = Path("data/anotasi/anotator_2.csv")
KOLOM = ["berita_id", "emiten_id", "kode", "sentimen", "dicatat_pada"]


def muat_baris() -> dict[tuple[int, int], tuple[str, str, str]]:
    """(berita_id, emiten_id) -> (kode, sentimen, dicatat_pada)."""
    if not BERKAS.exists():
        return {}
    with BERKAS.open(encoding="utf-8") as f:
        return {(int(b["berita_id"]), int(b["emiten_id"])): (b["kode"], b["sentimen"], b["dicatat_pada"])
                for b in csv.DictReader(f)}


def muat() -> dict[tuple[int, int], str]:
    return {k: v[1] for k, v in muat_baris().items()}


def simpan(semua: dict[tuple[int, int], tuple[str, str, str]]) -> None:
    BERKAS.parent.mkdir(parents=True, exist_ok=True)
    with BERKAS.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(KOLOM)
        for (b, e), (kode, sentimen, waktu) in sorted(semua.items()):
            w.writerow([b, e, kode, sentimen, waktu])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", type=int, default=100)
    a = p.parse_args()
    if WARNA and os.name == "nt":
        os.system("")

    with SessionLocal() as s:
        utama = set(s.execute(
            select(LabelSentimen.berita_id, LabelSentimen.emiten_id).where(
                LabelSentimen.asal == AsalLabel.ANALIS, LabelSentimen.versi_model == VERSI_ANOTASI)
        ).all())
        utama = {k for k in utama if bagian_data(k[0]) == "uji"}
        if not utama:
            raise SystemExit("Anotator utama belum melabeli bagian uji. Jalankan dulu: "
                             "python -m scripts.label_manual --hanya-uji")
        semua = muat_baris()
        tercatat = set(semua)
        baris = s.execute(
            select(BeritaEmiten, Berita, Emiten, SumberBerita)
            .join(Berita, Berita.id == BeritaEmiten.berita_id)
            .join(Emiten, Emiten.id == BeritaEmiten.emiten_id)
            .join(SumberBerita, SumberBerita.id == Berita.sumber_id)
        ).all()
        antrean = sorted(
            (r for r in baris if (r[0].berita_id, r[0].emiten_id) in utama
             and (r[0].berita_id, r[0].emiten_id) not in tercatat),
            # urutan berbeda dari anotator utama, supaya kelelahan di akhir sesi
            # tidak jatuh pada berita yang sama untuk keduanya
            key=lambda r: urutan_acak(r[0].emiten_id, r[0].berita_id),
        )
        print(_w("1;36", f"\nAnotator kedua — {len(tercatat)} sudah dilabel, {len(antrean)} tersedia, "
                         f"target {a.target}."))
        print("Tekan ? untuk pedoman. Label tersimpan otomatis ke", BERKAS)
        riwayat: list[tuple[tuple[int, int], int]] = []  # (pasangan, posisi di antrean)
        i = 0
        while i < len(antrean) and len(semua) < a.target:
            kaitan, berita, emiten, sumber = antrean[i]
            tampilkan_pasangan(kaitan, berita, emiten, sumber, f"[{len(semua) + 1}/{a.target}]")
            t = baca_tombol("\n  [1] positif  [2] netral  [3] negatif  [x] tak relevan  [s] lewati  [u] batal  [q] keluar > ")
            if t == "q":
                break
            if t == "?":
                print(PEDOMAN)
                continue
            if t == "u":
                if riwayat:
                    kunci, posisi = riwayat.pop()
                    semua.pop(kunci)
                    simpan(semua)
                    i = posisi
                    print(_w("35", "  ↶ label terakhir dibatalkan"))
                continue
            if t == "s":
                i += 1
                continue
            nilai = {"1": "positif", "2": "netral", "3": "negatif", "x": "tidak_relevan"}.get(t)
            if nilai is None:
                print("  tombol tidak dikenal — tekan ? untuk pedoman")
                continue
            kunci = (berita.id, emiten.id)
            semua[kunci] = (emiten.kode, nilai, datetime.now(timezone.utc).isoformat(timespec="seconds"))
            riwayat.append((kunci, i))
            simpan(semua)
            print(_w("32", f"  ✓ {nilai}"))
            i += 1

    print(_w("1;36", f"\nSelesai sesi. Total label anotator kedua: {len(semua)}."))
    print("Hitung kesepakatan:  python -m scripts.kesepakatan_anotator")


if __name__ == "__main__":
    main()
