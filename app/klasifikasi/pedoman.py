"""Pedoman anotasi sentimen, dipakai bersama oleh anotator manusia
(scripts/label_manual.py) dan pelabel LLM (app/klasifikasi/llm.py).

Satu sumber teks untuk keduanya: kalau manusia dan LLM membaca pedoman yang
berbeda, kesepakatan atau ketidaksepakatan keduanya tidak bisa ditafsirkan —
yang terukur bisa jadi perbedaan pedoman, bukan perbedaan penilai.
"""

PEDOMAN = """
PEDOMAN — nilai dari sudut pandang investor emiten yang DITAMPILKAN, bukan
nada artikel secara umum. Bila satu berita menyebut beberapa emiten, tiap
emiten dinilai sendiri-sendiri.

  1 POSITIF  cenderung menaikkan penilaian investor terhadap emiten ini:
             laba/pendapatan naik, kontrak/proyek baru, dividen, buyback,
             rekomendasi beli, target harga naik, ekspansi, izin terbit.
  2 NETRAL   tanpa arah jelas bagi emiten ini: jadwal RUPS/pengumuman rutin,
             rekap pasar yang hanya menyebut emiten sekilas, berita campuran
             yang seimbang, fakta tanpa implikasi.
  3 NEGATIF  cenderung menurunkan penilaian: rugi/laba turun, gugatan, denda,
             suspensi, gagal bayar, rekomendasi jual, target harga turun,
             regulasi yang merugikan, harga anjlok karena masalah emiten.
  x TIDAK RELEVAN  berita sebenarnya tidak membahas emiten ini
             (mis. "bank mandiri" di iklan promo). Tidak dijadikan label.

Ragu antara netral dan yang lain? Pilih netral. Konsistensi lebih penting
daripada ketepatan satu-dua berita.
"""
