"use strict";

/* ===================== COSTANTI ===================== */
const MAX_TURNS_DEFAULT = 8;
const TURN_TIMES = [600, 600, 300, 300, 300, 300, 300, 300];

const SETTINGS_FIELDS = [
  ["initial_capital", "Capitale iniziale", "Es. 50000", true],
  ["initial_raw_material_inventory", "Magazzino materie prime iniziale", "Es. 100", true],
  ["initial_capacity", "Capacità iniziale", "Es. 100", true],
  ["initial_personnel", "Personale iniziale", "Es. 5", true],
  ["market_initial_a", "Mercato iniziale A", "Valore iniziale A", false],
  ["market_initial_b", "Mercato iniziale B", "Valore iniziale B", false],
  ["market_final_a", "Mercato finale A", "Valore finale A", false],
  ["market_final_b", "Mercato finale B", "Valore finale B", false],
  ["pct_a_0", "Percentuale variabile mercato 1 A", "Es. 30", true],
  ["pct_a_1", "Percentuale variabile mercato 2 A", "Es. 30", true],
  ["pct_a_2", "Percentuale variabile mercato 3 A", "Es. 40", true],
  ["pct_b_0", "Percentuale variabile mercato 1 B", "Es. 30", true],
  ["pct_b_1", "Percentuale variabile mercato 2 B", "Es. 30", true],
  ["pct_b_2", "Percentuale variabile mercato 3 B", "Es. 40", true],
  ["interests", "Interessi", "Es. 5", true],
  ["purchase_cost", "Costo acquisto materie prime", "€/unità", true],
  ["production_time_a", "Produzione oraria Prodotto A", "Es. 4", true],
  ["production_time_b", "Produzione oraria Prodotto B", "Es. 5", true],
  ["investment_visibility_ratio_a", "Rapporto investimento/visibilità A", "Es. 2", true],
  ["investment_visibility_ratio_b", "Rapporto investimento/visibilità B", "Es. 2", true],
  ["innovation_internal_research_ratio_a", "Rapporto innovazione interna/ricerca A", "Es. 4", true],
  ["innovation_coproj_research_ratio_a", "Rapporto innovazione coprogg/ricerca A", "Es. 4", true],
  ["innovation_internal_research_ratio_b", "Rapporto innovazione interna/ricerca B", "Es. 4", true],
  ["innovation_coproj_research_ratio_b", "Rapporto innovazione coprogg/ricerca B", "Es. 4", true],
  ["investment_capacity_ratio", "Rapporto investimento/capacità", "Es. 3", true],
];

/* ===================== STATO ===================== */
const STATE = {
  adminPassword: "",
  roomCode: "",
  companyName: "",
  company: {}, products: {}, costs: {}, sales: { A: 0, B: 0 }, history: {},
  currentTurn: 1, maxTurns: MAX_TURNS_DEFAULT,
  gameFinished: false, turnConfirmed: false,
  view: "join", tab: "home",
  timerLeft: 0, timerTurn: null, timerId: null, pollId: null, autosaveId: null,
};

function saveSession() {
  try {
    sessionStorage.setItem("bg_session", JSON.stringify({
      adminPassword: STATE.adminPassword, roomCode: STATE.roomCode,
      companyName: STATE.companyName, view: STATE.view,
    }));
  } catch (e) {}
}
function loadSession() {
  try { return JSON.parse(sessionStorage.getItem("bg_session") || "null"); } catch (e) { return null; }
}

