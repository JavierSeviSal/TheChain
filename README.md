# The Chain — Digital Companion

A web-based companion app for **The Chain**, the solo automa variant for the board game **Food Chain Magnate**.  
Run the automa entirely from your phone or laptop — no physical cards needed.

---

## Features

- **Full Automation mode** — the app drives the entire automa turn: flips cards, adjusts competition tracks, recruits employees, manages inventory, and walks you through every phase.
- **Quick Mode** — draw a card and manually update tracks for a lighter experience.
- **Card images** extracted directly from the official PDF, cropped to the gray box borders.
- **Save / Load** — persist game state to JSON; auto-save after every phase.
- **Undo** — step back to the previous phase.
- **Bilingual UI** — English / Spanish, togglable at any time.
- **Expansion toggles** — enable/disable Ketchup & Mustard, The CFO, and Milestones when starting a new game.
- **Mobile-first responsive design** — works on phones, tablets, and desktops.

---

## Project Structure

```
TheChain/
├── app.py                   # Flask server & REST API
├── requirements.txt         # Python dependencies
├── Cartas.pdf               # Source PDF with 44 card designs
├── Tableros.pdf             # Source PDF with game mats/boards
├── Manual.pdf               # Automa rules reference
│
├── game/                    # Core game logic (pure Python)
│   ├── models.py            # Data models, enums, dataclasses
│   ├── cards.py             # All 44 cards encoded as structured data
│   ├── engine.py            # State-machine game engine
│   └── save_manager.py      # JSON serialisation / deserialisation
│
├── tools/
│   └── extract_cards.py     # One-time tool: extract card & board images from PDFs
│
├── templates/
│   └── index.html           # Single-page app shell (Jinja2)
│
├── static/
│   ├── css/style.css        # Mobile-first dark-theme stylesheet
│   ├── js/app.js            # Frontend application logic
│   ├── js/i18n.js           # EN/ES translations
│   ├── cards/               # 88 PNG card images (44 × front/back)
│   └── boards/              # 3 PNG mat images (inventory ×2, tracks)
│
└── saves/                   # Game save files (JSON)
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

**Requirements:** Python 3.8+, Flask, PyMuPDF, Pillow, PyPDF2.

### 2. Extract card & board images (one-time)

```bash
python tools/extract_cards.py
```

This renders every page of `Cartas.pdf` and `Tableros.pdf` at 300 DPI, detects the gray border grid, and crops each card/mat to its exact boundaries.  
Output: `static/cards/` (88 PNGs) and `static/boards/` (3 PNGs).

### 3. Run the server

```bash
python app.py
```

Open **http://localhost:5000** in your browser (or use your LAN IP to play from a phone on the same network).

---

## How It Works

### Game Modes

| Mode | Description |
|------|-------------|
| **Full Automation** | The app runs the complete automa turn. You only provide inputs when the automa needs information about _your_ game state (e.g. your earnings, restaurant placement). |
| **Quick Mode** | Draw a card and manually move track markers. Useful when you just want the card draw managed for you. |

### Turn Phases (Full mode)

1. **Restructuring** — flip the top Action card; adjust competition level based on the card face.
2. **Recruit & Train** — execute action slots (recruit employees, marketers; place map tiles).
3. **Get Food** — automa stocks inventory based on demand rules.
4. **Marketing** — place marketing campaigns if the card instructs.
5. **Develop** — resolve development actions.
6. **Lobby** — resolve lobby/political actions.
7. **Expand Chain** — open new restaurants if triggered.
8. **Dinnertime** — you report your earnings vs. the automa's to adjust the competition track.
9. **Cleanup** — drop perishable inventory, advance turn counter, check for game-end.

### Competition Track

The competition level (Cold → Cool → Neutral → Warm → Hot) determines which competition deck is active and affects the automa's aggressiveness.

### Recruit & Train Track

Tracks the automa's workforce size. Higher positions unlock more action slots per turn and increase food acquisition.

---

## API Reference

All endpoints return JSON.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/game/new` | Start a new game. Body: `{ "expansions": [...] }` |
| `GET`  | `/api/game/state` | Current game state (cards, tracks, inventory, phase, log) |
| `POST` | `/api/game/advance` | Advance to the next phase |
| `POST` | `/api/game/input` | Submit player input. Body: `{ "key": "...", "value": "..." }` |
| `POST` | `/api/game/undo` | Undo last phase |
| `POST` | `/api/game/mode` | Switch mode. Body: `{ "mode": "full" \| "quick" }` |
| `POST` | `/api/game/language` | Switch language. Body: `{ "lang": "en" \| "es" }` |
| `POST` | `/api/game/quick/draw` | Quick mode: draw a card |
| `POST` | `/api/game/quick/track` | Quick mode: update a track. Body: `{ "track": "...", "value": ... }` |
| `POST` | `/api/game/save` | Save current game. Body: `{ "slot": "name" }` |
| `POST` | `/api/game/load` | Load a save. Body: `{ "slot": "name" }` |
| `GET`  | `/api/game/saves` | List all save slots |
| `DELETE` | `/api/game/saves/<slot>` | Delete a save slot |

---

## Card Image Extraction

The extraction tool (`tools/extract_cards.py`) works as follows:

1. Renders each PDF page at **300 DPI** using PyMuPDF.
2. Converts to a NumPy array and scans for **gray border lines** (RGB ≈ 183, 178, 173).
3. Detects the 3 horizontal and 3 vertical divider lines that form the 2×2 card grid.
4. Crops each of the 4 quadrants to produce individual card images.
5. Falls back to known pixel positions if border detection fails.

For the board mats, it detects the bounding box of all non-white content and crops away the white margins.

---

## Tech Stack

- **Backend:** Python 3.8+ / Flask
- **Frontend:** Vanilla HTML, CSS, JavaScript (no build step)
- **PDF processing:** PyMuPDF (fitz), Pillow, NumPy
- **Persistence:** JSON files
- **Design:** Mobile-first, dark theme, responsive grid

---

## License

This is a fan-made companion tool. **Food Chain Magnate** is designed by Jeroen Doumen and Joris Wiersinga, published by Splotter Spellen. **The Chain** automa is designed by bgg user @runner199. All card artwork and game content belong to their respective owners.
