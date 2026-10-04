"""Laporan pengujian black-box per kebutuhan SRS, dari hasil uji otomatis.

    python -m scripts.laporan_pengujian

Setiap skenario ditulis dari sudut pandang pengguna (masukan → hasil yang
diharapkan) lalu dikaitkan dengan uji otomatis yang membuktikannya. Statusnya
TIDAK diisi tangan: pytest dijalankan, dan sebuah skenario dinyatakan lulus
hanya bila semua uji yang membuktikannya lulus pada saat laporan dibuat.

Uji berjenis "API" memanggil endpoint HTTP seperti klien sungguhan tanpa
melihat isi kode (black-box); uji berjenis "unit" memeriksa satu komponen.

Keluaran: data/pengujian/laporan_pengujian.md (dan .html untuk dibuka di Word)
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from html import escape
from pathlib import Path

LAPORAN = Path("data/pengujian/laporan_pengujian.md")

A = "tests/test_api.py::"
# (kode kebutuhan, skenario, masukan, hasil yang diharapkan, jenis, [uji])
SKENARIO: list[tuple[str, str, str, str, str, list[str]]] = [
    ("UC-01", "Melihat deret sentimen dan harga", "Pilih emiten BBCA, rentang September",
     "Deret skor harian dan harga penutupan tampil", "API",
     [A + "test_deret_sentimen", A + "test_deret_harga", A + "test_detail_emiten"]),
    ("UC-01", "Korelasi dihitung terhadap imbal hasil", "Emiten dengan data 10 hari",
     "Pearson dan Spearman tampil beserta kekuatannya", "API", [A + "test_korelasi_terhitung"]),
    ("UC-01 3a", "Data belum mencukupi", "Rentang dengan kurang dari 4 hari beririsan",
     "Pesan 'data belum cukup', bukan galat", "API",
     [A + "test_korelasi_kurang_data_memberi_catatan", "tests/test_korelasi.py::test_data_terlalu_sedikit_memberi_catatan_bukan_error"]),
    ("UC-01", "Rentang tanggal tidak valid", "Tanggal mulai setelah tanggal sampai",
     "Permintaan ditolak dengan pesan jelas", "API", [A + "test_rentang_terbalik_ditolak"]),
    ("UC-01", "Emiten tidak dikenal", "Kode emiten yang tidak terdaftar", "Respons 404 'tidak ditemukan'",
     "API", [A + "test_emiten_tidak_ada"]),
    ("UC-01", "Pencarian emiten", "Ketik nama perusahaan sebagian", "Emiten yang cocok muncul", "API",
     [A + "test_cari_emiten_berdasarkan_nama", A + "test_daftar_emiten"]),
    ("UC-01", "Daftar berita dan saringannya", "Saring berita BBCA berdasarkan sentimen",
     "Hanya berita dengan sentimen itu yang tampil", "API",
     [A + "test_daftar_berita_dan_label", A + "test_saring_berita_berdasarkan_sentimen"]),
    ("UC-02", "Menambah dan melihat watchlist", "Pengguna masuk, tambah BBCA", "BBCA tampil di watchlist",
     "API", [A + "test_tambah_dan_lihat_watchlist", A + "test_watchlist_terpisah_antar_pengguna"]),
    ("UC-02", "Menghapus emiten dari watchlist", "Hapus BBCA dari watchlist", "BBCA tidak lagi tampil",
     "API", [A + "test_hapus_watchlist", A + "test_hapus_yang_tidak_ada"]),
    ("UC-02", "Mengatur ambang notifikasi", "Ubah ambang BBCA ke 0,5; coba 0,01",
     "0,5 tersimpan; 0,01 ditolak", "API", [A + "test_ambang_watchlist_bisa_diatur"]),
    ("UC-02 3a", "Emiten di luar cakupan LQ45", "Tambah emiten yang tidak dipantau",
     "Ditolak dengan pesan", "API", [A + "test_kelola_emiten", A + "test_tambah_emiten_tak_dikenal"]),
    ("UC-02", "Watchlist tanpa login", "Buka watchlist tanpa token", "Respons 401", "API",
     [A + "test_watchlist_butuh_token"]),
    ("FR-6", "Notifikasi perubahan sentimen", "Sentimen BBCA berbalik dari negatif ke positif",
     "Satu notifikasi dibuat, tidak diulang", "unit",
     ["tests/test_notifikasi.py::test_perubahan_tajam_memicu_satu_notifikasi",
      "tests/test_notifikasi.py::test_perubahan_di_bawah_ambang_diam",
      "tests/test_notifikasi.py::test_satu_berita_tidak_cukup_untuk_disebut_perubahan"]),
    ("FR-6", "Membaca notifikasi", "Buka panel notifikasi, tandai dibaca",
     "Hanya notifikasi milik sendiri; jumlah belum dibaca jadi 0", "API",
     ["tests/test_notifikasi.py::test_api_notifikasi_milik_sendiri_dan_bisa_ditandai_dibaca"]),
    ("FR-6", "Email notifikasi opt-in", "Satu pengguna menyalakan email, satu tidak",
     "Hanya yang menyalakan yang menerima email", "unit",
     ["tests/test_notifikasi.py::test_email_hanya_untuk_yang_menyalakan_dan_diam_tanpa_smtp"]),
    ("UC-03", "Label per pasangan berita–emiten", "Berita yang menyebut dua emiten",
     "Masing-masing emiten mendapat label", "unit",
     ["tests/test_klasifikasi.py::test_pipeline_membuat_label_per_emiten",
      "tests/test_dataset_ml.py::test_model_per_emiten_memberi_label_berbeda_per_emiten"]),
    ("UC-03", "Tidak melabeli dua kali", "Siklus klasifikasi dijalankan ulang",
     "Tidak ada label ganda", "unit",
     ["tests/test_klasifikasi.py::test_tidak_melabeli_dua_kali",
      "tests/test_klasifikasi.py::test_ulangi_tidak_menggandakan_label_versi_sama"]),
    ("UC-04", "Berita cocok dengan pengumuman resmi", "Judul berita mirip pengumuman BEI",
     "Status Terkonfirmasi Resmi beserta jejaknya", "unit",
     ["tests/test_verifikasi.py::test_berita_cocok_jadi_terkonfirmasi",
      "tests/test_verifikasi.py::test_jejak_menyimpan_pengumuman_yang_dipakai"]),
    ("UC-04", "Kabar spekulatif tanpa pengumuman", "Berita 'dikabarkan akan akuisisi'",
     "Status Rumor Belum Terkonfirmasi", "unit",
     ["tests/test_verifikasi.py::test_kabar_spekulatif_tanpa_pengumuman_jadi_rumor"]),
    ("UC-04", "Berita biasa tanpa pengumuman", "Berita tanpa padanan dan tanpa bahasa spekulatif",
     "Status tetap Belum Diperiksa", "unit",
     ["tests/test_verifikasi.py::test_berita_biasa_tanpa_pengumuman_dibiarkan"]),
    ("UC-04", "Keputusan analis dihormati", "Siklus verifikasi otomatis berjalan lagi",
     "Status yang ditetapkan analis tidak ditimpa", "unit",
     ["tests/test_verifikasi.py::test_keputusan_analis_tidak_ditimpa", A + "test_ubah_status_verifikasi",
      A + "test_jejak_verifikasi_tercatat_saat_diubah_manual"]),
    ("UC-05", "Antrean tinjauan", "Analis membuka antrean", "Label model belum ditinjau, paling ragu dulu",
     "API", [A + "test_antrean_berisi_label_model_yang_belum_ditinjau"]),
    ("UC-05", "Koreksi label", "Analis mengubah label ke netral",
     "Label analis dipakai, label model tetap tersimpan", "API",
     [A + "test_koreksi_analis_mengalahkan_label_model", A + "test_statistik_menghitung_setuju_dan_koreksi"]),
    ("UC-05 4a", "Berita tidak relevan", "Analis menandai pemetaan salah",
     "Kaitan dicabut tanpa label; skor emiten ikut berubah", "API",
     [A + "test_tidak_relevan_mencabut_kaitan_dari_antrean_berita_dan_skor"]),
    ("UC-05", "Hak akses analis", "Pengguna biasa mencoba mengoreksi", "Respons 403", "API",
     [A + "test_koreksi_oleh_pengguna_biasa_ditolak", A + "test_koreksi_tanpa_token_ditolak",
      A + "test_ruang_analis_tertutup_bagi_tamu_dan_pengguna_biasa", A + "test_tidak_relevan_hanya_untuk_analis"]),
    ("UC-06", "Menambah sumber berita", "URL RSS baru yang valid", "Sumber tersimpan dan aktif", "API",
     [A + "test_tambah_sumber_menolak_alamat_tidak_valid_dan_duplikat"]),
    ("UC-06 3a", "Alamat tidak valid atau terdaftar", "URL bukan http(s), atau domain yang sudah ada",
     "Ditolak dengan pesan", "API", [A + "test_tambah_sumber_menolak_alamat_tidak_valid_dan_duplikat"]),
    ("UC-06", "Menonaktifkan sumber", "Admin mematikan satu portal", "Cakupan di ringkasan berkurang", "API",
     [A + "test_menonaktifkan_sumber_mengurangi_cakupan"]),
    ("FR-8", "Kelola akun", "Admin membuat lalu menonaktifkan akun", "Akun bisa masuk, lalu tidak bisa",
     "API", [A + "test_kelola_akun", A + "test_admin_tidak_bisa_mengunci_dirinya_sendiri"]),
    ("FR-8", "Halaman admin terlindungi", "Analis membuka halaman admin", "Respons 403", "API",
     [A + "test_halaman_admin_hanya_untuk_admin", A + "test_admin_mencakup_hak_analis"]),
    ("FR-1", "Pengumpulan berita", "Feed RSS berisi berita baru dan duplikat",
     "Berita baru tersimpan; duplikat dan sindikasi dikenali", "unit",
     ["tests/test_pipeline.py::test_menyimpan_berita_dan_memetakan_emiten",
      "tests/test_pipeline.py::test_url_sama_tidak_disimpan_dua_kali",
      "tests/test_pipeline.py::test_artikel_sindikasi_dikenali_lewat_sidik_jari"]),
    ("FR-1", "Pemetaan emiten akurat", "Teks menyebut 'menghantam' / kode ambigu",
     "Tidak salah petakan ke ANTM / kode tanpa konteks pasar", "unit",
     ["tests/test_matcher.py::test_nama_emiten_harus_kata_utuh",
      "tests/test_matcher.py::test_kode_ambigu_ditolak_tanpa_konteks_pasar"]),
    ("FR-4", "Skor agregat tertimbang", "Berita dari portal tak terverifikasi dan artikel rekap",
     "Bobotnya lebih kecil daripada berita khusus terverifikasi", "unit",
     ["tests/test_agregasi.py::test_sumber_tak_terverifikasi_ditimbang_lebih_rendah",
      "tests/test_diagnosa.py::test_artikel_rekap_pasar_tidak_menggeser_skor_sekuat_berita_khusus"]),
    ("NF-03", "Keandalan saat satu sumber gagal", "Satu artikel/emiten gagal diproses",
     "Sisanya tetap diproses", "unit",
     ["tests/test_pengaya.py::test_galat_satu_artikel_tidak_menghentikan_sisanya",
      "tests/test_verifikasi.py::test_emiten_gagal_tidak_menghentikan_yang_lain"]),
    ("NF-04", "Keamanan kata sandi dan token", "Token dipalsukan / kedaluwarsa; sandi salah",
     "Ditolak; pesan galat tidak membocorkan email terdaftar", "API",
     [A + "test_token_palsu_ditolak", A + "test_masuk_sandi_salah",
      A + "test_pesan_galat_sama_untuk_email_tak_terdaftar", "tests/test_keamanan.py::test_token_kedaluwarsa_ditolak",
      "tests/test_keamanan.py::test_hash_tidak_memuat_kata_sandi"]),
    ("NF-09", "Etika pengumpulan", "robots.txt melarang; halaman artikel diambil",
     "Halaman tidak diambil; isi artikel tidak disimpan", "unit",
     ["tests/test_pengaya.py::test_robots_menolak_tidak_mengambil_halaman",
      "tests/test_pengaya.py::test_isi_artikel_tidak_disimpan"]),
]


def jalankan_pytest() -> tuple[dict[str, str], int, int]:
    """(nodeid -> 'lulus' | 'gagal' | 'dilewati', jumlah kasus uji, jumlah lulus).
    Uji berparameter dihitung per kasus, sama seperti ringkasan pytest."""
    with tempfile.TemporaryDirectory() as d:
        xml = Path(d) / "hasil.xml"
        subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={xml}"], capture_output=True)
        akar = ET.parse(xml).getroot()
    hasil = {}
    kasus = lulus_kasus = 0
    for tc in akar.iter("testcase"):
        berkas = tc.get("classname", "").replace(".", "/") + ".py"
        nama = tc.get("name", "").split("[")[0]
        status = "gagal" if tc.find("failure") is not None or tc.find("error") is not None else \
            "dilewati" if tc.find("skipped") is not None else "lulus"
        kasus += 1
        lulus_kasus += status == "lulus"
        kunci = f"{berkas}::{nama}"
        if hasil.get(kunci) != "gagal":  # uji berparameter: satu gagal = gagal
            hasil[kunci] = status
    return hasil, kasus, lulus_kasus


def main() -> None:
    hasil, total_uji, uji_lulus = jalankan_pytest()
    baris = []
    for kode, skenario, masukan, harapan, jenis, uji in SKENARIO:
        status = [hasil.get(u, "tidak ditemukan") for u in uji]
        akhir = "Lulus" if all(s == "lulus" for s in status) else "Gagal"
        baris.append((kode, skenario, masukan, harapan, jenis, akhir, uji))
    lulus = sum(b[5] == "Lulus" for b in baris)

    md = (f"# Laporan pengujian black-box\n\nDibuat {datetime.now():%Y-%m-%d %H:%M} dari hasil uji otomatis.\n\n"
          f"**{lulus} dari {len(baris)} skenario lulus** · {uji_lulus} dari {total_uji} uji otomatis lulus.\n\n"
          "| No | Kebutuhan | Skenario | Masukan | Hasil yang diharapkan | Jenis | Status |\n"
          "|---|---|---|---|---|---|---|\n"
          + "".join(f"| {i} | {k} | {s} | {m} | {h} | {j} | {a} |\n"
                    for i, (k, s, m, h, j, a, _) in enumerate(baris, 1))
          + "\n## Uji otomatis yang membuktikan tiap skenario\n\n"
          + "".join(f"- **{i}. {k} {s}**: " + ", ".join(f"`{u.split('::')[1]}`" for u in uji) + "\n"
                    for i, (k, s, _, _, _, _, uji) in enumerate(baris, 1)))
    LAPORAN.parent.mkdir(parents=True, exist_ok=True)
    LAPORAN.write_text(md, encoding="utf-8")

    sel = lambda t, b=False: f"<td>{'<b>' if b else ''}{escape(t)}{'</b>' if b else ''}</td>"  # noqa: E731
    html = ("<html><head><meta charset='utf-8'><style>body{font-family:Calibri;font-size:10.5pt}"
            "table{border-collapse:collapse;width:100%}td,th{border:1px solid #999;padding:4px;vertical-align:top}"
            "th{background:#e8eaf0}</style></head><body>"
            f"<h2>Laporan Pengujian Black-Box</h2><p>Dibuat {datetime.now():%d-%m-%Y %H:%M} dari hasil uji otomatis "
            f"({uji_lulus} dari {total_uji} uji lulus). {lulus} dari {len(baris)} skenario lulus.</p>"
            "<table><tr><th>No</th><th>Kebutuhan</th><th>Skenario</th><th>Masukan</th>"
            "<th>Hasil yang diharapkan</th><th>Jenis</th><th>Status</th></tr>"
            + "".join("<tr>" + sel(str(i)) + sel(k) + sel(s) + sel(m) + sel(h) + sel(j) + sel(a, True) + "</tr>"
                      for i, (k, s, m, h, j, a, _) in enumerate(baris, 1))
            + "</table></body></html>")
    LAPORAN.with_suffix(".html").write_text(html, encoding="utf-8")
    print(md)
    print(f"Tersimpan di {LAPORAN} (+ .html)")


if __name__ == "__main__":
    main()