/* ===================== API ===================== */
async function api(method, endpoint, payload) {
  try {
    const res = await fetch(endpoint, {
      method,
      headers: { "Content-Type": "application/json" },
      body: method === "POST" ? JSON.stringify(payload || {}) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch (e) {}
    return [res.status, data];
  } catch (e) {
    return [500, { success: false, message: "Server non raggiungibile." }];
  }
}
const apiPost = (e, p) => api("POST", e, p);
const apiGet = (e) => api("GET", e);

/* ===================== UTILITÀ DOM ===================== */
const $app = document.getElementById("app");
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}
function setMsg(el, text, kind) { el.textContent = text || ""; el.className = "msg" + (kind ? " " + kind : ""); }
function kv(k, v) { return h("div", { class: "kv" }, h("span", {}, k), h("span", {}, v)); }
function fmt(v) {
  if (v === undefined || v === null || v === "") return "0";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100);
  return String(v);
}
function stopTimers() {
  [ "timerId", "pollId", "autosaveId" ].forEach((k) => { if (STATE[k]) { clearInterval(STATE[k]); STATE[k] = null; } });
}
function go(view) { stopTimers(); STATE.view = view; saveSession(); render(); }

function render() {
  $app.innerHTML = "";
  if (STATE.view === "admin_login") $app.append(viewAdminLogin());
  else if (STATE.view === "admin_control") $app.append(viewAdminControl());
  else if (STATE.view === "game") $app.append(viewGame());
  else $app.append(viewJoin());
}

/* ===================== INGRESSO IN STANZA ===================== */
function viewJoin() {
  const company = h("input", { placeholder: "Nome azienda", autocomplete: "off" });
  const room = h("input", { placeholder: "Codice stanza", autocomplete: "off", autocapitalize: "characters" });
  const msg = h("div", { class: "msg" });
  const btn = h("button", { onclick: async () => {
    const companyName = company.value.trim(), roomCode = room.value.trim().toUpperCase();
    if (!companyName || !roomCode) return setMsg(msg, "Inserisci nome azienda e codice stanza.", "err");
    btn.disabled = true; setMsg(msg, "");
    const [st, data] = await apiPost("/join_room", { company_name: companyName, room_code: roomCode });
    btn.disabled = false;
    if (st !== 200 || !data.success) return setMsg(msg, data.message || "Errore durante l'ingresso nella stanza.", "err");
    STATE.companyName = companyName; STATE.roomCode = roomCode;
    applyPlayer(data.player || {});
    await loadRoomMeta();
    STATE.tab = "home"; go("game");
  } }, "Entra nella stanza");
  return h("div", { class: "center" },
    h("div", { class: "card" },
      h("h1", {}, "Business Game"),
      h("h2", {}, "Entra nella stanza"),
      h("div", { class: "stack" }, company, room, btn,
        h("button", { class: "ghost", onclick: () => go("admin_login") }, "Pagina admin"), msg)));
}

function applyPlayer(p) {
  STATE.company = p.company || {};
  STATE.products = p.products || {};
  STATE.costs = p.costs || {};
  STATE.sales = p.sales || { A: 0, B: 0 };
  STATE.history = p.history || {};
  STATE.currentTurn = parseInt(p.current_turn || 1, 10);
  STATE.gameFinished = !!p.game_finished;
  STATE.turnConfirmed = !!p.choices_confirmed;
}
async function loadRoomMeta() {
  const [st, d] = await apiGet(`/room/${STATE.roomCode}`);
  if (st === 200 && d.success) {
    STATE.maxTurns = parseInt(d.room.max_turns || MAX_TURNS_DEFAULT, 10);
    return d.room;
  }
  return null;
}

/* ===================== ADMIN: LOGIN ===================== */
function viewAdminLogin() {
  const pw = h("input", { type: "password", placeholder: "Password admin" });
  const msg = h("div", { class: "msg" });
  const create = async () => {
    const password = pw.value.trim();
    if (!password) return setMsg(msg, "Inserisci la password admin.", "err");
    const [st, d] = await apiPost("/create_room", { password });
    if (st === 200 && d.success) { STATE.adminPassword = password; STATE.roomCode = d.room_code; go("admin_control"); }
    else setMsg(msg, d.message || "Errore durante la creazione stanza.", "err");
  };
  pw.addEventListener("keydown", (e) => { if (e.key === "Enter") create(); });
  return h("div", { class: "center" },
    h("div", { class: "card" },
      h("h1", {}, "Pagina admin"),
      h("p", {}, "Inserisci la password admin per creare una stanza."),
      h("div", { class: "stack" }, pw,
        h("button", { onclick: create }, "Crea stanza"),
        h("button", { class: "ghost", onclick: () => go("join") }, "Vai a «Entra in stanza»"), msg)));
}

