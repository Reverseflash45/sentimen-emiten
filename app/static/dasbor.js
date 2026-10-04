/* Dasbor sentimen emiten.
   Grafik digambar sendiri dengan SVG — tanpa pustaka luar, supaya dasbor tetap
   jalan saat demo tanpa internet. */

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const el = (t, a = {}, anak = []) => {
  const n = document.createElement(t);
  for (const [k, v] of Object.entries(a)) {
    if (k === "class") n.className = v;
    else n.setAttribute(k, v);
  }
  for (const c of [].concat(anak)) if (c != null) n.append(c);
  return n;
};

const state = {
  kode: null, emiten: [], token: null, saya: null, cakupan: null,
  baris: [], grafik: null,
  satuan: "harian", satuanManual: false,
  watchlist: new Set(),
  analis: { tab: "label", offset: 0 },
};

const fmtAngka = (v) => v.toLocaleString("id-ID");
const fmtSkor = (v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}`;
const fmtPersen = (v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
const tglLokal = (t) => new Date(`${t}T00:00:00`);
const fmtTgl = (t, opsi) => tglLokal(t).toLocaleDateString("id-ID", opsi);
const kelasArah = (v) => (v == null ? "" : v > 0 ? "naik" : v < 0 ? "turun" : "");
const warnaSkor = (s) => (s > 0.05 ? "var(--positif)" : s < -0.05 ? "var(--negatif)" : "var(--netral)");
const WARNA_SENTIMEN = { positif: "var(--positif)", netral: "var(--netral)", negatif: "var(--negatif)" };

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
const kirimJson = (url, badan, metode = "POST") =>
  ambil(url, { method: metode, headers: { "Content-Type": "application/json" }, body: JSON.stringify(badan) });

function galat(pesan) {
  const g = $("#galat");
  g.hidden = !pesan;
  g.textContent = pesan || "";
}

let tundaToast;
function toast(pesan, jenis = "sukses") {
  const t = $("#toast");
  t.textContent = pesan;
  t.className = `toast ${jenis}`;
  t.hidden = false;
  clearTimeout(tundaToast);
  tundaToast = setTimeout(() => { t.hidden = true; }, 2600);
}

const layarLebar = () => window.matchMedia("(min-width: 1081px)").matches;

function ikon(d) {
  const s = svgEl("svg", { viewBox: "0 0 20 20", "aria-hidden": "true" });
  s.append(svgEl("path", { d }));
  return s;
}
const ikonBintang = () => ikon("M10 2.8l2.2 4.6 5 .7-3.6 3.5.9 5-4.5-2.4-4.5 2.4.9-5L2.8 8.1l5-.7z");
const ikonSilang = () => ikon("M5 5l10 10M15 5L5 15");

function kosong(judul, penjelasan) {
  return el("div", { class: "kosong" }, [el("strong", {}, judul), el("span", {}, penjelasan)]);
}

function memuat(wadah, teks = "Memuat…") {
  wadah.innerHTML = "";
  wadah.append(el("p", { class: "ket memuat" }, teks));
}

/* ---------- ringkasan ---------- */

async function muatRingkasan() {
  const r = await ambil("/api/ringkasan");
  const bagian = [
    [r.jumlah_emiten, "emiten LQ45"],
    [r.jumlah_berita, "berita"],
    [r.jumlah_berlabel, "berlabel"],
    [r.jumlah_sumber, "portal"],
  ];
  const wadah = $("#ringkasan");
  wadah.innerHTML = "";
  bagian.forEach(([angka, label], i) => {
    if (i) wadah.append(el("span", { class: "pisah", "aria-hidden": "true" }, "/"));
    wadah.append(el("span", {}, [el("b", {}, fmtAngka(angka)), ` ${label}`]));
  });
  const aktif = (r.emiten_teraktif || []).slice(0, 8);
  if (aktif.length) {
    const baris = $("#chip-teraktif");
    baris.innerHTML = "";
    for (const e of aktif) {
      const chip = el("button", { class: "chip", title: e.nama }, [e.kode, el("span", {}, String(e.jumlah_berita))]);
      chip.onclick = () => pilihEmiten(e.kode);
      baris.append(chip);
    }
    $("#teraktif").hidden = false;
  }
  return r;
}

/* ---------- pencarian emiten (combobox) ---------- */

async function muatDaftarEmiten() {
  state.emiten = await ambil("/api/emiten");
  const sel = $("#analis-emiten");
  for (const e of state.emiten) sel.append(el("option", { value: e.kode }, `${e.kode} — ${e.nama}`));
}

/* Peringkat kecocokan: kode yang diawali kueri paling atas, lalu awal kata
   pada nama, lalu kemunculan di mana saja (nama/sektor). */
function cariEmiten(q) {
  q = q.trim().toLowerCase();
  if (!q) return state.emiten.slice(0, 8).map((e) => ({ e, nilai: 0 }));
  const hasil = [];
  for (const e of state.emiten) {
    const kode = e.kode.toLowerCase();
    const nama = e.nama.toLowerCase();
    let nilai = null;
    if (kode === q) nilai = 0;
    else if (kode.startsWith(q)) nilai = 1;
    else if (nama.split(/[\s()]+/).some((k) => k.startsWith(q))) nilai = 2;
    else if (nama.includes(q) || kode.includes(q)) nilai = 3;
    else if ((e.sektor || "").toLowerCase().includes(q)) nilai = 4;
    if (nilai != null) hasil.push({ e, nilai });
  }
  return hasil.sort((a, b) => a.nilai - b.nilai || a.e.kode.localeCompare(b.e.kode)).slice(0, 8);
}

function tandai(teks, q) {
  const i = q ? teks.toLowerCase().indexOf(q.trim().toLowerCase()) : -1;
  if (i < 0 || !q.trim()) return [teks];
  const n = q.trim().length;
  return [teks.slice(0, i), el("mark", {}, teks.slice(i, i + n)), teks.slice(i + n)];
}

const combo = { daftar: [], aktif: -1 };

function tampilkanSaran() {
  const input = $("#cari");
  const q = input.value;
  combo.daftar = cariEmiten(q);
  combo.aktif = combo.daftar.length ? 0 : -1;
  const ul = $("#saran");
  ul.innerHTML = "";
  if (!combo.daftar.length) {
    ul.append(el("li", { class: "kosong-saran", role: "option", "aria-disabled": "true" }, `Tidak ada emiten yang cocok dengan “${q}”`));
  }
  combo.daftar.forEach(({ e }, i) => {
    const li = el("li", { role: "option", id: `saran-${i}`, "aria-selected": String(i === combo.aktif) }, [
      el("span", { class: "s-kode" }, tandai(e.kode, q)),
      el("span", { class: "s-nama" }, tandai(e.nama, q)),
      el("span", { class: "s-sektor" }, e.sektor || ""),
    ]);
    li.addEventListener("mousedown", (ev) => { ev.preventDefault(); pilihEmiten(e.kode); });
    ul.append(li);
  });
  ul.hidden = false;
  input.setAttribute("aria-expanded", "true");
  input.setAttribute("aria-activedescendant", combo.aktif >= 0 ? `saran-${combo.aktif}` : "");
}

function tutupSaran() {
  $("#saran").hidden = true;
  $("#cari").setAttribute("aria-expanded", "false");
}

function geserSaran(arah) {
  if (!combo.daftar.length) return;
  combo.aktif = (combo.aktif + arah + combo.daftar.length) % combo.daftar.length;
  $$("#saran li[role=option]").forEach((li, i) => li.setAttribute("aria-selected", String(i === combo.aktif)));
  $(`#saran-${combo.aktif}`)?.scrollIntoView({ block: "nearest" });
  $("#cari").setAttribute("aria-activedescendant", `saran-${combo.aktif}`);
}

function pasangPencarian() {
  const input = $("#cari");
  input.addEventListener("input", tampilkanSaran);
  input.addEventListener("focus", () => { input.select(); tampilkanSaran(); });
  input.addEventListener("blur", () => setTimeout(() => {
    tutupSaran();
    // teks yang diketik tapi tidak dipilih dikembalikan ke emiten aktif
    input.value = state.kode ? labelEmiten(state.kode) : "";
  }, 120));
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); if ($("#saran").hidden) tampilkanSaran(); else geserSaran(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); geserSaran(-1); }
    else if (e.key === "Enter") {
      e.preventDefault();
      const pilihan = combo.daftar[combo.aktif];
      if (pilihan) { pilihEmiten(pilihan.e.kode); input.blur(); }
    } else if (e.key === "Escape") { tutupSaran(); input.blur(); }
  });
  // "/" di mana saja langsung ke pencarian, seperti di GitHub dan YouTube
  document.addEventListener("keydown", (e) => {
    if (e.key !== "/" || e.ctrlKey || e.metaKey) return;
    const t = e.target;
    if (t.matches("input, textarea, select") || t.isContentEditable) return;
    e.preventDefault();
    input.focus();
  });
}

const labelEmiten = (kode) => {
  const e = state.emiten.find((x) => x.kode === kode);
  return e ? `${e.kode} — ${e.nama}` : kode;
};

/* ---------- agregasi per satuan waktu ---------- */

const SATUAN = {
  harian: { kunci: (t) => t, label: (t) => fmtTgl(t, { day: "numeric", month: "short" }),
            panjang: (t) => fmtTgl(t, { weekday: "short", day: "numeric", month: "long", year: "numeric" }) },
  mingguan: {
    kunci: (t) => { const d = tglLokal(t); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); return isoLokal(d); },
    label: (t) => fmtTgl(t, { day: "numeric", month: "short" }),
    panjang: (t) => { const a = tglLokal(t); const b = new Date(a); b.setDate(a.getDate() + 6);
      return `Minggu ${a.toLocaleDateString("id-ID", { day: "numeric", month: "short" })} – ${b.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" })}`; },
  },
  bulanan: { kunci: (t) => `${t.slice(0, 7)}-01`, label: (t) => fmtTgl(t, { month: "short", year: "2-digit" }),
             panjang: (t) => fmtTgl(t, { month: "long", year: "numeric" }) },
  tahunan: { kunci: (t) => `${t.slice(0, 4)}-01-01`, label: (t) => t.slice(0, 4), panjang: (t) => `Tahun ${t.slice(0, 4)}` },
};
const NAMA_SATUAN = { harian: "harian", mingguan: "mingguan", bulanan: "bulanan", tahunan: "tahunan" };

