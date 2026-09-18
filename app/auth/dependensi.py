"""Dependency FastAPI untuk autentikasi dan pembatasan peran."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.keamanan import TokenTidakSah, baca_token
from app.database import get_session
from app.models import Peran, Pengguna

skema = HTTPBearer(auto_error=False, description="Token dari /api/auth/masuk")


def pengguna_aktif(
    kredensial: HTTPAuthorizationCredentials | None = Depends(skema),
    session: Session = Depends(get_session),
) -> Pengguna:
    if kredensial is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "perlu masuk terlebih dahulu",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        muatan = baca_token(kredensial.credentials)
    except TokenTidakSah as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e

    pengguna = session.get(Pengguna, muatan.get("sub"))
    if pengguna is None or not pengguna.aktif:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "akun tidak aktif")
    return pengguna


def wajib_analis(pengguna: Pengguna = Depends(pengguna_aktif)) -> Pengguna:
    """Koreksi label dan status verifikasi hanya boleh dilakukan analis.

    Peran diambil dari basis data, bukan dari isi token — supaya pencabutan hak
    langsung berlaku tanpa menunggu token lama kedaluwarsa.
    """
    if pengguna.peran is not Peran.ANALIS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "perlu peran analis")
    return pengguna
