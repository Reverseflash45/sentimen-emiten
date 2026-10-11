"""Endpoint autentikasi (SRS UC-02).

Pendaftaran mandiri sengaja TIDAK disediakan lewat API. Akun dibuat lewat
`python -m scripts.buat_pengguna`, karena sistem ini dipakai kalangan terbatas
dan pendaftaran terbuka hanya menambah permukaan serangan tanpa manfaat.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import batas
from app.auth.dependensi import pengguna_aktif
from app.auth.keamanan import buat_token, periksa_kata_sandi
from app.config import settings
from app.database import get_session
from app.models import Pengguna
from app.schemas import Masuk, PenggunaRingkas, Token

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _ip(request: Request) -> str:
    """IP pengirim; di Vercel diambil dari header proksi."""
    terusan = request.headers.get("x-forwarded-for", "")
    return (
        request.headers.get("x-real-ip")
        or terusan.split(",")[0].strip()
        or (request.client.host if request.client else "?")
    )


@router.post("/masuk", response_model=Token)
def masuk(badan: Masuk, request: Request, session: Session = Depends(get_session)) -> Token:
    email = badan.email.strip().lower()
    kunci = [f"ip:{_ip(request)}", f"email:{email}"]
    tunggu = batas.sisa_tunggu(kunci)
    if tunggu:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"terlalu banyak percobaan gagal, coba lagi dalam {max(1, tunggu // 60)} menit",
            headers={"Retry-After": str(tunggu)},
        )

    pengguna = session.scalar(select(Pengguna).where(Pengguna.email == email))
    # Pesan galat sengaja sama untuk email tidak terdaftar maupun sandi salah,
    # supaya tidak bisa dipakai menebak email mana yang punya akun.
    galat = HTTPException(status.HTTP_401_UNAUTHORIZED, "email atau kata sandi salah")
    if (
        pengguna is None
        or not pengguna.aktif
        or not periksa_kata_sandi(badan.kata_sandi, pengguna.kata_sandi_hash)
    ):
        batas.catat_gagal(kunci)
        raise galat
    batas.reset([f"email:{email}"])

    return Token(
        token=buat_token(pengguna.id, pengguna.peran.value),
        berlaku_jam=settings.token_berlaku_jam,
    )


@router.get("/saya", response_model=PenggunaRingkas)
def saya(pengguna: Pengguna = Depends(pengguna_aktif)) -> PenggunaRingkas:
    return PenggunaRingkas(
        id=pengguna.id, email=pengguna.email, nama=pengguna.nama, peran=pengguna.peran,
        kirim_email=pengguna.kirim_email,
    )
