/* ═══════════════════════════════════════════════════════════════════════
   The Chain — Main Application JS
   ═══════════════════════════════════════════════════════════════════════ */

// ─── Session ID ────────────────────────────────────────────────────────
// Generate a stable session id on the client side and send it with every
// request via the X-Session-ID header.  This avoids reliance on cookies,
// which are blocked when the app runs inside a cross-site iframe
// (e.g. Hugging Face Spaces embedded on huggingface.co).
function _getSessionId() {
    let sid = sessionStorage.getItem("thechain_sid");
    if (!sid) {
        sid = crypto.randomUUID().replace(/-/g, "");
        sessionStorage.setItem("thechain_sid", sid);
    }
    return sid;
}

const API = {
    async post(url, data = {}) {
        const res = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Session-ID": _getSessionId(),
            },
            credentials: "include",
            body: JSON.stringify(data),
        });
        if (!res.ok) {
            const text = await res.text();
            console.error(`API POST ${url} failed (${res.status}):`, text);
            throw new Error(`Server error ${res.status}`);
        }
        return res.json();
    },
    async get(url) {
        const res = await fetch(url, {
            cache: "no-store",
            headers: { "X-Session-ID": _getSessionId() },
            credentials: "include",
        });
        if (!res.ok) {
            const text = await res.text();
            console.error(`API GET ${url} failed (${res.status}):`, text);
            throw new Error(`Server error ${res.status}`);
        }
        return res.json();
    },
    async del(url) {
        const res = await fetch(url, {
            method: "DELETE",
            headers: { "X-Session-ID": _getSessionId() },
            credentials: "include",
        });
        if (!res.ok) {
            const text = await res.text();
            console.error(`API DELETE ${url} failed (${res.status}):`, text);
            throw new Error(`Server error ${res.status}`);
        }
        return res.json();
    },
};

// ─── Pre-set Scenarios ─────────────────────────────────────────────────

const SCENARIOS = [
    // {
    //     id: "cool_original",
    //     name: "Cool Original",
    //     name_es: "Original Clásico",
    //     emoji: "❄️",
    //     desc: "Base game only — no modules",
    //     desc_es: "Solo juego base — sin módulos",
    //     modules: {},
    //     optional_rules: {},
    // },
    // {
    //     id: "new_milestones",
    //     name: "New Milestones",
    //     name_es: "Nuevos Hitos",
    //     emoji: "🏆",
    //     desc: "Milestones module only",
    //     desc_es: "Solo módulo de Hitos",
    //     modules: { milestones: true },
    //     optional_rules: {},
    // },
    // {
    //     id: "first_coffee",
    //     name: "Your First Cup of Coffee",
    //     name_es: "Tu Primera Taza de Café",
    //     emoji: "☕",
    //     desc: "Coffee module",
    //     desc_es: "Módulo de Café",
    //     modules: { coffee: true },
    //     optional_rules: {},
    // },
    {
        id: "korean_city",
        name: "Korean City",
        name_es: "Ciudad Coreana",
        emoji: "🫰",
        desc: "New Districts + Kimchi",
        desc_es: "Nuevos Distritos + Kimchi",
        modules: { new_districts: true, kimchi: true },
        optional_rules: {},
    },
    {
        id: "nightlife",
        name: "Nightlife",
        name_es: "Vida Nocturna",
        emoji: "🌙",
        desc: "Milestones + Night Shift Managers",
        desc_es: "Hitos + Gerentes Nocturnos",
        modules: { milestones: true, night_shift: true },
        optional_rules: {},
    },
    {
        id: "sustenance",
        name: "Sustenance",
        name_es: "Sustento",
        emoji: "🍟",
        desc: "Coffee + Fry Chefs",
        desc_es: "Café + Cocineros de Frito",
        modules: { coffee: true, fry_chefs: true },
        optional_rules: {},
    },
    {
        id: "upmarket_area",
        name: "Upmarket Area",
        name_es: "Zona Exclusiva",
        emoji: "🍽️",
        desc: "Milestones + New Districts + Gourmet + Sushi",
        desc_es: "Hitos + Nuevos Distritos + Gourmet + Sushi",
        modules: { milestones: true, new_districts: true, gourmet: true, sushi: true },
        optional_rules: {},
    },
    {
        id: "city_builder",
        name: "City Builder",
        name_es: "Constructor de Ciudad",
        emoji: "🏗️",
        desc: "Lobbyists + New Districts + Rural Marketeer",
        desc_es: "Lobbistas + Nuevos Distritos + Promotor Rural",
        modules: { lobbyists: true, new_districts: true, rural_marketeer: true },
        optional_rules: {},
    },
    {
        id: "asian_fusion",
        name: "Asian Fusion",
        name_es: "Fusión Asiática",
        emoji: "🥢",
        desc: "Sushi + Kimchi + Noodle + Ketchup",
        desc_es: "Sushi + Kimchi + Fideos + Ketchup",
        modules: { sushi: true, kimchi: true, noodle: true, ketchup: true },
        optional_rules: {},
    },
    {
        id: "first_mover",
        name: "First Mover",
        name_es: "Primer Movimiento",
        emoji: "🚀",
        desc: "Hard Choices + Ketchup + Movie Stars + Lobbyists + Reserve Prices",
        desc_es: "Elecciones Difíciles + Ketchup + Estrellas + Lobbistas + Precios Reserva",
        modules: { ketchup: true, movie_stars: true, lobbyists: true, reserve_prices: true },
        optional_rules: { hard_choices: true },
    },
    {
        id: "overtime",
        name: "Overtime",
        name_es: "Tiempo Extra",
        emoji: "⏰",
        desc: "Night Shift + Mass & Rural Marketeer + New Districts + Noodle + Reserve Prices",
        desc_es: "Nocturno + Promotores Masivo y Rural + Nuevos Distritos + Fideos + Precios Reserva",
        modules: { night_shift: true, mass_marketeer: true, rural_marketeer: true, new_districts: true, noodle: true, reserve_prices: true },
        optional_rules: {},
    },
    // {
    //     id: "henri_lo_menu",
    //     name: "Henri Lo Menu",
    //     name_es: "Menú Henri Lo",
    //     emoji: "👨‍🍳",
    //     desc: "All modules enabled!",
    //     desc_es: "¡Todos los módulos activados!",
    //     modules: { coffee: true, kimchi: true, noodle: true, sushi: true, gourmet: true, mass_marketeer: true, rural_marketeer: true, night_shift: true, ketchup: true, fry_chefs: true, movie_stars: true, reserve_prices: true, lobbyists: true, new_districts: true, milestones: true },
    //     optional_rules: {},
    // },
];

