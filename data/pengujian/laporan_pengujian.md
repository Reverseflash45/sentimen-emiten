# Laporan pengujian black-box

Dibuat 2026-10-04 12:21 dari hasil uji otomatis.

**36 dari 36 skenario lulus** · 255 dari 255 uji otomatis lulus.

| No | Kebutuhan | Skenario | Masukan | Hasil yang diharapkan | Jenis | Status |
|---|---|---|---|---|---|---|
| 1 | UC-01 | Melihat deret sentimen dan harga | Pilih emiten BBCA, rentang September | Deret skor harian dan harga penutupan tampil | API | Lulus |
| 2 | UC-01 | Korelasi dihitung terhadap imbal hasil | Emiten dengan data 10 hari | Pearson dan Spearman tampil beserta kekuatannya | API | Lulus |
| 3 | UC-01 3a | Data belum mencukupi | Rentang dengan kurang dari 4 hari beririsan | Pesan 'data belum cukup', bukan galat | API | Lulus |
| 4 | UC-01 | Rentang tanggal tidak valid | Tanggal mulai setelah tanggal sampai | Permintaan ditolak dengan pesan jelas | API | Lulus |
| 5 | UC-01 | Emiten tidak dikenal | Kode emiten yang tidak terdaftar | Respons 404 'tidak ditemukan' | API | Lulus |
| 6 | UC-01 | Pencarian emiten | Ketik nama perusahaan sebagian | Emiten yang cocok muncul | API | Lulus |
| 7 | UC-01 | Daftar berita dan saringannya | Saring berita BBCA berdasarkan sentimen | Hanya berita dengan sentimen itu yang tampil | API | Lulus |
| 8 | UC-02 | Menambah dan melihat watchlist | Pengguna masuk, tambah BBCA | BBCA tampil di watchlist | API | Lulus |
| 9 | UC-02 | Menghapus emiten dari watchlist | Hapus BBCA dari watchlist | BBCA tidak lagi tampil | API | Lulus |
| 10 | UC-02 | Mengatur ambang notifikasi | Ubah ambang BBCA ke 0,5; coba 0,01 | 0,5 tersimpan; 0,01 ditolak | API | Lulus |
| 11 | UC-02 3a | Emiten di luar cakupan LQ45 | Tambah emiten yang tidak dipantau | Ditolak dengan pesan | API | Lulus |
| 12 | UC-02 | Watchlist tanpa login | Buka watchlist tanpa token | Respons 401 | API | Lulus |
| 13 | FR-6 | Notifikasi perubahan sentimen | Sentimen BBCA berbalik dari negatif ke positif | Satu notifikasi dibuat, tidak diulang | unit | Lulus |
| 14 | FR-6 | Membaca notifikasi | Buka panel notifikasi, tandai dibaca | Hanya notifikasi milik sendiri; jumlah belum dibaca jadi 0 | API | Lulus |
| 15 | FR-6 | Email notifikasi opt-in | Satu pengguna menyalakan email, satu tidak | Hanya yang menyalakan yang menerima email | unit | Lulus |
| 16 | UC-03 | Label per pasangan berita–emiten | Berita yang menyebut dua emiten | Masing-masing emiten mendapat label | unit | Lulus |
| 17 | UC-03 | Tidak melabeli dua kali | Siklus klasifikasi dijalankan ulang | Tidak ada label ganda | unit | Lulus |
| 18 | UC-04 | Berita cocok dengan pengumuman resmi | Judul berita mirip pengumuman BEI | Status Terkonfirmasi Resmi beserta jejaknya | unit | Lulus |
| 19 | UC-04 | Kabar spekulatif tanpa pengumuman | Berita 'dikabarkan akan akuisisi' | Status Rumor Belum Terkonfirmasi | unit | Lulus |
| 20 | UC-04 | Berita biasa tanpa pengumuman | Berita tanpa padanan dan tanpa bahasa spekulatif | Status tetap Belum Diperiksa | unit | Lulus |
| 21 | UC-04 | Keputusan analis dihormati | Siklus verifikasi otomatis berjalan lagi | Status yang ditetapkan analis tidak ditimpa | unit | Lulus |
| 22 | UC-05 | Antrean tinjauan | Analis membuka antrean | Label model belum ditinjau, paling ragu dulu | API | Lulus |
| 23 | UC-05 | Koreksi label | Analis mengubah label ke netral | Label analis dipakai, label model tetap tersimpan | API | Lulus |
| 24 | UC-05 4a | Berita tidak relevan | Analis menandai pemetaan salah | Kaitan dicabut tanpa label; skor emiten ikut berubah | API | Lulus |
| 25 | UC-05 | Hak akses analis | Pengguna biasa mencoba mengoreksi | Respons 403 | API | Lulus |
| 26 | UC-06 | Menambah sumber berita | URL RSS baru yang valid | Sumber tersimpan dan aktif | API | Lulus |
| 27 | UC-06 3a | Alamat tidak valid atau terdaftar | URL bukan http(s), atau domain yang sudah ada | Ditolak dengan pesan | API | Lulus |
| 28 | UC-06 | Menonaktifkan sumber | Admin mematikan satu portal | Cakupan di ringkasan berkurang | API | Lulus |
| 29 | FR-8 | Kelola akun | Admin membuat lalu menonaktifkan akun | Akun bisa masuk, lalu tidak bisa | API | Lulus |
| 30 | FR-8 | Halaman admin terlindungi | Analis membuka halaman admin | Respons 403 | API | Lulus |
| 31 | FR-1 | Pengumpulan berita | Feed RSS berisi berita baru dan duplikat | Berita baru tersimpan; duplikat dan sindikasi dikenali | unit | Lulus |
| 32 | FR-1 | Pemetaan emiten akurat | Teks menyebut 'menghantam' / kode ambigu | Tidak salah petakan ke ANTM / kode tanpa konteks pasar | unit | Lulus |
| 33 | FR-4 | Skor agregat tertimbang | Berita dari portal tak terverifikasi dan artikel rekap | Bobotnya lebih kecil daripada berita khusus terverifikasi | unit | Lulus |
| 34 | NF-03 | Keandalan saat satu sumber gagal | Satu artikel/emiten gagal diproses | Sisanya tetap diproses | unit | Lulus |
| 35 | NF-04 | Keamanan kata sandi dan token | Token dipalsukan / kedaluwarsa; sandi salah | Ditolak; pesan galat tidak membocorkan email terdaftar | API | Lulus |
| 36 | NF-09 | Etika pengumpulan | robots.txt melarang; halaman artikel diambil | Halaman tidak diambil; isi artikel tidak disimpan | unit | Lulus |

