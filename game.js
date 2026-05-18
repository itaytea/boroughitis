// Boroughitis — daily NJ municipality guessing game
// State lives in localStorage keyed by date so a refresh restores the puzzle.

const MAX_GUESSES = 6;
const STORAGE_KEY = "boroughitis.v1";
const EPOCH = Date.UTC(2025, 0, 1); // puzzle #1 = Jan 1 2025 UTC

// ---------------------------------------------------------------- data load

let MUNIS = [];                  // array of muni records
let MUNI_BY_ID = new Map();      // id -> record
let MUNI_BY_DISPLAY = new Map(); // display string -> record
let COUNTY_ADJ = {};             // county name -> [adjacent county names]
let SCHEDULE = null;             // { start_date, munis: [id...] } or null

async function loadData() {
  const [m, c, s] = await Promise.all([
    fetch("data/municipalities.json").then(r => r.json()),
    fetch("data/counties.json").then(r => r.json()),
    fetch("data/schedule.json").then(r => r.ok ? r.json() : null).catch(() => null),
  ]);
  MUNIS = m;
  COUNTY_ADJ = c;
  SCHEDULE = s;

  // Build lookup tables. Display = "Name, County" unless that collides; then
  // fall back to "Name (Type), County".
  const nameCountyCounts = new Map();
  for (const muni of MUNIS) {
    const key = `${muni.name}|${muni.county}`;
    nameCountyCounts.set(key, (nameCountyCounts.get(key) || 0) + 1);
  }

  for (const muni of MUNIS) {
    MUNI_BY_ID.set(muni.id, muni);
    const ambiguous = nameCountyCounts.get(`${muni.name}|${muni.county}`) > 1;
    const display = ambiguous
      ? `${muni.name} (${muni.type}), ${muni.county}`
      : `${muni.name}, ${muni.county}`;
    muni.display = display;
    MUNI_BY_DISPLAY.set(display.toLowerCase(), muni);
  }
}

// ------------------------------------------------------ daily puzzle picker

function todayDay() {
  // Days since EPOCH using UTC, so the puzzle flips at 00:00 UTC for everyone.
  const now = new Date();
  const utc = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  return Math.floor((utc - EPOCH) / 86400000);
}

function hashDay(day) {
  // Murmur-ish scramble so adjacent puzzles aren't alphabetically adjacent.
  let h = (day + 0x9e3779b9) | 0;
  h = Math.imul(h ^ (h >>> 16), 0x85ebca6b);
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
  h = h ^ (h >>> 16);
  return h >>> 0;
}

function todaysMuni() {
  // If a schedule.json is present and we're inside its date range, use it.
  // After the schedule runs out, fall back to the hash-shuffled order while
  // keeping the day count continuous from the schedule's start_date.
  if (SCHEDULE && SCHEDULE.start_date) {
    const [yy, mm, dd] = SCHEDULE.start_date.split("-").map(Number);
    const startUTC = Date.UTC(yy, mm - 1, dd);
    const now = new Date();
    const todayUTC = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
    const day = Math.floor((todayUTC - startUTC) / 86400000);
    if (day >= 0) {
      if (day < SCHEDULE.munis.length) {
        const m = MUNI_BY_ID.get(SCHEDULE.munis[day]);
        if (m) return { muni: m, day };
        console.warn("schedule muni id not found, falling back:", SCHEDULE.munis[day]);
      }
      return { muni: MUNIS[hashDay(day) % MUNIS.length], day };
    }
    // before start_date -- fall through to legacy EPOCH-based numbering
  }
  const day = todayDay();
  return { muni: MUNIS[hashDay(day) % MUNIS.length], day };
}

// ---------------------------------------------------------- state / storage

function loadState() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch { return {}; }
}
function saveState(s) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}

function getOrCreateToday(day) {
  const s = loadState();
  if (s.currentDay !== day) {
    s.currentDay = day;
    s.guesses = []; // array of muni ids
    s.done = false;
    s.won = false;
    saveState(s);
  }
  return s;
}

function recordResult(state, won) {
  // Update lifetime stats. Distribution[i-1] = wins on guess i.
  const stats = state.stats || {
    played: 0, wins: 0, streak: 0, maxStreak: 0,
    dist: [0, 0, 0, 0, 0, 0],
    lastWonDay: null,
  };
  stats.played++;
  if (won) {
    stats.wins++;
    stats.dist[state.guesses.length - 1]++;
    if (stats.lastWonDay === state.currentDay - 1 || stats.lastWonDay === null) {
      stats.streak = Math.max(1, stats.streak + 1);
    } else {
      stats.streak = 1;
    }
    stats.lastWonDay = state.currentDay;
    if (stats.streak > stats.maxStreak) stats.maxStreak = stats.streak;
  } else {
    stats.streak = 0;
  }
  state.stats = stats;
  saveState(state);
  return stats;
}

