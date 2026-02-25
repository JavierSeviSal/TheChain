"""Flask application for The Chain automa companion."""

from __future__ import annotations

import io
import json
import os
import threading
import time
import uuid

from flask import (
    Flask,
    g,
    jsonify,
    request,
    send_file,
    send_from_directory,
    render_template,
)

from game.engine import GameEngine
from game.save_manager import (
    save_game,
    load_game,
    list_saves,
    delete_save,
    _serialize_full_state,
    _deserialize_full_state,
)

app = Flask(__name__, static_folder="static", template_folder="templates")

# ─── Session Management ───────────────────────────────────────────────

SESSION_TIMEOUT = 2 * 60 * 60  # 2 hours
COOKIE_NAME = "thechain_session"
BASE_SAVES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves")

_sessions: dict[str, dict] = {}  # sid -> {"engine": GameEngine, "last": float}
_lock = threading.Lock()


def _get_session_id() -> str:
    """Return (or create) a session id via cookie, header, or query param.

    Resolution order:
      1.  g._sid            (already resolved this request)
      2.  X-Session-ID header  (client-generated, works in iframes)
      3.  ?session_id query param  (for navigations like download)
      4.  thechain_session cookie  (classic fallback)
    """
    if hasattr(g, "_sid"):
        return g._sid

    sid = (
        request.headers.get("X-Session-ID")
        or request.args.get("session_id")
        or request.cookies.get(COOKIE_NAME)
    )

    if sid and sid in _sessions:
        _sessions[sid]["last"] = time.time()
        g._sid = sid
        return sid

    # New session — reuse the client-supplied id when present so both
    # sides agree on the key without a round-trip.
    if not sid:
        sid = uuid.uuid4().hex
    with _lock:
        _sessions[sid] = {"engine": GameEngine(), "last": time.time()}
    g._sid = sid
    return sid


def _get_engine() -> GameEngine:
    sid = _get_session_id()
    return _sessions[sid]["engine"]


def _get_saves_dir() -> str:
    sid = _get_session_id()
    d = os.path.join(BASE_SAVES_DIR, sid)
    os.makedirs(d, exist_ok=True)
    return d


def _attach_cookie(response, sid: str):
    # Use SameSite=None + Secure so the cookie works inside cross-site
    # iframes (e.g. Hugging Face Spaces embeds).
    response.set_cookie(
        COOKIE_NAME,
        sid,
        max_age=SESSION_TIMEOUT,
        httponly=True,
        samesite="None",
        secure=True,
    )
    return response


def _cleanup_sessions():
    """Remove sessions older than timeout."""
    now = time.time()
    with _lock:
        expired = [s for s, v in _sessions.items() if now - v["last"] > SESSION_TIMEOUT]
        for s in expired:
            _sessions.pop(s, None)


@app.before_request
def _before():
    _cleanup_sessions()


@app.after_request
def _after(response):
    sid = _get_session_id()
    return _attach_cookie(response, sid)


# ─── Pages ─────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


# ─── Game API ──────────────────────────────────────────────────────────────


@app.route("/api/game/new", methods=["POST"])
def new_game():
    data = request.json or {}
    engine = _get_engine()
    result = engine.new_game(
        modules=data.get("modules"),
        optional_rules=data.get("optional_rules"),
        mode=data.get("mode", "full"),
        language=data.get("language", "en"),
    )
    return jsonify(result)


@app.route("/api/game/state")
def get_state():
    engine = _get_engine()
    return jsonify(engine.state.to_dict())


@app.route("/api/game/advance", methods=["POST"])
def advance_phase():
    engine = _get_engine()
    result = engine.advance_phase()
    # Auto-save after each phase
    save_game(engine.state, "autosave", saves_dir=_get_saves_dir())
    return jsonify(result)


@app.route("/api/game/input", methods=["POST"])
def process_input():
    data = request.json or {}
    engine = _get_engine()
    result = engine.process_input(data)
    save_game(engine.state, "autosave", saves_dir=_get_saves_dir())
    return jsonify(result)


