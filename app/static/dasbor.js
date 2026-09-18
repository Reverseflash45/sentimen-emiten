/* Dasbor sentimen emiten.
   Grafik digambar sendiri dengan SVG — tanpa pustaka luar, supaya dasbor tetap
   jalan saat demo tanpa internet. */

const $ = (s) => document.querySelector(s);
const el = (t, a = {}, anak = []) => {
  const n = document.createElement(t);
  for (const [k, v] of Object.entries(a)) {
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else n.setAttribute(k, v);
  }
  for (const c of [].concat(anak)) n.append(c);
  return n;
};

const state = { kode: null, emiten: [], token: null, saya: null, cakupan: null };

/* Token disimpan di memori halaman saja, bukan di localStorage: sesi berakhir
   saat tab ditutup, dan token tidak bisa dibaca skrip lain yang kebetulan
   berjalan di origin yang sama. */
function kepala() {
  return state.token ? { Authorization: `Bearer ${state.token}` } : {};
}

async function ambil(url, opsi = {}) {
  const r = await fetch(url, { ...opsi, headers: { ...kepala(), ...(opsi.headers || {}) } });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail || `${r.status} ${r.statusText}`);
  }
  return r.json();
}

function galat(pesan) {
  const g = $("#galat");
  g.hidden = !pesan;
  g.textContent = pesan || "";
}

function kosong(judul, penjelasan) {
  return el("div", { class: "kosong" }, [
    el("strong", {}, judul),
    el("span", {}, penjelasan),
  ]);
}

function memuat(wadah, teks = "Memuat\u2026") {
  wadah.innerHTML = "";
  wadah.append(el("p", { class: "ket memuat" }, teks));
}

/* ---------- ringkasan ---------- */

async function muatRingkasan() {
  const r = await ambil("/api/ringkasan");
  const kartu = [
    ["Emiten dipantau", r.jumlah_emiten],
    ["Sumber berita", r.jumlah_sumber],
    ["Berita terkumpul", r.jumlah_berita],
    ["Sudah berlabel", r.jumlah_berlabel],
    ["Antre klasifikasi", r.jumlah_belum_diklasifikasi],
  ];
  const wadah = $("#ringkasan");
  wadah.innerHTML = "";
  for (const [label, angka] of kartu) {
    wadah.append(
      el("div", { class: angka ? "kartu" : "kartu sepi" }, [
        el("div", { class: "angka" }, String(angka)),
        el("div", { class: "label" }, label),
      ])
    );
  }
}

async function muatDaftarEmiten() {
  state.emiten = await ambil("/api/emiten");
  const sel = $("#cari");
  const terpilih = sel.value;
  sel.innerHTML = "";
  sel.append(el("option", { value: "" }, "\u2014 pilih emiten \u2014"));
  for (const e of state.emiten) {
    sel.append(el("option", { value: e.kode }, `${e.kode} \u2014 ${e.nama}`));
  }
  if (terpilih) sel.value = terpilih;
}

/* ---------- grafik ---------- */

const NS = "http://www.w3.org/2000/svg";
const svgEl = (t, a) => {
  const n = document.createElementNS(NS, t);
  for (const [k, v] of Object.entries(a)) n.setAttribute(k, v);
  return n;
};