function isoLokal(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/* Skor periode = rata-rata skor harian berbobot jumlah berita (hari ramai
   berita lebih berpengaruh). Harga periode = harga penutupan terakhirnya. */
function agregasi(sentimen, harga, satuan) {
  const k = SATUAN[satuan].kunci;
  const s = new Map();
  for (const d of sentimen) {
    const kunci = k(d.tanggal);
    const a = s.get(kunci) || { tanggal: kunci, bobot: 0, jumlah_berita: 0, jumlah_positif: 0, jumlah_netral: 0, jumlah_negatif: 0 };
    a.bobot += d.skor * d.jumlah_berita;
    a.jumlah_berita += d.jumlah_berita;
    a.jumlah_positif += d.jumlah_positif;
    a.jumlah_netral += d.jumlah_netral;
    a.jumlah_negatif += d.jumlah_negatif;
    s.set(kunci, a);
  }
  const hasilS = [...s.values()].map((a) => ({ ...a, skor: a.jumlah_berita ? a.bobot / a.jumlah_berita : 0 }))
    .sort((a, b) => a.tanggal.localeCompare(b.tanggal));
  const h = new Map();
  for (const d of [...harga].sort((a, b) => a.tanggal.localeCompare(b.tanggal))) {
    if (d.penutupan != null) h.set(k(d.tanggal), { tanggal: k(d.tanggal), penutupan: d.penutupan });
  }
  return { sentimen: hasilS, harga: [...h.values()].sort((a, b) => a.tanggal.localeCompare(b.tanggal)) };
}

function satuanOtomatis() {
  const hari = (tglLokal($("#sampai").value) - tglLokal($("#mulai").value)) / 86400000;
  return hari <= 45 ? "harian" : hari <= 200 ? "mingguan" : hari <= 1100 ? "bulanan" : "tahunan";
}

function pasangSatuan(satuan, manual = false) {
  state.satuan = satuan;
  if (manual) state.satuanManual = true;
  for (const b of $$("#satuan button")) b.classList.toggle("aktif", b.dataset.satuan === satuan);
  if (state.grafik) gambarGrafik();
}

/* ---------- grafik ---------- */

const NS = "http://www.w3.org/2000/svg";
const svgEl = (t, a = {}) => {
  const n = document.createElementNS(NS, t);
  for (const [k, v] of Object.entries(a)) n.setAttribute(k, v);
  return n;
};
/* Warna grafik diatur lewat kelas di gaya.css, bukan atribut, supaya grafik
   ikut berganti saat tema terang/gelap berganti. */
const teksSvg = (isi, a) => {
  const t = svgEl("text", { class: "sumbu", "font-family": "inherit", ...a });
  t.textContent = isi;
  return t;
};

/* Batas atas/bawah sumbu harga yang dibulatkan, supaya label sumbu mudah dibaca. */
function sumbuHarga(min, max) {
  const rentang = max - min || max * 0.02 || 1;
  const kasar = rentang / 3;
  const pangkat = 10 ** Math.floor(Math.log10(kasar));
  const langkah = [1, 2, 2.5, 5, 10].map((k) => k * pangkat).find((v) => v >= kasar);
  const bawah = Math.floor((min - rentang * 0.08) / langkah) * langkah;
  const atas = Math.ceil((max + rentang * 0.08) / langkah) * langkah;
  const tik = [];
  for (let v = bawah; v <= atas + 1e-9; v += langkah) tik.push(v);
  return { bawah, atas, tik };
}

/* Dua grafik bertumpuk berbagi sumbu waktu: harga di atas, sentimen per
   periode di bawah. Sengaja tidak memakai satu grafik dua sumbu — skala rupiah
   dan skala −1…+1 yang ditumpuk membuat kemiringan garis bisa dibaca seolah
   berkaitan. */
function gambarGrafik() {
  const satuan = state.satuan;
  const fmt = SATUAN[satuan];
  const { sentimen, harga } = agregasi(state.grafik.sentimen, state.grafik.harga, satuan);
  const wadah = $("#grafik");
  wadah.innerHTML = "";
  $("#keterangan-periode").textContent =
    `${fmtTgl($("#mulai").value, { day: "numeric", month: "short", year: "numeric" })} – ` +
    `${fmtTgl($("#sampai").value, { day: "numeric", month: "short", year: "numeric" })} · per ${satuan.replace("an", "")}`;

  const tanggal = [...new Set([...sentimen.map((d) => d.tanggal), ...harga.map((d) => d.tanggal)])].sort();
  if (!tanggal.length) {
    wadah.append(kosong("Belum ada data pada rentang ini", "Coba rentang “Semua” di atas."));
    return;
  }

  const W = Math.max(300, Math.round(wadah.clientWidth || 900));
  const sempit = W < 560;
  const P = { kiri: sempit ? 46 : 58, kanan: 10, atas: 26, bawah: 30 };
  const H1 = sempit ? 150 : 200;
  const JARAK = 46;
  const H2 = sempit ? 96 : 116;
  const H = P.atas + H1 + JARAK + H2 + P.bawah;
  const lebar = W - P.kiri - P.kanan;
  const n = tanggal.length;
  // batang di ujung kiri/kanan harus muat utuh di area grafik, jadi titik
  // pertama & terakhir digeser ke dalam sebesar setengah lebar batang
  const lebarBatang = Math.max(3, Math.min(n <= 6 ? 36 : 16, (lebar / Math.max(1, n - 1)) * 0.6));
  const tepi = n > 1 ? lebarBatang / 2 + 2 : 0;
  const langkahX = n > 1 ? (lebar - 2 * tepi) / (n - 1) : lebar;
  const x = (i) => P.kiri + tepi + (n > 1 ? i * langkahX : lebar / 2);
  const indeks = new Map(tanggal.map((t, i) => [t, i]));
  const petaHarga = new Map(harga.map((d) => [d.tanggal, d]));
  const petaSent = new Map(sentimen.map((d) => [d.tanggal, d]));

  const svg = svgEl("svg", {
    viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img",
    "aria-label": `Grafik harga penutupan dan skor sentimen ${NAMA_SATUAN[satuan]}`,
  });
  // --- panel harga ---
  const atas1 = P.atas;
  svg.append(teksSvg(satuan === "harian" ? "Harga penutupan (Rp)" : "Harga penutupan akhir periode (Rp)",
    { x: P.kiri, y: atas1 - 12, class: "judul-panel" }));
  const nilaiHarga = harga.map((d) => d.penutupan);
  let yHarga = null;
  if (nilaiHarga.length) {
    const s = sumbuHarga(Math.min(...nilaiHarga), Math.max(...nilaiHarga));
    yHarga = (v) => atas1 + H1 - ((v - s.bawah) / (s.atas - s.bawah)) * H1;
    for (const v of s.tik) {
      svg.append(svgEl("line", { x1: P.kiri, x2: P.kiri + lebar, y1: yHarga(v), y2: yHarga(v), class: "kisi" }));
      svg.append(teksSvg(fmtAngka(Math.round(v)), { x: P.kiri - 8, y: yHarga(v) + 4, "text-anchor": "end" }));
    }
    const titik = tanggal.filter((t) => petaHarga.has(t)).map((t) => [x(indeks.get(t)), yHarga(petaHarga.get(t).penutupan)]);
    if (titik.length > 1) {
      const garis = titik.map(([a, b], i) => `${i ? "L" : "M"}${a.toFixed(1)},${b.toFixed(1)}`).join(" ");
      const dasar = (atas1 + H1).toFixed(1);
      svg.append(svgEl("path", { d: `${garis} L${titik.at(-1)[0].toFixed(1)},${dasar} L${titik[0][0].toFixed(1)},${dasar} Z`, class: "area-harga" }));
      svg.append(svgEl("path", { d: garis, class: "garis-harga" }));
    }
    if (titik.length <= 12) {
      for (const [a, b] of titik) svg.append(svgEl("circle", { cx: a, cy: b, r: 3, class: "titik-harga" }));
    }
  } else {
    svg.append(teksSvg("Belum ada data harga pada rentang ini", { x: P.kiri + lebar / 2, y: atas1 + H1 / 2, "text-anchor": "middle" }));
  }

  // --- panel sentimen ---
  const atas2 = atas1 + H1 + JARAK;
  const ySent = (v) => atas2 + H2 / 2 - (v * H2) / 2;
  svg.append(teksSvg(`Skor sentimen ${NAMA_SATUAN[satuan]} (−1 s/d +1)`, { x: P.kiri, y: atas2 - 12, class: "judul-panel" }));
  for (const v of [1, 0, -1]) {
    svg.append(svgEl("line", {
      x1: P.kiri, x2: P.kiri + lebar, y1: ySent(v), y2: ySent(v),
      class: v === 0 ? "kisi-nol" : "kisi", ...(v === 0 ? {} : { "stroke-dasharray": "3 4" }),
    }));
    svg.append(teksSvg(v === 0 ? "0" : fmtSkor(v).replace(".00", ""), { x: P.kiri - 8, y: ySent(v) + 4, "text-anchor": "end" }));
  }
  const batang = new Map();
  for (const d of sentimen) {
    const cx = x(indeks.get(d.tanggal));
    const y0 = ySent(0);
    const tinggi = Math.max(2, Math.abs(ySent(d.skor) - y0));
    const r = svgEl("rect", {
      x: cx - lebarBatang / 2, y: d.skor >= 0 ? y0 - tinggi : y0, width: lebarBatang, height: tinggi,
      rx: Math.min(1.5, lebarBatang / 2),
    });
    r.style.fill = warnaSkor(d.skor);
    batang.set(d.tanggal, r);
    svg.append(r);
  }
  if (!sentimen.length) {
    svg.append(teksSvg("Belum ada berita berlabel pada rentang ini", { x: P.kiri + lebar / 2, y: ySent(0) - 8, "text-anchor": "middle" }));
  }

  // --- label sumbu waktu ---
  const maksLabel = sempit ? 4 : 7;
  const loncat = Math.max(1, Math.ceil(n / maksLabel));
  tanggal.forEach((t, i) => {
    if (i % loncat && i !== n - 1) return;
    if (i !== n - 1 && n - 1 - i < loncat / 2) return; // hindari label berhimpit di ujung
    svg.append(teksSvg(fmt.label(t), {
      x: x(i), y: H - 8, "text-anchor": n === 1 ? "middle" : i === 0 ? "start" : i === n - 1 ? "end" : "middle",
    }));
  });

  // --- lapisan sorot (hover / sentuh) ---
  const garisSorot = svgEl("line", { y1: atas1, y2: atas2 + H2, class: "garis-sorot", visibility: "hidden" });
  const titikSorot = svgEl("circle", { r: 4.5, class: "titik-sorot", visibility: "hidden" });
  svg.append(garisSorot, titikSorot);
  const tangkap = svgEl("rect", { x: P.kiri - 6, y: atas1 - 6, width: lebar + 12, height: atas2 + H2 - atas1 + 12, fill: "transparent" });
  svg.append(tangkap);

  const tip = $("#tooltip");
  let aktif = null;
  const sorot = (e) => {
    const kotak = svg.getBoundingClientRect();
    const px = ((e.clientX - kotak.left) * W) / kotak.width;
    const i = n > 1 ? Math.max(0, Math.min(n - 1, Math.round((px - P.kiri - tepi) / langkahX))) : 0;
    const t = tanggal[i];
    const cx = x(i);
    garisSorot.setAttribute("x1", cx);
    garisSorot.setAttribute("x2", cx);
    garisSorot.setAttribute("visibility", "visible");
    const h = petaHarga.get(t);
    if (h && yHarga) {
      titikSorot.setAttribute("cx", cx);
      titikSorot.setAttribute("cy", yHarga(h.penutupan));
      titikSorot.setAttribute("visibility", "visible");
    } else {
      titikSorot.setAttribute("visibility", "hidden");
    }
    if (aktif !== t) {
      for (const [tg, r] of batang) r.setAttribute("opacity", tg === t ? "1" : "0.35");
      aktif = t;
    }
    const s = petaSent.get(t);
    tip.innerHTML = "";
    tip.append(el("div", { class: "tgl" }, fmt.panjang(t)));
    tip.append(el("div", { class: "baris" }, [el("span", {}, "Harga"), el("b", {}, h ? `Rp ${fmtAngka(h.penutupan)}` : "tidak ada data")]));
    const bSent = el("b", {}, s ? fmtSkor(s.skor) : "—");
    if (s) bSent.style.color = warnaSkor(s.skor);
    tip.append(el("div", { class: "baris" }, [el("span", {}, "Sentimen"), bSent]));
    tip.append(el("div", { class: "rinci" }, s
      ? `${s.jumlah_berita} berita · ${s.jumlah_positif} pos · ${s.jumlah_netral} net · ${s.jumlah_negatif} neg`
      : "tidak ada berita berlabel"));
    tip.hidden = false;
    let kiri = e.clientX + 14;
    if (kiri + tip.offsetWidth > window.innerWidth - 8) kiri = e.clientX - tip.offsetWidth - 14;
    let atas = e.clientY - tip.offsetHeight - 14;
    if (atas < 8) atas = e.clientY + 18;
    tip.style.left = `${Math.max(8, kiri)}px`;
    tip.style.top = `${atas}px`;
  };
  const lepas = () => {
    garisSorot.setAttribute("visibility", "hidden");
    titikSorot.setAttribute("visibility", "hidden");
    for (const r of batang.values()) r.setAttribute("opacity", "1");
    aktif = null;
    tip.hidden = true;
  };
  tangkap.addEventListener("pointermove", sorot);
  tangkap.addEventListener("pointerdown", sorot);
  tangkap.addEventListener("pointerleave", lepas);
  tangkap.addEventListener("pointercancel", lepas);

  wadah.append(svg);
}

let tundaUkur;
window.addEventListener("resize", () => {
  clearTimeout(tundaUkur);
  tundaUkur = setTimeout(() => {
    if (state.grafik && !$("#panel-grafik").hidden) gambarGrafik();
  }, 150);
});
window.addEventListener("scroll", () => { $("#tooltip").hidden = true; }, { passive: true });

function tampilkanMetrik(sentimen, harga, detail) {
  const berita = sentimen.reduce((a, d) => a + d.jumlah_berita, 0);
  const pos = sentimen.reduce((a, d) => a + d.jumlah_positif, 0);
  const net = sentimen.reduce((a, d) => a + d.jumlah_netral, 0);
  const neg = sentimen.reduce((a, d) => a + d.jumlah_negatif, 0);
  const skor = berita ? sentimen.reduce((a, d) => a + d.skor * d.jumlah_berita, 0) / berita : null;
  const valid = harga.filter((d) => d.penutupan != null);
  const awal = valid[0];
  const akhir = valid.at(-1);
  const ubah = awal && akhir && awal !== akhir ? ((akhir.penutupan - awal.penutupan) / awal.penutupan) * 100 : null;

  const kotak = (label, nilai, sub, kelas = "") =>
    el("div", {}, [el("div", { class: "label" }, label), el("div", { class: `nilai ${kelas}` }, nilai), el("div", { class: "sub" }, sub)]);
  const wadah = $("#metrik");
  wadah.innerHTML = "";
  wadah.append(
    kotak("Skor sentimen", skor == null ? "—" : fmtSkor(skor), `${pos} pos · ${net} net · ${neg} neg`, kelasArah(skor)),
    kotak("Berita berlabel", fmtAngka(berita), `${sentimen.length} hari ada berita`),
    kotak("Harga terakhir", akhir ? `Rp ${fmtAngka(akhir.penutupan)}` : "—",
          akhir ? fmtTgl(akhir.tanggal, { day: "numeric", month: "short" }) : `${fmtAngka(detail.jumlah_berita)} berita total`),
    kotak("Perubahan harga", ubah == null ? "—" : fmtPersen(ubah), "dalam rentang terpilih", kelasArah(ubah)),
  );
}

// koefisien bisa null bila API mengirim NaN; jangan sampai satu angka
// kosong menghentikan render korelasi dan daftar berita sesudahnya
const ada = (kor) => kor != null && Number.isFinite(kor.koefisien);

function tampilkanKorelasi(k) {
  const wadah = $("#korelasi");
  wadah.innerHTML = "";
  if (k.catatan) wadah.append(el("p", { class: "peringatan" }, k.catatan));
  const kotak = (judul, kor) =>
    el("div", { class: "kotak" }, [
      el("div", { class: "ket" }, judul),
      el("div", { class: `nilai ${ada(kor) ? kelasArah(kor.koefisien) : ""}` },
         ada(kor) ? (kor.koefisien > 0 ? "+" : "") + kor.koefisien.toFixed(3) : "—"),
      el("div", { class: "ket" }, ada(kor) ? `${kor.kekuatan} · n=${kor.n}` : "belum cukup data"),
    ]);
  wadah.append(kotak("Pearson (linear)", k.pearson));
  wadah.append(kotak("Spearman (monoton)", k.spearman));
  const saring = k.maks_emiten_per_berita ? `maks ${k.maks_emiten_per_berita} emiten/berita` : "semua berita";
  wadah.append(el("div", { class: "kotak" }, [
    el("div", { class: "ket" }, "Hari beririsan"),
    el("div", { class: "nilai" }, String(k.hari_beririsan)),
    el("div", { class: "ket" }, `lag ${k.lag} hari · ${saring}`),
  ]));
  if (k.maks_emiten_per_berita) {
    wadah.append(el("p", { class: "peringatan" },
      "Artikel rekap pasar sedang dibuang. Bandingkan dengan hasil tanpa saringan: korelasi yang " +
      "hanya muncul saat rekap diikutkan menandakan yang terukur adalah pergerakan indeks, bukan " +
      "sentimen per emiten."));
  }
  wadah.append(el("p", { class: "peringatan" }, k.peringatan));
}

/* ---------- berita ---------- */

function lencanaLabel(label) {
  if (!label) return el("span", { class: "lencana kosong" }, "belum dilabeli");
  return el("span", { class: `lencana ${label.sentimen}`, title: "keyakinan model" },
    [label.sentimen, el("span", { class: "yakin" }, `${(label.keyakinan * 100).toFixed(0)}%`)]);
}

const NAMA_STATUS = {
  terkonfirmasi_resmi: "terkonfirmasi resmi",
  rumor_belum_terkonfirmasi: "rumor",
  belum_diperiksa: "belum diperiksa",
};

function tombolJejak(beritaId) {
  const jejak = el("div", { class: "jejak", hidden: "hidden" });
  const lihat = el("button", { class: "jejak-tombol" }, "dasar verifikasi");
  lihat.onclick = async () => {
    if (!jejak.hidden) { jejak.hidden = true; return; }
    jejak.innerHTML = "";
    try {
      const riwayat = await ambil(`/api/berita/${beritaId}/jejak`);
      if (!riwayat.length) jejak.append(el("div", {}, "Belum pernah diperiksa."));
      for (const j of riwayat) {
        const baris = el("div", {}, [el("span", {}, `${NAMA_STATUS[j.status] || j.status} — ${j.alasan}`)]);
        if (j.pengumuman) {
          baris.append(" ");
          baris.append(el("a", { href: j.pengumuman.url, target: "_blank", rel: "noreferrer" }, "pengumuman resmi"));
        }
        jejak.append(baris);
      }
    } catch (e) {
      jejak.textContent = e.message;
    }
    jejak.hidden = false;
  };
  return { lihat, jejak };
}

async function muatBerita() {
  if (!state.kode) return;
  const p = new URLSearchParams({ kode: state.kode, limit: "30" });
  if ($("#saring-sentimen").value) p.set("sentimen", $("#saring-sentimen").value);
  if ($("#saring-status").value) p.set("status", $("#saring-status").value);

  const wadah = $("#berita");
  memuat(wadah);
  const daftar = await ambil(`/api/berita?${p}`);
  wadah.innerHTML = "";
  if (!daftar.length) {
    wadah.append(kosong("Tidak ada berita yang cocok",
      "Longgarkan saringan sentimen atau status, atau perlebar rentang tanggalnya."));
    return;
  }
  /* Delapan dulu: daftar 30 berita yang dibuka penuh membuat halaman
     memanjang dan grafik hilang dari pandangan. Sisanya satu klik. */
  const AWAL = 8;
  daftar.forEach((b, urutan) => {
    const tgl = b.terbit_pada
      ? new Date(b.terbit_pada).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" })
      : "tanggal tidak diketahui";
    const aksi = el("div", { class: "aksi" });
    if (bisaMeninjau()) {
      for (const sent of ["positif", "netral", "negatif"]) {
        const tombol = el("button", {}, `Koreksi → ${sent}`);
        tombol.onclick = async () => {
          tombol.disabled = true;
          try {
            await kirimJson(`/api/berita/${b.id}/koreksi`, { kode_emiten: state.kode, sentimen: sent });
            toast(`Label ${state.kode} diubah ke ${sent}`);
            await muatBerita();
            await muatEmiten();
            if (bisaMeninjau()) muatStatistikAnalis();
          } catch (e) {
            toast(e.message, "gagal");
          } finally {
            tombol.disabled = false;
          }
        };
        aksi.append(tombol);
      }
      const tolak = el("button", { title: "Berita ini tidak membahas emiten tersebut" }, `Tidak relevan untuk ${state.kode}`);
      tolak.onclick = async () => {
        tolak.disabled = true;
        try {
          await tolakPemetaan(b.id, state.kode);
          await muatEmiten(); // skor, korelasi, dan daftar berita ikut berubah
        } catch (e) {
          toast(e.message, "gagal");
          tolak.disabled = false;
        }
      };
      aksi.append(tolak);
    }
    const { lihat, jejak } = tombolJejak(b.id);
    aksi.append(lihat);
    const isi = el("div", { class: "isi" }, [
      el("a", { class: "judul", href: b.url, target: "_blank", rel: "noreferrer" }, b.judul),
      el("div", { class: "meta" }, [
        lencanaLabel(b.label),
        b.label && b.label.asal === "analis" ? el("span", { class: "lencana analis" }, "ditinjau") : null,
        el("span", {}, b.sumber),
        el("span", {}, tgl),
        el("span", {}, NAMA_STATUS[b.status_verifikasi] || b.status_verifikasi),
        b.emiten.length > 1 ? el("span", { title: b.emiten.join(", ") }, `${b.emiten.length} emiten`) : null,
      ]),
      aksi,
      jejak,
    ]);
    const item = el("div", { class: "berita-item" }, isi);
    if (urutan >= AWAL) item.hidden = true;
    wadah.append(item);
  });
  if (daftar.length > AWAL) {
    const lebih = el("button", { class: "tombol garis kecil lebih-banyak" }, `Tampilkan ${daftar.length - AWAL} berita lainnya`);
    lebih.onclick = () => {
      for (const x of wadah.querySelectorAll(".berita-item[hidden]")) x.hidden = false;
      lebih.remove();
    };
    wadah.append(lebih);
  }
}

/* ---------- peringkat seluruh emiten ---------- */

const KOLOM = [
  { kunci: "kode", label: "Emiten", kiri: true },
  { kunci: "sektor", label: "Sektor", kiri: true, opsional: true },
  { kunci: "skor", label: "Skor" },
  { kunci: "jumlah_berita", label: "Berita", hp: true },
  { kunci: "jumlah_positif", label: "Pos", opsional: true },
  { kunci: "jumlah_negatif", label: "Neg", opsional: true },
  { kunci: "harga_terakhir", label: "Harga", opsional: true },
  { kunci: "perubahan_harga", label: "Ubah" },
];
const urut = { kunci: null, naik: false };

function selSkor(skor) {
  const td = el("td", {});
  if (skor == null) {
    td.className = "sepi";
    td.textContent = "—";
    return td;
  }
  const isi = el("i", { class: "isi" });
  const lebar = Math.max(4, Math.abs(skor) * 50);
  isi.style.width = `${lebar}%`;
  isi.style.left = skor >= 0 ? "50%" : `${50 - lebar}%`;
  isi.style.background = warnaSkor(skor);
  const angka = el("span", { class: "angka" }, fmtSkor(skor));
  angka.style.color = warnaSkor(skor);
  td.append(el("span", { class: "skor" }, [angka, el("span", { class: "rel" }, [isi])]));
  return td;
}

function gambarPeringkat() {
  const wadah = $("#peringkat");
  wadah.innerHTML = "";
  const q = $("#cari-tabel").value.trim().toLowerCase();
  let baris = q
    ? state.baris.filter((b) => b.kode.toLowerCase().includes(q) || b.nama.toLowerCase().includes(q) || (b.sektor || "").toLowerCase().includes(q))
    : state.baris;
  if (!baris.length) {
    wadah.append(q
      ? kosong("Tidak ada emiten yang cocok", `Tidak ditemukan “${q}” di tabel ini.`)
      : kosong("Belum ada emiten dengan berita pada rentang ini",
          $("#hanya-berberita").checked
            ? "Hilangkan centang “Hanya yang ada beritanya”, atau perlebar rentang tanggalnya."
            : "Belum ada data pada rentang ini."));
    return;
  }
  if (urut.kunci) {
    baris = [...baris].sort((a, b) => {
      const p = a[urut.kunci], r = b[urut.kunci];
      if (p == null) return 1;
      if (r == null) return -1;
      const d = typeof p === "string" ? p.localeCompare(r) : p - r;
      return urut.naik ? d : -d;
    });
  }
  const tabel = el("table", { class: "peringkat" });
  const trh = el("tr");
  for (const k of KOLOM) {
    const panah = urut.kunci === k.kunci ? (urut.naik ? " ↑" : " ↓") : "";
    const kelas = [k.kiri ? "kiri" : "", k.opsional ? "opsional" : "", k.hp ? "opsional-hp" : "", urut.kunci === k.kunci ? "aktif" : ""].join(" ").trim();
    const th = el("th", kelas ? { class: kelas } : {}, k.label + panah);
    th.onclick = () => {
      if (urut.kunci === k.kunci) urut.naik = !urut.naik;
      else { urut.kunci = k.kunci; urut.naik = false; }
      gambarPeringkat();
    };
    trh.append(th);
  }
  tabel.append(el("thead", {}, trh));
  const tbody = el("tbody");
  for (const b of baris) {
    const tr = el("tr", { tabindex: "0", role: "button", "aria-label": `Lihat detail ${b.kode}` });
    if (b.kode === state.kode) tr.className = "terpilih";
    tr.append(el("td", { class: "kiri emiten" }, [
      el("div", { class: "kode" }, [b.kode, state.watchlist.has(b.kode) ? ikonBintang() : null]),
      el("div", { class: "nama" }, b.nama),
    ]));
    tr.append(el("td", { class: "kiri opsional redup" }, b.sektor || "—"));
    tr.append(selSkor(b.skor));
    tr.append(el("td", { class: b.jumlah_berita ? "opsional-hp" : "sepi opsional-hp" }, String(b.jumlah_berita)));
    tr.append(el("td", { class: "opsional" }, String(b.jumlah_positif)));
    tr.append(el("td", { class: "opsional" }, String(b.jumlah_negatif)));
    tr.append(el("td", { class: "opsional" }, b.harga_terakhir == null ? "—" : fmtAngka(b.harga_terakhir)));
    const u = b.perubahan_harga;
    tr.append(el("td", { class: u == null ? "sepi" : kelasArah(u) }, u == null ? "—" : fmtPersen(u)));
    tr.onclick = () => pilihEmiten(b.kode);
    tr.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pilihEmiten(b.kode); }
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
    state.baris = (await ambil(`/api/peringkat?${p}`)).baris;
    gambarPeringkat();
  } catch (e) {
    galat(e.message);
  }
}

