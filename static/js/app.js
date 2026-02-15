/* ═══════════════════════════════════════════════════════════════════════
   The Chain — Main Application JS
   ═══════════════════════════════════════════════════════════════════════ */

const API = {
    async post(url, data = {}) {
        const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
        return res.json();
    },
    async get(url) {
        const res = await fetch(url);
        return res.json();
    },
    async del(url) {
        const res = await fetch(url, { method: "DELETE" });
        return res.json();
    },
};

// ─── State ─────────────────────────────────────────────────────────────

let gameState = null;
let gameActive = false;

// ─── DOM refs ──────────────────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const welcomeScreen = $("#welcome-screen");
const gameScreen = $("#game-screen");
const menuOverlay = $("#menu-overlay");
const newgameOverlay = $("#newgame-overlay");
const loadOverlay = $("#load-overlay");
const cardOverlay = $("#card-overlay");
const inputOverlay = $("#input-overlay");

const turnBadge = $("#turn-badge");
const phaseBadge = $("#phase-badge");
const statusMsg = $("#status-msg");
const btnAdvance = $("#btn-advance");
const btnLang = $("#btn-lang");
const btnMode = $("#btn-mode");

// ─── Init ──────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    applyI18n();
    bindEvents();
    // Try loading autosave
    tryAutoLoad();
});

function bindEvents() {
    // Welcome
    $("#btn-welcome-new").onclick = () => showOverlay(newgameOverlay);
    $("#btn-welcome-load").onclick = () => showLoadOverlay();

    // Top bar
    $("#btn-menu").onclick = () => showOverlay(menuOverlay);
    $("#btn-undo").onclick = doUndo;
    $("#btn-save").onclick = () => doSave("manual_save");
    btnLang.onclick = () => {
        const lang = toggleLang();
        btnLang.textContent = lang.toUpperCase();
        if (gameActive) refreshUI();
    };
    btnMode.onclick = toggleMode;

    // Menu
    $("#btn-new-game").onclick = () => { hideOverlay(menuOverlay); showOverlay(newgameOverlay); };
    $("#btn-save-game").onclick = () => { hideOverlay(menuOverlay); promptSave(); };
    $("#btn-load-game").onclick = () => { hideOverlay(menuOverlay); showLoadOverlay(); };
    $("#btn-bank-break").onclick = doBankBreak;
    $("#btn-close-menu").onclick = () => hideOverlay(menuOverlay);

    // New game
    $("#btn-start-game").onclick = startNewGame;
    $("#btn-cancel-setup").onclick = () => hideOverlay(newgameOverlay);

    // Load
    $("#btn-close-load").onclick = () => hideOverlay(loadOverlay);

    // Card zoom
    $$(".card-img").forEach(img => {
        img.onclick = () => {
            if (img.src && !img.src.endsWith("/")) {
                $("#card-zoom-img").src = img.src;
                showOverlay(cardOverlay);
            }
        };
    });
    cardOverlay.onclick = (e) => {
        if (e.target !== $("#card-zoom-img")) hideOverlay(cardOverlay);
    };
    $("#btn-close-card").onclick = () => hideOverlay(cardOverlay);

    // Advance phase
    btnAdvance.onclick = advancePhase;

    // Input submit
    $("#btn-submit-input").onclick = submitInput;

    // Quick mode
    $("#btn-quick-draw").onclick = quickDraw;
    $("#btn-quick-update").onclick = quickUpdateTracks;
}

// ─── Overlays ──────────────────────────────────────────────────────────

function showOverlay(el) { el.classList.remove("hidden"); }
function hideOverlay(el) { el.classList.add("hidden"); }

// ─── New Game ──────────────────────────────────────────────────────────

