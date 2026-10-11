"""Aplikasi FastAPI: API analisis sentimen emiten + dasbor statis.

Jalankan:
    uvicorn app.main:app --reload
Dokumentasi otomatis ada di /docs, dasbor di /.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin as router_admin
from app.api import analis as router_analis
from app.api import auth as router_auth
from app.api import berita as router_berita
from app.api import emiten as router_emiten
from app.api import notifikasi as router_notifikasi
from app.api import peringkat as router_peringkat
from app.api import sistem as router_sistem
from app.api import watchlist as router_watchlist

STATIS = Path(__file__).parent / "static"

# Data publik ini sama untuk semua pengunjung tamu dan hanya berubah saat siklus
# pengumpulan atau saat analis melabeli ulang, jadi boleh disimpan sebentar di CDN.
API_PUBLIK = ("/api/peringkat", "/api/emiten", "/api/berita", "/api/ringkasan", "/api/rentang-data")
CACHE_PUBLIK = "public, max-age=0, s-maxage=120, stale-while-revalidate=600"

app = FastAPI(
    title="Analisis Sentimen Berita Emiten",
    version="0.5.0",
    description=(
        "Menyajikan tren sentimen berita per emiten dan menyandingkannya dengan "
        "pergerakan harga. Sistem tidak melakukan prediksi harga (SRS 10.3)."
    ),
)


@app.middleware("http")
async def cache_api_publik(request: Request, call_next):
    """Header keamanan dasar, plus cache CDN untuk respons GET publik.

    Permintaan yang membawa token tidak pernah di-cache.

    `Vary: Authorization` memisahkan keduanya, sehingga analis yang baru saja
    melabeli ulang berita langsung melihat hasilnya, bukan salinan cache tamu.
    """
    respons = await call_next(request)
    if (
        request.method == "GET"
        and request.url.path.startswith(API_PUBLIK)
        and respons.status_code == 200
    ):
        respons.headers["Cache-Control"] = (
            "private, no-store" if request.headers.get("authorization") else CACHE_PUBLIK
        )
        respons.headers["Vary"] = "Authorization"
    respons.headers.setdefault("X-Content-Type-Options", "nosniff")
    respons.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # Dasbor punya halaman masuk; jangan sampai bisa dibingkai situs lain (clickjacking).
    respons.headers.setdefault("X-Frame-Options", "DENY")
    return respons


app.include_router(router_sistem.router)
app.include_router(router_auth.router)
app.include_router(router_watchlist.router)
app.include_router(router_emiten.router)
app.include_router(router_peringkat.router)
app.include_router(router_berita.router)
app.include_router(router_analis.router)
app.include_router(router_notifikasi.router)
app.include_router(router_admin.router)

if STATIS.is_dir():
    app.mount("/statis", StaticFiles(directory=STATIS), name="statis")

    @app.get("/", include_in_schema=False)
    def dasbor() -> FileResponse:
        return FileResponse(STATIS / "index.html")
