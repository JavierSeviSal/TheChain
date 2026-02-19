"""Card loader for The Chain automa.

Loads all 44 card definitions from cards.yaml:
- 20 Action Deck cards (front: RECRUIT & TRAIN, back: GET FOOD & DRINKS / CLEANUP)
- 12 Warm Competition cards
- 12 Cool Competition cards
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import (
    Card,
    CardType,
    CardFront,
    CardBack,
    ActionSlot,
    CleanupAction,
    CompetitionEffect,
    Deck,
)

_CARDS_YAML = Path(__file__).parent / "cards.yaml"

# Cleanup action types in the order they appear in the compact [a, b, c, d, e] list
_CLEANUP_KEYS = [
    "get_kimchi",
    "move_distance",
    "move_waitress",
    "inventory_drop",
    "move_recruit_train",
]


# ─── YAML → model converters ────────────────────────────────────────────────


def _parse_action_slot(slot_num: int, raw: dict) -> ActionSlot:
    """Convert a YAML action dict into an ActionSlot."""
    return ActionSlot(
        slot_number=slot_num,
        action_type=raw["type"],
        target=str(raw["target"]),
        requires_module=raw.get("module"),
        fallback_food=raw.get("fallback"),
        star=raw.get("star"),
    )


def _parse_front(raw: dict) -> CardFront:
    """Convert a YAML front dict into a CardFront."""
    actions = [_parse_action_slot(i + 1, a) for i, a in enumerate(raw["actions"])]
    return CardFront(
        actions=actions,
        market_item=raw.get("market"),
    )


def _parse_back(raw: dict) -> CardBack:
    """Convert a YAML back dict into a CardBack."""
    cleanup_values = raw.get("cleanup", [0, 0, 0, 0, 0])
    cleanup_actions = [
        CleanupAction(action_type=k, value=int(v))
        for k, v in zip(_CLEANUP_KEYS, cleanup_values)
    ]
    develop = raw.get("develop") or {}
    lobby = raw.get("lobby") or {}
    fi = raw.get("food_item") or {}
    return CardBack(
        demand_type=raw.get("demand", "most_demand"),
        food_items=raw.get("foods", []),
        multiplier=raw.get("multiply", 1),
        cleanup_actions=cleanup_actions,
        food_item=fi.get("item"),
        food_item_module=fi.get("module"),
        food_item_fallback=fi.get("fallback"),
        food_item_multiply=fi.get("multiply", 1),
        develop_type=develop.get("type"),
        develop_house=str(develop["house"]) if "house" in develop else None,
        lobby_type=lobby.get("type"),
        lobby_house=str(lobby["house"]) if "house" in lobby else None,
    )


def _parse_action_card(raw: dict) -> Card:
    """Convert a YAML action card entry into a Card."""
    num = raw["number"]
    mt = raw.get("map_tiles", {})
    return Card(
        id=num,
        card_type=CardType.ACTION,
        card_number=num,
        front=_parse_front(raw["front"]),
        back=_parse_back(raw["back"]),
        map_tiles={
            "expand_chain": mt.get("expand_chain", 1),
            "market": mt.get("market", 1),
            "coffee_shop": mt.get("coffee_shop", 1),
            "develop_lobby": mt.get("develop_lobby", 1),
        },
    )


def _parse_warm_card(raw: dict) -> Card:
    """Convert a YAML warm competition card entry into a Card."""
    num = raw["number"]
    return Card(
        id=100 + num,
        card_type=CardType.WARM,
        card_number=num,
        competition_effect=CompetitionEffect(
            effect_type=raw["effect"],
            food_adjustments=raw.get("food_adj", []),
            track_adjustments=raw.get("track_adj", []),
            inventory_boost=raw.get("boost", False),
            map_tile=raw.get("map_tile", 1),
        ),
    )


def _parse_cool_card(raw: dict) -> Card:
    """Convert a YAML cool competition card entry into a Card."""
    num = raw["number"]
    return Card(
        id=200 + num,
        card_type=CardType.COOL,
        card_number=num,
        competition_effect=CompetitionEffect(
            effect_type=raw["effect"],
            inventory_loss_items=raw.get("loss_items", []),
            track_adjustments=raw.get("track_adj", []),
            inventory_drop=raw.get("drop", False),
            map_tile=raw.get("map_tile", 1),
        ),
    )


# ─── Public API ──────────────────────────────────────────────────────────────


def _load_yaml(path: Path | None = None) -> dict[str, Any]:
    """Load and return the parsed YAML card data."""
    p = path or _CARDS_YAML
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_action_deck(data: dict | None = None) -> list[Card]:
    """Build all 20 Action Deck cards from YAML data."""
    if data is None:
        data = _load_yaml()
    return [_parse_action_card(raw) for raw in data["action_cards"]]


def build_warm_deck(data: dict | None = None) -> list[Card]:
    """Build all 12 Warm (red) Competition cards from YAML data."""
    if data is None:
        data = _load_yaml()
    return [_parse_warm_card(raw) for raw in data["warm_cards"]]


def build_cool_deck(data: dict | None = None) -> list[Card]:
    """Build all 12 Cool (green) Competition cards from YAML data."""
    if data is None:
        data = _load_yaml()
    return [_parse_cool_card(raw) for raw in data["cool_cards"]]


def create_all_decks(yaml_path: Path | None = None) -> tuple[Deck, Deck, Deck]:
    """Create and return (action_deck, warm_deck, cool_deck).

    Optionally accepts a custom path to a YAML card definition file.
    """
    data = _load_yaml(yaml_path)

    action_deck = Deck(cards=build_action_deck(data), name="Action Deck")
    warm_deck = Deck(cards=build_warm_deck(data), name="Warm Competition")
    cool_deck = Deck(cards=build_cool_deck(data), name="Cool Competition")

    return action_deck, warm_deck, cool_deck