/* ===================== ADMIN: PARAMETRI STANZA ===================== */
function viewAdminControl() {
  const inputs = {};
  const msg = h("div", { class: "msg" });
  const roomTitle = h("div", { class: "code" }, STATE.roomCode || "-");
  const roomState = h("span", { class: "badge" }, "…");
  const playersBox = h("div", {});

  const settingsGrid = h("div", { class: "settings" });
  for (const [key, label, hint, numeric] of SETTINGS_FIELDS) {
    const inp = h("input", { placeholder: hint, inputmode: numeric ? "decimal" : "text" });
    inputs[key] = inp;
    settingsGrid.append(h("div", {}, h("label", {}, label), inp));
  }

  const val = (k, dflt) => (inputs[k].value.trim() || dflt);

  async function load() {
    const [st, d] = await apiGet(`/room/${STATE.roomCode}`);
    if (st !== 200 || !d.success) return;
    const s = d.room.settings || {};
    const t = (v) => (v === null || v === undefined ? "" : String(v));
    for (const [key] of SETTINGS_FIELDS) {
      let v;
      const m = key.match(/^pct_([ab])_(\d)$/);
      if (m) v = (s[`market_variable_percentages_${m[1]}`] || [])[parseInt(m[2], 10)] ?? 0;
      else v = s[key];
      inputs[key].value = t(v);
    }
  }

  async function save(autosave) {
    if (!STATE.roomCode) return setMsg(msg, "Nessuna stanza selezionata.", "err");
    if (!inputs.initial_capital.value.trim()) { if (!autosave) setMsg(msg, "Inserisci il capitale iniziale.", "err"); return; }
    const mia = val("market_initial_a", ""), mib = val("market_initial_b", ""), mfa = val("market_final_a", ""), mfb = val("market_final_b", "");
    if (!mia || !mib || !mfa || !mfb) return setMsg(msg, "Inserisci mercato iniziale e finale per A e B.", "err");
    const pa = [0, 1, 2].map((i) => val(`pct_a_${i}`, "0"));
    const pb = [0, 1, 2].map((i) => val(`pct_b_${i}`, "0"));
    const sum = (arr) => arr.reduce((a, x) => a + parseFloat(x), 0);
    if ([...pa, ...pb].some((x) => isNaN(parseFloat(x)))) return setMsg(msg, "Le percentuali devono essere numeriche.", "err");
    if (sum(pa) !== 100) return setMsg(msg, `La somma percentuali A deve essere 100. Somma attuale: ${sum(pa)}.`, "err");
    if (sum(pb) !== 100) return setMsg(msg, `La somma percentuali B deve essere 100. Somma attuale: ${sum(pb)}.`, "err");
    const payload = { room_code: STATE.roomCode, password: STATE.adminPassword,
      market_initial_a: mia, market_initial_b: mib, market_final_a: mfa, market_final_b: mfb,
      market_variable_percentages_a: pa, market_variable_percentages_b: pb };
    for (const [key] of SETTINGS_FIELDS) {
      if (key.startsWith("pct_") || key in payload) continue;
      payload[key] = key === "initial_capital" ? inputs[key].value.trim() : val(key, "0");
    }
    const [st, d] = await apiPost("/update_room_settings", payload);
    if (st === 200 && d.success) setMsg(msg, autosave ? "Autosave effettuato ✔" : "Parametri salvati correttamente.", "ok");
    else setMsg(msg, d.message || "Errore nel salvataggio dei parametri.", "err");
  }

  async function refreshPlayers() {
    const [st, d] = await apiGet(`/room/${STATE.roomCode}`);
    playersBox.innerHTML = "";
    if (st !== 200 || !d.success) { playersBox.append(h("p", {}, "Errore nel recupero dei giocatori.")); return; }
    const room = d.room;
    roomState.textContent = room.settings_ready ? "PRONTA" : "NON PRONTA";
    roomState.className = "badge" + (room.settings_ready ? " ok" : "");
    const players = room.players || [];
    if (!players.length) { playersBox.append(h("p", {}, "Nessun giocatore ancora entrato.")); return; }
    const tbl = h("table", {}, h("tr", {}, h("th", {}, "#"), h("th", {}, "Azienda"), h("th", {}, "Capitale"), h("th", {}, "Personale"), h("th", {}, "Turno")));
    players.forEach((p, i) => tbl.append(h("tr", {},
      h("td", {}, i + 1), h("td", {}, p.company_name),
      h("td", {}, fmt((p.company || {}).capital)), h("td", {}, fmt((p.company || {}).personnel)),
      h("td", {}, `${p.current_turn || 1}/${room.max_turns || MAX_TURNS_DEFAULT}`))));
    playersBox.append(h("div", { style: "overflow-x:auto" }, tbl));
  }

  load(); refreshPlayers();
  STATE.pollId = setInterval(refreshPlayers, 2000);
  STATE.autosaveId = setInterval(() => save(true), 60000);

  return h("div", {},
    h("div", { class: "card" }, h("div", { class: "row" },
      h("div", {}, h("label", {}, "Codice stanza (da dare ai giocatori)"), roomTitle), h("div", {}, roomState))),
    h("div", { class: "card" }, h("h2", {}, "Parametri stanza"), settingsGrid,
      h("div", { class: "stack" }, h("button", { onclick: () => save(false) }, "Salva parametri stanza"), msg)),
    h("div", { class: "card" }, h("h2", {}, "Giocatori nella stanza"), playersBox),
    h("div", { class: "row" },
      h("button", { class: "ghost", onclick: () => go("join") }, "Vai a «Entra in stanza»"),
      h("button", { class: "ghost", onclick: () => go("admin_login") }, "Torna al login admin")));
}

