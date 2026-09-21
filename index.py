"""Titik masuk untuk Vercel (lihat [tool.vercel] di pyproject.toml).

Aplikasinya sendiri tetap di `app/main.py`; berkas ini hanya meneruskan.
"""

from app.main import app  # noqa: F401
