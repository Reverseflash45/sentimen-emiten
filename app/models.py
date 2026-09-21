"""Skema basis data — mengikuti entitas pada SRS Proyek 1.

Catatan desain:
- Satu berita bisa terkait lebih dari satu emiten (SRS 10.1 butir 2),
  karena itu relasinya lewat tabel BeritaEmiten.
- Label sentimen disimpan terpisah dari berita supaya satu berita bisa punya
  beberapa label dari sumber berbeda: model, koreksi analis, atau versi model
  yang berbeda. Ini yang membuat pelatihan ulang (SRS 10.1 butir 8) mungkin
  tanpa menimpa riwayat.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Sentimen(str, enum.Enum):
    POSITIF = "positif"
    NETRAL = "netral"
    NEGATIF = "negatif"


class AsalLabel(str, enum.Enum):
    MODEL = "model"          # hasil inferensi otomatis
    ANALIS = "analis"        # koreksi manual (SRS UC-05)


class Kredibilitas(str, enum.Enum):
    TERVERIFIKASI_DEWAN_PERS = "terverifikasi_dewan_pers"
    PORTAL_UMUM = "portal_umum"
    TIDAK_TERVERIFIKASI = "tidak_terverifikasi"


class StatusVerifikasi(str, enum.Enum):
    TERKONFIRMASI_RESMI = "terkonfirmasi_resmi"
    RUMOR_BELUM_TERKONFIRMASI = "rumor_belum_terkonfirmasi"
    BELUM_DIPERIKSA = "belum_diperiksa"


class Emiten(Base):
    """Emiten yang dipantau. Cakupan dibatasi LQ45 (SRS 10.3)."""

    __tablename__ = "emiten"

    id: Mapped[int] = mapped_column(primary_key=True)
    kode: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    nama: Mapped[str] = mapped_column(String(160))
    sektor: Mapped[str | None] = mapped_column(String(80), default=None)
    # nama lain yang dipakai media, dipisah "|" — dipakai pencocokan teks
    alias: Mapped[str | None] = mapped_column(Text, default=None)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    dibuat_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    berita_terkait: Mapped[list[BeritaEmiten]] = relationship(back_populates="emiten")
    harga: Mapped[list[HargaSaham]] = relationship(back_populates="emiten")

    def daftar_alias(self) -> list[str]:
        return [a.strip() for a in (self.alias or "").split("|") if a.strip()]


class SumberBerita(Base):
    """Portal berita beserta status kredibilitasnya (SRS UC-06)."""

    __tablename__ = "sumber_berita"

    id: Mapped[int] = mapped_column(primary_key=True)
    nama: Mapped[str] = mapped_column(String(120), unique=True)
    domain: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    url_rss: Mapped[str | None] = mapped_column(String(400), default=None)
    kredibilitas: Mapped[Kredibilitas] = mapped_column(
        Enum(Kredibilitas), default=Kredibilitas.PORTAL_UMUM
    )
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    dibuat_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    berita: Mapped[list[Berita]] = relationship(back_populates="sumber")


class Berita(Base):
    """Satu artikel berita.

    Isi artikel TIDAK disimpan utuh (NF-09) — hanya ringkasan/cuplikan dari
    RSS beserta tautan aslinya.
    """

    __tablename__ = "berita"
    __table_args__ = (Index("ix_berita_terbit", "terbit_pada"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sumber_id: Mapped[int] = mapped_column(ForeignKey("sumber_berita.id"), index=True)
    judul: Mapped[str] = mapped_column(Text)
    ringkasan: Mapped[str | None] = mapped_column(Text, default=None)
    url: Mapped[str] = mapped_column(String(600), unique=True, index=True)
    # sidik jari judul+ringkasan, untuk menangkap artikel yang disindikasi ulang
    sidik_jari: Mapped[str] = mapped_column(String(64), index=True)
    terbit_pada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    diambil_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    status_verifikasi: Mapped[StatusVerifikasi] = mapped_column(
        Enum(StatusVerifikasi), default=StatusVerifikasi.BELUM_DIPERIKSA
    )
    sudah_diklasifikasi: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    sumber: Mapped[SumberBerita] = relationship(back_populates="berita")
    emiten_terkait: Mapped[list[BeritaEmiten]] = relationship(
        back_populates="berita", cascade="all, delete-orphan"
    )
    label: Mapped[list[LabelSentimen]] = relationship(
        back_populates="berita", cascade="all, delete-orphan"
    )


class BeritaEmiten(Base):
    """Kaitan berita ke emiten beserta cara pencocokannya."""

    __tablename__ = "berita_emiten"
    __table_args__ = (UniqueConstraint("berita_id", "emiten_id", name="uq_berita_emiten"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    berita_id: Mapped[int] = mapped_column(ForeignKey("berita.id"), index=True)
    emiten_id: Mapped[int] = mapped_column(ForeignKey("emiten.id"), index=True)
    # "kode" bila menemukan ticker, "nama" bila menemukan nama perusahaan/alias
    cara_cocok: Mapped[str] = mapped_column(String(16))
    kutipan: Mapped[str | None] = mapped_column(Text, default=None)

    berita: Mapped[Berita] = relationship(back_populates="emiten_terkait")
    emiten: Mapped[Emiten] = relationship(back_populates="berita_terkait")


class LabelSentimen(Base):
    """Label sentimen untuk pasangan berita-emiten."""

    __tablename__ = "label_sentimen"
    __table_args__ = (
        UniqueConstraint("berita_id", "emiten_id", "asal", "versi_model", name="uq_label"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    berita_id: Mapped[int] = mapped_column(ForeignKey("berita.id"), index=True)
    emiten_id: Mapped[int] = mapped_column(ForeignKey("emiten.id"), index=True)
    sentimen: Mapped[Sentimen] = mapped_column(Enum(Sentimen))
    keyakinan: Mapped[float] = mapped_column(Float, default=0.0)
    asal: Mapped[AsalLabel] = mapped_column(Enum(AsalLabel), default=AsalLabel.MODEL)
    versi_model: Mapped[str] = mapped_column(String(60), default="-")
    dibuat_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    berita: Mapped[Berita] = relationship(back_populates="label")


class HargaSaham(Base):
    """Harga harian emiten, untuk disandingkan dengan tren sentimen (SRS 10.1 butir 7)."""

    __tablename__ = "harga_saham"
    __table_args__ = (UniqueConstraint("emiten_id", "tanggal", name="uq_harga_harian"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    emiten_id: Mapped[int] = mapped_column(ForeignKey("emiten.id"), index=True)
    tanggal: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    pembukaan: Mapped[float | None] = mapped_column(Float, default=None)
    tertinggi: Mapped[float | None] = mapped_column(Float, default=None)
    terendah: Mapped[float | None] = mapped_column(Float, default=None)
    penutupan: Mapped[float | None] = mapped_column(Float, default=None)
    volume: Mapped[int | None] = mapped_column(BigInteger, default=None)  # volume harian bisa > 2^31

    emiten: Mapped[Emiten] = relationship(back_populates="harga")


class KeterbukaanInformasi(Base):
    """Pengumuman resmi BEI — pembanding untuk menentukan status verifikasi."""

    __tablename__ = "keterbukaan_informasi"

    id: Mapped[int] = mapped_column(primary_key=True)
    emiten_id: Mapped[int] = mapped_column(ForeignKey("emiten.id"), index=True)
    judul: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(600), unique=True)
    terbit_pada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    diambil_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class LogPengumpulan(Base):
    """Catatan tiap siklus pengumpulan — kegagalan satu sumber tidak boleh
    menghentikan sumber lain, dan harus tercatat (NF-03)."""

    __tablename__ = "log_pengumpulan"

    id: Mapped[int] = mapped_column(primary_key=True)
    sumber_id: Mapped[int | None] = mapped_column(ForeignKey("sumber_berita.id"), default=None)
    mulai_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    selesai_pada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    jumlah_ditemukan: Mapped[int] = mapped_column(Integer, default=0)
    jumlah_baru: Mapped[int] = mapped_column(Integer, default=0)
    berhasil: Mapped[bool] = mapped_column(Boolean, default=True)
    pesan: Mapped[str | None] = mapped_column(Text, default=None)


class VerifikasiBerita(Base):
    """Jejak kenapa sebuah berita diberi status verifikasi tertentu.

    Tabel ini sengaja terpisah supaya keputusan verifikasi bisa ditelusuri:
    analis harus bisa melihat pengumuman resmi mana yang dipakai sebagai dasar,
    bukan cuma melihat label "terkonfirmasi" tanpa alasan.
    """

    __tablename__ = "verifikasi_berita"
    __table_args__ = (
        UniqueConstraint("berita_id", "keterbukaan_id", name="uq_verifikasi_berita"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    berita_id: Mapped[int] = mapped_column(ForeignKey("berita.id"), index=True)
    keterbukaan_id: Mapped[int | None] = mapped_column(
        ForeignKey("keterbukaan_informasi.id"), default=None, index=True
    )
    status: Mapped[StatusVerifikasi] = mapped_column(Enum(StatusVerifikasi))
    # 0..1 — seberapa mirip judul berita dengan judul pengumuman
    kemiripan: Mapped[float] = mapped_column(Float, default=0.0)
    alasan: Mapped[str] = mapped_column(Text, default="")
    otomatis: Mapped[bool] = mapped_column(Boolean, default=True)
    dibuat_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Peran(str, enum.Enum):
    PENGGUNA = "pengguna"    # bisa melihat dan mengelola watchlist sendiri
    ANALIS = "analis"        # bisa mengoreksi label dan status verifikasi


class Pengguna(Base):
    """Akun pengguna sistem (SRS UC-02, UC-05).

    Kata sandi tidak pernah disimpan apa adanya — hanya hasil turunannya
    beserta garam acak per akun.
    """

    __tablename__ = "pengguna"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    nama: Mapped[str] = mapped_column(String(120))
    kata_sandi_hash: Mapped[str] = mapped_column(String(255))
    peran: Mapped[Peran] = mapped_column(Enum(Peran), default=Peran.PENGGUNA)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    dibuat_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    watchlist: Mapped[list[Watchlist]] = relationship(
        back_populates="pengguna", cascade="all, delete-orphan"
    )


class Watchlist(Base):
    """Emiten yang dipantau seorang pengguna (SRS UC-02)."""

    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("pengguna_id", "emiten_id", name="uq_watchlist"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pengguna_id: Mapped[int] = mapped_column(ForeignKey("pengguna.id"), index=True)
    emiten_id: Mapped[int] = mapped_column(ForeignKey("emiten.id"), index=True)
    catatan: Mapped[str | None] = mapped_column(Text, default=None)
    ditambah_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    pengguna: Mapped[Pengguna] = relationship(back_populates="watchlist")
    emiten: Mapped[Emiten] = relationship()


class PengayaanBerita(Base):
    """Catatan bahwa badan artikel sebuah berita sudah pernah diambil.

    Tanpa catatan ini, berita yang halamannya sudah diambil tapi ternyata tidak
    menyebut emiten mana pun akan tetap tidak terpetakan — dan ikut terambil
    lagi pada setiap siklus berikutnya. Portal yang sama akan dihujani
    permintaan untuk artikel yang sudah jelas hasilnya, dan siklus tidak pernah
    selesai.
    """

    __tablename__ = "pengayaan_berita"

    id: Mapped[int] = mapped_column(primary_key=True)
    berita_id: Mapped[int] = mapped_column(
        ForeignKey("berita.id"), unique=True, index=True
    )
    dicoba_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    # jumlah kaitan emiten yang ditemukan; 0 berarti sudah diperiksa dan memang
    # tidak menyebut emiten yang dipantau
    jumlah_kaitan: Mapped[int] = mapped_column(Integer, default=0)
    # False bila halamannya gagal diambil — layak dicoba lagi nanti
    berhasil_diambil: Mapped[bool] = mapped_column(Boolean, default=True)
