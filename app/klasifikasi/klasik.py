"""Pembanding klasik untuk IndoBERT: TF-IDF + Naive Bayes dan TF-IDF + SVM
(SRS 10.2).

Kedua model membaca masukan yang SAMA PERSIS dengan IndoBERT — teks berita
ditambah segmen emiten (kode, nama, kutipan) — dan dilatih pada pembagian data
yang sama. Kalau masukannya berbeda, selisih kinerja tidak bisa lagi dibaca
sebagai selisih metode: bisa saja yang menang hanya model yang diberi
informasi lebih banyak.

Yang membedakan ketiganya hanya cara membaca teks:
  - TF-IDF memperlakukan teks sebagai kumpulan kata lepas (tanpa urutan),
  - Naive Bayes menganggap tiap kata berdiri sendiri terhadap kelasnya,
  - SVM mencari batas pemisah antar-kelas pada ruang kata itu,
  - IndoBERT membaca kata dalam konteksnya.
Selisih SVM → IndoBERT karenanya mengukur sumbangan pemahaman konteks.

scikit-learn diimpor saat dipakai, bukan saat modul dimuat — server web tidak
memasangnya.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path

from app.klasifikasi.basis import Pengklasifikasi, Prediksi
from app.klasifikasi.dataset import KELAS, Contoh
from app.models import Sentimen

JENIS = ("nb", "svm")
VERSI = {"nb": "nb-tfidf-v1", "svm": "svm-tfidf-v1"}
FOLDER_BAWAAN = "model"

#: kisi hiperparameter yang dicoba pada data validasi
KISI = {
    "nb": [{"alpha": a} for a in (0.01, 0.05, 0.1, 0.3, 1.0)],
    "svm": [{"C": c} for c in (0.01, 0.1, 0.3, 1.0, 3.0, 10.0)],
}


def masukan(teks: str, target: str) -> str:
    """Satu string dari pasangan kalimat IndoBERT. Pemisah [SEP] tidak berarti
    apa-apa bagi TF-IDF, jadi cukup disambung."""
    return f"{teks} {target}".strip()


def bangun(jenis: str, param: dict):
    """Pipeline TF-IDF + pengklasifikasi.

    Unigram dan bigram, supaya frasa seperti "laba turun" atau "net sell"
    terbaca sebagai satu ciri — kata lepasnya sering bermakna sebaliknya.
    `sublinear_tf` meredam kata yang diulang-ulang dalam satu berita.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
    from sklearn.svm import LinearSVC

    vektor = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), sublinear_tf=True, min_df=1)
    if jenis == "nb":
        model = MultinomialNB(alpha=param["alpha"])
    elif jenis == "svm":
        # bobot kelas seimbang: sama alasannya dengan bobot kelas di pelatihan
        # IndoBERT — tanpa itu model bisa "menang" dengan menebak kelas mayoritas
        model = LinearSVC(C=param["C"], class_weight="balanced", random_state=42)
    else:
        raise ValueError(f"jenis tidak dikenal: {jenis}")
    return Pipeline([("tfidf", vektor), ("model", model)])


def _f1_makro(benar: list[str], tebak: list[str]) -> float:
    from sklearn.metrics import f1_score

    return f1_score(benar, tebak, labels=[k.value for k in KELAS], average="macro", zero_division=0)


@dataclass
class HasilLatih:
    pipeline: object
    jenis: str
    param: dict
    f1_validasi: float
    percobaan: list[tuple[dict, float]]


def latih(jenis: str, latih_: list[Contoh], validasi: list[Contoh]) -> HasilLatih:
    """Memilih hiperparameter terbaik pada data VALIDASI, lalu mengembalikan
    model yang dilatih pada data latih saja — sama seperti IndoBERT memilih
    epoch terbaik pada validasi. Data uji tidak disentuh."""
    x_latih = [masukan(c.teks, c.target) for c in latih_]
    y_latih = [c.sentimen.value for c in latih_]
    x_val = [masukan(c.teks, c.target) for c in validasi]
    y_val = [c.sentimen.value for c in validasi]

    percobaan: list[tuple[dict, float]] = []
    terbaik: tuple[float, dict, object] | None = None
    for param in KISI[jenis]:
        pipa = bangun(jenis, param).fit(x_latih, y_latih)
        f1 = _f1_makro(y_val, list(pipa.predict(x_val)))
        percobaan.append((param, f1))
        if terbaik is None or f1 > terbaik[0]:
            terbaik = (f1, param, pipa)
    assert terbaik is not None
    return HasilLatih(pipeline=terbaik[2], jenis=jenis, param=terbaik[1],
                      f1_validasi=terbaik[0], percobaan=percobaan)


def lokasi_model(jenis: str, folder: str | Path | None = None) -> Path:
    folder = folder or os.environ.get("MODEL_KLASIK") or FOLDER_BAWAAN
    return Path(folder) / f"klasik-{jenis}.joblib"


def _softmax(skor: list[float]) -> list[float]:
    m = max(skor)
    e = [math.exp(s - m) for s in skor]
    t = sum(e)
    return [v / t for v in e]


class PengklasifikasiKlasik(Pengklasifikasi):
    """Membungkus pipeline TF-IDF tersimpan sebagai `Pengklasifikasi`.

    Keyakinan Naive Bayes adalah peluang dari model itu sendiri. SVM tidak
    menghasilkan peluang; keyakinannya adalah softmax dari jarak ke batas
    pemisah. Nilai itu menjaga URUTAN keyakinan (dipakai antrean analis dan
    bobot agregasi), tetapi bukan peluang terkalibrasi — jangan dibandingkan
    langsung dengan keyakinan IndoBERT.
    """

    per_emiten = True

    def __init__(self, jenis: str, lokasi: str | Path | None = None, pipeline=None) -> None:
        if jenis not in JENIS:
            raise ValueError(f"jenis harus salah satu dari {JENIS}")
        self.jenis = jenis
        self.versi = VERSI[jenis]
        if pipeline is None:
            import joblib

            jalur = Path(lokasi) if lokasi else lokasi_model(jenis)
            if not jalur.exists():
                raise FileNotFoundError(
                    f"{jalur} belum ada. Latih dulu:  python -m scripts.latih_klasik --jenis {jenis}"
                )
            simpanan = joblib.load(jalur)
            pipeline = simpanan["pipeline"]
        self.pipeline = pipeline

    def prediksi(self, teks: str) -> Prediksi:
        return self.prediksi_emiten(teks, "")

    def prediksi_emiten(self, teks: str, target: str) -> Prediksi:
        return self.prediksi_emiten_banyak([(teks, target)])[0]

    def prediksi_emiten_banyak(self, pasangan: list[tuple[str, str]]) -> list[Prediksi]:
        if not pasangan:
            return []
        x = [masukan(t, s) for t, s in pasangan]
        kelas = [Sentimen(k) for k in self.pipeline.classes_]
        if self.jenis == "nb":
            baris = self.pipeline.predict_proba(x).tolist()
        else:
            skor = self.pipeline.decision_function(x)
            # dua kelas saja di data latih: decision_function berdimensi satu
            baris = [_softmax([-s, s]) for s in skor.tolist()] if skor.ndim == 1 else [
                _softmax(r) for r in skor.tolist()
            ]
        hasil = []
        for p in baris:
            j = max(range(len(p)), key=p.__getitem__)
            hasil.append(Prediksi(sentimen=kelas[j], keyakinan=float(p[j])))
        return hasil