// All module keys (for unchecking modules not in a scenario)
const ALL_MODULE_KEYS = [
    "coffee", "kimchi", "noodle", "sushi", "gourmet",
    "mass_marketeer", "rural_marketeer", "night_shift",
    "ketchup", "fry_chefs", "movie_stars", "reserve_prices",
    "lobbyists", "new_districts", "milestones",
];
const ALL_RULE_KEYS = [
    "hard_choices", "expand_connections", "expand_6_restaurants",
    "aggressive_setup", "aggressive_restructuring",
];

// Module key → checkbox ID mapping
const MOD_CHECKBOX_MAP = {
    coffee: "mod-coffee", kimchi: "mod-kimchi", noodle: "mod-noodle",
    sushi: "mod-sushi", gourmet: "mod-gourmet",
    mass_marketeer: "mod-mass-marketeer", rural_marketeer: "mod-rural-marketeer",
    night_shift: "mod-night-shift", ketchup: "mod-ketchup",
    fry_chefs: "mod-fry-chefs", movie_stars: "mod-movie-stars",
    reserve_prices: "mod-reserve-prices", lobbyists: "mod-lobbyists",
    new_districts: "mod-new-districts", milestones: "mod-milestones",
};
const RULE_CHECKBOX_MAP = {
    hard_choices: "opt-hard-choices", expand_connections: "opt-expand-connections",
    expand_6_restaurants: "opt-expand-6", aggressive_setup: "opt-aggressive-setup",
    aggressive_restructuring: "opt-aggressive-restructuring",
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
    $("#file-welcome-upload").onchange = uploadSaveFromDevice;


    // Top bar
    $("#btn-menu").onclick = () => showOverlay(menuOverlay);
    $("#btn-undo").onclick = doUndo;
    $("#btn-save").onclick = downloadSaveToDevice;
    btnLang.onclick = () => {
        const lang = toggleLang();
        btnLang.textContent = lang.toUpperCase();
        if (gameActive) refreshUI();
    };
    btnMode.onclick = toggleMode;

    // Menu
    $("#btn-new-game").onclick = () => { hideOverlay(menuOverlay); showOverlay(newgameOverlay); };
    $("#btn-save-load").onclick = () => { hideOverlay(menuOverlay); showLoadOverlay(); };
    $("#btn-bank-break").onclick = doBankBreak;
    $("#btn-view-reserve").onclick = viewReserveCard;
    $("#btn-close-menu").onclick = () => hideOverlay(menuOverlay);

    // New game
    $("#btn-start-game").onclick = startNewGame;
    $("#btn-cancel-setup").onclick = () => hideOverlay(newgameOverlay);

    // Enable/Disable all modules
    const btnEnableAll = document.getElementById("btn-enable-all");
    const btnDisableAll = document.getElementById("btn-disable-all");
    if (btnEnableAll) {
        btnEnableAll.addEventListener("click", (e) => {
            e.stopPropagation();
            document.querySelectorAll("#modules-grid input[type='checkbox']").forEach(cb => { cb.checked = true; });
        });
    }
    if (btnDisableAll) {
        btnDisableAll.addEventListener("click", (e) => {
            e.stopPropagation();
            document.querySelectorAll("#modules-grid input[type='checkbox']").forEach(cb => { cb.checked = false; });
        });
    }

    // Setup tabs
    $("#btn-tab-individual").onclick = () => switchSetupTab("individual");
    $("#btn-tab-scenarios").onclick = () => switchSetupTab("scenarios");
    buildScenarioList();

    // Load / Save & Load
    $("#btn-close-load").onclick = () => hideOverlay(loadOverlay);
    $("#btn-download-save").onclick = downloadSaveToDevice;
    $("#file-upload-save").onchange = uploadSaveFromDevice;

    // Card zoom
    $$(".card-img").forEach(img => {
        img.onclick = () => {
            if (img.src && !img.src.endsWith("/")) {
                $("#card-zoom-img").src = img.src;
                showOverlay(cardOverlay);
            }
        };
    });
    // Competition card zoom
    $("#comp-card-img").onclick = () => {
        const img = $("#comp-card-img");
        if (img.src && !img.src.endsWith("placeholder.png")) {
            $("#card-zoom-img").src = img.src;
            showOverlay(cardOverlay);
        }
    };
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
}

// ─── Overlays ──────────────────────────────────────────────────────────

function showOverlay(el) { el.classList.remove("hidden"); }
function hideOverlay(el) { el.classList.add("hidden"); }

// ─── Setup Tabs & Scenarios ────────────────────────────────────────────

function switchSetupTab(tab) {
    const indView = $("#individual-view");
    const sceView = $("#scenario-view");
    const btnInd = $("#btn-tab-individual");
    const btnSce = $("#btn-tab-scenarios");

    if (tab === "scenarios") {
        indView.classList.add("hidden");
        sceView.classList.remove("hidden");
        btnInd.classList.remove("active");
        btnSce.classList.add("active");
    } else {
        sceView.classList.add("hidden");
        indView.classList.remove("hidden");
        btnSce.classList.remove("active");
        btnInd.classList.add("active");
    }
}

function buildScenarioList() {
    const list = $("#scenario-list");
    if (!list) return;
    list.innerHTML = "";
    SCENARIOS.forEach(sc => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "scenario-btn";
        const es = currentLang === "es";
        btn.innerHTML = `<span class="scenario-emoji">${sc.emoji}</span>`
            + `<span class="scenario-info">`
            + `<strong>${es ? sc.name_es : sc.name}</strong>`
            + `<small>${es ? sc.desc_es : sc.desc}</small>`
            + `</span>`;
        btn.onclick = () => applyScenario(sc);
        list.appendChild(btn);
    });
}

