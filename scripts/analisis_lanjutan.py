"""Analisis hubungan sentimen dan harga di luar korelasi per emiten.

    pip install -r requirements-ml.txt
    python -m scripts.unduh_harga 2026-01-01 2026-12-31 --indeks   # sekali, untuk IHSG
    python -m scripts.analisis_lanjutan
    python -m scripts.analisis_lanjutan --mulai 2026-09-17 --ambang-peristiwa 0.6

Dua analisis, keduanya menjawab kelemahan korelasi per emiten:

1. REGRESI PANEL (efek tetap emiten, galat baku terkluster per emiten)
       r(i, t+lag) = b * sentimen(i, t) + c * r_IHSG(t+lag) + a_i + e
   Korelasi per emiten hanya punya beberapa hari data. Panel menggabungkan
   seluruh emiten sehingga jumlah pengamatannya cukup, sementara efek tetap
   a_i menyerap perbedaan rata-rata return antar-emiten. Return IHSG dijadikan
   kontrol: tanpa itu, sentimen artikel rekap pasar yang mengikuti arah indeks
   akan tampak "berhubungan" dengan harga padahal yang terukur adalah pasar.

2. EVENT STUDY (market model)
   Hari dengan sentimen ekstrem (|skor| >= ambang, minimal 2 berita) menjadi
   peristiwa. Untuk tiap peristiwa, alfa dan beta emiten terhadap IHSG
   diestimasi pada 60 hari bursa sebelumnya (berhenti 6 hari sebelum
   peristiwa), lalu abnormal return = return aktual − return yang diharapkan
   dari pergerakan pasar. CAR dijumlahkan pada beberapa jendela di sekitar
   peristiwa dan diuji apakah rata-ratanya berbeda dari nol.

Keduanya dijalankan dua kali: dengan semua berita, dan hanya berita yang
menyebut satu emiten (tanpa artikel rekap). Hasil yang hanya muncul saat rekap
diikutkan menandakan yang terukur adalah pergerakan pasar, bukan sentimen per
emiten. Laporkan keduanya.

Sesuai SRS 10.3, ini analisis hubungan, bukan model prediksi harga.
Keluaran: data/analisis/laporan_analisis.md
"""

from __future__ import annotations

import argparse
import math
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select

from app.analitik.agregasi import hitung_skor_harian
from app.analitik.korelasi import ambil_harga
from app.database import SessionLocal
from app.models import Emiten

BERKAS_IHSG = Path("data/indeks/IHSG.csv")
LAPORAN = Path("data/analisis/laporan_analisis.md")
JENDELA_ESTIMASI = (-65, -6)   # hari bursa relatif terhadap peristiwa
MIN_ESTIMASI = 30
JENDELA_CAR = {"[-1,+1]": (-1, 1), "[0,+1]": (0, 1), "[0,+3]": (0, 3)}


def tanggal(teks: str) -> date:
    return datetime.strptime(teks, "%Y-%m-%d").date()


def muat_ihsg():
    import pandas as pd

    if not BERKAS_IHSG.exists():
        raise SystemExit(f"{BERKAS_IHSG} belum ada. Jalankan: python -m scripts.unduh_harga 2026-01-01 "
                         f"{date.today()} --indeks")
    d = pd.read_csv(BERKAS_IHSG, parse_dates=["tanggal"]).dropna(subset=["penutupan"])
    d["tanggal"] = d["tanggal"].dt.date
    d = d.sort_values("tanggal").set_index("tanggal")["penutupan"]
    return d.pct_change().dropna()