function gambarGrafik(sentimen, harga) {
  const wadah = $("#grafik");
  wadah.innerHTML = "";

  const tanggal = [...new Set([...sentimen.map((d) => d.tanggal), ...harga.map((d) => d.tanggal)])].sort();
  if (!tanggal.length) {
    wadah.append(kosong("Belum ada data pada rentang ini",
                        "Coba pintasan rentang \u201cSemua\u201d di atas."));
    return;
  }

  const W = 900, H = 320, P = { atas: 18, kanan: 56, bawah: 34, kiri: 52 };
  const lebar = W - P.kiri - P.kanan;
  const tinggi = H - P.atas - P.bawah;
  const x = (t) => P.kiri + (tanggal.indexOf(t) / Math.max(1, tanggal.length - 1)) * lebar;

  const hargaNilai = harga.map((d) => d.penutupan).filter((v) => v != null);
  const hMin = hargaNilai.length ? Math.min(...hargaNilai) : 0;
  const hMax = hargaNilai.length ? Math.max(...hargaNilai) : 1;
  const bantal = (hMax - hMin) * 0.12 || 1;
  const yHarga = (v) => P.atas + tinggi - ((v - (hMin - bantal)) / ((hMax + bantal) - (hMin - bantal))) * tinggi;
  const ySent = (v) => P.atas + tinggi / 2 - (v * tinggi) / 2;

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });

  // garis nol sentimen
  svg.append(svgEl("line", {
    x1: P.kiri, x2: P.kiri + lebar, y1: ySent(0), y2: ySent(0),
    stroke: "#242a31", "stroke-dasharray": "4 4",
  }));

  // sumbu kiri (sentimen)
  for (const v of [1, 0.5, 0, -0.5, -1]) {
    const y = ySent(v);
    const t = svgEl("text", { x: P.kiri - 9, y: y + 4, fill: "#8b8f99", "font-size": "11", "text-anchor": "end" });
    t.textContent = v.toFixed(1);
    svg.append(t);
  }
  // sumbu kanan (harga)
  if (hargaNilai.length) {
    for (const frac of [0, 0.5, 1]) {
      const v = hMin + (hMax - hMin) * frac;
      const t = svgEl("text", { x: P.kiri + lebar + 9, y: yHarga(v) + 4, fill: "#8b8f99", "font-size": "11" });
      t.textContent = Math.round(v).toLocaleString("id-ID");
      svg.append(t);
    }
  }

  // batang jumlah berita
  const maksBerita = Math.max(1, ...sentimen.map((d) => d.jumlah_berita));
  for (const d of sentimen) {
    const tinggiBatang = (d.jumlah_berita / maksBerita) * 34;
    svg.append(svgEl("rect", {
      x: x(d.tanggal) - 3, y: P.atas + tinggi - tinggiBatang, width: 6, height: tinggiBatang,
      fill: "#5eead4", opacity: "0.16", rx: "2",
    }));
  }

  const jalur = (titik, fx, fy, warna) => {
    if (titik.length < 2) return;
    const d = titik.map((p, i) => `${i ? "L" : "M"}${fx(p).toFixed(1)},${fy(p).toFixed(1)}`).join(" ");
    svg.append(svgEl("path", { d, fill: "none", stroke: warna, "stroke-width": "2", "stroke-linejoin": "round" }));
    for (const p of titik) {
      svg.append(svgEl("circle", { cx: fx(p), cy: fy(p), r: "2.6", fill: warna }));
    }
  };

  const hargaValid = harga.filter((d) => d.penutupan != null);
  jalur(hargaValid, (p) => x(p.tanggal), (p) => yHarga(p.penutupan), "#fbbf24");
  jalur(sentimen, (p) => x(p.tanggal), (p) => ySent(p.skor), "#5eead4");

  // label tanggal (maksimal 6 supaya tidak tumpang tindih)
  const langkah = Math.max(1, Math.ceil(tanggal.length / 6));
  tanggal.forEach((t, i) => {
    if (i % langkah) return;
    const teks = svgEl("text", {
      x: x(t), y: H - 12, fill: "#8b8f99", "font-size": "11", "text-anchor": "middle",
    });
    teks.textContent = t.slice(5);
    svg.append(teks);
  });

  wadah.append(svg);
}

function tampilkanKorelasi(k) {
  const wadah = $("#korelasi");
  wadah.innerHTML = "";

  if (k.catatan) {
    wadah.append(el("p", { class: "peringatan" }, k.catatan));
  }
  const kotak = (judul, kor) =>
    el("div", { class: "kotak" }, [
      el("div", { class: "ket" }, judul),
      el("div", { class: "nilai" }, kor ? (kor.koefisien > 0 ? "+" : "") + kor.koefisien.toFixed(4) : "—"),
      el("div", { class: "ket" }, kor ? `${kor.kekuatan} · n=${kor.n}` : "belum cukup data"),
    ]);

  wadah.append(kotak("Pearson (linear)", k.pearson));
  wadah.append(kotak("Spearman (monoton)", k.spearman));
  const saring = k.maks_emiten_per_berita
    ? `maks ${k.maks_emiten_per_berita} emiten/berita`
    : "semua berita";
  wadah.append(
    el("div", { class: "kotak" }, [
      el("div", { class: "ket" }, "Hari beririsan"),
      el("div", { class: "nilai" }, String(k.hari_beririsan)),
      el("div", { class: "ket" }, `lag ${k.lag} hari · ${saring}`),
    ])
  );
  if (k.maks_emiten_per_berita) {
    wadah.append(
      el("p", { class: "peringatan" },
        "Artikel rekap pasar sedang dibuang. Bandingkan dengan hasil tanpa " +
        "saringan: korelasi yang hanya muncul saat rekap diikutkan menandakan " +
        "yang terukur adalah pergerakan indeks, bukan sentimen per emiten.")
    );
  }
  wadah.append(el("p", { class: "peringatan" }, k.peringatan));
}

