"""Mengukur kebutuhan non-fungsional NF-01.

    python -m scripts.ukur_kinerja
    python -m scripts.ukur_kinerja --alamat http://127.0.0.1:8000 --ulang 20

NF-01: halaman dashboard dan detail emiten dimuat < 5 detik pada koneksi
normal; klasifikasi satu berita tidak melebihi 2 detik.

Waktu muat halaman diukur sebagai jumlah waktu SEMUA permintaan yang
dibutuhkan halaman itu, dijalankan berurutan. Peramban menjalankan sebagian
permintaan bersamaan, jadi angka ini batas atas — kalau batas atasnya pun di
bawah 5 detik, kebutuhannya terpenuhi tanpa perlu berasumsi.

Waktu klasifikasi diukur per berita untuk setiap model yang tersedia di mesin
ini, setelah satu pemanasan (pemuatan model tidak dihitung sebagai waktu
klasifikasi, karena terjadi sekali per proses, bukan per berita).

Keluaran: data/analisis/laporan_kinerja.md
"""

from __future__ import annotations

import argparse
import statistics
import time
from datetime import datetime
from pathlib import Path

import httpx

LAPORAN = Path("data/analisis/laporan_kinerja.md")
BATAS_HALAMAN = 5.0
BATAS_KLASIFIKASI = 2.0

HALAMAN = {
    "Dashboard (beranda)": ["/", "/statis/gaya.css", "/statis/dasbor.js", "/api/ringkasan", "/api/emiten",
                           "/api/rentang-data", "/api/peringkat?hanya_berberita=true"],
    "Detail emiten (BBCA)": ["/api/emiten/BBCA", "/api/emiten/BBCA/sentimen", "/api/emiten/BBCA/harga",
                             "/api/emiten/BBCA/korelasi?lag=0", "/api/berita?kode=BBCA&limit=30"],
}

CONTOH = [
    ("Laba bersih BBCA naik 12% pada kuartal III 2026, ditopang pertumbuhan kredit dua digit.",
     "BBCA (Bank Central Asia Tbk). Laba bersih BBCA naik 12%"),
    ("IHSG ditutup melemah 0,8% dengan net sell asing di saham perbankan besar.",
     "BBRI (Bank Rakyat Indonesia (Persero) Tbk). net sell asing di saham perbankan"),
    ("Aneka Tambang digugat pailit oleh kreditur atas utang yang jatuh tempo.",
     "ANTM (Aneka Tambang Tbk). Aneka Tambang digugat pailit"),
]


def ringkas(nilai: list[float]) -> tuple[float, float, float]:
    urut = sorted(nilai)
    p95 = urut[min(len(urut) - 1, round(0.95 * (len(urut) - 1)))]
    return statistics.median(urut), p95, max(urut)


def ukur_halaman(alamat: str, ulang: int) -> list[tuple[str, float, float, float, bool]]:
    hasil = []
    with httpx.Client(base_url=alamat, timeout=30, follow_redirects=True) as k:
        for nama, jalur in HALAMAN.items():
            for j in jalur:  # pemanasan: fungsi serverless yang "dingin" tidak mewakili muatan biasa
                k.get(j)
            waktu = []
            for _ in range(ulang):
                mulai = time.perf_counter()
                for j in jalur:
                    k.get(j).raise_for_status()
                waktu.append(time.perf_counter() - mulai)
            med, p95, maks = ringkas(waktu)
            hasil.append((nama, med, p95, maks, p95 < BATAS_HALAMAN))
    return hasil


def ukur_model(ulang: int) -> list[tuple[str, str, float, float, bool]]:
    pembuat = []
    from app.klasifikasi import PengklasifikasiLeksikon
    pembuat.append(("leksikon", lambda: PengklasifikasiLeksikon(), "CPU"))
    try:
        from app.klasifikasi.klasik import PengklasifikasiKlasik, lokasi_model
        for j in ("nb", "svm"):
            if lokasi_model(j).exists():
                pembuat.append((f"TF-IDF + {j.upper()}", lambda j=j: PengklasifikasiKlasik(j), "CPU"))
    except ImportError:
        pass
    try:
        import torch

        from app.klasifikasi.indobert import LOKASI_BAWAAN, PengklasifikasiIndoBERT
        if Path(LOKASI_BAWAAN).exists():
            perangkat = "GPU" if torch.cuda.is_available() else "CPU"
            pembuat.append(("IndoBERT", lambda: PengklasifikasiIndoBERT(), perangkat))
    except ImportError:
        pass
    try:
        from app.klasifikasi.llm import PengklasifikasiLLM
        llm = PengklasifikasiLLM()
        llm.klien.get(f"{llm.alamat}/api/version", timeout=3).raise_for_status()
        pembuat.append((f"LLM {llm.model}", lambda: llm, "GPU (Ollama)"))
    except Exception:  # noqa: BLE001 — Ollama tidak berjalan: lewati
        pass

    hasil = []
    for nama, buat, perangkat in pembuat:
        model = buat()
        model.prediksi_emiten(*CONTOH[0])  # pemanasan
        waktu = []
        for i in range(ulang):
            teks, target = CONTOH[i % len(CONTOH)]
            mulai = time.perf_counter()
            model.prediksi_emiten(teks, target)
            waktu.append(time.perf_counter() - mulai)
        med, p95, _ = ringkas(waktu)
        hasil.append((nama, perangkat, med, p95, p95 < BATAS_KLASIFIKASI))
        if hasattr(model, "lepas"):
            model.lepas()
    return hasil


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--alamat", default="https://sentimen.raffstw.my.id")
    p.add_argument("--ulang", type=int, default=10)
    a = p.parse_args()

    halaman = ukur_halaman(a.alamat, a.ulang)
    model = ukur_model(max(a.ulang, 20))
    ya = lambda ok: "memenuhi" if ok else "**tidak memenuhi**"  # noqa: E731
    isi = (f"# Pengukuran NF-01\n\nDiukur {datetime.now():%Y-%m-%d %H:%M} terhadap {a.alamat}, "
           f"{a.ulang} ulangan per halaman setelah pemanasan.\n\n"
           f"## Waktu muat halaman (batas {BATAS_HALAMAN:.0f} detik)\n\n"
           "Jumlah waktu semua permintaan halaman bila dijalankan berurutan — batas atas waktu muat di peramban.\n\n"
           "| Halaman | Median | P95 | Maks | Status |\n|---|---|---|---|---|\n"
           + "".join(f"| {n} | {m:.2f} dtk | {p:.2f} dtk | {x:.2f} dtk | {ya(ok)} |\n" for n, m, p, x, ok in halaman)
           + f"\n## Waktu klasifikasi satu berita (batas {BATAS_KLASIFIKASI:.0f} detik)\n\n"
           "Setelah model dimuat; diukur di mesin pengembang.\n\n"
           "| Model | Perangkat | Median | P95 | Status |\n|---|---|---|---|---|\n"
           + "".join(f"| {n} | {d} | {m * 1000:.1f} ms | {p * 1000:.1f} ms | {ya(ok)} |\n" for n, d, m, p, ok in model))
    LAPORAN.parent.mkdir(parents=True, exist_ok=True)
    LAPORAN.write_text(isi, encoding="utf-8")
    print(isi)
    print(f"Tersimpan di {LAPORAN}")


if __name__ == "__main__":
    main()