@app.route("/api/game/undo", methods=["POST"])
def undo():
    engine = _get_engine()
    result = engine.undo()
    return jsonify(result)


@app.route("/api/game/mode", methods=["POST"])
def set_mode():
    data = request.json or {}
    mode = data.get("mode", "full")
    from game.models import GameMode

    engine = _get_engine()
    engine.state.mode = GameMode(mode)
    return jsonify({"status": "ok", "mode": mode})


@app.route("/api/game/language", methods=["POST"])
def set_language():
    data = request.json or {}
    lang = data.get("language", "en")
    engine = _get_engine()
    engine.state.language = lang
    return jsonify({"status": "ok", "language": lang})


# ─── Quick mode API ────────────────────────────────────────────────────────


@app.route("/api/game/quick/draw", methods=["POST"])
def quick_draw():
    engine = _get_engine()
    result = engine.quick_draw()
    return jsonify(result)


@app.route("/api/game/quick/track", methods=["POST"])
def quick_track():
    data = request.json or {}
    engine = _get_engine()
    result = engine.quick_update_track(
        data.get("track", ""),
        data.get("value", 0),
    )
    return jsonify(result)


# ─── Save/Load API ─────────────────────────────────────────────────────────


@app.route("/api/game/save", methods=["POST"])
def save():
    data = request.json or {}
    slot = data.get("slot_name", "manual_save")
    engine = _get_engine()
    result = save_game(engine.state, slot, saves_dir=_get_saves_dir())
    return jsonify(result)


@app.route("/api/game/load", methods=["POST"])
def load():
    data = request.json or {}
    slot = data.get("slot_name", "autosave")
    engine = _get_engine()
    state = load_game(slot, saves_dir=_get_saves_dir())
    if state:
        engine.state = state
        return jsonify({"status": "ok", "message": f"Game loaded from '{slot}'."})
    return jsonify({"status": "error", "message": f"Save '{slot}' not found."})


@app.route("/api/game/saves")
def get_saves():
    return jsonify(list_saves(saves_dir=_get_saves_dir()))


@app.route("/api/game/saves/<slot_name>", methods=["DELETE"])
def remove_save(slot_name):
    result = delete_save(slot_name, saves_dir=_get_saves_dir())
    return jsonify(result)


# ─── Download / Upload Save ────────────────────────────────────────────


@app.route("/api/game/download")
def download_save():
    """Download the current game state as a JSON file."""
    engine = _get_engine()
    save_data = {
        "meta": {
            "slot_name": "download",
            "timestamp": time.time(),
            "turn": engine.state.turn_number,
            "phase": engine.state.phase.value,
        },
        "state": _serialize_full_state(engine.state),
    }
    buf = io.BytesIO()
    buf.write(json.dumps(save_data, indent=2).encode("utf-8"))
    buf.seek(0)
    filename = f"thechain_turn{engine.state.turn_number}.json"
    try:
        return send_file(
            buf, mimetype="application/json", as_attachment=True, download_name=filename
        )
    except TypeError:
        # Flask < 2.0 uses attachment_filename instead of download_name
        return send_file(
            buf,
            mimetype="application/json",
            as_attachment=True,
            attachment_filename=filename,
        )


@app.route("/api/game/upload", methods=["POST"])
def upload_save():
    """Upload a previously downloaded save file and restore it."""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file provided."}), 400
    f = request.files["file"]
    try:
        save_data = json.load(f)
        state = _deserialize_full_state(save_data["state"])
        engine = _get_engine()
        engine.state = state
        save_game(engine.state, "autosave", saves_dir=_get_saves_dir())
        return jsonify({"status": "ok", "message": "Save uploaded and restored."})
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return jsonify({"status": "error", "message": f"Invalid save file: {e}"}), 400


# ─── Card images ───────────────────────────────────────────────────────────


@app.route("/static/cards/<path:filename>")
def card_image(filename):
    return send_from_directory(os.path.join(app.static_folder, "cards"), filename)


@app.route("/static/boards/<path:filename>")
def board_image(filename):
    return send_from_directory(os.path.join(app.static_folder, "boards"), filename)


# ─── Run ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"Starting server at http://{host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)
