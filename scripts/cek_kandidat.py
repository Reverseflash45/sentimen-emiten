"""Menguji daftar kandidat RSS portal finansial Indonesia.

    python -m scripts.cek_kandidat

Dipakai saat sumber lama mati — URL RSS portal berita Indonesia sering berubah.
Script ini TIDAK mengubah basis data; ia hanya melaporkan mana yang hidup,
berapa item yang terbaca, dan judul terbaru sebagai bukti isinya benar.
Tambahkan yang lolos ke `data/lq45.py` lalu jalankan `scripts.init_db`.
"""

from __future__ import annotations

import concurrent.futures as cf
import xml.etree.ElementTree as ET

import httpx

from app.config import settings

ATOM = "{http://www.w3.org/2005/Atom}"

# Kandidat, bukan daftar resmi. Yang gagal belum tentu salah URL — bisa jadi
# portalnya menolak klien non-peramban, dan itu pilihan mereka yang dihormati.
KANDIDAT: list[tuple[str, str, str]] = [
    ("CNBC Indonesia Market", "https://www.cnbcindonesia.com/market/rss", "cnbcindonesia.com"),
    ("CNBC Indonesia Investment", "https://www.cnbcindonesia.com/investment/rss", "cnbcindonesia.com"),
    ("Kontan Investasi", "https://investasi.kontan.co.id/rss", "kontan.co.id"),
    ("Kontan Utama", "https://www.kontan.co.id/rss", "kontan.co.id"),
    ("IDX Channel", "https://www.idxchannel.com/rss", "idxchannel.com"),
    ("IDX Channel Market", "https://www.idxchannel.com/market-news/rss", "idxchannel.com"),
    ("Detik Finance", "https://finance.detik.com/rss", "detik.com"),
    ("Antara Ekonomi", "https://www.antaranews.com/rss/ekonomi.xml", "antaranews.com"),
    ("Liputan6 Bisnis", "https://feed.liputan6.com/rss/bisnis", "liputan6.com"),
    ("Tempo Bisnis", "https://rss.tempo.co/bisnis", "tempo.co"),
    ("Okezone Economy", "https://sindikasi.okezone.com/index.php/rss/6/RSS2.0", "okezone.com"),
    ("Republika Ekonomi", "https://republika.co.id/rss/ekonomi", "republika.co.id"),
    ("Media Indonesia Ekonomi", "https://mediaindonesia.com/read/rss/ekonomi", "mediaindonesia.com"),
    ("Investor.id", "https://investor.id/rss", "investor.id"),
    ("Pasardana", "https://pasardana.id/rss", "pasardana.id"),
    ("Bloomberg Technoz", "https://www.bloombergtechnoz.com/rss", "bloombergtechnoz.com"),
    ("Bisnis.com Market", "https://market.bisnis.com/rss", "bisnis.com"),
    ("EmitenNews", "https://emitennews.com/feed", "emitennews.com"),
]


def cek(kandidat: tuple[str, str, str]) -> str:
    nama, url, _ = kandidat
    try:
        r = httpx.get(
            url,
            headers={"User-Agent": settings.user_agent},
            timeout=20.0,
            follow_redirects=True,
        )
        if r.status_code >= 400:
            return f"  x  {nama:26} HTTP {r.status_code}"
        akar = ET.fromstring(r.content)
        item = akar.findall(".//item") or akar.findall(f".//{ATOM}entry")
        if not item:
            return f"  x  {nama:26} XML terbaca tapi tidak ada item"
        judul = (
            item[0].findtext("title")
            or item[0].findtext(f"{ATOM}title")
            or ""
        ).strip()
        return f"  v  {nama:26} {len(item):3} item  {judul[:56]}"
    except ET.ParseError:
        return f"  x  {nama:26} bukan XML yang sah (mungkin halaman HTML)"
    except Exception as e:  # noqa: BLE001
        return f"  x  {nama:26} {type(e).__name__}: {str(e)[:60]}"


def main() -> None:
    print(f"User-Agent: {settings.user_agent}\n")
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        baris = list(ex.map(cek, KANDIDAT))
    for b in sorted(baris, reverse=True):
        print(b)
    hidup = sum(1 for b in baris if b.strip().startswith("v"))
    print(f"\n{hidup} dari {len(KANDIDAT)} kandidat hidup.")
    print("Tambahkan yang lolos ke SUMBER_AWAL di data/lq45.py, lalu: python -m scripts.init_db")


if __name__ == "__main__":
    main()
