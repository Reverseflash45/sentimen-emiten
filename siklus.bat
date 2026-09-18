@echo off
REM Pembungkus untuk Task Scheduler Windows.
REM
REM Task Scheduler tidak memakai PATH dan direktori kerja seperti PowerShell
REM biasa, jadi keduanya ditetapkan di sini. Tanpa ini, tugas terjadwal gagal
REM dengan "No module named app" — dan kegagalannya tidak terlihat sampai
REM berhari-hari kemudian saat datanya ternyata kosong.

cd /d "%~dp0"
call ".venv\Scripts\activate.bat"
python -m scripts.siklus_harian %*
exit /b %ERRORLEVEL%
