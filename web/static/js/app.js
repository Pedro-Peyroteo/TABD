"use strict";

// ── Category colors ─────────────────────────────────────────
const CAT_COLORS = {
  "Ginásio":             "#ff5b3a",
  "Centro Desportivo":   "#3b82f6",
  "Piscina":             "#06b6d4",
  "Estúdio de Dança":    "#a855f7",
  "Artes Marciais":      "#ef4444",
  "Yoga / Pilates":      "#10b981",
  "Escalada":            "#f59e0b",
  "CrossFit":            "#fb923c",
  "Boxe / Kickboxing":   "#dc2626",
  "Outro":               "#6b7280",
};
const catColor = c => CAT_COLORS[c] || CAT_COLORS["Outro"];

// ── State ───────────────────────────────────────────────────
let map, drawControl, drawnLayer, radiusCircle, userMarker;
let allMarkers = [];
let activeCategory = "", activeSport = "", activeCity = "", activeSearch = "";
let activeFacility = null;
let mapInitialized = false;
let overviewCache = null;
let toastTimeout = null;
// Routing state
let routeControl = null;
let userLocation = null;     // [lat, lon] (cached after geolocate)
let routeMode = "car";       // car | foot | bike
// Geolocation watch state
let watchId = null;
let lastRadiusItems = [];    // itens actualmente no painel de raio
let lastUsedRadius = 0;

// Events state
let eventsVisible = false;
let eventMarkers = [];
let activeEventSport = "";
let activeEvent = null;
let originalPanelBody = null;  // template for facility mode

const api = async p => { const r = await fetch(p); if (!r.ok) throw new Error(p); return r.json(); };

// ── Haversine distance (km) ──────────────────────────────────
function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const φ1 = lat1 * Math.PI / 180, φ2 = lat2 * Math.PI / 180;
  const Δφ = (lat2 - lat1) * Math.PI / 180;
  const Δλ = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(Δφ / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

const fmt = n => n.toLocaleString("pt-PT");

function toast(msg, ms = 3000) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => t.classList.add("hidden"), ms);
}


// ════════════════════════════════════════════════════════════
// LANDING
// ════════════════════════════════════════════════════════════

async function bootLanding() {
  try {
    const [overview, sports, cities] = await Promise.all([
      api("/api/overview"),
      api("/api/sports"),
      api("/api/cities"),
    ]);
    overviewCache = overview;

    // Hero stats
    const statsEl = document.getElementById("hero-stats");
    const pctHours = Math.round((overview.withHours / overview.total) * 100);
    statsEl.innerHTML = [
      { label: "Instalações", value: fmt(overview.total) },
      { label: "Categorias",  value: overview.categories.length },
      { label: "Cidades",     value: overview.topCities.length + "+" },
      { label: "Com horários", value: `${pctHours}%` },
    ].map(s => `
      <div>
        <span class="hero-stat-label">${s.label}</span>
        <span class="hero-stat-value">${s.value}</span>
      </div>`).join("");

    // Dropdowns
    const catSel  = document.getElementById("lnd-cat");
    overview.categories.forEach(c =>
      catSel.insertAdjacentHTML("beforeend",
        `<option value="${c.name}">${c.name}</option>`));

    const sportSel = document.getElementById("lnd-sport");
    populateSportSelect(sportSel, sports);

    const citySel = document.getElementById("lnd-city");
    cities.slice(0, 100).forEach(c =>
      citySel.insertAdjacentHTML("beforeend",
        `<option value="${c.name}">${c.name}</option>`));

    // Refilter sports when category changes
    catSel.addEventListener("change", async () => {
      const cat = catSel.value;
      try {
        const url = cat ? `/api/sports?category=${encodeURIComponent(cat)}` : "/api/sports";
        populateSportSelect(sportSel, await api(url));
      } catch (e) { console.error("refresh sports:", e); }
    });
  } catch (e) { console.error("landing boot:", e); }
}

function populateSportSelect(selectEl, sportsData) {
  const current = selectEl.value;
  selectEl.innerHTML = `<option value="">Todas</option>`;
  sportsData.slice(0, 30).forEach(s =>
    selectEl.insertAdjacentHTML("beforeend",
      `<option value="${s.name}">${s.name}</option>`));
  if (current && sportsData.some(s => s.name === current)) selectEl.value = current;
  else selectEl.value = "";
}

function launchMap() {
  activeCategory = document.getElementById("lnd-cat").value;
  activeSport    = document.getElementById("lnd-sport").value;
  activeCity     = document.getElementById("lnd-city").value;

  document.getElementById("landing").classList.add("fade-out");
  const appEl = document.getElementById("app");
  appEl.classList.remove("app-hidden");
  appEl.classList.add("app-visible");

  if (!mapInitialized) {
    initMap();
    mapInitialized = true;
    loadFilters();
    loadKPIs();
    loadFacilities();
    renderLegend();
  } else {
    loadFacilities();
  }
  setTimeout(() => { document.getElementById("landing").style.display = "none"; }, 450);
}

function showLanding() {
  document.getElementById("landing").style.display = "flex";
  document.getElementById("landing").classList.remove("fade-out");
}


// ════════════════════════════════════════════════════════════
// GEOLOCATION + AUTO-EXPAND RADIUS
// ════════════════════════════════════════════════════════════

