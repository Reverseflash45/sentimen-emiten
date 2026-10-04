"""Melatih pembanding klasik: TF-IDF + Naive Bayes dan TF-IDF + SVM (SRS 10.2).

    pip install -r requirements-ml.txt
    python -m scripts.latih_klasik              # keduanya
    python -m scripts.latih_klasik --jenis svm
    python -m scripts.latih_klasik --perak auto   # + label LLM untuk data latih

Data dan pembagiannya sama dengan scripts/latih_indobert.py: label manusia
buatan manusia, per berita, 70/15/15. Hiperparameter (alpha untuk NB, C untuk
SVM) dipilih pada data VALIDASI; data uji hanya dibaca scripts/evaluasi_model.py.

Tidak butuh GPU — pelatihan selesai dalam hitungan detik di laptop mana pun.

Keluaran: model/klasik-nb.joblib dan model/klasik-svm.joblib.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter

from app.database import SessionLocal
from app.klasifikasi.dataset import muat_data_latih, versi_llm_terbaru
from app.klasifikasi.klasik import JENIS, VERSI, latih, lokasi_model

MINIMAL_LATIH = 200


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--jenis", choices=[*JENIS, "semua"], default="semua")
    p.add_argument("--folder", default=None, help="folder keluaran (bawaan: MODEL_KLASIK / model)")
    p.add_argument("--paksa", action="store_true", help=f"tetap latih walau data latih < {MINIMAL_LATIH}")
    p.add_argument("--perak", default=None,
                   help="versi label LLM (mis. llm-qwen2.5-7b) atau 'auto' untuk melengkapi data latih/validasi")
    a = p.parse_args()

    import joblib

    with SessionLocal() as s:
        perak = versi_llm_terbaru(s) if a.perak == "auto" else a.perak
        data = muat_data_latih(s, perak)
    data_latih = [c for c in data if c.bagian == "latih"]
    validasi = [c for c in data if c.bagian == "validasi"]
    asal = Counter(c.asal for c in data)
    print(f"Data latih {len(data_latih)}, validasi {len(validasi)} — sumber label: {dict(asal)}"
          + (f" (perak: {perak})" if perak else "") + ". Bagian uji tidak disentuh.")
    print("Sebaran latih:", dict(Counter(c.sentimen.value for c in data_latih)))
    if len(data_latih) < MINIMAL_LATIH and not a.paksa:
        sys.exit(f"Data latih baru {len(data_latih)}. Tambah label dengan scripts.label_manual "
                 f"(butuh ≥ {MINIMAL_LATIH}), atau pakai --paksa untuk uji coba.")
    if not validasi:
        sys.exit("Belum ada data validasi. Tambah label dulu.")
    if len({c.sentimen for c in data_latih}) < 2:
        sys.exit("Data latih baru berisi satu kelas — model tidak bisa belajar membedakan apa pun.")

    for jenis in JENIS if a.jenis == "semua" else [a.jenis]:
        mulai = time.time()
        hasil = latih(jenis, data_latih, validasi)
        jalur = lokasi_model(jenis, a.folder)
        jalur.parent.mkdir(parents=True, exist_ok=True)
        metrik = {
            "versi": VERSI[jenis],
            "hiperparameter_terpilih": hasil.param,
            "macro_f1_validasi": round(hasil.f1_validasi, 4),
            "semua_percobaan": [{"param": prm, "macro_f1_validasi": round(f1, 4)} for prm, f1 in hasil.percobaan],
            "jumlah": {"latih": len(data_latih), "validasi": len(validasi)},
            "sumber_label": {"perak": perak, "per_asal": dict(asal)},
            "catatan_validasi": "terhadap label perak LLM" if perak else "terhadap label manusia",
            "durasi_detik": round(time.time() - mulai, 2),
        }
        joblib.dump({"pipeline": hasil.pipeline, "metrik": metrik}, jalur)
        jalur.with_suffix(".json").write_text(json.dumps(metrik, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"\n{VERSI[jenis]}")
        for prm, f1 in hasil.percobaan:
            tanda = "  ← terpilih" if prm == hasil.param else ""
            print(f"  {prm}  macro-F1 validasi {f1:.4f}{tanda}")
        print(f"  tersimpan di {jalur}")

    print("\nBerikutnya:  python -m scripts.evaluasi_model")


if __name__ == "__main__":
    main()
