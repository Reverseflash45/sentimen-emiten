"""Fungsi bantu yang dipakai beberapa router."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Emiten

RENTANG_BAWAAN_HARI = 30

# Batas ini bukan batas penelitian, melainkan penjaga beban: satu permintaan
# rentang panjang menghitung skor harian untuk setiap berita pada rentang itu.
# Lima tahun jauh melampaui kebutuhan (data sentimen baru mulai dikumpulkan
# 2026), tapi cukup longgar supaya "seluruh data" tidak pernah tertolak.
RENTANG_MAKS_HARI = 1830


def rentang(mulai: date | None, sampai: date | None) -> tuple[date, date]:
    """Menormalkan rentang tanggal, dengan bawaan 30 hari terakhir."""
    sampai = sampai or date.today()
    mulai = mulai or (sampai - timedelta(days=RENTANG_BAWAAN_HARI))
    if mulai > sampai:
        raise HTTPException(400, "tanggal mulai melewati tanggal sampai")
    if (sampai - mulai).days > RENTANG_MAKS_HARI:
        raise HTTPException(400, f"rentang maksimum {RENTANG_MAKS_HARI} hari")
    return mulai, sampai


def ambil_emiten(session: Session, kode: str) -> Emiten:
    emiten = session.scalar(select(Emiten).where(Emiten.kode == kode.upper()))
    if emiten is None:
        raise HTTPException(404, f"emiten {kode.upper()} tidak ditemukan")
    return emiten