async function useMyLocation() {
  if (!navigator.geolocation) { toast("Geolocalização não suportada no browser."); return; }
  toast("A obter localização...", 5000);

  // Parar watch anterior se existir
  if (watchId !== null) { navigator.geolocation.clearWatch(watchId); watchId = null; }

  let firstFix = true;

  watchId = navigator.geolocation.watchPosition(
    pos => {
      const { latitude: lat, longitude: lon } = pos.coords;
      if (firstFix) {
        firstFix = false;
        if (!mapInitialized) {
          launchMap();
          setTimeout(() => locateAndExpand(lat, lon), 550);
        } else {
          locateAndExpand(lat, lon);
        }
      } else {
        // Posição actualizada — mover marcador e recalcular distâncias
        updateUserPosition(lat, lon);
      }
    },
    err => toast(`Localização indisponível: ${err.message}`, 4000),
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
  );
}

function updateUserPosition(lat, lon) {
  userLocation = [lat, lon];

  // Mover marcador
  if (userMarker) {
    userMarker.setLatLng([lat, lon]);
  } else {
    userMarker = L.circleMarker([lat, lon], {
      radius: 7, color: "#fff", weight: 2,
      fillColor: "#ff5b3a", fillOpacity: 1,
    }).addTo(map).bindTooltip("Você está aqui", { className: "leaflet-dark-tooltip" });
  }

  // Mover círculo de raio
  if (radiusCircle) radiusCircle.setLatLng([lat, lon]);

  // Recalcular distâncias dos itens no painel e reordenar
  if (lastRadiusItems.length > 0) {
    const updated = lastRadiusItems
      .map(it => ({ ...it, distKm: Math.round(haversineKm(lat, lon, it.lat, it.lon) * 100) / 100 }))
      .sort((a, b) => a.distKm - b.distKm);
    lastRadiusItems = updated;
    renderRadiusResults(updated, lastUsedRadius);
  }
}

async function locateAndExpand(lat, lon) {
  userLocation = [lat, lon];
  map.setView([lat, lon], 13);
  if (userMarker) map.removeLayer(userMarker);
  userMarker = L.circleMarker([lat, lon], {
    radius: 7, color: "#fff", weight: 2,
    fillColor: "#ff5b3a", fillOpacity: 1,
  }).addTo(map).bindTooltip("Você está aqui", { className: "leaflet-dark-tooltip" });

  // Tenta raios progressivamente maiores até encontrar resultados
  const radii = [3, 5, 10, 25, 50, 100];
  let found = null;
  let usedRadius = 0;

  for (const r of radii) {
    const data = await fetchRadius(lat, lon, r);
    if (data.length > 0) {
      found = data;
      usedRadius = r;
      if (r > 3) toast(`Sem resultados em 3 km — alargado para ${r} km · ${data.length} encontradas`, 4500);
      break;
    }
  }

  if (!found) {
    drawRadiusCircle(lat, lon, 100);
    showAreaPanel(`Sem resultados num raio de 100 km · $geoNear`, "", "");
    return;
  }

  lastRadiusItems = found;
  lastUsedRadius = usedRadius;
  drawRadiusCircle(lat, lon, usedRadius);
  renderRadiusResults(found, usedRadius);
}

async function fetchRadius(lat, lon, radiusKm) {
  const params = new URLSearchParams({ lat, lon, radius_km: radiusKm, limit: 50 });
  if (activeCategory) params.set("category", activeCategory);
  if (activeSport)    params.set("sport",    activeSport);
  try {
    return await api(`/api/geo/nearby?${params}`);
  } catch (e) { console.error("nearby:", e); return []; }
}

function drawRadiusCircle(lat, lon, radiusKm) {
  if (radiusCircle) map.removeLayer(radiusCircle);
  radiusCircle = L.circle([lat, lon], {
    radius: radiusKm * 1000,
    color: "#ff5b3a", fillColor: "#ff5b3a",
    fillOpacity: .04, weight: 1.5, dashArray: "6 4",
  }).addTo(map);
  // Auto-zoom para enquadrar
  map.fitBounds(radiusCircle.getBounds(), { padding: [40, 40], maxZoom: 14 });
  document.getElementById("btn-clear").style.display = "flex";
}

function renderRadiusResults(items, radiusKm) {
  showAreaPanel(`Raio · ${radiusKm} km · $geoNear`, items.length, items);
}


// ════════════════════════════════════════════════════════════
// MAP INIT
// ════════════════════════════════════════════════════════════

function initMap() {
  map = L.map("map", { center: [39.5, -8.0], zoom: 7, zoomControl: false });
  L.control.zoom({ position: "bottomright" }).addTo(map);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png", {
    attribution: "© OpenStreetMap · © CartoDB",
    maxZoom: 19,
  }).addTo(map);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png", {
    maxZoom: 19, pane: "shadowPane",
  }).addTo(map);

  drawnLayer = new L.FeatureGroup().addTo(map);
  map.on(L.Draw.Event.CREATED, onShapeDrawn);
  map.on("contextmenu", e => {
    map.setView(e.latlng, Math.max(map.getZoom(), 12));
    locateAndExpand(e.latlng.lat, e.latlng.lng);
  });
}


