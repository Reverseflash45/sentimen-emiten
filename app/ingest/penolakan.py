"""Menolak pemetaan berita-emiten yang keliru (SRS UC-05 alur alternatif 4a).

Dipakai bersama oleh dasbor analis dan scripts.label_manual, supaya kedua
jalan itu berakibat sama: kaitannya hilang dari skor sentimen, daftar berita,
dan antrean tinjauan, sementara buktinya tetap tersimpan.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import BeritaEmiten, LabelSentimen, PemetaanDitolak


def tolak_pemetaan(
    session: Session, berita_id: int, emiten_id: int, pengguna_id: int | None = None
) -> bool:
    """Memindahkan kaitan berita-emiten ke daftar tolakan.

    Label yang sudah ada untuk pasangan itu ikut dihapus: label sentimen
    terhadap emiten yang sebenarnya tidak dibahas tidak bermakna, dan kalau
    dibiarkan ia akan ikut terbaca sebagai data latih. Mengembalikan False bila
    kaitannya memang tidak ada (sudah ditolak, atau tidak pernah dipetakan).
    Tidak melakukan commit — itu urusan pemanggil.
    """
    kaitan = session.scalar(
        select(BeritaEmiten).where(
            BeritaEmiten.berita_id == berita_id, BeritaEmiten.emiten_id == emiten_id
        )
    )
    if kaitan is None:
        return False
    sudah = session.scalar(
        select(PemetaanDitolak).where(
            PemetaanDitolak.berita_id == berita_id, PemetaanDitolak.emiten_id == emiten_id
        )
    )
    if sudah is None:
        session.add(
            PemetaanDitolak(
                berita_id=berita_id,
                emiten_id=emiten_id,
                cara_cocok=kaitan.cara_cocok,
                kutipan=kaitan.kutipan,
                pengguna_id=pengguna_id,
            )
        )
    session.execute(
        delete(LabelSentimen).where(
            LabelSentimen.berita_id == berita_id, LabelSentimen.emiten_id == emiten_id
        )
    )
    session.delete(kaitan)
    return True


def pasangan_ditolak(session: Session) -> set[tuple[int, int]]:
    """(berita_id, emiten_id) yang pernah ditolak."""
    return set(session.execute(select(PemetaanDitolak.berita_id, PemetaanDitolak.emiten_id)).all())
