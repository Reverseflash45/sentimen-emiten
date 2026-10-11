"""Pembatas percobaan masuk yang gagal, per alamat IP dan per email.

Menahan tebak-tebakan kata sandi: setelah MAKS_GAGAL kegagalan dalam JENDELA,
permintaan berikutnya langsung ditolak dengan 429 sampai jendela bergeser.
Disimpan di memori proses (setiap instans serverless menghitung sendiri), jadi
ini penghalang tambahan di atas bcrypt yang memang lambat, bukan pengganti
sandi yang kuat.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

MAKS_GAGAL = 10
JENDELA_DETIK = 15 * 60

_kunci = threading.Lock()
_gagal: dict[str, deque[float]] = defaultdict(deque)


def _bersihkan(antrean: deque[float], sekarang: float) -> None:
    while antrean and antrean[0] <= sekarang - JENDELA_DETIK:
        antrean.popleft()


def sisa_tunggu(kunci: list[str], sekarang: float | None = None) -> int:
    """Detik yang harus ditunggu bila salah satu kunci sudah melewati batas; 0 bila boleh."""
    sekarang = time.monotonic() if sekarang is None else sekarang
    tunggu = 0
    with _kunci:
        for k in kunci:
            antrean = _gagal.get(k)
            if not antrean:
                continue
            _bersihkan(antrean, sekarang)
            if len(antrean) >= MAKS_GAGAL:
                tunggu = max(tunggu, int(antrean[0] + JENDELA_DETIK - sekarang) + 1)
    return tunggu


def catat_gagal(kunci: list[str], sekarang: float | None = None) -> None:
    sekarang = time.monotonic() if sekarang is None else sekarang
    with _kunci:
        for k in kunci:
            antrean = _gagal[k]
            _bersihkan(antrean, sekarang)
            antrean.append(sekarang)
        if len(_gagal) > 10_000:  # jangan tumbuh tanpa batas di instans yang hidup lama
            for k in [k for k, v in _gagal.items() if not v]:
                del _gagal[k]


def reset(kunci: list[str] | None = None) -> None:
    """Hapus catatan (setelah berhasil masuk, atau di pengujian)."""
    with _kunci:
        if kunci is None:
            _gagal.clear()
        else:
            for k in kunci:
                _gagal.pop(k, None)
