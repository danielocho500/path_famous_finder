(() => {
  "use strict";

  const getApiBase = () => {
    const path = window.location.pathname;
    if (path.endsWith("/finder")) {
      return path.slice(0, -"/finder".length) + "/api/v1";
    }
    return path.replace(/\/+$/, "") + "/api/v1";
  };

  const API_BASE = getApiBase();

  const state = {
    pool: [],
    selectedFrom: null,
    selectedTo: null,
    suggestionsFrom: [],
    suggestionsTo: [],
    activeIndexFrom: -1,
    activeIndexTo: -1,
    pathData: null,
    currentStepIndex: 0,
    map: null,
    graticuleLayer: null,
    fullRouteLine: null,
    traversedRouteLine: null,
    stepMarkers: [],
    blueDotMarker: null,
    blueDotAnimFrame: null,
    blueDotCurrentLatLng: null,
  };

  const el = {
    mapStage: document.getElementById("map-stage"),
    mapContainer: document.getElementById("antique-map"),

    selectorOverlay: document.getElementById("selector-overlay"),
    hudOverlay: document.getElementById("hud-overlay"),

    imgSelectFrom: document.getElementById("img-select-from"),
    monoSelectFrom: document.getElementById("mono-select-from"),
    titleSelectFrom: document.getElementById("title-select-from"),
    metaSelectFrom: document.getElementById("meta-select-from"),
    inputFrom: document.getElementById("input-from"),
    clearFrom: document.getElementById("clear-from"),
    listFrom: document.getElementById("list-from"),

    imgSelectTo: document.getElementById("img-select-to"),
    monoSelectTo: document.getElementById("mono-select-to"),
    titleSelectTo: document.getElementById("title-select-to"),
    metaSelectTo: document.getElementById("meta-select-to"),
    inputTo: document.getElementById("input-to"),
    clearTo: document.getElementById("clear-to"),
    listTo: document.getElementById("list-to"),

    btnDice: document.getElementById("btn-dice"),
    findPathBtn: document.getElementById("find-path-btn"),
    statusBanner: document.getElementById("status-banner"),

    btnBackSearch: document.getElementById("btn-back-search"),
    btnWorldView: document.getElementById("btn-world-view"),
    routeTitle: document.getElementById("route-title"),
    routeKicker: document.getElementById("route-kicker"),

    imgStepFrom: document.getElementById("img-step-from"),
    fallbackStepFrom: document.getElementById("fallback-step-from"),
    roleStepFrom: document.getElementById("role-step-from"),
    nameStepFrom: document.getElementById("name-step-from"),
    lifeStepFrom: document.getElementById("life-step-from"),

    stepSupertype: document.getElementById("step-supertype"),
    stepTypeLabel: document.getElementById("step-type-label"),
    stepContextName: document.getElementById("step-context-name"),

    imgStepTo: document.getElementById("img-step-to"),
    fallbackStepTo: document.getElementById("fallback-step-to"),
    roleStepTo: document.getElementById("role-step-to"),
    nameStepTo: document.getElementById("name-step-to"),
    lifeStepTo: document.getElementById("life-step-to"),

    navPrev: document.getElementById("nav-prev"),
    prevCaption: document.getElementById("prev-caption"),
    navNext: document.getElementById("nav-next"),
    nextCaption: document.getElementById("next-caption"),

    stepBadge: document.getElementById("step-badge"),
    stepDate: document.getElementById("step-date"),
    stepPlace: document.getElementById("step-place"),
    mapCoordsReadout: document.getElementById("map-coords-readout"),
    stepNarrative: document.getElementById("step-narrative"),
    stepSources: document.getElementById("step-sources"),
  };

  // --- Formatting Helpers ---

  const ROMAN_NUMERALS = [
    "", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
  ];

  function toRoman(num) {
    return ROMAN_NUMERALS[num] || String(num);
  }

  function getInitials(name) {
    if (!name) return "?";
    const parts = name
      .replace(/[()]/g, "")
      .trim()
      .split(/\s+/)
      .filter((w) => w.length > 0 && !["de", "del", "la", "el", "los", "las", "von", "van"].includes(w.toLowerCase()));
    if (parts.length === 0) return name.slice(0, 2).toUpperCase();
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function extractYear(val) {
    if (!val) return null;
    if (typeof val === "object") {
      if (val.year == null) return null;
      const yr = Number(val.year);
      const prefix = val.approximate ? "c. " : "";
      if (yr < 0) return `${prefix}${Math.abs(yr)} a. C.`;
      if (yr < 1000) return `${prefix}${yr} d. C.`;
      return `${prefix}${yr}`;
    }
    const s = String(val).trim();
    if (s.startsWith("-")) {
      const m = s.match(/^-(\d+)/);
      return m ? `${parseInt(m[1], 10)} a. C.` : s;
    }
    const m = s.match(/^(\d{1,4})/);
    if (!m) return s;
    const yr = parseInt(m[1], 10);
    return yr < 1000 ? `${yr} d. C.` : String(yr);
  }

  function formatLifespan(person) {
    if (!person) return "";
    const b = extractYear(person.birth || person.birth_date);
    const d = extractYear(person.death || person.death_date);
    if (b && d) return `${b} – ${d}`;
    if (b) return `n. ${b}`;
    if (d) return `† ${d}`;
    return "";
  }

  function getPersonOccupation(person) {
    if (!person) return "Figura histórica documentada";
    return (
      person.principal_occupation ||
      person.occupation ||
      person.description ||
      "Figura histórica documentada"
    );
  }

  const MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
  ];

  function formatSingleIsoDate(val) {
    if (!val) return "";
    if (typeof val === "object") {
      if (val.year == null) return "";
      const yr = Number(val.year);
      const approx = val.approximate ? "c. " : "";
      const yrLabel = yr < 0 ? `${Math.abs(yr)} a. C.` : yr < 600 ? `${yr} d. C.` : String(yr);
      if (val.month && val.day) {
        const mName = MONTHS_ES[Number(val.month) - 1] || "";
        if (mName) return `${approx}${val.day} de ${mName} de ${yrLabel}`;
      }
      if (val.month) {
        const mName = MONTHS_ES[Number(val.month) - 1] || "";
        if (mName) return `${approx}${mName} de ${yrLabel}`;
      }
      return `${approx}${yrLabel}`;
    }
    const s = String(val).trim();
    if (s.startsWith("-")) {
      const m = s.match(/^-(\d+)/);
      return m ? `${parseInt(m[1], 10)} a. C.` : s;
    }
    const fullMatch = s.match(/^(\d{3,4})-(\d{2})-(\d{2})/);
    if (fullMatch) {
      const year = parseInt(fullMatch[1], 10);
      const monthIdx = parseInt(fullMatch[2], 10) - 1;
      const day = parseInt(fullMatch[3], 10);
      const monthName = MONTHS_ES[monthIdx] || "";
      if (monthName) return `${day} de ${monthName} de ${year}`;
      return String(year);
    }
    const ymMatch = s.match(/^(\d{3,4})-(\d{2})$/);
    if (ymMatch) {
      const year = parseInt(ymMatch[1], 10);
      const monthIdx = parseInt(ymMatch[2], 10) - 1;
      const monthName = MONTHS_ES[monthIdx] || "";
      return monthName ? `${monthName} de ${year}` : String(year);
    }
    const yMatch = s.match(/^(\d{1,4})$/);
    if (yMatch) {
      const yr = parseInt(yMatch[1], 10);
      return yr < 600 ? `${yr} d. C.` : String(yr);
    }
    return s;
  }

  function formatPeriod(period) {
    if (!period) return "Fecha histórica";
    const start = period.start;
    const end = period.end;
    if (!start && !end) return "Fecha documentada";
    const sFmt = formatSingleIsoDate(start);
    const eFmt = formatSingleIsoDate(end);
    if (sFmt && (!eFmt || sFmt === eFmt)) return sFmt;
    return `${sFmt} – ${eFmt}`;
  }

  function formatDMS(lat, lng) {
    if (lat == null || lng == null || Number.isNaN(Number(lat)) || Number.isNaN(Number(lng))) {
      return "";
    }
    const toDms = (deg, posHem, negHem) => {
      const hem = deg >= 0 ? posHem : negHem;
      const abs = Math.abs(Number(deg));
      const d = Math.floor(abs);
      const mFloat = (abs - d) * 60;
      const m = Math.floor(mFloat);
      const s = Math.round((mFloat - m) * 60);
      return `${d}°${String(m).padStart(2, "0")}′${String(s).padStart(2, "0")}″${hem}`;
    };
    return `${toDms(lat, "N", "S")} · ${toDms(lng, "E", "O")}`;
  }

  function formatPlaceLine(location) {
    if (!location) return "Ubicación histórica documentada";
    const parts = [];
    if (location.name) parts.push(location.name);
    const cityCountry = [location.city, location.country]
      .filter((x) => x && x !== location.name)
      .join(", ");
    if (cityCountry) parts.push(cityCountry);
    return parts.join(" · ") || "Ubicación histórica documentada";
  }

  function formatShortPlace(location) {
    if (!location) return "Archivo";
    return location.city || location.name || location.country || "Archivo";
  }

  const SUPERTYPE_LABELS = {
    personal: "Vínculo personal o familiar",
    personal_and_professional: "Encuentro directo / profesional",
    professional: "Colaboración u obra compartida",
  };

  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showStatus(msg, isError = false) {
    if (!msg) {
      el.statusBanner.hidden = true;
      el.statusBanner.textContent = "";
      el.statusBanner.classList.remove("error");
      return;
    }
    el.statusBanner.textContent = msg;
    el.statusBanner.classList.toggle("error", Boolean(isError));
    el.statusBanner.hidden = false;
  }

  // --- API Calls ---

  async function fetchPeopleSearch(query, limit = 10) {
    const url = `${API_BASE}/people/search?q=${encodeURIComponent(query || "")}&limit=${limit}`;
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Error al buscar personajes (${res.status})`);
    }
    const data = await res.json();
    return Array.isArray(data) ? data : data.items || [];
  }

  async function fetchShortestPath(fromId, toId) {
    const url = `${API_BASE}/paths/shortest?from_id=${encodeURIComponent(fromId)}&to_id=${encodeURIComponent(toId)}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `Error al calcular la ruta (${res.status})`);
    }
    return data;
  }

  // --- Portrait Helper ---

  function applyPortrait(imgEl, fallbackEl, person) {
    const name = person?.name || "";
    const initials = getInitials(name);
    fallbackEl.textContent = initials;

    if (person?.image_url) {
      imgEl.hidden = false;
      fallbackEl.hidden = true;
      imgEl.alt = `Retrato de ${name}`;
      imgEl.onerror = () => {
        imgEl.hidden = true;
        fallbackEl.hidden = false;
      };
      imgEl.src = person.image_url;
    } else {
      imgEl.removeAttribute("src");
      imgEl.hidden = true;
      fallbackEl.hidden = false;
    }
  }

  // --- Two Portrait Boxes (Left & Right) + Autocomplete ---

  function debounce(fn, delay = 110) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  function renderSelectBox(slot, person) {
    const isFrom = slot === "from";
    const imgEl = isFrom ? el.imgSelectFrom : el.imgSelectTo;
    const monoEl = isFrom ? el.monoSelectFrom : el.monoSelectTo;
    const titleEl = isFrom ? el.titleSelectFrom : el.titleSelectTo;
    const metaEl = isFrom ? el.metaSelectFrom : el.metaSelectTo;
    const inputEl = isFrom ? el.inputFrom : el.inputTo;
    const clearBtn = isFrom ? el.clearFrom : el.clearTo;
    const listEl = isFrom ? el.listFrom : el.listTo;

    if (!person) {
      imgEl.removeAttribute("src");
      imgEl.hidden = true;
      monoEl.textContent = "?";
      monoEl.hidden = false;
      titleEl.textContent = "Selecciona un personaje";
      metaEl.textContent = "Escribe abajo o tira los dados";
      clearBtn.hidden = !inputEl.value;
      return;
    }

    applyPortrait(imgEl, monoEl, person);
    titleEl.textContent = person.name;
    const life = formatLifespan(person);
    const occ = getPersonOccupation(person);
    metaEl.textContent = [life, occ].filter(Boolean).join(" · ");

    inputEl.value = person.name;
    clearBtn.hidden = false;
    listEl.hidden = true;
    inputEl.setAttribute("aria-expanded", "false");
  }

  function selectPerson(slot, person) {
    if (slot === "from") {
      state.selectedFrom = person;
      renderSelectBox("from", person);
    } else {
      state.selectedTo = person;
      renderSelectBox("to", person);
    }
    showStatus("");
  }

  function renderAutocompleteList(slot, items, query) {
    const isFrom = slot === "from";
    const listEl = isFrom ? el.listFrom : el.listTo;
    const inputEl = isFrom ? el.inputFrom : el.inputTo;

    if (isFrom) {
      state.suggestionsFrom = items;
      state.activeIndexFrom = items.length > 0 ? 0 : -1;
    } else {
      state.suggestionsTo = items;
      state.activeIndexTo = items.length > 0 ? 0 : -1;
    }

    if (!items || items.length === 0) {
      listEl.innerHTML = `
        <div class="ac-empty">
          No se encontraron coincidencias para «${escapeHtml(query)}».
        </div>
      `;
      listEl.hidden = false;
      inputEl.setAttribute("aria-expanded", "true");
      return;
    }

    const headerLabel = query.trim()
      ? `Coincidencias para «${escapeHtml(query.trim())}»`
      : `Personajes del archivo`;

    const rowsHtml = items
      .map((person, idx) => {
        const lifespan = formatLifespan(person);
        const occ = getPersonOccupation(person);
        const initials = getInitials(person.name);
        const isActive = idx === 0 ? "active" : "";

        return `
          <button
            type="button"
            class="ac-item ${isActive}"
            role="option"
            aria-selected="${idx === 0 ? "true" : "false"}"
            data-index="${idx}"
          >
            <div class="ac-thumb">
              ${
                person.image_url
                  ? `<img src="${escapeHtml(person.image_url)}" alt="" loading="lazy" onerror="this.hidden=true;this.nextElementSibling.hidden=false;">
                     <span class="ac-monogram" hidden>${escapeHtml(initials)}</span>`
                  : `<span class="ac-monogram">${escapeHtml(initials)}</span>`
              }
            </div>
            <div class="ac-main">
              <span class="ac-name">${escapeHtml(person.name)}</span>
              <span class="ac-sub">${escapeHtml(occ)}</span>
            </div>
            <span class="ac-years">${escapeHtml(lifespan)}</span>
          </button>
        `;
      })
      .join("");

    listEl.innerHTML = `
      <div class="ac-header">
        <span>${headerLabel}</span>
        <span>Top ${items.length}</span>
      </div>
      ${rowsHtml}
    `;
    listEl.hidden = false;
    inputEl.setAttribute("aria-expanded", "true");

    listEl.querySelectorAll(".ac-item").forEach((optEl) => {
      optEl.addEventListener("mousedown", (ev) => {
        ev.preventDefault();
        const idx = Number(optEl.dataset.index);
        const chosen = items[idx];
        if (chosen) {
          selectPerson(slot, chosen);
        }
      });
    });
  }

  function updateActiveOption(slot, newIndex) {
    const isFrom = slot === "from";
    const listEl = isFrom ? el.listFrom : el.listTo;
    const items = isFrom ? state.suggestionsFrom : state.suggestionsTo;
    if (!items.length) return;

    const bounded = ((newIndex % items.length) + items.length) % items.length;
    if (isFrom) {
      state.activeIndexFrom = bounded;
    } else {
      state.activeIndexTo = bounded;
    }

    const optionEls = listEl.querySelectorAll(".ac-item");
    optionEls.forEach((node, idx) => {
      const active = idx === bounded;
      node.classList.toggle("active", active);
      node.setAttribute("aria-selected", active ? "true" : "false");
      if (active) node.scrollIntoView({ block: "nearest" });
    });
  }

  function setupCombobox(slot) {
    const isFrom = slot === "from";
    const inputEl = isFrom ? el.inputFrom : el.inputTo;
    const clearBtn = isFrom ? el.clearFrom : el.clearTo;
    const listEl = isFrom ? el.listFrom : el.listTo;

    const runSearch = debounce(async (q) => {
      try {
        const items = await fetchPeopleSearch(q, 10);
        renderAutocompleteList(slot, items, q);
      } catch (err) {
        console.error(err);
      }
    }, 100);

    inputEl.addEventListener("focus", () => {
      const currentVal = inputEl.value.trim();
      const selected = isFrom ? state.selectedFrom : state.selectedTo;
      const queryToUse = selected && selected.name === currentVal ? "" : currentVal;
      runSearch(queryToUse);
    });

    inputEl.addEventListener("input", () => {
      const val = inputEl.value;
      clearBtn.hidden = !val;
      runSearch(val);
    });

    inputEl.addEventListener("keydown", (ev) => {
      const items = isFrom ? state.suggestionsFrom : state.suggestionsTo;
      const activeIdx = isFrom ? state.activeIndexFrom : state.activeIndexTo;

      if (ev.key === "ArrowDown") {
        if (listEl.hidden) {
          runSearch(inputEl.value);
        } else {
          ev.preventDefault();
          updateActiveOption(slot, activeIdx + 1);
        }
      } else if (ev.key === "ArrowUp") {
        if (!listEl.hidden) {
          ev.preventDefault();
          updateActiveOption(slot, activeIdx - 1);
        }
      } else if (ev.key === "Enter") {
        if (!listEl.hidden && items.length > 0 && activeIdx >= 0) {
          ev.preventDefault();
          selectPerson(slot, items[activeIdx]);
          inputEl.blur();
        } else {
          ev.preventDefault();
          executeShortestPathSearch();
        }
      } else if (ev.key === "Escape") {
        listEl.hidden = true;
        inputEl.setAttribute("aria-expanded", "false");
      }
    });

    inputEl.addEventListener("blur", () => {
      setTimeout(() => {
        listEl.hidden = true;
        inputEl.setAttribute("aria-expanded", "false");
      }, 160);
    });

    clearBtn.addEventListener("click", () => {
      inputEl.value = "";
      clearBtn.hidden = true;
      inputEl.focus();
    });
  }

  // --- Random Dice Picker ---

  async function ensurePeoplePool() {
    if (state.pool.length >= 2) return state.pool;
    const all = await fetchPeopleSearch("", 120);
    const connectedWithImg = all.filter((p) => (p.degree || 0) > 0 && p.image_url);
    state.pool = connectedWithImg.length >= 2 ? connectedWithImg : all;
    return state.pool;
  }

  async function rollRandomPair() {
    try {
      el.btnDice.classList.add("rolling");
      setTimeout(() => el.btnDice.classList.remove("rolling"), 430);

      const pool = await ensurePeoplePool();
      if (pool.length < 2) return;

      const idx1 = Math.floor(Math.random() * pool.length);
      let idx2 = Math.floor(Math.random() * (pool.length - 1));
      if (idx2 >= idx1) idx2 += 1;

      selectPerson("from", pool[idx1]);
      selectPerson("to", pool[idx2]);
    } catch (err) {
      console.error(err);
    }
  }

  // --- Full-Tab Antique Map & Moving Blue Dot ---

  function ensureAntiqueMap() {
    if (state.map) return state.map;

    const map = L.map(el.mapContainer, {
      center: [24, -15],
      zoom: 3,
      minZoom: 2,
      maxZoom: 15,
      zoomControl: true,
      worldCopyJump: true,
      attributionControl: true,
    });

    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}", {
      attribution: '&copy; National Geographic, Esri, OSM &middot; Atlas Histórico',
      maxZoom: 16,
      maxNativeZoom: 12,
    }).addTo(map);

    const graticuleGroup = L.layerGroup().addTo(map);
    const parallelStyle = {
      color: "#8c7250",
      weight: 0.85,
      opacity: 0.42,
      dashArray: "4 6",
      interactive: false,
    };
    L.polyline([[0, -180], [0, 180]], {
      color: "#755a38",
      weight: 1.1,
      opacity: 0.5,
      dashArray: "8 4",
      interactive: false,
    }).addTo(graticuleGroup);
    [23.436, -23.436, 45, -45, 66.56].forEach((lat) => {
      L.polyline([[lat, -180], [lat, 180]], parallelStyle).addTo(graticuleGroup);
    });
    [-135, -90, -45, 0, 45, 90, 135].forEach((lng) => {
      L.polyline([[-80, lng], [80, lng]], parallelStyle).addTo(graticuleGroup);
    });

    state.map = map;
    state.graticuleLayer = graticuleGroup;
    return map;
  }

  function getStepLatLng(step) {
    const loc = step?.location;
    if (loc && loc.lat != null && loc.lng != null) {
      return [Number(loc.lat), Number(loc.lng)];
    }
    return [20.0, 0.0];
  }

  function animateBlueDotTo(targetLatLng, durationMs = 900) {
    if (!state.blueDotMarker) return;
    if (state.blueDotAnimFrame) {
      cancelAnimationFrame(state.blueDotAnimFrame);
      state.blueDotAnimFrame = null;
    }

    const startLatLng = state.blueDotCurrentLatLng || targetLatLng;
    const [startLat, startLng] = startLatLng;
    const [endLat, endLng] = targetLatLng;

    if (
      Math.abs(startLat - endLat) < 0.0001 &&
      Math.abs(startLng - endLng) < 0.0001
    ) {
      state.blueDotMarker.setLatLng(targetLatLng);
      state.blueDotCurrentLatLng = targetLatLng;
      return;
    }

    const startTime = performance.now();
    const easeInOutCubic = (t) =>
      t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

    const tick = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / durationMs);
      const eased = easeInOutCubic(progress);

      const curLat = startLat + (endLat - startLat) * eased;
      const curLng = startLng + (endLng - startLng) * eased;
      const pos = [curLat, curLng];

      state.blueDotMarker.setLatLng(pos);
      state.blueDotCurrentLatLng = pos;

      if (progress < 1) {
        state.blueDotAnimFrame = requestAnimationFrame(tick);
      } else {
        state.blueDotAnimFrame = null;
      }
    };

    state.blueDotAnimFrame = requestAnimationFrame(tick);
  }

  function renderMapForPath(steps) {
    const map = ensureAntiqueMap();

    if (state.fullRouteLine) {
      map.removeLayer(state.fullRouteLine);
      state.fullRouteLine = null;
    }
    if (state.traversedRouteLine) {
      map.removeLayer(state.traversedRouteLine);
      state.traversedRouteLine = null;
    }
    state.stepMarkers.forEach((m) => map.removeLayer(m));
    state.stepMarkers = [];
    if (state.blueDotMarker) {
      map.removeLayer(state.blueDotMarker);
      state.blueDotMarker = null;
    }

    if (!steps || steps.length === 0) return;

    const coordsList = steps.map((s) => getStepLatLng(s));

    state.fullRouteLine = L.polyline(coordsList, {
      color: "#6e5536",
      weight: 2.5,
      opacity: 0.65,
      dashArray: "6 7",
      lineCap: "round",
    }).addTo(map);

    state.traversedRouteLine = L.polyline([coordsList[0]], {
      color: "#184a8c",
      weight: 3.8,
      opacity: 0.92,
      lineCap: "round",
    }).addTo(map);

    steps.forEach((step, idx) => {
      const latLng = coordsList[idx];
      const pinIcon = L.divIcon({
        className: "step-pin-icon",
        html: `<div class="step-pin-badge" data-step="${idx}">${idx + 1}</div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });

      const marker = L.marker(latLng, {
        icon: pinIcon,
        title: `Encuentro ${idx + 1}: ${step.from_person.name} → ${step.to_person.name} (${formatShortPlace(step.location)})`,
        zIndexOffset: 100 + idx,
      }).addTo(map);

      marker.on("click", () => {
        goToStep(idx);
      });

      state.stepMarkers.push(marker);
    });

    const originCoords = coordsList[0];
    state.blueDotCurrentLatLng = originCoords;

    const blueIcon = L.divIcon({
      className: "blue-traveler-icon",
      html: `
        <div class="blue-traveler-beacon">
          <span class="blue-traveler-ring"></span>
          <span class="blue-traveler-core"></span>
        </div>
      `,
      iconSize: [26, 26],
      iconAnchor: [13, 13],
    });

    state.blueDotMarker = L.marker(originCoords, {
      icon: blueIcon,
      zIndexOffset: 1000,
      interactive: false,
    }).addTo(map);
  }

  function updateMapStepState(stepIdx, flyCamera = true) {
    const steps = state.pathData?.steps || [];
    if (!steps.length || !state.map) return;

    const coordsList = steps.map((s) => getStepLatLng(s));
    const targetCoords = coordsList[stepIdx];

    if (state.traversedRouteLine) {
      state.traversedRouteLine.setLatLngs(coordsList.slice(0, stepIdx + 1));
    }

    state.stepMarkers.forEach((marker, idx) => {
      const elNode = marker.getElement();
      if (!elNode) return;
      const badge = elNode.querySelector(".step-pin-badge");
      if (!badge) return;
      badge.classList.toggle("active", idx === stepIdx);
      badge.classList.toggle("visited", idx < stepIdx);
    });

    animateBlueDotTo(targetCoords, 900);

    if (flyCamera) {
      const currentZoom = state.map.getZoom();
      const targetZoom = Math.max(currentZoom, 5);
      state.map.flyTo(targetCoords, targetZoom > 6 ? 5 : targetZoom, {
        animate: true,
        duration: 1.15,
      });
    }
  }

  function fitFullWorldRoute() {
    const steps = state.pathData?.steps || [];
    if (!steps.length || !state.map) return;
    const coordsList = steps.map((s) => getStepLatLng(s));
    const bounds = L.latLngBounds(coordsList);
    state.map.flyToBounds(bounds, {
      padding: [130, 80],
      maxZoom: 6,
      duration: 1.1,
    });
  }

  // --- HUD Updater (Top 2 Involved Cards + Bottom Event Description between Arrows) ---

  function updateHudForStep(stepIdx) {
    const steps = state.pathData?.steps || [];
    const total = steps.length;
    const step = steps[stepIdx];
    if (!step) return;

    // Top Left Card: Involved Person 1
    const pFrom = step.from_person;
    applyPortrait(el.imgStepFrom, el.fallbackStepFrom, pFrom);
    el.nameStepFrom.textContent = pFrom.name;
    el.lifeStepFrom.textContent = [formatLifespan(pFrom), getPersonOccupation(pFrom)]
      .filter(Boolean)
      .join(" · ");
    el.roleStepFrom.textContent = step.roles?.from_role
      ? `Rol: ${step.roles.from_role}`
      : stepIdx === 0
      ? "Punto de partida"
      : `Eslabón ${stepIdx}`;

    // Top Nexus
    el.stepSupertype.textContent =
      SUPERTYPE_LABELS[step.supertype] || step.supertype || "Vínculo documentado";
    el.stepTypeLabel.textContent = step.type_label || step.type_id;

    if (step.context && step.context.name) {
      el.stepContextName.textContent = step.context.name;
      el.stepContextName.hidden = false;
    } else {
      el.stepContextName.textContent = "";
      el.stepContextName.hidden = true;
    }

    // Top Right Card: Involved Person 2
    const pTo = step.to_person;
    applyPortrait(el.imgStepTo, el.fallbackStepTo, pTo);
    el.nameStepTo.textContent = pTo.name;
    el.lifeStepTo.textContent = [formatLifespan(pTo), getPersonOccupation(pTo)]
      .filter(Boolean)
      .join(" · ");
    el.roleStepTo.textContent = step.roles?.to_role
      ? `Rol: ${step.roles.to_role}`
      : stepIdx === total - 1
      ? "Destino final"
      : `Eslabón ${stepIdx + 1}`;

    // Bottom Center Event Description Card
    el.stepBadge.textContent = `Encuentro ${toRoman(stepIdx + 1)} de ${toRoman(total)}`;
    el.stepDate.textContent = formatPeriod(step.period);
    el.stepPlace.textContent = formatPlaceLine(step.location);
    const dms = formatDMS(step.location?.lat, step.location?.lng);
    el.mapCoordsReadout.textContent = dms;
    el.mapCoordsReadout.hidden = !dms;

    el.stepNarrative.textContent =
      step.note ||
      `${pFrom.name} y ${pTo.name} coincidieron documentadamente en ${formatPlaceLine(step.location)} (${formatPeriod(step.period)}).`;

    // Sources: Links in vivid blue so the user can visit them
    if (step.sources && step.sources.length > 0) {
      el.stepSources.innerHTML = step.sources
        .map((src) => {
          const label = src.title || src.publisher || src.url || "Fuente primaria verificada";
          const pub = src.publisher && src.publisher !== label ? ` (${escapeHtml(src.publisher)})` : "";
          if (src.url) {
            return `
              <div class="source-entry">
                <span class="source-tag">Fuente:</span>
                <a class="source-blue-link" href="${escapeHtml(src.url)}" target="_blank" rel="noopener noreferrer" title="Abrir fuente en nueva pestaña">
                  ${escapeHtml(label)}${pub} ↗
                </a>
              </div>
            `;
          }
          return `
            <div class="source-entry">
              <span class="source-tag">Fuente:</span>
              <span>${escapeHtml(label)}${pub}</span>
            </div>
          `;
        })
        .join("");
    } else {
      el.stepSources.innerHTML = `
        <div class="source-entry">
          <span class="source-tag">Fuente:</span>
          <span>Registro prosopográfico verificado</span>
        </div>
      `;
    }

    // Bottom Arrows
    el.navPrev.disabled = stepIdx <= 0;
    if (stepIdx > 0) {
      const prevStep = steps[stepIdx - 1];
      el.prevCaption.textContent = `Paso ${stepIdx} · ${formatShortPlace(prevStep.location)}`;
    } else {
      el.prevCaption.textContent = "Inicio";
    }

    el.navNext.disabled = stepIdx >= total - 1;
    if (stepIdx < total - 1) {
      const nextStep = steps[stepIdx + 1];
      el.nextCaption.textContent = `Paso ${stepIdx + 2} · ${formatShortPlace(nextStep.location)}`;
    } else {
      el.nextCaption.textContent = "Destino final";
    }
  }

  function goToStep(stepIdx, flyCamera = true) {
    const steps = state.pathData?.steps || [];
    if (!steps.length) return;
    const bounded = Math.max(0, Math.min(steps.length - 1, stepIdx));
    state.currentStepIndex = bounded;

    updateHudForStep(bounded);
    updateMapStepState(bounded, flyCamera);
  }

  // --- Mode Switching (Select Overlay vs Full-Tab Map Exploration) ---

  function enterExploreMode() {
    document.body.dataset.mode = "explore";
    el.mapStage.classList.remove("is-blurred");
    el.selectorOverlay.hidden = true;
    el.hudOverlay.hidden = false;
  }

  function enterSelectMode() {
    document.body.dataset.mode = "select";
    el.mapStage.classList.add("is-blurred");
    el.hudOverlay.hidden = true;
    el.selectorOverlay.hidden = false;
  }

  // --- Main Path Search Execution ---

  async function resolvePersonIfTyped(slot) {
    const isFrom = slot === "from";
    const existing = isFrom ? state.selectedFrom : state.selectedTo;
    const rawText = (isFrom ? el.inputFrom.value : el.inputTo.value).trim();

    if (existing && (!rawText || existing.name.toLowerCase() === rawText.toLowerCase())) {
      return existing;
    }
    if (!rawText) return existing || null;

    const matches = await fetchPeopleSearch(rawText, 10);
    if (matches.length > 0) {
      selectPerson(slot, matches[0]);
      return matches[0];
    }
    return existing || null;
  }

  async function executeShortestPathSearch() {
    try {
      el.findPathBtn.disabled = true;
      el.findPathBtn.textContent = "Buscando...";

      const fromPerson = await resolvePersonIfTyped("from");
      const toPerson = await resolvePersonIfTyped("to");

      if (!fromPerson || !toPerson) {
        showStatus("Selecciona dos personajes famosos antes de buscar.", true);
        return;
      }

      if (fromPerson.id === toPerson.id) {
        showStatus("Elige dos personajes distintos para trazar su camino.", true);
        return;
      }

      showStatus(`Trazando ruta entre ${fromPerson.name} y ${toPerson.name}...`);

      const result = await fetchShortestPath(fromPerson.id, toPerson.id);

      if (!result.found || !result.steps || result.steps.length === 0) {
        showStatus(
          `No se encontró una cadena verificada entre ${fromPerson.name} y ${toPerson.name}. Prueba con otros dados o personajes.`,
          true
        );
        return;
      }

      showStatus("");
      state.pathData = result;
      state.currentStepIndex = 0;

      const hops = result.hop_count || result.hops || result.steps.length;
      el.routeTitle.textContent = `${result.from_person.name} → ${result.to_person.name}`;
      el.routeKicker.textContent = `${hops} ${hops === 1 ? "evento" : "eventos"}`;

      enterExploreMode();

      const map = ensureAntiqueMap();
      setTimeout(() => {
        map.invalidateSize();
        renderMapForPath(result.steps);
        goToStep(0, true);
      }, 50);
    } catch (err) {
      console.error(err);
      showStatus(err.message || "Error al consultar la ruta histórica.", true);
    } finally {
      el.findPathBtn.disabled = false;
      el.findPathBtn.textContent = "Buscar conexión";
    }
  }

  // --- Initialization ---

  async function init() {
    ensureAntiqueMap();
    setupCombobox("from");
    setupCombobox("to");

    el.btnDice.addEventListener("click", () => {
      rollRandomPair();
    });

    el.findPathBtn.addEventListener("click", () => {
      executeShortestPathSearch();
    });

    el.btnBackSearch.addEventListener("click", () => {
      enterSelectMode();
    });

    el.btnWorldView.addEventListener("click", () => {
      fitFullWorldRoute();
    });

    el.navPrev.addEventListener("click", () => {
      if (state.currentStepIndex > 0) {
        goToStep(state.currentStepIndex - 1, true);
      }
    });

    el.navNext.addEventListener("click", () => {
      const total = state.pathData?.steps?.length || 0;
      if (state.currentStepIndex < total - 1) {
        goToStep(state.currentStepIndex + 1, true);
      }
    });

    // Mobile touch-swipe support on the bottom event card
    const encounterCard = document.getElementById("encounter-card");
    if (encounterCard) {
      let touchStartX = null;
      let touchStartY = null;
      encounterCard.addEventListener(
        "touchstart",
        (ev) => {
          if (ev.touches.length === 1) {
            touchStartX = ev.touches[0].clientX;
            touchStartY = ev.touches[0].clientY;
          }
        },
        { passive: true }
      );
      encounterCard.addEventListener(
        "touchend",
        (ev) => {
          if (touchStartX == null || !ev.changedTouches.length) return;
          const dx = ev.changedTouches[0].clientX - touchStartX;
          const dy = ev.changedTouches[0].clientY - touchStartY;
          touchStartX = null;
          touchStartY = null;
          if (Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.4) {
            const total = state.pathData?.steps?.length || 0;
            if (dx < 0 && state.currentStepIndex < total - 1) {
              goToStep(state.currentStepIndex + 1, true);
            } else if (dx > 0 && state.currentStepIndex > 0) {
              goToStep(state.currentStepIndex - 1, true);
            }
          }
        },
        { passive: true }
      );
    }

    document.addEventListener("keydown", (ev) => {
      const tag = document.activeElement?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (el.hudOverlay.hidden) return;

      if (ev.key === "ArrowLeft") {
        ev.preventDefault();
        if (state.currentStepIndex > 0) {
          goToStep(state.currentStepIndex - 1, true);
        }
      } else if (ev.key === "ArrowRight") {
        ev.preventDefault();
        const total = state.pathData?.steps?.length || 0;
        if (state.currentStepIndex < total - 1) {
          goToStep(state.currentStepIndex + 1, true);
        }
      } else if (ev.key === "Escape") {
        enterSelectMode();
      }
    });

    // Load initial random pair on startup over the blurred antique map
    await rollRandomPair();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
