# Kuesioner Usability — Sistem Analisis Sentimen Berita Emiten (NF-05)

Instrumen: System Usability Scale (SUS) adaptasi bahasa Indonesia
(Sharfina & Santoso, 2016; Cronbach's α = 0,841). Pindahkan ke Google Forms
dengan urutan butir **tidak diubah**, lalu ekspor jawabannya ke CSV dan jalankan
`python -m scripts.skor_sus berkas.csv`.

Sasaran responden: investor pemula (sesuai NF-05: dapat dipakai investor
pemula tanpa pelatihan khusus). Minimal 15–20 orang; jangan dibantu selama
mengerjakan tugas — kebingungan responden justru yang sedang diukur.

## Bagian A — Data responden

1. Lama berinvestasi saham: belum pernah / < 1 tahun / 1–3 tahun / > 3 tahun
2. Seberapa sering membaca berita saham: tidak pernah / mingguan / harian
3. Perangkat yang dipakai mengerjakan: laptop/komputer / ponsel

## Bagian B — Tugas (kerjakan di https://sentimen.raffstw.my.id)

1. Cari emiten **Bank Central Asia (BBCA)** lewat kotak pencarian.
2. Lihat grafiknya, lalu tentukan apakah sentimen BBCA sebulan terakhir cenderung positif atau negatif.
3. Ubah rentang waktu menjadi **3 bulan** dan tampilkan grafik **per minggu**.
4. Temukan satu berita BBCA yang berstatus **belum diperiksa** atau **rumor**.
5. Dari tabel peringkat, temukan emiten dengan skor sentimen **paling negatif**.
6. Masuk dengan akun uji yang diberikan, tambahkan BBCA ke **watchlist**, lalu atur notifikasinya ke **±0,5**.
7. Buka **panel notifikasi** (ikon lonceng).

Catat (opsional, untuk laporan): tugas mana yang gagal atau butuh waktu lama.

## Bagian C — System Usability Scale

Skala: 1 = sangat tidak setuju, 2 = tidak setuju, 3 = netral, 4 = setuju, 5 = sangat setuju.

1. Saya berpikir akan menggunakan sistem ini lagi.
2. Saya merasa sistem ini rumit untuk digunakan.
3. Saya merasa sistem ini mudah digunakan.
4. Saya membutuhkan bantuan dari orang lain atau teknisi dalam menggunakan sistem ini.
5. Saya merasa fitur-fitur sistem ini berjalan dengan semestinya.
6. Saya merasa ada banyak hal yang tidak konsisten (tidak serasi pada sistem ini).
7. Saya merasa orang lain akan memahami cara menggunakan sistem ini dengan cepat.
8. Saya merasa sistem ini membingungkan.
9. Saya merasa tidak ada hambatan dalam menggunakan sistem ini.
10. Saya perlu membiasakan diri terlebih dahulu sebelum menggunakan sistem ini.

## Bagian D — Masukan terbuka (opsional)

1. Apa yang paling membingungkan?
2. Fitur apa yang paling berguna?

## Rujukan

- Sharfina, Z., & Santoso, H. B. (2016). An Indonesian Adaptation of the System Usability Scale (SUS). *ICACSIS 2016*, 145–148.
- Bangor, A., Kortum, P. T., & Miller, J. T. (2008). An Empirical Evaluation of the System Usability Scale. *International Journal of Human-Computer Interaction, 24*(6), 574–594.
- Sauro, J., & Lewis, J. R. (2016). *Quantifying the User Experience* (2nd ed.). Morgan Kaufmann.
