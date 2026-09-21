"""Titik masuk untuk Vercel.

Vercel mencari objek `app` di berkas seperti `index.py` di akar proyek.
Aplikasinya sendiri tetap di `app/main.py`; berkas ini hanya meneruskan,
supaya Vercel tidak perlu menebak berkas mana yang harus dijalankan.
"""

from app.main import app  # noqa: F401
