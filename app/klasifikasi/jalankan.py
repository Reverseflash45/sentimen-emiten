"""Menjalankan pelabelan sentimen atas berita yang belum diklasifikasi.

Label dibuat per pasangan berita-emiten, bukan per berita. Satu artikel bisa
menyebut dua emiten dengan nada berbeda ("A untung setelah mengambil alih
pangsa B"), jadi label yang benar adalah label untuk emiten tertentu.

Pada baseline leksikon teks yang dinilai masih sama untuk semua emiten dalam
satu berita; pemisahan per emiten disiapkan sejak sekarang supaya model
berbasis konteks nanti bisa memakai kutipan spesifik tanpa mengubah skema.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.klasifikasi.basis import Pengklasifikasi
from app.klasifikasi.dataset import teks_target, teks_utama
from app.models import AsalLabel, Berita, BeritaEmiten, LabelSentimen


@dataclass
class HasilKlasifikasi:
    berita_diproses: int = 0
    label_dibuat: int = 0
    dilewati_tanpa_emiten: int = 0

    def ringkas(self) -> str:
        return (
            f"berita={self.berita_diproses} label={self.label_dibuat} "
            f"tanpa_emiten={self.dilewati_tanpa_emiten}"
        )


def teks_untuk_model(berita: Berita) -> str:
    return teks_utama(berita.judul, berita.ringkasan)


def label_sudah_ada(session: Session, berita_id: int, emiten_id: int, versi: str) -> bool:
    return session.scalar(
        select(LabelSentimen.id).where(
            LabelSentimen.berita_id == berita_id,
            LabelSentimen.emiten_id == emiten_id,
            LabelSentimen.asal == AsalLabel.MODEL,
            LabelSentimen.versi_model == versi,
        )
    ) is not None


def klasifikasi_berita_baru(
    session: Session,
    pengklasifikasi: Pengklasifikasi,
    batas: int | None = None,
    ulangi: bool = False,
) -> HasilKlasifikasi:
    """Melabeli berita yang belum punya label dari versi model ini.

    `ulangi=True` memproses ulang seluruh berita — dipakai saat versi model
    berganti. Label lama tidak dihapus supaya perbandingan antarversi tetap
    bisa dilakukan.
    """
    hasil = HasilKlasifikasi()

    kueri = select(Berita)
    if not ulangi:
        kueri = kueri.where(Berita.sudah_diklasifikasi.is_(False))
    kueri = kueri.order_by(Berita.id)
    if batas:
        kueri = kueri.limit(batas)

    for berita in session.scalars(kueri):
        kaitan = list(
            session.scalars(select(BeritaEmiten).where(BeritaEmiten.berita_id == berita.id))
        )
        hasil.berita_diproses += 1
        if not kaitan:
            hasil.dilewati_tanpa_emiten += 1
            berita.sudah_diklasifikasi = True
            continue

        belum = [k for k in kaitan if not label_sudah_ada(session, berita.id, k.emiten_id, pengklasifikasi.versi)]
        teks = teks_untuk_model(berita)
        if pengklasifikasi.per_emiten:
            # satu prediksi per emiten: nada berita bisa berbeda antar-emiten
            semua_prediksi = pengklasifikasi.prediksi_emiten_banyak(
                [(teks, teks_target(k.emiten.kode, k.emiten.nama, k.kutipan)) for k in belum]
            )
        else:
            semua_prediksi = [pengklasifikasi.prediksi(teks)] * len(belum) if belum else []
        for k, prediksi in zip(belum, semua_prediksi):
            session.add(
                LabelSentimen(
                    berita_id=berita.id,
                    emiten_id=k.emiten_id,
                    sentimen=prediksi.sentimen,
                    keyakinan=prediksi.keyakinan,
                    asal=AsalLabel.MODEL,
                    versi_model=pengklasifikasi.versi,
                )
            )
            hasil.label_dibuat += 1
        berita.sudah_diklasifikasi = True

    session.commit()
    return hasil
