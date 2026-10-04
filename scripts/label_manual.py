"""Anotasi manual: memberi label sentimen emas (gold label) untuk melatih dan
menguji IndoBERT.

    python -m scripts.label_manual            # mulai / lanjutkan
    python -m scripts.label_manual --target 1000
    python -m scripts.label_manual --hanya-uji --target 200   # cukup data uji

Satu tombol per pasangan berita-emiten:
    1 positif   2 netral   3 negatif
    x tidak relevan (emitennya salah dipetakan)   s lewati
    u batalkan label terakhir   ? pedoman   q keluar

Kenapa label manual wajib: seluruh label yang ada saat ini dibuat leksikon.
Model yang dilatih dengan label itu hanya belajar meniru leksikon — tidak
mungkin lebih baik darinya, dan perbandingan keduanya menjadi tidak sah.

Label disimpan sebagai asal=ANALIS, versi_model="anotasi". Karena label analis
selalu diutamakan, anotasi ini sekaligus memperbaiki angka di dasbor.

Prediksi leksikon sengaja TIDAK ditampilkan: melihatnya lebih dulu membuat
penilai cenderung setuju (anchoring), sehingga label emas ikut bias ke arah
model yang justru hendak diuji.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.ingest.penolakan import tolak_pemetaan
from app.klasifikasi.dataset import VERSI_ANOTASI, bagian_data
from app.klasifikasi.pedoman import PEDOMAN
from app.models import AsalLabel, Berita, BeritaEmiten, Emiten, LabelSentimen, Sentimen, SumberBerita

BERKAS_TIDAK_RELEVAN = Path("data/anotasi/tidak_relevan.csv")

WARNA = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
def _w(kode: str, teks: str) -> str:
    return f"\033[{kode}m{teks}\033[0m" if WARNA else teks


def baca_tombol(prompt: str) -> str:
    print(prompt, end="", flush=True)
    try:
        import msvcrt  # Windows: satu tombol tanpa Enter
        ch = msvcrt.getwch()
        print(ch)
        return ch.lower()
    except ImportError:
        return (input() or " ")[0].lower()


def urutan_acak(berita_id: int, emiten_id: int) -> str:
    """Urutan tampil yang acak tapi tetap: sampel tidak bias ke berita
    terbaru, dan sesi berikutnya melanjutkan urutan yang sama."""
    return hashlib.sha1(f"{berita_id}-{emiten_id}".encode()).hexdigest()


def muat_tidak_relevan() -> set[tuple[int, int]]:
    if not BERKAS_TIDAK_RELEVAN.exists():
        return set()
    with BERKAS_TIDAK_RELEVAN.open(encoding="utf-8") as f:
        return {(int(b["berita_id"]), int(b["emiten_id"])) for b in csv.DictReader(f)}


def catat_tidak_relevan(berita_id: int, emiten_id: int, kode: str) -> None:
    BERKAS_TIDAK_RELEVAN.parent.mkdir(parents=True, exist_ok=True)
    baru = not BERKAS_TIDAK_RELEVAN.exists()
    with BERKAS_TIDAK_RELEVAN.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if baru:
            w.writerow(["berita_id", "emiten_id", "kode", "dicatat_pada"])
        w.writerow([berita_id, emiten_id, kode, datetime.now(timezone.utc).isoformat(timespec="seconds")])


def main() -> None:
    p = argparse.ArgumentParser(description="Anotasi manual label sentimen")
    p.add_argument("--target", type=int, default=1000, help="jumlah label yang dituju (untuk progres)")
    p.add_argument("--hanya-uji", action="store_true",
                   help="hanya pasangan di bagian UJI — data latih bisa memakai label perak LLM, "
                        "tetapi data uji wajib label manusia")
    a = p.parse_args()

    if WARNA and os.name == "nt":
        os.system("")  # aktifkan kode warna ANSI di terminal Windows

    with SessionLocal() as s:
        sudah = set(s.execute(
            select(LabelSentimen.berita_id, LabelSentimen.emiten_id).where(LabelSentimen.asal == AsalLabel.ANALIS)
        ).all())
        abaikan = muat_tidak_relevan()
        baris = s.execute(
            select(BeritaEmiten, Berita, Emiten, SumberBerita)
            .join(Berita, Berita.id == BeritaEmiten.berita_id)
            .join(Emiten, Emiten.id == BeritaEmiten.emiten_id)
            .join(SumberBerita, SumberBerita.id == Berita.sumber_id)
        ).all()
        lewati = sudah | abaikan
        if a.hanya_uji:
            baris = [r for r in baris if bagian_data(r[0].berita_id) == "uji"]
            sudah = {k for k in sudah if bagian_data(k[0]) == "uji"}
        antrean = sorted(
            (r for r in baris if (r[0].berita_id, r[0].emiten_id) not in lewati),
            key=lambda r: urutan_acak(r[0].berita_id, r[0].emiten_id),
        )
        jumlah = len(sudah)
        print(_w("1;36", f"\nAnotasi sentimen — {jumlah} sudah dilabel, {len(antrean)} antre, target {a.target}."))
        print("Tekan ? untuk pedoman. Label tersimpan otomatis; aman keluar kapan saja.\n")

        riwayat: list[tuple[LabelSentimen, int]] = []  # (label, posisi di antrean)
        i = 0
        while i < len(antrean):
            kaitan, berita, emiten, sumber = antrean[i]
            tgl = berita.terbit_pada.strftime("%d %b %Y") if berita.terbit_pada else "-"
            lebar = 88
            print(_w("2", "─" * lebar))
            print(_w("2", f"[{jumlah + 1}/{a.target}]  {sumber.nama} · {tgl}"))
            print(_w("1", textwrap.fill(berita.judul, lebar)))
            if berita.ringkasan:
                print(textwrap.fill(berita.ringkasan[:600], lebar))
            kutip = (kaitan.kutipan or "").replace("…", "…").strip()
            print(_w("1;33", f"\n  Emiten: {emiten.kode} — {emiten.nama}"))
            if kutip:
                print(_w("33", textwrap.fill(f"  “{kutip}”", lebar, subsequent_indent="   ")))

            t = baca_tombol("\n  [1] positif  [2] netral  [3] negatif  [x] tak relevan  [s] lewati  [u] batal  [q] keluar > ")
            if t == "q":
                break
            if t == "?":
                print(PEDOMAN)
                continue
            if t == "u":
                if riwayat:
                    terakhir, posisi = riwayat.pop()
                    s.delete(terakhir)
                    s.commit()
                    jumlah -= 1
                    i = posisi
                    print(_w("35", "  ↶ label terakhir dibatalkan"))
                else:
                    print("  tidak ada yang bisa dibatalkan di sesi ini")
                continue
            if t == "s":
                i += 1
                continue
            if t == "x":
                catat_tidak_relevan(berita.id, emiten.id, emiten.kode)
                # sama seperti tombol "Tidak relevan" di dasbor: kaitannya
                # dicabut supaya tidak ikut menggeser skor emiten ini
                tolak_pemetaan(s, berita.id, emiten.id)
                s.commit()
                print(_w("35", "  ✕ dicatat tidak relevan, kaitannya dicabut"))
                i += 1
                continue
            sentimen = {"1": Sentimen.POSITIF, "2": Sentimen.NETRAL, "3": Sentimen.NEGATIF}.get(t)
            if sentimen is None:
                print("  tombol tidak dikenal — tekan ? untuk pedoman")
                continue
            label = LabelSentimen(
                berita_id=berita.id, emiten_id=emiten.id, sentimen=sentimen,
                keyakinan=1.0, asal=AsalLabel.ANALIS, versi_model=VERSI_ANOTASI,
            )
            s.add(label)
            s.commit()
            riwayat.append((label, i))
            jumlah += 1
            warna = {"positif": "32", "netral": "37", "negatif": "31"}[sentimen.value]
            print(_w(warna, f"  ✓ {sentimen.value}"))
            i += 1

        print(_w("1;36", f"\nSelesai sesi. Total label manual: {jumlah}."))
        if jumlah >= 300:
            print("Lanjutkan dengan:  python -m scripts.latih_indobert")


if __name__ == "__main__":
    main()
