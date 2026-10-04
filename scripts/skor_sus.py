"""Menghitung skor System Usability Scale (SUS) untuk NF-05.

    python -m scripts.skor_sus hasil_google_forms.csv

Instrumen: SUS adaptasi bahasa Indonesia (Sharfina & Santoso, 2016), 10 butir
skala Likert 1–5. Kuesioner dan tugas untuk responden ada di
data/pengujian/kuesioner_sus.md.

Berkas CSV boleh langsung hasil ekspor Google Forms: kolom butir SUS dikenali
dari kolom yang semua isinya angka 1–5, diambil 10 pertama sesuai urutan
kolom. Pastikan urutan pertanyaan di formulir sama dengan urutan butir SUS.

Perhitungan per responden: butir ganjil (positif) = jawaban − 1, butir genap
(negatif) = 5 − jawaban, jumlahkan, kali 2,5 → skala 0–100.

Penafsiran:
  - Keberterimaan (Bangor dkk., 2008): ≥ 70 dapat diterima, 50–70 marginal,
    < 50 tidak dapat diterima.
  - Nilai huruf (Sauro & Lewis, 2016, skala melengkung): rata-rata global
    SUS ≈ 68 setara nilai C.

Keluaran: data/pengujian/hasil_sus.md
"""

from __future__ import annotations

import csv
import math
import statistics
import sys
from pathlib import Path

LAPORAN = Path("data/pengujian/hasil_sus.md")

#: (batas bawah, nilai) — Sauro & Lewis (2016), skala melengkung
SKALA_HURUF = [(84.1, "A+"), (80.8, "A"), (78.9, "A−"), (77.2, "B+"), (74.1, "B"), (72.6, "B−"),
               (71.1, "C+"), (65.0, "C"), (62.7, "C−"), (51.7, "D"), (0.0, "F")]


def skor_responden(jawaban: list[int]) -> float:
    if len(jawaban) != 10 or not all(1 <= j <= 5 for j in jawaban):
        raise ValueError("satu responden harus punya 10 jawaban bernilai 1–5")
    return 2.5 * sum((j - 1) if i % 2 == 0 else (5 - j) for i, j in enumerate(jawaban))


def keberterimaan(skor: float) -> str:
    return "dapat diterima" if skor >= 70 else "marginal" if skor >= 50 else "tidak dapat diterima"


def huruf(skor: float) -> str:
    return next(h for batas, h in SKALA_HURUF if skor >= batas)


def baca_csv(jalur: Path) -> list[list[int]]:
    with jalur.open(encoding="utf-8-sig", newline="") as f:
        baris = list(csv.reader(f))
    kepala, isi = baris[0], [b for b in baris[1:] if any(c.strip() for c in b)]

    def kolom_likert(i: int) -> bool:
        nilai = [b[i].strip() for b in isi if i < len(b)]
        return bool(nilai) and all(v.isdigit() and 1 <= int(v) <= 5 for v in nilai)

    kolom = [i for i in range(len(kepala)) if kolom_likert(i)][:10]
    if len(kolom) < 10:
        raise SystemExit(f"Hanya {len(kolom)} kolom berisi jawaban 1–5; SUS butuh 10.")
    return [[int(b[i]) for i in kolom] for b in isi]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    data = baca_csv(Path(sys.argv[1]))
    skor = [skor_responden(j) for j in data]
    n = len(skor)
    rata = statistics.mean(skor)
    sd = statistics.stdev(skor) if n > 1 else 0.0
    # selang kepercayaan 95% dengan distribusi t (sampel responden biasanya kecil)
    galat = 0.0
    if n > 1:
        from scipy import stats

        galat = stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n)
    bawah, atas = max(0.0, rata - galat), min(100.0, rata + galat)
    isi = (f"# Hasil System Usability Scale (NF-05)\n\nInstrumen: SUS adaptasi bahasa Indonesia "
           f"(Sharfina & Santoso, 2016). Responden: **{n}**.\n\n"
           f"- Skor SUS rata-rata: **{rata:.1f}** (SD {sd:.1f}; selang kepercayaan 95% "
           f"{bawah:.1f}–{atas:.1f})\n"
           f"- Keberterimaan: **{keberterimaan(rata)}** (Bangor dkk., 2008)\n"
           f"- Nilai: **{huruf(rata)}** (Sauro & Lewis, 2016; rata-rata global ≈ 68 = C)\n\n"
           "| Responden | Skor | Keberterimaan |\n|---|---|---|\n"
           + "".join(f"| R{i} | {s:.1f} | {keberterimaan(s)} |\n" for i, s in enumerate(skor, 1))
           + "\nNF-05 terpenuhi bila rata-rata ≥ 70 (dapat diterima).\n")
    LAPORAN.parent.mkdir(parents=True, exist_ok=True)
    LAPORAN.write_text(isi, encoding="utf-8")
    print(isi)
    print(f"Tersimpan di {LAPORAN}")


if __name__ == "__main__":
    main()