/* ---------- akun ---------- */

const PERAN = { pengguna: { label: "Pengguna" }, analis: { label: "Analis" }, admin: { label: "Admin" } };
// admin mencakup hak analis: meninjau label dan status verifikasi
const bisaMeninjau = () => ["analis", "admin"].includes(state.saya?.peran);

function pilihTampilan(nama) {
  $("#tampilan-pasar").hidden = nama !== "pasar";
  $("#panel-analis").hidden = nama !== "analis";
  $("#panel-admin").hidden = nama !== "admin";
  for (const b of $$("#pilih-tampilan button")) {
    b.classList.toggle("aktif", b.dataset.tampilan === nama);
    b.setAttribute("aria-selected", String(b.dataset.tampilan === nama));
  }
  $("#tooltip").hidden = true;
  if (nama === "pasar" && state.grafik) gambarGrafik(); // lebar wadah bisa berubah saat tersembunyi
  if (nama === "admin") muatAdmin();
}

function perbaruiAkun() {
  const saya = state.saya;
  const peran = saya ? saya.peran : "tamu";
  document.body.dataset.peran = peran;
  $("#chip-akun").hidden = !saya;
  $("#tombol-masuk").textContent = saya ? "Keluar" : "Masuk";
  $("#panel-watchlist").hidden = !saya;
  $("#pilih-tampilan").hidden = !bisaMeninjau();
  $("#tab-admin").hidden = peran !== "admin";
  const kini = $("#pilih-tampilan button.aktif")?.dataset.tampilan;
  if (!bisaMeninjau() || (kini === "admin" && peran !== "admin")) pilihTampilan("pasar");
  $("#notif").hidden = !saya;
  if (!saya) {
    $("#panel-notif").hidden = true;
    clearInterval(state.tundaNotif);
  }
  $("#tombol-pantau").hidden = !saya;
  if (saya) {
    $("#avatar").textContent = saya.nama.split(/\s+/).map((k) => k[0]).slice(0, 2).join("").toUpperCase();
    $("#nama-akun").textContent = saya.nama.split(/\s+/)[0];
    $("#peran-akun").textContent = PERAN[peran].label;
  } else {
    state.watchlist.clear();
  }
  perbaruiTombolPantau();
}