/* ---------- berita ---------- */

function lencanaLabel(label) {
  if (!label) return el("span", { class: "lencana kosong" }, "belum dilabeli");
  const teks = `${label.sentimen} ${(label.keyakinan * 100).toFixed(0)}%`;
  return el("span", { class: `lencana ${label.sentimen}` }, teks);
}

const NAMA_STATUS = {
  terkonfirmasi_resmi: "terkonfirmasi resmi",
  rumor_belum_terkonfirmasi: "rumor",
  belum_diperiksa: "belum diperiksa",
};

async function muatBerita() {
  if (!state.kode) return;
  const p = new URLSearchParams({ kode: state.kode, limit: "30" });
  const s = $("#saring-sentimen").value;
  const st = $("#saring-status").value;
  if (s) p.set("sentimen", s);
  if (st) p.set("status", st);

  const wadah = $("#berita");
  memuat(wadah);
  const daftar = await ambil(`/api/berita?${p}`);
  wadah.innerHTML = "";
  if (!daftar.length) {
    wadah.append(kosong(
      "Tidak ada berita yang cocok",
      "Longgarkan saringan sentimen atau status, atau perlebar rentang tanggalnya."
    ));
    return;
  }

  for (const b of daftar) {
    const tgl = b.terbit_pada ? new Date(b.terbit_pada).toLocaleDateString("id-ID") : "tanggal tidak diketahui";
    const aksi = el("div", { class: "aksi" });
    for (const s of state.saya && state.saya.peran === "analis"
      ? ["positif", "netral", "negatif"]
      : []) {
      const tombol = el("button", { class: "kecil" }, `koreksi: ${s}`);
      tombol.onclick = async () => {
        tombol.disabled = true;
        try {
          await fetch(`/api/berita/${b.id}/koreksi`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ kode_emiten: state.kode, sentimen: s }),
            headers: { "Content-Type": "application/json", ...kepala() },
          });
          await muatBerita();
          await muatEmiten(false);
        } finally {
          tombol.disabled = false;
        }
      };
      aksi.append(tombol);
    }

    const jejak = el("div", { class: "jejak", hidden: "hidden" });
    const lihat = el("button", { class: "kecil" }, "dasar verifikasi");
    lihat.onclick = async () => {
      if (!jejak.hidden) { jejak.hidden = true; return; }
      jejak.innerHTML = "";
      try {
        const daftar = await ambil(`/api/berita/${b.id}/jejak`);
        if (!daftar.length) {
          jejak.append(el("div", {}, "Belum pernah diperiksa."));
        }
        for (const j of daftar) {
          const baris = el("div", {}, [
            el("span", {}, `${NAMA_STATUS[j.status] || j.status} — ${j.alasan}`),
          ]);
          if (j.pengumuman) {
            baris.append(" ");
            baris.append(
              el("a", { href: j.pengumuman.url, target: "_blank", rel: "noreferrer" },
                 "pengumuman resmi")
            );
          }
          jejak.append(baris);
        }
        jejak.hidden = false;
      } catch (e) {
        jejak.textContent = e.message;
        jejak.hidden = false;
      }
    };
    aksi.append(lihat);

    const isi = el("div", { class: "isi" }, [
      el("a", { class: "judul", href: b.url, target: "_blank", rel: "noreferrer" }, b.judul),
      el("div", { class: "meta" }, [
        el("span", {}, b.sumber),
        el("span", {}, tgl),
        el("span", {}, NAMA_STATUS[b.status_verifikasi] || b.status_verifikasi),
        el("span", {}, b.emiten.join(", ")),
        ...(b.label && b.label.asal === "analis" ? [el("span", { class: "lencana analis" }, "dikoreksi analis")] : []),
      ]),
      aksi,
      jejak,
    ]);

    wadah.append(el("div", { class: "berita-item" }, [lencanaLabel(b.label), isi]));
  }
}

/* ---------- ikhtisar seluruh emiten ---------- */

