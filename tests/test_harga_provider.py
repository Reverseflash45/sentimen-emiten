"""Uji pembacaan harga dari CSV."""

from __future__ import annotations

from datetime import date

import pytest

from app.harga.provider import PenyediaCsv

CSV_ID = """Tanggal,Pembukaan,Tertinggi,Terendah,Penutupan,Volume
2026-09-01,9000,9100,8950,9050,12000000
2026-09-02,9050,9200,9000,9180,15000000
2026-10-05,9180,9300,9100,9250,9000000
"""

CSV_EN = """Date,Open,High,Low,Close,Volume
2026-09-01,9000,9100,8950,9050,12000000
"""

CSV_RUSAK = """Kolom,Aneh
1,2
"""


@pytest.fixture()
def folder(tmp_path):
    (tmp_path / "BBCA.csv").write_text(CSV_ID, encoding="utf-8")
    (tmp_path / "BBRI.csv").write_text(CSV_EN, encoding="utf-8")
    (tmp_path / "RUSAK.csv").write_text(CSV_RUSAK, encoding="utf-8")
    return tmp_path


def test_membaca_kolom_bahasa_indonesia(folder):
    baris = PenyediaCsv(folder).ambil("BBCA", date(2026, 9, 1), date(2026, 9, 30))
    assert len(baris) == 2          # baris Oktober di luar rentang
    assert baris[0].penutupan == 9050
    assert baris[0].volume == 12000000


def test_membaca_kolom_bahasa_inggris(folder):
    baris = PenyediaCsv(folder).ambil("BBRI", date(2026, 9, 1), date(2026, 9, 30))
    assert len(baris) == 1
    assert baris[0].pembukaan == 9000


def test_rentang_tanggal_dihormati(folder):
    baris = PenyediaCsv(folder).ambil("BBCA", date(2026, 10, 1), date(2026, 10, 31))
    assert len(baris) == 1
    assert baris[0].penutupan == 9250


def test_hasil_terurut_menaik(folder):
    baris = PenyediaCsv(folder).ambil("BBCA", date(2026, 1, 1), date(2026, 12, 31))
    assert [b.tanggal for b in baris] == sorted(b.tanggal for b in baris)


def test_emiten_tanpa_berkas_mengembalikan_kosong(folder):
    assert PenyediaCsv(folder).ambil("TIDAKADA", date(2026, 9, 1), date(2026, 9, 30)) == []


def test_csv_tanpa_kolom_tanggal_ditolak_dengan_jelas(folder):
    with pytest.raises(ValueError, match="kolom tanggal"):
        PenyediaCsv(folder).ambil("RUSAK", date(2026, 9, 1), date(2026, 9, 30))


def test_semua_tanggal_dikembalikan_dalam_utc(folder):
    baris = PenyediaCsv(folder).ambil("BBCA", date(2026, 1, 1), date(2026, 12, 31))
    assert all(b.tanggal.tzinfo is not None for b in baris)
