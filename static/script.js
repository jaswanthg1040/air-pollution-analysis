const input = document.getElementById("placeInput");
const btn = document.getElementById("searchBtn");
const errorMsg = document.getElementById("errorMsg");
const card = document.getElementById("resultCard");

if (btn) btn.addEventListener("click", searchPlace);
if (input) input.addEventListener("keydown", (e) => { if (e.key === "Enter") searchPlace(); });

document.addEventListener("DOMContentLoaded", () => {
  loadRecords();
  loadChartData();
});

async function searchPlace() {
  if (!input || !btn || !errorMsg || !card) return;

  const place = input.value.trim();
  errorMsg.textContent = "";
  if (!place) {
    errorMsg.textContent = "Please type a place name.";
    return;
  }

  btn.textContent = "Searching...";
  btn.disabled = true;

  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ place }),
    });
    const data = await res.json();

    if (!res.ok) {
      errorMsg.textContent = data.error || "Something went wrong.";
      card.classList.add("hidden");
      return;
    }

    document.getElementById("placeName").textContent = data.place;
    document.getElementById("placeRegion").textContent =
      [data.region, data.country].filter(Boolean).join(", ");
    document.getElementById("aqiValue").textContent = data.aqi ?? "N/A";
    document.getElementById("aqiCircle").style.background = data.color;
    document.getElementById("aqiStatus").textContent = data.status;
    document.getElementById("aqiAdvice").textContent = data.advice;
    document.getElementById("pm25").textContent = data.pm25 ?? "--";
    document.getElementById("no2").textContent = data.no2 ?? "--";
    document.getElementById("so2").textContent = data.so2 ?? "--";
    document.getElementById("co").textContent = data.co ?? "--";

    card.classList.remove("hidden");
    loadRecords();
    loadChartData();
    input.value = "";

  } catch (err) {
    errorMsg.textContent = "Server error. Is the Flask app running?";
  } finally {
    btn.textContent = "Search";
    btn.disabled = false;
  }
}

async function loadRecords() {
  const container = document.getElementById("recordsList");
  if (!container) return;

  try {
    const res = await fetch("/api/records");
    const records = await res.json();
    container.innerHTML = "";

    if (!records || records.length === 0) {
      container.innerHTML = "<p class='empty'>No places searched yet.</p>";
      return;
    }

    records.forEach((r) => {
      const item = document.createElement("div");
      item.className = "record-item";

      const row = document.createElement("div");
      row.className = "record-row";
      row.style.borderLeft = `6px solid ${r.color}`;

      const heading = document.createElement("button");
      heading.className = "record-heading";
      heading.innerHTML = `<span>${r.city}</span><small>${r.date} · AQI ${r.aqi ?? "N/A"} · ${r.status}</small>`;

      const deleteBtn = document.createElement("button");
      deleteBtn.className = "btn small danger";
      deleteBtn.textContent = "🗑 Delete";
      deleteBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm(`Delete ${r.city}? This removes it from the data and all charts.`)) return;
        await fetch(`/api/delete/${r.id}`, { method: "DELETE" });
        loadRecords();
        loadChartData();
      });

      row.appendChild(heading);
      row.appendChild(deleteBtn);

      const details = document.createElement("div");
      details.className = "record-details hidden";
      details.innerHTML = `
        <div class="pollutant-grid">
          <div class="pollutant"><span>PM2.5</span><strong>${r.pm25 ?? "--"}</strong></div>
          <div class="pollutant"><span>NO2</span><strong>${r.no2 ?? "--"}</strong></div>
          <div class="pollutant"><span>SO2</span><strong>${r.so2 ?? "--"}</strong></div>
          <div class="pollutant"><span>CO</span><strong>${r.co ?? "--"}</strong></div>
        </div>
        <a class="btn small" href="/download/row/${r.id}">⬇ Download this row</a>
      `;

      heading.addEventListener("click", () => {
        details.classList.toggle("hidden");
      });

      item.appendChild(row);
      item.appendChild(details);
      container.appendChild(item);
    });
  } catch (err) {
    container.innerHTML = "<p class='empty'>Couldn't load records. Is the server running?</p>";
  }
}

// ---------- 3D INTERACTIVE CHARTS (Plotly) ----------

async function loadChartData() {
  const container = document.getElementById("plot3d");
  if (!container) return;

  try {
    const res = await fetch("/api/chart-data");
    const data = await res.json();
    const chartType = container.dataset.chart;

    if (chartType === "trend") renderTrend3D(data.trend);
    if (chartType === "citywise") renderCitywise3D(data.citywise);
    if (chartType === "distribution") renderDistribution3D(data.distribution);
  } catch (err) {
    container.innerHTML = "<p style='padding:40px;text-align:center;color:#666;'>Couldn't load chart data.</p>";
  }
}

const PALETTE_JS = ["#5B8DEF", "#7ED6A5", "#FFC857", "#EF7674", "#B98CE0", "#5FD0C4", "#F2A65A"];

function getThemeColors() {
  const isDark = document.body.classList.contains("dark");
  return {
    paper: isDark ? "#1f2233" : "#ffffff",
    plot: isDark ? "#1f2233" : "#ffffff",
    font: isDark ? "#eee" : "#1b1b1b",
    grid: isDark ? "#3a3d55" : "#e5e7eb",
  };
}

