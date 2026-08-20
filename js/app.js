const KARATS = [
  { code: 999, name: "Emas 999", hint: "24K tulen" },
  { code: 916, name: "Emas 916", hint: "22K barang kemas" },
  { code: 835, name: "Emas 835", hint: "20K" },
  { code: 750, name: "Emas 750", hint: "18K" },
  { code: 585, name: "Emas 585", hint: "14K" },
  { code: 375, name: "Emas 375", hint: "9K" },
];

const FALLBACK = {
  prices: { spotSellRmPerKg: 588314 },
  lastUpdate: "2026-08-21T01:07:24+08:00",
};

let spotPerGram = FALLBACK.prices.spotSellRmPerKg / 1000;

function karatPrice(code) {
  const ratio = code === 999 ? 1 : code / 1000;
  return spotPerGram * ratio;
}

function formatRm(value) {
  return value.toLocaleString("ms-MY", {
    style: "currency",
    currency: "MYR",
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  });
}

function renderPrices() {
  const grid = document.getElementById("price-grid");
  grid.innerHTML = KARATS.map((item, index) => {
    const featured = index === 0 || item.code === 916 ? " featured" : "";
    return `
      <article class="price-card${featured}">
        <p class="karat">${item.name} · ${item.hint}</p>
        <strong>${formatRm(karatPrice(item.code))}</strong>
      </article>
    `;
  }).join("");
}

function updateCalculator() {
  const weight = Number(document.getElementById("weight").value) || 0;
  const karat = Number(document.getElementById("karat").value);
  document.getElementById("calc-value").textContent = formatRm(karatPrice(karat) * weight);
}

function formatStamp(iso) {
  try {
    return new Date(iso).toLocaleString("ms-MY", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Asia/Kuala_Lumpur",
    });
  } catch (err) {
    return iso;
  }
}

async function loadPrices() {
  const status = document.getElementById("live-status");
  try {
    const response = await fetch("/api/prices");
    if (!response.ok) throw new Error("Gagal memuatkan harga");
    const data = await response.json();
    const kg = data?.prices?.spotSellRmPerKg;
    if (!kg) throw new Error("Data harga tidak lengkap");
    spotPerGram = kg / 1000;
    status.textContent = `Harga spot 999: ${formatRm(spotPerGram)} /g · dikemas kini ${formatStamp(data.lastUpdate)}`;
  } catch (err) {
    spotPerGram = FALLBACK.prices.spotSellRmPerKg / 1000;
    status.textContent = `Menggunakan harga rujukan ${formatRm(spotPerGram)} /g · ${formatStamp(FALLBACK.lastUpdate)}`;
  }
  renderPrices();
  updateCalculator();
}

document.getElementById("gold-form").addEventListener("submit", (event) => {
  event.preventDefault();
  updateCalculator();
});

document.getElementById("weight").addEventListener("input", updateCalculator);
document.getElementById("karat").addEventListener("change", updateCalculator);

const toggle = document.querySelector(".nav-toggle");
const nav = document.getElementById("site-nav");
toggle.addEventListener("click", () => {
  const open = nav.classList.toggle("open");
  toggle.setAttribute("aria-expanded", String(open));
});

nav.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    nav.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
  });
});

loadPrices();