async function kirimMasuk(e) {
  e.preventDefault();
  const g = $("#galat-masuk");
  g.hidden = true;
  const tombol = $("#kirim-masuk");
  tombol.disabled = true;
  try {
    const r = await fetch("/api/auth/masuk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: $("#masuk-email").value.trim(), kata_sandi: $("#masuk-sandi").value }),
    });
    const b = await r.json();
    if (!r.ok) throw new Error(b.detail || "gagal masuk");
    state.token = b.token;
    $("#masuk-sandi").value = "";
    state.saya = await ambil("/api/auth/saya");
    $("#dialog-masuk").close();
    perbaruiAkun();
    toast(`Masuk sebagai ${PERAN[state.saya.peran].label.toLowerCase()}`);
    await muatWatchlist();
    if (bisaMeninjau()) muatRuangAnalis();
    muatNotifikasi();
    // notifikasi dibuat siklus terjadwal; periksa ulang tiap 5 menit selama tab terbuka
    clearInterval(state.tundaNotif);
    state.tundaNotif = setInterval(muatNotifikasi, 5 * 60 * 1000);
    if (state.kode) muatBerita();
  } catch (err) {
    g.textContent = err.message;
    g.hidden = false;
  } finally {
    tombol.disabled = false;
  }
}

function keluar() {
  state.token = null;
  state.saya = null;
  perbaruiAkun();
  $("#watchlist").innerHTML = "";
  toast("Kamu sudah keluar");
  if (state.baris.length) gambarPeringkat();
  if (state.kode) muatBerita();
}

/* ---------- watchlist (pengguna & analis) ---------- */