// ── Markers ─────────────────────────────────────────────────
async function loadFacilities() {
  allMarkers.forEach(m => map.removeLayer(m));
  allMarkers = [];

  const p = new URLSearchParams();
  if (activeCategory) p.set("category", activeCategory);
  if (activeSport)    p.set("sport",    activeSport);
  if (activeCity)     p.set("city",     activeCity);
  p.set("limit", "3000");

  try {
    const data = await api(`/api/facilities?${p}`);
    const filtered = activeSearch
      ? data.filter(d => d.name.toLowerCase().includes(activeSearch.toLowerCase()))
      : data;

    document.getElementById("kv-visible").textContent = fmt(filtered.length);

    filtered.forEach(f => {
      const color = catColor(f.category);
      const icon  = L.divIcon({
        html: `<div class="fac-marker" style="--cat-color:${color}"></div>`,
        className:  "",
        iconSize:   [14, 14],
        iconAnchor: [7, 7],
      });
      const marker = L.marker([f.lat, f.lon], { icon })
        .addTo(map)
        .bindTooltip(`<strong>${f.name}</strong><br><span style="color:${color}">${f.category}</span>${f.city ? ` · ${f.city}` : ""}`,
                     { className: "leaflet-dark-tooltip", offset: [0, -8], direction: "top" })
        .on("click", () => openPanel(f.osm_id));
      allMarkers.push(marker);
    });

    // Zoom para enquadrar resultados sempre que um filtro está activo
    if (filtered.length && (activeCity || activeCategory || activeSport || activeSearch)) {
      const grp = L.featureGroup(allMarkers);
      map.fitBounds(grp.getBounds().pad(0.12), { maxZoom: 14 });
    }

    // Feedback visual do filtro
    const filterLabel = activeCategory || activeSport || activeCity || activeSearch;
    if (filterLabel) {
      toast(`${fmt(filtered.length)} instalações · ${filterLabel}`, 3000);
    }
  } catch (e) { console.error("facilities:", e); }
}


// ════════════════════════════════════════════════════════════
// FILTERS + KPIs + LEGEND
// ════════════════════════════════════════════════════════════

async function loadKPIs() {
  const ov = overviewCache || await api("/api/overview");
  overviewCache = ov;
  document.getElementById("kv-total").textContent = fmt(ov.total);
  document.getElementById("kv-hours").textContent = `${Math.round(ov.withHours / ov.total * 100)}%`;
  document.getElementById("kv-web").textContent   = `${Math.round(ov.withWebsite / ov.total * 100)}%`;
}

async function loadFilters() {
  const ov = overviewCache || await api("/api/overview");
  overviewCache = ov;

  // Categorias (com cor e contagem)
  const catEl = document.getElementById("cat-filters");
  catEl.innerHTML = `<label class="filter-pill${activeCategory ? "" : " active"}" data-value="">
                       <span class="filter-dot" style="--cat-color:#8a8a93"></span>
                       Todas
                       <span class="filter-count">${fmt(ov.total)}</span>
                     </label>`;
  ov.categories.forEach(c => {
    const active = c.name === activeCategory ? " active" : "";
    catEl.insertAdjacentHTML("beforeend",
      `<label class="filter-pill${active}" data-value="${c.name}" style="--cat-color:${catColor(c.name)}">
         <span class="filter-dot"></span>
         ${c.name}
         <span class="filter-count">${fmt(c.count)}</span>
       </label>`);
  });
  catEl.querySelectorAll(".filter-pill").forEach(el =>
    el.addEventListener("click", () => setPill("cat", el)));

  await renderSportPills();
  // Events feature desativada — fora do âmbito do brief académico

  // Cidades clicáveis — carrega todas do /api/cities
  const cityEl = document.getElementById("city-list");
  const allCities = await api("/api/cities");

  function renderCityRows(list) {
    cityEl.innerHTML =
      `<div class="city-row${!activeCity ? " active" : ""}" data-city="">
         <span>Todas</span><span class="city-count">${fmt(ov.total)}</span>
       </div>` +
      list.map(c =>
        `<div class="city-row${c.name === activeCity ? " active" : ""}" data-city="${c.name}">
           <span>${c.name}</span><span class="city-count">${c.count}</span>
         </div>`).join("");
    cityEl.querySelectorAll(".city-row").forEach(r =>
      r.addEventListener("click", () => {
        activeCity = r.dataset.city;
        cityEl.querySelectorAll(".city-row").forEach(x => x.classList.toggle("active", x.dataset.city === activeCity));
        loadFacilities();
      }));
  }

  renderCityRows(allCities);

  // Pesquisa de cidades
  const citySearch = document.getElementById("city-search");
  if (citySearch) {
    citySearch.addEventListener("input", e => {
      const q = e.target.value.trim().toLowerCase();
      renderCityRows(q ? allCities.filter(c => c.name.toLowerCase().includes(q)) : allCities);
    });
  }

  // Search
  const searchEl = document.getElementById("search-input");
  let debounce;
  searchEl.addEventListener("input", e => {
    clearTimeout(debounce);
    debounce = setTimeout(() => { activeSearch = e.target.value.trim(); loadFacilities(); }, 250);
  });
}

async function setPill(type, el) {
  const groupId = type === "cat" ? "#cat-filters" : "#sport-filters";
  document.querySelectorAll(`${groupId} .filter-pill`).forEach(p => p.classList.remove("active"));
  el.classList.add("active");
  const val = el.dataset.value;
  if (type === "cat") {
    activeCategory = val;
    await renderSportPills();
  } else {
    activeSport = val;
  }
  loadFacilities();
}

