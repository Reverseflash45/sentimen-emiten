"""Pengaturan bersama untuk seluruh uji.

PBKDF2 sengaja dibuat lambat — itu memang gunanya. Tapi di dalam uji, jumlah
iterasi penuh membuat suite berjalan berkali-kali lebih lama tanpa menguji hal
baru, jadi di sini iterasinya diturunkan. Jumlah iterasi ikut tersimpan di
dalam string hash, sehingga pemeriksaan tetap bekerja apa adanya.

Nilai yang dipakai di luar uji diperiksa sendiri di `test_keamanan.py`.
"""

from __future__ import annotations

import pytest

from app.auth import keamanan


@pytest.fixture(autouse=True)
def _pbkdf2_cepat(monkeypatch):
    monkeypatch.setattr(keamanan, "ITERASI", 1_000)
