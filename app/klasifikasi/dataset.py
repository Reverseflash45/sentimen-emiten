"""Bagian yang dipakai bersama oleh anotasi, pelatihan, evaluasi, dan inferensi.

Teks masukan model dan pembagian data sengaja didefinisikan di SATU tempat.
Kalau skrip pelatihan menyusun teks sedikit berbeda dari kode inferensi
(urutan, pemisah, ada/tidaknya kutipan), model dinilai bagus saat evaluasi
tetapi salah di produksi — dan selisih semacam itu hampir tidak terlihat.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AsalLabel, Berita, BeritaEmiten, Emiten, LabelSentimen, Sentimen

#: versi_model untuk label manual hasil anotasi (asal=ANALIS)
VERSI_ANOTASI = "anotasi"

#: urutan kelas untuk model; jangan diubah setelah model dilatih
KELAS: list[Sentimen] = [Sentimen.NEGATIF, Sentimen.NETRAL, Sentimen.POSITIF]


def teks_utama(judul: str, ringkasan: str | None) -> str:
    return f"{judul}. {ringkasan or ''}".strip()


def teks_target(kode: str, nama: str, kutipan: str | None) -> str:
    """Segmen kedua pasangan kalimat: emiten yang dinilai dan kalimat yang
    menyebutnya. Inilah yang membuat label bisa berbeda antar-emiten dalam
    satu berita yang sama."""
    kutip = (kutipan or "").replace("…", " ").strip()
    return f"{kode} ({nama}). {kutip}".strip()


def bagian_data(berita_id: int) -> str:
    """Membagi data per BERITA (bukan per pasangan) secara deterministik:
    70% latih, 15% validasi, 15% uji.

    Per berita, supaya satu artikel yang menyebut beberapa emiten tidak
    muncul sekaligus di data latih dan data uji — kebocoran yang membuat
    skor uji terlihat lebih tinggi dari kenyataan. Berbasis hash, jadi
    pembagiannya tetap sama walau data baru terus bertambah."""
    ember = int(hashlib.sha1(f"berita-{berita_id}".encode()).hexdigest(), 16) % 100
    if ember < 70:
        return "latih"
    if ember < 85:
        return "validasi"
    return "uji"


@dataclass(frozen=True)
class Contoh:
    berita_id: int
    kode: str
    teks: str
    target: str
    sentimen: Sentimen
    bagian: str


def muat_label_emas(session: Session) -> list[Contoh]:
    """Semua label buatan manusia (anotasi maupun koreksi analis di dasbor).
    Bila satu pasangan berita-emiten punya beberapa, yang terbaru dipakai."""
    baris = session.execute(
        select(LabelSentimen, Berita, Emiten, BeritaEmiten.kutipan)
        .join(Berita, Berita.id == LabelSentimen.berita_id)
        .join(Emiten, Emiten.id == LabelSentimen.emiten_id)
        .outerjoin(
            BeritaEmiten,
            (BeritaEmiten.berita_id == LabelSentimen.berita_id)
            & (BeritaEmiten.emiten_id == LabelSentimen.emiten_id),
        )
        .where(LabelSentimen.asal == AsalLabel.ANALIS)
        .order_by(LabelSentimen.dibuat_pada)
    ).all()
    terbaru: dict[tuple[int, int], Contoh] = {}
    for label, berita, emiten, kutipan in baris:
        terbaru[(berita.id, emiten.id)] = Contoh(
            berita_id=berita.id,
            kode=emiten.kode,
            teks=teks_utama(berita.judul, berita.ringkasan),
            target=teks_target(emiten.kode, emiten.nama, kutipan),
            sentimen=label.sentimen,
            bagian=bagian_data(berita.id),
        )
    return sorted(terbaru.values(), key=lambda c: (c.berita_id, c.kode))
