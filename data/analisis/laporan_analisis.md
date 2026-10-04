# Analisis lanjutan sentimen dan harga

Rentang sentimen 2026-09-01 s/d 2026-10-04. Dibuat 2026-10-04 11:40. Sesuai SRS 10.3, ini analisis hubungan, bukan prediksi harga.

## Semua berita

326 pasangan emiten-hari bursa bersentimen, 45 emiten.

### Regresi panel

`r(i,t+lag) = b·sentimen(i,t) + c·r_IHSG(t+lag) + a_i`, galat baku terkluster per emiten.

| Lag | N | Emiten | b (sentimen) | SE | p | c (IHSG) | R² |
|---|---|---|---|---|---|---|---|
| 0 | 326 | 45 | +0.78% | +0.33% | 0.017 | 1.13 | 0.362 |
| 1 | 294 | 44 | -0.13% | +0.29% | 0.643 | 1.20 | 0.287 |

_b_ dibaca: kenaikan skor sentimen 1 poin (skala −1…+1) berkaitan dengan perubahan return sebesar _b_, setelah memperhitungkan pergerakan IHSG.

### Event study (|skor| ≥ 0.5, ≥ 2 berita)

85 peristiwa, 24 dilewati (data estimasi kurang atau hari sesudahnya belum terjadi).

| Kelompok | Jendela | N | CAR rata-rata | t | p |
|---|---|---|---|---|---|
| positif | [-1,+1] | 22 | +1.12% | 1.52 | 0.143 |
| positif | [0,+1] | 22 | +0.72% | 0.94 | 0.356 |
| positif | [0,+3] | 22 | +0.32% | 0.37 | 0.714 |
| negatif | [-1,+1] | 39 | -2.46% | -1.81 | 0.078 |
| negatif | [0,+1] | 39 | -1.97% | -1.81 | 0.078 |
| negatif | [0,+3] | 39 | -3.05% | -1.81 | 0.078 |

## Tanpa artikel rekap (1 emiten per berita)

159 pasangan emiten-hari bursa bersentimen, 40 emiten.

### Regresi panel

`r(i,t+lag) = b·sentimen(i,t) + c·r_IHSG(t+lag) + a_i`, galat baku terkluster per emiten.

| Lag | N | Emiten | b (sentimen) | SE | p | c (IHSG) | R² |
|---|---|---|---|---|---|---|---|
| 0 | 159 | 40 | +0.45% | +0.76% | 0.548 | 1.12 | 0.465 |
| 1 | 142 | 38 | +0.45% | +0.53% | 0.399 | 0.88 | 0.368 |

_b_ dibaca: kenaikan skor sentimen 1 poin (skala −1…+1) berkaitan dengan perubahan return sebesar _b_, setelah memperhitungkan pergerakan IHSG.

### Event study (|skor| ≥ 0.5, ≥ 2 berita)

29 peristiwa, 5 dilewati (data estimasi kurang atau hari sesudahnya belum terjadi).

| Kelompok | Jendela | N | CAR rata-rata | t | p |
|---|---|---|---|---|---|
| positif | [-1,+1] | 17 | +2.01% | 2.96 | 0.009 |
| positif | [0,+1] | 17 | +1.51% | 2.71 | 0.015 |
| positif | [0,+3] | 17 | +1.22% | 2.25 | 0.039 |
| negatif | [-1,+1] | 7 | -4.51% | -1.13 | 0.301 |
| negatif | [0,+1] | 7 | -3.90% | -0.95 | 0.380 |
| negatif | [0,+3] | 7 | -6.85% | -0.87 | 0.418 |

## Cara membaca

- p < 0,05 berarti hubungan itu kecil kemungkinannya muncul kebetulan; p di atas itu berarti data belum cukup untuk menyimpulkan apa pun — bukan bukti bahwa hubungannya tidak ada.
- Dengan data sentimen yang baru beberapa minggu, jumlah peristiwa dan pengamatan masih kecil. Jalankan ulang saat data bertambah.
- Peristiwa dari emiten yang sama bisa berdekatan sehingga jendelanya tumpang-tindih; uji t mengabaikan ketergantungan itu, jadi p-nya cenderung terlalu optimistis.