def kumpulkan(session, mulai: date, sampai: date, maks_emiten: int | None):
    """Satu baris per (emiten, hari bursa): return emiten, return pasar, skor."""
    import pandas as pd

    pasar = muat_ihsg()
    hari_bursa = list(pasar.index)
    harga_mulai = date(mulai.year, 1, 1) if mulai.month > 3 else date(mulai.year - 1, 10, 1)

    baris_harga, baris_sentimen = [], []
    for e in session.scalars(select(Emiten).where(Emiten.aktif.is_(True)).order_by(Emiten.kode)):
        h = ambil_harga(session, e.kode, harga_mulai, sampai)
        for t, v in h.items():
            baris_harga.append((e.kode, t, v))
        for s in hitung_skor_harian(session, e.kode, mulai, sampai, maks_emiten_per_berita=maks_emiten):
            # berita hari libur bursa dipetakan ke hari bursa berikutnya
            t = next((h_ for h_ in hari_bursa if h_ >= s.tanggal), None)
            if t is not None:
                baris_sentimen.append((e.kode, t, s.skor, s.jumlah_berita))

    harga = pd.DataFrame(baris_harga, columns=["kode", "tanggal", "tutup"]).sort_values(["kode", "tanggal"])
    harga["r"] = harga.groupby("kode")["tutup"].pct_change()
    harga = harga.dropna(subset=["r"])
    harga["r_pasar"] = harga["tanggal"].map(pasar)
    harga = harga.dropna(subset=["r_pasar"])

    sent = pd.DataFrame(baris_sentimen, columns=["kode", "tanggal", "skor", "berita"])
    if not sent.empty:
        # beberapa hari kalender bisa jatuh ke hari bursa yang sama (akhir pekan)
        sent["bobot"] = sent["skor"] * sent["berita"]
        sent = sent.groupby(["kode", "tanggal"], as_index=False)[["bobot", "berita"]].sum()
        sent["skor"] = sent["bobot"] / sent["berita"]
        sent = sent.drop(columns="bobot")
    return harga, sent


def regresi_panel(harga, sent, lag: int) -> dict | None:
    import statsmodels.formula.api as smf

    if sent.empty:
        return None
    h = harga.copy()
    # r(t+lag): geser return ke belakang `lag` hari bursa per emiten
    h["r_maju"] = h.groupby("kode")["r"].shift(-lag)
    h["r_pasar_maju"] = h.groupby("kode")["r_pasar"].shift(-lag)
    d = sent.merge(h[["kode", "tanggal", "r_maju", "r_pasar_maju"]], on=["kode", "tanggal"]).dropna()
    if len(d) < 20 or d["kode"].nunique() < 3:
        return {"n": len(d), "emiten": d["kode"].nunique(), "catatan": "data belum cukup"}
    m = smf.ols("r_maju ~ skor + r_pasar_maju + C(kode)", data=d).fit(
        cov_type="cluster", cov_kwds={"groups": d["kode"]})
    return {
        "n": int(m.nobs), "emiten": int(d["kode"].nunique()),
        "b": m.params["skor"], "se": m.bse["skor"], "p": m.pvalues["skor"],
        "c": m.params["r_pasar_maju"], "r2": m.rsquared,
    }


def event_study(harga, sent, ambang: float) -> dict:
    import numpy as np
    from scipy import stats

    peristiwa = sent[(sent["skor"].abs() >= ambang) & (sent["berita"] >= 2)]
    car: dict[str, dict[str, list[float]]] = {"positif": {k: [] for k in JENDELA_CAR},
                                              "negatif": {k: [] for k in JENDELA_CAR}}
    dilewati = 0
    per_emiten = {k: g.reset_index(drop=True) for k, g in harga.groupby("kode")}
    for _, ev in peristiwa.iterrows():
        g = per_emiten.get(ev["kode"])
        if g is None:
            dilewati += 1
            continue
        idx = g.index[g["tanggal"] == ev["tanggal"]]
        if len(idx) == 0:
            dilewati += 1
            continue
        i0 = int(idx[0])
        est = g.iloc[max(0, i0 + JENDELA_ESTIMASI[0]): max(0, i0 + JENDELA_ESTIMASI[1])]
        akhir = max(b for _, b in JENDELA_CAR.values())
        if len(est) < MIN_ESTIMASI or i0 + akhir >= len(g) or i0 - 1 < 0:
            dilewati += 1  # estimasi kurang panjang, atau hari sesudah peristiwa belum terjadi
            continue
        beta, alfa = np.polyfit(est["r_pasar"], est["r"], 1)
        ar = g["r"] - (alfa + beta * g["r_pasar"])
        kelompok = "positif" if ev["skor"] > 0 else "negatif"
        for nama, (a, b) in JENDELA_CAR.items():
            car[kelompok][nama].append(float(ar.iloc[i0 + a: i0 + b + 1].sum()))

    hasil = {"peristiwa": len(peristiwa), "dilewati": dilewati, "kelompok": {}}
    for kel, jendela in car.items():
        hasil["kelompok"][kel] = {}
        for nama, nilai in jendela.items():
            if len(nilai) >= 2:
                t, p = stats.ttest_1samp(nilai, 0.0)
                hasil["kelompok"][kel][nama] = (len(nilai), float(np.mean(nilai)), float(t), float(p))
            else:
                hasil["kelompok"][kel][nama] = (len(nilai), float(np.mean(nilai)) if nilai else math.nan,
                                                math.nan, math.nan)
    return hasil


