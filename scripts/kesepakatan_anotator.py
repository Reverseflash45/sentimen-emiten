"""Kesepakatan antar-anotator manusia (Cohen's kappa).

    python -m scripts.kesepakatan_anotator

Membandingkan label anotator utama (label emas bagian uji) dengan label
anotator kedua (data/anotasi/anotator_2.csv). Pasangan yang ditandai tidak
relevan oleh salah satu anotator dilaporkan terpisah dan tidak ikut kappa.

Cara membaca kappa (Landis & Koch, 1977): < 0,20 lemah, 0,21–0,40 cukup,
0,41–0,60 sedang, 0,61–0,80 kuat, > 0,80 hampir sempurna. Kappa antar-manusia
juga menjadi batas atas wajar: model yang kesepakatannya dengan anotator utama
melampaui kesepakatan dua manusia patut dicurigai, bukan dirayakan.

Keluaran: data/anotasi/laporan_kesepakatan.md
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.klasifikasi.dataset import KELAS, VERSI_ANOTASI
from app.models import AsalLabel, LabelSentimen
from scripts.evaluasi_model import metrik
from scripts.label_anotator2 import muat

LAPORAN = Path("data/anotasi/laporan_kesepakatan.md")


def main() -> None:
    kedua = muat()
    if not kedua:
        raise SystemExit("Belum ada label anotator kedua. Jalankan: python -m scripts.label_anotator2")
    with SessionLocal() as s:
        utama = {(b, e): sen.value for b, e, sen in s.execute(
            select(LabelSentimen.berita_id, LabelSentimen.emiten_id, LabelSentimen.sentimen).where(
                LabelSentimen.asal == AsalLabel.ANALIS, LabelSentimen.versi_model == VERSI_ANOTASI)
        ).all()}

    sama = [k for k in kedua if k in utama]
    tak_relevan = [k for k in sama if kedua[k] == "tidak_relevan"]
    dinilai = [k for k in sama if kedua[k] != "tidak_relevan"]
    if len(dinilai) < 20:
        raise SystemExit(f"Baru {len(dinilai)} pasangan yang dinilai keduanya — terlalu sedikit untuk kappa.")
    a = [utama[k] for k in dinilai]
    b = [kedua[k] for k in dinilai]
    m = metrik(a, b)
    kelas = [k.value for k in KELAS]
    tafsir = next(t for batas, t in [(0.2, "lemah"), (0.4, "cukup"), (0.6, "sedang"), (0.8, "kuat"),
                                     (1.01, "hampir sempurna")] if m["kappa"] <= batas)
    isi = (f"# Kesepakatan antar-anotator\n\n{len(dinilai)} pasangan bagian uji dinilai kedua anotator.\n\n"
           f"- Persentase sama: **{m['akurasi']:.1%}**\n- Cohen's kappa: **{m['kappa']:.3f}** ({tafsir})\n"
           f"- Ditandai tidak relevan oleh anotator kedua: {len(tak_relevan)}\n"
           f"- Sebaran anotator utama: {dict(Counter(a))}; anotator kedua: {dict(Counter(b))}\n\n"
           "## Matriks (baris = anotator utama, kolom = anotator kedua)\n\n| | " + " | ".join(kelas)
           + " |\n|---|" + "---|" * len(kelas) + "\n"
           + "".join(f"| {x} | " + " | ".join(str(m['matriks'][x][y]) for y in kelas) + " |\n" for x in kelas))
    LAPORAN.parent.mkdir(parents=True, exist_ok=True)
    LAPORAN.write_text(isi, encoding="utf-8")
    print(isi)
    print(f"Tersimpan di {LAPORAN}")


if __name__ == "__main__":
    main()
