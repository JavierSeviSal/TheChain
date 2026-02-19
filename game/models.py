"""Data models for The Chain automa."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import random
import copy
import json


# ─── Enums ───────────────────────────────────────────────────────────────────


class CompetitionLevel(Enum):
    COLD = 0
    COOL = 1
    NEUTRAL = 2
    WARM = 3
    HOT = 4

    def label(self) -> str:
        return self.name.capitalize()

    def move_up(self) -> "CompetitionLevel":
        return CompetitionLevel(min(self.value + 1, 4))

    def move_down(self) -> "CompetitionLevel":
        return CompetitionLevel(max(self.value - 1, 0))


class CardType(Enum):
    ACTION = "action"
    WARM = "warm"
    COOL = "cool"


class GamePhase(Enum):
    SETUP = "setup"
    RESTRUCTURING = "restructuring"
    ORDER_OF_BUSINESS = "order_of_business"
    RECRUIT_TRAIN = "recruit_train"
    INITIATE_MARKETING = "initiate_marketing"
    GET_FOOD = "get_food"
    DEVELOP = "develop"
    LOBBY = "lobby"
    EXPAND_CHAIN = "expand_chain"
    DINNERTIME = "dinnertime"
    PAYDAY = "payday"
    MARKETING_CAMPAIGNS = "marketing_campaigns"
    CLEANUP = "cleanup"
    GAME_OVER = "game_over"
    # Sub-phases for player input
    WAITING_FOR_INPUT = "waiting_for_input"


class GameMode(Enum):
    FULL = "full"
    QUICK = "quick"


class DemandType(Enum):
    MOST = "most_demand"
    ALL = "all_demand"


# Core items are always available; module items require expansion toggle
CORE_FOOD_ITEMS = {"burger", "pizza", "beer", "lemonade", "softdrink"}


class FoodItem(Enum):
    BURGER = "burger"
    PIZZA = "pizza"
    BEER = "beer"
    LEMONADE = "lemonade"
    SOFTDRINK = "softdrink"
    SUSHI = "sushi"
    NOODLE = "noodle"
    COFFEE = "coffee"
    KIMCHI = "kimchi"

    def label(self) -> str:
        return self.name.capitalize()

    @property
    def is_core(self) -> bool:
        return self.value in CORE_FOOD_ITEMS


# ─── Card model ──────────────────────────────────────────────────────────────


@dataclass
class ActionSlot:
    """One of the 4 action slots on an Action Deck card front (RECRUIT & TRAIN side)."""

    slot_number: int  # 1 (top) to 4 (bottom)
    action_type: str  # "recruit_marketeer", "recruit_employee", "move_distance",
    # "move_waitress", "claim_milestone", "get_food"
    target: str  # e.g., "Zeppelin Pilot", "Burger Chef", "-3", "+1", milestone name
    fallback_food: Optional[str | list] = (
        None  # Food item(s) if action can't be taken (module not in use)
    )
    requires_module: Optional[str] = None  # Module that must be active for this action
    star: Optional[str] = (
        None  # Star type on this slot: "expand_chain", "coffee_shop", "develop", "lobby", "garden"
    )


@dataclass
class CardFront:
    """RECRUIT & TRAIN side of an Action Deck card."""

    actions: list[ActionSlot] = field(default_factory=list)  # 4 action slots
    market_item: Optional[str] = None  # Food/drink shown on lower-left corner


@dataclass
class CleanupAction:
    """One cleanup action on the back of an Action Deck card."""

    action_type: str  # "get_kimchi", "move_distance", "move_waitress", "inventory_drop", "move_recruit_train"
    value: int = 0  # +/- amount


@dataclass
class CardBack:
    """GET FOOD & DRINKS / CLEANUP side of an Action Deck card."""

    demand_type: str = "most_demand"  # "most_demand" or "all_demand"
    food_items: list[str] = field(
        default_factory=list
    )  # Specific food items or empty for demand-based
    multiplier: int = 1  # How many units to add (×1, ×2, etc.)
    cleanup_actions: list[CleanupAction] = field(default_factory=list)
    food_item: Optional[str] = None  # Right-box food/drink item
    food_item_module: Optional[str] = None  # Required module for food_item
    food_item_fallback: Optional[str] = None  # Fallback if module inactive
    food_item_multiply: int = 1  # Right-box multiplier (1 or 2)
    develop_type: Optional[str] = None  # "house" or "garden"
    develop_house: Optional[str] = None  # House number (e.g. "19", "2")
    lobby_type: Optional[str] = None  # "road" or "park"
    lobby_house: Optional[str] = None  # House number for park (e.g. "4", "pi")


@dataclass
class CompetitionEffect:
    """Effect of a Competition Card."""

    effect_type: str  # "expand_chain", "coffee_shop_or_expand", "bonus_cash",
    # "no_driveins", "fire_employees", "pay_per_employee"
    food_adjustments: list[dict] = field(
        default_factory=list
    )  # [{item, amount, module?, fallback?}]
    track_adjustments: list[dict] = field(default_factory=list)  # [{type, value}]
    inventory_boost: bool = False
    inventory_drop: bool = False
    inventory_loss_items: list[str] = field(default_factory=list)
    map_tile: int = 1


@dataclass
class Card:
    """A single card in the game."""

    id: int
    card_type: CardType  # ACTION, WARM, COOL
    card_number: (
        int  # Number printed on the card (1-20 for action, 1-12 for competition)
    )

    # Action deck cards have front + back
    front: Optional[CardFront] = None
    back: Optional[CardBack] = None

    # Map tiles for action deck cards (expand_chain, market, coffee_shop, develop_lobby)
    map_tiles: dict = field(default_factory=dict)

    # Competition cards have a single effect
    competition_effect: Optional[CompetitionEffect] = None

    @property
    def image_front(self) -> str:
        return f"/static/cards/{self.card_type.value}_{self.card_number:02d}_front.png"

    @property
    def image_back(self) -> str:
        return f"/static/cards/{self.card_type.value}_{self.card_number:02d}_back.png"

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "card_type": self.card_type.value,
            "card_number": self.card_number,
            "image_front": self.image_front,
            "image_back": self.image_back,
            "map_tiles": self.map_tiles,
        }
        if self.front:
            d["front"] = {
                "actions": [
                    {
                        "slot": a.slot_number,
                        "type": a.action_type,
                        "target": a.target,
                        "fallback_food": a.fallback_food,
                        "requires_module": a.requires_module,
                        "star": a.star,
                    }
                    for a in self.front.actions
                ],
                "market_item": self.front.market_item,
            }
        if self.back:
            d["back"] = {
                "demand_type": self.back.demand_type,
                "food_items": self.back.food_items,
                "multiplier": self.back.multiplier,
                "cleanup_actions": [
                    {"type": c.action_type, "value": c.value}
                    for c in self.back.cleanup_actions
                ],
                "develop_type": self.back.develop_type,
                "develop_house": self.back.develop_house,
                "lobby_type": self.back.lobby_type,
                "lobby_house": self.back.lobby_house,
                "food_item": self.back.food_item,
                "food_item_module": self.back.food_item_module,
                "food_item_fallback": self.back.food_item_fallback,
                "food_item_multiply": self.back.food_item_multiply,
            }
        if self.competition_effect:
            d["competition_effect"] = {
                "type": self.competition_effect.effect_type,
                "food_adjustments": self.competition_effect.food_adjustments,
                "track_adjustments": self.competition_effect.track_adjustments,
                "inventory_boost": self.competition_effect.inventory_boost,
                "inventory_drop": self.competition_effect.inventory_drop,
                "inventory_loss_items": self.competition_effect.inventory_loss_items,
                "map_tile": self.competition_effect.map_tile,
            }
        return d


# ─── Deck ────────────────────────────────────────────────────────────────────


@dataclass
class Deck:
    """A deck of cards with draw, place-on-top, place-under, shuffle operations."""

    cards: list[Card] = field(default_factory=list)
    name: str = ""

    def shuffle(self):
        random.shuffle(self.cards)

    def draw(self) -> Optional[Card]:
        if self.cards:
            return self.cards.pop(0)
        return None

    def peek(self) -> Optional[Card]:
        return self.cards[0] if self.cards else None

    def place_on_top(self, card: Card):
        self.cards.insert(0, card)

    def place_under(self, card: Card):
        self.cards.append(card)

    def is_empty(self) -> bool:
        return len(self.cards) == 0

    def size(self) -> int:
        return len(self.cards)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "size": self.size(),
            "top_card": self.peek().to_dict() if self.peek() else None,
        }

    def to_snapshot_dict(self) -> dict:
        """Full serialization for undo snapshots — includes card list."""
        return {
            "name": self.name,
            "size": self.size(),
            "top_card": self.peek().to_dict() if self.peek() else None,
            "cards": [
                {"card_type": c.card_type.value, "card_number": c.card_number}
                for c in self.cards
            ],
        }


# ─── Tracks ──────────────────────────────────────────────────────────────────

RECRUIT_TRAIN_TRACK = {
    # Position -> (open_slots, food_amount)
    # The physical board has 4 rows (bottom to top):
    #   Pos 1 (start): 1 open slot,  green box = 2
    #   Pos 2:         2 open slots, green box = 3
    #   ── SHUFFLE boundary ──
    #   Pos 3:         3 open slots, green box = 4
    #   Pos 4 (top):   4 open slots, green box = 5
    1: {"open_slots": 1, "food_amount": 2},
    2: {"open_slots": 2, "food_amount": 3},
    3: {"open_slots": 3, "food_amount": 4},
    4: {"open_slots": 4, "food_amount": 5},
}

# Crossing between position 2 and 3 triggers an Action Deck shuffle
SHUFFLE_BOUNDARY = (2, 3)


@dataclass
class TrackMarker:
    """A single track marker with a current position."""

    name: str
    position: int
    min_pos: int
    max_pos: int
    labels: dict = field(default_factory=dict)  # position -> label string

    def move(self, delta: int) -> tuple[int, int, bool]:
        """Move marker by delta. Returns (old_pos, new_pos, crossed_shuffle)."""
        old = self.position
        new = max(self.min_pos, min(self.max_pos, self.position + delta))
        # Check if we crossed the shuffle boundary
        crossed = False
        if self.name == "recruit_train" and old != new:
            lo, hi = SHUFFLE_BOUNDARY
            # Crossed if old and new are on different sides of the boundary
            if (old <= lo and new >= hi) or (old >= hi and new <= lo):
                crossed = True
        self.position = new
        return old, new, crossed

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "position": self.position,
            "min": self.min_pos,
            "max": self.max_pos,
        }
        if self.labels:
            d["labels"] = self.labels
            d["current_label"] = self.labels.get(self.position, str(self.position))
        return d


@dataclass
class Tracks:
    """All track markers for The Chain."""

    recruit_train: TrackMarker = field(
        default_factory=lambda: TrackMarker(
            name="recruit_train",
            position=1,
            min_pos=1,
            max_pos=4,
            labels={
                1: "1 Open Slot (food ×2)",
                2: "2 Open Slots (food ×3)",
                3: "3 Open Slots (food ×4)",
                4: "4 Open Slots (food ×5)",
            },
        )
    )
    price_distance: TrackMarker = field(
        default_factory=lambda: TrackMarker(
            name="price_distance",
            position=10,
            min_pos=6,
            max_pos=10,
        )
    )
    waitresses: TrackMarker = field(
        default_factory=lambda: TrackMarker(
            name="waitresses",
            position=0,
            min_pos=0,
            max_pos=4,
        )
    )
    competition: CompetitionLevel = field(
        default_factory=lambda: CompetitionLevel.NEUTRAL
    )

    def get_open_slots(self) -> int:
        return RECRUIT_TRAIN_TRACK[self.recruit_train.position]["open_slots"]

    def get_food_amount(self) -> int:
        return RECRUIT_TRAIN_TRACK[self.recruit_train.position]["food_amount"]

    def move_competition(self, delta: int) -> CompetitionLevel:
        """Move competition marker. Positive=toward HOT, Negative=toward COLD."""
        if delta > 0:
            for _ in range(delta):
                self.competition = self.competition.move_up()
        elif delta < 0:
            for _ in range(abs(delta)):
                self.competition = self.competition.move_down()
        return self.competition

    def to_dict(self) -> dict:
        return {
            "recruit_train": self.recruit_train.to_dict(),
            "price_distance": self.price_distance.to_dict(),
            "waitresses": self.waitresses.to_dict(),
            "competition": {
                "level": self.competition.value,
                "label": self.competition.label(),
            },
            "open_slots": self.get_open_slots(),
            "food_amount": self.get_food_amount(),
        }


# ─── Inventory ───────────────────────────────────────────────────────────────


@dataclass
class Inventory:
    """Food & drink inventory — Fridge & Freezer mechanic.

    Each item is tracked as a single count 0-10.
    The physical mat has two rows of 5 slots:
      Bottom row: positions 1-5
      Top row:    positions 6-10
    Inventory Drop (-5): items on the top row (count ≥ 6) lose 5.
    Inventory Boost (+5): items on the bottom row (count 1-5) gain 5.
    Cap: max 10 per item (coffee is exempt).
    """

    items: dict = field(default_factory=lambda: {item.value: 0 for item in FoodItem})
    MAX_PER_ITEM = 10

    def add(self, item: str, amount: int):
        """Add amount, capped at MAX_PER_ITEM."""
        if item in self.items:
            self.items[item] = min(self.items[item] + amount, self.MAX_PER_ITEM)

    def remove(self, item: str, amount: int) -> int:
        """Remove up to amount. Returns amount actually removed."""
        if item not in self.items:
            return 0
        removed = min(self.items[item], amount)
        self.items[item] -= removed
        return removed

    def total(self, item: str) -> int:
        return self.items.get(item, 0)

    def inventory_drop(self) -> list[str]:
        """Cleanup action: items on the top row (≥ 6) drop by 5.

        Returns list of description strings for items that dropped.
        """
        msgs = []
        for item, count in self.items.items():
            if count >= 6:
                old = count
                self.items[item] = count - 5
                msgs.append(f"{item}: {old}→{self.items[item]}")
        return msgs

    def inventory_boost(self) -> list[str]:
        """Competition effect: items on the bottom row (1-5) boost by 5.

        Returns list of description strings for items that boosted.
        """
        msgs = []
        for item, count in self.items.items():
            if 1 <= count <= 5:
                old = count
                self.items[item] = count + 5
                msgs.append(f"{item}: {old}→{self.items[item]}")
        return msgs

    def cap_inventory(self) -> list[str]:
        """Enforce max 10 per item (excluding coffee). Returns descriptions."""
        msgs = []
        for item_name, count in self.items.items():
            if count > self.MAX_PER_ITEM and item_name != FoodItem.COFFEE.value:
                old = count
                self.items[item_name] = self.MAX_PER_ITEM
                msgs.append(f"{item_name}: {old}→{self.MAX_PER_ITEM}")
        return msgs

    def clear_item(self, item: str):
        """Remove all of a specific item (cool competition effect)."""
        if item in self.items:
            self.items[item] = 0

    def to_dict(self) -> dict:
        """Serialise for API / UI. Provides row info for display."""
        result = {}
        for item, count in self.items.items():
            top_row = max(0, count - 5) if count > 5 else 0
            bottom_row = min(count, 5)
            result[item] = {
                "count": count,
                "top": top_row,
                "bottom": bottom_row,
                "total": count,
            }
        return result


# ─── Marketeers ──────────────────────────────────────────────────────────────

# Campaign duration by marketeer type (number of marketing campaigns, inclusive).
# -1 means the campaign lasts forever (Rural Marketeer).
MARKETEER_DURATIONS = {
    "Marketing Trainee": 2,
    "Campaign Manager": 3,
    "Brand Manager": 4,
    "Brand Director": 5,
    "Gourmet Food Critic": 3,
    "Rural Marketeer": -1,  # Eternal — stays for the rest of the game
}


@dataclass
class MarketeerSlot:
    slot_number: int  # 1, 2, or 3
    marketeer: Optional[str] = None
    is_busy: bool = False
    market_item: Optional[str] = None  # What food/drink this campaign advertises
    campaign_number: Optional[int] = None  # Player-assigned campaign number
    campaigns_left: Optional[int] = None  # Remaining marketing campaigns before removal
    placed_turn: Optional[int] = None  # Turn when the marketeer started marketing

    def to_dict(self) -> dict:
        return {
            "slot": self.slot_number,
            "marketeer": self.marketeer,
            "is_busy": self.is_busy,
            "market_item": self.market_item,
            "campaign_number": self.campaign_number,
            "campaigns_left": self.campaigns_left,
            "placed_turn": self.placed_turn,
        }


# ─── Milestones ──────────────────────────────────────────────────────────────

MILESTONES = [
    "first_to_lower_prices",
    "first_to_train",
    "first_to_hire_3",
    "first_to_have_waitress",
    "first_to_market",
    "first_to_pay_20_salary",
    "first_cart_operator",
    "first_errand_boy",
    "first_discount_manager",
    "first_to_throw_away",
]


# ─── Game State ──────────────────────────────────────────────────────────────


@dataclass
class GameState:
    """Complete state of a Chain automa game."""

    # Meta
    turn_number: int = 0
    phase: GamePhase = GamePhase.SETUP
    mode: GameMode = GameMode.FULL
    language: str = "en"

    # Active modules/expansions (beer, lemonade, softdrink are core — not toggleable)
    modules: dict = field(
        default_factory=lambda: {
            "coffee": False,
            "kimchi": False,
            "noodle": False,
            "sushi": False,
            "gourmet": False,
            "mass_marketeer": False,
            "rural_marketeer": False,
            "night_shift": False,
            "ketchup": False,
            "fry_chefs": False,
            "movie_stars": False,
            "reserve_prices": False,
            "lobbyists": False,
            "new_districts": False,
            "milestones": False,
        }
    )

    # Optional difficulty rules
    optional_rules: dict = field(
        default_factory=lambda: {
            "hard_choices": False,
            "expand_connections": False,
            "expand_6_restaurants": False,
            "aggressive_setup": False,
            "aggressive_restructuring": False,
        }
    )

    # Decks
    action_deck: Deck = field(default_factory=lambda: Deck(name="Action Deck"))
    discard_pile: Deck = field(default_factory=lambda: Deck(name="Discard Pile"))
    warm_deck: Deck = field(default_factory=lambda: Deck(name="Warm Competition"))
    cool_deck: Deck = field(default_factory=lambda: Deck(name="Cool Competition"))

    # Tracks
    tracks: Tracks = field(default_factory=Tracks)

    # Inventory
    inventory: Inventory = field(default_factory=Inventory)

    # Marketeers
    marketeer_slots: list[MarketeerSlot] = field(
        default_factory=lambda: [MarketeerSlot(1), MarketeerSlot(2), MarketeerSlot(3)]
    )
    mass_marketeer: bool = False

    # Employee pile
    employee_pile: list[str] = field(default_factory=list)

    # Milestones claimed by The Chain
    milestones_claimed: list[str] = field(default_factory=list)

    # Milestones already claimed by the player (not available to The Chain)
    milestones_unavailable: list[str] = field(default_factory=list)

    # Milestones that triggered but need user confirmation
    pending_milestone_checks: list[str] = field(default_factory=list)

    # Phase to restore after milestone confirmation flow completes
    phase_before_milestone: Optional[str] = None

    # Queued competition card actions needing user interaction (demand prompts, restaurant placement)
    pending_competition_actions: list[dict] = field(default_factory=list)
    # Phase to resume after all competition actions are processed
    phase_after_competition: Optional[str] = None

    # Restaurants placed by The Chain
    restaurants: list[dict] = field(default_factory=list)  # [{tile, position, ...}]
    max_restaurants: int = 3

    # Current revealed cards
    current_front_card: Optional[dict] = None  # Serialized card data for current turn
    current_back_card: Optional[dict] = None
    current_competition_card: Optional[dict] = (
        None  # Competition card encountered this turn
    )

    # Bank state
    bank_breaks: int = 0

    # Turn log
    action_log: list[dict] = field(default_factory=list)

    # History for undo
    history: list[str] = field(default_factory=list)  # JSON snapshots

    # Player input pending
    pending_input: Optional[dict] = None  # {type, prompt, options}

    # First turn flag
    is_first_turn: bool = True

    # Pending stars from the current front card (develop, lobby, expand_chain, coffee_shop)
    pending_stars: list = field(default_factory=list)

    # Chain's cash earned this turn (for competition adjustment)
    chain_cash_this_turn: int = 0

    # Cumulative cash earned by the Chain across all turns
    chain_total_cash: int = 0

    # Bonus cash flag (from warm competition)
    bonus_cash_multiplier: float = 1.0

    # No drive-ins flag (from cool competition)
    no_driveins_this_turn: bool = False

    # Movie star tracking (B > C > D; None = no movie star)
    chain_movie_star: Optional[str] = None

    # Turn order decided during Order of Business (informational)
    turn_order: Optional[str] = None  # "chain_first" or "player_first"

    # Display phase: the phase currently shown to the user (not the next queued phase)
    display_phase: Optional[str] = None

    # Deck progress tracking
    cards_drawn_this_cycle: int = 0
    deck_cycles: int = 0
    total_cards_drawn: int = 0

    def reshuffle_deck(self):
        """Combine discard pile back into action deck and shuffle.
        Called when action deck runs out or on R&T track shuffle trigger."""
        if self.discard_pile.cards:
            self.action_deck.cards.extend(self.discard_pile.cards)
            self.discard_pile.cards.clear()
        self.action_deck.shuffle()
        self.deck_cycles += 1
        self.cards_drawn_this_cycle = 0

    def log(self, message: str, category: str = "info"):
        self.action_log.append(
            {
                "turn": self.turn_number,
                "phase": self.phase.value,
                "message": message,
                "category": category,
            }
        )

    def save_snapshot(self):
        """Save current state to history for undo."""
        snapshot = self.to_dict()
        # Replace lightweight deck dicts with full card-list snapshots
        snapshot["action_deck"] = self.action_deck.to_snapshot_dict()
        snapshot["discard_pile"] = self.discard_pile.to_snapshot_dict()
        snapshot["warm_deck"] = self.warm_deck.to_snapshot_dict()
        snapshot["cool_deck"] = self.cool_deck.to_snapshot_dict()
        # Don't include history in the snapshot to avoid nesting
        snapshot.pop("history", None)
        self.history.append(json.dumps(snapshot))
        # Keep last 20 snapshots
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def to_dict(self) -> dict:
        return {
            "turn_number": self.turn_number,
            "phase": self.phase.value,
            "mode": self.mode.value,
            "language": self.language,
            "modules": self.modules,
            "optional_rules": self.optional_rules,
            "action_deck": self.action_deck.to_dict(),
            "discard_pile": self.discard_pile.to_dict(),
            "warm_deck": self.warm_deck.to_dict(),
            "cool_deck": self.cool_deck.to_dict(),
            "tracks": self.tracks.to_dict(),
            "inventory": self.inventory.to_dict(),
            "marketeer_slots": [ms.to_dict() for ms in self.marketeer_slots],
            "mass_marketeer": self.mass_marketeer,
            "employee_pile": self.employee_pile,
            "milestones_claimed": self.milestones_claimed,
            "restaurants": self.restaurants,
            "max_restaurants": self.max_restaurants,
            "current_front_card": self.current_front_card,
            "current_back_card": self.current_back_card,
            "current_competition_card": self.current_competition_card,
            "bank_breaks": self.bank_breaks,
            "action_log": self.action_log[-50:],  # Last 50 entries
            "pending_input": self.pending_input,
            "is_first_turn": self.is_first_turn,
            "pending_stars": self.pending_stars,
            "chain_cash_this_turn": self.chain_cash_this_turn,
            "chain_total_cash": self.chain_total_cash,
            "bonus_cash_multiplier": self.bonus_cash_multiplier,
            "no_driveins_this_turn": self.no_driveins_this_turn,
            "milestones_unavailable": self.milestones_unavailable,
            "pending_milestone_checks": self.pending_milestone_checks,
            "phase_before_milestone": self.phase_before_milestone,
            "pending_competition_actions": self.pending_competition_actions,
            "phase_after_competition": self.phase_after_competition,
            "chain_movie_star": self.chain_movie_star,
            "turn_order": self.turn_order,
            "display_phase": self.display_phase or self.phase.value,
        }