async function muatWatchlist() {
  if (!state.saya) return;
  const daftar = await ambil("/api/watchlist");
  state.watchlist = new Set(daftar.map((w) => w.kode));
  perbaruiTombolPantau();
  if (state.baris.length) gambarPeringkat();
  const wadah = $("#watchlist");
  wadah.innerHTML = "";
  if (!daftar.length) {
    wadah.append(kosong("Watchlist masih kosong", "Buka sebuah emiten, lalu tekan Pantau di samping namanya."));
    return;
  }
  for (const w of daftar) {
    const skor = w.skor_terakhir;
    const hapus = el("button", { class: "hapus", "aria-label": `Hapus ${w.kode} dari watchlist`, title: "Hapus" }, ikonSilang());
    hapus.onclick = async (e) => {
      e.stopPropagation();
      await ubahPantau(w.kode, false);
    };
    const skorEl = el("div", { class: "skor" }, skor == null ? "—" : fmtSkor(skor));
    if (skor != null) skorEl.style.color = warnaSkor(skor);
    const kartu = el("div", { class: "kartu-wl", role: "button", tabindex: "0", "aria-label": `Buka ${w.kode}` }, [
      hapus,
      el("div", { class: "kode" }, w.kode),
      el("div", { class: "nama" }, w.nama),
      skorEl,
      el("div", { class: "sub-wl" }, w.tanggal_skor ? `skor ${fmtTgl(w.tanggal_skor, { day: "numeric", month: "short" })}` : "belum ada skor"),
      el("div", { class: "bawah" }, [
        el("span", {}, `${w.berita_7_hari} berita`),
        el("span", {}, w.harga_terakhir == null ? "—" : `Rp ${fmtAngka(w.harga_terakhir)}`),
      ]),
      pilihAmbang(w),
    ]);
    kartu.onclick = () => pilihEmiten(w.kode);
    kartu.onkeydown = (e) => { if (e.key === "Enter") pilihEmiten(w.kode); };
    wadah.append(kartu);
  }
}

/* UC-02: ambang perubahan sentimen yang memicu notifikasi, per emiten. */
function pilihAmbang(w) {
  const label = (v) => `±${String(v).replace(".", ",")}`;
  const pilih = el("select", { "aria-label": `Ambang notifikasi ${w.kode}` });
  const nilai = [0.2, 0.3, 0.5, 0.75, 1];
  if (!nilai.some((v) => Math.abs(v - w.ambang) < 1e-9)) nilai.push(w.ambang);
  for (const v of nilai.sort((a, b) => a - b)) {
    const o = el("option", { value: String(v) }, label(v));
    o.selected = Math.abs(v - w.ambang) < 1e-9;
    pilih.append(o);
  }
  pilih.onchange = async () => {
    try {
      await kirimJson("/api/watchlist", { kode_emiten: w.kode, ambang: Number(pilih.value) });
      toast(`${w.kode}: beri tahu bila sentimen bergeser ${label(Number(pilih.value))}`);
    } catch (e) {
      toast(e.message, "gagal");
    }
  };
  const baris = el("div", { class: "ambang-wl", title: "Rata-rata sentimen 7 hari terakhir dibanding 7 hari sebelumnya" },
    [el("span", {}, "Beri tahu bila bergeser"), pilih]);
  // kartu bisa diklik untuk membuka emiten; pilihan ambang tidak boleh ikut memicunya
  baris.onclick = (e) => e.stopPropagation();
  baris.onkeydown = (e) => e.stopPropagation();
  return baris;
}

function perbaruiTombolPantau() {
  const t = $("#tombol-pantau");
  const aktif = Boolean(state.kode && state.watchlist.has(state.kode));
  t.setAttribute("aria-pressed", String(aktif));
  t.replaceChildren(ikonBintang(), aktif ? "Dipantau" : "Pantau");
}

async function ubahPantau(kode, pantau) {
  try {
    if (pantau) await kirimJson("/api/watchlist", { kode_emiten: kode });
    else await ambil(`/api/watchlist/${kode}`, { method: "DELETE" });
    toast(pantau ? `${kode} ditambahkan ke watchlist` : `${kode} dihapus dari watchlist`);
    await muatWatchlist();
  } catch (e) {
    toast(e.message, "gagal");
  }
}

/* ---------- ruang kerja analis ---------- */

/* UC-05 4a: berita yang salah petakan dikeluarkan tanpa label. Skor emiten
   ikut berubah, jadi statistik dan peringkat dimuat ulang. */
async function tolakPemetaan(beritaId, kode) {
  await kirimJson(`/api/berita/${beritaId}/tidak-relevan`, { kode_emiten: kode });
  toast(`Kaitan ${kode} dicabut dari berita ini`);
  muatStatistikAnalis();
  muatPeringkat();
}

function muatRuangAnalis() {
  state.analis.offset = 0;
  muatStatistikAnalis();
  muatAntrean();
  muatVerifikasi();
}

async function muatStatistikAnalis() {
  const s = await ambil("/api/analis/statistik");
  const wadah = $("#statistik-analis");
  wadah.innerHTML = "";
  const persen = (a, b) => (b ? Math.round((a / b) * 100) : 0);
  const kotak = (label, nilai, sub, bilah = null) => el("div", { class: "kotak" }, [
    el("div", { class: "label" }, label), el("div", { class: "nilai" }, nilai), el("div", { class: "sub" }, sub),
    bilah == null ? null : el("div", { class: "bilah" }, [Object.assign(el("i"), { style: `width:${bilah}%` })]),
  ]);
  wadah.append(
    kotak("Sudah ditinjau", fmtAngka(s.sudah_ditinjau), `dari ${fmtAngka(s.pasangan_berlabel_model)} label model`,
          persen(s.sudah_ditinjau, s.pasangan_berlabel_model)),
    kotak("Antre", fmtAngka(s.tersisa), "menunggu keputusan"),
    kotak("Kesepakatan", s.sudah_ditinjau ? `${persen(s.setuju, s.sudah_ditinjau)}%` : "—",
          `${s.setuju} setuju · ${s.dikoreksi} dikoreksi`),
    kotak("Belum diverifikasi", fmtAngka(s.verifikasi.belum_diperiksa || 0),
          `${s.verifikasi.rumor_belum_terkonfirmasi || 0} rumor · ${s.verifikasi.terkonfirmasi_resmi || 0} resmi`),
  );
  // matriks model (baris) vs analis (kolom): diagonal = setuju
  const kelas = ["positif", "netral", "negatif"];
  const maks = Math.max(1, ...kelas.flatMap((m) => kelas.map((a) => s.matriks[m]?.[a] || 0)));
  const tabel = el("table", { class: "matriks-kecil" });
  tabel.append(el("tr", {}, [el("th", {}, "model ↓ / analis →"), ...kelas.map((k) => el("th", {}, k.slice(0, 3)))]));
  for (const m of kelas) {
    const tr = el("tr", {}, [el("th", {}, m.slice(0, 3))]);
    for (const a of kelas) {
      const v = s.matriks[m]?.[a] || 0;
      const td = el("td", {}, String(v));
      const warna = m === a ? "var(--positif)" : "var(--negatif)";
      td.style.background = `color-mix(in srgb, ${warna} ${Math.round(6 + (v / maks) * 34)}%, transparent)`;
      tr.append(td);
    }
    tabel.append(tr);
  }
  wadah.append(el("div", { class: "kotak matriks" }, [el("div", { class: "label" }, "Model vs analis"), tabel]));
  $("#jumlah-antrean").textContent = s.tersisa ? fmtAngka(s.tersisa) : "";
  $("#jumlah-verifikasi").textContent = s.verifikasi.belum_diperiksa ? fmtAngka(s.verifikasi.belum_diperiksa) : "";
  $("#jumlah-tinjau").textContent = s.tersisa ? fmtAngka(s.tersisa) : "";
}

async function muatAntrean(tambah = false) {
  const wadah = $("#antrean");
  if (!tambah) { state.analis.offset = 0; memuat(wadah); }
  const p = new URLSearchParams({ urut: $("#analis-urut").value, limit: "10", offset: String(state.analis.offset) });
  if ($("#analis-emiten").value) p.set("kode", $("#analis-emiten").value);
  const d = await ambil(`/api/analis/antrean?${p}`);
  if (!tambah) wadah.innerHTML = "";
  if (!d.item.length && !tambah) {
    wadah.append(kosong("Antrean kosong", "Semua label model pada saringan ini sudah ditinjau. Kerja bagus!"));
  }
  for (const it of d.item) wadah.append(kartuTinjau(it));
  state.analis.offset += d.item.length;
  $("#antrean-lagi").hidden = state.analis.offset >= d.total;
}

function kartuTinjau(it) {
  const tgl = it.terbit_pada ? new Date(it.terbit_pada).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" }) : "-";
  const m = it.label_model;
  const yakin = Math.round(m.keyakinan * 100);
  const bilah = el("span", { class: "keyakinan" }, [el("i")]);
  bilah.firstChild.style.width = `${yakin}%`;
  bilah.firstChild.style.background = WARNA_SENTIMEN[m.sentimen];
  const kartu = el("div", { class: "item-tinjau" });
  const putus = async (sentimen) => {
    for (const b of kartu.querySelectorAll("button")) b.disabled = true;
    try {
      await kirimJson(`/api/berita/${it.berita_id}/koreksi`, { kode_emiten: it.kode, sentimen });
      kartu.classList.add("keluar");
      toast(sentimen === m.sentimen ? `Disetujui: ${it.kode} ${sentimen}` : `Dikoreksi: ${it.kode} → ${sentimen}`);
      setTimeout(() => kartu.remove(), 260);
      state.analis.offset = Math.max(0, state.analis.offset - 1);
      muatStatistikAnalis();
      if ($("#antrean").children.length <= 3) muatAntrean(true);
      if (state.kode === it.kode) { muatEmiten(); muatBerita(); }
    } catch (e) {
      toast(e.message, "gagal");
      for (const b of kartu.querySelectorAll("button")) b.disabled = false;
    }
  };
  const tombol = (teks, kelas, sentimen) => {
    const b = el("button", { class: kelas }, teks);
    b.onclick = () => putus(sentimen);
    return b;
  };
  const tolak = el("button", { class: "tolak", title: "Berita ini tidak membahas emiten tersebut — kaitannya dicabut tanpa menyimpan label" },
    `Tidak relevan untuk ${it.kode}`);
  tolak.onclick = async () => {
    for (const b of kartu.querySelectorAll("button")) b.disabled = true;
    try {
      await tolakPemetaan(it.berita_id, it.kode);
      kartu.classList.add("keluar");
      setTimeout(() => kartu.remove(), 260);
      state.analis.offset = Math.max(0, state.analis.offset - 1);
      if ($("#antrean").children.length <= 3) muatAntrean(true);
    } catch (e) {
      toast(e.message, "gagal");
      for (const b of kartu.querySelectorAll("button")) b.disabled = false;
    }
  };
  const kutip = (it.kutipan || "").replace(/…/g, "").trim();
  kartu.append(
    el("div", { class: "isi" }, [
      el("a", { class: "judul", href: it.url, target: "_blank", rel: "noreferrer" }, it.judul),
      el("div", { class: "meta" }, [el("span", {}, it.sumber), el("span", {}, tgl), el("span", {}, NAMA_STATUS[it.status_verifikasi])]),
      el("div", { class: "kutip" }, [el("b", {}, it.kode), ` ${it.nama}`, kutip ? el("div", {}, `“…${kutip}…”`) : null]),
      el("div", { class: "model" }, [
        "Model", el("span", { class: `lencana ${m.sentimen}` }, m.sentimen), bilah, `yakin ${yakin}% · ${m.versi_model}`,
      ]),
    ]),
    el("div", { class: "putusan" }, [
      tombol(`Setuju — ${m.sentimen}`, "setuju", m.sentimen),
      tombol("Positif", "p", "positif"),
      tombol("Netral", "n", "netral"),
      tombol("Negatif", "g", "negatif"),
      tolak,
    ]),
  );
  return kartu;
}

