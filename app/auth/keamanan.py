"""Penyimpanan kata sandi dan token sesi.

Kata sandi diturunkan dengan PBKDF2-HMAC-SHA256 dari pustaka bawaan Python,
memakai garam acak per akun dan 240.000 iterasi. Pilihan ini disengaja:

- kata sandi tidak pernah disimpan apa adanya, juga tidak di-hash sekali jalan
  dengan SHA-256 — hash cepat justru mempermudah serangan daftar kata;
- PBKDF2 tersedia di pustaka bawaan, jadi tidak ada paket yang perlu dikompilasi.
  Argon2id sebenarnya lebih baik dan menjadi jalur peningkatan yang jelas;
  bentuk simpanannya sudah memuat nama algoritme di depan, jadi penggantian bisa
  dilakukan bertahap tanpa memaksa semua orang mengatur ulang kata sandinya.

Perbandingan hash memakai `hmac.compare_digest` supaya lama pembandingan tidak
membocorkan seberapa banyak karakter yang cocok.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

from app.config import settings

ALGORITME = "pbkdf2_sha256"
#: nilai sebenarnya; `ITERASI` boleh diturunkan di dalam uji
ITERASI_BAWAAN = 240_000
ITERASI = ITERASI_BAWAAN
PANJANG_GARAM = 16


def hash_kata_sandi(kata_sandi: str, garam: bytes | None = None) -> str:
    garam = garam or os.urandom(PANJANG_GARAM)
    turunan = hashlib.pbkdf2_hmac("sha256", kata_sandi.encode("utf-8"), garam, ITERASI)
    return f"{ALGORITME}${ITERASI}${garam.hex()}${turunan.hex()}"


def periksa_kata_sandi(kata_sandi: str, tersimpan: str) -> bool:
    try:
        algoritme, iterasi, garam_hex, turunan_hex = tersimpan.split("$")
        if algoritme != ALGORITME:
            return False
        turunan = hashlib.pbkdf2_hmac(
            "sha256", kata_sandi.encode("utf-8"), bytes.fromhex(garam_hex), int(iterasi)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(turunan.hex(), turunan_hex)


# --------------------------------------------------------------------- token


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _dari_b64(teks: str) -> bytes:
    return base64.urlsafe_b64decode(teks + "=" * (-len(teks) % 4))


def _tanda_tangan(isi: str) -> str:
    mac = hmac.new(settings.secret_key.encode("utf-8"), isi.encode("utf-8"), hashlib.sha256)
    return _b64(mac.digest())


def buat_token(pengguna_id: int, peran: str, berlaku_jam: int | None = None) -> str:
    """Token sesi bertanda tangan HMAC.

    Bentuknya sengaja sederhana dan ditulis sendiri supaya isinya terlihat jelas
    saat diperiksa: muatan JSON ber-base64 ditambah tanda tangan HMAC-SHA256.
    Tanpa kunci rahasia, muatan tidak bisa dipalsukan.
    """
    jam = berlaku_jam or settings.token_berlaku_jam
    muatan = {
        "sub": pengguna_id,
        "peran": peran,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=jam)).timestamp()),
    }
    isi = _b64(json.dumps(muatan, separators=(",", ":")).encode("utf-8"))
    return f"{isi}.{_tanda_tangan(isi)}"


class TokenTidakSah(Exception):
    pass


def baca_token(token: str) -> dict:
    try:
        isi, tanda = token.split(".")
    except ValueError as e:
        raise TokenTidakSah("bentuk token tidak dikenali") from e

    if not hmac.compare_digest(tanda, _tanda_tangan(isi)):
        raise TokenTidakSah("tanda tangan tidak cocok")

    try:
        muatan = json.loads(_dari_b64(isi))
    except (ValueError, TypeError) as e:
        raise TokenTidakSah("muatan token rusak") from e

    if muatan.get("exp", 0) < datetime.now(timezone.utc).timestamp():
        raise TokenTidakSah("token sudah kedaluwarsa")
    return muatan
