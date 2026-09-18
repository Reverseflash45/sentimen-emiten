"""Daftar emiten yang dipantau.

KOMPOSISI YANG DIPAKAI: periode efektif **3 Agustus 2026 - 30 Oktober 2026**.
Pada evaluasi itu INDY dan NCKL masuk; SMGR dan TOWR keluar.

PENTING: komposisi LQ45 dievaluasi ulang BEI tiap enam bulan (Februari dan
Agustus), dengan penyesuaian tiga bulanan. Sebelum periode berikutnya dimulai,
perbarui daftar ini dari pengumuman resmi BEI dan CATAT tanggal periodenya di
laporan — hasil penelitian hanya bisa dibaca kalau pembaca tahu komposisi mana
yang dipakai.

Daftar sebelumnya meleset pada 16 dari 45 kode. Itu bukan kesalahan kecil:
emiten yang tidak dipantau beritanya tidak pernah masuk analisis sama sekali,
dan tidak ada gejala apa pun yang menandakannya.

Format: (kode, nama, sektor, alias dipisah "|")

Alias diisi nama pendek yang biasa dipakai media, dengan satu syarat: alias
harus menunjuk SATU perusahaan, bukan satu grup. "Astra" pernah dipakai sebagai
alias ASII dan membuat berita tentang Astra Otoparts terpetakan ke Astra
International — dua emiten berbeda. Hal yang sama berlaku untuk "Indofood",
yang juga merupakan bagian nama Indofood CBP (ICBP).

Alias yang panjangnya kurang dari empat huruf tidak pernah dicocokkan sebagai
nama (lihat matcher), jadi "BCA" dan "BRI" di bawah hanya berfungsi sebagai
catatan, bukan pola pencocokan.
"""

EMITEN_AWAL: list[tuple[str, str, str, str]] = [
    # --- Keuangan ---
    ("BBCA", "Bank Central Asia Tbk", "Keuangan", "BCA|Bank BCA"),
    ("BBRI", "Bank Rakyat Indonesia (Persero) Tbk", "Keuangan", "BRI|Bank BRI"),
    ("BMRI", "Bank Mandiri (Persero) Tbk", "Keuangan", "Bank Mandiri"),
    ("BBNI", "Bank Negara Indonesia (Persero) Tbk", "Keuangan", "BNI|Bank BNI"),
    ("BBTN", "Bank Tabungan Negara (Persero) Tbk", "Keuangan", "BTN|Bank BTN"),

    # --- Infrastruktur & Telekomunikasi ---
    ("TLKM", "Telkom Indonesia (Persero) Tbk", "Infrastruktur", "Telkom Indonesia"),
    ("ISAT", "Indosat Tbk", "Infrastruktur", "Indosat|Indosat Ooredoo Hutchison"),
    ("EXCL", "XLSmart Telecom Sejahtera Tbk", "Infrastruktur", "XLSmart|XL Axiata"),

    # --- Energi ---
    ("ADRO", "Alamtri Resources Indonesia Tbk", "Energi", "Alamtri"),
    ("AADI", "Adaro Andalan Indonesia Tbk", "Energi", "Adaro Andalan"),
    ("ADMR", "Adaro Minerals Indonesia Tbk", "Energi", "Adaro Minerals"),
    ("PTBA", "Bukit Asam Tbk", "Energi", "Bukit Asam"),
    ("ITMG", "Indo Tambangraya Megah Tbk", "Energi", "Indo Tambangraya"),
    ("MEDC", "Medco Energi Internasional Tbk", "Energi", "Medco Energi|Medco"),
    ("PGAS", "Perusahaan Gas Negara Tbk", "Energi", "PGN"),
    ("PGEO", "Pertamina Geothermal Energy Tbk", "Energi", "Pertamina Geothermal"),
    ("AKRA", "AKR Corporindo Tbk", "Energi", "AKR Corporindo"),
    ("INDY", "Indika Energy Tbk", "Energi", "Indika Energy|Indika"),
    ("BUMI", "Bumi Resources Tbk", "Energi", "Bumi Resources"),
    ("CUAN", "Petrindo Jaya Kreasi Tbk", "Energi", "Petrindo Jaya Kreasi|Petrindo"),
    ("DEWA", "Darma Henwa Tbk", "Energi", "Darma Henwa"),

    # --- Barang Baku ---
    ("ANTM", "Aneka Tambang Tbk", "Barang Baku", "Antam|Aneka Tambang"),
    ("INCO", "Vale Indonesia Tbk", "Barang Baku", "Vale Indonesia"),
    ("MDKA", "Merdeka Copper Gold Tbk", "Barang Baku", "Merdeka Copper"),
    ("MBMA", "Merdeka Battery Materials Tbk", "Barang Baku", "Merdeka Battery"),
    ("AMMN", "Amman Mineral Internasional Tbk", "Barang Baku", "Amman Mineral"),
    ("NCKL", "Trimegah Bangun Persada Tbk", "Barang Baku", "Trimegah Bangun Persada|Harita Nickel"),
    ("BRPT", "Barito Pacific Tbk", "Barang Baku", "Barito Pacific"),
    ("ESSA", "Essa Industries Indonesia Tbk", "Barang Baku", "Essa Industries"),
    ("INKP", "Indah Kiat Pulp & Paper Tbk", "Barang Baku", "Indah Kiat"),

    # --- Konsumen Primer ---
    ("ICBP", "Indofood CBP Sukses Makmur Tbk", "Konsumen Primer", "Indofood CBP"),
    ("INDF", "Indofood Sukses Makmur Tbk", "Konsumen Primer", "Indofood Sukses Makmur"),
    ("UNVR", "Unilever Indonesia Tbk", "Konsumen Primer", "Unilever Indonesia"),
    ("CPIN", "Charoen Pokphand Indonesia Tbk", "Konsumen Primer", "Charoen Pokphand"),
    ("JPFA", "Japfa Comfeed Indonesia Tbk", "Konsumen Primer", "Japfa"),
    ("AMRT", "Sumber Alfaria Trijaya Tbk", "Konsumen Primer", "Alfamart|Sumber Alfaria"),

    # --- Konsumen Nonprimer ---
    ("MAPI", "Mitra Adiperkasa Tbk", "Konsumen Nonprimer", "Mitra Adiperkasa"),
    ("HRTA", "Hartadinata Abadi Tbk", "Konsumen Nonprimer", "Hartadinata Abadi|Hartadinata"),
    ("SCMA", "Surya Citra Media Tbk", "Konsumen Nonprimer", "Surya Citra Media"),

    # --- Kesehatan ---
    ("KLBF", "Kalbe Farma Tbk", "Kesehatan", "Kalbe Farma|Kalbe"),

    # --- Perindustrian ---
    ("ASII", "Astra International Tbk", "Perindustrian", "Astra International"),
    ("UNTR", "United Tractors Tbk", "Perindustrian", "United Tractors"),

    # --- Teknologi ---
    ("GOTO", "GoTo Gojek Tokopedia Tbk", "Teknologi", "GoTo|Gojek Tokopedia"),
    ("EMTK", "Elang Mahkota Teknologi Tbk", "Teknologi", "Elang Mahkota"),
    ("WIFI", "Solusi Sinergi Digital Tbk", "Teknologi", "Solusi Sinergi Digital"),
]

