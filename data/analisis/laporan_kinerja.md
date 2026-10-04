# Pengukuran NF-01

Diukur 2026-10-04 12:19 terhadap https://sentimen.raffstw.my.id, 10 ulangan per halaman setelah pemanasan.

## Waktu muat halaman (batas 5 detik)

Jumlah waktu semua permintaan halaman bila dijalankan berurutan — batas atas waktu muat di peramban.

| Halaman | Median | P95 | Maks | Status |
|---|---|---|---|---|
| Dashboard (beranda) | 2.49 dtk | 2.92 dtk | 2.92 dtk | memenuhi |
| Detail emiten (BBCA) | 1.73 dtk | 1.86 dtk | 1.86 dtk | memenuhi |

## Waktu klasifikasi satu berita (batas 2 detik)

Setelah model dimuat; diukur di mesin pengembang.

| Model | Perangkat | Median | P95 | Status |
|---|---|---|---|---|
| leksikon | CPU | 0.0 ms | 0.0 ms | memenuhi |
| TF-IDF + NB | CPU | 0.5 ms | 0.8 ms | memenuhi |
| TF-IDF + SVM | CPU | 0.3 ms | 0.4 ms | memenuhi |
| IndoBERT | GPU | 8.3 ms | 10.7 ms | memenuhi |
| LLM qwen2.5:7b | GPU (Ollama) | 215.1 ms | 223.8 ms | memenuhi |
