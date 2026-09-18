"""Membuat atau memperbarui akun pengguna.

    python -m scripts.buat_pengguna analis@contoh.id "Rafi Fernandito" --peran analis

Kata sandi ditanyakan lewat prompt tersembunyi, tidak lewat argumen — argumen
baris perintah tersimpan di riwayat shell dan terlihat di daftar proses.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.auth.keamanan import hash_kata_sandi
from app.database import SessionLocal, engine
from app.models import Base, Peran, Pengguna

PANJANG_MIN = 10


def minta_kata_sandi() -> str:
    for _ in range(3):
        satu = getpass.getpass("Kata sandi        : ")
        if len(satu) < PANJANG_MIN:
            print(f"  terlalu pendek, minimal {PANJANG_MIN} karakter", file=sys.stderr)
            continue
        dua = getpass.getpass("Ulangi kata sandi : ")
        if satu != dua:
            print("  tidak sama, coba lagi", file=sys.stderr)
            continue
        return satu
    raise SystemExit("gagal membaca kata sandi")


def main() -> None:
    p = argparse.ArgumentParser(description="Buat atau perbarui akun pengguna")
    p.add_argument("email")
    p.add_argument("nama")
    p.add_argument("--peran", choices=[x.value for x in Peran], default=Peran.PENGGUNA.value)
    a = p.parse_args()

    Base.metadata.create_all(engine)
    email = a.email.strip().lower()
    sandi = minta_kata_sandi()

    with SessionLocal() as session:
        pengguna = session.scalar(select(Pengguna).where(Pengguna.email == email))
        if pengguna is None:
            pengguna = Pengguna(email=email, nama=a.nama, peran=Peran(a.peran))
            session.add(pengguna)
            aksi = "dibuat"
        else:
            pengguna.nama = a.nama
            pengguna.peran = Peran(a.peran)
            pengguna.aktif = True
            aksi = "diperbarui"
        pengguna.kata_sandi_hash = hash_kata_sandi(sandi)
        session.commit()

    print(f"Akun {email} ({a.peran}) {aksi}.")


if __name__ == "__main__":
    main()