const KOLOM = [
  { kunci: "kode", label: "Kode", kiri: true },
  { kunci: "nama", label: "Nama", kiri: true },
  { kunci: "sektor", label: "Sektor", kiri: true },
  { kunci: "skor", label: "Skor sentimen" },
  { kunci: "jumlah_berita", label: "Berita" },
  { kunci: "jumlah_positif", label: "Pos" },
  { kunci: "jumlah_negatif", label: "Neg" },
  { kunci: "harga_terakhir", label: "Harga" },
  { kunci: "perubahan_harga", label: "Ubah %" },
];

const urut = { kunci: null, naik: false };

function selSkor(skor) {
  const td = el("td", {});
  if (skor == null) {
    td.className = "sepi";
    td.textContent = "—";
    return td;
  }
  const lebar = Math.max(2, Math.abs(skor) * 46);
  const warna = skor > 0.05 ? "var(--positif)" : skor < -0.05 ? "var(--negatif)" : "var(--netral)";
  const bar = el("i", { class: "bar-skor" });
  bar.style.width = `${lebar}px`;
  bar.style.background = warna;
  td.append(`${skor > 0 ? "+" : ""}${skor.toFixed(2)} `, bar);
  return td;
}

function gambarPeringkat(baris) {
  const wadah = $("#peringkat");
  wadah.innerHTML = "";
  if (!baris.length) {
    wadah.append(kosong(
      "Belum ada emiten dengan berita pada rentang ini",
      $("#hanya-berberita").checked
        ? "Hilangkan centang \u201chanya yang ada beritanya\u201d untuk melihat seluruh emiten, atau perlebar rentang tanggalnya."
        : "Jalankan python -m scripts.siklus_harian untuk mengumpulkan berita."
    ));
    return;
  }

  if (urut.kunci) {
    baris = [...baris].sort((a, b) => {
      const x = a[urut.kunci], y = b[urut.kunci];
      if (x == null) return 1;
      if (y == null) return -1;
      const d = typeof x === "string" ? x.localeCompare(y) : x - y;
      return urut.naik ? d : -d;
    });
  }

  const tabel = el("table", { class: "peringkat" });
  const thead = el("thead");
  const trh = el("tr");
  for (const k of KOLOM) {
    const panah = urut.kunci === k.kunci ? (urut.naik ? " \u2191" : " \u2193") : "";
    const th = el("th", k.kiri ? { class: "kiri" } : {}, k.label + panah);
    th.onclick = () => {
      if (urut.kunci === k.kunci) urut.naik = !urut.naik;
      else { urut.kunci = k.kunci; urut.naik = false; }
      gambarPeringkat(baris);
    };
    trh.append(th);
  }
  thead.append(trh);
  tabel.append(thead);

  const tbody = el("tbody");
  for (const b of baris) {
    const tr = el("tr", { tabindex: "0", role: "button",
                          "aria-label": `Lihat detail ${b.kode}` });
    tr.append(el("td", { class: "kiri kode" }, b.kode));
    tr.append(el("td", { class: "kiri nama" }, b.nama));
    tr.append(el("td", { class: "kiri" }, b.sektor || "—"));
    tr.append(selSkor(b.skor));
    tr.append(el("td", b.jumlah_berita ? {} : { class: "sepi" }, String(b.jumlah_berita)));
    tr.append(el("td", {}, String(b.jumlah_positif)));
    tr.append(el("td", {}, String(b.jumlah_negatif)));
    tr.append(el("td", {}, b.harga_terakhir == null ? "—"
      : b.harga_terakhir.toLocaleString("id-ID")));
    const u = b.perubahan_harga;
    tr.append(el("td", { class: u == null ? "sepi" : u > 0 ? "naik" : u < 0 ? "turun" : "" },
      u == null ? "—" : `${u > 0 ? "+" : ""}${u.toFixed(2)}%`));
    const buka = () => {
      $("#cari").value = b.kode;
      muatEmiten();
      $("#panel-grafik").scrollIntoView({ behavior: "smooth", block: "start" });
    };
    tr.onclick = buka;
    tr.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); buka(); }
    };
    tbody.append(tr);
  }
  tabel.append(tbody);
  wadah.append(tabel);
}