SUMBER_AWAL: list[tuple[str, str, str, str]] = [
    # (nama, domain, url_rss, kredibilitas)
    #
    # Sumber dipilih dengan satu syarat: isinya memang membahas emiten, bukan
    # ekonomi makro atau gaya hidup. Menambah portal yang beritanya jarang
    # menyebut emiten bukan langkah netral — ia mengencerkan rasio pemetaan dan
    # mengisi basis data dengan berita yang tidak pernah terpakai.
    #
    # Diuji hidup pada 18 September 2026 lewat `python -m scripts.cek_kandidat`.
    # Jalankan ulang script itu sebelum pengumpulan data penelitian dimulai.
    ("CNBC Indonesia", "www.cnbcindonesia.com",
     "https://www.cnbcindonesia.com/market/rss", "terverifikasi_dewan_pers"),
    ("Kontan", "investasi.kontan.co.id",
     "https://investasi.kontan.co.id/rss", "terverifikasi_dewan_pers"),
    ("Detik Finance", "finance.detik.com",
     "https://finance.detik.com/rss", "terverifikasi_dewan_pers"),
    ("IDX Channel", "www.idxchannel.com",
     "https://www.idxchannel.com/rss", "terverifikasi_dewan_pers"),
    ("Bloomberg Technoz", "www.bloombergtechnoz.com",
     "https://www.bloombergtechnoz.com/rss", "terverifikasi_dewan_pers"),
    ("Republika Ekonomi", "republika.co.id",
     "https://republika.co.id/rss/ekonomi", "terverifikasi_dewan_pers"),
    # Pasardana kerap menyebut kode emiten langsung di judul, tapi bukan anggota
    # terverifikasi Dewan Pers — bobotnya pada agregasi memang lebih rendah.
    ("Pasardana", "pasardana.id",
     "https://pasardana.id/rss", "portal_umum"),
]

# Sumber yang pernah dipakai lalu dinonaktifkan. Barisnya sengaja tidak dihapus:
# alasan penonaktifan adalah bagian dari catatan penelitian, dan kalau portalnya
# hidup kembali, cukup pindahkan barisnya ke SUMBER_AWAL.
#
# Kegagalan di bawah TIDAK diakali dengan memalsukan User-Agent supaya terlihat
# seperti peramban. Portal yang menolak klien otomatis sedang menyatakan
# keberatan, dan menembusnya akan membuat cara pengumpulan data penelitian ini
# tidak bisa dipertanggungjawabkan.
SUMBER_NONAKTIF: list[tuple[str, str]] = [
    # (domain, alasan)
    ("market.bisnis.com", "HTTP 403 — portal menolak klien non-peramban (18 Sep 2026)"),
    ("emitennews.com", "HTTP 500 — endpoint feed bermasalah (18 Sep 2026)"),
]
