# Sistem Analisis Sentimen Berita Emiten

Implementasi dari SRS Proyek 1 — Analisa dan Desain Perangkat Lunak,
D4 Teknik Informatika, Fakultas Vokasi Universitas Airlangga.

**Tahap saat ini: pipeline data + analitik + API & dasbor.** Pengumpulan berita,
pemetaan ke emiten, pelabelan sentimen (baseline leksikon), penyimpanan harga,
agregasi skor harian, korelasi dengan pergerakan harga,
verifikasi berita ke pengumuman resmi BEI, autentikasi, watchlist, REST API, dan
dasbor web sudah berjalan. Yang tersisa: model IndoBERT hasil fine-tuning.

---

## Kenapa dibangun bertahap

Model IndoBERT yang menjadi inti sistem baru akan dilatih pada tahap skripsi.
Karena itu modul klasifikasi dirancang sebagai antarmuka yang bisa ditukar
(`app/klasifikasi/basis.py`): sekarang diisi baseline leksikon, nanti diganti
IndoBERT hasil fine-tuning tanpa mengubah pipeline, API, maupun basis data.
Cukup buat kelas turunan `Pengklasifikasi` dengan `versi` berbeda — label lama
tidak ditimpa, sehingga hasil dua versi bisa dibandingkan langsung.

Semua pekerjaan di sekeliling model — pengumpulan, pembersihan, pemetaan
emiten, verifikasi, agregasi — tidak bergantung pada model dan bisa diselesaikan
lebih dulu.

## Menjalankan

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # lalu sesuaikan isinya

python -m scripts.init_db       # buat tabel + isi 45 emiten & 7 sumber
python -m scripts.cek_sumber    # periksa RSS mana yang masih hidup
python -m scripts.collect       # jalankan satu siklus pengumpulan
python -m scripts.petakan_ulang --semua   # cari emiten di badan artikel
python -m scripts.klasifikasi   # labeli berita yang belum diklasifikasi
python -m scripts.siklus_harian # ketiganya sekaligus, untuk penjadwal
python -m scripts.diagnosa_pemetaan   # kenapa sisa berita tidak terpetakan
python -m scripts.periksa_pemetaan --acak   # periksa presisi pemetaan manual
python -m scripts.bersihkan_pemetaan --lihat  # buang pemetaan lama bila aturan berubah
python -m scripts.verifikasi --csv data/keterbukaan/contoh.csv
python -m scripts.buat_pengguna anda@contoh.id "Nama Anda" --peran analis
pytest -q                       # 205 uji
```

Menjalankan API dan dasbor:

```bash
python -m scripts.jalankan_api  # atau: uvicorn app.main:app --reload
```

Lalu buka <http://127.0.0.1:8000> untuk dasbor dan
<http://127.0.0.1:8000/docs> untuk dokumentasi API yang dibuat otomatis.

Untuk analitik harga:

```bash
# unduh harga ke berkas CSV (butuh: pip install yfinance)
python -m scripts.unduh_harga 2026-01-01 2026-09-30

