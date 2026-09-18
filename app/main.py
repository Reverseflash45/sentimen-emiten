"""Aplikasi FastAPI: API analisis sentimen emiten + dasbor statis.

Jalankan:
    uvicorn app.main:app --reload
Dokumentasi otomatis ada di /docs, dasbor di /.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth as router_auth
from app.api import berita as router_berita
from app.api import emiten as router_emiten
from app.api import peringkat as router_peringkat
from app.api import sistem as router_sistem
from app.api import watchlist as router_watchlist

STATIS = Path(__file__).parent / "static"

app = FastAPI(
    title="Analisis Sentimen Berita Emiten",
    version="0.5.0",
    description=(
        "Menyajikan tren sentimen berita per emiten dan menyandingkannya dengan "
        "pergerakan harga. Sistem tidak melakukan prediksi harga (SRS 10.3)."
    ),
)

app.include_router(router_sistem.router)
app.include_router(router_auth.router)
app.include_router(router_watchlist.router)
app.include_router(router_emiten.router)
app.include_router(router_peringkat.router)
app.include_router(router_berita.router)

if STATIS.is_dir():
    app.mount("/statis", StaticFiles(directory=STATIS), name="statis")

    @app.get("/", include_in_schema=False)
    def dasbor() -> FileResponse:
        return FileResponse(STATIS / "index.html")
