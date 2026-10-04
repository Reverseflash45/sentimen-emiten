"""Notifikasi perubahan sentimen emiten di watchlist (SRS FR-6, UC-02).

Aturannya sengaja sederhana supaya bisa dijelaskan dalam satu kalimat:

    rata-rata skor 7 hari terakhir dibanding 7 hari sebelumnya; bila selisihnya
    mencapai ambang yang dipilih pengguna, kirim peringatan.

Tiga pengaman mencegah peringatan yang menyesatkan atau berulang:
  - kedua jendela harus punya minimal MIN_BERITA berita — satu berita saja
    bisa menggeser rata-rata sejauh apa pun, dan itu bukan "perubahan sentimen";
  - rata-rata ditimbang jumlah berita per hari, sama seperti grafik di dasbor;
  - emiten yang sudah diperingatkan tidak diperingatkan lagi selama JENDELA hari,
    karena pergeseran yang sama akan tetap terdeteksi di siklus berikutnya.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analitik.agregasi import SkorHarian, hitung_skor_harian
from app.models import Emiten, Notifikasi, Pengguna, Watchlist

JENDELA = 7
MIN_BERITA = 2


@dataclass(frozen=True)
class Perubahan:
    skor_sebelum: float
    skor_sesudah: float
    berita_sebelum: int
    berita_sesudah: int

    @property
    def selisih(self) -> float:
        return self.skor_sesudah - self.skor_sebelum


def rerata(skor: list[SkorHarian]) -> tuple[float | None, int]:
    """Rata-rata skor harian ditimbang jumlah berita, beserta jumlah beritanya."""
    n = sum(s.jumlah_berita for s in skor)
    if not n:
        return None, 0
    return sum(s.skor * s.jumlah_berita for s in skor) / n, n


def ukur_perubahan(session: Session, kode: str, hari_ini: date) -> Perubahan | None:
    """None bila salah satu jendela belum punya cukup berita untuk dibandingkan."""
    sesudah, n1 = rerata(hitung_skor_harian(session, kode, hari_ini - timedelta(days=JENDELA - 1), hari_ini))
    sebelum, n0 = rerata(hitung_skor_harian(
        session, kode, hari_ini - timedelta(days=2 * JENDELA - 1), hari_ini - timedelta(days=JENDELA)
    ))
    if sesudah is None or sebelum is None or n0 < MIN_BERITA or n1 < MIN_BERITA:
        return None
    return Perubahan(round(sebelum, 4), round(sesudah, 4), n0, n1)


def _angka(v: float) -> str:
    return f"{v:+.2f}".replace("-", "−").replace(".", ",")


def susun_pesan(kode: str, p: Perubahan) -> str:
    arah = "naik" if p.selisih > 0 else "turun"
    return (f"Sentimen {kode} {arah} dari {_angka(p.skor_sebelum)} menjadi {_angka(p.skor_sesudah)} "
            f"(rata-rata {JENDELA} hari terakhir dibanding {JENDELA} hari sebelumnya, "
            f"{p.berita_sesudah} berita).")


def periksa_watchlist(session: Session, hari_ini: date | None = None) -> list[Notifikasi]:
    """Membuat notifikasi untuk setiap entri watchlist yang perubahannya
    melewati ambang. Aman dijalankan berkali-kali sehari. Tidak commit."""
    hari_ini = hari_ini or date.today()
    entri = session.execute(
        select(Watchlist, Emiten)
        .join(Emiten, Emiten.id == Watchlist.emiten_id)
        .join(Pengguna, Pengguna.id == Watchlist.pengguna_id)
        .where(Pengguna.aktif.is_(True), Emiten.aktif.is_(True))
    ).all()

    perubahan: dict[str, Perubahan | None] = {}  # satu hitungan per emiten
    baru: list[Notifikasi] = []
    for w, emiten in entri:
        if emiten.kode not in perubahan:
            perubahan[emiten.kode] = ukur_perubahan(session, emiten.kode, hari_ini)
        p = perubahan[emiten.kode]
        if p is None or abs(p.selisih) < w.ambang:
            continue
        sudah = session.scalar(
            select(Notifikasi.id).where(
                Notifikasi.pengguna_id == w.pengguna_id,
                Notifikasi.emiten_id == emiten.id,
                Notifikasi.tanggal > hari_ini - timedelta(days=JENDELA),
            )
        )
        if sudah is not None:
            continue
        n = Notifikasi(
            pengguna_id=w.pengguna_id, emiten_id=emiten.id, tanggal=hari_ini,
            skor_sebelum=p.skor_sebelum, skor_sesudah=p.skor_sesudah,
            jumlah_berita=p.berita_sesudah, pesan=susun_pesan(emiten.kode, p),
        )
        session.add(n)
        baru.append(n)
    return baru