## Uji otomatis yang membuktikan tiap skenario

- **1. UC-01 Melihat deret sentimen dan harga**: `test_deret_sentimen`, `test_deret_harga`, `test_detail_emiten`
- **2. UC-01 Korelasi dihitung terhadap imbal hasil**: `test_korelasi_terhitung`
- **3. UC-01 3a Data belum mencukupi**: `test_korelasi_kurang_data_memberi_catatan`, `test_data_terlalu_sedikit_memberi_catatan_bukan_error`
- **4. UC-01 Rentang tanggal tidak valid**: `test_rentang_terbalik_ditolak`
- **5. UC-01 Emiten tidak dikenal**: `test_emiten_tidak_ada`
- **6. UC-01 Pencarian emiten**: `test_cari_emiten_berdasarkan_nama`, `test_daftar_emiten`
- **7. UC-01 Daftar berita dan saringannya**: `test_daftar_berita_dan_label`, `test_saring_berita_berdasarkan_sentimen`
- **8. UC-02 Menambah dan melihat watchlist**: `test_tambah_dan_lihat_watchlist`, `test_watchlist_terpisah_antar_pengguna`
- **9. UC-02 Menghapus emiten dari watchlist**: `test_hapus_watchlist`, `test_hapus_yang_tidak_ada`
- **10. UC-02 Mengatur ambang notifikasi**: `test_ambang_watchlist_bisa_diatur`
- **11. UC-02 3a Emiten di luar cakupan LQ45**: `test_kelola_emiten`, `test_tambah_emiten_tak_dikenal`
- **12. UC-02 Watchlist tanpa login**: `test_watchlist_butuh_token`
- **13. FR-6 Notifikasi perubahan sentimen**: `test_perubahan_tajam_memicu_satu_notifikasi`, `test_perubahan_di_bawah_ambang_diam`, `test_satu_berita_tidak_cukup_untuk_disebut_perubahan`
- **14. FR-6 Membaca notifikasi**: `test_api_notifikasi_milik_sendiri_dan_bisa_ditandai_dibaca`
- **15. FR-6 Email notifikasi opt-in**: `test_email_hanya_untuk_yang_menyalakan_dan_diam_tanpa_smtp`
- **16. UC-03 Label per pasangan berita–emiten**: `test_pipeline_membuat_label_per_emiten`, `test_model_per_emiten_memberi_label_berbeda_per_emiten`
- **17. UC-03 Tidak melabeli dua kali**: `test_tidak_melabeli_dua_kali`, `test_ulangi_tidak_menggandakan_label_versi_sama`
- **18. UC-04 Berita cocok dengan pengumuman resmi**: `test_berita_cocok_jadi_terkonfirmasi`, `test_jejak_menyimpan_pengumuman_yang_dipakai`
- **19. UC-04 Kabar spekulatif tanpa pengumuman**: `test_kabar_spekulatif_tanpa_pengumuman_jadi_rumor`
- **20. UC-04 Berita biasa tanpa pengumuman**: `test_berita_biasa_tanpa_pengumuman_dibiarkan`
- **21. UC-04 Keputusan analis dihormati**: `test_keputusan_analis_tidak_ditimpa`, `test_ubah_status_verifikasi`, `test_jejak_verifikasi_tercatat_saat_diubah_manual`
- **22. UC-05 Antrean tinjauan**: `test_antrean_berisi_label_model_yang_belum_ditinjau`
- **23. UC-05 Koreksi label**: `test_koreksi_analis_mengalahkan_label_model`, `test_statistik_menghitung_setuju_dan_koreksi`
- **24. UC-05 4a Berita tidak relevan**: `test_tidak_relevan_mencabut_kaitan_dari_antrean_berita_dan_skor`
- **25. UC-05 Hak akses analis**: `test_koreksi_oleh_pengguna_biasa_ditolak`, `test_koreksi_tanpa_token_ditolak`, `test_ruang_analis_tertutup_bagi_tamu_dan_pengguna_biasa`, `test_tidak_relevan_hanya_untuk_analis`
- **26. UC-06 Menambah sumber berita**: `test_tambah_sumber_menolak_alamat_tidak_valid_dan_duplikat`
- **27. UC-06 3a Alamat tidak valid atau terdaftar**: `test_tambah_sumber_menolak_alamat_tidak_valid_dan_duplikat`
- **28. UC-06 Menonaktifkan sumber**: `test_menonaktifkan_sumber_mengurangi_cakupan`
- **29. FR-8 Kelola akun**: `test_kelola_akun`, `test_admin_tidak_bisa_mengunci_dirinya_sendiri`
- **30. FR-8 Halaman admin terlindungi**: `test_halaman_admin_hanya_untuk_admin`, `test_admin_mencakup_hak_analis`
- **31. FR-1 Pengumpulan berita**: `test_menyimpan_berita_dan_memetakan_emiten`, `test_url_sama_tidak_disimpan_dua_kali`, `test_artikel_sindikasi_dikenali_lewat_sidik_jari`
- **32. FR-1 Pemetaan emiten akurat**: `test_nama_emiten_harus_kata_utuh`, `test_kode_ambigu_ditolak_tanpa_konteks_pasar`
- **33. FR-4 Skor agregat tertimbang**: `test_sumber_tak_terverifikasi_ditimbang_lebih_rendah`, `test_artikel_rekap_pasar_tidak_menggeser_skor_sekuat_berita_khusus`
- **34. NF-03 Keandalan saat satu sumber gagal**: `test_galat_satu_artikel_tidak_menghentikan_sisanya`, `test_emiten_gagal_tidak_menghentikan_yang_lain`
- **35. NF-04 Keamanan kata sandi dan token**: `test_token_palsu_ditolak`, `test_masuk_sandi_salah`, `test_pesan_galat_sama_untuk_email_tak_terdaftar`, `test_token_kedaluwarsa_ditolak`, `test_hash_tidak_memuat_kata_sandi`
- **36. NF-09 Etika pengumpulan**: `test_robots_menolak_tidak_mengambil_halaman`, `test_isi_artikel_tidak_disimpan`
