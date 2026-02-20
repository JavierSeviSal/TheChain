"""Save/load game state to/from JSON files."""

from __future__ import annotations

import os
import json
import time
from datetime import datetime
from typing import Optional

from .models import (
    GameState,
    GamePhase,
    GameMode,
    CompetitionLevel,
    CardType,
    Card,
    CardFront,
    CardBack,
    ActionSlot,
    CleanupAction,
    CompetitionEffect,
    Deck,
    Tracks,
    TrackMarker,
    Inventory,
    MarketeerSlot,
    FoodItem,
)
from .cards import create_all_decks

SAVES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "saves"
)


def ensure_saves_dir():
    os.makedirs(SAVES_DIR, exist_ok=True)


def save_game(state: GameState, slot_name: str = "autosave") -> dict:
    """Save the full game state to a JSON file."""
    ensure_saves_dir()

    save_data = {
        "meta": {
            "slot_name": slot_name,
            "timestamp": time.time(),
            "date": datetime.now().isoformat(),
            "turn": state.turn_number,
            "phase": state.phase.value,
        },
        "state": _serialize_full_state(state),
    }

    filepath = os.path.join(SAVES_DIR, f"{slot_name}.json")
    with open(filepath, "w") as f:
        json.dump(save_data, f, indent=2)

    return {
        "status": "ok",
        "message": f"Game saved to '{slot_name}'.",
        "filepath": filepath,
    }


def load_game(slot_name: str) -> Optional[GameState]:
    """Load game state from a JSON file."""
    ensure_saves_dir()
    filepath = os.path.join(SAVES_DIR, f"{slot_name}.json")

    if not os.path.exists(filepath):
        return None

    with open(filepath, "r") as f:
        save_data = json.load(f)

    return _deserialize_full_state(save_data["state"])