# lalu impor berkas itu ke basis data
python -m scripts.impor_harga data/harga 2026-01-01 2026-09-30
python -m scripts.laporan_korelasi BBCA 2026-01-01 2026-09-30
python -m scripts.laporan_korelasi BBCA 2026-01-01 2026-09-30 1   # lag 1 hari
```

Berkas CSV boleh berkolom bahasa Indonesia (`tanggal, pembukaan, penutupan, …`)
maupun Inggris (`date, open, close, …`) — keduanya dikenali. Berkas hasil unduhan
manual dari situs mana pun bisa dipakai langsung asal kolomnya salah satu dari
dua bentuk itu.

Pengunduhan dan pengimporan sengaja dipisah. Sumber daring bisa berubah,
mengoreksi angka lama, atau hilang; kalau penelitian bergantung pada pemanggilan
langsung, angka yang dilaporkan hari ini belum tentu bisa dihasilkan ulang bulan
depan. Berkas CSV yang tersimpan adalah data penelitiannya — lampirkan bersama
laporan.

`scripts.cek_sumber` sebaiknya dijalankan lebih dulu — URL RSS portal berita
sering berubah, dan lebih baik ketahuan di situ daripada saat pengumpulan penuh.
Kalau ada sumber yang mati, `python -m scripts.cek_kandidat` menguji sederet
kandidat pengganti tanpa menyentuh basis data.

## Kenapa perlu `petakan_ulang`

Ringkasan RSS panjangnya cuma sekitar dua kalimat, dan judul berita finansial
sering tidak menyebut emiten mana pun — "Daftar Lengkap 8 Blok Migas Dilelang"
tidak memuat satu pun kode atau nama emiten, padahal isinya membahas beberapa.
Dari satu siklus uji, hanya 6 dari 105 berita terpetakan dari judul dan
ringkasan saja.

`scripts.petakan_ulang` mengambil halaman artikel untuk berita yang belum punya
emiten, mencocokkan nama dan kode di badan teksnya, lalu **membuang halamannya**.
Yang tersimpan hanya kutipan pendek di sekitar kecocokan — potongan yang
dibutuhkan analis untuk memeriksa pemetaannya benar (NF-09 tetap dipatuhi).
robots.txt dan crawl-delay portal tetap dihormati, dan jumlah halaman per siklus
dibatasi supaya satu portal tidak dihujani permintaan.

Langkahnya dipisah dari `collect` supaya siklus pengumpulan tetap cepat dan
pengambilan halaman — yang lebih berat — bisa dijadwalkan sendiri.

Setiap artikel yang halamannya berhasil diambil dicatat di tabel
`pengayaan_berita`, termasuk yang hasilnya nihil. Hasil nihil pun sebuah
jawaban: mengulangnya tiap siklus hanya membebani portal dan membuat siklus
tidak pernah selesai. Artikel yang **gagal** diambil tetap dicoba lagi, karena
kegagalan jaringan bisa bersifat sesaat. Setelah daftar emiten diperluas,
`--ulangi` memaksa pengambilan ulang — artikel yang tadinya nihil bisa jadi
cocok dengan emiten yang baru ditambahkan.

## Struktur

```
app/
  config.py            konfigurasi dari .env
  database.py          koneksi dan sesi SQLAlchemy
  models.py            skema basis data (entitas SRS)
  ingest/
    robots.py          kepatuhan robots.txt (NF-09)
    rss.py             pengambilan & parsing RSS/Atom
    cleaner.py         pembersihan teks (SRS 10.1 butir 3)
    matcher.py         pemetaan berita ke emiten (SRS 10.1 butir 2)
    pipeline.py        siklus pengumpulan
    pengaya.py         pengayaan pemetaan dari badan artikel
    diagnosa.py        memisahkan gagal-cocok dari di-luar-cakupan
  harga/
    provider.py        sumber harga: CSV dan yfinance
  analitik/
    agregasi.py        skor sentimen harian (SRS 10.1 butir 6)
    statistik.py       Pearson & Spearman, ditulis sendiri
    korelasi.py        penyandingan sentimen dengan harga (butir 7)
  klasifikasi/
    basis.py           antarmuka Pengklasifikasi — titik tukar model
    leksikon.py        baseline leksikon finansial Indonesia
    jalankan.py        pelabelan berita per pasangan berita-emiten
  auth/
    keamanan.py        hash kata sandi (PBKDF2) dan token sesi ber-HMAC
    dependensi.py      dependency autentikasi dan pembatasan peran
  verifikasi/
    sumber.py          pengumuman BEI: berkas CSV dan endpoint IDX
    pencocok.py        pencocokan judul berita dengan pengumuman
    jalankan.py        siklus verifikasi + pencatatan alasannya
  api/
    bantu.py           normalisasi rentang tanggal & pencarian emiten
    emiten.py          daftar, detail, deret sentimen/harga, korelasi
    peringkat.py       ikhtisar seluruh emiten (SRS UC-01)
    berita.py          daftar berita, koreksi analis, status & jejak verifikasi
    sistem.py          ringkasan dasbor, daftar sumber, /api/sehat
    auth.py            masuk dan identitas pengguna
    watchlist.py       watchlist per pengguna (SRS UC-02)
  static/              dasbor web (HTML + CSS + JS, tanpa pustaka luar)
  schemas.py           skema respons API
  main.py              aplikasi FastAPI
