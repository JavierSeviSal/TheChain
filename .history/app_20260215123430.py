"""Flask application for The Chain automa companion."""

import os
from flask import Flask, jsonify, request, send_from_directory, render_template

from game.engine import GameEngine
from game.save_manager import save_game, load_game, list_saves, delete_save

app = Flask(__name__, static_folder="static", template_folder="templates")

# Global game engine instance
engine = GameEngine()


# ─── Pages ─────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


# ─── Game API ──────────────────────────────────────────────────────────────


@app.route("/api/game/new", methods=["POST"])
def new_game():
    data = request.json or {}
    result = engine.new_game(
        modules=data.get("modules"),
        optional_rules=data.get("optional_rules"),
        mode=data.get("mode", "full"),
        language=data.get("language", "en"),
    )
    return jsonify(result)


@app.route("/api/game/state")
def get_state():
    return jsonify(engine.state.to_dict())


@app.route("/api/game/advance", methods=["POST"])
def advance_phase():
    result = engine.advance_phase()
    # Auto-save after each phase
    save_game(engine.state, "autosave")
    return jsonify(result)


@app.route("/api/game/input", methods=["POST"])
def process_input():
    data = request.json or {}
    result = engine.process_input(data)
    save_game(engine.state, "autosave")
    return jsonify(result)


@app.route("/api/game/undo", methods=["POST"])
def undo():
    result = engine.undo()
    return jsonify(result)


@app.route("/api/game/mode", methods=["POST"])
def set_mode():
    data = request.json or {}
    mode = data.get("mode", "full")
    from game.models import GameMode

    engine.state.mode = GameMode(mode)
    return jsonify({"status": "ok", "mode": mode})


@app.route("/api/game/language", methods=["POST"])
def set_language():
    data = request.json or {}
    lang = data.get("language", "en")
    engine.state.language = lang
    return jsonify({"status": "ok", "language": lang})


# ─── Quick mode API ────────────────────────────────────────────────────────


@app.route("/api/game/quick/draw", methods=["POST"])
def quick_draw():
    result = engine.quick_draw()
    return jsonify(result)


@app.route("/api/game/quick/track", methods=["POST"])
def quick_track():
    data = request.json or {}
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
    result = save_game(engine.state, slot)
    return jsonify(result)


@app.route("/api/game/load", methods=["POST"])
def load():
    data = request.json or {}
    slot = data.get("slot_name", "autosave")
    state = load_game(slot)
    if state:
        engine.state = state
        return jsonify({"status": "ok", "message": f"Game loaded from '{slot}'."})
    return jsonify({"status": "error", "message": f"Save '{slot}' not found."})


@app.route("/api/game/saves")
def get_saves():
    return jsonify(list_saves())


@app.route("/api/game/saves/<slot_name>", methods=["DELETE"])
def remove_save(slot_name):
    result = delete_save(slot_name)
    return jsonify(result)


# ─── Card images ───────────────────────────────────────────────────────────


@app.route("/static/cards/<path:filename>")
def card_image(filename):
    return send_from_directory(os.path.join(app.static_folder, "cards"), filename)


@app.route("/static/boards/<path:filename>")
def board_image(filename):
    return send_from_directory(os.path.join(app.static_folder, "boards"), filename)


# ─── Run ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="192.168.1.100", port=5000, debug=True)