async function muatVerifikasi() {
  const wadah = $("#daftar-verifikasi");
  memuat(wadah);
  const daftar = await ambil(`/api/berita?${new URLSearchParams({ status: $("#verifikasi-status").value, limit: "15" })}`);
  wadah.innerHTML = "";
  if (!daftar.length) {
    wadah.append(kosong("Tidak ada berita dengan status ini", "Pilih status lain di atas."));
    return;
  }
  for (const b of daftar) {
    const tgl = b.terbit_pada ? new Date(b.terbit_pada).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" }) : "-";
    const kartu = el("div", { class: "item-tinjau" });
    const tetapkan = async (status) => {
      for (const x of kartu.querySelectorAll("button")) x.disabled = true;
      try {
        await kirimJson(`/api/berita/${b.id}/verifikasi`, { status });
        kartu.classList.add("keluar");
        toast(`Ditetapkan: ${NAMA_STATUS[status]}`);
        setTimeout(() => kartu.remove(), 260);
        muatStatistikAnalis();
      } catch (e) {
        toast(e.message, "gagal");
        for (const x of kartu.querySelectorAll("button")) x.disabled = false;
      }
    };
    const tombol = (teks, kelas, status) => {
      const x = el("button", { class: kelas }, teks);
      x.onclick = () => tetapkan(status);
      return x;
    };
    const { lihat, jejak } = tombolJejak(b.id);
    const status = $("#verifikasi-status").value;
    kartu.append(
      el("div", { class: "isi" }, [
        el("a", { class: "judul", href: b.url, target: "_blank", rel: "noreferrer" }, b.judul),
        el("div", { class: "meta" }, [el("span", {}, b.sumber), el("span", {}, tgl), el("span", {}, b.emiten.join(", ") || "tanpa emiten"), lencanaLabel(b.label)]),
        jejak,
      ]),
      el("div", { class: "putusan verif" }, [
        status !== "terkonfirmasi_resmi" ? tombol("Terkonfirmasi resmi", "p", "terkonfirmasi_resmi") : null,
        status !== "rumor_belum_terkonfirmasi" ? tombol("Rumor", "g", "rumor_belum_terkonfirmasi") : null,
        status !== "belum_diperiksa" ? tombol("Belum diperiksa", "n", "belum_diperiksa") : null,
        lihat,
      ]),
    );
    wadah.append(kartu);
  }
}

function pasangRuangAnalis() {
  for (const b of $$("#panel-analis [role=tab]")) {
    b.onclick = () => {
      state.analis.tab = b.dataset.tab;
      for (const x of $$("#panel-analis [role=tab]")) x.classList.toggle("aktif", x === b);
      $("#tab-label").hidden = b.dataset.tab !== "label";
      $("#tab-verifikasi").hidden = b.dataset.tab !== "verifikasi";
    };
  }
  $("#analis-emiten").onchange = () => muatAntrean();
  $("#analis-urut").onchange = () => muatAntrean();
  $("#antrean-lagi").onclick = () => muatAntrean(true);
  $("#verifikasi-status").onchange = muatVerifikasi;
}

/* ---------- notifikasi (FR-6) ---------- */

function waktuRelatif(iso) {
  const menit = (Date.now() - new Date(iso).getTime()) / 60000;
  if (menit < 1) return "baru saja";
  if (menit < 60) return `${Math.round(menit)} menit lalu`;
  if (menit < 1440) return `${Math.round(menit / 60)} jam lalu`;
  return new Date(iso).toLocaleDateString("id-ID", { day: "numeric", month: "short" });
}

async function muatNotifikasi() {
  if (!state.saya) return;
  try {
    state.notif = await ambil("/api/notifikasi?limit=20");
  } catch {
    return;
  }
  const n = state.notif.belum_dibaca;
  const j = $("#jumlah-notif");
  j.hidden = !n;
  j.textContent = n > 9 ? "9+" : String(n);
  $("#tombol-notif").setAttribute("aria-label", n ? `Notifikasi, ${n} belum dibaca` : "Notifikasi");
  gambarNotifikasi();
}

function gambarNotifikasi() {
  const wadah = $("#daftar-notif");
  wadah.innerHTML = "";
  const item = state.notif?.item || [];
  $("#baca-semua").hidden = !state.notif?.belum_dibaca;
  if (!item.length) {
    wadah.append(el("p", { class: "kosong-notif" }, state.watchlist.size
      ? "Belum ada perubahan sentimen yang melewati ambang."
      : "Pantau emiten dulu — notifikasi hanya untuk emiten di watchlist."));
    return;
  }
  for (const n of item) {
    const naik = n.skor_sesudah > n.skor_sebelum;
    const b = el("button", { class: `item-notif${n.dibaca ? "" : " baru"}` }, [
      el("span", { class: `arah ${naik ? "naik" : "turun"}`, "aria-hidden": "true" }, naik ? "▲" : "▼"),
      el("span", { class: "isi-notif" }, [
        el("b", {}, n.kode), " ", n.pesan.replace(/^Sentimen \S+ /, ""),
        el("span", { class: "waktu" }, waktuRelatif(n.dibuat_pada)),
      ]),
    ]);
    b.onclick = () => {
      bukaNotif(false);
      pilihTampilan("pasar");
      pilihEmiten(n.kode);
    };
    wadah.append(b);
  }
}

async function aturEmailNotif() {
  const kotak = $("#email-notif");
  kotak.disabled = true;
  try {
    const r = await kirimJson("/api/notifikasi/email", { aktif: kotak.checked });
    state.saya.kirim_email = r.kirim_email;
    toast(r.kirim_email ? `Notifikasi juga dikirim ke ${state.saya.email}` : "Email notifikasi dimatikan");
  } catch (e) {
    kotak.checked = !kotak.checked;
    toast(e.message, "gagal");
  } finally {
    kotak.disabled = false;
  }
}

function bukaNotif(buka) {
  $("#panel-notif").hidden = !buka;
  $("#tombol-notif").setAttribute("aria-expanded", String(buka));
  if (buka) {
    $("#email-notif").checked = Boolean(state.saya?.kirim_email);
    muatNotifikasi();
  }
}

/* ---------- admin (FR-8, UC-06) ---------- */

const KREDIBILITAS = {
  terverifikasi_dewan_pers: "Terverifikasi Dewan Pers",
  portal_umum: "Portal umum",
  tidak_terverifikasi: "Tidak terverifikasi",
};

function pilihan(opsi, nilai, label) {
  const s = el("select", { "aria-label": label });
  for (const [v, teks] of Object.entries(opsi)) {
    const o = el("option", { value: v }, teks);
    o.selected = v === nilai;
    s.append(o);
  }
  return s;
}

function tabelAdmin(kolom, baris) {
  const t = el("table", { class: "tabel-admin" });
  t.append(el("thead", {}, el("tr", {}, kolom.map(([teks, kelas]) => el("th", kelas ? { class: kelas } : {}, teks)))));
  t.append(el("tbody", {}, baris));
  return el("div", { class: "bungkus-admin" }, t);
}

/* Perubahan kecil (centang, pilihan) langsung disimpan; bila gagal, kendali
   dikembalikan ke nilai lama supaya layar tidak berbohong soal isi basis data. */
async function simpanAdmin(url, badan, pesan, kembalikan) {
  try {
    await kirimJson(url, badan, "PATCH");
    toast(pesan);
  } catch (e) {
    toast(e.message, "gagal");
    if (kembalikan) kembalikan();
  }
}

function formAdmin(isian, teksTombol, kirim) {
  const tombol = el("button", { class: "tombol kecil", type: "submit" }, teksTombol);
  const form = el("form", { class: "form-admin" }, [...isian, tombol]);
  form.onsubmit = async (e) => {
    e.preventDefault();
    tombol.disabled = true;
    try {
      await kirim();
      muatAdmin();
    } catch (err) {
      toast(err.message, "gagal");
    } finally {
      tombol.disabled = false;
    }
  };
  return form;
}

const isian = (atribut) => el("input", { required: "", ...atribut });

async function adminSumber(wadah) {
  const daftar = await ambil("/api/admin/sumber");
  const nama = isian({ placeholder: "Nama portal", "aria-label": "Nama portal" });
  const url = isian({ type: "url", placeholder: "https://portal.co.id/rss", "aria-label": "Alamat RSS", class: "lebar" });
  const kred = pilihan(KREDIBILITAS, "portal_umum", "Kredibilitas");
  wadah.append(formAdmin([nama, url, kred], "Tambah sumber", async () => {
    await kirimJson("/api/admin/sumber", { nama: nama.value, url_rss: url.value, kredibilitas: kred.value });
    toast(`${nama.value} ditambahkan — ikut dikumpulkan pada siklus berikutnya`);
  }));
  wadah.append(tabelAdmin([["Portal"], ["Kredibilitas"], ["Berita", "angka"], ["Siklus terakhir"], ["Aktif", "tengah"]],
    daftar.map((s) => {
      const k = pilihan(KREDIBILITAS, s.kredibilitas, `Kredibilitas ${s.nama}`);
      k.onchange = () => simpanAdmin(`/api/admin/sumber/${s.id}`, { kredibilitas: k.value },
        `Kredibilitas ${s.nama} diperbarui`, () => { k.value = s.kredibilitas; });
      const aktif = el("input", { type: "checkbox", "aria-label": `${s.nama} aktif` });
      aktif.checked = s.aktif;
      aktif.onchange = () => simpanAdmin(`/api/admin/sumber/${s.id}`, { aktif: aktif.checked },
        `${s.nama} ${aktif.checked ? "diaktifkan" : "dinonaktifkan"}`, () => { aktif.checked = !aktif.checked; });
      const status = s.siklus_terakhir
        ? el("span", { class: s.siklus_terakhir_berhasil ? "status-ok" : "status-gagal", title: s.pesan_terakhir || "" },
          `${s.siklus_terakhir_berhasil ? "Berhasil" : "Gagal"} · ${waktuRelatif(s.siklus_terakhir)}`)
        : el("span", { class: "redup" }, "belum pernah");
      return el("tr", {}, [
        el("td", {}, [el("div", { class: "utama" }, s.nama), el("div", { class: "sub" }, s.url_rss || s.domain)]),
        el("td", {}, k), el("td", { class: "angka" }, fmtAngka(s.jumlah_berita)), el("td", {}, status),
        el("td", { class: "tengah" }, aktif),
      ]);
    })));
}

