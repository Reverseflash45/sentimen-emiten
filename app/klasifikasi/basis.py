"""Antarmuka pengklasifikasi sentimen.

Bagian ini sengaja dibuat sebagai antarmuka, bukan satu implementasi tetap.
Baseline saat ini berbasis leksikon; saat IndoBERT sudah dilatih (rencana
skripsi), model itu cukup dibungkus kelas baru yang mewarisi `Pengklasifikasi`
tanpa mengubah pipeline, API, maupun basis data. `versi` ikut tersimpan di
setiap label, jadi hasil dua versi model bisa dibandingkan (SRS 10.1 butir 8).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models import Sentimen


@dataclass(frozen=True)
class Prediksi:
    sentimen: Sentimen
    keyakinan: float          # 0..1
    penjelasan: str | None = None   # kata pemicu, untuk audit manual


class Pengklasifikasi(ABC):
    """Kontrak minimal sebuah pengklasifikasi sentimen berita."""

    #: dicatat pada setiap label, mis. "leksikon-v1" atau "indobert-v1"
    versi: str = "-"

    @abstractmethod
    def prediksi(self, teks: str) -> Prediksi:
        """Mengklasifikasi satu teks."""

    def prediksi_banyak(self, daftar: list[str]) -> list[Prediksi]:
        """Versi batch. Model berbasis neural sebaiknya menimpa metode ini
        supaya bisa memproses satu batch sekaligus."""
        return [self.prediksi(t) for t in daftar]
