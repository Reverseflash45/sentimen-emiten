from app.ingest.matcher import cocokkan

EMITEN = {
    "BBCA": ["Bank Central Asia Tbk", "BCA", "Bank BCA"],
    "INCO": ["Vale Indonesia Tbk", "Vale Indonesia"],
    "ACES": ["Aspirasi Hidup Indonesia Tbk", "Ace Hardware"],
    "GOTO": ["GoTo Gojek Tokopedia Tbk", "GoTo"],
}


def test_cocok_lewat_kode():
    hasil = cocokkan("Saham BBCA ditutup menguat hari ini", EMITEN)
    assert [k.kode for k in hasil] == ["BBCA"]
    assert hasil[0].cara == "kode"


def test_cocok_lewat_nama_perusahaan():
    hasil = cocokkan("Bank Central Asia Tbk membagikan dividen interim", EMITEN)
    assert [k.kode for k in hasil] == ["BBCA"]
    assert hasil[0].cara == "nama"


def test_kode_ambigu_ditolak_tanpa_konteks_pasar():
    # "ACES" di sini bagian dari kalimat Inggris, bukan kode emiten
    hasil = cocokkan("The team ACES every challenge they face", EMITEN)
    assert hasil == []


def test_kode_ambigu_diterima_dengan_konteks_pasar():
    hasil = cocokkan("Saham ACES menguat setelah laporan laba", EMITEN)
    assert [k.kode for k in hasil] == ["ACES"]


def test_kode_tidak_cocok_sebagian_kata():
    # "BBCAX" bukan BBCA
    assert cocokkan("Produk BBCAX diluncurkan", EMITEN) == []


def test_satu_berita_bisa_terkait_beberapa_emiten():
    teks = "Saham BBCA dan GOTO sama-sama menguat di bursa hari ini"
    assert {k.kode for k in cocokkan(teks, EMITEN)} == {"BBCA", "GOTO"}


def test_tidak_ada_duplikat_untuk_emiten_yang_sama():
    teks = "BBCA menguat. Bank Central Asia Tbk mencatat laba. BBCA ditutup naik."
    hasil = cocokkan(teks, EMITEN)
    assert len(hasil) == 1


def test_kutipan_ikut_disertakan():
    hasil = cocokkan("Saham BBCA ditutup menguat hari ini", EMITEN)
    assert "BBCA" in hasil[0].kutipan


def test_nama_emiten_harus_kata_utuh():
    """'menghantam' memuat 'antam'. Tanpa batas kata, sebuah berita serangan
    udara terpetakan ke Aneka Tambang — ini terjadi pada uji nyata."""
    daftar = {"ANTM": ["Aneka Tambang Tbk", "Antam"]}
    assert cocokkan("serangan yang menghantam sekolah dasar di Minab", daftar) == []
    assert cocokkan("Saham Antam menguat di bursa hari ini", daftar)


def test_nama_di_tengah_kata_lain_tidak_cocok():
    daftar = {"MEDC": ["Medco Energi Internasional Tbk", "Medco"]}
    assert cocokkan("biaya pengobatan medcocok tidak ditanggung", daftar) == []