data/lq45.py           daftar emiten & portal berita
scripts/               perintah baris perintah
siklus.bat             pembungkus untuk Task Scheduler Windows
tests/                 205 uji, semuanya tanpa jaringan
```

## Endpoint

| Metode | Jalur | Kegunaan |
| --- | --- | --- |
| GET | `/api/ringkasan` | angka ringkas untuk halaman depan dasbor |
| GET | `/api/peringkat` | ikhtisar seluruh emiten dalam satu tabel |
| GET | `/api/rentang-data` | tanggal paling awal & akhir yang ada datanya |
| GET | `/api/emiten` | daftar emiten, bisa dicari (`?q=`) |
| GET | `/api/emiten/{kode}` | detail emiten + harga terakhir |
| GET | `/api/emiten/{kode}/sentimen` | deret skor sentimen harian |
| GET | `/api/emiten/{kode}/harga` | deret harga penutupan |
| GET | `/api/emiten/{kode}/korelasi` | Pearson & Spearman, `?lag=`, `?maks_emiten_per_berita=` |
| GET | `/api/berita` | daftar berita, saring per emiten/sentimen/status |
| POST | `/api/berita/{id}/koreksi` | koreksi label oleh analis (UC-05) |
| POST | `/api/berita/{id}/verifikasi` | tandai terkonfirmasi resmi / rumor (UC-04) |
| GET | `/api/emiten/{kode}/keterbukaan` | pengumuman resmi BEI yang tersimpan |
| GET | `/api/berita/{id}/jejak` | dasar pemberian status verifikasi |
| GET | `/api/sumber` | daftar portal beserta kredibilitasnya |
| POST | `/api/auth/masuk` | tukar email + kata sandi dengan token sesi |
| GET | `/api/auth/saya` | identitas dan peran pemilik token |
| GET | `/api/watchlist` | watchlist pengguna yang sedang masuk |
| POST | `/api/watchlist` | tambah emiten ke watchlist |
| DELETE | `/api/watchlist/{kode}` | hapus emiten dari watchlist |

Endpoint `POST /api/berita/{id}/koreksi` dan `/verifikasi` menuntut peran
**analis**; sisanya bisa dibaca tanpa masuk.

## Akun dan peran

```bash
python -m scripts.buat_pengguna anda@contoh.id "Nama Anda" --peran analis
python -m scripts.buat_pengguna rekan@contoh.id "Rekan" --peran pengguna
```

Kata sandi ditanyakan lewat prompt tersembunyi, bukan lewat argumen — argumen
baris perintah tersimpan di riwayat shell dan terlihat di daftar proses.

| Peran | Bisa |
| --- | --- |
| `pengguna` | melihat semua data, mengelola watchlist sendiri |
| `analis` | semua di atas, ditambah koreksi label dan status verifikasi |

Sebelum dipakai di luar mesin sendiri, isi `SECRET_KEY` di `.env` dengan nilai
acak:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Verifikasi berita (UC-04)

```bash
# sumber utama untuk penelitian: berkas hasil unduhan manual dari situs BEI
python -m scripts.verifikasi --csv data/keterbukaan/idx.csv --kode BBCA --hari 90

