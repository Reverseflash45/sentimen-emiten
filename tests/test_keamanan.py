"""Uji penyimpanan kata sandi dan token sesi."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.auth import keamanan
from app.auth.keamanan import (
    TokenTidakSah,
    _b64,
    baca_token,
    buat_token,
    hash_kata_sandi,
    periksa_kata_sandi,
)


def test_iterasi_bawaan_cukup_tinggi():
    """Penjaga supaya nilai rendah yang dipakai uji tidak pernah ikut terbawa."""
    assert keamanan.ITERASI_BAWAAN >= 200_000


def test_hash_tidak_memuat_kata_sandi():
    h = hash_kata_sandi("rahasia123")
    assert "rahasia123" not in h
    assert h.startswith("pbkdf2_sha256$")


def test_dua_hash_kata_sandi_sama_berbeda():
    """Garam acak per akun: dua orang dengan sandi sama tidak terlihat sama."""
    assert hash_kata_sandi("sama") != hash_kata_sandi("sama")


def test_periksa_kata_sandi():
    h = hash_kata_sandi("rahasia123")
    assert periksa_kata_sandi("rahasia123", h)
    assert not periksa_kata_sandi("rahasia124", h)


def test_hash_rusak_ditolak_bukan_dilempar():
    assert not periksa_kata_sandi("apa saja", "bukan-hash")
    assert not periksa_kata_sandi("apa saja", "md5$1$aa$bb")


def test_token_bolak_balik():
    muatan = baca_token(buat_token(7, "analis"))
    assert muatan["sub"] == 7 and muatan["peran"] == "analis"


def test_token_tanda_tangan_diubah_ditolak():
    token = buat_token(7, "analis")
    isi, _ = token.split(".")
    with pytest.raises(TokenTidakSah):
        baca_token(f"{isi}.tandatanganpalsu")


def test_muatan_diubah_ditolak():
    """Menaikkan peran sendiri lewat isi token harus gagal."""
    token = buat_token(7, "pengguna")
    _, tanda = token.split(".")
    jahat = {
        "sub": 7,
        "peran": "analis",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
    }
    isi = _b64(json.dumps(jahat, separators=(",", ":")).encode())
    with pytest.raises(TokenTidakSah):
        baca_token(f"{isi}.{tanda}")


def test_token_kedaluwarsa_ditolak():
    with pytest.raises(TokenTidakSah):
        baca_token(buat_token(7, "analis", berlaku_jam=-1))


def test_token_bentuk_aneh_ditolak():
    for buruk in ["", "tanpatitik", "a.b.c"]:
        with pytest.raises(TokenTidakSah):
            baca_token(buruk)