async function startNewGame() {
    const modules = {
        coffee: $("#mod-coffee").checked,
        kimchi: $("#mod-kimchi").checked,
        noodle: $("#mod-noodle").checked,
        sushi: $("#mod-sushi").checked,
        beer: $("#mod-beer").checked,
        lemonade: $("#mod-lemonade").checked,
        milestones: $("#mod-milestones").checked,
    };
    const optional_rules = {
        hard_choices: $("#opt-hard-choices").checked,
        expand_connections: $("#opt-expand-connections").checked,
        expand_6_restaurants: $("#opt-expand-6").checked,
        aggressive_setup: $("#opt-aggressive-setup").checked,
        aggressive_restructuring: $("#opt-aggressive-restructuring").checked,
    };
    const mode = document.querySelector('input[name="mode"]:checked').value;

    const result = await API.post("/api/game/new", {
        modules, optional_rules, mode, language: currentLang,
    });

    hideOverlay(newgameOverlay);
    gameActive = true;
    welcomeScreen.classList.add("hidden");
    gameScreen.classList.remove("hidden");

    await refreshState();
    setStatus(result.message);

    // Auto-advance to first turn
    advancePhase();
}

// ─── Game Flow ─────────────────────────────────────────────────────────

async function advancePhase() {
    btnAdvance.disabled = true;
    const result = await API.post("/api/game/advance");
    btnAdvance.disabled = false;

    await refreshState();
    setStatus(result.message);

    // Handle waiting for input
    if (result.status === "waiting" && result.input_needed) {
        showInputPrompt(result.input_needed);
    }

    // Update cards from result
    if (result.current_back_card) {
        updateCardImage("back", result.current_back_card);
    }
    if (result.current_front_card) {
        updateCardImage("front", result.current_front_card);
    }

    // Game over
    if (result.status === "game_over") {
        btnAdvance.textContent = "🏁 " + (currentLang === "es" ? "Partida Terminada" : "Game Over");
        btnAdvance.disabled = true;
        btnAdvance.classList.remove("pulse");
    }
}

async function submitInput() {
    const formData = collectInputData();
    if (!formData) return;

    hideOverlay(inputOverlay);
    const result = await API.post("/api/game/input", formData);
    await refreshState();
    setStatus(result.message);

    if (result.status === "waiting" && result.input_needed) {
        showInputPrompt(result.input_needed);
    }
}

function collectInputData() {
    const fields = inputOverlay.querySelectorAll("[data-field-name]");
    const data = {};
    let inputType = inputOverlay.dataset.inputType || "";
    data.type = inputType;

    fields.forEach(field => {
        const name = field.dataset.fieldName;
        if (field.type === "checkbox") {
            // Collect all checked values for multiselect
            if (!data[name]) data[name] = [];
            if (field.checked) data[name].push(field.value);
        } else if (field.type === "number") {
            data[name] = parseInt(field.value) || 0;
        } else {
            data[name] = field.value;
        }
    });

    return data;
}

function showInputPrompt(input) {
    const prompt = currentLang === "es" ? (input.prompt_es || input.prompt) : input.prompt;
    $("#input-prompt").textContent = prompt;

    const container = $("#input-fields");
    container.innerHTML = "";
    inputOverlay.dataset.inputType = input.type;

    (input.fields || []).forEach(f => {
        // Skip fields with failed conditions
        if (f.condition === false) return;

        const div = document.createElement("div");
        div.className = "input-field";

        const label = document.createElement("label");
        label.textContent = currentLang === "es" ? (f.label_es || f.label) : f.label;
        div.appendChild(label);

        if (f.type === "number") {
            const inp = document.createElement("input");
            inp.type = "number";
            inp.min = f.min ?? 0;
            inp.max = f.max ?? 999;
            inp.value = f.default ?? f.min ?? 0;
            inp.dataset.fieldName = f.name;
            div.appendChild(inp);
        } else if (f.type === "select") {
            const sel = document.createElement("select");
            sel.dataset.fieldName = f.name;
            (f.options || []).forEach(opt => {
                const o = document.createElement("option");
                o.value = opt;
                o.textContent = foodLabel(opt);
                sel.appendChild(o);
            });
            div.appendChild(sel);
        } else if (f.type === "multiselect") {
            const group = document.createElement("div");
            group.className = "checkbox-group";
            (f.options || []).forEach(opt => {
                const lbl = document.createElement("label");
                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.value = opt;
                cb.dataset.fieldName = f.name;
                lbl.appendChild(cb);
                lbl.appendChild(document.createTextNode(" " + foodLabel(opt)));
                group.appendChild(lbl);
            });
            div.appendChild(group);
        }

        container.appendChild(div);
    });

    showOverlay(inputOverlay);
}

