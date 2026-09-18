"""Uji konsistensi daftar sumber dan emiten di `data/lq45.py`.

Uji ini tidak memeriksa apakah URL-nya hidup — itu kerjaan `scripts.cek_sumber`
dan butuh jaringan. Yang diperiksa di sini adalah hal-hal yang bisa salah tanpa
disadari saat daftarnya disunting tangan.
"""

from __future__ import annotations

from app.ingest.cleaner import normalisasi
from app.models import Kredibilitas
from data.lq45 import EMITEN_AWAL, SUMBER_AWAL, SUMBER_NONAKTIF


def test_kode_emiten_tidak_kembar():
    kode = [k for k, *_ in EMITEN_AWAL]
    assert len(kode) == len(set(kode))


def test_kode_emiten_empat_huruf_kapital():
    for kode, *_ in EMITEN_AWAL:
        assert kode.isupper() and kode.isalpha() and len(kode) == 4, kode


def test_domain_sumber_tidak_kembar():
    domain = [d for _, d, *_ in SUMBER_AWAL]
    assert len(domain) == len(set(domain))


def test_kredibilitas_sumber_dikenali():
    for nama, _, _, kredibilitas in SUMBER_AWAL:
        assert kredibilitas in {k.value for k in Kredibilitas}, nama


def test_url_rss_https():
    """Pengambilan lewat HTTP biasa tidak dipakai — isinya bisa diubah di jalan."""
    for nama, _, url, _ in SUMBER_AWAL:
        assert url.startswith("https://"), nama


def test_domain_sumber_cocok_dengan_url():
    """Domain dipakai untuk pemeriksaan robots.txt; kalau tidak cocok dengan
    URL RSS-nya, yang diperiksa jadi situs yang salah."""
    for nama, domain, url, _ in SUMBER_AWAL:
        assert domain in url, f"{nama}: {domain} tidak ada di {url}"


def test_sumber_nonaktif_tidak_ikut_aktif():
    """Satu domain tidak boleh berada di dua daftar sekaligus."""
    aktif = {d for _, d, *_ in SUMBER_AWAL}
    nonaktif = {d for d, _ in SUMBER_NONAKTIF}
    assert not (aktif & nonaktif)


def test_setiap_sumber_nonaktif_punya_alasan():
    for domain, alasan in SUMBER_NONAKTIF:
        assert len(alasan) > 10, domain


def test_alias_bukan_bagian_nama_emiten_lain():
    """Alias harus menunjuk satu perusahaan, bukan satu grup.

    "Astra" cocok dengan Astra International maupun Astra Otoparts; "Indofood"
    cocok dengan INDF maupun ICBP. Alias semacam itu memetakan berita ke emiten
    yang salah, dan kesalahannya tidak terlihat lagi setelah teragregasi.
    """
    nama = {kode: normalisasi(n) for kode, n, _, _ in EMITEN_AWAL}
    salah: list[str] = []
    for kode, _, _, alias in EMITEN_AWAL:
        for a in (alias or "").split("|"):
            a = normalisasi(a)
            if len(a) < 4:
                continue
            for kode_lain, nama_lain in nama.items():
                if kode_lain != kode and a in nama_lain:
                    salah.append(f"alias {a!r} ({kode}) ikut cocok ke {kode_lain}")
    assert not salah, "; ".join(salah)


def test_alias_tidak_sama_dengan_kode_emiten_lain():
    kode_semua = {k for k, *_ in EMITEN_AWAL}
    for kode, _, _, alias in EMITEN_AWAL:
        for a in (alias or "").split("|"):
            assert a.strip().upper() not in (kode_semua - {kode}), f"{kode}: {a}"
