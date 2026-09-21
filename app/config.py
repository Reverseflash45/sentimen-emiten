"""Konfigurasi aplikasi, dibaca dari environment / berkas .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_ignore_empty: variabel yang ada tapi kosong (mis. dibuat tanpa nilai di
    # dasbor hosting) dianggap tidak diisi, sehingga nilai bawaan yang dipakai.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "sqlite:///./sentimen.db"
    # WAJIB diganti sebelum dipakai di luar mesin sendiri — lihat .env.example.
    # Nilai bawaan ini sengaja mudah dikenali supaya ketahuan kalau lupa diganti.
    secret_key: str = "ganti-kunci-ini-sebelum-dipakai-serius"
    token_berlaku_jam: int = 12
    user_agent: str = "SentimenEmitenBot/0.1"
    crawl_delay: float = 2.0
    max_items_per_source: int = 40
    # batas halaman artikel yang diambil per siklus pengayaan pemetaan
    maks_perkaya_per_siklus: int = 40


settings = Settings()