async function adminEmiten(wadah) {
  const daftar = await ambil("/api/admin/emiten");
  const kode = isian({ placeholder: "Kode", maxlength: "4", "aria-label": "Kode emiten", class: "pendek" });
  const nama = isian({ placeholder: "Nama perusahaan", "aria-label": "Nama perusahaan" });
  const sektor = el("input", { placeholder: "Sektor", "aria-label": "Sektor" });
  const alias = el("input", { placeholder: "Alias, pisah dengan |", "aria-label": "Alias", class: "lebar" });
  wadah.append(formAdmin([kode, nama, sektor, alias], "Tambah emiten", async () => {
    await kirimJson("/api/admin/emiten", { kode: kode.value, nama: nama.value, sektor: sektor.value || null, alias: alias.value || null });
    toast(`${kode.value.toUpperCase()} ditambahkan`);
  }));
  const saring = el("input", { type: "search", placeholder: "Saring emiten…", "aria-label": "Saring emiten", class: "saring-admin" });
  wadah.append(saring);
  const baris = daftar.map((e) => {
    const a = el("input", { value: e.alias || "", placeholder: "—", "aria-label": `Alias ${e.kode}`, class: "lebar" });
    a.onchange = () => simpanAdmin(`/api/admin/emiten/${e.kode}`, { alias: a.value }, `Alias ${e.kode} disimpan`);
    const aktif = el("input", { type: "checkbox", "aria-label": `${e.kode} dipantau` });
    aktif.checked = e.aktif;
    aktif.onchange = () => simpanAdmin(`/api/admin/emiten/${e.kode}`, { aktif: aktif.checked },
      `${e.kode} ${aktif.checked ? "dipantau lagi" : "tidak lagi dipantau"}`, () => { aktif.checked = !aktif.checked; });
    const tr = el("tr", { class: e.aktif ? "" : "nonaktif" }, [
      el("td", {}, [el("div", { class: "utama" }, e.kode), el("div", { class: "sub" }, e.nama)]),
      el("td", { class: "redup" }, e.sektor || "—"), el("td", {}, a),
      el("td", { class: "angka" }, fmtAngka(e.jumlah_berita)), el("td", { class: "tengah" }, aktif),
    ]);
    tr.dataset.cari = `${e.kode} ${e.nama} ${e.sektor || ""} ${e.alias || ""}`.toLowerCase();
    return tr;
  });
  saring.oninput = () => {
    const q = saring.value.trim().toLowerCase();
    for (const tr of baris) tr.hidden = Boolean(q) && !tr.dataset.cari.includes(q);
  };
  wadah.append(tabelAdmin([["Emiten"], ["Sektor"], ["Alias (untuk pencocokan)"], ["Berita", "angka"], ["Dipantau", "tengah"]], baris));
  wadah.append(el("p", { class: "ket" }, "Emiten yang tidak dipantau tidak dihapus: berita dan harganya tetap tersimpan sebagai catatan periode sebelumnya, tetapi tidak lagi ikut dicocokkan."));
}

async function adminAkun(wadah) {
  const daftar = await ambil("/api/admin/akun");
  const LABEL = { pengguna: "Pengguna", analis: "Analis", admin: "Admin" };
  const email = isian({ type: "email", placeholder: "email@contoh.id", "aria-label": "Email" });
  const nama = isian({ placeholder: "Nama", "aria-label": "Nama" });
  const peran = pilihan(LABEL, "pengguna", "Peran");
  const sandi = isian({ type: "password", placeholder: "Kata sandi (min. 10)", minlength: "10", autocomplete: "new-password", "aria-label": "Kata sandi" });
  wadah.append(formAdmin([email, nama, peran, sandi], "Buat akun", async () => {
    await kirimJson("/api/admin/akun", { email: email.value, nama: nama.value, peran: peran.value, kata_sandi: sandi.value });
    toast(`Akun ${email.value} dibuat`);
  }));
  wadah.append(tabelAdmin([["Akun"], ["Peran"], ["Watchlist", "angka"], ["Dibuat"], ["Aktif", "tengah"], [""]],
    daftar.map((a) => {
      const diri = a.id === state.saya.id;
      const p = pilihan(LABEL, a.peran, `Peran ${a.email}`);
      p.disabled = diri;
      p.onchange = () => simpanAdmin(`/api/admin/akun/${a.id}`, { peran: p.value }, `Peran ${a.nama} diubah ke ${LABEL[p.value]}`,
        () => { p.value = a.peran; });
      const aktif = el("input", { type: "checkbox", "aria-label": `${a.email} aktif` });
      aktif.checked = a.aktif;
      aktif.disabled = diri;
      aktif.onchange = () => simpanAdmin(`/api/admin/akun/${a.id}`, { aktif: aktif.checked },
        `${a.nama} ${aktif.checked ? "diaktifkan" : "dinonaktifkan"}`, () => { aktif.checked = !aktif.checked; });
      const ulang = el("button", { class: "tautan-tombol", type: "button" }, "Atur ulang sandi");
      ulang.onclick = async () => {
        const baru = window.prompt(`Kata sandi baru untuk ${a.email} (minimal 10 karakter):`);
        if (!baru) return;
        if (baru.length < 10) return toast("Kata sandi minimal 10 karakter", "gagal");
        await simpanAdmin(`/api/admin/akun/${a.id}`, { kata_sandi: baru }, `Kata sandi ${a.nama} diganti`);
      };
      return el("tr", { class: a.aktif ? "" : "nonaktif" }, [
        el("td", {}, [el("div", { class: "utama" }, a.nama + (diri ? " (kamu)" : "")), el("div", { class: "sub" }, a.email)]),
        el("td", {}, p), el("td", { class: "angka" }, String(a.jumlah_watchlist)),
        el("td", { class: "redup" }, new Date(a.dibuat_pada).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" })),
        el("td", { class: "tengah" }, aktif), el("td", {}, ulang),
      ]);
    })));
}

async function adminLog(wadah) {
  const daftar = await ambil("/api/admin/log?limit=80");
  const sehari = daftar.filter((l) => Date.now() - new Date(l.mulai_pada).getTime() < 86400000);
  const gagal = sehari.filter((l) => !l.berhasil).length;
  wadah.append(el("p", { class: "ringkas-admin" }, [
    el("b", {}, `${sehari.length}`), " pengambilan sumber dalam 24 jam · ",
    el("b", {}, fmtAngka(sehari.reduce((n, l) => n + l.jumlah_baru, 0))), " berita baru · ",
    el("b", { class: gagal ? "turun" : "" }, String(gagal)), " gagal",
  ]));
  wadah.append(tabelAdmin([["Waktu"], ["Sumber"], ["Ditemukan", "angka"], ["Baru", "angka"], ["Status"]],
    daftar.map((l) => el("tr", {}, [
      el("td", { class: "redup nowrap" }, new Date(l.mulai_pada).toLocaleString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })),
      el("td", {}, l.sumber || "—"),
      el("td", { class: "angka" }, String(l.jumlah_ditemukan)), el("td", { class: "angka" }, String(l.jumlah_baru)),
      el("td", {}, l.berhasil ? el("span", { class: "status-ok" }, "Berhasil")
        : [el("span", { class: "status-gagal" }, "Gagal"), el("div", { class: "sub" }, l.pesan || "")]),
    ]))));
}

async function adminModel(wadah) {
  const m = await ambil("/api/admin/model");
  const latih = m.label_emas.latih;
  const persen = Math.min(100, Math.round((latih / m.minimal_latih) * 100));
  const bilah = el("div", { class: "bilah" }, el("i"));
  bilah.firstChild.style.width = `${persen}%`;
  const kotak = (label, nilai, sub, tambahan = null) => el("div", { class: "kotak" },
    [el("div", { class: "label" }, label), el("div", { class: "nilai" }, nilai), el("div", { class: "sub" }, sub), tambahan]);
  const sebaran = Object.entries(m.sebaran_kelas).map(([k, v]) => `${v} ${k}`).join(" · ") || "belum ada";
  const versi = Object.entries(m.label_per_versi).map(([k, v]) => `${k}: ${fmtAngka(v)}`).join(" · ") || "belum ada";
  wadah.append(el("div", { class: "statistik-analis model-admin" }, [
    kotak("Label emas", fmtAngka(m.label_emas.total), sebaran),
    kotak("Data latih", `${fmtAngka(latih)} / ${m.minimal_latih}`, m.siap_dilatih ? "cukup untuk dilatih" : "minimal untuk mulai melatih", bilah),
    kotak("Validasi · Uji", `${m.label_emas.validasi} · ${m.label_emas.uji}`, "dipisah per berita, 70/15/15"),
    kotak("Label model tersimpan", "", versi),
  ]));
  const langkah = [
    ["Anotasi label emas (buta, tanpa melihat prediksi model)", "python -m scripts.label_manual"],
    ["Latih pembanding TF-IDF + Naive Bayes / SVM", "python -m scripts.latih_klasik"],
    ["Fine-tuning IndoBERT (butuh GPU)", "python -m scripts.latih_indobert"],
    ["Bandingkan semua model pada data uji", "python -m scripts.evaluasi_model"],
    ["Labeli ulang seluruh berita dengan model terbaik", "python -m scripts.klasifikasi --model indobert --ulangi"],
  ];
  wadah.append(el("h3", { class: "subjudul" }, "Pelatihan ulang"));
  wadah.append(el("p", { class: "ket" }, "Pelatihan dijalankan di laptop ber-GPU, bukan dari server web: server tidak punya GPU, dan proses berdurasi puluhan menit akan diputus batas waktu permintaan."));
  wadah.append(el("ol", { class: "langkah-model" }, langkah.map(([teks, perintah]) =>
    el("li", {}, [el("span", {}, teks), el("code", {}, perintah)]))));
}

const BAGIAN_ADMIN = { sumber: adminSumber, emiten: adminEmiten, akun: adminAkun, log: adminLog, model: adminModel };

