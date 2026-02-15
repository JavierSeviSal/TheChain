/* ═══════════════════════════════════════════════════════════════════════
   i18n — English / Spanish translations
   ═══════════════════════════════════════════════════════════════════════ */

const I18N = {
    en: {
        // Top bar
        menu: "Menu",
        // Welcome
        welcome_desc: "Solo Automa Companion for Food Chain Magnate",
        new_game: "New Game",
        load_game: "Load Game",
        save_game: "Save Game",
        // Setup
        new_game_setup: "New Game Setup",
        modules: "Expansion Modules",
        difficulty: "Difficulty Options",
        game_mode: "Game Mode",
        start_game: "Start Game",
        cancel: "Cancel",
        close: "Close",
        bank_break: "Bank Break!",
        // Phases
        next_phase: "Next Phase ▶",
        // Panels
        tracks: "Tracks",
        recruit_train_short: "R&T",
        price_distance: "Price+Dist",
        waitresses: "Waitresses",
        competition: "Competition",
        inventory: "Inventory",
        marketeers: "Marketeers",
        employees: "Employees",
        milestones: "Milestones",
        restaurants: "Restaurants",
        deck_info: "Deck",
        action_log: "Action Log",
        food_cleanup: "Food & Cleanup",
        recruit_train: "Recruit & Train",
        // Quick mode
        quick_controls: "Quick Controls",
        draw_card: "Draw Card",
        update_tracks: "Update Tracks",
        // Input
        confirm: "Confirm",
        // Food items
        burger: "Burger",
        pizza: "Pizza",
        sushi: "Sushi",
        noodle: "Noodle",
        coffee: "Coffee",
        kimchi: "Kimchi",
        beer: "Beer",
        lemonade: "Lemonade",
        // Competition levels
        cold: "Cold",
        cool: "Cool",
        neutral: "Neutral",
        warm: "Warm",
        hot: "Hot",
        // Misc
        empty: "Empty",
        busy: "BUSY",
        turn: "Turn",
        open_slots: "open slots",
        no_card: "No card",
        cards_remaining: "cards remaining",
        slot: "Slot",
        tile: "Tile",
        save_name: "Save name",
        full_mode: "Full",
        quick_mode: "Quick",
    },
    es: {
        menu: "Menú",
        welcome_desc: "Compañero Automa Solo para Food Chain Magnate",
        new_game: "Nueva Partida",
        load_game: "Cargar Partida",
        save_game: "Guardar Partida",
        new_game_setup: "Configurar Nueva Partida",
        modules: "Módulos de Expansión",
        difficulty: "Opciones de Dificultad",
        game_mode: "Modo de Juego",
        start_game: "Iniciar Partida",
        cancel: "Cancelar",
        close: "Cerrar",
        bank_break: "¡Quiebra del Banco!",
        next_phase: "Siguiente Fase ▶",
        tracks: "Pistas",
        recruit_train_short: "R&E",
        price_distance: "Precio+Dist",
        waitresses: "Camareras",
        competition: "Competencia",
        inventory: "Inventario",
        marketeers: "Promotores",
        employees: "Empleados",
        milestones: "Hitos",
        restaurants: "Restaurantes",
        deck_info: "Mazo",
        action_log: "Registro de Acciones",
        food_cleanup: "Comida y Limpieza",
        recruit_train: "Reclutar y Entrenar",
        quick_controls: "Controles Rápidos",
        draw_card: "Robar Carta",
        update_tracks: "Actualizar Pistas",
        confirm: "Confirmar",
        burger: "Hamburguesa",
        pizza: "Pizza",
        sushi: "Sushi",
        noodle: "Fideos",
        coffee: "Café",
        kimchi: "Kimchi",
        beer: "Cerveza",
        lemonade: "Limonada",
        cold: "Frío",
        cool: "Fresco",
        neutral: "Neutro",
        warm: "Cálido",
        hot: "Caliente",
        empty: "Vacío",
        busy: "OCUPADO",
        turn: "Turno",
        open_slots: "casillas abiertas",
        no_card: "Sin carta",
        cards_remaining: "cartas restantes",
        slot: "Casilla",
        tile: "Casilla",
        save_name: "Nombre del guardado",
        full_mode: "Completo",
        quick_mode: "Rápido",
    },
};

const FOOD_ICONS = {
    burger: "🍔",
    pizza: "🍕",
    sushi: "🍣",
    noodle: "🍜",
    coffee: "☕",
    kimchi: "🥬",
    beer: "🍺",
    lemonade: "🍋",
};

let currentLang = localStorage.getItem("chain_lang") || "en";

function t(key) {
    return (I18N[currentLang] && I18N[currentLang][key]) || I18N.en[key] || key;
}

function applyI18n() {
    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        el.textContent = t(key);
    });
}

function toggleLang() {
    currentLang = currentLang === "en" ? "es" : "en";
    localStorage.setItem("chain_lang", currentLang);
    applyI18n();
    return currentLang;
}