async function renderSportPills() {
  const sportEl = document.getElementById("sport-filters");
  sportEl.innerHTML = `<label class="filter-pill sport${activeSport ? "" : " active"}" data-value="">Todas</label>`;
  try {
    const url = activeCategory
      ? `/api/sports?category=${encodeURIComponent(activeCategory)}`
      : "/api/sports";
    const data = await api(url);
    const names = new Set(data.map(d => d.name));
    if (activeSport && !names.has(activeSport)) activeSport = "";

    data.slice(0, 20).forEach(s => {
      const active = s.name === activeSport ? " active" : "";
      sportEl.insertAdjacentHTML("beforeend",
        `<label class="filter-pill sport${active}" data-value="${s.name}">
           ${s.name}
           <span class="filter-count">${s.count}</span>
         </label>`);
    });
    sportEl.querySelectorAll(".filter-pill").forEach(el =>
      el.addEventListener("click", () => setPill("sport", el)));
  } catch (e) { console.error("render sport pills:", e); }
}

function renderLegend() {
  const el = document.getElementById("legend");
  const ov = overviewCache;
  if (!ov) return;
  el.innerHTML =
    `<div class="legend-title">Legenda</div>` +
    ov.categories.slice(0, 6).map(c => `
      <div class="legend-row">
        <span class="legend-dot" style="background:${catColor(c.name)}"></span>
        <span>${c.name}</span>
      </div>`).join("");
}


// ════════════════════════════════════════════════════════════
// DETAIL PANEL
// ════════════════════════════════════════════════════════════

async function openPanel(osmId) {
  document.getElementById("panel").classList.remove("panel-closed");

  // Restaurar template do painel se vínhamos de event mode
  if (originalPanelBody && activeEvent) {
    document.getElementById("panel-body").innerHTML = originalPanelBody;
  }
  activeEvent = null;

  try {
    const f = await api(`/api/facilities/${osmId}`);
    if (routeControl && activeFacility && activeFacility.osm_id !== f.osm_id) clearRoute();
    activeFacility = f;

    const badge = document.getElementById("panel-cat-badge");
    badge.textContent = f.category;
    badge.style.setProperty("--cat-color", catColor(f.category));

    document.getElementById("panel-name").textContent = f.name;

    const addr = [f.address.street, f.address.housenumber].filter(Boolean).join(" ");
    const cityLine = [f.address.postcode, f.address.city].filter(Boolean).join(" ");
    document.getElementById("panel-address").textContent =
      [addr, cityLine].filter(Boolean).join(" · ") || "Sem morada registada";

    // Modalidades
    const sportsEl = document.getElementById("panel-sports");
    sportsEl.innerHTML = (f.sports || []).length
      ? f.sports.map(s => `<span class="sport-pill">${s}</span>`).join("")
      : `<span class="muted-line">Não especificadas</span>`;

    // Contactos
    const cEl = document.getElementById("panel-contacts");
    const rows = [];
    if (f.contact.phone)
      rows.push(`<div class="contact-row"><span class="contact-label">Telefone</span>
                 <a href="tel:${f.contact.phone}">${f.contact.phone}</a></div>`);
    if (f.contact.website)
      rows.push(`<div class="contact-row"><span class="contact-label">Website</span>
                 <a href="${f.contact.website}" target="_blank" rel="noopener">${shortUrl(f.contact.website)}</a></div>`);
    if (f.contact.email)
      rows.push(`<div class="contact-row"><span class="contact-label">Email</span>
                 <a href="mailto:${f.contact.email}">${f.contact.email}</a></div>`);
    if (f.operator)
      rows.push(`<div class="contact-row"><span class="contact-label">Operador</span><span>${f.operator}</span></div>`);
    cEl.innerHTML = rows.length ? rows.join("") : `<span class="muted-line">Sem contactos registados</span>`;

    document.getElementById("panel-hours").textContent =
      f.opening_hours || "Não especificados";

    const amenEl = document.getElementById("panel-amenities");
    const amenList = [
      { key: "wheelchair", label: "Acessível" },
      { key: "parking",    label: "Estacionamento" },
      { key: "shower",     label: "Balneários" },
      { key: "indoor",     label: "Interior" },
      { key: "covered",    label: "Coberto" },
    ];
    amenEl.innerHTML = amenList.map(a => {
      const v = f.amenities[a.key];
      const ok = v && v !== "no";
      const cls = ok ? "amen-yes" : v === "no" ? "amen-no" : "";
      return `<div class="amenity ${cls}">${a.label}</div>`;
    }).join("");

    map.flyTo([f.lat, f.lon], Math.max(map.getZoom(), 14), { duration: 0.5 });

    // Carregar eventos próximos
    loadFacilityEvents(f.osm_id, f.lat, f.lon);
  } catch (e) { console.error(e); }
}

function closePanel() {
  document.getElementById("panel").classList.add("panel-closed");
}

// ════════════════════════════════════════════════════════════
// ROUTING (carro / pé / bicicleta via OSRM)
// ════════════════════════════════════════════════════════════

const OSRM_ENDPOINTS = {
  car:  "https://routing.openstreetmap.de/routed-car/route/v1",
  foot: "https://routing.openstreetmap.de/routed-foot/route/v1",
  bike: "https://routing.openstreetmap.de/routed-bike/route/v1",
};