/* Daftar LQ45 yang kedaluwarsa tidak menimbulkan galat apa pun — emiten yang
   baru masuk indeks hanya tidak pernah dicocokkan. Karena itu diingatkan. */
async function periksaPeriodeLq45() {
  const p = $("#peringatan-periode");
  try {
    const s = await ambil("/api/admin/periode-lq45");
    const akhir = fmtTgl(s.akhir, { day: "numeric", month: "long", year: "numeric" });
    p.hidden = s.status === "berlaku";
    p.classList.toggle("lewat", s.status === "kedaluwarsa");
    p.textContent = s.status === "kedaluwarsa"
      ? `Komposisi LQ45 di data/lq45.py sudah tidak berlaku sejak ${akhir}. Perbarui dari pengumuman resmi BEI, lalu jalankan scripts.init_db.`
      : `Komposisi LQ45 di data/lq45.py berakhir ${akhir} (${s.sisa_hari} hari lagi). Siapkan daftar periode berikutnya dari pengumuman BEI.`;
  } catch {
    p.hidden = true;
  }
}

async function muatAdmin() {
  periksaPeriodeLq45();
  const bagian = state.bagianAdmin || "sumber";
  for (const b of $$("#tab-admin-isi button")) b.classList.toggle("aktif", b.dataset.bagian === bagian);
  const wadah = $("#isi-admin");
  memuat(wadah);
  const isi = el("div");
  try {
    await BAGIAN_ADMIN[bagian](isi);
    wadah.replaceChildren(isi);
  } catch (e) {
    wadah.replaceChildren(kosong("Gagal memuat", e.message));
  }
}

/* ---------- alur utama ---------- */

function pilihEmiten(kode) {
  state.kode = kode;
  $("#cari").value = labelEmiten(kode);
  tutupSaran();
  muatEmiten({ gulir: true });
}

async function muatEmiten({ gulir = false } = {}) {
  const kode = state.kode;
  if (!kode) return;
  const p = new URLSearchParams();
  if ($("#mulai").value) p.set("mulai", $("#mulai").value);
  if ($("#sampai").value) p.set("sampai", $("#sampai").value);
  const pk = new URLSearchParams(p);
  pk.set("lag", $("#lag").value);
  if ($("#maks-emiten").value) pk.set("maks_emiten_per_berita", $("#maks-emiten").value);

  galat("");
  const panel = $("#panel-grafik");
  const pertamaKali = panel.hidden;
  panel.hidden = false;
  $("#panel-berita").hidden = false;
  $("#detail-kosong").hidden = true;
  /* Layar lebar: detail ada di samping daftar, jadi cukup gulir bila
     kepalanya sudah lewat ke atas. Layar sempit: detail ada di atas daftar. */
  const lewat = panel.getBoundingClientRect().top < 0;
  if ((gulir || pertamaKali) && (lewat || !layarLebar())) {
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  $("#kode-emiten").textContent = kode;
  perbaruiTombolPantau();
  if (!state.grafik) memuat($("#grafik"));

  try {
    const [detail, sentimen, harga, kor] = await Promise.all([
      ambil(`/api/emiten/${kode}`),
      ambil(`/api/emiten/${kode}/sentimen?${p}`),
      ambil(`/api/emiten/${kode}/harga?${p}`),
      ambil(`/api/emiten/${kode}/korelasi?${pk}`),
    ]);
    if (state.kode !== kode) return; // pengguna sudah pindah emiten
    $("#judul-emiten").textContent = `${detail.nama}${detail.sektor ? " · " + detail.sektor : ""}`;
    tampilkanMetrik(sentimen.titik, harga.titik, detail);
    state.grafik = { sentimen: sentimen.titik, harga: harga.titik };
    if (!state.satuanManual) pasangSatuan(satuanOtomatis());
    else gambarGrafik();

    /* Grafik yang timpang bukan grafik yang rusak. Tanpa keterangan ini,
       garis harga panjang di sebelah satu titik sentimen terbaca sebagai
       kesalahan tampilan, padahal itu keadaan datanya. */
    const catatan = $("#catatan-grafik");
    if (sentimen.titik.length && harga.titik.length && sentimen.titik.length < harga.titik.length / 4) {
      catatan.textContent =
        `Sentimen baru tersedia ${sentimen.titik.length} hari, harga ${harga.titik.length} hari. ` +
        "Korelasi baru berarti setelah deret sentimennya cukup panjang.";
      catatan.hidden = false;
    } else {
      catatan.hidden = true;
    }
    tampilkanKorelasi(kor);
  } catch (e) {
    galat(e.message);
  }
  // berita dimuat terpisah: kegagalan grafik atau korelasi tidak boleh
  // ikut mengosongkan daftar berita emiten ini
  if (state.kode !== kode) return;
  if (state.baris.length) gambarPeringkat();
  try {
    await muatBerita();
  } catch (e) {
    galat(e.message);
  }
}

function tutupDetail() {
  state.kode = null;
  state.grafik = null;
  $("#cari").value = "";
  $("#panel-grafik").hidden = true;
  $("#panel-berita").hidden = true;
  $("#detail-kosong").hidden = false;
  $("#tooltip").hidden = true;
  if (state.baris.length) gambarPeringkat();
}

function pasangRentang(mulai, sampai, tombol) {
  $("#mulai").value = mulai;
  $("#sampai").value = sampai;
  for (const b of $$("#pintasan button")) b.classList.toggle("aktif", b === tombol);
  $("#kustom").hidden = !tombol?.dataset.kustom;
  state.satuanManual = false; // rentang baru: satuan grafik kembali otomatis
  muatPeringkat();
  if (state.kode) muatEmiten();
}

function tanggalAwal() {
  const kini = new Date();
  $("#sampai").value = isoLokal(kini);
  $("#mulai").value = isoLokal(new Date(kini.getTime() - 30 * 86400000));
  $('#pintasan button[data-hari="30"]').classList.add("aktif");
}

async function muatCakupanData() {
  try {
    state.cakupan = await ambil("/api/rentang-data");
  } catch {
    return;
  }
  const c = state.cakupan;
  if (!c.mulai) return;
  const opsi = { day: "numeric", month: "short", year: "numeric" };
  const r = (a, b) => (a ? `${fmtTgl(a, opsi)} – ${fmtTgl(b, opsi)}` : "—");
  $("#cakupan-data").textContent = `Berita ${r(c.berita_mulai, c.berita_sampai)} · Harga ${r(c.harga_mulai, c.harga_sampai)}`;
  $("#mulai").min = $("#sampai").min = c.mulai;
}

function pasangPintasan() {
  for (const b of $$("#pintasan button")) {
    b.onclick = () => {
      const kini = new Date();
      if (b.dataset.hari) {
        pasangRentang(isoLokal(new Date(kini.getTime() - Number(b.dataset.hari) * 86400000)), isoLokal(kini), b);
      } else if (b.dataset.ytd) {
        pasangRentang(`${kini.getFullYear()}-01-01`, isoLokal(kini), b);
      } else if (b.dataset.semua) {
        const c = state.cakupan;
        if (!c || !c.mulai) return galat("Belum ada data sama sekali.");
        pasangRentang(c.mulai, c.sampai, b);
      } else if (b.dataset.kustom) {
        for (const x of $$("#pintasan button")) x.classList.toggle("aktif", x === b);
        $("#kustom").hidden = false;
        $("#mulai").focus();
      }
    };
  }
  $("#terapkan-kustom").onclick = () => {
    if (!$("#mulai").value || !$("#sampai").value) return galat("Isi tanggal mulai dan sampai.");
    if ($("#mulai").value > $("#sampai").value) return galat("Tanggal mulai tidak boleh setelah tanggal sampai.");
    galat("");
    pasangRentang($("#mulai").value, $("#sampai").value, $('#pintasan button[data-kustom]'));
  };
}

(async function mulai() {
  tanggalAwal();
  pasangPintasan();
  pasangPencarian();
  pasangRuangAnalis();
  for (const b of $$("#satuan button")) b.onclick = () => pasangSatuan(b.dataset.satuan, true);
  $("#hanya-berberita").onchange = muatPeringkat;
  $("#cari-tabel").addEventListener("input", gambarPeringkat);
  $("#tombol-masuk").onclick = () => {
    if (state.saya) return keluar();
    $("#galat-masuk").hidden = true;
    $("#dialog-masuk").showModal();
  };
  $("#tutup-masuk").onclick = () => $("#dialog-masuk").close();
  $("#form-masuk").addEventListener("submit", kirimMasuk);
  $("#tombol-pantau").onclick = () => ubahPantau(state.kode, !state.watchlist.has(state.kode));
  $("#tutup-detail").onclick = tutupDetail;
  $("#lag").onchange = () => { if (state.kode) muatEmiten(); };
  $("#maks-emiten").onchange = () => {
    muatPeringkat();
    if (state.kode) muatEmiten();
  };
  $("#saring-sentimen").onchange = muatBerita;
  $("#saring-status").onchange = muatBerita;
  for (const b of $$("#pilih-tampilan button")) b.onclick = () => pilihTampilan(b.dataset.tampilan);
  for (const b of $$("#tab-admin-isi button")) {
    b.onclick = () => { state.bagianAdmin = b.dataset.bagian; muatAdmin(); };
  }
  $("#tombol-notif").onclick = (e) => { e.stopPropagation(); bukaNotif($("#panel-notif").hidden); };
  $("#email-notif").onchange = aturEmailNotif;
  $("#baca-semua").onclick = async (e) => {
    e.stopPropagation();
    try {
      await kirimJson("/api/notifikasi/baca", {});
      await muatNotifikasi();
    } catch (err) {
      toast(err.message, "gagal");
    }
  };
  // panel pengaturan menutup sendiri saat klik di luar, seperti menu biasa
  document.addEventListener("click", (e) => {
    const d = $(".lanjutan");
    if (d.open && !d.contains(e.target)) d.open = false;
    if (!$("#panel-notif").hidden && !$("#notif").contains(e.target)) bukaNotif(false);
  });
  perbaruiAkun();
  try {
    const [ringkasan] = await Promise.all([muatRingkasan(), muatDaftarEmiten(), muatCakupanData(), muatPeringkat()]);
    /* Layar lebar: kolom detail tidak dibiarkan kosong. Emiten yang paling
       banyak diberitakan dibuka lebih dulu; daftar di kiri tetap jadi pemilih. */
    const pertama = ringkasan?.emiten_teraktif?.[0]?.kode;
    if (layarLebar() && pertama && !state.kode) pilihEmiten(pertama);
  } catch (e) {
    galat(e.message);
  }
})();
