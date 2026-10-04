"""Melabeli pasangan berita-emiten dengan LLM lokal lewat Ollama (gratis).

    # sekali: pasang Ollama (https://ollama.com) lalu
    ollama pull qwen2.5:7b
    python -m scripts.label_llm                 # semua pasangan yang belum
    python -m scripts.label_llm --batas 50      # uji coba
    python -m scripts.label_llm --model gemma2:9b

Label disimpan sebagai label MODEL dengan versi "llm-<nama model>", berdampingan
dengan label leksikon — bukan sebagai label manusia. Lihat app/klasifikasi/llm.py
untuk dua perannya (metode pembanding dan label perak untuk data latih) dan
kenapa label ini tidak pernah dipakai sebagai data uji.

Hasil disimpan per 25 pasangan dan pasangan yang sudah berlabel dilewati, jadi
proses yang terputus cukup dijalankan ulang untuk melanjutkan.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.klasifikasi.dataset import bagian_data, teks_target, teks_utama
from app.klasifikasi.llm import PengklasifikasiLLM
from app.models import AsalLabel, Berita, BeritaEmiten, Emiten, LabelSentimen

SIMPAN_TIAP = 25


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default=None, help="model Ollama (bawaan: MODEL_LLM / qwen2.5:7b)")
    p.add_argument("--batas", type=int, default=None)
    a = p.parse_args()

    llm = PengklasifikasiLLM(a.model)
    try:
        llm.klien.get(f"{llm.alamat}/api/version").raise_for_status()
    except httpx.HTTPError:
        sys.exit(f"Ollama tidak menjawab di {llm.alamat}. Jalankan aplikasi Ollama lebih dulu.")

    with SessionLocal() as s:
        sudah = set(s.execute(
            select(LabelSentimen.berita_id, LabelSentimen.emiten_id).where(
                LabelSentimen.asal == AsalLabel.MODEL, LabelSentimen.versi_model == llm.versi)
        ).all())
        baris = [r for r in s.execute(
            select(BeritaEmiten, Berita, Emiten)
            .join(Berita, Berita.id == BeritaEmiten.berita_id)
            .join(Emiten, Emiten.id == BeritaEmiten.emiten_id)
            .order_by(Berita.id, Emiten.kode)
        ).all() if (r[0].berita_id, r[0].emiten_id) not in sudah]
        if a.batas:
            baris = baris[: a.batas]
        print(f"{llm.versi}: {len(sudah)} sudah berlabel, {len(baris)} akan dilabeli.", flush=True)

        hitung: Counter[str] = Counter()
        mulai = time.time()
        for i, (kaitan, berita, emiten) in enumerate(baris, start=1):
            pr = llm.prediksi_emiten(teks_utama(berita.judul, berita.ringkasan),
                                     teks_target(emiten.kode, emiten.nama, kaitan.kutipan))
            s.add(LabelSentimen(berita_id=berita.id, emiten_id=emiten.id, sentimen=pr.sentimen,
                                keyakinan=pr.keyakinan, asal=AsalLabel.MODEL, versi_model=llm.versi))
            hitung[pr.sentimen.value] += 1
            if pr.penjelasan:
                hitung["jawaban_tak_dikenal"] += 1
            if i % SIMPAN_TIAP == 0 or i == len(baris):
                s.commit()
                laju = (time.time() - mulai) / i
                sisa = (len(baris) - i) * laju
                print(f"  {i}/{len(baris)}  {laju:.2f} dtk/pasangan  sisa ±{sisa / 60:.0f} menit  "
                      f"{dict(hitung)}", flush=True)

    llm.lepas()
    print(f"\nSelesai. Keyakinan dari logprobs: {'ya' if llm.ada_logprobs else 'tidak (diisi 0,5)'}")
    print("Pembagian data tetap per berita (70/15/15); label pada bagian uji tidak dipakai melatih.")
    _ = bagian_data  # pembagian yang sama dipakai latih_* dan evaluasi_model


if __name__ == "__main__":
    main()