function applyScenario(sc) {
    // Set modules
    ALL_MODULE_KEYS.forEach(key => {
        const cb = document.getElementById(MOD_CHECKBOX_MAP[key]);
        if (cb) cb.checked = !!sc.modules[key];
    });
    // Set optional rules
    ALL_RULE_KEYS.forEach(key => {
        const cb = document.getElementById(RULE_CHECKBOX_MAP[key]);
        if (cb) cb.checked = !!sc.optional_rules[key];
    });
    // Switch to individual view so user can review/tweak
    switchSetupTab("individual");
}

// ─── New Game ──────────────────────────────────────────────────────────

async function startNewGame() {
    const modules = {
        coffee: $("#mod-coffee").checked,
        kimchi: $("#mod-kimchi").checked,
        noodle: $("#mod-noodle").checked,
        sushi: $("#mod-sushi").checked,
        gourmet: $("#mod-gourmet").checked,
        mass_marketeer: $("#mod-mass-marketeer").checked,
        rural_marketeer: $("#mod-rural-marketeer").checked,
        night_shift: $("#mod-night-shift").checked,
        ketchup: $("#mod-ketchup").checked,
        fry_chefs: $("#mod-fry-chefs").checked,
        movie_stars: $("#mod-movie-stars").checked,
        reserve_prices: $("#mod-reserve-prices").checked,
        lobbyists: $("#mod-lobbyists").checked,
        new_districts: $("#mod-new-districts").checked,
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
    // Game over — return to welcome screen instead of calling the API
    if (gameState && gameState.phase === "game_over") {
        gameScreen.classList.add("hidden");
        welcomeScreen.classList.remove("hidden");
        gameActive = false;
        return;
    }
    btnAdvance.disabled = true;
    try {
        const result = await API.post("/api/game/advance");
        btnAdvance.disabled = false;

        await refreshState();
        // Show original phase message if milestones intercepted the result
        setStatus(result.phase_message || result.message);

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
    } catch (e) {
        console.error("advancePhase error:", e);
        btnAdvance.disabled = false;
        setStatus("Error advancing phase. Please try again.");
        await refreshState();
    }
}

async function submitInput() {
    const formData = collectInputData();
    console.log("submitInput called, formData:", JSON.stringify(formData));
    if (!formData) { console.warn("submitInput: no formData, returning"); return; }

    hideOverlay(inputOverlay);
    try {
        console.log("submitInput: calling API.post...");
        const result = await API.post("/api/game/input", formData);
        console.log("submitInput: API response:", JSON.stringify(result));
        await refreshState();
        console.log("submitInput: refreshState done");
        // Show original phase message if milestones intercepted the result
        setStatus(result.phase_message || result.message);

        if (result.status === "waiting" && result.input_needed) {
            showInputPrompt(result.input_needed);
        }
    } catch (e) {
        console.error("submitInput error:", e);
        setStatus("Error processing input. Please try again.");
        await refreshState();
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
        } else if (field.tagName === "SELECT" && /^campaign_slot_/.test(name)) {
            // Campaign number selects should be sent as integers
            data[name] = parseInt(field.value) || 0;
        } else {
            data[name] = field.value;
        }
    });

    return data;
}

