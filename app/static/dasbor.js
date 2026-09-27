/* Dasbor sentimen emiten.
   Grafik digambar sendiri dengan SVG — tanpa pustaka luar, supaya dasbor tetap
   jalan saat demo tanpa internet. */

const $ = (s) => document.querySelector(s);
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
};

const fmtAngka = (v) => v.toLocaleString("id-ID");
const fmtSkor = (v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}`;
const fmtPersen = (v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
const fmtTglPendek = (t) => new Date(`${t}T00:00:00`).toLocaleDateString("id-ID", { day: "numeric", month: "short" });
const fmtTglPanjang = (t) =>
  new Date(`${t}T00:00:00`).toLocaleDateString("id-ID", { weekday: "short", day: "numeric", month: "long", year: "numeric" });
const kelasArah = (v) => (v == null ? "" : v > 0 ? "naik" : v < 0 ? "turun" : "");
const warnaSkor = (s) => (s > 0.05 ? "var(--positif)" : s < -0.05 ? "var(--negatif)" : "var(--netral)");

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
  return el("div", { class: "kosong" }, [el("strong", {}, judul), el("span", {}, penjelasan)]);
}

function memuat(wadah, teks = "Memuat…") {
  wadah.innerHTML = "";
  wadah.append(el("p", { class: "ket memuat" }, teks));
}

/* ---------- ringkasan ---------- */

async function muatRingkasan() {
  const r = await ambil("/api/ringkasan");
  const kartu = [
    ["Emiten dipantau", r.jumlah_emiten],
    ["Berita terkumpul", r.jumlah_berita],
    ["Sudah berlabel", r.jumlah_berlabel],
    ["Sumber berita", r.jumlah_sumber],
  ];
  const wadah = $("#ringkasan");
  wadah.innerHTML = "";
  for (const [label, angka] of kartu) {
    wadah.append(el("div", { class: "kartu" }, [
      el("div", { class: "angka" }, fmtAngka(angka)),
      el("div", { class: "label" }, label),
    ]));
  }

  const aktif = (r.emiten_teraktif || []).slice(0, 6);
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
}

async function muatDaftarEmiten() {
  state.emiten = await ambil("/api/emiten");
  const sel = $("#cari");
  const terpilih = sel.value;
  sel.innerHTML = "";
  sel.append(el("option", { value: "" }, "Pilih emiten…"));
  for (const e of state.emiten) {
    sel.append(el("option", { value: e.kode }, `${e.kode} — ${e.nama}`));
  }
  if (terpilih) sel.value = terpilih;
}

/* ---------- grafik ---------- */

const NS = "http://www.w3.org/2000/svg";
const svgEl = (t, a = {}) => {
  const n = document.createElementNS(NS, t);
  for (const [k, v] of Object.entries(a)) n.setAttribute(k, v);
  return n;
};
const teksSvg = (isi, a) => {
  const t = svgEl("text", { fill: "#8b919c", "font-size": "11", "font-family": "inherit", ...a });
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

/* Dua grafik bertumpuk berbagi sumbu waktu: harga di atas, sentimen harian di
   bawah. Sengaja tidak memakai satu grafik dua sumbu — skala rupiah dan skala
   −1…+1 yang ditumpuk membuat kemiringan garis bisa dibaca seolah berkaitan. */
function gambarGrafik(sentimen, harga) {
  state.grafik = { sentimen, harga };
  const wadah = $("#grafik");
  wadah.innerHTML = "";

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
  const langkahX = n > 1 ? lebar / (n - 1) : lebar;
  const x = (i) => P.kiri + (n > 1 ? i * langkahX : lebar / 2);
  const indeks = new Map(tanggal.map((t, i) => [t, i]));
  const petaHarga = new Map(harga.filter((d) => d.penutupan != null).map((d) => [d.tanggal, d]));
  const petaSent = new Map(sentimen.map((d) => [d.tanggal, d]));

  const svg = svgEl("svg", {
    viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img",
    "aria-label": "Grafik harga penutupan dan skor sentimen harian",
  });
  const defs = svgEl("defs");
  const grad = svgEl("linearGradient", { id: "isi-harga", x1: "0", y1: "0", x2: "0", y2: "1" });
  grad.append(svgEl("stop", { offset: "0%", "stop-color": "#5eead4", "stop-opacity": "0.28" }));
  grad.append(svgEl("stop", { offset: "100%", "stop-color": "#5eead4", "stop-opacity": "0" }));
  defs.append(grad);
  svg.append(defs);

  // --- panel harga ---
  const atas1 = P.atas;
  svg.append(teksSvg("Harga penutupan (Rp)", { x: P.kiri, y: atas1 - 12, fill: "#e8eaed", "font-size": "12", "font-weight": "600" }));
  const nilaiHarga = [...petaHarga.values()].map((d) => d.penutupan);
  let yHarga = null;
  if (nilaiHarga.length) {
    const s = sumbuHarga(Math.min(...nilaiHarga), Math.max(...nilaiHarga));
    yHarga = (v) => atas1 + H1 - ((v - s.bawah) / (s.atas - s.bawah)) * H1;
    for (const v of s.tik) {
      svg.append(svgEl("line", { x1: P.kiri, x2: P.kiri + lebar, y1: yHarga(v), y2: yHarga(v), stroke: "#1d2128" }));
      svg.append(teksSvg(fmtAngka(Math.round(v)), { x: P.kiri - 8, y: yHarga(v) + 4, "text-anchor": "end" }));
    }
    const titik = tanggal.filter((t) => petaHarga.has(t)).map((t) => [x(indeks.get(t)), yHarga(petaHarga.get(t).penutupan)]);
    if (titik.length > 1) {
      const garis = titik.map(([a, b], i) => `${i ? "L" : "M"}${a.toFixed(1)},${b.toFixed(1)}`).join(" ");
      const dasar = (atas1 + H1).toFixed(1);
      svg.append(svgEl("path", { d: `${garis} L${titik.at(-1)[0].toFixed(1)},${dasar} L${titik[0][0].toFixed(1)},${dasar} Z`, fill: "url(#isi-harga)" }));
      svg.append(svgEl("path", { d: garis, fill: "none", stroke: "#5eead4", "stroke-width": "2", "stroke-linejoin": "round", "stroke-linecap": "round" }));
    } else if (titik.length === 1) {
      svg.append(svgEl("circle", { cx: titik[0][0], cy: titik[0][1], r: 4, fill: "#5eead4" }));
    }
  } else {
    svg.append(teksSvg("Belum ada data harga pada rentang ini", { x: P.kiri + lebar / 2, y: atas1 + H1 / 2, "text-anchor": "middle" }));
  }

  // --- panel sentimen ---
  const atas2 = atas1 + H1 + JARAK;
  const ySent = (v) => atas2 + H2 / 2 - (v * H2) / 2;
  svg.append(teksSvg("Skor sentimen harian (−1 s/d +1)", { x: P.kiri, y: atas2 - 12, fill: "#e8eaed", "font-size": "12", "font-weight": "600" }));
  for (const v of [1, 0, -1]) {
    svg.append(svgEl("line", {
      x1: P.kiri, x2: P.kiri + lebar, y1: ySent(v), y2: ySent(v),
      stroke: v === 0 ? "#2a3039" : "#1d2128", ...(v === 0 ? {} : { "stroke-dasharray": "3 4" }),
    }));
    svg.append(teksSvg(v === 0 ? "0" : fmtSkor(v).replace(".00", ""), { x: P.kiri - 8, y: ySent(v) + 4, "text-anchor": "end" }));
  }
  const lebarBatang = Math.max(3, Math.min(16, langkahX * 0.6));
  const batang = new Map();
  for (const d of sentimen) {
    const cx = x(indeks.get(d.tanggal));
    const y0 = ySent(0);
    const y1 = ySent(d.skor);
    const tinggi = Math.max(2, Math.abs(y1 - y0));
    const r = svgEl("rect", {
      x: cx - lebarBatang / 2, y: d.skor >= 0 ? y0 - tinggi : y0, width: lebarBatang, height: tinggi,
      rx: Math.min(3, lebarBatang / 2), fill: warnaSkor(d.skor),
    });
    batang.set(d.tanggal, r);
    svg.append(r);
  }
  if (!sentimen.length) {
    svg.append(teksSvg("Belum ada berita berlabel pada rentang ini", { x: P.kiri + lebar / 2, y: ySent(0) - 8, "text-anchor": "middle" }));
  }

  // --- label tanggal ---
  const maksLabel = sempit ? 4 : 7;
  const loncat = Math.max(1, Math.ceil(n / maksLabel));
  tanggal.forEach((t, i) => {
    if (i % loncat && i !== n - 1) return;
    if (i !== n - 1 && n - 1 - i < loncat / 2) return; // hindari label berhimpit di ujung
    svg.append(teksSvg(fmtTglPendek(t), {
      x: x(i), y: H - 8, "text-anchor": n === 1 ? "middle" : i === 0 ? "start" : i === n - 1 ? "end" : "middle",
    }));
  });

  // --- lapisan sorot (hover / sentuh) ---
  const garisSorot = svgEl("line", { y1: atas1, y2: atas2 + H2, stroke: "#8b919c", "stroke-width": "1", "stroke-dasharray": "3 3", visibility: "hidden" });
  const titikSorot = svgEl("circle", { r: 5, fill: "#07080a", stroke: "#5eead4", "stroke-width": "2.5", visibility: "hidden" });
  svg.append(garisSorot, titikSorot);
  const tangkap = svgEl("rect", { x: P.kiri - 6, y: atas1 - 6, width: lebar + 12, height: atas2 + H2 - atas1 + 12, fill: "transparent" });
  svg.append(tangkap);

  const tip = $("#tooltip");
  let aktif = null;
  const sorot = (e) => {
    const kotak = svg.getBoundingClientRect();
    const px = ((e.clientX - kotak.left) * W) / kotak.width;
    const i = n > 1 ? Math.max(0, Math.min(n - 1, Math.round((px - P.kiri) / langkahX))) : 0;
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
      for (const [tg, r] of batang) r.setAttribute("opacity", tg === t ? "1" : "0.45");
      aktif = t;
    }
    const s = petaSent.get(t);
    tip.innerHTML = "";
    tip.append(el("div", { class: "tgl" }, fmtTglPanjang(t)));
    tip.append(el("div", { class: "baris" }, [el("span", {}, "Harga"), el("b", {}, h ? `Rp ${fmtAngka(h.penutupan)}` : "tidak ada data")]));
    const bSent = el("b", {}, s ? fmtSkor(s.skor) : "—");
    if (s) bSent.style.color = warnaSkor(s.skor);
    tip.append(el("div", { class: "baris" }, [el("span", {}, "Sentimen"), bSent]));
    tip.append(el("div", { class: "rinci" }, s
      ? `${s.jumlah_berita} berita · ${s.jumlah_positif} pos · ${s.jumlah_netral} net · ${s.jumlah_negatif} neg`
      : "tidak ada berita berlabel"));
    tip.hidden = false;
    const lebarTip = tip.offsetWidth;
    const tinggiTip = tip.offsetHeight;
    let kiri = e.clientX + 14;
    if (kiri + lebarTip > window.innerWidth - 8) kiri = e.clientX - lebarTip - 14;
    let atas = e.clientY - tinggiTip - 14;
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
    if (state.grafik && !$("#panel-grafik").hidden) gambarGrafik(state.grafik.sentimen, state.grafik.harga);
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
          akhir ? fmtTglPendek(akhir.tanggal) : `${fmtAngka(detail.jumlah_berita)} berita total`),
    kotak("Perubahan harga", ubah == null ? "—" : fmtPersen(ubah), "dalam rentang terpilih", kelasArah(ubah)),
  );
}

function tampilkanKorelasi(k) {
  const wadah = $("#korelasi");
  wadah.innerHTML = "";
  if (k.catatan) wadah.append(el("p", { class: "peringatan" }, k.catatan));

  const kotak = (judul, kor) =>
    el("div", { class: "kotak" }, [
      el("div", { class: "ket" }, judul),
      el("div", { class: `nilai ${kor ? kelasArah(kor.koefisien) : ""}` },
         kor ? (kor.koefisien > 0 ? "+" : "") + kor.koefisien.toFixed(3) : "—"),
      el("div", { class: "ket" }, kor ? `${kor.kekuatan} · n=${kor.n}` : "belum cukup data"),
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
  return el("span", { class: `lencana ${label.sentimen}` }, `${label.sentimen} ${(label.keyakinan * 100).toFixed(0)}%`);
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
    wadah.append(kosong("Tidak ada berita yang cocok",
      "Longgarkan saringan sentimen atau status, atau perlebar rentang tanggalnya."));
    return;
  }

  for (const b of daftar) {
    const tgl = b.terbit_pada
      ? new Date(b.terbit_pada).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" })
      : "tanggal tidak diketahui";
    const aksi = el("div", { class: "aksi" });
    if (state.saya && state.saya.peran === "analis") {
      for (const sent of ["positif", "netral", "negatif"]) {
        const tombol = el("button", {}, `koreksi: ${sent}`);
        tombol.onclick = async () => {
          tombol.disabled = true;
          try {
            await fetch(`/api/berita/${b.id}/koreksi`, {
              method: "POST",
              headers: { "Content-Type": "application/json", ...kepala() },
              body: JSON.stringify({ kode_emiten: state.kode, sentimen: sent }),
            });
            await muatBerita();
            await muatEmiten({ gulir: false });
          } finally {
            tombol.disabled = false;
          }
        };
        aksi.append(tombol);
      }
    }

    const jejak = el("div", { class: "jejak", hidden: "hidden" });
    const lihat = el("button", {}, "dasar verifikasi");
    lihat.onclick = async () => {
      if (!jejak.hidden) { jejak.hidden = true; return; }
      jejak.innerHTML = "";
      try {
        const riwayat = await ambil(`/api/berita/${b.id}/jejak`);
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
    aksi.append(lihat);

    const isi = el("div", { class: "isi" }, [
      el("a", { class: "judul", href: b.url, target: "_blank", rel: "noreferrer" }, b.judul),
      el("div", { class: "meta" }, [
        lencanaLabel(b.label),
        b.label && b.label.asal === "analis" ? el("span", { class: "lencana analis" }, "dikoreksi analis") : null,
        el("span", {}, b.sumber),
        el("span", {}, tgl),
        el("span", {}, NAMA_STATUS[b.status_verifikasi] || b.status_verifikasi),
        b.emiten.length > 1 ? el("span", {}, b.emiten.join(", ")) : null,
      ]),
      aksi,
      jejak,
    ]);
    const kelas = b.label ? b.label.sentimen : "";
    wadah.append(el("div", { class: `berita-item ${kelas}` }, [el("span", { class: "strip" }), isi]));
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
    ? state.baris.filter((b) => b.kode.toLowerCase().includes(q) || b.nama.toLowerCase().includes(q))
    : state.baris;

  if (!baris.length) {
    wadah.append(q
      ? kosong("Tidak ada emiten yang cocok", `Tidak ditemukan “${q}”. Coba kode (mis. BBCA) atau nama perusahaan.`)
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
    tr.append(el("td", { class: "kiri emiten" }, [el("div", { class: "kode" }, b.kode), el("div", { class: "nama" }, b.nama)]));
    tr.append(el("td", { class: "kiri opsional redup" }, b.sektor || "—"));
    tr.append(selSkor(b.skor));
    tr.append(el("td", { class: b.jumlah_berita ? "opsional-hp" : "sepi opsional-hp" }, String(b.jumlah_berita)));
    tr.append(el("td", { class: "opsional" }, String(b.jumlah_positif)));
    tr.append(el("td", { class: "opsional" }, String(b.jumlah_negatif)));
    tr.append(el("td", { class: "opsional" }, b.harga_terakhir == null ? "—" : fmtAngka(b.harga_terakhir)));
    const u = b.perubahan_harga;
    tr.append(el("td", { class: u == null ? "sepi" : kelasArah(u) }, u == null ? "—" : fmtPersen(u)));
    const buka = () => pilihEmiten(b.kode);
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
    state.baris = d.baris;
    gambarPeringkat();
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
  document.body.dataset.peran = masuk ? state.saya.peran : "tamu";
}

async function kirimMasuk() {
  const g = $("#galat-masuk");
  g.hidden = true;
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
  if (state.kode) muatBerita();
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
    const kode = el("span", { class: "wl-kode" }, w.kode);
    kode.onclick = () => pilihEmiten(w.kode);
    const buang = el("button", { class: "tombol garis kecil" }, "Hapus");
    buang.onclick = async () => {
      await ambil(`/api/watchlist/${w.kode}`, { method: "DELETE" });
      await muatWatchlist();
    };
    wadah.append(el("div", { class: "wl-item" }, [
      kode,
      el("span", { class: "wl-nama" }, w.nama),
      el("span", { class: `wl-angka ${kelasArah(skor)}` }, skor == null ? "skor —" : `skor ${fmtSkor(skor)}`),
      el("span", { class: "wl-angka" }, `${w.berita_7_hari} berita/7h`),
      el("span", { class: "wl-angka" }, w.harga_terakhir == null ? "—" : fmtAngka(w.harga_terakhir)),
      buang,
    ]));
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

function pilihEmiten(kode) {
  $("#cari").value = kode;
  muatEmiten({ gulir: true });
}

async function muatEmiten({ gulir = false } = {}) {
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
  const panel = $("#panel-grafik");
  const pertamaKali = panel.hidden;
  panel.hidden = false;
  $("#panel-berita").hidden = false;
  if (gulir || pertamaKali) panel.scrollIntoView({ behavior: "smooth", block: "start" });
  $("#kode-emiten").textContent = kode;
  memuat($("#grafik"));

  try {
    const [detail, sentimen, harga, kor] = await Promise.all([
      ambil(`/api/emiten/${kode}`),
      ambil(`/api/emiten/${kode}/sentimen?${p}`),
      ambil(`/api/emiten/${kode}/harga?${p}`),
      ambil(`/api/emiten/${kode}/korelasi?${pk}`),
    ]);

    $("#judul-emiten").textContent = `${detail.nama}${detail.sektor ? " · " + detail.sektor : ""}`;
    tampilkanMetrik(sentimen.titik, harga.titik, detail);
    gambarGrafik(sentimen.titik, harga.titik);

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
    if (state.baris.length) gambarPeringkat();
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
  $("#tooltip").hidden = true;
  if (state.baris.length) gambarPeringkat();
}

const iso = (d) => d.toISOString().slice(0, 10);

function pasangRentang(mulai, sampai, tombol) {
  $("#mulai").value = mulai;
  $("#sampai").value = sampai;
  for (const b of document.querySelectorAll("#pintasan button")) b.classList.toggle("aktif", b === tombol);
  muatPeringkat();
  if (state.kode) muatEmiten();
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
    `Data tersedia — berita: ${c.berita_mulai || "—"} s/d ${c.berita_sampai || "—"} · ` +
    `harga: ${c.harga_mulai || "—"} s/d ${c.harga_sampai || "—"}`;
}

function pasangPintasan() {
  for (const b of document.querySelectorAll("#pintasan button")) {
    b.onclick = () => {
      const kini = new Date();
      if (b.dataset.hari) {
        pasangRentang(iso(new Date(kini.getTime() - Number(b.dataset.hari) * 86400000)), iso(kini), b);
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
  $("#muat").onclick = () => {
    // tanggal diubah manual: tidak lagi cocok dengan pintasan mana pun
    for (const b of document.querySelectorAll("#pintasan button")) b.classList.remove("aktif");
    muatPeringkat();
    if (state.kode) muatEmiten();
  };
  $("#hanya-berberita").onchange = muatPeringkat;
  $("#cari-tabel").addEventListener("input", gambarPeringkat);
  $("#tombol-masuk").onclick = () => {
    if (state.saya) return keluar();
    const p = $("#panel-masuk");
    p.hidden = !p.hidden;
    if (!p.hidden) $("#masuk-email").focus();
  };
  $("#kirim-masuk").onclick = kirimMasuk;
  $("#masuk-sandi").addEventListener("keydown", (e) => { if (e.key === "Enter") kirimMasuk(); });
  $("#tambah-watchlist").onclick = tambahKeWatchlist;
  $("#tutup-detail").onclick = tutupDetail;
  perbaruiAkun();
  $("#cari").addEventListener("change", () => {
    if ($("#cari").value) muatEmiten({ gulir: true });
    else tutupDetail();
  });
  $("#maks-emiten").onchange = () => {
    muatPeringkat();
    if (state.kode) muatEmiten();
  };
  $("#saring-sentimen").onchange = muatBerita;
  $("#saring-status").onchange = muatBerita;
  try {
    await Promise.all([muatRingkasan(), muatDaftarEmiten(), muatCakupanData(), muatPeringkat()]);
  } catch (e) {
    galat(e.message);
  }
})();
