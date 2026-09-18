"""Skema respons API (pydantic v2).

Dipisah dari model basis data supaya bentuk respons tidak ikut berubah setiap
kali skema tabel disesuaikan — dan supaya kolom internal tidak ikut terekspos.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import AsalLabel, Kredibilitas, Peran, Sentimen, StatusVerifikasi


class EmitenRingkas(BaseModel):
    kode: str
    nama: str
    sektor: str | None = None


class EmitenDetail(EmitenRingkas):
    alias: list[str] = Field(default_factory=list)
    jumlah_berita: int = 0
    harga_terakhir: float | None = None
    tanggal_harga_terakhir: date | None = None


class SumberRingkas(BaseModel):
    id: int
    nama: str
    domain: str
    kredibilitas: Kredibilitas
    aktif: bool


class LabelRingkas(BaseModel):
    sentimen: Sentimen
    keyakinan: float
    asal: AsalLabel
    versi_model: str


class BeritaRingkas(BaseModel):
    id: int
    judul: str
    url: str
    sumber: str
    kredibilitas: Kredibilitas
    terbit_pada: datetime | None = None
    status_verifikasi: StatusVerifikasi
    emiten: list[str] = Field(default_factory=list)
    label: LabelRingkas | None = None


class TitikSentimen(BaseModel):
    tanggal: date
    skor: float
    jumlah_berita: int
    jumlah_positif: int
    jumlah_netral: int
    jumlah_negatif: int


class DeretSentimen(BaseModel):
    kode: str
    mulai: date
    sampai: date
    titik: list[TitikSentimen]


class TitikHarga(BaseModel):
    tanggal: date
    penutupan: float | None = None
    volume: int | None = None


class DeretHarga(BaseModel):
    kode: str
    mulai: date
    sampai: date
    titik: list[TitikHarga]


class Korelasi(BaseModel):
    metode: str
    koefisien: float
    n: int
    kekuatan: str


class HasilKorelasi(BaseModel):
    kode: str
    mulai: date
    sampai: date
    lag: int
    hari_beririsan: int
    maks_emiten_per_berita: int | None = None
    pearson: Korelasi | None = None
    spearman: Korelasi | None = None
    catatan: str | None = None
    # ditampilkan apa adanya di UI — sistem tidak memprediksi harga (SRS 10.3)
    peringatan: str = (
        "Korelasi bukan sebab-akibat. Angka ini menggambarkan hubungan pada "
        "rentang yang dipilih saja dan bukan prediksi harga."
    )


class KoreksiLabel(BaseModel):
    """Koreksi manual analis (SRS UC-05)."""

    kode_emiten: str
    sentimen: Sentimen
    catatan: str | None = None


class UbahVerifikasi(BaseModel):
    status: StatusVerifikasi


class Ringkasan(BaseModel):
    jumlah_emiten: int
    jumlah_sumber: int
    jumlah_berita: int
    jumlah_berlabel: int
    jumlah_belum_diklasifikasi: int
    berita_terakhir: datetime | None = None
    emiten_teraktif: list[dict] = Field(default_factory=list)


class PengumumanRingkas(BaseModel):
    id: int
    judul: str
    url: str
    terbit_pada: datetime | None = None


class JejakVerifikasi(BaseModel):
    """Alasan sebuah berita diberi status verifikasi tertentu (SRS UC-04)."""

    status: StatusVerifikasi
    kemiripan: float
    alasan: str
    otomatis: bool
    dibuat_pada: datetime
    pengumuman: PengumumanRingkas | None = None


class Masuk(BaseModel):
    email: str
    kata_sandi: str


class Token(BaseModel):
    token: str
    tipe: str = "bearer"
    berlaku_jam: int


class PenggunaRingkas(BaseModel):
    id: int
    email: str
    nama: str
    peran: Peran


class TambahWatchlist(BaseModel):
    kode_emiten: str
    catatan: str | None = None


class ItemWatchlist(BaseModel):
    kode: str
    nama: str
    sektor: str | None = None
    catatan: str | None = None
    skor_terakhir: float | None = None
    tanggal_skor: date | None = None
    berita_7_hari: int = 0
    harga_terakhir: float | None = None


class BarisPeringkat(BaseModel):
    """Satu baris pada tabel ikhtisar seluruh emiten (SRS UC-01)."""

    kode: str
    nama: str
    sektor: str | None = None
    skor: float | None = None          # rata-rata tertimbang pada rentang
    jumlah_berita: int = 0
    jumlah_positif: int = 0
    jumlah_negatif: int = 0
    harga_terakhir: float | None = None
    perubahan_harga: float | None = None   # persen, awal ke akhir rentang


class Peringkat(BaseModel):
    mulai: date
    sampai: date
    baris: list[BarisPeringkat] = Field(default_factory=list)


class RentangData(BaseModel):
    """Tanggal paling awal dan akhir yang benar-benar ada datanya."""

    mulai: date | None = None
    sampai: date | None = None
    berita_mulai: date | None = None
    berita_sampai: date | None = None
    harga_mulai: date | None = None
    harga_sampai: date | None = None
