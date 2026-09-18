"""Agregasi skor sentimen harian per emiten (SRS 10.1 butir 6).

Aturan pembobotan:
- Label analis selalu menang atas label model untuk berita yang sama. Koreksi
  manusia adalah kebenaran acuan, bukan sekadar suara tambahan.
- Label model ditimbang dengan nilai keyakinannya. Berita yang modelnya ragu
  tidak boleh menggeser skor sekuat berita yang jelas.
- Portal tak terverifikasi ditimbang lebih rendah. Ini yang membedakan sistem
  ini dari sekadar menghitung rata-rata: rumor dari sumber tak jelas tidak
  diperlakukan setara dengan berita dari portal terverifikasi.
- Berita yang menyebut banyak emiten sekaligus ditimbang lebih rendah untuk
  tiap emitennya. Artikel rekap pasar seperti "IHSG Masih Cenderung Bearish"
  menyebut lima emiten dalam satu tulisan; nada artikel itu tentang pasar
  secara keseluruhan, bukan tentang satu emiten tertentu. Memberi bobot penuh
  ke kelimanya akan membuat satu artikel makro menggeser skor lima emiten
  sekaligus, dan artikel semacam itu terbit tiap hari bursa.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AsalLabel,
    Berita,
    BeritaEmiten,
    Emiten,
    Kredibilitas,
    LabelSentimen,
    Sentimen,
    SumberBerita,
)

NILAI_SENTIMEN: dict[Sentimen, float] = {
    Sentimen.POSITIF: 1.0,
    Sentimen.NETRAL: 0.0,
    Sentimen.NEGATIF: -1.0,
}

BOBOT_KREDIBILITAS: dict[Kredibilitas, float] = {
    Kredibilitas.TERVERIFIKASI_DEWAN_PERS: 1.0,
    Kredibilitas.PORTAL_UMUM: 0.7,
    Kredibilitas.TIDAK_TERVERIFIKASI: 0.4,
}


def bobot_dilusi(jumlah_emiten: int) -> float:
    """Bobot sebuah berita untuk satu emiten, bila berita itu menyebut beberapa.

    Pembagian rata (1/n) dipilih, bukan 1/sqrt(n) yang lebih landai, karena
    penafsirannya jelas: satu artikel menyumbang satu satuan bobot, dibagi
    kepada emiten yang dibahasnya. Artikel yang benar-benar tentang satu emiten
    tetap berbobot penuh.
    """
    return 1.0 / max(1, jumlah_emiten)


@dataclass
class SkorHarian:
    tanggal: date
    skor: float           # -1 sampai +1
    jumlah_berita: int
    jumlah_positif: int
    jumlah_netral: int
    jumlah_negatif: int


def _label_terpilih(labels: list[LabelSentimen]) -> LabelSentimen | None:
    """Memilih satu label untuk satu pasangan berita-emiten.

    Analis menang; di antara label model, yang terbaru yang dipakai.
    """
    if not labels:
        return None
    analis = [l for l in labels if l.asal == AsalLabel.ANALIS]
    kandidat = analis or labels
    return max(kandidat, key=lambda l: l.dibuat_pada)


def hitung_skor_harian(
    session: Session,
    kode_emiten: str,
    mulai: date,
    sampai: date,
    maks_emiten_per_berita: int | None = None,
) -> list[SkorHarian]:
    """Menghitung deret waktu skor sentimen harian satu emiten.

    `maks_emiten_per_berita` membuang berita yang menyebut lebih banyak emiten
    daripada itu. Gunanya bukan untuk dipakai sebagai setelan tetap, melainkan
    untuk uji kepekaan: bandingkan hasil dengan dan tanpa artikel rekap pasar.

    Pada data uji nyata, sekitar 70% pemetaan berasal dari artikel rekap seperti
    "ANALIS MARKET", "Saham Bank Jadi Pemberat", atau "Asing Jual Saham Tambang"
    — artikel yang menyebut banyak emiten sekaligus dan nadanya tentang indeks,
    bukan tentang satu perusahaan. Kalau korelasi yang dihitung hanya bertahan
    ketika artikel semacam itu diikutkan, yang sebenarnya terukur adalah
    pergerakan IHSG, bukan sentimen per emiten. Itu temuan yang harus dilaporkan,
    bukan disembunyikan dengan memilih setelan yang hasilnya paling bagus.
    """
    emiten = session.scalar(select(Emiten).where(Emiten.kode == kode_emiten.upper()))
    if emiten is None:
        return []

    baris = session.execute(
        select(Berita, SumberBerita)
        .join(BeritaEmiten, BeritaEmiten.berita_id == Berita.id)
        .join(SumberBerita, SumberBerita.id == Berita.sumber_id)
        .where(BeritaEmiten.emiten_id == emiten.id)
    ).all()

    # berapa emiten yang dibahas tiap berita — dipakai untuk bobot dilusi
    id_berita = [b.id for b, _ in baris]
    jumlah_emiten_per_berita: dict[int, int] = {}
    if id_berita:
        for berita_id, jumlah in session.execute(
            select(BeritaEmiten.berita_id, func.count(BeritaEmiten.id))
            .where(BeritaEmiten.berita_id.in_(id_berita))
            .group_by(BeritaEmiten.berita_id)
        ).all():
            jumlah_emiten_per_berita[berita_id] = jumlah

    # kumpulkan label per berita lebih dulu, supaya tidak query berulang
    label_per_berita: dict[int, list[LabelSentimen]] = defaultdict(list)
    for l in session.scalars(
        select(LabelSentimen).where(LabelSentimen.emiten_id == emiten.id)
    ):
        label_per_berita[l.berita_id].append(l)

    harian: dict[date, list[tuple[float, float, Sentimen]]] = defaultdict(list)

    for berita, sumber in baris:
        waktu: datetime | None = berita.terbit_pada or berita.diambil_pada
        if waktu is None:
            continue
        tgl = waktu.date()
        if not (mulai <= tgl <= sampai):
            continue

        jumlah_emiten = jumlah_emiten_per_berita.get(berita.id, 1)
        if maks_emiten_per_berita is not None and jumlah_emiten > maks_emiten_per_berita:
            continue

        label = _label_terpilih(label_per_berita.get(berita.id, []))
        if label is None:
            continue  # belum diklasifikasi — tidak dihitung

        bobot_sumber = BOBOT_KREDIBILITAS.get(sumber.kredibilitas, 0.5)
        # koreksi analis dianggap pasti
        keyakinan = 1.0 if label.asal == AsalLabel.ANALIS else max(0.0, min(1.0, label.keyakinan))
        dilusi = bobot_dilusi(jumlah_emiten)
        bobot = bobot_sumber * keyakinan * dilusi
        harian[tgl].append((NILAI_SENTIMEN[label.sentimen], bobot, label.sentimen))

    hasil: list[SkorHarian] = []
    for tgl in sorted(harian):
        entri = harian[tgl]
        total_bobot = sum(b for _, b, _ in entri)
        skor = sum(n * b for n, b, _ in entri) / total_bobot if total_bobot else 0.0
        hasil.append(
            SkorHarian(
                tanggal=tgl,
                skor=round(skor, 4),
                jumlah_berita=len(entri),
                jumlah_positif=sum(1 for _, _, s in entri if s == Sentimen.POSITIF),
                jumlah_netral=sum(1 for _, _, s in entri if s == Sentimen.NETRAL),
                jumlah_negatif=sum(1 for _, _, s in entri if s == Sentimen.NEGATIF),
            )
        )
    return hasil
