@echo off
REM Cadangan basis data bulanan untuk Task Scheduler Windows (lihat scripts/cadangkan_db.py).
REM pg_dump dicari di PATH; Task Scheduler tidak selalu mewarisinya, jadi
REM folder PostgreSQL ditambahkan bila ada.

cd /d "%~dp0"
if exist "C:\Program Files\PostgreSQL\18\bin" set "PATH=C:\Program Files\PostgreSQL\18\bin;%PATH%"
if not exist "data\log" mkdir "data\log"
call ".venv\Scripts\activate.bat"
python -m scripts.cadangkan_db %* >> data\log\cadangan.log 2>&1
exit /b %ERRORLEVEL%
