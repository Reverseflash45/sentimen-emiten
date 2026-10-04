"""Mengirim notifikasi watchlist lewat email (SRS FR-6, saluran tambahan).

Notifikasi di dalam aplikasi selalu dibuat; email hanya tambahan, dan hanya
untuk pengguna yang menyalakannya sendiri di panel notifikasi (opt-in). Email
tanpa persetujuan penerimanya adalah spam, apa pun isinya.

Aktif hanya bila SMTP diatur lewat environment (.env atau secret GitHub Actions):

    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=alamat@gmail.com
    SMTP_PASSWORD=<app password 16 huruf, bukan kata sandi akun>
    SMTP_FROM=Sentimen Emiten <alamat@gmail.com>    # opsional

Tanpa itu, fungsi di sini tidak mengirim apa pun dan tidak menimbulkan galat —
siklus pengumpulan tidak boleh gagal hanya karena email belum diatur.
"""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.models import Notifikasi, Pengguna

TAUTAN_DASBOR = os.environ.get("ALAMAT_DASBOR", "https://sentimen.raffstw.my.id")


@dataclass(frozen=True)
class KonfigSmtp:
    host: str
    port: int
    user: str
    sandi: str
    pengirim: str

    @classmethod
    def dari_env(cls) -> KonfigSmtp | None:
        host, user, sandi = (os.environ.get(k, "").strip() for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"))
        if not (host and user and sandi):
            return None
        return cls(host=host, port=int(os.environ.get("SMTP_PORT") or 587), user=user, sandi=sandi,
                   pengirim=os.environ.get("SMTP_FROM", "").strip() or user)


def susun_email(pengguna: Pengguna, daftar: list[Notifikasi], pengirim: str) -> EmailMessage:
    m = EmailMessage()
    kode = ", ".join(sorted({n.emiten.kode for n in daftar}))
    m["Subject"] = f"Sentimen berubah: {kode}"
    m["From"] = pengirim
    m["To"] = pengguna.email
    baris = "\n".join(f"- {n.pesan}" for n in daftar)
    m.set_content(
        f"Halo {pengguna.nama},\n\nSentimen berita emiten di watchlist kamu bergeser melewati ambang:\n\n"
        f"{baris}\n\nLihat grafik dan beritanya: {TAUTAN_DASBOR}\n\n"
        "Ini analisis hubungan sentimen, bukan rekomendasi membeli atau menjual efek.\n"
        "Matikan email ini lewat panel notifikasi di dasbor.\n"
    )
    return m


def kirim_notifikasi(session: Session, baru: list[Notifikasi], konfig: KonfigSmtp | None = None) -> str:
    """Satu email per pengguna yang opt-in, berisi semua notifikasi barunya.
    Mengembalikan ringkasan untuk log siklus."""
    konfig = konfig or KonfigSmtp.dari_env()
    if konfig is None:
        return "nonaktif (SMTP belum diatur)"
    per_pengguna: dict[int, list[Notifikasi]] = {}
    for n in baru:
        per_pengguna.setdefault(n.pengguna_id, []).append(n)
    terkirim = gagal = 0
    with smtplib.SMTP(konfig.host, konfig.port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(konfig.user, konfig.sandi)
        for pid, daftar in per_pengguna.items():
            pengguna = session.get(Pengguna, pid)
            if pengguna is None or not pengguna.aktif or not pengguna.kirim_email:
                continue
            try:
                smtp.send_message(susun_email(pengguna, daftar, konfig.pengirim))
                terkirim += 1
            except smtplib.SMTPException:
                gagal += 1  # satu alamat bermasalah tidak menghentikan yang lain
    return f"{terkirim} terkirim, {gagal} gagal"