// ─── State Refresh ─────────────────────────────────────────────────────

async function refreshState() {
    gameState = await API.get("/api/game/state");
    refreshUI();
}

function refreshUI() {
    if (!gameState) return;

    // Top bar
    turnBadge.textContent = `${t("turn")} ${gameState.turn_number}`;
    phaseBadge.textContent = formatPhase(gameState.phase);

    // Mode button
    btnMode.textContent = gameState.mode === "full" ? t("full_mode") : t("quick_mode");

    // Quick controls visibility
    const quickPanel = $("#quick-controls");
    if (gameState.mode === "quick") {
        quickPanel.classList.remove("hidden");
    } else {
        quickPanel.classList.add("hidden");
    }

    // Cards
    if (gameState.current_back_card) updateCardImage("back", gameState.current_back_card);
    if (gameState.current_front_card) updateCardImage("front", gameState.current_front_card);

    // Tracks
    updateTracks();

    // Inventory
    updateInventory();

    // Info panel
    updateMarketeers();
    updateEmployees();
    updateMilestones();
    updateRestaurants();
    updateDeckInfo();

    // Log
    updateLog();

    // Advance button
    if (gameState.phase === "game_over") {
        btnAdvance.textContent = "🏁 " + (currentLang === "es" ? "Partida Terminada" : "Game Over");
        btnAdvance.disabled = true;
        btnAdvance.classList.remove("pulse");
    } else if (gameState.phase === "waiting_for_input") {
        btnAdvance.disabled = true;
        btnAdvance.classList.remove("pulse");
        if (gameState.pending_input) {
            showInputPrompt(gameState.pending_input);
        }
    } else {
        btnAdvance.textContent = t("next_phase");
        btnAdvance.disabled = false;
        btnAdvance.classList.add("pulse");
    }
}

function updateCardImage(side, cardData) {
    const img = side === "back" ? $("#back-card-img") : $("#front-card-img");
    if (cardData) {
        const src = side === "back" ? cardData.image_back : cardData.image_front;
        if (src) img.src = src;
    }
}

function updateTracks() {
    if (!gameState || !gameState.tracks) return;
    const tracks = gameState.tracks;

    // Recruit & Train
    const rtPos = tracks.recruit_train.position;
    $("#rt-value").textContent = rtPos;
    $("#rt-info").textContent = `(${tracks.open_slots} ${t("open_slots")})`;
    renderTrackBar("rt-markers", 1, 7, rtPos, [
        "1", "2", "2", "3", "3", "4", "4"
    ]);

    // Price + Distance
    const pdPos = tracks.price_distance.position;
    $("#pd-value").textContent = `$${pdPos}`;
    renderTrackBar("pd-markers", 6, 10, pdPos, ["6","7","8","9","10"]);

    // Waitresses
    const wPos = tracks.waitresses.position;
    $("#wait-value").textContent = wPos;
    renderTrackBar("wait-markers", 0, 4, wPos, ["0","1","2","3","4"]);

    // Competition
    const compLevel = tracks.competition.level;
    $$(".comp-level").forEach(el => {
        const lvl = parseInt(el.dataset.level);
        el.classList.toggle("active", lvl === compLevel);
        // Update text based on language
        const labels = ["cold", "cool", "neutral", "warm", "hot"];
        el.textContent = t(labels[lvl]);
    });
}

function renderTrackBar(containerId, min, max, current, labels) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";
    for (let i = min; i <= max; i++) {
        const m = document.createElement("div");
        m.className = "marker" + (i === current ? " active" : "");
        m.textContent = labels[i - min] || i;
        container.appendChild(m);
    }
}

function updateInventory() {
    if (!gameState || !gameState.inventory) return;
    const grid = $("#inv-grid");
    grid.innerHTML = "";

    const items = ["burger", "pizza", "sushi", "noodle", "coffee", "kimchi", "beer", "lemonade"];
    const modules = gameState.modules || {};

    items.forEach(item => {
        // Skip items whose module is disabled
        if (modules[item] === false && item !== "burger" && item !== "pizza") return;

        const inv = gameState.inventory[item] || { top: 0, bottom: 0, total: 0 };
        const div = document.createElement("div");
        div.className = "inv-item" + (inv.total === 0 ? " empty" : "");
        div.innerHTML = `
            <div class="inv-icon">${FOOD_ICONS[item] || "📦"}</div>
            <div class="inv-name">${t(item)}</div>
            <div class="inv-count">${inv.total}</div>
            <div class="inv-detail">↑${inv.top} ↓${inv.bottom}</div>
        `;
        grid.appendChild(div);
    });
}

