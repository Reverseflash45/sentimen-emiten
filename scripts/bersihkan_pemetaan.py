"""Menghapus pemetaan hasil pengayaan agar bisa dibangun ulang.

    python -m scripts.bersihkan_pemetaan --lihat      # lihat apa yang akan dihapus
    python -m scripts.bersihkan_pemetaan --hapus

Dipakai setelah penyaring atau pencocok diperbaiki: pemetaan lama dibuat oleh
aturan yang sudah diketahui keliru, jadi membiarkannya berarti menyimpan
kesalahan yang sudah disadari.

Hanya pemetaan yang berasal dari pengayaan badan artikel yang dihapus —
dikenali dari tabel `pengayaan_berita`. Pemetaan dari judul dan ringkasan RSS
tidak disentuh. Label ANALIS tidak pernah dihapus tanpa izin tegas: koreksi
manusia adalah data yang tidak bisa dibuat ulang oleh proses otomatis.
"""

from __future__ import annotations

import argparse

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import (
    AsalLabel,
    Berita,
    BeritaEmiten,
    Emiten,
    LabelSentimen,
    PengayaanBerita,
)


def main() -> None:
    p = argparse.ArgumentParser(description="Bersihkan pemetaan hasil pengayaan")
    kelompok = p.add_mutually_exclusive_group(required=True)
    kelompok.add_argument("--lihat", action="store_true", help="tampilkan saja, jangan hapus")
    kelompok.add_argument("--hapus", action="store_true", help="hapus sungguhan")
    p.add_argument("--paksa", action="store_true",
                   help="ikut hapus walaupun ada koreksi analis yang akan hilang")
    a = p.parse_args()

    with SessionLocal() as session:
        id_diperkaya = [
            row for row in session.scalars(select(PengayaanBerita.berita_id))
        ]
        if not id_diperkaya:
            print("Belum ada pemetaan hasil pengayaan.")
            return

        kaitan = list(
            session.execute(
                select(BeritaEmiten, Berita, Emiten)
                .join(Berita, Berita.id == BeritaEmiten.berita_id)
                .join(Emiten, Emiten.id == BeritaEmiten.emiten_id)
                .where(BeritaEmiten.berita_id.in_(id_diperkaya))
            ).all()
        )
        pasangan = {(k.berita_id, k.emiten_id) for k, _, _ in kaitan}

        analis = [
            l for l in session.scalars(
                select(LabelSentimen).where(LabelSentimen.asal == AsalLabel.ANALIS)
            )
            if (l.berita_id, l.emiten_id) in pasangan
        ]

        print(f"Berita yang pernah diperkaya : {len(id_diperkaya)}")
        print(f"Kaitan emiten yang akan dihapus : {len(kaitan)}")
        print(f"Koreksi analis yang ikut hilang : {len(analis)}")

        if a.lihat:
            for k, berita, emiten in kaitan[:30]:
                print(f"  [{emiten.kode}] {berita.judul[:70]}")
            if len(kaitan) > 30:
                print(f"  ... {len(kaitan) - 30} lainnya")
            print("\nJalankan dengan --hapus untuk menghapus sungguhan.")
            return

        if analis and not a.paksa:
            print(
                "\nDibatalkan. Ada koreksi analis yang akan ikut terhapus, dan\n"
                "koreksi manusia tidak bisa dibuat ulang oleh proses otomatis.\n"
                "Tambahkan --paksa kalau memang itu yang diinginkan."
            )
            return

        # label dihapus lebih dulu supaya tidak ada label menggantung tanpa kaitan
        for berita_id, emiten_id in pasangan:
            session.execute(
                delete(LabelSentimen).where(
                    LabelSentimen.berita_id == berita_id,
                    LabelSentimen.emiten_id == emiten_id,
                )
            )
        session.execute(
            delete(BeritaEmiten).where(BeritaEmiten.berita_id.in_(id_diperkaya))
        )
        session.execute(delete(PengayaanBerita))

        for berita in session.scalars(select(Berita).where(Berita.id.in_(id_diperkaya))):
            berita.sudah_diklasifikasi = False
        session.commit()

    print("\nSelesai. Bangun ulang dengan:")
    print("  python -m scripts.petakan_ulang --semua")
    print("  python -m scripts.klasifikasi")


if __name__ == "__main__":
    main()
