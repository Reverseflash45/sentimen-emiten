"""Titik masuk untuk Vercel.

Vercel mencari objek `app` di berkas seperti `index.py` di akar proyek.
Aplikasinya sendiri tetap di `app/main.py`; berkas ini hanya meneruskan,
supaya Vercel tidak perlu menebak berkas mana yang harus dijalankan.
"""

try:
    from app.main import app  # noqa: F401
except Exception:  # SEMENTARA: tampilkan penyebab gagal start untuk diagnosis deploy
    import traceback

    _jejak = traceback.format_exc().encode()

    async def app(scope, receive, send):  # type: ignore[no-redef]
        if scope["type"] != "http":
            return
        await send({"type": "http.response.start", "status": 500, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": _jejak})