function updateMarketeers() {
    const container = $("#marketeer-slots");
    container.innerHTML = "";
    (gameState.marketeer_slots || []).forEach(slot => {
        const div = document.createElement("div");
        div.className = "slot-item";
        div.innerHTML = `
            <span class="slot-num">${slot.slot}</span>
            <span class="slot-name">${slot.marketeer || t("empty")}</span>
            ${slot.is_busy ? `<span class="slot-busy">${t("busy")}</span>` : ""}
        `;
        container.appendChild(div);
    });
    if (gameState.mass_marketeer) {
        const div = document.createElement("div");
        div.className = "slot-item";
        div.innerHTML = `<span class="slot-num">M</span><span class="slot-name">Mass Marketeer</span>`;
        container.appendChild(div);
    }
}

function updateEmployees() {
    const container = $("#employee-list");
    container.innerHTML = "";
    (gameState.employee_pile || []).forEach(emp => {
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = emp;
        container.appendChild(tag);
    });
    if (container.children.length === 0) {
        container.innerHTML = `<span class="text-muted">${t("empty")}</span>`;
    }
}

function updateMilestones() {
    const container = $("#milestone-list");
    container.innerHTML = "";
    (gameState.milestones_claimed || []).forEach(m => {
        const tag = document.createElement("span");
        tag.className = "tag milestone";
        tag.textContent = m.replace(/_/g, " ");
        container.appendChild(tag);
    });
    if (container.children.length === 0) {
        container.innerHTML = `<span class="text-muted">—</span>`;
    }
}

function updateRestaurants() {
    const container = $("#restaurant-list");
    container.innerHTML = "";
    (gameState.restaurants || []).forEach((r, i) => {
        const tag = document.createElement("span");
        tag.className = "tag restaurant";
        tag.textContent = `#${i + 1} (${t("tile")} ${r.tile})`;
        container.appendChild(tag);
    });
    const max = gameState.max_restaurants || 3;
    const remaining = max - (gameState.restaurants || []).length;
    if (remaining > 0) {
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = `${remaining} ${currentLang === "es" ? "disponibles" : "available"}`;
        container.appendChild(tag);
    }
}

function updateDeckInfo() {
    const container = $("#deck-info");
    if (!gameState) return;
    const ad = gameState.action_deck || {};
    const wd = gameState.warm_deck || {};
    const cd = gameState.cool_deck || {};
    container.innerHTML = `
        📇 Action: ${ad.size || 0} ${t("cards_remaining")}<br>
        🔴 Warm: ${wd.size || 0}<br>
        🟢 Cool: ${cd.size || 0}
    `;
}

function updateLog() {
    const container = $("#action-log");
    container.innerHTML = "";
    const entries = gameState.action_log || [];
    // Show most recent first
    [...entries].reverse().forEach(entry => {
        const div = document.createElement("div");
        div.className = "log-entry";
        div.innerHTML = `
            <span class="log-turn">${entry.turn}</span>
            <span class="log-category">${entry.category}</span>
            <span class="log-msg">${entry.message}</span>
        `;
        container.appendChild(div);
    });
}

// ─── Helpers ───────────────────────────────────────────────────────────

function formatPhase(phase) {
    const phases = {
        setup: "Setup",
        restructuring: currentLang === "es" ? "Reestructurar" : "Restructuring",
        recruit_train: currentLang === "es" ? "Reclutar" : "Recruit & Train",
        get_food: currentLang === "es" ? "Comida" : "Get Food",
        marketing: "Marketing",
        develop: currentLang === "es" ? "Desarrollar" : "Develop",
        lobby: "Lobby",
        expand_chain: currentLang === "es" ? "Expandir" : "Expand Chain",
        dinnertime: currentLang === "es" ? "Cena" : "Dinnertime",
        cleanup: currentLang === "es" ? "Limpieza" : "Cleanup",
        game_over: currentLang === "es" ? "Fin" : "Game Over",
        waiting_for_input: currentLang === "es" ? "Esperando..." : "Waiting...",
    };
    return phases[phase] || phase;
}

