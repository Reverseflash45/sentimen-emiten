"""Fine-tuning IndoBERT untuk sentimen berita per emiten.

    pip install -r requirements-ml.txt
    python -m scripts.latih_indobert
    python -m scripts.latih_indobert --epoch 6 --lr 3e-5

Data: label emas buatan manusia (scripts/label_manual.py), dibagi per berita
menjadi latih/validasi/uji (lihat app/klasifikasi/dataset.py). Bagian UJI tidak
disentuh sama sekali di sini — ia hanya dipakai scripts/evaluasi_model.py,
supaya angka akhir tidak ikut "dioptimalkan" selama memilih epoch terbaik.

Masukan berupa pasangan kalimat: [judul + ringkasan] [SEP] [kode (nama). kutipan].
Segmen kedua memberi tahu model emiten mana yang sedang dinilai.

Keluaran: folder model/indobert-sentimen (model + tokenizer + metrik.json).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

from app.database import SessionLocal
from app.klasifikasi.dataset import KELAS, Contoh, muat_label_emas
from app.klasifikasi.indobert import LOKASI_BAWAAN, PANJANG_MAKS

MODEL_DASAR = "indobenchmark/indobert-base-p1"
MINIMAL_LATIH = 200


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dasar", default=MODEL_DASAR, help="model pra-latih dari Hugging Face")
    p.add_argument("--keluaran", default=LOKASI_BAWAAN)
    p.add_argument("--epoch", type=int, default=5)
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--paksa", action="store_true", help=f"tetap latih walau data latih < {MINIMAL_LATIH}")
    a = p.parse_args()

    import numpy as np
    import torch
    from sklearn.metrics import classification_report, f1_score
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

    random.seed(a.seed)
    np.random.seed(a.seed)
    torch.manual_seed(a.seed)

    with SessionLocal() as s:
        data = muat_label_emas(s)
    latih = [c for c in data if c.bagian == "latih"]
    validasi = [c for c in data if c.bagian == "validasi"]
    print(f"Label emas: {len(data)} (latih {len(latih)}, validasi {len(validasi)}, "
          f"uji {len(data) - len(latih) - len(validasi)} — disimpan untuk evaluasi)")
    print("Sebaran latih:", dict(Counter(c.sentimen.value for c in latih)))
    if len(latih) < MINIMAL_LATIH and not a.paksa:
        sys.exit(f"Data latih baru {len(latih)}. Tambah label dengan scripts.label_manual "
                 f"(butuh ≥ {MINIMAL_LATIH}), atau pakai --paksa untuk uji coba.")
    if not validasi:
        sys.exit("Belum ada data validasi. Tambah label dulu.")

    perangkat = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Perangkat: {perangkat}" + (f" ({torch.cuda.get_device_name(0)})" if perangkat == "cuda" else ""))

    indeks = {k: i for i, k in enumerate(KELAS)}
    tokenizer = AutoTokenizer.from_pretrained(a.dasar)
    model = AutoModelForSequenceClassification.from_pretrained(
        a.dasar, num_labels=len(KELAS),
        id2label={i: k.value for i, k in enumerate(KELAS)},
        label2id={k.value: i for i, k in enumerate(KELAS)},
    ).to(perangkat)

    def kumpulkan(contoh: list[Contoh]):
        enc = tokenizer([c.teks for c in contoh], [c.target for c in contoh], truncation="longest_first",
                        max_length=PANJANG_MAKS, padding=True, return_tensors="pt")
        enc["labels"] = torch.tensor([indeks[c.sentimen] for c in contoh])
        return enc

    muat_latih = DataLoader(latih, batch_size=a.batch, shuffle=True, collate_fn=kumpulkan,
                            generator=torch.Generator().manual_seed(a.seed))
    muat_val = DataLoader(validasi, batch_size=a.batch * 2, collate_fn=kumpulkan)

    # bobot kelas: data berita cenderung didominasi satu kelas; tanpa bobot,
    # model bisa "menang" hanya dengan menebak kelas mayoritas
    hitung = Counter(indeks[c.sentimen] for c in latih)
    bobot = torch.tensor([len(latih) / (len(KELAS) * max(1, hitung[i])) for i in range(len(KELAS))],
                         dtype=torch.float, device=perangkat)
    fungsi_rugi = torch.nn.CrossEntropyLoss(weight=bobot)

    optim = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    total = len(muat_latih) * a.epoch
    jadwal = get_linear_schedule_with_warmup(optim, int(total * 0.1), total)
    presisi_campuran = perangkat == "cuda"
    penskala = torch.amp.GradScaler("cuda", enabled=presisi_campuran)

    def nilai() -> tuple[float, list[int], list[int]]:
        model.eval()
        benar, tebak = [], []
        with torch.inference_mode():
            for batch in muat_val:
                label = batch.pop("labels")
                batch = {k: v.to(perangkat) for k, v in batch.items()}
                with torch.autocast(perangkat, enabled=presisi_campuran):
                    logit = model(**batch).logits
                tebak += logit.argmax(-1).cpu().tolist()
                benar += label.tolist()
        model.train()
        return f1_score(benar, tebak, average="macro"), benar, tebak

    terbaik, epoch_terbaik, sabar = -1.0, 0, 0
    keluaran = Path(a.keluaran)
    mulai = time.time()
    model.train()
    for epoch in range(1, a.epoch + 1):
        rugi_total = 0.0
        for batch in muat_latih:
            label = batch.pop("labels").to(perangkat)
            batch = {k: v.to(perangkat) for k, v in batch.items()}
            with torch.autocast(perangkat, enabled=presisi_campuran):
                rugi = fungsi_rugi(model(**batch).logits.float(), label)
            optim.zero_grad(set_to_none=True)
            penskala.scale(rugi).backward()
            penskala.unscale_(optim)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            penskala.step(optim)
            penskala.update()
            jadwal.step()
            rugi_total += rugi.item()
        f1, benar, tebak = nilai()
        print(f"epoch {epoch}: rugi latih {rugi_total / len(muat_latih):.4f} · macro-F1 validasi {f1:.4f}")
        if f1 > terbaik:
            terbaik, epoch_terbaik, sabar = f1, epoch, 0
            keluaran.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(keluaran)
            tokenizer.save_pretrained(keluaran)
            laporan = classification_report(benar, tebak, labels=list(range(len(KELAS))),
                                            target_names=[k.value for k in KELAS], digits=4, zero_division=0)
        else:
            sabar += 1
            if sabar >= 2:
                print("Validasi tidak membaik 2 epoch berturut-turut — berhenti lebih awal.")
                break

    metrik = {
        "model_dasar": a.dasar, "epoch_terbaik": epoch_terbaik, "macro_f1_validasi": round(terbaik, 4),
        "jumlah": {"latih": len(latih), "validasi": len(validasi)},
        "sebaran_latih": {KELAS[i].value: hitung[i] for i in range(len(KELAS))},
        "hiperparameter": {"epoch_maks": a.epoch, "lr": a.lr, "batch": a.batch, "seed": a.seed,
                           "panjang_maks": PANJANG_MAKS},
        "durasi_detik": round(time.time() - mulai),
    }
    (keluaran / "metrik.json").write_text(json.dumps(metrik, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nModel terbaik (epoch {epoch_terbaik}) tersimpan di {keluaran}")
    print(laporan)
    print("Berikutnya:  python -m scripts.evaluasi_model")


if __name__ == "__main__":
    main()