def list_saves() -> list[dict]:
    """List all saved games with metadata."""
    ensure_saves_dir()
    saves = []
    for filename in sorted(os.listdir(SAVES_DIR)):
        if filename.endswith(".json"):
            filepath = os.path.join(SAVES_DIR, filename)
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                meta = data.get("meta", {})
                saves.append(
                    {
                        "slot_name": meta.get("slot_name", filename[:-5]),
                        "date": meta.get("date", ""),
                        "turn": meta.get("turn", 0),
                        "phase": meta.get("phase", ""),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                saves.append(
                    {"slot_name": filename[:-5], "date": "corrupted", "turn": 0}
                )
    return saves


def delete_save(slot_name: str) -> dict:
    """Delete a saved game."""
    ensure_saves_dir()
    filepath = os.path.join(SAVES_DIR, f"{slot_name}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
        return {"status": "ok", "message": f"Save '{slot_name}' deleted."}
    return {"status": "error", "message": f"Save '{slot_name}' not found."}


# ─── Serialization ────────────────────────────────────────────────────────


def _serialize_full_state(state: GameState) -> dict:
    """Serialize complete game state including full deck contents."""
    return {
        "turn_number": state.turn_number,
        "phase": state.phase.value,
        "mode": state.mode.value,
        "language": state.language,
        "modules": state.modules,
        "optional_rules": state.optional_rules,
        "action_deck_cards": [_serialize_card(c) for c in state.action_deck.cards],
        "discard_pile_cards": [_serialize_card(c) for c in state.discard_pile.cards],
        "warm_deck_cards": [_serialize_card(c) for c in state.warm_deck.cards],
        "cool_deck_cards": [_serialize_card(c) for c in state.cool_deck.cards],
        "tracks": {
            "recruit_train": state.tracks.recruit_train.position,
            "price_distance": state.tracks.price_distance.position,
            "waitresses": state.tracks.waitresses.position,
            "competition": state.tracks.competition.value,
        },
        "inventory": {k: v for k, v in state.inventory.items.items()},
        "marketeer_slots": [
            {
                "slot": s.slot_number,
                "marketeer": s.marketeer,
                "is_busy": s.is_busy,
                "market_item": s.market_item,
                "campaign_number": s.campaign_number,
                "campaigns_left": s.campaigns_left,
                "placed_turn": s.placed_turn,
            }
            for s in state.marketeer_slots
        ],
        "mass_marketeer": state.mass_marketeer,
        "employee_pile": state.employee_pile.copy(),
        "milestones_claimed": state.milestones_claimed.copy(),
        "milestones_unavailable": state.milestones_unavailable.copy(),
        "pending_milestone_checks": state.pending_milestone_checks.copy(),
        "phase_before_milestone": state.phase_before_milestone,
        "pending_employee_checks": [c.copy() for c in state.pending_employee_checks],
        "phase_before_employee_check": state.phase_before_employee_check,
        "pending_competition_actions": [
            a.copy() for a in state.pending_competition_actions
        ],
        "phase_after_competition": state.phase_after_competition,
        "restaurants": [r.copy() for r in state.restaurants],
        "max_restaurants": state.max_restaurants,
        "current_front_card": state.current_front_card,
        "current_back_card": state.current_back_card,
        "current_competition_card": state.current_competition_card,
        "bank_breaks": state.bank_breaks,
        "bank_reserve_card": state.bank_reserve_card,
        "action_log": state.action_log[-100:],
        "is_first_turn": state.is_first_turn,
        "pending_stars": state.pending_stars,
        "chain_cash_this_turn": state.chain_cash_this_turn,
        "chain_total_cash": state.chain_total_cash,
        "bonus_cash_multiplier": state.bonus_cash_multiplier,
        "no_driveins_this_turn": state.no_driveins_this_turn,
        "chain_movie_star": state.chain_movie_star,
        "turn_order": state.turn_order,
        "display_phase": state.display_phase,
        "pending_input": state.pending_input,
        "next_phase_after_input": state.next_phase_after_input,
        "cards_drawn_this_cycle": state.cards_drawn_this_cycle,
        "deck_cycles": state.deck_cycles,
        "total_cards_drawn": state.total_cards_drawn,
    }


def _serialize_card(card: Card) -> dict:
    """Serialize a card to a minimal representation for save files."""
    return {
        "id": card.id,
        "card_type": card.card_type.value,
        "card_number": card.card_number,
    }


def _deserialize_full_state(data: dict) -> GameState:
    """Rebuild full GameState from serialized data."""
    state = GameState()
    state.turn_number = data.get("turn_number", 0)
    # Handle legacy phase name migration
    phase_value = data.get("phase", "setup")
    if phase_value == "marketing":
        phase_value = "initiate_marketing"  # Renamed phase
    state.phase = GamePhase(phase_value)
    state.mode = GameMode(data.get("mode", "full"))
    state.language = data.get("language", "en")
    saved_modules = data.get("modules", state.modules)
    # Strip legacy module keys that are now always-on core items
    for legacy_key in ("beer", "lemonade", "softdrink"):
        saved_modules.pop(legacy_key, None)
    state.modules = saved_modules
    state.optional_rules = data.get("optional_rules", state.optional_rules)

    # Rebuild decks from card references
    action_deck, warm_deck, cool_deck = create_all_decks()
    all_cards = {}
    for c in action_deck.cards + warm_deck.cards + cool_deck.cards:
        all_cards[(c.card_type.value, c.card_number)] = c

    # Restore deck order
    state.action_deck = Deck(name="Action Deck")
    for cd in data.get("action_deck_cards", []):
        key = (cd["card_type"], cd["card_number"])
        if key in all_cards:
            state.action_deck.cards.append(all_cards[key])

    state.discard_pile = Deck(name="Discard Pile")
    for cd in data.get("discard_pile_cards", []):
        key = (cd["card_type"], cd["card_number"])
        if key in all_cards:
            state.discard_pile.cards.append(all_cards[key])

    state.warm_deck = Deck(name="Warm Competition")
    for cd in data.get("warm_deck_cards", []):
        key = (cd["card_type"], cd["card_number"])
        if key in all_cards:
            state.warm_deck.cards.append(all_cards[key])

    state.cool_deck = Deck(name="Cool Competition")
    for cd in data.get("cool_deck_cards", []):
        key = (cd["card_type"], cd["card_number"])
        if key in all_cards:
            state.cool_deck.cards.append(all_cards[key])

    # Restore tracks
    tracks_data = data.get("tracks", {})
    rt_pos = tracks_data.get("recruit_train", 1)
    state.tracks.recruit_train.position = max(
        state.tracks.recruit_train.min_pos,
        min(state.tracks.recruit_train.max_pos, rt_pos),
    )
    state.tracks.price_distance.position = tracks_data.get("price_distance", 10)
    state.tracks.waitresses.position = tracks_data.get("waitresses", 0)
    state.tracks.competition = CompetitionLevel(tracks_data.get("competition", 2))

    # Restore inventory
    inv_data = data.get("inventory", {})
    for item, vals in inv_data.items():
        if item in state.inventory.items:
            if isinstance(vals, dict):
                # Migration: old format had {top, bottom}, new is single int
                state.inventory.items[item] = vals.get(
                    "count", vals.get("top", 0) + vals.get("bottom", 0)
                )
            else:
                state.inventory.items[item] = vals

    # Restore marketeers
    slots_data = data.get("marketeer_slots", [])
    for i, sd in enumerate(slots_data):
        if i < len(state.marketeer_slots):
            state.marketeer_slots[i].marketeer = sd.get("marketeer")
            state.marketeer_slots[i].is_busy = sd.get("is_busy", False)
            state.marketeer_slots[i].market_item = sd.get("market_item")
            state.marketeer_slots[i].campaign_number = sd.get("campaign_number")
            state.marketeer_slots[i].campaigns_left = sd.get("campaigns_left")
            state.marketeer_slots[i].placed_turn = sd.get("placed_turn")

    state.mass_marketeer = data.get("mass_marketeer", False)
    state.employee_pile = data.get("employee_pile", [])
    state.milestones_claimed = data.get("milestones_claimed", [])
    state.milestones_unavailable = data.get("milestones_unavailable", [])
    state.pending_milestone_checks = data.get("pending_milestone_checks", [])
    state.phase_before_milestone = data.get("phase_before_milestone")
    state.pending_employee_checks = data.get("pending_employee_checks", [])
    state.phase_before_employee_check = data.get("phase_before_employee_check")
    state.pending_competition_actions = data.get("pending_competition_actions", [])
    state.phase_after_competition = data.get("phase_after_competition")
    state.restaurants = data.get("restaurants", [])
    state.max_restaurants = data.get("max_restaurants", 3)
    state.current_front_card = data.get("current_front_card")
    state.current_back_card = data.get("current_back_card")
    state.current_competition_card = data.get("current_competition_card")
    state.bank_breaks = data.get("bank_breaks", 0)
    state.bank_reserve_card = data.get("bank_reserve_card", None)
    state.action_log = data.get("action_log", [])
    state.is_first_turn = data.get("is_first_turn", False)
    state.pending_stars = data.get("pending_stars", [])
    state.chain_cash_this_turn = data.get("chain_cash_this_turn", 0)
    state.chain_total_cash = data.get("chain_total_cash", 0)
    state.bonus_cash_multiplier = data.get("bonus_cash_multiplier", 1.0)
    state.no_driveins_this_turn = data.get("no_driveins_this_turn", False)
    state.chain_movie_star = data.get("chain_movie_star", None)
    state.turn_order = data.get("turn_order", None)
    state.display_phase = data.get("display_phase", None)
    state.pending_input = data.get("pending_input")
    state.next_phase_after_input = data.get("next_phase_after_input")
    state.cards_drawn_this_cycle = data.get("cards_drawn_this_cycle", 0)
    state.deck_cycles = data.get("deck_cycles", 0)
    state.total_cards_drawn = data.get("total_cards_drawn", 0)

    return state
