"""Mengunggah model IndoBERT hasil fine-tuning ke Hugging Face Hub (gratis).

    huggingface-cli login                       # sekali, pakai token "write"
    python -m scripts.unggah_model nama-akun/indobert-sentimen-emiten
    python -m scripts.unggah_model nama-akun/indobert-sentimen-emiten --publik

Kenapa Hub, bukan git: modelnya ±500 MB, melebihi batas berkas GitHub, dan
siklus terjadwal di GitHub Actions perlu mengunduhnya. Setelah diunggah, isi
secret GitHub Actions:

    MODEL_INDOBERT = nama-akun/indobert-sentimen-emiten
    HF_TOKEN       = token "read" (hanya bila repositori model privat)

Siklus berikutnya melabeli berita baru dengan IndoBERT. Jalankan juga sekali
dari laptop agar berita lama ikut berlabel IndoBERT — tanpa itu dasbor
memakai dua sumber label sekaligus (lama: leksikon, baru: IndoBERT):

    python -m scripts.klasifikasi --model indobert --ulangi

Lakukan ini HANYA setelah scripts/evaluasi_model.py pada data uji manusia
menunjukkan IndoBERT lebih baik daripada leksikon.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.klasifikasi.indobert import LOKASI_BAWAAN


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("repo", help="nama-akun/nama-model di Hugging Face")
    p.add_argument("--folder", default=LOKASI_BAWAAN)
    p.add_argument("--publik", action="store_true", help="repositori model publik (bawaan: privat)")
    a = p.parse_args()

    from huggingface_hub import HfApi

    folder = Path(a.folder)
    if not (folder / "config.json").exists():
        raise SystemExit(f"{folder} bukan folder model. Latih dulu: python -m scripts.latih_indobert")
    api = HfApi()
    api.create_repo(a.repo, private=not a.publik, exist_ok=True)
    api.upload_folder(folder_path=str(folder), repo_id=a.repo,
                      commit_message="Model IndoBERT sentimen berita emiten")
    print(f"Terunggah: https://huggingface.co/{a.repo}")
    print("Isi secret GitHub Actions MODEL_INDOBERT dengan nama repositori itu.")


if __name__ == "__main__":
    main()
