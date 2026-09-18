"""Uji parser RSS/Atom — tidak menyentuh jaringan."""

from app.ingest.rss import parse_feed

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Pasar Modal</title>
    <item>
      <title>Laba BBCA Naik 12 Persen</title>
      <link>https://contoh.id/berita/1?utm_source=rss</link>
      <description>&lt;p&gt;JAKARTA, CONTOH.ID - Bank Central Asia mencatat kenaikan laba.&lt;/p&gt;</description>
      <pubDate>Mon, 15 Sep 2026 08:30:00 +0700</pubDate>
    </item>
    <item>
      <title>IHSG Dibuka Menguat</title>
      <link>https://contoh.id/berita/2</link>
      <description>Indeks naik tipis pada pembukaan.</description>
      <dc:date>2026-09-15T02:00:00Z</dc:date>
    </item>
    <item>
      <title></title>
      <link>https://contoh.id/berita/3</link>
    </item>
  </channel>
</rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Emiten Tambang Bagikan Dividen</title>
    <link rel="alternate" href="https://atom.test/a"/>
    <summary>Pembagian dividen interim diumumkan.</summary>
    <published>2026-09-14T10:00:00Z</published>
  </entry>
</feed>"""


def test_parse_rss_dua_item_valid():
    hasil = parse_feed(RSS)
    # item ketiga tanpa judul harus dilewati
    assert len(hasil) == 2
    assert hasil[0].judul == "Laba BBCA Naik 12 Persen"


def test_parameter_pelacakan_dibuang_dari_url():
    hasil = parse_feed(RSS)
    assert hasil[0].url == "https://contoh.id/berita/1"


def test_html_dan_pembuka_redaksi_dibersihkan_dari_ringkasan():
    hasil = parse_feed(RSS)
    ringkasan = hasil[0].ringkasan
    assert "<p>" not in ringkasan
    assert ringkasan.startswith("Bank Central Asia")


def test_tanggal_diubah_ke_utc():
    hasil = parse_feed(RSS)
    terbit = hasil[0].terbit_pada
    assert terbit is not None
    assert terbit.tzinfo is not None
    assert terbit.hour == 1  # 08:30 WIB = 01:30 UTC


def test_tanggal_dublin_core_terbaca():
    assert parse_feed(RSS)[1].terbit_pada is not None


def test_parse_atom():
    hasil = parse_feed(ATOM)
    assert len(hasil) == 1
    assert hasil[0].url == "https://atom.test/a"
    assert hasil[0].terbit_pada is not None


def test_feed_rusak_melempar_kesalahan_jelas():
    import pytest
    with pytest.raises(ValueError):
        parse_feed("bukan xml sama sekali <<<")