function makeBar3DTrace(items) {
  let allX = [], allY = [], allZ = [], allI = [], allJ = [], allK = [], colors = [];
  let offset = 0;

  items.forEach((it) => {
    const { x0, x1, y0, y1, z, color } = it;
    const zTop = z === 0 ? 0.01 : z;
    const verts = [
      [x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0],
      [x0, y0, zTop], [x1, y0, zTop], [x1, y1, zTop], [x0, y1, zTop],
    ];
    verts.forEach((v) => {
      allX.push(v[0]); allY.push(v[1]); allZ.push(v[2]);
      colors.push(color);
    });
    const faces = [
      [0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7],
      [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
      [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7],
    ];
    faces.forEach((f) => {
      allI.push(f[0] + offset); allJ.push(f[1] + offset); allK.push(f[2] + offset);
    });
    offset += 8;
  });

  return {
    type: "mesh3d",
    x: allX, y: allY, z: allZ,
    i: allI, j: allJ, k: allK,
    vertexcolor: colors,
    flatshading: true,
    opacity: 1,
  };
}

function baseLayout(sceneExtra) {
  const c = getThemeColors();
  return {
    margin: { l: 0, r: 0, b: 0, t: 30 },
    paper_bgcolor: c.paper,
    plot_bgcolor: c.plot,
    font: { color: c.font },
    scene: Object.assign({
      xaxis: { gridcolor: c.grid, backgroundcolor: c.paper, color: c.font },
      yaxis: { gridcolor: c.grid, backgroundcolor: c.paper, color: c.font },
      zaxis: { gridcolor: c.grid, backgroundcolor: c.paper, color: c.font },
    }, sceneExtra),
  };
}

function renderTrend3D(data) {
  const container = document.getElementById("plot3d");
  const cities = Object.keys(data || {});
  if (!cities.length) {
    container.innerHTML = "<p style='padding:40px;text-align:center;color:#666;'>No data yet. Search a place first.</p>";
    return;
  }

  const c = getThemeColors();

  const traces = cities.map((city, i) => {
    const entry = data[city];
    return {
      type: "scatter",
      mode: "lines+markers",
      name: city,
      x: entry.dates,
      y: entry.aqi,
      line: { color: PALETTE_JS[i % PALETTE_JS.length], width: 3 },
      marker: { size: 7, color: PALETTE_JS[i % PALETTE_JS.length] },
    };
  });

  const layout = {
    margin: { l: 50, r: 20, b: 50, t: 30 },
    paper_bgcolor: c.paper,
    plot_bgcolor: c.plot,
    font: { color: c.font },
    xaxis: { title: "Date", type: "category", gridcolor: c.grid, color: c.font },
    yaxis: { title: "AQI", gridcolor: c.grid, color: c.font },
    legend: { orientation: "h", y: -0.2 },
  };

  Plotly.newPlot(container, traces, layout, { responsive: true });
}

function renderCitywise3D(data) {
  const container = document.getElementById("plot3d");
  if (!data || !data.cities || data.cities.length === 0) {
    container.innerHTML = "<p style='padding:40px;text-align:center;color:#666;'>No data yet. Search a place first.</p>";
    return;
  }

  const items = data.cities.map((c, i) => ({
    x0: i, x1: i + 0.6, y0: 0, y1: 0.6,
    z: data.values[i],
    color: PALETTE_JS[i % PALETTE_JS.length],
  }));

  const trace = makeBar3DTrace(items);
  const layout = baseLayout({
    xaxis: { title: "City", tickvals: data.cities.map((c, i) => i + 0.3), ticktext: data.cities },
    yaxis: { title: "", showticklabels: false },
    zaxis: { title: "Average AQI" },
  });

  Plotly.newPlot(container, [trace], layout, { responsive: true });
}

function renderDistribution3D(data) {
  const container = document.getElementById("plot3d");
  if (!data || !data.counts || data.counts.length === 0) {
    container.innerHTML = "<p style='padding:40px;text-align:center;color:#666;'>No data yet. Search a place first.</p>";
    return;
  }

  const edges = data.edges;
  const items = data.counts.map((count, i) => {
    const span = edges[i + 1] - edges[i];
    const width = span > 0 ? span * 0.8 : 1;
    return {
      x0: edges[i], x1: edges[i] + width,
      y0: 0, y1: 0.6,
      z: count,
      color: "#5B8DEF",
    };
  });

  const trace = makeBar3DTrace(items);
  const layout = baseLayout({
    xaxis: { title: "AQI" },
    yaxis: { title: "", showticklabels: false },
    zaxis: { title: "Frequency" },
  });

  Plotly.newPlot(container, [trace], layout, { responsive: true });
}
// ---------- THEME TOGGLE ----------
function applyTheme(theme) {
  document.body.classList.toggle("dark", theme === "dark");
  localStorage.setItem("airwatch-theme", theme);
  const toggleBtn = document.getElementById("themeToggle");
  if (toggleBtn) toggleBtn.textContent = theme === "dark" ? "☀ Light" : "🌙 Dark";
  loadChartData();
}

document.addEventListener("DOMContentLoaded", () => {
  const saved = localStorage.getItem("airwatch-theme") || "light";
  applyTheme(saved);

  const toggleBtn = document.getElementById("themeToggle");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const isDark = document.body.classList.contains("dark");
      applyTheme(isDark ? "light" : "dark");
    });
  }
});