function showInputPrompt(input) {
    const prompt = currentLang === "es" ? (input.prompt_es || input.prompt) : input.prompt;

    const promptEl = $("#input-prompt");
    // For competition card acknowledgment, use innerHTML to support line breaks
    if (input.type === "acknowledge_competition_card") {
        const isWarm = input.card_type === "warm";
        const willResolve = input.will_resolve;
        const matchClass = willResolve ? "comp-prompt-match" : "comp-prompt-nomatch";
        const icon = isWarm ? "🔴" : "🟢";
        // Replace \n with <br> for proper line breaks
        const htmlPrompt = prompt.replace(/\n/g, "<br>");
        promptEl.innerHTML = `<div class="comp-step-prompt ${matchClass}">${icon} ${htmlPrompt}</div>`;
    } else {
        promptEl.textContent = prompt;
    }

    const container = $("#input-fields");
    container.innerHTML = "";
    inputOverlay.dataset.inputType = input.type;

    // ── Display inventory if provided (e.g., during dinnertime prompt) ───────
    if (input.inventory_display && input.inventory_display.length > 0) {
        const inventorySection = document.createElement("div");
        inventorySection.className = "prompt-inventory";
        
        const heading = document.createElement("div");
        heading.className = "prompt-inventory-heading";
        heading.textContent = currentLang === "es" ? "Inventario actual:" : "Current Inventory:";
        inventorySection.appendChild(heading);
        
        const itemsContainer = document.createElement("div");
        itemsContainer.className = "prompt-inventory-items";
        
        input.inventory_display.forEach(item => {
            const itemEl = document.createElement("div");
            itemEl.className = "prompt-inventory-item";
            itemEl.textContent = `${item.icon} ${item.item}: ${item.count}`;
            itemsContainer.appendChild(itemEl);
        });
        
        inventorySection.appendChild(itemsContainer);
        container.appendChild(inventorySection);
    }

    // ── Milestone roundup — custom two-section UI ─────────────────────
    if (input.type === "milestone_player_roundup") {
        const chainClaimed = [...(input.chain_claimed || [])].sort((a, b) => {
            const ca = (a.color || "").toLowerCase();
            const cb = (b.color || "").toLowerCase();
            return ca < cb ? -1 : ca > cb ? 1 : 0;
        });
        const available = [...(input.available || [])].sort((a, b) => {
            const ca = (a.color || "").toLowerCase();
            const cb = (b.color || "").toLowerCase();
            return ca < cb ? -1 : ca > cb ? 1 : 0;
        });

        if (chainClaimed.length > 0) {
            const notice = document.createElement("div");
            notice.className = "milestone-roundup-section milestone-roundup-chain";
            const heading = document.createElement("p");
            heading.className = "milestone-roundup-heading";
            heading.textContent = currentLang === "es"
                ? "La Cadena reclamó estos hitos. Marca los que TÚ TAMBIÉN reclamaste (reclamación conjunta — no coloca ficha X):"
                : "The Chain claimed these milestones. Check any you ALSO claimed (joint claim — no X token needed):";
            notice.appendChild(heading);

            const group = document.createElement("div");
            group.className = "checkbox-group";
            chainClaimed.forEach(m => {
                const lbl = document.createElement("label");
                lbl.className = "milestone-roundup-option chain-claimed-option";
                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.value = m.key;
                cb.dataset.fieldName = "chain_jointly_claimed";
                const labelText = currentLang === "es" ? m.label_es : m.label_en;
                lbl.appendChild(cb);
                lbl.appendChild(document.createTextNode(" 🏆 " + labelText));
                if (m.color) lbl.style.borderLeft = "3px solid " + m.color;
                group.appendChild(lbl);
            });
            notice.appendChild(group);
            container.appendChild(notice);
        }

        if (available.length > 0) {
            const section = document.createElement("div");
            section.className = "milestone-roundup-section milestone-roundup-available";
            const heading = document.createElement("p");
            heading.className = "milestone-roundup-heading";
            heading.textContent = currentLang === "es"
                ? "¿Reclamaste alguno de estos hitos disponibles este turno?"
                : "Did you claim any of these available milestones this round?";
            section.appendChild(heading);

            const group = document.createElement("div");
            group.className = "checkbox-group";
            available.forEach(m => {
                const lbl = document.createElement("label");
                lbl.className = "milestone-roundup-option";
                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.value = m.key;
                cb.dataset.fieldName = "player_claimed";
                const labelText = currentLang === "es" ? m.label_es : m.label_en;
                lbl.appendChild(cb);
                lbl.appendChild(document.createTextNode(" " + labelText));
                if (m.color) lbl.style.borderLeft = "3px solid " + m.color;
                group.appendChild(lbl);
            });
            section.appendChild(group);
            container.appendChild(section);
        }

        showOverlay(inputOverlay);
        return;
    }

    // Track field definitions for dynamic dependencies
    let mostDemandField = null;
    let mostDemandDiv = null;

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
                // Support both {value, label} objects and plain strings
                if (typeof opt === "object" && opt.value !== undefined) {
                    o.value = opt.value;
                    o.textContent = opt.label || opt.value;
                } else {
                    o.value = opt;
                    o.textContent = foodLabel(opt);
                }
                sel.appendChild(o);
            });
            // Pre-select default if provided
            if (f.default !== undefined) {
                sel.value = String(f.default);
            }
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

        // For demand_info: track the most_demand_items field for dynamic updates
        if (f.name === "most_demand_items") {
            mostDemandField = f;
            mostDemandDiv = div;
            // Only hide if there is also an items_with_demand field (two-step all_demand flow)
            const hasItemsWithDemand = (input.fields || []).some(ff => ff.name === "items_with_demand");
            if (hasItemsWithDemand) {
                div.style.display = "none"; // hidden until 2+ items checked above
            }
        }

        container.appendChild(div);
    });

    // Wire dynamic dependency: items_with_demand → most_demand_items
    if ((input.type === "demand_info" || input.type === "competition_demand_info") && mostDemandDiv) {
        const firstCheckboxes = container.querySelectorAll('[data-field-name="items_with_demand"]');
        const rebuildMostDemand = () => {
            const checked = Array.from(firstCheckboxes).filter(cb => cb.checked).map(cb => cb.value);
            if (checked.length <= 1) {
                // 0 or 1 item: hide second list and clear its checkboxes
                mostDemandDiv.style.display = "none";
                mostDemandDiv.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
                return;
            }
            // 2+ items: show second list with only the checked items from first list
            mostDemandDiv.style.display = "";
            const group = mostDemandDiv.querySelector(".checkbox-group");
            group.innerHTML = "";
            checked.forEach(opt => {
                const lbl = document.createElement("label");
                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.value = opt;
                cb.dataset.fieldName = "most_demand_items";
                lbl.appendChild(cb);
                lbl.appendChild(document.createTextNode(" " + foodLabel(opt)));
                group.appendChild(lbl);
            });
        };
        firstCheckboxes.forEach(cb => cb.addEventListener("change", rebuildMostDemand));
    }

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
    phaseBadge.textContent = formatPhase(gameState.display_phase || gameState.phase);

    // Mode button
    btnMode.textContent = gameState.mode === "full" ? t("full_mode") : t("quick_mode");

    // Quick mode: show only cards + deck controls; hide everything else
    const quickPanel = $("#quick-controls");
    const tracksPanel = document.querySelector(".tracks-panel");
    const inventoryPanel = document.querySelector(".inventory-panel");
    const infoPanel = document.querySelector(".info-panel");
    const logPanel = document.querySelector(".log-panel");
    const actionRow = document.querySelector(".action-row");
    const statusMsg = $("#status-msg");
    const isQuick = gameState.mode === "quick";
    quickPanel.classList.toggle("hidden", !isQuick);
    if (tracksPanel) tracksPanel.classList.toggle("hidden", isQuick);
    if (inventoryPanel) inventoryPanel.classList.toggle("hidden", isQuick);
    if (infoPanel) infoPanel.classList.toggle("hidden", isQuick);
    if (logPanel) logPanel.classList.toggle("hidden", isQuick);
    if (actionRow) actionRow.classList.toggle("hidden", isQuick);
    turnBadge.classList.toggle("hidden", isQuick);
    phaseBadge.classList.toggle("hidden", isQuick);
    if (isQuick) { hideOverlay(inputOverlay); }

    // Cards
    updateCardImage("back", gameState.current_back_card);
    updateCardImage("front", gameState.current_front_card);
    updateCompetitionCard();

    // Deck info (always update so quick mode shows deck sizes)
    updateDeckInfo();

    // Full-mode only panels & phase logic
    if (!isQuick) {
        updateTracks();
        updateInventory();
        updateMarketeers();
        updateEmployees();
        updateMilestones();
        updateRestaurants();
        updateChainCash();
        updateLog();

        // Advance button — context-aware label
        let labelPhase;
        if (gameState.phase === "waiting_for_input" && gameState.next_phase_after_input) {
            labelPhase = gameState.next_phase_after_input;
        } else if (gameState.phase === "waiting_for_input" && gameState.phase_after_competition) {
            labelPhase = "continue_competition";
        } else {
            labelPhase = gameState.phase;
        }
        btnAdvance.textContent = getAdvanceLabel(labelPhase);
        if (gameState.phase === "game_over") {
            btnAdvance.disabled = false;
            btnAdvance.classList.add("pulse");
        } else if (gameState.phase === "waiting_for_input") {
            if (gameState.pending_input) {
                btnAdvance.disabled = true;
                btnAdvance.classList.remove("pulse");
                showInputPrompt(gameState.pending_input);
            } else {
                hideOverlay(inputOverlay);
                btnAdvance.disabled = false;
                btnAdvance.classList.add("pulse");
            }
        } else {
            hideOverlay(inputOverlay);
            btnAdvance.disabled = false;
            btnAdvance.classList.add("pulse");
        }
    }
}