# sumber operasional: ambil langsung dari situs BEI
python -m scripts.verifikasi --idx --hari 30
```

Format CSV-nya sama longgarnya dengan berkas harga — kolom
`kode, judul, url, tanggal` maupun `code, title, link, date` sama-sama dikenali.
Contohnya ada di `data/keterbukaan/contoh.csv`.

## Keputusan desain

**Label sentimen disimpan terpisah dari berita.** Satu berita bisa punya
beberapa label: dari model, dari koreksi analis, atau dari versi model berbeda.
Tanpa pemisahan ini, koreksi analis (UC-05) akan menimpa hasil model dan
riwayatnya hilang — padahal justru koreksi itu yang menjadi data tambahan untuk
pelatihan ulang.

**Satu berita bisa terkait beberapa emiten**, lewat tabel `berita_emiten` yang
juga menyimpan cara pencocokan dan kutipan teksnya. Kutipan ini yang dipakai
analis untuk memeriksa apakah pemetaannya benar.

**Kode emiten yang juga kata umum diperlakukan khusus.** Kode seperti `INCO`,
`ACES`, atau `TIME` akan salah tangkap pada kalimat berbahasa Inggris. Kode
semacam itu hanya diterima bila teksnya memuat petunjuk pasar modal — kata
seperti saham, emiten, bursa, IHSG, atau dividen.

**Artikel yang disindikasi ulang dikenali lewat sidik jari isi**, bukan hanya
URL. Portal berbeda sering memuat artikel yang sama dengan tautan berbeda;
tanpa ini skor sentimen agregat akan terhitung berulang.

**Isi artikel tidak disimpan utuh.** Hanya judul, ringkasan dari RSS, dan
tautan aslinya — sesuai NF-09. Pada pengayaan pemetaan, halaman artikel memang
diambil, tapi dipakai untuk mencocokkan emiten lalu dibuang; yang tersimpan cuma
kutipan pendek di sekitar kecocokan.

**Pemetaan dari judul saja tidak cukup, dan itu diukur bukan diduga.** Satu
siklus nyata memetakan 6 dari 105 berita. Angka itulah yang membuat langkah
pengayaan dari badan artikel ada — bukan karena kelihatannya bagus.

**Pengayaan dicatat, bukan diulang.** Lihat bagian `petakan_ulang` di atas.

**Rasio pemetaan yang rendah tidak otomatis berarti sistemnya cacat.** Setelah
pengayaan dijalankan, sebagian besar berita yang tetap tanpa emiten ternyata
membahas emiten di luar LQ45 — BKSL, ASPI, INPS, HOKI, SKBM, DOID dan
seterusnya. Itu konsekuensi batasan cakupan (SRS 10.3), bukan kegagalan
pencocokan. `scripts.diagnosa_pemetaan` memisahkan dua sebab itu dan
melaporkan secara khusus berita yang menyebut emiten **dipantau** tapi gagal
dipetakan — hanya kelompok terakhir itu yang perlu diperbaiki.

Kalau diagnosa menampilkan kode besar seperti BYAN atau HRUM berulang kali,
yang perlu diperbarui bukan pencocokannya melainkan daftar LQ45 di
`data/lq45.py` — komposisinya dievaluasi ulang BEI tiap Februari dan Agustus.

**Blok "berita terkait" dan "baca juga" dibuang sebelum pencocokan.** Pada uji
nyata, sebuah berita serangan udara di Iran terpetakan ke ANTM dan sebuah berita
kurs rupiah terpetakan ke EXCL — bukan karena artikelnya membahas emiten itu,
melainkan karena judul artikel lain menempel di halaman yang sama. Penyaringnya
berlapis tiga: buang tag non-artikel, buang elemen yang kelas atau id-nya
menandakan rekomendasi, lalu buang paragraf yang terlalu pendek, diawali "baca
juga", atau isinya didominasi tautan.

Kalau seluruh paragraf tersaring, hasilnya kosong — bukan jatuh ke seluruh teks
halaman. Jatuh ke sana justru mengembalikan persis bagian yang baru saja sengaja
dibuang.

**Pencocokan nama menuntut batas kata.** Tanpa itu "menghantam" memuat "antam",
dan sebuah berita serangan udara terpetakan ke Aneka Tambang. Ini bukan contoh
yang dikarang — ia muncul pada pemeriksaan sampel pertama.

**`init_db` menyelaraskan, bukan sekadar mengisi.** Versi pertamanya melewati
baris emiten yang sudah ada, jadi perbaikan alias di `data/lq45.py` tidak pernah
sampai ke basis data: pencocokan diam-diam tetap memakai alias lama sementara
berkas sumbernya terlihat sudah benar. Cacat seperti ini sangat sulit disadari
karena tidak menimbulkan galat apa pun — yang menemukannya adalah pemeriksaan
sampel, bukan uji otomatis. Sekarang nama, sektor, dan alias ikut diperbarui,
dan setiap perubahan alias dicetak beserta pengingat bahwa pemetaan lama dibuat
memakai alias lama.

**Alias harus menunjuk satu perusahaan, bukan satu grup.** "Astra" cocok dengan
Astra International maupun Astra Otoparts; "Indofood" cocok dengan INDF maupun
ICBP. Ada uji yang menolak alias semacam itu, supaya daftar emiten tidak
diam-diam rusak saat disunting kemudian.

**Presisi lebih penting daripada jangkauan pada tahap pemetaan.** Berita yang
terlewat hanya membuat data lebih sedikit; berita yang salah petakan
menyuntikkan sentimen keliru ke skor sebuah emiten, dan setelah teragregasi
kesalahan itu tidak terlihat lagi. `scripts.periksa_pemetaan --acak` menampilkan
sampel acak pemetaan beserta kutipan buktinya untuk diperiksa dengan mata
sendiri — hasilnya adalah angka presisi yang pantas masuk laporan, bukan klaim
"pemetaan bekerja dengan baik".

**Artikel rekap pasar tidak diberi bobot penuh untuk tiap emitennya.** Artikel
seperti "ANALIS MARKET: IHSG Masih Cenderung Bearish" menyebut lima emiten
sekaligus, dan nadanya tentang pasar secara keseluruhan — bukan tentang BBCA
atau TLKM masing-masing. Bobotnya dibagi rata (1/n) antar emiten yang dibahas.
Tanpa aturan ini, satu artikel makro yang terbit tiap hari bursa akan menggeser
skor lima emiten sekaligus dengan bobot penuh, dan korelasi yang dihitung dari
skor itu jadi mencerminkan pergerakan indeks, bukan sentimen per emiten.

**Skor harian ditimbang, bukan dirata-rata biasa.** Tiga hal memengaruhi bobot
sebuah berita: keyakinan model, kredibilitas portal sumbernya, dan apakah
labelnya sudah dikoreksi analis. Koreksi analis selalu menang atas label model.
Tanpa pembobotan ini, satu rumor dari portal tak terverifikasi akan menggeser
skor sekuat berita dari portal terverifikasi — padahal justru membedakan
keduanya yang menjadi tujuan sistem.

**Korelasi dihitung terhadap imbal hasil harian, bukan harga mentah.** Harga
saham punya tren; mengorelasikan sentimen dengan harga mentah akan menghasilkan
angka tinggi yang menyesatkan hanya karena keduanya sama-sama naik sepanjang
periode.

**Pearson dan Spearman disajikan berdampingan.** Pearson peka terhadap satu hari
yang melonjak; Spearman tidak. Selisih besar di antara keduanya adalah tanda
bahwa hasilnya digerakkan oleh sedikit hari ekstrem, bukan pola yang konsisten.

**Rumus statistik ditulis sendiri, tidak memakai SciPy.** Bukan karena menghindari
pustaka, tapi supaya cara perhitungan — termasuk penanganan nilai kembar pada
Spearman — terbuka dan bisa dipertanggungjawabkan saat sidang.

**Hari bursa libur dilewati, bukan diisi nol.** Nol akan terbaca sebagai harga
jatuh ke titik tersebut.

**Kegagalan satu sumber tidak menghentikan sumber lain** (NF-03). Tiap siklus
per sumber dicatat di tabel `log_pengumpulan` beserta pesan kesalahannya.

**Bila robots.txt tidak bisa diambil, akses ditolak.** Lebih baik melewatkan
satu sumber daripada mengambil yang tidak diizinkan.

**Baseline leksikon ada bukan sebagai model akhir, tapi sebagai pembanding.**
Sebuah transformer baru layak dipakai kalau akurasinya mengalahkan hitungan kata
sesederhana ini. Kalau tidak, yang salah ada pada pelatihannya, bukan pada
datanya. Baseline ini juga membuat seluruh alur bisa diuji sekarang tanpa
menunggu model siap.

**Label dibuat per pasangan berita-emiten, bukan per berita.** Satu artikel bisa
menyebut dua emiten dengan nada berbeda — "A menguat setelah mengambil pangsa
B". Label yang benar adalah label untuk emiten tertentu, jadi pemisahan ini
disiapkan sejak sekarang meski baseline masih menilai teks yang sama.

**Koreksi analis disimpan sebagai label baru, bukan menimpa label model.**
Selisih antara keduanya justru yang menjadi data pelatihan ulang dan bahan
pengukuran akurasi model.

**Dasbor menggambar grafiknya sendiri dengan SVG, tanpa pustaka luar.** Supaya
demo saat sidang tetap jalan tanpa internet dan tidak ada dependensi front-end
yang perlu dijelaskan.

**Dasbor dibuka dengan ikhtisar seluruh emiten, bukan satu emiten.** Halaman
per emiten menjawab "bagaimana emiten ini?"; yang tidak dijawabnya adalah
"emiten mana yang perlu dilihat hari ini?" — dan justru itu pertanyaan yang
muncul lebih dulu ketika ada 45 emiten dipantau.

**Skor pada ikhtisar adalah rata-rata tertimbang rentang, bukan skor hari
terakhir.** Hari terakhir mudah menyesatkan: emiten yang kebetulan tidak
diberitakan hari itu akan tampak netral, padahal sepekan sebelumnya diberitakan
negatif terus-menerus.

**Rentang "seluruh data" dihitung dari isi basis data, bukan ditebak.** Data
harga bisa mundur sembilan bulan sementara data sentimen baru mulai terkumpul.
Dasbor menampilkan kedua rentang itu terpisah supaya ketimpangannya terlihat —
grafik yang garis harganya panjang dan garis sentimennya pendek bukan grafik
yang rusak, itu keadaan datanya.

**Batas rentang permintaan ada untuk menjaga beban, bukan membatasi
penelitian.** Karena itu batasnya longgar (lima tahun): cukup untuk menolak
permintaan yang jelas keliru, tapi tidak pernah menolak "seluruh data".

**Ringkasan hanya menghitung emiten dan sumber yang aktif.** Memasukkan yang
sudah dinonaktifkan akan melaporkan cakupan lebih besar daripada yang
sebenarnya berjalan — angka yang salah ke arah yang menyenangkan.

**Peringatan "bukan prediksi harga" dikirim oleh API, bukan ditulis di UI.**
Dengan begitu peringatan itu ikut ke mana pun datanya dipakai, bukan hanya di
dasbor ini.

**Verifikasi hanya bisa menaikkan keyakinan, tidak pernah membuktikan kabar
salah.** Tidak adanya pengumuman resmi bisa berarti kabarnya memang belum
diumumkan. Karena itu sistem hanya memberi status TERKONFIRMASI_RESMI bila ada
pengumuman yang cocok, memberi status rumor hanya bila beritanya sendiri memakai
bahasa spekulatif ("dikabarkan", "santer", "isu"), dan selain itu membiarkan
statusnya BELUM_DIPERIKSA. Memaksa setiap berita tanpa pengumuman menjadi
"rumor" akan membuat sistem sering salah menuduh.

**Keputusan analis tidak pernah ditimpa proses otomatis.** Berita yang statusnya
sudah ditetapkan manusia dilewati, kecuali dijalankan dengan `--paksa`.

**Setiap keputusan verifikasi menyimpan alasannya** di tabel
`verifikasi_berita`: pengumuman mana yang dipakai, seberapa mirip judulnya, dan
kata apa yang beririsan. Tanpa jejak ini analis tidak punya cara memeriksa
apakah sistemnya keliru — dan status "terkonfirmasi" tanpa dasar yang bisa
ditelusuri tidak ada gunanya.

**Pencocokan judul memakai Jaccard atas kata bermakna, bukan kecocokan persis.**
Judul berita hampir tidak pernah sama dengan judul pengumuman BEI yang penuh
kalimat baku; yang bisa diandalkan cuma irisan kata pentingnya. Satu kata sama
dianggap belum cukup, karena terlalu mudah terjadi secara kebetulan.

**Kata sandi disimpan sebagai turunan PBKDF2-HMAC-SHA256, bukan hash biasa.**
Garamnya acak per akun dan iterasinya 240.000. SHA-256 sekali jalan terlalu cepat
— justru kecepatan itu yang dipakai penyerang untuk mencoba daftar kata. Argon2id
sebenarnya lebih baik dan menjadi jalur peningkatan berikutnya; nama algoritme
sudah disimpan di depan string hash, jadi penggantian bisa bertahap tanpa memaksa
semua orang mengatur ulang kata sandinya.

**Peran diambil dari basis data, bukan dari isi token.** Kalau peran dibaca dari
token, mencabut hak seseorang baru berlaku setelah token lamanya kedaluwarsa.

**Pesan galat saat masuk sengaja sama** untuk email tidak terdaftar maupun kata
sandi salah, supaya tidak bisa dipakai menebak alamat mana yang punya akun.

**Token disimpan di memori halaman, bukan di localStorage.** Sesi berakhir saat
tab ditutup. Untuk sistem sekecil ini, kerugiannya cuma harus masuk ulang;
keuntungannya token tidak tertinggal di penyimpanan peramban.

**Harga diambil sekali lalu disimpan sebagai CSV, bukan dipanggil setiap
analisis.** Alasannya sama dengan alasan memilih berkas untuk keterbukaan
informasi: hasil penelitian harus bisa dihasilkan ulang orang lain, dan itu
hanya mungkin kalau datanya ikut tersimpan.

**Sumber CSV lebih diutamakan daripada endpoint BEI untuk penelitian.** Endpoint
situs BEI tidak dijanjikan stabil dan bisa berubah sewaktu-waktu; berkas unduhan
bisa dilampirkan ke laporan sehingga hasilnya bisa diulang orang lain persis
sama.


## Yang belum dikerjakan

- IndoBERT hasil fine-tuning — baseline leksikon masih dipakai sementara
- Notifikasi ke pengguna saat sentimen emiten watchlist bergerak tajam
- Verifikasi daftar LQ45 terhadap pengumuman resmi BEI terbaru
- Penjadwalan otomatis (saat ini tiap siklus dijalankan manual)

## Batasan yang disengaja

Sistem menyajikan hubungan korelatif dan tidak melakukan prediksi harga
(SRS 10.3). Modul analitik sengaja tidak menyediakan fungsi apa pun yang
mengeluarkan ramalan harga, dan setiap keluaran laporan disertai keterangan
bahwa angkanya bukan rekomendasi membeli atau menjual efek.

## Presisi pemetaan yang terukur

Pemeriksaan sampel acak beserta kutipan buktinya, sebelum dan sesudah perbaikan
penyaring dan pencocok:

| Tahap | Sampel | Benar | Presisi |
| --- | --- | --- | --- |
| Sebelum perbaikan | 27 | 21 | 77,8% |
| Sesudah perbaikan alias di basis data | 30 | 29 | 96,7% |
| Sesudah `init_db` menyelaraskan alias | 30 | 30 | 100% |
| Sesudah daftar LQ45 diperbaiki (45 emiten benar) | 30 | 30 | 100% |

Perbaikan daftar LQ45 menaikkan **jangkauan**, bukan presisi: pemetaan naik dari
39 ke 64 dan berita terpetakan dari 7 ke 13, sementara presisinya bertahan.
Kenaikan itu datang dari emiten yang sebelumnya tidak ada di daftar tapi sering
disebut — AMMN muncul di lima artikel pada satu sampel saja, BUMI di tiga.

Empat cacat yang ditemukan pemeriksaan itu: sisipan "Baca Juga:" di tengah
paragraf, pencocokan nama tanpa batas kata ("menghantam" memuat "antam"), dan
alias yang menunjuk grup ("Astra" juga cocok dengan Astra Otoparts), dan
`init_db` yang tidak pernah memperbarui alias emiten yang sudah tersimpan —
sehingga perbaikan ketiga tidak berlaku sampai cacat keempat ini ikut
diperbaiki. Keempatnya kini punya uji regresi sendiri.

Angka sesudah perbaikan diukur pada kumpulan berita yang sama dengan yang
dipakai menemukan cacatnya, jadi ia menggambarkan perbaikan — bukan presisi
akhir yang bebas bias. Pengukuran untuk laporan sebaiknya memakai berita yang
dikumpulkan setelah perbaikan.

## Menjalankan otomatis tiap hari

```bat
REM sekali, dari PowerShell yang dijalankan sebagai Administrator:
schtasks /create /tn "Sentimen Emiten" /tr "C:\Users\<nama>\projects\sentimen-emiten\siklus.bat" /sc daily /st 18:30 /f
```

Ganti `<nama>` dengan nama pengguna Windows yang sebenarnya. Pukul 18:30
dipilih karena bursa sudah tutup dan rekap harian portal sudah terbit.

Untuk mengumpulkan lebih rapat — RSS hanya menyimpan puluhan artikel terakhir,
sehingga portal yang ramai bisa menggeser berita pagi sebelum sore tiba:

```bat
schtasks /create /tn "Sentimen Emiten" /tr "...\siklus.bat" /sc hourly /mo 4 /f
```

Memeriksa dan menghapus:

```bat
schtasks /query /tn "Sentimen Emiten"
schtasks /run   /tn "Sentimen Emiten"     REM jalankan sekarang untuk menguji
schtasks /delete /tn "Sentimen Emiten" /f
```

`siklus.bat` menetapkan direktori kerja dan mengaktifkan virtualenv sendiri.
Task Scheduler tidak mewarisi keduanya dari sesi PowerShell, dan tanpa itu
tugas terjadwal gagal dengan `No module named app` — kegagalan yang tidak
terlihat sampai berhari-hari kemudian ketika datanya ternyata kosong. Karena
itu **jalankan `schtasks /run` sekali setelah membuat tugasnya**, lalu periksa
`data/log/siklus.log`.

Siklusnya aman dijalankan berkali-kali sehari: berita yang sudah ada dikenali
sebagai duplikat, dan artikel yang sudah diperkaya tidak diambil ulang.

### Kenapa penjadwalan ini bukan soal kenyamanan

RSS hanya menyimpan puluhan artikel terakhir. Berita hari ini yang tidak
terkumpul hari ini **hilang selamanya** — tidak ada arsip yang bisa diambil
mundur. Deret waktu sentimen hanya bisa tumbuh ke depan, satu hari per hari,
sementara data harga bisa diunduh sembilan bulan ke belakang dalam satu menit.

Ketimpangan itu yang menentukan jadwal penelitian: kalau butuh 30 hari bursa
untuk analisis, itu berarti sekitar enam minggu kalender sejak pengumpulan
dimulai. Setiap hari yang terlewat adalah lubang permanen.

## Temuan yang harus masuk laporan: dominasi artikel rekap

Dari pemeriksaan 30 sampel pemetaan, sekitar **70% berasal dari artikel rekap
pasar** — "ANALIS MARKET", "Saham Bank Jadi Pemberat", "IHSG Turun 0,33%",
"Asing Jual Saham Tambang". Artikel semacam itu menyebut banyak emiten sekaligus
dan nadanya tentang indeks, bukan tentang satu perusahaan.

Ini bukan cacat pemetaan — pemetaannya benar, emitennya memang disebut. Ini
sifat pasokan beritanya: portal Indonesia jauh lebih banyak menerbitkan rekap
harian daripada berita khusus per emiten LQ45.

Akibatnya harus diuji, bukan diasumsikan:

```bash
python -m scripts.uji_kepekaan BBCA 2026-01-01 2026-09-30
```

Perintah itu menghitung korelasi berulang dengan batas jumlah emiten per berita
yang berbeda — dari hanya berita satu-emiten sampai seluruh berita — lalu
menampilkannya berdampingan. Korelasi yang bertahan di semua batas adalah
temuan yang kuat. Korelasi yang runtuh begitu rekap dibuang juga temuan: bahwa
yang terukur adalah pergerakan IHSG, bukan sentimen per emiten.

Laporkan seluruh barisnya. Memilih satu batas karena angkanya paling enak
dilihat adalah bentuk *p-hacking*, dan itu hal pertama yang akan dicari penguji
yang teliti.

## Catatan data

**Sumber berita dipilih dengan satu syarat: isinya membahas emiten.** Dari 18
kandidat yang diuji, 11 hidup, tapi hanya 7 yang dipakai. Okezone Economy
mengirim berita sepak bola, Antara dan Liputan6 mengirim ekonomi makro, Tempo
mengirim berita gangguan kereta. Menambahkannya bukan langkah netral: berita
yang tidak pernah menyebut emiten akan mengisi basis data tanpa pernah terpakai
dan memperburuk rasio pemetaan yang dilaporkan.

Dua sumber dinonaktifkan, barisnya tetap disimpan di `SUMBER_NONAKTIF` beserta
alasannya: `market.bisnis.com` menolak dengan HTTP 403, `emitennews.com`
mengembalikan HTTP 500. Keduanya **tidak** diakali dengan memalsukan User-Agent
supaya terlihat seperti peramban — portal yang menolak klien otomatis sedang
menyatakan keberatan, dan menembusnya membuat cara pengumpulan data penelitian
ini tidak bisa dipertanggungjawabkan.

**Komposisi LQ45 yang dipakai: periode efektif 3 Agustus - 30 Oktober 2026**
(INDY dan NCKL masuk; SMGR dan TOWR keluar). Diverifikasi terhadap dua sumber
pemberitaan yang keduanya memuat daftar lengkap dan sama persis. Sebelum dipakai
untuk penelitian akhir, cocokkan sekali lagi dengan pengumuman resmi BEI dan
cantumkan tanggal periodenya di laporan — hasil penelitian hanya bisa dibaca
kalau pembaca tahu komposisi mana yang dipakai.

Daftar versi pertama meleset pada **16 dari 45 kode**. Kesalahan seperti itu
tidak menimbulkan gejala apa pun: emiten yang tidak ada di daftar tidak pernah
dicocokkan, jadi beritanya hanya tampak "di luar cakupan" — persis seperti
emiten yang memang bukan LQ45. Yang membongkarnya adalah `diagnosa_pemetaan`,
yang menampilkan kode luar cakupan paling sering muncul: BYAN dan ULTJ memang
benar di luar LQ45, tapi daftar itu juga memunculkan AMMN dan BUMI yang
seharusnya ikut dipantau.

Emiten yang keluar dari komposisi **dinonaktifkan, bukan dihapus**. Berita dan
harganya tetap tersimpan sebagai catatan periode sebelumnya — data itu tidak
bisa diambil ulang — tapi tidak lagi ikut dicocokkan pada siklus berikutnya.

Pemetaan lama ke emiten itu juga tetap ada, dan itu memang benar: beritanya
sungguh menyebut emiten tersebut, dan pemetaannya dibuat ketika emiten itu masih
dipantau. Yang berubah hanya cakupannya. Karena itu `periksa_pemetaan` tidak
menampilkannya secara bawaan — kalau ikut terhitung saat mengukur presisi, ia
akan terbaca sebagai kesalahan padahal bukan.

Daftar emiten pada `data/lq45.py` adalah titik awal. Komposisi LQ45 dievaluasi
ulang BEI tiap Februari dan Agustus — perbarui dari pengumuman resmi dan catat
tanggal evaluasi yang dipakai sebelum daftar ini dipakai untuk penelitian.