/* ===================== GIOCO ===================== */
const TABS = [["home", "Home"], ["market", "Mercato"], ["levers", "Leve"], ["guide", "Guida"], ["report", "Report"]];

function turnSeconds() {
  const i = STATE.currentTurn - 1;
  return i >= 0 && i < TURN_TIMES.length ? TURN_TIMES[i] : TURN_TIMES[TURN_TIMES.length - 1];
}

function viewGame() {
  const timerEl = h("div", { class: "timer" }, "Tempo turno: --:--");
  const content = h("div", {});
  const tabsEl = h("div", { class: "tabs" });

  function drawTabs() {
    tabsEl.innerHTML = "";
    TABS.forEach(([id, label]) => tabsEl.append(h("button", { class: STATE.tab === id ? "on" : "", onclick: () => { STATE.tab = id; drawTabs(); drawContent(); } }, label)));
    tabsEl.append(timerEl);
  }
  function drawContent() {
    content.innerHTML = "";
    if (STATE.tab === "home") content.append(tabHome());
    else content.append(h("div", { class: "card" }, h("h2", {}, TABS.find((t) => t[0] === STATE.tab)[1]), h("p", {}, "Sezione in arrivo nella versione web.")));
  }
  function drawTimer() {
    if (STATE.gameFinished) timerEl.textContent = "Partita terminata";
    else if (STATE.currentTurn > STATE.maxTurns) timerEl.textContent = "Turni completati";
    else if (STATE.turnConfirmed) timerEl.textContent = "Scelte confermate";
    else {
      const m = Math.floor(STATE.timerLeft / 60), s = Math.floor(STATE.timerLeft % 60);
      timerEl.textContent = `Tempo turno: ${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }
  }
  STATE.timerLeft = turnSeconds(); STATE.timerTurn = STATE.currentTurn;
  STATE.timerId = setInterval(() => {
    if (STATE.gameFinished || STATE.currentTurn > STATE.maxTurns) return drawTimer();
    if (STATE.timerTurn !== STATE.currentTurn) { STATE.turnConfirmed = false; STATE.timerLeft = turnSeconds(); STATE.timerTurn = STATE.currentTurn; return drawTimer(); }
    if (STATE.turnConfirmed) return drawTimer();
    STATE.timerLeft -= 1; drawTimer();
    if (STATE.timerLeft <= 0) { STATE.turnConfirmed = true; timerEl.textContent = "Tempo scaduto"; /* invio automatico: nella sezione Leve */ }
  }, 1000);

  drawTabs(); drawContent(); drawTimer();
  return h("div", {}, h("div", { class: "card" }, h("strong", {}, STATE.companyName), ` · stanza ${STATE.roomCode}`), tabsEl, content);
}

function tabHome() {
  const c = STATE.company || {}, pr = STATE.products || {}, sales = STATE.sales || {};
  const prodCard = (key) => {
    const p = pr[key] || {};
    return h("div", { class: "card" }, h("h2", {}, `Prodotto ${key}`),
      kv("Prezzo", fmt(p.price)), kv("Visibilità", fmt(p.visibility)), kv("Ricerca", fmt(p.research)),
      kv("Quantità", fmt(p.quantity)), kv("Produzione oraria", fmt(p.production_per_hour)), kv("Venduto", fmt(sales[key])));
  };
  const ranking = h("div", {}, "Caricamento…");
  apiGet(`/room/${STATE.roomCode}`).then(([st, d]) => {
    ranking.innerHTML = "";
    if (st !== 200 || !d.success) return ranking.append("Impossibile caricare la classifica.");
    const r = d.room.current_ranking || [];
    if (!r.length) return ranking.append("Classifica non ancora disponibile.");
    const tbl = h("table", {}, h("tr", {}, h("th", {}, "#"), h("th", {}, "Azienda"), h("th", {}, "Punteggio"), h("th", {}, "Quota"), h("th", {}, "ROE")));
    r.forEach((i) => tbl.append(h("tr", {}, h("td", {}, fmt(i.posizione)), h("td", {}, i.azienda || "Azienda"), h("td", {}, fmt(i.punteggio)), h("td", {}, fmt(i.quota_mercato)), h("td", {}, fmt(i.roe)))));
    ranking.append(h("div", { style: "overflow-x:auto" }, tbl));
  });
  return h("div", {},
    h("div", { class: "card" }, h("h2", {}, "Azienda"),
      kv("Azienda", STATE.companyName || "N/D"), kv("Stanza", STATE.roomCode || "N/D"),
      kv("Turno", `${STATE.currentTurn}/${STATE.maxTurns + 1}`),
      kv("Capitale", fmt(c.capital)), kv("Magazzino materie prime", fmt(c.raw_material_inventory)),
      kv("Capacità", fmt(c.capacity)), kv("Personale", fmt(c.personnel)), kv("Investimenti", fmt(c.fixed_investments))),
    h("div", { class: "grid2" }, prodCard("A"), prodCard("B")),
    h("div", { class: "card" }, h("h2", {}, "Classifica"), ranking));
}

/* ===================== AVVIO ===================== */
(function init() {
  const s = loadSession();
  if (s && s.view === "admin_control" && s.roomCode && s.adminPassword) {
    STATE.adminPassword = s.adminPassword; STATE.roomCode = s.roomCode; STATE.view = "admin_control";
  } else if (s && s.view === "game" && s.roomCode && s.companyName) {
    STATE.roomCode = s.roomCode; STATE.companyName = s.companyName;
    apiGet(`/room/${s.roomCode}`).then(([st, d]) => {
      const p = st === 200 && d.success ? (d.room.players || []).find((x) => x.company_name === s.companyName) : null;
      if (p) { STATE.maxTurns = parseInt(d.room.max_turns || MAX_TURNS_DEFAULT, 10); applyPlayer(p); STATE.view = "game"; } else STATE.view = "join";
      render();
    });
    return;
  }
  render();
})();