// -------------------------------------------------------- compare functions

function compare(guess, answer) {
  return {
    name: nameCmp(guess, answer),
    type: typeCmp(guess, answer),
    county: countyCmp(guess, answer),
    pop: popCmp(guess, answer),
    direction: dirCmp(guess, answer),
  };
}

function nameCmp(g, a) {
  if (g.id === a.id) return { color: "green", text: g.name };
  if (a.borders.includes(g.id)) return { color: "yellow", text: g.name };
  return { color: "gray", text: g.name };
}

function typeCmp(g, a) {
  if (g.type === a.type) return { color: "green", text: g.type };
  return { color: "gray", text: g.type };
}

function countyCmp(g, a) {
  if (g.county === a.county) return { color: "green", text: g.county };
  const adj = COUNTY_ADJ[a.county] || [];
  if (adj.includes(g.county)) return { color: "yellow", text: g.county };
  return { color: "gray", text: g.county };
}

function popCmp(g, a) {
  const arrow = a.population > g.population ? "↑"
              : a.population < g.population ? "↓"
              : "✓";
  return {
    color: arrow === "✓" ? "green" : "gray",
    text: `${formatPop(g.population)} ${arrow}`,
    arrow,
  };
}

function formatPop(n) {
  if (n >= 100000) return (n / 1000).toFixed(0) + "k";
  if (n >= 10000) return (n / 1000).toFixed(0) + "k";
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return String(n);
}

function bearing(from, to) {
  const [lat1, lon1] = from.map(d => d * Math.PI / 180);
  const [lat2, lon2] = to.map(d => d * Math.PI / 180);
  const dLon = lon2 - lon1;
  const y = Math.sin(dLon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) -
            Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
  return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

function dirCmp(g, a) {
  if (g.id === a.id) return { color: "green", arrow: "✓", deg: 0 };
  const b = bearing(g.centroid, a.centroid);
  return { color: "gray", arrow: "↑", deg: b };
}

// ------------------------------------------------------------------ render

function renderGrid(state, answer) {
  const grid = document.getElementById("guess-grid");
  grid.innerHTML = "";
  for (let i = 0; i < MAX_GUESSES; i++) {
    const guessId = state.guesses[i];
    if (guessId) {
      const guess = MUNI_BY_ID.get(guessId);
      grid.appendChild(renderRow(compare(guess, answer)));
    } else {
      grid.appendChild(renderEmptyRow());
    }
  }
}

function renderRow(cmp) {
  const row = document.createElement("div");
  row.className = "row";

  row.appendChild(cell("name " + cmp.name.color, cmp.name.text));
  row.appendChild(cell(cmp.type.color, cmp.type.text));
  row.appendChild(cell(cmp.county.color, cmp.county.text));
  row.appendChild(cell(cmp.pop.color, cmp.pop.text));

  const dirCell = document.createElement("div");
  dirCell.className = "cell " + cmp.direction.color;
  if (cmp.direction.arrow === "✓") {
    dirCell.textContent = "✓";
  } else {
    const a = document.createElement("span");
    a.className = "dir-arrow";
    a.textContent = "↑";
    a.style.transform = `rotate(${cmp.direction.deg}deg)`;
    dirCell.appendChild(a);
  }
  row.appendChild(dirCell);

  return row;
}

function cell(cls, text) {
  const c = document.createElement("div");
  c.className = "cell " + cls;
  c.textContent = text;
  return c;
}

function renderEmptyRow() {
  const row = document.createElement("div");
  row.className = "row empty";
  for (let i = 0; i < 5; i++) {
    const c = document.createElement("div");
    c.className = "cell";
    c.textContent = "·";
    row.appendChild(c);
  }
  return row;
}

async function renderOutline(muni) {
  const box = document.getElementById("outline-box");
  box.innerHTML = '<span class="outline-placeholder">…</span>';
  try {
    const svg = await fetch(`data/outlines/${muni.id}.svg`).then(r => r.text());
    box.innerHTML = svg;
  } catch (e) {
    box.innerHTML = '<span class="outline-placeholder">outline missing</span>';
  }
}

function renderDatalist() {
  const dl = document.getElementById("muni-options");
  dl.innerHTML = "";
  const sorted = [...MUNIS].sort((a, b) => a.display.localeCompare(b.display));
  for (const m of sorted) {
    const opt = document.createElement("option");
    opt.value = m.display;
    dl.appendChild(opt);
  }
}

function setNote(text) {
  document.getElementById("note").textContent = text || "";
}

function showEndState(state, answer) {
  const end = document.getElementById("end-state");
  const msg = document.getElementById("end-message");
  end.classList.remove("hidden");
  if (state.won) {
    msg.textContent = `Got it in ${state.guesses.length}! It was ${answer.name}, ${answer.county}.`;
  } else {
    msg.textContent = `The answer was ${answer.name}, ${answer.county}.`;
  }
  document.getElementById("guess-input").disabled = true;
  document.getElementById("guess-btn").disabled = true;
}

// ---------------------------------------------------------- submit handling

function setupForm(state, answer) {
  const form = document.getElementById("guess-form");
  const input = document.getElementById("guess-input");

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (state.done) return;
    const raw = input.value.trim();
    const muni = MUNI_BY_DISPLAY.get(raw.toLowerCase());
    if (!muni) {
      setNote(`Not a NJ municipality I know. Try "Newark, Essex".`);
      return;
    }
    if (state.guesses.includes(muni.id)) {
      setNote("Already guessed that one.");
      return;
    }
    state.guesses.push(muni.id);
    input.value = "";
    setNote("");

    const won = muni.id === answer.id;
    if (won || state.guesses.length >= MAX_GUESSES) {
      state.done = true;
      state.won = won;
      recordResult(state, won);
    } else {
      saveState(state);
    }
    renderGrid(state, answer);
    if (state.done) showEndState(state, answer);
  });
}

