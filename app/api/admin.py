"""Pengelolaan sistem oleh admin (SRS FR-8, UC-06).

Mencakup sumber berita, daftar emiten, akun pengguna, pemantauan siklus
pengumpulan, dan status data latih model.

Catatan penting: `data/lq45.py` tetap menjadi acuan resmi komposisi LQ45 dan
daftar portal penelitian. `python -m scripts.init_db` menyelaraskan basis data
ke berkas itu, sehingga perubahan admin pada emiten atau sumber yang tercantum
di sana akan tertimpa saat init_db dijalankan. Itu disengaja: daftar yang
dipakai penelitian harus bisa dibaca di repositori, bukan hanya di basis data.
"""

from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependensi import wajib_admin
from app.auth.keamanan import hash_kata_sandi
from app.database import get_session
from app.klasifikasi.dataset import muat_label_emas
from app.models import (
    AsalLabel,
    Berita,
    BeritaEmiten,
    Emiten,
    LabelSentimen,
    LogPengumpulan,
    Pengguna,
    SumberBerita,
    Watchlist,
)
from app.schemas import (
    AkunAdmin,
    EmitenAdmin,
    LogAdmin,
    StatusModel,
    SumberAdmin,
    TambahAkun,
    TambahEmiten,
    TambahSumber,
    UbahAkun,
    UbahEmiten,
    UbahSumber,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

MINIMAL_LATIH = 200


# ------------------------------------------------------------------ sumber


def _domain(url: str) -> str:
    """Host dari URL RSS; menolak alamat yang bukan http(s) (UC-06 3a)."""
    u = urlparse(url.strip())
    if u.scheme not in ("http", "https") or not u.netloc or "." not in u.netloc:
        raise HTTPException(400, "alamat RSS tidak valid — harus diawali http:// atau https://")
    return u.netloc.lower()


def _rakit_sumber(session: Session, s: SumberBerita) -> SumberAdmin:
    jumlah = session.scalar(select(func.count(Berita.id)).where(Berita.sumber_id == s.id)) or 0
    log = session.scalar(
        select(LogPengumpulan).where(LogPengumpulan.sumber_id == s.id)
        .order_by(LogPengumpulan.mulai_pada.desc()).limit(1)
    )
    return SumberAdmin(
        id=s.id, nama=s.nama, domain=s.domain, url_rss=s.url_rss, kredibilitas=s.kredibilitas,
        aktif=s.aktif, jumlah_berita=jumlah,
        siklus_terakhir=log.mulai_pada if log else None,
        siklus_terakhir_berhasil=log.berhasil if log else None,
        pesan_terakhir=(log.pesan or "").splitlines()[0][:200] if log and log.pesan else None,
    )


@router.get("/sumber", response_model=list[SumberAdmin])
def daftar_sumber(_: Pengguna = Depends(wajib_admin), session: Session = Depends(get_session)):
    return [_rakit_sumber(session, s) for s in session.scalars(select(SumberBerita).order_by(SumberBerita.nama))]


@router.post("/sumber", response_model=SumberAdmin, status_code=status.HTTP_201_CREATED)
def tambah_sumber(badan: TambahSumber, _: Pengguna = Depends(wajib_admin),
                  session: Session = Depends(get_session)):
    domain = _domain(badan.url_rss)
    bentrok = session.scalar(select(SumberBerita).where(
        (SumberBerita.nama == badan.nama.strip()) | (SumberBerita.domain == domain)
        | (SumberBerita.url_rss == badan.url_rss.strip())
    ))
    if bentrok is not None:
        raise HTTPException(400, f"portal sudah terdaftar sebagai “{bentrok.nama}”")
    s = SumberBerita(nama=badan.nama.strip(), domain=domain, url_rss=badan.url_rss.strip(),
                     kredibilitas=badan.kredibilitas)
    session.add(s)
    session.commit()
    return _rakit_sumber(session, s)


@router.patch("/sumber/{sumber_id}", response_model=SumberAdmin)
def ubah_sumber(sumber_id: int, badan: UbahSumber, _: Pengguna = Depends(wajib_admin),
                session: Session = Depends(get_session)):
    s = session.get(SumberBerita, sumber_id)
    if s is None:
        raise HTTPException(404, "sumber tidak ditemukan")
    if badan.url_rss is not None:
        domain = _domain(badan.url_rss)
        bentrok = session.scalar(select(SumberBerita).where(
            SumberBerita.id != s.id,
            (SumberBerita.domain == domain) | (SumberBerita.url_rss == badan.url_rss.strip()),
        ))
        if bentrok is not None:
            raise HTTPException(400, f"alamat itu sudah dipakai “{bentrok.nama}”")
        s.url_rss, s.domain = badan.url_rss.strip(), domain
    if badan.nama is not None:
        if session.scalar(select(SumberBerita.id).where(SumberBerita.id != s.id,
                                                        SumberBerita.nama == badan.nama.strip())):
            raise HTTPException(400, "nama portal sudah dipakai")
        s.nama = badan.nama.strip()
    if badan.kredibilitas is not None:
        s.kredibilitas = badan.kredibilitas
    if badan.aktif is not None:
        s.aktif = badan.aktif
    session.commit()
    return _rakit_sumber(session, s)


# ------------------------------------------------------------------ emiten


def _rakit_emiten(session: Session, e: Emiten) -> EmitenAdmin:
    jumlah = session.scalar(select(func.count(BeritaEmiten.id)).where(BeritaEmiten.emiten_id == e.id)) or 0
    return EmitenAdmin(kode=e.kode, nama=e.nama, sektor=e.sektor, alias=e.alias, aktif=e.aktif,
                       jumlah_berita=jumlah)


@router.get("/emiten", response_model=list[EmitenAdmin])
def daftar_emiten(_: Pengguna = Depends(wajib_admin), session: Session = Depends(get_session)):
    return [_rakit_emiten(session, e) for e in session.scalars(select(Emiten).order_by(Emiten.kode))]


def _bersihkan_alias(alias: str | None) -> str | None:
    if alias is None:
        return None
    bagian = [a.strip() for a in alias.split("|") if a.strip()]
    return "|".join(bagian) or None


@router.post("/emiten", response_model=EmitenAdmin, status_code=status.HTTP_201_CREATED)
def tambah_emiten(badan: TambahEmiten, _: Pengguna = Depends(wajib_admin),
                  session: Session = Depends(get_session)):
    kode = badan.kode.upper()
    if session.scalar(select(Emiten.id).where(Emiten.kode == kode)):
        raise HTTPException(400, f"emiten {kode} sudah terdaftar")
    e = Emiten(kode=kode, nama=badan.nama.strip(), sektor=(badan.sektor or "").strip() or None,
               alias=_bersihkan_alias(badan.alias))
    session.add(e)
    session.commit()
    return _rakit_emiten(session, e)


@router.patch("/emiten/{kode}", response_model=EmitenAdmin)
def ubah_emiten(kode: str, badan: UbahEmiten, _: Pengguna = Depends(wajib_admin),
                session: Session = Depends(get_session)):
    e = session.scalar(select(Emiten).where(Emiten.kode == kode.upper()))
    if e is None:
        raise HTTPException(404, f"emiten {kode.upper()} tidak ditemukan")
    if badan.nama is not None:
        e.nama = badan.nama.strip()
    if badan.sektor is not None:
        e.sektor = badan.sektor.strip() or None
    if badan.alias is not None:
        e.alias = _bersihkan_alias(badan.alias)
    if badan.aktif is not None:
        # dinonaktifkan, bukan dihapus: berita dan harga yang sudah terkumpul
        # tetap catatan periode sebelumnya dan tidak bisa diambil ulang
        e.aktif = badan.aktif
    session.commit()
    return _rakit_emiten(session, e)


# ------------------------------------------------------------------ akun


def _rakit_akun(session: Session, p: Pengguna) -> AkunAdmin:
    n = session.scalar(select(func.count(Watchlist.id)).where(Watchlist.pengguna_id == p.id)) or 0
    return AkunAdmin(id=p.id, email=p.email, nama=p.nama, peran=p.peran, aktif=p.aktif,
                     dibuat_pada=p.dibuat_pada, jumlah_watchlist=n)


@router.get("/akun", response_model=list[AkunAdmin])
def daftar_akun(_: Pengguna = Depends(wajib_admin), session: Session = Depends(get_session)):
    return [_rakit_akun(session, p) for p in session.scalars(select(Pengguna).order_by(Pengguna.id))]


@router.post("/akun", response_model=AkunAdmin, status_code=status.HTTP_201_CREATED)
def tambah_akun(badan: TambahAkun, _: Pengguna = Depends(wajib_admin),
                session: Session = Depends(get_session)):
    email = badan.email.strip().lower()
    if session.scalar(select(Pengguna.id).where(Pengguna.email == email)):
        raise HTTPException(400, "email sudah terdaftar")
    p = Pengguna(email=email, nama=badan.nama.strip(), peran=badan.peran,
                 kata_sandi_hash=hash_kata_sandi(badan.kata_sandi))
    session.add(p)
    session.commit()
    return _rakit_akun(session, p)


@router.patch("/akun/{akun_id}", response_model=AkunAdmin)
def ubah_akun(akun_id: int, badan: UbahAkun, admin: Pengguna = Depends(wajib_admin),
              session: Session = Depends(get_session)):
    p = session.get(Pengguna, akun_id)
    if p is None:
        raise HTTPException(404, "akun tidak ditemukan")
    # admin tidak boleh mengunci dirinya sendiri — tanpa admin lain, tidak ada
    # lagi yang bisa mengembalikan haknya kecuali lewat basis data langsung
    if p.id == admin.id and (badan.aktif is False or (badan.peran is not None and badan.peran != p.peran)):
        raise HTTPException(400, "tidak bisa menonaktifkan atau menurunkan peran akun sendiri")
    if badan.nama is not None:
        p.nama = badan.nama.strip()
    if badan.peran is not None:
        p.peran = badan.peran
    if badan.aktif is not None:
        p.aktif = badan.aktif
    if badan.kata_sandi is not None:
        p.kata_sandi_hash = hash_kata_sandi(badan.kata_sandi)
    session.commit()
    return _rakit_akun(session, p)


# ------------------------------------------------------------------ pemantauan


@router.get("/log", response_model=list[LogAdmin])
def log_pengumpulan(limit: int = Query(60, ge=1, le=500), _: Pengguna = Depends(wajib_admin),
                    session: Session = Depends(get_session)):
    baris = session.execute(
        select(LogPengumpulan, SumberBerita.nama)
        .outerjoin(SumberBerita, SumberBerita.id == LogPengumpulan.sumber_id)
        .order_by(LogPengumpulan.mulai_pada.desc(), LogPengumpulan.id.desc())
        .limit(limit)
    ).all()
    return [
        LogAdmin(id=l.id, sumber=nama, mulai_pada=l.mulai_pada, selesai_pada=l.selesai_pada,
                 jumlah_ditemukan=l.jumlah_ditemukan, jumlah_baru=l.jumlah_baru, berhasil=l.berhasil,
                 pesan=(l.pesan or "").splitlines()[0][:300] if l.pesan else None)
        for l, nama in baris
    ]


@router.get("/model", response_model=StatusModel)
def status_model(_: Pengguna = Depends(wajib_admin), session: Session = Depends(get_session)):
    """Kesiapan data untuk pelatihan ulang.

    Pelatihan sendiri dijalankan di mesin ber-GPU (scripts/latih_indobert.py),
    bukan dari server web: server tidak punya GPU, dan proses berdurasi puluhan
    menit akan diputus batas waktu permintaan.
    """
    emas = muat_label_emas(session)
    per_bagian = Counter(c.bagian for c in emas)
    per_versi = Counter(
        v for v in session.scalars(select(LabelSentimen.versi_model).where(LabelSentimen.asal == AsalLabel.MODEL))
    )
    return StatusModel(
        label_emas={"total": len(emas), **{k: per_bagian.get(k, 0) for k in ("latih", "validasi", "uji")}},
        sebaran_kelas=dict(Counter(c.sentimen.value for c in emas)),
        label_per_versi=dict(per_versi),
        minimal_latih=MINIMAL_LATIH,
        siap_dilatih=per_bagian.get("latih", 0) >= MINIMAL_LATIH,
    )
