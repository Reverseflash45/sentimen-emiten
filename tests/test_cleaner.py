from app.ingest.cleaner import bersihkan, normalisasi, sidik_jari


def test_membuang_tag_html():
    assert bersihkan("<p>Laba <b>naik</b> tajam</p>") == "Laba naik tajam"


def test_membuang_pembuka_redaksi():
    assert bersihkan("JAKARTA, KONTAN.CO.ID - Saham BBCA menguat") == "Saham BBCA menguat"
    assert bersihkan("Bisnis.com, JAKARTA — Emiten cetak laba") == "Emiten cetak laba"


def test_membuang_url_dan_spasi_ganda():
    hasil = bersihkan("Baca   di https://contoh.id/berita   selengkapnya")
    assert "https" not in hasil
    assert "  " not in hasil


def test_normalisasi_membuang_tanda_baca():
    assert normalisasi("Laba, naik 42% (yoy)!") == "laba naik 42 yoy"


def test_sidik_jari_sama_untuk_judul_setara():
    a = sidik_jari("Laba BBRI Naik 42%", "Kinerja kuartal III")
    b = sidik_jari("laba bbri naik 42 %", "kinerja kuartal iii")
    assert a == b


def test_sidik_jari_beda_untuk_judul_berbeda():
    assert sidik_jari("Laba BBRI naik") != sidik_jari("Laba BBCA naik")


def test_teks_kosong_aman():
    assert bersihkan(None) == ""
    assert bersihkan("") == ""