// --------------------------------------------------------- share grid + UI

function shareGrid(state, answer, puzzleNum) {
  const lines = [`Boroughitis #${puzzleNum} ${state.won ? state.guesses.length : "X"}/${MAX_GUESSES}`];
  for (const id of state.guesses) {
    const g = MUNI_BY_ID.get(id);
    const c = compare(g, answer);
    const row = [
      colorEmoji(c.name.color),
      colorEmoji(c.type.color),
      colorEmoji(c.county.color),
      c.pop.arrow,
      g.id === answer.id ? "✅" : dirEmoji(c.direction.deg),
    ].join("");
    lines.push(row);
  }
  return lines.join("\n");
}

function colorEmoji(c) {
  return c === "green" ? "🟩" : c === "yellow" ? "🟨" : "⬜";
}

function dirEmoji(deg) {
  // Round to nearest of 8 cardinal directions.
  const dirs = ["⬆️","↗️","➡️","↘️","⬇️","↙️","⬅️","↖️"];
  const i = Math.round(deg / 45) % 8;
  return dirs[i];
}

function setupShare(state, answer, puzzleNum) {
  document.getElementById("share-btn").addEventListener("click", async () => {
    const text = shareGrid(state, answer, puzzleNum);
    try {
      await navigator.clipboard.writeText(text);
      setNote("Copied to clipboard!");
    } catch {
      setNote(text);
    }
  });
}

// --------------------------------------------------------- stats + how-to

function openDialog(id) { document.getElementById(id).showModal(); }

function setupDialogs(state) {
  document.getElementById("howto-btn").addEventListener("click", () => openDialog("howto-dialog"));
  document.getElementById("stats-btn").addEventListener("click", () => {
    renderStats(state);
    openDialog("stats-dialog");
  });
}

function renderStats(state) {
  const s = state.stats || { played: 0, wins: 0, streak: 0, maxStreak: 0, dist: [0,0,0,0,0,0] };
  document.getElementById("stat-played").textContent = s.played;
  document.getElementById("stat-winpct").textContent = s.played ? Math.round(100 * s.wins / s.played) + "%" : "0%";
  document.getElementById("stat-streak").textContent = s.streak;
  document.getElementById("stat-max").textContent = s.maxStreak;
  const dist = document.getElementById("stat-dist");
  dist.innerHTML = "";
  const max = Math.max(1, ...s.dist);
  s.dist.forEach((count, i) => {
    const row = document.createElement("div");
    row.className = "bar";
    row.innerHTML = `<span class="label">${i + 1}</span><div class="fill" style="width:${(count / max) * 100}%">${count}</div>`;
    dist.appendChild(row);
  });
}

// ------------------------------------------------------------------- init

(async function init() {
  try {
    await loadData();
  } catch (e) {
    setNote("Data not loaded. Run scripts/build_data.py first.");
    console.error(e);
    return;
  }
  if (MUNIS.length === 0) {
    setNote("No municipalities found in data/municipalities.json.");
    return;
  }

  const { muni: answer, day } = todaysMuni();
  const state = getOrCreateToday(day);

  // Header meta
  document.getElementById("puzzle-num").textContent = `#${String(day + 1).padStart(3, "0")}`;
  document.getElementById("puzzle-date").textContent = new Date().toLocaleDateString(
    undefined, { month: "short", day: "numeric", year: "numeric" }
  );

  renderDatalist();
  renderOutline(answer);
  renderGrid(state, answer);
  setupForm(state, answer);
  setupShare(state, answer, day + 1);
  setupDialogs(state);

  if (state.done) showEndState(state, answer);

  // First-time visit: pop the how-to dialog.
  if (!state.stats || state.stats.played === 0) {
    if (state.guesses.length === 0) openDialog("howto-dialog");
  }
})();