async function openDirections() {
  if (!activeFacility) return;

  // Garantir que temos a origem (GPS)
  if (!userLocation) {
    toast("A obter a sua localização...", 3000);
    const got = await requestGeolocation();
    if (!got) {
      toast("Sem localização — não é possível calcular rota.", 4000);
      return;
    }
    userLocation = got;
    if (userMarker) map.removeLayer(userMarker);
    userMarker = L.circleMarker(userLocation, {
      radius: 7, color: "#fff", weight: 2,
      fillColor: "#ff5b3a", fillOpacity: 1,
    }).addTo(map).bindTooltip("Você está aqui", { className: "leaflet-dark-tooltip" });
  }

  drawRoute();
}

function requestGeolocation() {
  return new Promise(resolve => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      pos => resolve([pos.coords.latitude, pos.coords.longitude]),
      ()  => resolve(null),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  });
}

function drawRoute() {
  if (!userLocation || !activeFacility) return;

  // Limpar rota anterior
  if (routeControl) { map.removeControl(routeControl); routeControl = null; }

  const card = document.getElementById("route-card");
  card.classList.remove("hidden");
  document.getElementById("route-info").innerHTML = `<span class="route-loading">A calcular rota (${modeLabel(routeMode)})...</span>`;
  updateModeButtons();

  routeControl = L.Routing.control({
    waypoints: [
      L.latLng(userLocation[0], userLocation[1]),
      L.latLng(activeFacility.lat, activeFacility.lon),
    ],
    router: L.Routing.osrmv1({
      serviceUrl: OSRM_ENDPOINTS[routeMode],
      profile:    "driving",   // O endpoint já implica o modo
    }),
    lineOptions: {
      styles: [
        { color: "#000", weight: 8, opacity: .35 },
        { color: "#ff5b3a", weight: 5, opacity: 1 },
      ],
      extendToWaypoints: true,
      missingRouteTolerance: 0,
    },
    show: false,
    addWaypoints: false,
    routeWhileDragging: false,
    fitSelectedRoutes: true,
    createMarker: () => null,  // já temos os nossos
  }).addTo(map);

  routeControl.on("routesfound", e => {
    const r = e.routes[0];
    document.getElementById("route-info").innerHTML = `
      <span class="route-duration">${fmtDuration(r.summary.totalTime)}</span>
      <span class="route-divider">·</span>
      <span class="route-distance">${fmtDistance(r.summary.totalDistance)}</span>`;
  });

  routeControl.on("routingerror", err => {
    console.error("routing:", err);
    document.getElementById("route-info").innerHTML =
      `<span class="route-error">Rota indisponível para ${modeLabel(routeMode)}</span>`;
  });
}

function switchRouteMode(mode) {
  if (mode === routeMode) return;
  routeMode = mode;
  if (userLocation && activeFacility) drawRoute();
  else updateModeButtons();
}

function updateModeButtons() {
  document.querySelectorAll(".route-mode").forEach(b =>
    b.classList.toggle("active", b.dataset.mode === routeMode));
}

function clearRoute() {
  if (routeControl) { map.removeControl(routeControl); routeControl = null; }
  document.getElementById("route-card").classList.add("hidden");
}

function modeLabel(mode) {
  return { car: "carro", foot: "a pé", bike: "bicicleta" }[mode] || mode;
}

