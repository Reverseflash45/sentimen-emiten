"""Endpoint autentikasi (SRS UC-02).

Pendaftaran mandiri sengaja TIDAK disediakan lewat API. Akun dibuat lewat
`python -m scripts.buat_pengguna`, karena sistem ini dipakai kalangan terbatas
dan pendaftaran terbuka hanya menambah permukaan serangan tanpa manfaat.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependensi import pengguna_aktif
from app.auth.keamanan import buat_token, periksa_kata_sandi
from app.config import settings
from app.database import get_session
from app.models import Pengguna
from app.schemas import Masuk, PenggunaRingkas, Token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/masuk", response_model=Token)
def masuk(badan: Masuk, session: Session = Depends(get_session)) -> Token:
    pengguna = session.scalar(
        select(Pengguna).where(Pengguna.email == badan.email.strip().lower())
    )
    # Pesan galat sengaja sama untuk email tidak terdaftar maupun sandi salah,
    # supaya tidak bisa dipakai menebak email mana yang punya akun.
    galat = HTTPException(status.HTTP_401_UNAUTHORIZED, "email atau kata sandi salah")
    if pengguna is None or not pengguna.aktif:
        raise galat
    if not periksa_kata_sandi(badan.kata_sandi, pengguna.kata_sandi_hash):
        raise galat

    return Token(
        token=buat_token(pengguna.id, pengguna.peran.value),
        berlaku_jam=settings.token_berlaku_jam,
    )


@router.get("/saya", response_model=PenggunaRingkas)
def saya(pengguna: Pengguna = Depends(pengguna_aktif)) -> PenggunaRingkas:
    return PenggunaRingkas(
        id=pengguna.id, email=pengguna.email, nama=pengguna.nama, peran=pengguna.peran
    )