const PLACEHOLDER_CARD = "/static/cards/placeholder.png";

function updateCardImage(side, cardData) {
    const img = side === "back" ? $("#back-card-img") : $("#front-card-img");
    if (cardData) {
        const src = side === "back" ? cardData.image_back : cardData.image_front;
        img.src = src || PLACEHOLDER_CARD;
    } else {
        img.src = PLACEHOLDER_CARD;
    }
}

function updateCompetitionCard() {
    const slot = $("#comp-card-slot");
    const img = $("#comp-card-img");
    const label = $("#comp-card-label");
    const card = gameState ? gameState.current_competition_card : null;

    if (!slot) return;

    if (!card) {
        slot.classList.add("hidden");
        return;
    }

    // Show the dedicated competition card slot
    slot.classList.remove("hidden");

    const isWarm = card.card_type === "warm";

    // Set card image
    if (card.image_front) {
        img.src = card.image_front;
    } else {
        img.src = PLACEHOLDER_CARD;
    }

    // Style the label
    const typeLabel = isWarm ? "🔴 Warm" : "🟢 Cool";
    const willResolve = card.will_resolve;
    const resolved = card.resolved;

    let statusText = "";
    if (resolved) {
        statusText = " — ✅ Resolved";
    } else if (willResolve === false) {
        statusText = " — ❌ Not matched";
    }
    label.textContent = `${typeLabel} #${card.card_number}${statusText}`;
    label.className = "card-label " + (isWarm ? "warm-label" : "cool-label");
}

function updateTracks() {
    if (!gameState || !gameState.tracks) return;
    const tracks = gameState.tracks;

    // Recruit & Train
    const rtPos = tracks.recruit_train.position;
    $("#rt-slots-value").textContent = tracks.open_slots;
    $("#rt-food-value").textContent = `×${tracks.food_amount}`;
    // $("#rt-info").textContent = `(${tracks.open_slots} ${t("open_slots")}, ${t("food")} ×${tracks.food_amount})`;
    renderTrackBar("rt-markers", 1, 4, rtPos, [
        "1", "2", "3", "4"
    ], 2); // shuffleAfter=2 inserts a SHUFFLE divider after position 2
    // Food multiplier sub-track (×2–×5 aligned with R&T positions)
    renderTrackBar("rt-food-markers", 1, 4, rtPos, [
        "×2", "×3", "×4", "×5"
    ], 2);

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

function renderTrackBar(containerId, min, max, current, labels, shuffleAfter) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";
    for (let i = min; i <= max; i++) {
        const m = document.createElement("div");
        m.className = "marker" + (i === current ? " active" : "");
        m.textContent = labels[i - min] || i;
        container.appendChild(m);
        // Insert SHUFFLE divider after the specified position
        if (shuffleAfter && i === shuffleAfter) {
            const s = document.createElement("div");
            s.className = "shuffle-divider";
            s.textContent = "⟡";
            s.title = "SHUFFLE";
            container.appendChild(s);
        }
    }
}

function updateInventory() {
    if (!gameState || !gameState.inventory) return;
    const grid = $("#inv-grid");
    grid.innerHTML = "";

    const items = ["burger", "pizza", "beer", "lemonade", "softdrink", "sushi", "noodle", "coffee", "kimchi"];
    const modules = gameState.modules || {};
    // Core items (burger, pizza, beer, lemonade, softdrink) are always shown
    const coreItems = new Set(["burger", "pizza", "beer", "lemonade", "softdrink"]);

    items.forEach(item => {
        // Skip expansion items whose module is disabled
        if (!coreItems.has(item) && modules[item] === false) return;

        const inv = gameState.inventory[item] || { top: 0, bottom: 0, total: 0, gained: 0, lost: 0 };
        const div = document.createElement("div");
        const gained = inv.gained || 0;
        const lost = inv.lost || 0;
        let deltaHtml = "";
        if (gained > 0) deltaHtml += `<span class="inv-delta gain">▲${gained}</span>`;
        if (lost > 0)   deltaHtml += `<span class="inv-delta loss">▼${lost}</span>`;
        div.className = "inv-item" + (inv.total === 0 ? " empty" : "");
        div.innerHTML = `
            <div class="inv-icon">${FOOD_ICONS[item] || "📦"}</div>
            <div class="inv-name">${t(item)}</div>
            <div class="inv-count">${inv.total}</div>
            <div class="inv-delta-row">${deltaHtml}</div>
        `;
        grid.appendChild(div);
    });
}

