"""Membandingkan pengklasifikasi pada bagian UJI label emas.

    python -m scripts.evaluasi_model
    python -m scripts.evaluasi_model --tanpa-indobert   # hanya leksikon (sebelum model dilatih)

Yang dibandingkan:
  - mayoritas : selalu menebak kelas terbanyak di data latih. Model yang tidak
                mengalahkan ini tidak belajar apa pun.
  - leksikon  : baseline saat ini (leksikon-v1).
  - indobert  : hasil scripts/latih_indobert.py.

Selisih macro-F1 IndoBERT vs leksikon dilengkapi selang kepercayaan 95% dari
bootstrap berpasangan: dengan data uji yang kecil, selisih beberapa poin bisa
saja kebetulan, dan selang ini menunjukkan seberapa yakin selisih itu nyata.

Data uji hanya memakai label "buta" dari scripts.label_manual. Koreksi yang
dibuat di dasbor ikut melatih model, tetapi tidak dipakai untuk menilainya.

Laporan ditulis ke data/anotasi/laporan_evaluasi.md.
"""

from __future__ import annotations

import argparse
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.database import SessionLocal
from app.klasifikasi import PengklasifikasiLeksikon
from app.klasifikasi.dataset import KELAS, muat_label_emas

LAPORAN = Path("data/anotasi/laporan_evaluasi.md")


def metrik(benar: list[str], tebak: list[str]) -> dict:
    kelas = [k.value for k in KELAS]
    per_kelas = {}
    for k in kelas:
        tp = sum(1 for b, t in zip(benar, tebak) if b == k and t == k)
        fp = sum(1 for b, t in zip(benar, tebak) if b != k and t == k)
        fn = sum(1 for b, t in zip(benar, tebak) if b == k and t != k)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        per_kelas[k] = {"presisi": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0, "n": tp + fn}
    return {
        "akurasi": sum(b == t for b, t in zip(benar, tebak)) / len(benar),
        "macro_f1": sum(v["f1"] for v in per_kelas.values()) / len(kelas),
        "per_kelas": per_kelas,
        "matriks": {b: {t: sum(1 for x, y in zip(benar, tebak) if x == b and y == t) for t in kelas} for b in kelas},
    }


def selang_selisih(benar, tebak_a, tebak_b, ulang=2000, seed=0) -> tuple[float, float]:
    """Bootstrap berpasangan untuk selisih macro-F1 (a − b)."""
    acak = random.Random(seed)
    n = len(benar)
    selisih = []
    for _ in range(ulang):
        i = [acak.randrange(n) for _ in range(n)]
        pilih = lambda xs: [xs[j] for j in i]  # noqa: E731
        selisih.append(metrik(pilih(benar), pilih(tebak_a))["macro_f1"] - metrik(pilih(benar), pilih(tebak_b))["macro_f1"])
    selisih.sort()
    return selisih[int(0.025 * ulang)], selisih[int(0.975 * ulang)]


def tabel_md(nama_hasil: dict[str, dict]) -> str:
    kelas = [k.value for k in KELAS]
    s = "| Model | Akurasi | Macro-F1 | " + " | ".join(f"F1 {k}" for k in kelas) + " |\n"
    s += "|---|---|---|" + "---|" * len(kelas) + "\n"
    for nama, m in nama_hasil.items():
        s += f"| {nama} | {m['akurasi']:.3f} | **{m['macro_f1']:.3f}** | " + \
             " | ".join(f"{m['per_kelas'][k]['f1']:.3f}" for k in kelas) + " |\n"
    return s


def matriks_md(nama: str, m: dict) -> str:
    kelas = [k.value for k in KELAS]
    s = f"**{nama}** (baris = label emas, kolom = tebakan)\n\n| | " + " | ".join(kelas) + " |\n|---|" + "---|" * len(kelas) + "\n"
    for b in kelas:
        s += f"| {b} | " + " | ".join(str(m["matriks"][b][t]) for t in kelas) + " |\n"
    return s


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tanpa-indobert", action="store_true")
    p.add_argument("--model", default=None, help="lokasi model IndoBERT (bawaan: MODEL_INDOBERT / model/indobert-sentimen)")
    a = p.parse_args()

    with SessionLocal() as s:
        data = muat_label_emas(s)
    # Hanya label buta: koreksi di dasbor dibuat sambil melihat tebakan model,
    # sehingga cenderung setuju dengannya dan akan menggelembungkan skor model.
    uji = [c for c in data if c.bagian == "uji" and c.asal == "anotasi"]
    latih = [c for c in data if c.bagian == "latih"]
    if len(uji) < 30:
        raise SystemExit(f"Data uji baru {len(uji)} contoh — terlalu sedikit untuk angka yang bermakna. "
                         "Tambah label dengan scripts.label_manual.")

    benar = [c.sentimen.value for c in uji]
    mayoritas = Counter(c.sentimen.value for c in latih).most_common(1)[0][0] if latih else "netral"
    hasil = {"mayoritas": metrik(benar, [mayoritas] * len(uji))}

    leks = PengklasifikasiLeksikon()
    tebak_leks = [leks.prediksi(c.teks).sentimen.value for c in uji]
    hasil[leks.versi] = metrik(benar, tebak_leks)

    catatan_selisih = ""
    if not a.tanpa_indobert:
        from app.klasifikasi.indobert import PengklasifikasiIndoBERT
        ib = PengklasifikasiIndoBERT(a.model)
        tebak_ib = [pr.sentimen.value for pr in ib.prediksi_emiten_banyak([(c.teks, c.target) for c in uji])]
        hasil[ib.versi] = metrik(benar, tebak_ib)
        lo, hi = selang_selisih(benar, tebak_ib, tebak_leks)
        beda = hasil[ib.versi]["macro_f1"] - hasil[leks.versi]["macro_f1"]
        yakin = "nyata (selang tidak memuat 0)" if lo > 0 or hi < 0 else "belum bisa dipastikan (selang memuat 0)"
        catatan_selisih = (f"\nSelisih macro-F1 {ib.versi} − {leks.versi}: **{beda:+.3f}**, "
                           f"selang kepercayaan 95% [{lo:+.3f}, {hi:+.3f}] — {yakin}.\n")

    sebaran = Counter(benar)
    isi = (
        f"# Laporan evaluasi pengklasifikasi sentimen\n\n"
        f"Dibuat {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} pada bagian **uji** label emas: "
        f"{len(uji)} pasangan berita-emiten (" + ", ".join(f"{k} {sebaran[k]}" for k in [x.value for x in KELAS]) + ").\n\n"
        + tabel_md(hasil) + catatan_selisih + "\n## Matriks kebingungan\n\n"
        + "\n".join(matriks_md(n, m) for n, m in hasil.items() if n != "mayoritas")
    )
    LAPORAN.parent.mkdir(parents=True, exist_ok=True)
    LAPORAN.write_text(isi, encoding="utf-8")
    print(isi)
    print(f"Tersimpan di {LAPORAN}")


if __name__ == "__main__":
    main()
