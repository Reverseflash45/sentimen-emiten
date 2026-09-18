"""Pengayaan pemetaan: mengambil halaman artikel untuk menemukan emiten.

Kenapa perlu: ringkasan RSS panjangnya hanya sekitar dua kalimat, dan judul
berita finansial sering tidak menyebut emiten mana pun ("Daftar Lengkap 8 Blok
Migas Dilelang"). Nama atau kode emiten baru muncul di badan artikel. Tanpa
langkah ini sebagian besar berita berakhir tanpa emiten, dan agregasi harian
jadi kosong padahal beritanya ada.

Yang tetap dipatuhi:
- Isi artikel TIDAK disimpan (NF-09). Halaman diambil, dipakai untuk mencocokkan,
  lalu dibuang. Yang tersimpan hanya kutipan pendek di sekitar kecocokan —
  potongan yang memang dibutuhkan analis untuk memeriksa pemetaannya benar.
- robots.txt diperiksa lebih dulu, dan jeda antar permintaan mengikuti
  crawl-delay portal (fail-closed, sama seperti pengambilan RSS).
- Jumlah halaman per siklus dibatasi, supaya satu portal tidak dihujani
  permintaan.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.ingest import robots
from app.ingest.cleaner import bersihkan
from app.ingest.matcher import cocokkan
from app.models import Berita, BeritaEmiten, Emiten, PengayaanBerita

# tag yang isinya bukan artikel
TAG_BUANG = ("script", "style", "nav", "header", "footer", "aside", "form", "iframe")

# Blok "berita terkait", "populer", dan sejenisnya memuat JUDUL ARTIKEL LAIN.
# Kalau ikut terbaca, berita perang bisa terpetakan ke emiten tambang hanya
# karena ada tautan rekomendasi di sampingnya. Presisi lebih penting daripada
# jangkauan di sini: satu pemetaan salah menyuntikkan sentimen keliru ke skor
# sebuah emiten, dan kesalahan itu tidak terlihat lagi setelah teragregasi.
POLA_BUKAN_ARTIKEL = re.compile(
    r"terkait|populer|rekomendasi|baca[-_ ]?juga|lihat[-_ ]?juga|simak[-_ ]?juga|"
    r"related|trending|sidebar|widget|komentar|newsletter|langganan|"
    r"topik|tagar|breadcrumb|share|iklan|promo|banner|footer|headline",
    re.IGNORECASE,
)

# Sisipan "Baca juga: <judul artikel lain>" di tengah badan artikel.
#
# Sebagian portal menaruhnya di paragraf sendiri, sebagian menyisipkannya di
# tengah kalimat: "...RDG 18-19 Agustus 2026. Baca Juga: XLSMART (EXCL) Pasang
# Strategi...". Bentuk kedua inilah yang memetakan berita kurs rupiah ke EXCL.
# Karena itu sisipan dipotong dari posisi penandanya sampai akhir paragraf,
# bukan hanya dibuang kalau paragrafnya diawali penanda itu.
PEMBUKA_SISIPAN = re.compile(
    r"^\s*(baca|lihat|simak|tonton)\s+(juga|selengkapnya)\s*[:\-–—]?", re.IGNORECASE
)
SISIPAN_TENGAH = re.compile(
    r"\b(baca|lihat|simak|tonton)\s+(juga|selengkapnya)\s*[:\-–—].*$",
    re.IGNORECASE | re.DOTALL,
)

# Paragraf pendek nyaris selalu teaser atau keterangan gambar, bukan kalimat
# artikel. Ambangnya rendah supaya kalimat pendek yang sah tetap ikut.
MIN_PANJANG_PARAGRAF = 40

# batas teks yang dipakai untuk pencocokan; artikel berita jarang lebih panjang
# dari ini, dan membatasinya menjaga waktu proses tetap wajar
MAKS_KARAKTER = 20_000

# Satu artikel yang lambat tidak boleh menyandera seluruh siklus. Portal yang
# butuh lebih dari ini biasanya memang sedang bermasalah.
TIMEOUT = 12.0


@dataclass
class HasilPengayaan:
    diperiksa: int = 0
    diambil: int = 0
    terpetakan: int = 0
    emiten_baru: int = 0
    dilewati_robots: int = 0
    sisa: int = 0
    gagal: list[str] = field(default_factory=list)

    def ringkas(self) -> str:
        return (
            f"diperiksa={self.diperiksa} diambil={self.diambil} "
            f"berita_terpetakan={self.terpetakan} kaitan_baru={self.emiten_baru} "
            f"dilewati_robots={self.dilewati_robots} gagal={len(self.gagal)} "
            f"sisa_belum_dicoba={self.sisa}"
        )


def _blok_bukan_artikel(tag) -> bool:
    """Apakah sebuah elemen kemungkinan blok rekomendasi, bukan isi artikel."""
    # Membuang satu elemen ikut membuang anak-anaknya, padahal anak itu masih
    # ada di daftar yang sedang ditelusuri. Elemen yang sudah terbuang dilewati.
    if getattr(tag, "attrs", None) is None:
        return False
    petunjuk = " ".join(
        [
            " ".join(tag.get("class") or []),
            tag.get("id") or "",
            tag.get("data-testid") or "",
        ]
    )
    return bool(petunjuk.strip()) and bool(POLA_BUKAN_ARTIKEL.search(petunjuk))


def _teks_paragraf(p) -> str:
    """Teks satu paragraf, dengan sisipan rekomendasi dipotong.

    Mengembalikan string kosong bila paragraf itu seluruhnya bukan isi artikel.
    """
    teks = p.get_text(" ", strip=True)
    if PEMBUKA_SISIPAN.match(teks):
        return ""
    # paragraf yang isinya didominasi tautan hampir selalu daftar judul lain
    panjang_tautan = sum(len(a.get_text(" ", strip=True)) for a in p.find_all("a"))
    if teks and panjang_tautan > 0.6 * len(teks):
        return ""
    teks = SISIPAN_TENGAH.sub("", teks).strip()
    if len(teks) < MIN_PANJANG_PARAGRAF:
        return ""
    return teks


def ekstrak_teks(html: str) -> str:
    """Mengambil teks yang kira-kira merupakan isi artikel.

    Tidak memakai pustaka ekstraksi khusus; cukup tiga saringan berlapis:
    buang tag non-artikel, buang blok yang kelas atau id-nya menandakan
    rekomendasi, lalu buang paragraf yang bukan kalimat artikel. Hasilnya tidak
    sempurna, tapi untuk mencari nama dan kode emiten tidak perlu sempurna —
    yang penting nama emiten lain tidak ikut terbaca.
    """
    if not html:
        return ""
    sup = BeautifulSoup(html, "lxml")

    for tag in sup(list(TAG_BUANG)):
        tag.decompose()

    for tag in list(sup.find_all(["div", "section", "ul", "ol", "li", "span"])):
        if _blok_bukan_artikel(tag):
            tag.decompose()

    semua_p = sup.find_all("p")
    paragraf = [teks for teks in (_teks_paragraf(p) for p in semua_p) if teks]

    if paragraf:
        teks = " ".join(paragraf)
    elif semua_p:
        # Ada paragraf tapi semuanya tersaring — itu jawaban, bukan kegagalan.
        # Jatuh ke seluruh teks halaman di sini justru mengembalikan persis
        # bagian yang baru saja sengaja dibuang.
        teks = ""
    else:
        # halaman tanpa <p> sama sekali (sebagian portal memakai <div>) —
        # pakai seluruh teks; blok rekomendasi sudah terbuang di atas
        teks = sup.get_text(" ", strip=True)
    return bersihkan(teks)[:MAKS_KARAKTER]


def ambil_halaman(url: str, klien: httpx.Client | None = None) -> str | None:
    """Mengambil satu halaman artikel. None bila robots.txt tidak mengizinkan."""
    if not robots.boleh_diambil(url):
        return None
    kepala = {"User-Agent": settings.user_agent}
    if klien is not None:
        r = klien.get(url, headers=kepala, timeout=TIMEOUT)
    else:
        r = httpx.get(url, headers=kepala, timeout=TIMEOUT, follow_redirects=True)
    r.raise_for_status()
    return r.text


def catat_pengayaan(
    session: Session, berita_id: int, jumlah_kaitan: int, berhasil: bool
) -> None:
    """Menandai bahwa berita ini sudah pernah dicoba diperkaya."""
    ada = session.scalar(
        select(PengayaanBerita).where(PengayaanBerita.berita_id == berita_id)
    )
    if ada is not None:
        ada.dicoba_pada = datetime.now(timezone.utc)
        ada.jumlah_kaitan = jumlah_kaitan
        ada.berhasil_diambil = berhasil
        return
    session.add(
        PengayaanBerita(
            berita_id=berita_id, jumlah_kaitan=jumlah_kaitan, berhasil_diambil=berhasil
        )
    )


def perkaya_sampai_habis(
    session: Session,
    batas_per_putaran: int | None = None,
    klien: httpx.Client | None = None,
    jeda: bool = True,
    lapor: Callable[[str], None] | None = None,
    ulangi: bool = False,
    maks_putaran: int = 50,
) -> HasilPengayaan:
    """Menjalankan pengayaan berulang sampai tidak ada sisa.

    Batas per putaran tetap dihormati supaya pola permintaannya tidak berubah;
    yang hilang hanya keharusan mengetik perintah yang sama berkali-kali.
    `maks_putaran` menjaga agar kesalahan logika tidak berubah menjadi
    perulangan tanpa henti.
    """
    total = HasilPengayaan()
    for _ in range(maks_putaran):
        bagian = perkaya_pemetaan(
            session,
            batas=batas_per_putaran,
            klien=klien,
            jeda=jeda,
            lapor=lapor,
            # pengulangan paksa hanya berlaku pada putaran pertama; kalau tidak,
            # artikel yang sama akan diambil ulang tanpa henti
            ulangi=ulangi and total.diperiksa == 0,
        )
        total.diperiksa += bagian.diperiksa
        total.diambil += bagian.diambil
        total.terpetakan += bagian.terpetakan
        total.emiten_baru += bagian.emiten_baru
        total.dilewati_robots += bagian.dilewati_robots
        total.gagal.extend(bagian.gagal)
        total.sisa = bagian.sisa
        if bagian.diperiksa == 0 or bagian.sisa == 0:
            break
    return total


def perkaya_pemetaan(
    session: Session,
    batas: int | None = None,
    klien: httpx.Client | None = None,
    jeda: bool = True,
    lapor: Callable[[str], None] | None = None,
    ulangi: bool = False,
) -> HasilPengayaan:
    """Mencari emiten pada badan artikel untuk berita yang belum terpetakan.

    Hanya berita yang belum punya kaitan emiten yang diproses — berita yang
    sudah terpetakan dari judul tidak perlu diambil ulang.

    Berita yang halamannya sudah pernah diambil tidak diambil lagi, walaupun
    hasilnya nihil — hasil nihil pun sebuah jawaban, dan mengulangnya hanya
    membebani portal. `ulangi=True` memaksa pengambilan ulang; itu berguna
    setelah daftar emiten diperluas, karena artikel yang tadinya nihil bisa jadi
    cocok dengan emiten yang baru ditambahkan.

    `lapor` dipanggil sekali per artikel. Proses ini mengambil puluhan halaman
    dan bisa berjalan beberapa menit; tanpa laporan jalan, tidak ada cara
    membedakan proses yang lambat dari proses yang menggantung.
    """
    def catat(pesan: str) -> None:
        if lapor is not None:
            lapor(pesan)
    hasil = HasilPengayaan()
    batas = batas or settings.maks_perkaya_per_siklus

    daftar_emiten: dict[str, list[str]] = {}
    for e in session.scalars(select(Emiten).where(Emiten.aktif.is_(True))):
        daftar_emiten[e.kode] = [e.nama, *e.daftar_alias()]
    peta_id = {e.kode: e.id for e in session.scalars(select(Emiten))}

    sudah_terpetakan = select(BeritaEmiten.berita_id)
    kueri = select(Berita).where(Berita.id.not_in(sudah_terpetakan))
    if not ulangi:
        # halaman yang berhasil diambil tidak perlu diambil lagi; yang gagal
        # diambil masih layak dicoba (portal bisa sedang bermasalah sesaat)
        sudah_dicoba = select(PengayaanBerita.berita_id).where(
            PengayaanBerita.berhasil_diambil.is_(True)
        )
        kueri = kueri.where(Berita.id.not_in(sudah_dicoba))

    belum = len(list(session.scalars(kueri)))
    daftar = list(session.scalars(kueri.order_by(Berita.id.desc()).limit(batas)))
    total = len(daftar)
    hasil.sisa = max(0, belum - total)
    catat(
        f"{belum} berita belum diperkaya; memproses {total} "
        f"(sisa {hasil.sisa} untuk siklus berikutnya)"
    )

    for nomor, berita in enumerate(daftar, start=1):
        hasil.diperiksa += 1
        awalan = f"[{nomor}/{total}]"
        potong_judul = berita.judul[:54]

        try:
            html = ambil_halaman(berita.url, klien)
        except Exception as e:  # noqa: BLE001 — satu artikel gagal, lanjut
            hasil.gagal.append(f"{berita.id}: {type(e).__name__}: {e}")
            catat(f"{awalan} gagal  {potong_judul} — {type(e).__name__}")
            catat_pengayaan(session, berita.id, 0, berhasil=False)
            session.commit()
            continue

        if html is None:
            hasil.dilewati_robots += 1
            catat(f"{awalan} robots {potong_judul}")
            catat_pengayaan(session, berita.id, 0, berhasil=False)
            session.commit()
            continue

        hasil.diambil += 1
        teks = ekstrak_teks(html)
        # judul tetap disertakan: kadang nama emiten hanya ada di judul versi web
        kecocokan = cocokkan(f"{berita.judul}. {teks}", daftar_emiten)
        if not kecocokan:
            catat(f"{awalan} kosong {potong_judul}")
            catat_pengayaan(session, berita.id, 0, berhasil=True)
            session.commit()
            continue

        hasil.terpetakan += 1
        catat(f"{awalan} cocok  {', '.join(k.kode for k in kecocokan):20} {potong_judul}")
        for k in kecocokan:
            emiten_id = peta_id.get(k.kode)
            if emiten_id is None:
                continue
            session.add(
                BeritaEmiten(
                    berita_id=berita.id,
                    emiten_id=emiten_id,
                    cara_cocok=k.cara,
                    kutipan=k.kutipan,
                )
            )
            hasil.emiten_baru += 1
        # berita perlu dilabeli ulang karena sekarang punya emiten
        berita.sudah_diklasifikasi = False
        catat_pengayaan(session, berita.id, len(kecocokan), berhasil=True)
        session.commit()

        if jeda:
            time.sleep(robots.jeda_crawl(berita.url))

    session.commit()
    return hasil