async function muatPeringkat() {
  memuat($("#peringkat"));
  const p = new URLSearchParams();
  if ($("#mulai").value) p.set("mulai", $("#mulai").value);
  if ($("#sampai").value) p.set("sampai", $("#sampai").value);
  if ($("#maks-emiten").value) p.set("maks_emiten_per_berita", $("#maks-emiten").value);
  if ($("#hanya-berberita").checked) p.set("hanya_berberita", "true");
  try {
    const d = await ambil(`/api/peringkat?${p}`);
    gambarPeringkat(d.baris);
  } catch (e) {
    galat(e.message);
  }
}

/* ---------- akun & watchlist ---------- */

function perbaruiAkun() {
  const masuk = Boolean(state.saya);
  $("#siapa").textContent = masuk ? `${state.saya.nama} · ${state.saya.peran}` : "";
  $("#tombol-masuk").textContent = masuk ? "Keluar" : "Masuk";
  $("#panel-watchlist").hidden = !masuk;
  if (masuk) $("#panel-masuk").hidden = true;
  // tombol koreksi hanya berguna bagi analis
  document.body.dataset.peran = masuk ? state.saya.peran : "tamu";
}

async function kirimMasuk() {
  const g = $("#galat-masuk");
  g.hidden = true;
  try {
    const r = await fetch("/api/auth/masuk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: $("#masuk-email").value.trim(),
        kata_sandi: $("#masuk-sandi").value,
      }),
    });
    const b = await r.json();
    if (!r.ok) throw new Error(b.detail || "gagal masuk");
    state.token = b.token;
    $("#masuk-sandi").value = "";
    state.saya = await ambil("/api/auth/saya");
    perbaruiAkun();
    await muatWatchlist();
    if (state.kode) await muatBerita();
  } catch (e) {
    g.textContent = e.message;
    g.hidden = false;
  }
}

function keluar() {
  state.token = null;
  state.saya = null;
  perbaruiAkun();
  $("#watchlist").innerHTML = "";
}

async function muatWatchlist() {
  if (!state.saya) return;
  const daftar = await ambil("/api/watchlist");
  const wadah = $("#watchlist");
  wadah.innerHTML = "";
  if (!daftar.length) {
    wadah.append(el("p", { class: "ket" }, "Belum ada emiten. Pilih emiten lalu klik tambah."));
    return;
  }
  for (const w of daftar) {
    const skor = w.skor_terakhir;
    const kelas = skor == null ? "" : skor > 0 ? " naik" : skor < 0 ? " turun" : "";
    const kode = el("span", { class: "wl-kode" }, w.kode);
    kode.onclick = () => { $("#cari").value = w.kode; muatEmiten(); };

    const buang = el("button", { class: "kecil" }, "hapus");
    buang.onclick = async () => {
      await ambil(`/api/watchlist/${w.kode}`, { method: "DELETE" });
      await muatWatchlist();
    };

    wadah.append(
      el("div", { class: "wl-item" }, [
        kode,
        el("span", { class: "wl-nama" }, w.nama),
        el("span", { class: `wl-angka${kelas}` },
           skor == null ? "skor —" : `skor ${skor > 0 ? "+" : ""}${skor.toFixed(2)}`),
        el("span", { class: "wl-angka" }, `${w.berita_7_hari} berita/7h`),
        el("span", { class: "wl-angka" },
           w.harga_terakhir == null ? "—" : w.harga_terakhir.toLocaleString("id-ID")),
        buang,
      ])
    );
  }
}

async function tambahKeWatchlist() {
  if (!state.saya || !state.kode) return galat("Pilih emiten dulu.");
  await ambil("/api/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kode_emiten: state.kode }),
  });
  await muatWatchlist();
}

/* ---------- alur utama ---------- */

