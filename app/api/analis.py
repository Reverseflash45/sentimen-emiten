"""Ruang kerja analis: antrean tinjauan label dan statistik kesepakatan.

Analis tidak perlu mencari sendiri berita mana yang layak ditinjau: antrean
menyajikan pasangan berita-emiten yang labelnya masih buatan model, yang
paling tidak yakin lebih dulu — di situlah koreksi manusia paling bernilai.

Statistik membandingkan label model dengan keputusan analis. Tingkat
kesepakatan ini adalah ukuran kualitas model yang paling langsung terbaca,
dan matriksnya menunjukkan ke arah mana model paling sering keliru.
"""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analitik.agregasi import _label_terpilih
from app.auth.dependensi import wajib_analis
from app.database import get_session
from app.models import (
    AsalLabel, Berita, BeritaEmiten, Emiten, LabelSentimen, Pengguna, Sentimen, StatusVerifikasi, SumberBerita,
)
from app.schemas import Antrean, ItemAntrean, LabelRingkas, StatistikAnalis

router = APIRouter(prefix="/api/analis", tags=["analis"])


def _label_per_pasangan(session: Session) -> dict[tuple[int, int], tuple[LabelSentimen | None, LabelSentimen | None]]:
    """(berita, emiten) -> (label model terpilih, label analis terpilih)."""
    model: dict[tuple[int, int], list[LabelSentimen]] = {}
    analis: dict[tuple[int, int], list[LabelSentimen]] = {}
    for l in session.scalars(select(LabelSentimen)):
        tujuan = analis if l.asal == AsalLabel.ANALIS else model
        tujuan.setdefault((l.berita_id, l.emiten_id), []).append(l)
    kunci = set(model) | set(analis)
    return {k: (_label_terpilih(model.get(k, [])), _label_terpilih(analis.get(k, []))) for k in kunci}


@router.get("/antrean", response_model=Antrean)
def antrean(
    kode: str | None = Query(None, description="batasi ke satu emiten"),
    urut: str = Query("keyakinan", pattern="^(keyakinan|terbaru)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: Pengguna = Depends(wajib_analis),
    session: Session = Depends(get_session),
) -> Antrean:
    label = _label_per_pasangan(session)
    kueri = (
        select(BeritaEmiten, Berita, Emiten, SumberBerita)
        .join(Berita, Berita.id == BeritaEmiten.berita_id)
        .join(Emiten, Emiten.id == BeritaEmiten.emiten_id)
        .join(SumberBerita, SumberBerita.id == Berita.sumber_id)
    )
    if kode:
        kueri = kueri.where(Emiten.kode == kode.upper())

    calon = []
    for be, berita, emiten, sumber in session.execute(kueri).all():
        model, analis = label.get((be.berita_id, be.emiten_id), (None, None))
        if model is None or analis is not None:
            continue
        calon.append((model, be, berita, emiten, sumber))

    if urut == "keyakinan":
        calon.sort(key=lambda c: (c[0].keyakinan, -(c[2].id)))
    else:
        # berita tanpa tanggal terbit ditaruh paling akhir
        calon.sort(key=lambda c: c[2].terbit_pada.timestamp() if c[2].terbit_pada else float("-inf"), reverse=True)

    item = [
        ItemAntrean(
            berita_id=berita.id, judul=berita.judul, ringkasan=berita.ringkasan, url=berita.url,
            sumber=sumber.nama, terbit_pada=berita.terbit_pada, status_verifikasi=berita.status_verifikasi,
            kode=emiten.kode, nama=emiten.nama, kutipan=be.kutipan,
            label_model=LabelRingkas(sentimen=model.sentimen, keyakinan=model.keyakinan,
                                     asal=model.asal, versi_model=model.versi_model),
        )
        for model, be, berita, emiten, sumber in calon[offset : offset + limit]
    ]
    return Antrean(total=len(calon), item=item)


@router.get("/statistik", response_model=StatistikAnalis)
def statistik(
    _: Pengguna = Depends(wajib_analis),
    session: Session = Depends(get_session),
) -> StatistikAnalis:
    nama = [s.value for s in Sentimen]
    matriks = {m: {a: 0 for a in nama} for m in nama}
    berlabel_model = ditinjau = setuju = 0
    for model, analis in _label_per_pasangan(session).values():
        if model is None:
            continue
        berlabel_model += 1
        if analis is None:
            continue
        ditinjau += 1
        matriks[model.sentimen.value][analis.sentimen.value] += 1
        setuju += model.sentimen == analis.sentimen

    status = Counter(s.value for s in session.scalars(select(Berita.status_verifikasi)))
    return StatistikAnalis(
        pasangan_berlabel_model=berlabel_model,
        sudah_ditinjau=ditinjau,
        tersisa=berlabel_model - ditinjau,
        setuju=setuju,
        dikoreksi=ditinjau - setuju,
        matriks=matriks,
        verifikasi={s.value: status.get(s.value, 0) for s in StatusVerifikasi},
    )