function updateMarketeers() {
    const container = $("#marketeer-slots");
    container.innerHTML = "";
    (gameState.marketeer_slots || []).forEach(slot => {
        const div = document.createElement("div");
        div.className = "slot-item" + (slot.is_busy ? " slot-busy-item" : "");
        if (slot.marketeer) {
            let details = `<span class="slot-num">${slot.slot}</span>`;
            details += `<span class="slot-name">${slot.marketeer}</span>`;
            if (slot.is_busy) {
                const itemIcon = FOOD_ICONS[slot.market_item] || "";
                const itemLabel = slot.market_item ? `${itemIcon} ${t(slot.market_item)}` : "";
                // Rural Marketeer: no campaign number — show "Giant Billboard"
                const campNum = slot.campaign_number != null
                    ? `#${slot.campaign_number}`
                    : (slot.marketeer === "Rural Marketeer" ? "🪧" : "");
                const campLeft = slot.campaigns_left === -1
                    ? "∞ " + (currentLang === "es" ? "(permanente)" : "(permanent)")
                    : (slot.campaigns_left != null
                        ? `${slot.campaigns_left} ${currentLang === "es" ? "rest." : "left"}`
                        : "");
                details += `<span class="slot-campaign">${itemLabel} ${campNum}</span>`;
                details += `<span class="slot-duration">${campLeft}</span>`;
            } else {
                details += `<span class="slot-status">${currentLang === "es" ? "Nuevo" : "New"}</span>`;
            }
            div.innerHTML = details;
        } else {
            div.innerHTML = `
                <span class="slot-num">${slot.slot}</span>
                <span class="slot-name empty-slot">${t("empty")}</span>
            `;
        }
        container.appendChild(div);
    });
    if (gameState.mass_marketeer) {
        const div = document.createElement("div");
        div.className = "slot-item slot-mass";
        div.innerHTML = `<span class="slot-num">M</span><span class="slot-name">Mass Marketeer</span><span class="slot-status">${currentLang === "es" ? "Listo (2x campañas)" : "Ready (2x campaigns)"}</span>`;
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

    const claimed = new Set(gameState.milestones_claimed || []);
    const unavailable = new Set(gameState.milestones_unavailable || []);
    const expired = new Set(gameState.milestones_expired || []);
    const turn2tokens = new Set(gameState.milestones_turn2_tokens || []);
    const activeMilestones = gameState.active_milestones || [];

    if (activeMilestones.length > 0) {
        // Sort milestones by color so they group visually
        const sorted = [...activeMilestones].sort((a, b) => {
            const ca = (a.color || "").toLowerCase();
            const cb = (b.color || "").toLowerCase();
            if (ca < cb) return -1;
            if (ca > cb) return 1;
            return 0;
        });
        // Show full milestone board with status indicators
        sorted.forEach(m => {
            const tag = document.createElement("span");
            const label = currentLang === "es" ? m.label_es : m.label_en;
            if (claimed.has(m.key)) {
                tag.className = "tag milestone";
                tag.textContent = "🏆 " + label;
                tag.title = currentLang === "es" ? "Reclamado por La Cadena" : "Claimed by The Chain";
            } else if (unavailable.has(m.key)) {
                tag.className = "tag milestone-unavailable";
                tag.textContent = "👤 " + label;
                tag.title = currentLang === "es" ? "Reclamado por el jugador" : "Claimed by player";
                tag.style.textDecoration = "line-through";
                tag.style.opacity = "0.5";
            } else if (expired.has(m.key)) {
                tag.className = "tag milestone-expired";
                tag.textContent = "✖ " + label;
                tag.title = currentLang === "es" ? "Expirado" : "Expired";
            } else {
                tag.className = "tag milestone-available";
                tag.textContent = label;
                if (turn2tokens.has(m.key)) {
                    tag.textContent = "⏰ " + label;
                    tag.title = currentLang === "es" ? "Eliminar después del turno 2" : "Remove after turn 2";
                } else {
                    tag.title = currentLang === "es" ? "Disponible" : "Available";
                }
            }
            // Apply color-coded left border accent if a color is defined
            if (m.color) {
                tag.style.borderLeft = "3px solid " + m.color;
            }
            container.appendChild(tag);
        });
    } else {
        // Fallback: show claimed and expired like before
        (gameState.milestones_claimed || []).forEach(m => {
            const tag = document.createElement("span");
            tag.className = "tag milestone";
            tag.textContent = "🏆 " + m.replace(/_/g, " ");
            container.appendChild(tag);
        });
        (gameState.milestones_expired || []).forEach(m => {
            const tag = document.createElement("span");
            tag.className = "tag milestone-expired";
            tag.textContent = "✖ " + m.replace(/_/g, " ");
            tag.title = "Expired";
            container.appendChild(tag);
        });
    }

    if (container.children.length === 0) {
        container.innerHTML = `<span class="text-muted">—</span>`;
    }

    // Show "View Reserve Card" button if player has first_to_have_20 milestone
    const viewReserveBtn = $("#btn-view-reserve");
    if (unavailable.has("first_to_have_20") && gameState.bank_reserve_card) {
        viewReserveBtn.classList.remove("hidden");
    } else {
        viewReserveBtn.classList.add("hidden");
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

function updateChainCash() {
    const totalEl = $("#chain-cash-total");
    const turnEl = $("#chain-cash-turn");
    if (!totalEl) return;
    const total = gameState.chain_total_cash || 0;
    const thisTurn = gameState.chain_cash_this_turn || 0;
    totalEl.textContent = `$${total}`;
    turnEl.textContent = thisTurn > 0 ? `+$${thisTurn} ${t("this_turn")}` : "";
    turnEl.style.display = thisTurn > 0 ? "block" : "none";
}

function updateDeckInfo() {
    if (!gameState) return;
    const ad = gameState.action_deck || {};
    const dp = gameState.discard_pile || {};
    const wd = gameState.warm_deck || {};
    const cd = gameState.cool_deck || {};
    const drawn = gameState.cards_drawn_this_cycle || 0;
    const cycles = gameState.deck_cycles || 0;
    const total = gameState.total_cards_drawn || 0;
    const deckSize = ad.size || 0;
    const discardSize = dp.size || 0;
    const posLabel = deckSize > 0 ? `${drawn} / ${deckSize + discardSize}` : "\u2014";
    const cycleLabel = cycles > 0 ? ` \u00b7 ${t("cycle")} #${cycles}` : "";
    const html = `
        \ud83d\udcc7 Action: ${deckSize} ${t("cards_remaining")}${discardSize > 0 ? ` \u00b7 \u267b\ufe0f ${discardSize} discarded` : ""} (${posLabel}${cycleLabel})<br>
        🔴 Warm: ${wd.size || 0}<br>
        🟢 Cool: ${cd.size || 0}<br>
        <small>${t("total_drawn")}: ${total}</small>
    `;
    const container = $("#deck-info");
    if (container) container.innerHTML = html;
    const quickContainer = document.getElementById("quick-deck-info");
    if (quickContainer) quickContainer.innerHTML = html;
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
        order_of_business: currentLang === "es" ? "Orden de Juego" : "Order of Business",
        recruit_train: currentLang === "es" ? "Reclutar" : "Recruit & Train",
        initiate_marketing: currentLang === "es" ? "Iniciar Marketing" : "Initiate Marketing",
        get_food: currentLang === "es" ? "Comida" : "Get Food",
        develop: currentLang === "es" ? "Desarrollar" : "Develop",
        lobby: "Lobby",
        expand_chain: currentLang === "es" ? "Expandir" : "Expand Chain",
        dinnertime: currentLang === "es" ? "Cena" : "Dinnertime",
        payday: currentLang === "es" ? "Día de Pago" : "Payday",
        marketing_campaigns: currentLang === "es" ? "Campañas de Marketing" : "Marketing Campaigns",
        cleanup: currentLang === "es" ? "Limpieza" : "Cleanup",
        game_over: currentLang === "es" ? "Fin" : "Game Over",
        waiting_for_input: currentLang === "es" ? "Esperando..." : "Waiting...",
    };
    return phases[phase] || phase;
}

function getAdvanceLabel(nextPhase) {
    const es = currentLang === "es";
    const turnOrder = gameState ? gameState.turn_order : null;

    // Worktime phases where turn order matters
    const worktimePhases = [
        "recruit_train", "initiate_marketing", "get_food",
        "develop", "lobby", "expand_chain"
    ];

    const isWorktime = worktimePhases.includes(nextPhase);

    // For worktime phases, labels depend on turn order
    // In FCM, the first player does ALL worktime phases, then the second player
    if (isWorktime && turnOrder) {
        // Chain's worktime phase labels (used in both turn orders)
        const chainLabels = {
            recruit_train:       es ? "R&T de La Cadena ▶"          : "Chain's R&T ▶",
            initiate_marketing:  es ? "Marketing de La Cadena ▶"    : "Chain's Marketing ▶",
            get_food:            es ? "Comida de La Cadena ▶"       : "Chain's Get Food ▶",
            develop:             es ? "Desarrollo de La Cadena ▶"   : "Chain's Develop ▶",
            lobby:               es ? "Lobby de La Cadena ▶"        : "Chain's Lobby ▶",
            expand_chain:        es ? "Expandir de La Cadena ▶"     : "Chain's Expand ▶",
        };

        if (turnOrder === "player_first" && nextPhase === "recruit_train") {
            // Player goes first — first worktime button reminds to do ALL worktime first
            return es
                ? "Tu Worktime hecho → R&T Cadena ▶"
                : "Your Worktime Done → Chain's R&T ▶";
        }

        return chainLabels[nextPhase];
    }

    // After Chain's last worktime (expand_chain), dinnertime button
    // When chain went first, remind player to do their worktime before dinnertime
    if (nextPhase === "dinnertime" && turnOrder === "chain_first") {
        return es
            ? "Tu Worktime hecho → Cena ▶"
            : "Your Worktime Done → Dinnertime ▶";
    }

    // Non-worktime phases — standard labels
    const labels = {
        setup:                 es ? "Iniciar Partida ▶"           : "Begin Game ▶",
        restructuring:         es ? "Iniciar Reestructuración ▶"  : "Begin Restructuring ▶",
        order_of_business:     es ? "Resolver Orden de Juego ▶"   : "Resolve Order of Business ▶",
        recruit_train:         es ? "Iniciar Reclutar ▶"          : "Begin Recruit & Train ▶",
        initiate_marketing:    es ? "Iniciar Marketing ▶"         : "Initiate Marketing ▶",
        get_food:              es ? "Resolver Comida ▶"           : "Resolve Get Food ▶",
        develop:               es ? "Resolver Desarrollar ▶"      : "Resolve Develop ▶",
        lobby:                 es ? "Resolver Lobby ▶"            : "Resolve Lobby ▶",
        expand_chain:          es ? "Resolver Expandir ▶"         : "Resolve Expand Chain ▶",
        dinnertime:            es ? "Iniciar Cena ▶"              : "Begin Dinnertime ▶",
        payday:                es ? "Resolver Día de Pago ▶"      : "Resolve Payday ▶",
        marketing_campaigns:   es ? "Resolver Campañas ▶"         : "Resolve Campaigns ▶",
        cleanup:               es ? "Limpieza y Fin de Turno ▶"   : "Cleanup & End Turn ▶",
        game_over:             es ? "🏁 Partida Terminada"        : "🏁 Game Over",
        waiting_for_input:     es ? "Esperando..."                : "Waiting...",
        continue_competition:  es ? "Continuar ▶"                 : "Continue ▶",
    };
    return labels[nextPhase] || (es ? "Siguiente Fase ▶" : "Next Phase ▶");
}

function foodLabel(item) {
    return (FOOD_ICONS[item] || "") + " " + t(item);
}

// Regex to capitalize food/drink item names in status messages
const _FOOD_NAMES_RE = new RegExp(
    "\\b(" + Object.keys(FOOD_ICONS).join("|") + ")\\b", "gi"
);

function setStatus(msg) {
    if (msg) {
        msg = msg.replace(_FOOD_NAMES_RE, m => m.charAt(0).toUpperCase() + m.slice(1));
    }
    statusMsg.textContent = msg || "";
}

// ─── Actions ───────────────────────────────────────────────────────────

async function doUndo() {
    hideOverlay(inputOverlay);          // dismiss any blocking overlay immediately
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
    if (result.reveal_reserve_card) {
        showReserveCardOverlay(result.reveal_reserve_card, result.reserve_prices_module, false);
    } else {
        setStatus(result.message);
    }
}

async function viewReserveCard() {
    const result = await API.post("/api/game/view_reserve");
    if (result.status === "error") {
        setStatus(result.message);
        return;
    }
    if (result.reserve_card) {
        showReserveCardOverlay(result.reserve_card, result.reserve_prices_module, true);
    }
}

function showReserveCardOverlay(cardValue, isReservePrices, isMilestoneBenefit) {
    if (isReservePrices) {
        // Reserve Prices module: show alternate Base Price card image (.png)
        $("#reserve-reveal-img").src = `/static/cards/reserve_price_${cardValue}.png`;
        $("#reserve-reveal-header").textContent = "🏦 The Chain's Base Price Reserve";
        if (isMilestoneBenefit) {
            $("#reserve-reveal-sub").textContent =
                "🏆 Milestone Benefit: You can view the Chain's base price card.";
            $("#reserve-reveal-extra").textContent =
                "The base price card is $" + cardValue + ". This does NOT trigger a bank break.";
        } else {
            $("#reserve-reveal-sub").textContent =
                "The base price card secretly chosen at the start of this game was…";
            $("#reserve-reveal-extra").textContent =
                "Add $400 to the bank (2 players × $200). Compare this card with yours to determine the new base unit price.";
        }
        $("#reserve-reveal-extra").classList.remove("hidden");
    } else {
        // Base game: show standard reserve card image (.jpg)
        $("#reserve-reveal-img").src = `/static/cards/reserve${cardValue}.jpg`;
        $("#reserve-reveal-header").textContent = "🏦 The Chain's Bank Reserve";
        if (isMilestoneBenefit) {
            $("#reserve-reveal-sub").textContent =
                "🏆 Milestone Benefit: You can view the Chain's reserve card.";
            $("#reserve-reveal-extra").textContent =
                "The reserve card is $" + cardValue + ". This does NOT trigger a bank break.";
            $("#reserve-reveal-extra").classList.remove("hidden");
        } else {
            $("#reserve-reveal-sub").textContent =
                "The bank card secretly chosen at the start of this game was…";
            $("#reserve-reveal-extra").classList.add("hidden");
        }
    }
    showOverlay($("#reserve-reveal-overlay"));
}

function closeReserveReveal() {
    hideOverlay($("#reserve-reveal-overlay"));
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

async function quickShuffleDeck(deckName) {
    const result = await API.post("/api/game/quick/shuffle", { deck: deckName });
    if (result.status === "error") { setStatus(result.message); return; }
    await refreshState();
    setStatus(currentLang === "es" ? `Mazo ${deckName} barajado.` : `${deckName} deck shuffled.`);
}

async function quickDiscardFrom(deckName) {
    const result = await API.post("/api/game/quick/discard", { deck: deckName });
    if (result.status === "error") { setStatus(result.message); return; }
    await refreshState();
    const cardLabel = result.card ? `${result.card.card_type} #${result.card.card_number}` : "card";
    setStatus(currentLang === "es" ? `${cardLabel} descartada de ${deckName}.` : `${cardLabel} discarded from ${deckName} deck.`);
}

// ─── Competition Draw / Resolve ────────────────────────────────────────

async function quickDrawCompetition(deckName) {
    const result = await API.post("/api/game/quick/draw_competition", { deck: deckName });
    if (result.status === "error") { setStatus(result.message); return; }
    await refreshState();
    const card = result.card;
    const container = document.getElementById(`${deckName}-drawn-card`);
    if (container && card) {
        const label = `${card.card_type} #${card.card_number}`;
        const imgSrc = card.image_front || "";
        container.innerHTML = `
            <div class="drawn-card-preview">
                ${imgSrc ? `<img src="${imgSrc}" class="drawn-card-img" alt="${label}">` : ""}
                <span class="drawn-card-label">${label}</span>
            </div>
            <div class="drawn-card-actions">
                <button class="primary-btn" onclick="resolveCompetition('${deckName}', true)">
                    ${currentLang === "es" ? "✅ Resuelta" : "✅ Resolved"}
                </button>
                <button class="muted-btn" onclick="resolveCompetition('${deckName}', false)">
                    ${currentLang === "es" ? "❌ No resuelta" : "❌ Not Resolved"}
                </button>
            </div>
        `;
        container.classList.remove("hidden");
    }
}

async function resolveCompetition(deckName, wasResolved) {
    const result = await API.post("/api/game/quick/resolve_competition", {
        deck: deckName,
        resolved: wasResolved,
    });
    if (result.status === "error") { setStatus(result.message); return; }
    const container = document.getElementById(`${deckName}-drawn-card`);
    if (container) { container.classList.add("hidden"); container.innerHTML = ""; }
    await refreshState();
    if (wasResolved) {
        setStatus(currentLang === "es"
            ? `Carta devuelta al fondo del mazo ${deckName}.`
            : `Card returned to bottom of ${deckName} deck.`);
    } else {
        setStatus(currentLang === "es"
            ? "Carta colocada al fondo del mazo de acci\u00f3n."
            : "Card placed on bottom of action deck.");
    }
}

// ─── Download / Upload Save ───────────────────────────────────────────

function downloadSaveToDevice() {
    // Navigation requests can't carry custom headers, so pass session id
    // as a query parameter instead.
    window.location.href = `/api/game/download?session_id=${_getSessionId()}`;
}

async function uploadSaveFromDevice(e) {
    const fileInput = e ? e.target : $("#file-upload-save");
    const file = fileInput.files[0];
    if (!file) return;

    const form = new FormData();
    form.append("file", file);

    try {
        const res = await fetch("/api/game/upload", {
            method: "POST",
            headers: { "X-Session-ID": _getSessionId() },
            credentials: "include",
            body: form,
        });
        const result = await res.json();
        if (result.status === "ok") {
            hideOverlay(loadOverlay);
            gameActive = true;
            welcomeScreen.classList.add("hidden");
            gameScreen.classList.remove("hidden");
            await refreshState();
            setStatus(result.message);
        } else {
            setStatus(result.message);
        }
    } catch (e) {
        setStatus("Upload failed: " + e.message);
    }
    fileInput.value = "";
}