def persen(v: float) -> str:
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v * 100:+.2f}%"


def angka(v: float, d: int = 3) -> str:
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{d}f}"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mulai", type=tanggal, default=date(2026, 9, 1))
    p.add_argument("--sampai", type=tanggal, default=date.today())
    p.add_argument("--ambang-peristiwa", type=float, default=0.5)
    a = p.parse_args()

    bagian = [f"# Analisis lanjutan sentimen dan harga\n\nRentang sentimen {a.mulai} s/d {a.sampai}. "
              f"Dibuat {datetime.now().strftime('%Y-%m-%d %H:%M')}. Sesuai SRS 10.3, ini analisis hubungan, "
              "bukan prediksi harga.\n"]
    with SessionLocal() as s:
        for judul, maks in (("Semua berita", None), ("Tanpa artikel rekap (1 emiten per berita)", 1)):
            harga, sent = kumpulkan(s, a.mulai, a.sampai, maks)
            bagian.append(f"\n## {judul}\n\n{len(sent)} pasangan emiten-hari bursa bersentimen, "
                          f"{sent['kode'].nunique() if not sent.empty else 0} emiten.\n")

            bagian.append("\n### Regresi panel\n\n`r(i,t+lag) = b·sentimen(i,t) + c·r_IHSG(t+lag) + a_i`, "
                          "galat baku terkluster per emiten.\n\n"
                          "| Lag | N | Emiten | b (sentimen) | SE | p | c (IHSG) | R² |\n|---|---|---|---|---|---|---|---|\n")
            for lag in (0, 1):
                r = regresi_panel(harga, sent, lag)
                if r is None or "b" not in r:
                    n = r["n"] if r else 0
                    bagian.append(f"| {lag} | {n} | {r['emiten'] if r else 0} | data belum cukup | | | | |\n")
                    continue
                bagian.append(f"| {lag} | {r['n']} | {r['emiten']} | {persen(r['b'])} | {persen(r['se'])} | "
                              f"{angka(r['p'])} | {angka(r['c'], 2)} | {angka(r['r2'])} |\n")
            bagian.append("\n_b_ dibaca: kenaikan skor sentimen 1 poin (skala −1…+1) berkaitan dengan perubahan "
                          "return sebesar _b_, setelah memperhitungkan pergerakan IHSG.\n")

            ev = event_study(harga, sent, a.ambang_peristiwa) if not sent.empty else None
            bagian.append(f"\n### Event study (|skor| ≥ {a.ambang_peristiwa}, ≥ 2 berita)\n\n")
            if ev is None:
                bagian.append("Belum ada data sentimen.\n")
                continue
            bagian.append(f"{ev['peristiwa']} peristiwa, {ev['dilewati']} dilewati (data estimasi kurang "
                          "atau hari sesudahnya belum terjadi).\n\n| Kelompok | Jendela | N | CAR rata-rata | t | p |\n"
                          "|---|---|---|---|---|---|\n")
            for kel, jendela in ev["kelompok"].items():
                for nama, (n, rerata, t, pv) in jendela.items():
                    bagian.append(f"| {kel} | {nama} | {n} | {persen(rerata)} | {angka(t, 2)} | {angka(pv)} |\n")

    bagian.append("\n## Cara membaca\n\n- p < 0,05 berarti hubungan itu kecil kemungkinannya muncul "
                  "kebetulan; p di atas itu berarti data belum cukup untuk menyimpulkan apa pun — bukan "
                  "bukti bahwa hubungannya tidak ada.\n- Dengan data sentimen yang baru beberapa minggu, "
                  "jumlah peristiwa dan pengamatan masih kecil. Jalankan ulang saat data bertambah.\n"
                  "- Peristiwa dari emiten yang sama bisa berdekatan sehingga jendelanya tumpang-tindih; "
                  "uji t mengabaikan ketergantungan itu, jadi p-nya cenderung terlalu optimistis.\n")
    isi = "".join(bagian)
    LAPORAN.parent.mkdir(parents=True, exist_ok=True)
    LAPORAN.write_text(isi, encoding="utf-8")
    print(isi)
    print(f"Tersimpan di {LAPORAN}")


if __name__ == "__main__":
    main()