function fmtDistance(m) {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`;
}
function fmtDuration(s) {
  const min = Math.round(s / 60);
  if (min < 1)  return "< 1 min";
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

function shortUrl(u) { return u.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "").slice(0, 36); }


// ════════════════════════════════════════════════════════════
// POLYGON SELECTION ($geoWithin)
// ════════════════════════════════════════════════════════════

function startDraw() {
  if (drawControl) { drawControl.disable(); drawControl = null; }
  clearDrawnShapes();
  document.getElementById("btn-draw-poly").classList.add("active");
  document.getElementById("draw-hint").classList.remove("hidden");
  drawControl = new L.Draw.Polygon(map, {
    shapeOptions: { color: "#ff5b3a", fillColor: "#ff5b3a", fillOpacity: .08, weight: 2 },
    showLength: false,
  });
  drawControl.enable();
}

async function onShapeDrawn(e) {
  document.getElementById("btn-draw-poly").classList.remove("active");
  document.getElementById("draw-hint").classList.add("hidden");
  drawnLayer.clearLayers();
  drawnLayer.addLayer(e.layer);
  document.getElementById("btn-clear").style.display = "flex";

  const coords = e.layer.toGeoJSON().geometry.coordinates[0];
  const coordStr = coords.map(c => `${c[0]},${c[1]}`).join(";");

  const params = new URLSearchParams({ coords: coordStr });
  if (activeCategory) params.set("category", activeCategory);
  if (activeSport)    params.set("sport",    activeSport);

  showAreaPanel("Polígono · $geoWithin", "...", null);

  try {
    const data = await api(`/api/geo/within?${params}`);
    if (!data.total) {
      showAreaPanel("Polígono · $geoWithin", 0, []);
      return;
    }
    renderWithinResults(data);
  } catch (err) {
    showAreaPanel("Polígono · $geoWithin · erro", 0, []);
  }
}

function clearDrawnShapes() { if (drawnLayer) drawnLayer.clearLayers(); }

function clearSelection() {
  clearDrawnShapes();
  if (radiusCircle) { map.removeLayer(radiusCircle); radiusCircle = null; }
  if (watchId !== null) { navigator.geolocation.clearWatch(watchId); watchId = null; }
  lastRadiusItems = [];
  lastUsedRadius = 0;
  document.getElementById("area-panel").classList.add("hidden");
  document.getElementById("btn-clear").style.display = "none";
  document.getElementById("btn-draw-poly").classList.remove("active");
  document.getElementById("draw-hint").classList.add("hidden");
  if (drawControl) { drawControl.disable(); drawControl = null; }
}


// ── Shared: area panel rendering ────────────────────────────
function showAreaPanel(title, total, items) {
  document.getElementById("area-title").textContent = title;
  const summary = document.getElementById("area-summary");
  const results = document.getElementById("area-results");
  document.getElementById("area-panel").classList.remove("hidden");

  if (total === "...") {
    summary.innerHTML = `<p class="muted-line">A consultar MongoDB...</p>`;
    results.innerHTML = "";
    return;
  }
  if (!total) {
    summary.innerHTML = `<p class="muted-line">Sem resultados nesta zona.</p>`;
    results.innerHTML = "";
    return;
  }
  // Default: items é uma lista plana (radius search)
  if (Array.isArray(items)) {
    summary.innerHTML = `
      <div class="area-total">${total}<small>instalações ordenadas por distância</small></div>`;
    results.innerHTML = items.map(it => `
      <div class="area-row" onclick="openPanel(${it.osm_id})">
        <span class="area-row-dot" style="--cat-color:${catColor(it.category)}"></span>
        <div class="area-row-text">
          <span class="area-row-name">${it.name}</span>
          <span class="area-row-meta">${it.category}${it.city ? ` · ${it.city}` : ""}</span>
        </div>
        <span class="area-row-dist">${it.distKm} km</span>
      </div>`).join("");
  }
}

function renderWithinResults(data) {
  const summary = document.getElementById("area-summary");
  const results = document.getElementById("area-results");
  summary.innerHTML = `
    <div class="area-total">${data.total}<small>instalações na área</small></div>
    <div class="area-breakdown">
      ${data.byCategory.map(c => `
        <span class="area-cat-chip" style="--cat-color:${catColor(c.name)}">
          ${c.name} <strong>${c.count}</strong>
        </span>`).join("")}
    </div>`;
  results.innerHTML = data.items.slice(0, 40).map(it => `
    <div class="area-row" onclick="openPanel(${it.osm_id})">
      <span class="area-row-dot" style="--cat-color:${catColor(it.category)}"></span>
      <div class="area-row-text">
        <span class="area-row-name">${it.name}</span>
        <span class="area-row-meta">${it.category}${it.city ? ` · ${it.city}` : ""}</span>
      </div>
    </div>`).join("");
}


// ════════════════════════════════════════════════════════════
// EVENTS — overview + sidebar filters + events visible by default
// ════════════════════════════════════════════════════════════

let eventsOverviewCache = null;
let activeEventSource = "";
let activeEventSearch = "";

async function initEventsSection() {
  try {
    const ov = await api("/api/events/overview");
    eventsOverviewCache = ov;

    // Tab counter
    document.getElementById("tab-count-events").textContent = ov.upcoming;
    document.getElementById("tab-count-facilities").textContent = fmt(overviewCache?.total ?? 0);

    const summary = document.getElementById("events-summary");
    summary.textContent = `${ov.upcoming} eventos futuros · ${ov.bySport.length} desportos`;
    summary.classList.remove("muted-line");

    const filtersEl = document.getElementById("events-sport-filters");
    filtersEl.innerHTML = `<label class="filter-pill sport active" data-value="">Todos</label>`;
    ov.bySport.slice(0, 12).forEach(s => {
      filtersEl.insertAdjacentHTML("beforeend",
        `<label class="filter-pill sport" data-value="${s.name}">
           ${s.name} <span class="filter-count">${s.count}</span>
         </label>`);
    });
    filtersEl.querySelectorAll(".filter-pill").forEach(el =>
      el.addEventListener("click", () => {
        filtersEl.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
        el.classList.add("active");
        activeEventSport = el.dataset.value;
        if (eventsVisible) loadEvents();
      }));

    // Toggle (defaults to ON now)
    const toggle = document.getElementById("events-toggle");
    toggle.checked = true;
    eventsVisible = true;
    toggle.addEventListener("change", e => {
      eventsVisible = e.target.checked;
      eventsVisible ? loadEvents() : clearEventMarkers();
    });

    // Load events on map immediately
    loadEvents();

    // Set up the dedicated /events view filters & grid
    initEventsView(ov);
  } catch (e) { console.error("events init:", e); }
}


// ════════════════════════════════════════════════════════════
// VIEW SWITCHING
// ════════════════════════════════════════════════════════════

function switchView(view) {
  document.querySelectorAll("#main-tabs .tab").forEach(t =>
    t.classList.toggle("active", t.dataset.view === view));
  document.getElementById("layout").classList.toggle("view-active", view === "map");
  document.getElementById("events-view").classList.toggle("view-active", view === "events");
  document.getElementById("kpi-bar-mini").style.display = view === "map" ? "flex" : "none";

  if (view === "events") {
    renderEventsGrid();
  } else if (view === "map") {
    // Ensure map redraws correctly after being hidden
    if (map) setTimeout(() => map.invalidateSize(), 100);
  }
}


// ════════════════════════════════════════════════════════════
// EVENTS VIEW (dedicated grid)
// ════════════════════════════════════════════════════════════

function initEventsView(ov) {
  // Update subtitle
  document.getElementById("events-page-sub").textContent =
    `${ov.upcoming} eventos · ${ov.bySport.length} desportos · fontes: Smoothcomp, Eventbrite, Wikidata, curados`;

  // Sport filters
  const sEl = document.getElementById("ev-sport-filters");
  sEl.innerHTML = `<label class="filter-pill sport active" data-value="">Todos</label>`;
  ov.bySport.slice(0, 16).forEach(s =>
    sEl.insertAdjacentHTML("beforeend",
      `<label class="filter-pill sport" data-value="${s.name}">
         ${s.name} <span class="filter-count">${s.count}</span>
       </label>`));
  sEl.querySelectorAll(".filter-pill").forEach(el =>
    el.addEventListener("click", () => {
      sEl.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
      el.classList.add("active");
      activeEventSport = el.dataset.value;
      renderEventsGrid();
    }));

  // Source filters — dinâmicos a partir das fontes que realmente existem
  api("/api/events/sources").then(sources => {
    const srcEl = document.getElementById("ev-source-filters");
    srcEl.innerHTML = `<label class="filter-pill sport active" data-value="">Todas</label>`;
    sources.forEach(s =>
      srcEl.insertAdjacentHTML("beforeend",
        `<label class="filter-pill sport" data-value="${s.name}">
           ${s.name} <span class="filter-count">${s.count}</span>
         </label>`));
    srcEl.querySelectorAll(".filter-pill").forEach(el =>
      el.addEventListener("click", () => {
        srcEl.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
        el.classList.add("active");
        activeEventSource = el.dataset.value;
        renderEventsGrid();
      }));
  }).catch(e => console.error("sources:", e));

  // Search
  const searchEl = document.getElementById("events-search");
  let debounce;
  searchEl.addEventListener("input", e => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      activeEventSearch = e.target.value.trim().toLowerCase();
      renderEventsGrid();
    }, 220);
  });
}

async function renderEventsGrid() {
  const grid = document.getElementById("events-grid");
  grid.innerHTML = `<div class="event-empty">A carregar...</div>`;

  const params = new URLSearchParams({ upcoming_only: "true", limit: "200" });
  if (activeEventSport) params.set("sport", activeEventSport);

  try {
    let events = await api(`/api/events?${params}`);
    if (activeEventSource) {
      events = events.filter(e => e.source === activeEventSource);
    }
    if (activeEventSearch) {
      events = events.filter(e =>
        e.title.toLowerCase().includes(activeEventSearch) ||
        (e.city && e.city.toLowerCase().includes(activeEventSearch)) ||
        (e.venue_name && e.venue_name.toLowerCase().includes(activeEventSearch))
      );
    }

    if (!events.length) {
      grid.innerHTML = `<div class="event-empty">Nenhum evento corresponde aos filtros.</div>`;
      return;
    }

    grid.innerHTML = events.map(ev => {
      const d = new Date(ev.start_date);
      const day   = d.getDate();
      const month = d.toLocaleDateString("pt-PT", { month: "short" }).replace(".", "");
      const where = [ev.venue_name, ev.city].filter(Boolean).join(" · ") || "Portugal";
      const organizer = ev.organizer || ev.source;
      return `
        <article class="event-card" onclick='openEventFromGrid(${JSON.stringify(ev).replace(/'/g,"&apos;")})'>
          <div class="event-card-top">
            <div class="event-card-date">
              <span class="ec-day">${day}</span>
              <span class="ec-month">${month}</span>
            </div>
            <div class="event-card-meta">
              <h3 class="event-card-title">${ev.title}</h3>
              <span class="event-card-where">${where}</span>
              ${organizer ? `<span class="event-card-where" style="font-size:.68rem">${organizer}</span>` : ""}
            </div>
          </div>
          <div class="event-card-tags">
            <span class="event-tag tag-sport">${ev.sport}</span>
            ${ev.category ? `<span class="event-tag">${ev.category}</span>` : ""}
            <span class="event-tag tag-source" data-source="${ev.source}">${ev.source}</span>
          </div>
        </article>`;
    }).join("");
  } catch (e) {
    console.error("renderEventsGrid:", e);
    grid.innerHTML = `<div class="event-empty">Erro a carregar eventos.</div>`;
  }
}

function openEventFromGrid(ev) {
  switchView("map");
  setTimeout(() => openEventPanel(ev), 200);
}

async function loadEvents() {
  clearEventMarkers();
  const params = new URLSearchParams({ upcoming_only: "true", limit: "100" });
  if (activeEventSport) params.set("sport", activeEventSport);

  try {
    const events = await api(`/api/events?${params}`);
    events.forEach(ev => {
      const icon = L.divIcon({
        html: `<div class="event-marker"></div>`,
        className: "",
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });
      const marker = L.marker([ev.lat, ev.lon], { icon, zIndexOffset: 500 })
        .addTo(map)
        .bindTooltip(`<strong>${ev.title}</strong><br>
                      <span style="color:#fbbf24">${fmtDate(ev.start_date)}</span> · ${ev.city}`,
                     { className: "leaflet-dark-tooltip", offset: [0, -12], direction: "top" })
        .on("click", () => openEventPanel(ev));
      eventMarkers.push(marker);
    });
    toast(`${events.length} eventos no mapa`, 2500);
  } catch (e) { console.error("loadEvents:", e); }
}

function clearEventMarkers() {
  eventMarkers.forEach(m => map.removeLayer(m));
  eventMarkers = [];
}

function openEventPanel(ev) {
  activeEvent = ev;
  activeFacility = null; // limpar para evitar conflitos com rota
  document.getElementById("panel").classList.remove("panel-closed");

  // Use o painel existente, ajustando conteúdo
  const badge = document.getElementById("panel-cat-badge");
  badge.textContent = `EVENTO · ${ev.sport.toUpperCase()}`;
  badge.style.setProperty("--cat-color", "#fbbf24");

  document.getElementById("panel-name").textContent = ev.title;
  document.getElementById("panel-address").textContent =
    `${ev.venue_name} · ${ev.address || ev.city}`;

  // Substituir os blocos: data, organização, descrição, preço, registo
  const panelBody = document.getElementById("panel-body");
  panelBody.innerHTML = `
    <div class="panel-block">
      <p class="panel-block-title">Quando</p>
      <div class="event-meta">
        <span class="event-date">
          ${fmtDateFull(ev.start_date)}
          ${ev.end_date && ev.end_date.slice(0,10) !== ev.start_date.slice(0,10)
            ? `<small>até ${fmtDateFull(ev.end_date)}</small>` : ""}
        </span>
        <span class="event-organizer">${ev.organizer || "—"}</span>
        <div class="event-card-tags" style="margin-top:.35rem">
          <span class="event-tag tag-source" data-source="${ev.source || 'manual'}">${ev.source === 'Wikidata' ? 'Dados Wikidata' : ev.source === 'manual' ? 'Curado' : ev.source}</span>
        </div>
      </div>
    </div>
    <div class="panel-block">
      <p class="panel-block-title">Descrição</p>
      <p class="event-description">${ev.description || "Sem descrição disponível."}</p>
    </div>
    ${ev.price ? `
    <div class="panel-block">
      <p class="panel-block-title">Preço / Inscrição</p>
      <div class="event-price-row">
        <span>Preço</span>
        <span>${ev.price}</span>
      </div>
    </div>` : ""}
    ${ev.near_facility ? `
    <div class="panel-block">
      <p class="panel-block-title">Instalação associada</p>
      <div class="panel-event-row" onclick="openPanel(${ev.near_facility.osm_id})">
        <div class="panel-event-info">
          <div class="panel-event-title">${ev.near_facility.name}</div>
          <div class="panel-event-meta">${ev.near_facility.category} · ${(ev.near_facility.distance_m/1000).toFixed(2)} km</div>
        </div>
      </div>
    </div>` : ""}
    <div class="panel-block">
      <button class="panel-action" onclick="openDirectionsEvent()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12l18-9-7 18-3-7-8-2z"/></svg>
        Calcular rota
      </button>
      ${ev.registration_url ? `
      <a href="${ev.registration_url}" target="_blank" rel="noopener" class="panel-action"
         style="margin-top:.5rem; background:transparent; color:#fbbf24; border:1px solid #fbbf24; text-decoration:none">
        Página oficial
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M10 14L21 3M21 14v6a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h6"/></svg>
      </a>` : ""}
    </div>
  `;

  map.flyTo([ev.lat, ev.lon], Math.max(map.getZoom(), 13), { duration: 0.5 });
}

async function openDirectionsEvent() {
  if (!activeEvent) return;
  // Reutilizar a lógica de rotas tratando o evento como destino
  activeFacility = {
    osm_id: -1,
    name: activeEvent.title,
    lat: activeEvent.lat,
    lon: activeEvent.lon,
  };
  await openDirections();
}

async function loadFacilityEvents(osmId, lat, lon) {
  try {
    const events = await api(`/api/events/by-facility/${osmId}?radius_km=5`);
    const block = document.getElementById("panel-events-block");
    const list  = document.getElementById("panel-events");
    if (!events.length) { block.style.display = "none"; return; }
    block.style.display = "block";
    list.innerHTML = events.slice(0, 5).map(ev => `
      <div class="panel-event-row" onclick='openEventPanel(${JSON.stringify(ev).replace(/'/g, "&apos;")})'>
        <div class="panel-event-date">
          <span class="pe-day">${new Date(ev.start_date).getDate()}</span>
          <span class="pe-month">${new Date(ev.start_date).toLocaleDateString("pt-PT", { month: "short" }).replace(".", "")}</span>
        </div>
        <div class="panel-event-info">
          <div class="panel-event-title">${ev.title}</div>
          <div class="panel-event-meta">${ev.sport} · ${ev.venue_name}${ev.distKm ? ` · ${ev.distKm} km` : ""}</div>
        </div>
      </div>`).join("");
  } catch (e) { console.error("facility events:", e); }
}

function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-PT", { day: "2-digit", month: "short" });
}
function fmtDateFull(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-PT", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}


// ── Boot ────────────────────────────────────────────────────
originalPanelBody = document.getElementById("panel-body").innerHTML;
bootLanding();