async function muatEmiten(gantiJudul = true) {
  const kode = $("#cari").value;
  if (!kode) return;
  state.kode = kode;

  const p = new URLSearchParams();
  if ($("#mulai").value) p.set("mulai", $("#mulai").value);
  if ($("#sampai").value) p.set("sampai", $("#sampai").value);
  const pk = new URLSearchParams(p);
  pk.set("lag", $("#lag").value);
  if ($("#maks-emiten").value) pk.set("maks_emiten_per_berita", $("#maks-emiten").value);

  galat("");
  try {
    const [detail, sentimen, harga, kor] = await Promise.all([
      ambil(`/api/emiten/${kode}`),
      ambil(`/api/emiten/${kode}/sentimen?${p}`),
      ambil(`/api/emiten/${kode}/harga?${p}`),
      ambil(`/api/emiten/${kode}/korelasi?${pk}`),
    ]);

    if (gantiJudul) {
      $("#judul-emiten").textContent = `${detail.kode} — ${detail.nama}${detail.sektor ? " · " + detail.sektor : ""}`;
    }
    $("#panel-grafik").hidden = false;
    $("#panel-berita").hidden = false;
    $("#petunjuk").hidden = true;
    gambarGrafik(sentimen.titik, harga.titik);

    /* Grafik yang timpang bukan grafik yang rusak. Tanpa keterangan ini,
       garis harga panjang di sebelah satu titik sentimen terbaca sebagai
       kesalahan tampilan, padahal itu keadaan datanya. */
    const catatan = $("#catatan-grafik");
    if (sentimen.titik.length && harga.titik.length &&
        sentimen.titik.length < harga.titik.length / 4) {
      catatan.textContent =
        `Sentimen baru tersedia ${sentimen.titik.length} hari, harga ${harga.titik.length} hari. ` +
        "Korelasi baru berarti setelah deret sentimennya cukup panjang.";
      catatan.hidden = false;
    } else {
      catatan.hidden = true;
    }

    tampilkanKorelasi(kor);
    await muatBerita();
  } catch (e) {
    galat(e.message);
  }
}

const iso = (d) => d.toISOString().slice(0, 10);

function pasangRentang(mulai, sampai, tombol) {
  $("#mulai").value = mulai;
  $("#sampai").value = sampai;
  for (const b of document.querySelectorAll("#pintasan button")) {
    b.classList.toggle("aktif", b === tombol);
  }
  muatPeringkat();
  if (state.kode) muatEmiten(false);
}

function tanggalAwal() {
  const kini = new Date();
  $("#sampai").value = iso(kini);
  $("#mulai").value = iso(new Date(kini.getTime() - 30 * 86400000));
  document.querySelector('#pintasan button[data-hari="30"]')?.classList.add("aktif");
}

async function muatCakupanData() {
  try {
    state.cakupan = await ambil("/api/rentang-data");
  } catch {
    return;
  }
  const c = state.cakupan;
  if (!c.mulai) return;
  $("#cakupan-data").textContent =
    `Data tersedia: berita ${c.berita_mulai || "—"} s/d ${c.berita_sampai || "—"} · ` +
    `harga ${c.harga_mulai || "—"} s/d ${c.harga_sampai || "—"}`;
}

function pasangPintasan() {
  for (const b of document.querySelectorAll("#pintasan button")) {
    b.onclick = () => {
      const kini = new Date();
      if (b.dataset.hari) {
        pasangRentang(
          iso(new Date(kini.getTime() - Number(b.dataset.hari) * 86400000)),
          iso(kini), b
        );
      } else if (b.dataset.ytd) {
        pasangRentang(`${kini.getFullYear()}-01-01`, iso(kini), b);
      } else if (b.dataset.semua) {
        const c = state.cakupan;
        if (!c || !c.mulai) return galat("Belum ada data sama sekali.");
        pasangRentang(c.mulai, c.sampai, b);
      }
    };
  }
}

(async function mulai() {
  tanggalAwal();
  pasangPintasan();
  $("#muat").onclick = () => { muatEmiten(); muatPeringkat(); };
  $("#hanya-berberita").onchange = muatPeringkat;
  $("#tombol-masuk").onclick = () => {
    if (state.saya) return keluar();
    $("#panel-masuk").hidden = !$("#panel-masuk").hidden;
  };
  $("#kirim-masuk").onclick = kirimMasuk;
  $("#masuk-sandi").addEventListener("keydown", (e) => { if (e.key === "Enter") kirimMasuk(); });
  $("#tambah-watchlist").onclick = tambahKeWatchlist;
  perbaruiAkun();
  $("#cari").addEventListener("change", () => {
    if ($("#cari").value) muatEmiten();
  });
  $("#maks-emiten").onchange = () => {
    muatPeringkat();
    if (state.kode) muatEmiten(false);
  };
  $("#saring-sentimen").onchange = muatBerita;
  $("#saring-status").onchange = muatBerita;
  try {
    await Promise.all([
      muatRingkasan(), muatDaftarEmiten(), muatCakupanData(), muatPeringkat(),
    ]);
  } catch (e) {
    galat(e.message);
  }
})();