function foodLabel(item) {
    return (FOOD_ICONS[item] || "") + " " + t(item);
}

function setStatus(msg) {
    statusMsg.textContent = msg || "";
}

// ─── Actions ───────────────────────────────────────────────────────────

async function doUndo() {
    const result = await API.post("/api/game/undo");
    if (result.status === "ok") {
        await refreshState();
        setStatus(currentLang === "es" ? "Acción deshecha." : "Action undone.");
    } else {
        setStatus(result.message);
    }
}

async function doSave(slotName) {
    const result = await API.post("/api/game/save", { slot_name: slotName });
    setStatus(result.message);
}

function promptSave() {
    const name = prompt(t("save_name"), "save_" + Date.now());
    if (name) doSave(name);
}

async function showLoadOverlay() {
    const saves = await API.get("/api/game/saves");
    const container = $("#saves-list");
    container.innerHTML = "";

    if (saves.length === 0) {
        container.innerHTML = `<p class="text-muted">${currentLang === "es" ? "No hay partidas guardadas." : "No saved games."}</p>`;
    } else {
        saves.forEach(save => {
            const div = document.createElement("div");
            div.className = "save-item";
            div.innerHTML = `
                <div class="save-info" data-slot="${save.slot_name}">
                    <div class="save-name">${save.slot_name}</div>
                    <div class="save-meta">${t("turn")} ${save.turn} — ${save.date}</div>
                </div>
                <button class="save-delete" data-delete="${save.slot_name}">🗑</button>
            `;
            div.querySelector(".save-info").onclick = () => loadGameSlot(save.slot_name);
            div.querySelector(".save-delete").onclick = async (e) => {
                e.stopPropagation();
                await API.del(`/api/game/saves/${save.slot_name}`);
                showLoadOverlay();
            };
            container.appendChild(div);
        });
    }

    showOverlay(loadOverlay);
}

async function loadGameSlot(slotName) {
    const result = await API.post("/api/game/load", { slot_name: slotName });
    hideOverlay(loadOverlay);
    if (result.status === "ok") {
        gameActive = true;
        welcomeScreen.classList.add("hidden");
        gameScreen.classList.remove("hidden");
        await refreshState();
        setStatus(result.message);
    } else {
        setStatus(result.message);
    }
}

async function tryAutoLoad() {
    // Try loading autosave on startup
    const result = await API.post("/api/game/load", { slot_name: "autosave" });
    if (result.status === "ok") {
        gameActive = true;
        welcomeScreen.classList.add("hidden");
        gameScreen.classList.remove("hidden");
        await refreshState();
    }
}

async function doBankBreak() {
    hideOverlay(menuOverlay);
    const result = await API.post("/api/game/input", { type: "bank_break" });
    await refreshState();
    setStatus(result.message);
}

function toggleMode() {
    if (!gameActive) return;
    const newMode = gameState.mode === "full" ? "quick" : "full";
    API.post("/api/game/mode", { mode: newMode }).then(() => refreshState());
}

// ─── Quick Mode ────────────────────────────────────────────────────────

async function quickDraw() {
    const result = await API.post("/api/game/quick/draw");
    if (result.back_card) updateCardImage("back", result.back_card);
    if (result.front_card) updateCardImage("front", result.front_card);
    await refreshState();
}

async function quickUpdateTracks() {
    await API.post("/api/game/quick/track", {
        track: "recruit_train",
        value: parseInt($("#qtrack-rt").value) || 1,
    });
    await API.post("/api/game/quick/track", {
        track: "price_distance",
        value: parseInt($("#qtrack-pd").value) || 10,
    });
    await API.post("/api/game/quick/track", {
        track: "waitresses",
        value: parseInt($("#qtrack-wait").value) || 0,
    });
    await API.post("/api/game/quick/track", {
        track: "competition",
        value: parseInt($("#qtrack-comp").value) || 2,
    });
    await refreshState();
    setStatus(currentLang === "es" ? "Pistas actualizadas." : "Tracks updated.");
}
