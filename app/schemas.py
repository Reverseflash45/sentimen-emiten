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


class TolakPemetaan(BaseModel):
    """Analis menyatakan berita ini tidak membahas emiten tersebut (UC-05 4a)."""

    kode_emiten: str


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
    kirim_email: bool = False


class UbahEmailNotifikasi(BaseModel):
    aktif: bool


class TambahWatchlist(BaseModel):
    kode_emiten: str
    catatan: str | None = None
    # skala skor sentimen -1..+1; di bawah 0,1 notifikasi akan terlalu sering
    ambang: float | None = Field(None, ge=0.1, le=1.0)


class ItemWatchlist(BaseModel):
    kode: str
    nama: str
    sektor: str | None = None
    catatan: str | None = None
    skor_terakhir: float | None = None
    tanggal_skor: date | None = None
    berita_7_hari: int = 0
    harga_terakhir: float | None = None
    ambang: float = 0.3


class ItemNotifikasi(BaseModel):
    id: int
    kode: str
    nama: str
    tanggal: date
    skor_sebelum: float
    skor_sesudah: float
    jumlah_berita: int
    pesan: str
    dibaca: bool
    dibuat_pada: datetime


class DaftarNotifikasi(BaseModel):
    belum_dibaca: int
    item: list[ItemNotifikasi]


# ---------------------------------------------------------------- admin


class SumberAdmin(BaseModel):
    id: int
    nama: str
    domain: str
    url_rss: str | None = None
    kredibilitas: Kredibilitas
    aktif: bool
    jumlah_berita: int = 0
    siklus_terakhir: datetime | None = None
    siklus_terakhir_berhasil: bool | None = None
    pesan_terakhir: str | None = None


class TambahSumber(BaseModel):
    nama: str = Field(min_length=2, max_length=120)
    url_rss: str = Field(max_length=400)
    kredibilitas: Kredibilitas = Kredibilitas.PORTAL_UMUM


class UbahSumber(BaseModel):
    nama: str | None = Field(None, min_length=2, max_length=120)
    url_rss: str | None = Field(None, max_length=400)
    kredibilitas: Kredibilitas | None = None
    aktif: bool | None = None


class EmitenAdmin(BaseModel):
    kode: str
    nama: str
    sektor: str | None = None
    alias: str | None = None
    aktif: bool
    jumlah_berita: int = 0


class TambahEmiten(BaseModel):
    kode: str = Field(min_length=4, max_length=8, pattern=r"^[A-Za-z]{4}$")
    nama: str = Field(min_length=3, max_length=160)
    sektor: str | None = Field(None, max_length=80)
    alias: str | None = None


class UbahEmiten(BaseModel):
    nama: str | None = Field(None, min_length=3, max_length=160)
    sektor: str | None = Field(None, max_length=80)
    alias: str | None = None
    aktif: bool | None = None


class AkunAdmin(BaseModel):
    id: int
    email: str
    nama: str
    peran: Peran
    aktif: bool
    dibuat_pada: datetime
    jumlah_watchlist: int = 0


class TambahAkun(BaseModel):
    email: str = Field(min_length=5, max_length=160, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    nama: str = Field(min_length=2, max_length=120)
    peran: Peran = Peran.PENGGUNA
    kata_sandi: str = Field(min_length=10, max_length=200)


class UbahAkun(BaseModel):
    nama: str | None = Field(None, min_length=2, max_length=120)
    peran: Peran | None = None
    aktif: bool | None = None
    kata_sandi: str | None = Field(None, min_length=10, max_length=200)


class LogAdmin(BaseModel):
    id: int
    sumber: str | None = None
    mulai_pada: datetime
    selesai_pada: datetime | None = None
    jumlah_ditemukan: int
    jumlah_baru: int
    berhasil: bool
    pesan: str | None = None


class StatusModel(BaseModel):
    label_emas: dict[str, int]
    sebaran_kelas: dict[str, int]
    label_per_versi: dict[str, int]
    minimal_latih: int
    siap_dilatih: bool


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


# ------------------------------------------------ ruang kerja analis


class ItemAntrean(BaseModel):
    """Satu pasangan berita-emiten berlabel model yang belum ditinjau analis."""

    berita_id: int
    judul: str
    ringkasan: str | None = None
    url: str
    sumber: str
    terbit_pada: datetime | None = None
    status_verifikasi: StatusVerifikasi
    kode: str
    nama: str
    kutipan: str | None = None
    label_model: LabelRingkas


class Antrean(BaseModel):
    total: int
    item: list[ItemAntrean] = Field(default_factory=list)


class StatistikAnalis(BaseModel):
    pasangan_berlabel_model: int
    sudah_ditinjau: int
    tersisa: int
    setuju: int
    dikoreksi: int
    #: matriks[label_model][label_analis] = jumlah
    matriks: dict[str, dict[str, int]] = Field(default_factory=dict)
    verifikasi: dict[str, int] = Field(default_factory=dict)
