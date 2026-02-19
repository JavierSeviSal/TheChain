"""Game engine for The Chain automa — handles the full turn flow."""

from __future__ import annotations
from typing import Optional
import random

from .models import (
    GameState,
    GamePhase,
    GameMode,
    CompetitionLevel,
    Card,
    CardType,
    Deck,
    Inventory,
    Tracks,
    MarketeerSlot,
    RECRUIT_TRAIN_TRACK,
    MARKETEER_DURATIONS,
    FoodItem,
    CORE_FOOD_ITEMS,
)
from .cards import create_all_decks


def _is_item_available(item: str, modules: dict) -> bool:
    """Check whether a food/drink item is available given the active modules.

    Core items (burger, pizza, beer, lemonade, softdrink) are always available.
    Expansion items (sushi, noodle, coffee, kimchi) require their module to be on.
    """
    if item in CORE_FOOD_ITEMS:
        return True
    return modules.get(item, False)


class GameEngine:
    """Manages the state machine and executes game phases."""

    def __init__(self, state: Optional[GameState] = None):
        self.state = state or GameState()

    # ─── Game setup ──────────────────────────────────────────────────────

    def new_game(
        self,
        modules: dict = None,
        optional_rules: dict = None,
        mode: str = "full",
        language: str = "en",
    ) -> dict:
        """Initialize a new game."""
        self.state = GameState()
        self.state.mode = GameMode(mode)
        self.state.language = language

        if modules:
            self.state.modules.update(modules)
        if optional_rules:
            self.state.optional_rules.update(optional_rules)

        # Set max restaurants based on optional rules
        if self.state.optional_rules.get("expand_6_restaurants"):
            self.state.max_restaurants = 6

        # Create and shuffle decks
        action_deck, warm_deck, cool_deck = create_all_decks()
        action_deck.shuffle()
        warm_deck.shuffle()
        cool_deck.shuffle()

        self.state.action_deck = action_deck
        self.state.warm_deck = warm_deck
        self.state.cool_deck = cool_deck

        # Place initial competition cards under the action deck (3 warm + 3 cool)
        if self.state.optional_rules.get("aggressive_setup"):
            # Optional: 6 warm, 0 cool
            for _ in range(6):
                card = self.state.warm_deck.draw()
                if card:
                    self.state.action_deck.place_under(card)
        else:
            # Standard: 3 warm + 3 cool
            for _ in range(3):
                card = self.state.warm_deck.draw()
                if card:
                    self.state.action_deck.place_under(card)
            for _ in range(3):
                card = self.state.cool_deck.draw()
                if card:
                    self.state.action_deck.place_under(card)

        # Set initial track positions
        self.state.tracks.recruit_train.position = 1
        self.state.tracks.price_distance.position = 10
        self.state.tracks.waitresses.position = 0
        self.state.tracks.competition = CompetitionLevel.NEUTRAL

        self.state.phase = GamePhase.SETUP
        self.state.turn_number = 0
        self.state.is_first_turn = True

        self.state.log("New game started!", "setup")
        self.state.log(
            f"Modules: {', '.join(k for k, v in self.state.modules.items() if v)}",
            "setup",
        )
        self.state.log(f"Action Deck: {self.state.action_deck.size()} cards", "setup")

        return {
            "status": "ok",
            "message": "Game initialized. Place The Chain's first restaurant.",
        }

    # ─── Phase execution ─────────────────────────────────────────────────

    # Human-readable milestone labels (English, Spanish)
    MILESTONE_LABELS = {
        "first_to_train": ("First to Train Someone", "Primero en Entrenar a Alguien"),
        "first_to_hire_3": (
            "First to Hire 3 People in 1 Turn",
            "Primero en Contratar 3 en 1 Turno",
        ),
        "first_to_lower_prices": (
            "First to Lower Prices",
            "Primero en Bajar Precios",
        ),
        "first_to_have_waitress": (
            "First to Have a Waitress",
            "Primero en Tener Camarera",
        ),
        "first_to_market": ("First to Market", "Primero en Hacer Marketing"),
        "first_to_pay_20_salary": (
            "First to Pay $20 in Salaries",
            "Primero en Pagar $20 en Salarios",
        ),
        "first_cart_operator": ("First Cart Operator", "Primer Operador de Carrito"),
        "first_errand_boy": ("First Errand Boy", "Primer Chico de los Recados"),
        "first_discount_manager": (
            "First Discount Manager",
            "Primer Gerente de Descuentos",
        ),
        "first_to_throw_away": (
            "First to Throw Away Food",
            "Primero en Tirar Comida",
        ),
    }

    def _check_track_milestones(self):
        """Queue track-based milestones for user confirmation after any track movement.

        FIRST TO TRAIN SOMEONE: R&T track reaches 2 OPEN SLOTS (position 2).
        FIRST TO HIRE 3 PEOPLE IN 1 TURN: R&T track reaches 3 OPEN SLOTS (position 3).
        FIRST TO LOWER PRICES: Price+Distance < 10 AND has inventory to serve at least one house.

        Instead of auto-claiming, milestones are queued into pending_milestone_checks
        so the user can confirm whether the milestone is still available (not already
        claimed by the human player).
        """
        skip = (
            set(self.state.milestones_claimed)
            | set(self.state.milestones_unavailable)
            | set(self.state.pending_milestone_checks)
        )
        open_slots = self.state.tracks.get_open_slots()

        if open_slots >= 2 and "first_to_train" not in skip:
            self.state.pending_milestone_checks.append("first_to_train")
            self.state.log(
                "Milestone triggered: First to Train Someone — awaiting confirmation.",
                "milestone",
            )

        if open_slots >= 3 and "first_to_hire_3" not in skip:
            self.state.pending_milestone_checks.append("first_to_hire_3")
            self.state.log(
                "Milestone triggered: First to Hire 3 People in 1 Turn — awaiting confirmation.",
                "milestone",
            )

        pd_pos = self.state.tracks.price_distance.position
        if pd_pos < 10 and "first_to_lower_prices" not in skip:
            has_food = any(
                count > 0
                for item, count in self.state.inventory.items.items()
                if _is_item_available(item, self.state.modules)
            )
            if has_food:
                self.state.pending_milestone_checks.append("first_to_lower_prices")
                self.state.log(
                    "Milestone triggered: First to Lower Prices — awaiting confirmation.",
                    "milestone",
                )

    def _prompt_pending_milestones(self, result: dict) -> dict:
        """If milestones are pending confirmation, intercept the result with a prompt.

        Only intercepts when the result is not already 'waiting' or 'game_over'.
        Saves the current phase so it can be restored after all milestones are confirmed.
        """
        if not self.state.pending_milestone_checks:
            return result
        if result.get("status") in ("waiting", "game_over", "error"):
            return result

        milestone = self.state.pending_milestone_checks[0]
        en_name, es_name = self.MILESTONE_LABELS.get(milestone, (milestone, milestone))

        # Save the current phase before switching to WAITING_FOR_INPUT
        if self.state.phase_before_milestone is None:
            self.state.phase_before_milestone = self.state.phase.value

        self.state.pending_input = {
            "type": "milestone_confirm",
            "milestone_key": milestone,
            "prompt": (
                f"🏆 Milestone triggered: {en_name}.\n"
                f"Is this milestone still available? (Has the player NOT claimed it yet?)"
            ),
            "prompt_es": (
                f"🏆 Hito activado: {es_name}.\n"
                f"¿Está este hito disponible? (¿El jugador NO lo ha reclamado aún?)"
            ),
            "fields": [
                {
                    "name": "available",
                    "label": "Is this milestone available for The Chain?",
                    "label_es": "¿Está disponible para La Cadena?",
                    "type": "select",
                    "options": ["yes", "no"],
                },
            ],
        }
        self.state.phase = GamePhase.WAITING_FOR_INPUT

        # Preserve the original phase message so the UI can show it
        phase_message = result.get("message", "")

        return {
            "status": "waiting",
            "message": f"Milestone check: {en_name}",
            "phase_message": phase_message,
            "input_needed": self.state.pending_input,
        }

    WORKTIME_PHASES = {
        "recruit_train",
        "initiate_marketing",
        "get_food",
        "develop",
        "lobby",
        "expand_chain",
    }

    def _worktime_turn_hint(self, is_last_worktime: bool = False) -> str:
        """Return a turn-order hint for worktime phases.

        In FCM, the first player does ALL worktime phases, then the second.
        - chain_first: only after the LAST worktime phase, remind the player
          to do all their worktime before proceeding to Dinnertime.
        - player_first: no per-phase hint (player already did all theirs).
        """
        if is_last_worktime and self.state.turn_order == "chain_first":
            return (
                " ⏩ Chain's worktime complete! Now do ALL your worktime phases "
                "(Recruit & Train, Marketing, Get Food, Develop, Lobby, Expand) "
                "before proceeding to Dinnertime."
            )
        return ""

    def advance_phase(self) -> dict:
        """Advance to the next phase and execute it. Returns result dict."""
        self.state.save_snapshot()
        phase = self.state.phase

        # Track the phase being executed for display purposes
        # (handlers transition state.phase to the NEXT phase, but the UI
        # should show the phase that is currently running)
        if phase != GamePhase.WAITING_FOR_INPUT:
            self.state.display_phase = phase.value

        handlers = {
            GamePhase.SETUP: self._do_first_turn,
            GamePhase.RESTRUCTURING: self._do_restructuring,
            GamePhase.ORDER_OF_BUSINESS: self._do_order_of_business,
            GamePhase.RECRUIT_TRAIN: self._do_recruit_train,
            GamePhase.GET_FOOD: self._do_get_food,
            GamePhase.INITIATE_MARKETING: self._do_initiate_marketing,
            GamePhase.DEVELOP: self._do_develop,
            GamePhase.LOBBY: self._do_lobby,
            GamePhase.EXPAND_CHAIN: self._do_expand_chain,
            GamePhase.DINNERTIME: self._do_dinnertime_prompt,
            GamePhase.PAYDAY: self._do_payday,
            GamePhase.MARKETING_CAMPAIGNS: self._do_marketing_campaigns,
            GamePhase.CLEANUP: self._do_cleanup,
            GamePhase.GAME_OVER: lambda: {
                "status": "game_over",
                "message": "The game has ended.",
            },
        }

        handler = handlers.get(phase)
        if handler:
            result = handler()
            return self._prompt_pending_milestones(result)
        return {"status": "error", "message": f"Unknown phase: {phase.value}"}

    def process_input(self, input_data: dict) -> dict:
        """Process player input (e.g., dinnertime earnings comparison)."""
        self.state.save_snapshot()
        input_type = input_data.get("type", "")

        if input_type == "first_restaurant_placed":
            self.state.restaurants.append(
                {
                    "tile": input_data.get("tile", 1),
                    "position": input_data.get("position", ""),
                }
            )
            self.state.log("The Chain placed its first restaurant.", "setup")
            self.state.is_first_turn = False

            # Prompt the player to place their first restaurant
            self.state.pending_input = {
                "type": "player_first_restaurant_placed",
                "prompt": "Now place YOUR first restaurant on the map and confirm.",
                "prompt_es": "Ahora coloca TU primer restaurante en el mapa y confirma.",
                "fields": [],
            }
            self.state.phase = GamePhase.WAITING_FOR_INPUT
            return {
                "status": "waiting",
                "message": "The Chain placed its restaurant. Now place yours.",
                "input_needed": self.state.pending_input,
            }

        elif input_type == "player_first_restaurant_placed":
            self.state.pending_input = None
            self.state.log("Player placed their first restaurant.", "setup")
            self.state.turn_number = 1
            self.state.phase = GamePhase.RESTRUCTURING
            return {
                "status": "ok",
                "message": "Both restaurants placed. Begin Turn 1!",
                "next_phase": "restructuring",
            }

        elif input_type == "dinnertime_result":
            chain_earned = input_data.get("chain_earned", 0)
            player_earned = input_data.get("player_earned", 0)

            # Apply bonus cash multiplier
            chain_earned = int(chain_earned * self.state.bonus_cash_multiplier)
            self.state.chain_cash_this_turn = chain_earned
            self.state.chain_total_cash += chain_earned

            # Competition adjustment
            if chain_earned > player_earned:
                old = self.state.tracks.competition
                self.state.tracks.move_competition(-1)  # Move toward COLD
                self.state.log(
                    f"Chain earned ${chain_earned} > Player ${player_earned}. "
                    f"Competition: {old.label()} → {self.state.tracks.competition.label()}",
                    "dinnertime",
                )
            elif chain_earned < player_earned:
                old = self.state.tracks.competition
                self.state.tracks.move_competition(1)  # Move toward HOT
                self.state.log(
                    f"Chain earned ${chain_earned} < Player ${player_earned}. "
                    f"Competition: {old.label()} → {self.state.tracks.competition.label()}",
                    "dinnertime",
                )
            else:
                self.state.log(
                    f"Chain and Player earned equal (${chain_earned}). Competition unchanged.",
                    "dinnertime",
                )

            # If the Chain sold anything, ask user what was sold to update inventory
            if chain_earned > 0:
                sold_prompt = self._build_sold_items_prompt()
                if sold_prompt is not None:
                    return sold_prompt

            self.state.phase = GamePhase.PAYDAY
            return {
                "status": "ok",
                "message": "Dinnertime resolved. Proceeding to Payday.",
                "next_phase": "payday",
            }

        elif input_type == "dinnertime_sold_items":
            sold_msgs = []
            for key, qty in input_data.items():
                if key == "type":
                    continue
                qty = int(qty)
                if qty > 0 and key in self.state.inventory.items:
                    removed = self.state.inventory.remove(key, qty)
                    if removed > 0:
                        sold_msgs.append(f"{key} ×{removed}")

            if sold_msgs:
                self.state.log(f"Sold: {', '.join(sold_msgs)}", "dinnertime")
            else:
                self.state.log("No items sold from inventory.", "dinnertime")

            self.state.phase = GamePhase.PAYDAY
            return {
                "status": "ok",
                "message": "Inventory updated. Proceeding to Payday.",
                "next_phase": "payday",
            }

        elif input_type == "demand_info":
            # Player provides which food items have demand on the map
            self.state.pending_input = None
            return self._resolve_get_food(input_data)

        elif input_type == "demand_tiebreak":
            # Player provides house demand counts to break a tie
            return self._resolve_demand_tiebreak(input_data)

        elif input_type == "competition_restaurant_placed":
            # Restaurant placed from competition card effect
            tile = input_data.get("tile", 1)
            self.state.restaurants.append(
                {"tile": tile, "position": input_data.get("position", "")}
            )
            self.state.log(
                f"Competition card: restaurant placed on tile {tile}.", "competition"
            )
            self.state.pending_input = None
            return self._resume_after_competition()

        elif input_type == "competition_demand_info":
            # Demand info from competition card effect
            # Note: pending_input is NOT cleared yet — _resolve_competition_demand reads it
            return self._resolve_competition_demand(input_data)

        elif input_type == "competition_demand_tiebreak":
            # Tiebreak for competition card demand
            return self._resolve_competition_demand_tiebreak(input_data)

        elif input_type == "initiate_marketing_campaigns":
            return self._resolve_initiate_marketing(input_data)

        elif input_type == "order_of_business":
            return self._resolve_order_of_business(input_data)

        elif input_type == "bank_break":
            self.state.bank_breaks += 1
            self.state.log(f"Bank break #{self.state.bank_breaks}!", "game")
            if self.state.bank_breaks >= 2:
                self.state.phase = GamePhase.GAME_OVER
                self.state.log("Second bank break! Game over!", "game")
                return {
                    "status": "game_over",
                    "message": "Second bank break! The game is over!",
                }
            return {
                "status": "ok",
                "message": f"Bank break #{self.state.bank_breaks} recorded.",
            }

        elif input_type == "restaurant_placed":
            tile = input_data.get("tile", 1)
            self.state.restaurants.append(
                {"tile": tile, "position": input_data.get("position", "")}
            )
            self.state.log(f"New restaurant placed on tile {tile}.", "expand")
            self.state.pending_input = None
            return self._continue_after_stars()

        elif input_type == "acknowledge":
            # Player acknowledges an instruction
            self.state.pending_input = None
            return self._continue_after_stars()

        elif input_type == "milestone_confirm":
            milestone_key = (self.state.pending_input or {}).get("milestone_key", "")
            available = input_data.get("available", "yes")
            en_name, _ = self.MILESTONE_LABELS.get(
                milestone_key, (milestone_key, milestone_key)
            )
            self.state.pending_input = None

            # Remove from pending checks
            if milestone_key in self.state.pending_milestone_checks:
                self.state.pending_milestone_checks.remove(milestone_key)

            if available == "yes":
                self.state.milestones_claimed.append(milestone_key)
                self.state.log(f"Milestone claimed: {en_name}!", "milestone")
                msg = f"The Chain claimed: {en_name}"
            else:
                self.state.milestones_unavailable.append(milestone_key)
                self.state.log(
                    f"Milestone unavailable (player has it): {en_name}.",
                    "milestone",
                )
                msg = f"Milestone already claimed by player: {en_name}"

            # If more milestones pending, prompt next one
            if self.state.pending_milestone_checks:
                return self._prompt_pending_milestones({"status": "ok", "message": msg})

            # All milestones resolved — restore the phase before interruption
            if self.state.phase_before_milestone:
                self.state.phase = GamePhase(self.state.phase_before_milestone)
                self.state.phase_before_milestone = None

            return {"status": "ok", "message": msg}

        return {"status": "error", "message": f"Unknown input type: {input_type}"}

    # ─── First turn ──────────────────────────────────────────────────────

    def _do_first_turn(self) -> dict:
        """Handle the Chain's first turn: draw top card, show it, place first restaurant."""
        self.state.log("=== THE CHAIN'S FIRST TURN ===", "phase")
        self.state.log("The Chain is first in turn order.", "setup")

        # Draw the top card so the player can see the expand_chain tile
        top_card = self.state.action_deck.peek()
        if top_card:
            card_data = top_card.to_dict()
            self.state.current_front_card = card_data
            map_tile = card_data.get("map_tiles", {}).get("expand_chain", 1)
            self.state.log(
                f"First card revealed: #{top_card.card_number}. "
                f"Use expand_chain tile {map_tile} for placement.",
                "setup",
            )
        else:
            card_data = None
            map_tile = 1

        self.state.pending_input = {
            "type": "first_restaurant_placed",
            "prompt": f"Place The Chain's first restaurant. Target map tile: {map_tile}",
            "prompt_es": f"Coloca el primer restaurante de La Cadena. Casilla objetivo: {map_tile}",
            "fields": [
                {
                    "name": "tile",
                    "label": "Map tile (1-9)",
                    "label_es": "Casilla del mapa (1-9)",
                    "type": "number",
                    "min": 1,
                    "max": 9,
                    "default": map_tile,
                },
            ],
        }
        self.state.phase = GamePhase.WAITING_FOR_INPUT
        return {
            "status": "waiting",
            "message": "Place The Chain's first restaurant.",
            "input_needed": self.state.pending_input,
        }

    # ─── Restructuring ───────────────────────────────────────────────────

    def _do_restructuring(self) -> dict:
        """RESTRUCTURING phase: flip card, competition adjustment, resolve competition card."""
        self.state.log(
            f"=== TURN {self.state.turn_number} — RESTRUCTURING ===", "phase"
        )

        # Reset per-turn flags
        self.state.bonus_cash_multiplier = 1.0
        self.state.no_driveins_this_turn = False
        self.state.chain_cash_this_turn = 0
        self.state.current_competition_card = None

        # STEP 1: Flip top card to reveal back side + front side of next card
        top_card = self.state.action_deck.draw()
        if top_card is None:
            self.state.log("Action deck is empty!", "error")
            return {"status": "error", "message": "Action deck is empty!"}

        # The flipped card's BACK is the current GET FOOD/CLEANUP card
        self.state.current_back_card = top_card.to_dict()

        # The NEXT card on top is the FRONT (RECRUIT & TRAIN) card
        next_card = self.state.action_deck.peek()
        if next_card:
            self.state.current_front_card = next_card.to_dict()
        else:
            self.state.current_front_card = None

        # Place the flipped card into the discard pile
        self.state.discard_pile.place_under(top_card)

        # Update deck progress counters
        self.state.total_cards_drawn += 1
        self.state.cards_drawn_this_cycle += 1

        # If action deck is now empty, reshuffle discard pile back in
        if self.state.action_deck.is_empty() and not self.state.discard_pile.is_empty():
            self.state.reshuffle_deck()
            self.state.log(
                "Action deck empty — reshuffled discard pile back in!", "restructuring"
            )
            # Update front card after reshuffle
            next_card = self.state.action_deck.peek()
            if next_card:
                self.state.current_front_card = next_card.to_dict()

        self.state.log(
            f"Flipped card #{top_card.card_number} (back side: GET FOOD & DRINKS / CLEANUP).",
            "restructuring",
        )
        if next_card:
            self.state.log(
                f"Next card revealed: #{next_card.card_number} (front side: RECRUIT & TRAIN).",
                "restructuring",
            )

        # STEP 2: Competition Adjustment
        result_msgs = self._competition_adjustment()

        # STEP 3: Check if competition card is now on top — keep resolving/discarding
        # until we reach a normal action card (or the deck is empty)
        competition_cards_handled = []
        while True:
            top_after = self.state.action_deck.peek()
            if not top_after or top_after.card_type not in (
                CardType.WARM,
                CardType.COOL,
            ):
                break
            resolved_msg = self._check_resolve_competition(top_after)
            if resolved_msg:
                result_msgs.append(resolved_msg)
            # Track all competition cards encountered this turn
            if self.state.current_competition_card:
                competition_cards_handled.append(self.state.current_competition_card)

        # Store the last competition card for the UI (or the only one)
        if competition_cards_handled:
            self.state.current_competition_card = competition_cards_handled[-1]

        # Update the front card to whatever action card is now on top
        final_top = self.state.action_deck.peek()
        if final_top:
            self.state.current_front_card = final_top.to_dict()

        # Turn 1: skip Order of Business — Chain is first automatically
        is_first_turn = self.state.turn_number == 1
        next_after_restructuring = (
            "recruit_train" if is_first_turn else "order_of_business"
        )

        # Check if any competition card effects need user interaction
        if self.state.pending_competition_actions:
            self.state.phase_after_competition = next_after_restructuring
            restructuring_msg = "Restructuring complete. " + " ".join(result_msgs)
            first_action = self._process_pending_competition_actions()
            if first_action:
                first_action["phase_message"] = restructuring_msg
                first_action["current_back_card"] = self.state.current_back_card
                first_action["current_front_card"] = self.state.current_front_card
                return first_action

        if is_first_turn:
            self.state.turn_order = "chain_first"
            self.state.log(
                "Turn 1: The Chain is first in turn order. Order of Business skipped.",
                "order_of_business",
            )
            self.state.phase = GamePhase.RECRUIT_TRAIN
            return {
                "status": "ok",
                "message": "Restructuring complete. "
                + " ".join(result_msgs)
                + " Turn 1: Chain goes first (Order of Business skipped).",
                "next_phase": "recruit_train",
                "current_back_card": self.state.current_back_card,
                "current_front_card": self.state.current_front_card,
            }

        self.state.phase = GamePhase.ORDER_OF_BUSINESS
        return {
            "status": "ok",
            "message": "Restructuring complete. " + " ".join(result_msgs),
            "next_phase": "order_of_business",
            "current_back_card": self.state.current_back_card,
            "current_front_card": self.state.current_front_card,
        }

    # ─── Order of Business ──────────────────────────────────────────────

    # Movie star rank priority: B > C > D
    MOVIE_STAR_RANKS = ["B", "C", "D"]

    def _do_order_of_business(self) -> dict:
        """ORDER OF BUSINESS phase: determine turn order.

        The player with the most unoccupied slots in their org chart chooses
        a Turn Order slot first. If tied, the holder of the highest-ranking
        movie star (B > C > D) goes first (when movie_stars module is enabled).
        If still tied, previous turn order stands (Chain goes first on turn 1).
        """
        self.state.current_competition_card = None
        self.state.log(f"=== ORDER OF BUSINESS ===", "phase")

        chain_slots = self.state.tracks.get_open_slots()
        chain_star = self.state.chain_movie_star

        # Build prompt fields
        fields = [
            {
                "name": "player_open_slots",
                "label": f"How many open (unoccupied) slots do you have in your org chart? (The Chain has {chain_slots})",
                "label_es": f"¿Cuántas casillas abiertas (sin ocupar) tienes en tu organigrama? (La Cadena tiene {chain_slots})",
                "type": "number",
                "min": 0,
                "max": 50,
                "default": 0,
            },
        ]

        # If movie stars module enabled, ask about player's movie star
        if self.state.modules.get("movie_stars"):
            star_info = (
                f" The Chain has: {chain_star}-movie star."
                if chain_star
                else " The Chain has no movie star."
            )
            fields.append(
                {
                    "name": "player_movie_star",
                    "label": f"Do you have a movie star?{star_info}",
                    "label_es": f"¿Tienes una estrella de cine?{star_info}",
                    "type": "select",
                    "options": ["none", "B", "C", "D"],
                }
            )

        self.state.pending_input = {
            "type": "order_of_business",
            "prompt": f"Order of Business — Determine turn order. The Chain has {chain_slots} open slot(s)."
            + (f" Movie star: {chain_star}." if chain_star else ""),
            "prompt_es": f"Orden de juego — Determinar orden de turno. La Cadena tiene {chain_slots} casilla(s) abierta(s)."
            + (f" Estrella de cine: {chain_star}." if chain_star else ""),
            "fields": fields,
        }
        self.state.phase = GamePhase.WAITING_FOR_INPUT
        return {
            "status": "waiting",
            "message": f"Order of Business: The Chain has {chain_slots} open slot(s). Who goes first?",
            "input_needed": self.state.pending_input,
        }

    def _resolve_order_of_business(self, input_data: dict) -> dict:
        """Process player input for Order of Business and determine turn order."""
        self.state.pending_input = None
        chain_slots = self.state.tracks.get_open_slots()
        player_slots = int(input_data.get("player_open_slots", 0))

        # Determine who goes first
        if chain_slots > player_slots:
            goes_first = "chain_first"
            reason = f"The Chain has more open slots ({chain_slots} vs {player_slots})"
        elif player_slots > chain_slots:
            goes_first = "player_first"
            reason = f"You have more open slots ({player_slots} vs {chain_slots})"
        else:
            # Tied on open slots — check movie stars if module enabled
            reason = f"Tied on open slots ({chain_slots} each)"
            if self.state.modules.get("movie_stars"):
                chain_star = self.state.chain_movie_star
                player_star = input_data.get("player_movie_star", "none")
                if player_star == "none":
                    player_star = None

                chain_rank = (
                    self.MOVIE_STAR_RANKS.index(chain_star)
                    if chain_star in self.MOVIE_STAR_RANKS
                    else 99
                )
                player_rank = (
                    self.MOVIE_STAR_RANKS.index(player_star)
                    if player_star in self.MOVIE_STAR_RANKS
                    else 99
                )

                if chain_rank < player_rank:
                    goes_first = "chain_first"
                    reason += f". The Chain's {chain_star}-movie star outranks yours"
                elif player_rank < chain_rank:
                    goes_first = "player_first"
                    reason += f". Your {player_star}-movie star outranks The Chain's"
                else:
                    # Still tied — previous turn order stands
                    goes_first = self.state.turn_order or "chain_first"
                    reason += ". Still tied — previous turn order stands"
            else:
                # No movie stars — previous turn order stands
                goes_first = self.state.turn_order or "chain_first"
                reason += ". Previous turn order stands"

        self.state.turn_order = goes_first

        if goes_first == "chain_first":
            self.state.log(
                f"Turn order: The Chain goes FIRST. ({reason})",
                "order_of_business",
            )
            msg = f"The Chain goes first! {reason}."
        else:
            self.state.log(
                f"Turn order: YOU go FIRST. ({reason})",
                "order_of_business",
            )
            msg = f"You go first! {reason}. When you finish your turn, click 'Begin Chain's Recruit & Train ▶'."

        self.state.phase = GamePhase.RECRUIT_TRAIN
        return {
            "status": "ok",
            "message": msg,
            "next_phase": "recruit_train",
        }

    def _competition_adjustment(self) -> list[str]:
        """Step 2 of Restructuring: adjust based on competition track."""
        msgs = []
        level = self.state.tracks.competition

        if level == CompetitionLevel.HOT:
            # Place WARM on top AND under
            card1 = self.state.warm_deck.draw()
            card2 = self.state.warm_deck.draw()
            if card1:
                self.state.action_deck.place_on_top(card1)
                msgs.append(f"HOT: Warm card placed on top of Action Deck.")
            else:
                self.state.log(
                    "Warm deck exhausted — cannot place card on top.", "warning"
                )
                msgs.append("HOT: Warm deck empty — no card placed on top.")
            if card2:
                self.state.action_deck.place_under(card2)
                msgs.append(f"Warm card placed under Action Deck.")
            else:
                self.state.log(
                    "Warm deck exhausted — cannot place card under.", "warning"
                )
                msgs.append("Warm deck empty — no card placed under.")
            # Move marker down to WARM
            self.state.tracks.competition = CompetitionLevel.WARM
            msgs.append(f"Competition moved to WARM.")
            self.state.log(
                "Competition HOT → placed Warm card on top + under. Moved to WARM.",
                "restructuring",
            )

        elif level == CompetitionLevel.WARM or self.state.optional_rules.get(
            "aggressive_restructuring"
        ):
            card = self.state.warm_deck.draw()
            if card:
                self.state.action_deck.place_under(card)
                msgs.append("WARM: Warm card placed under Action Deck.")
                self.state.log(
                    "Competition WARM → placed Warm card under deck.", "restructuring"
                )
            else:
                self.state.log("Warm deck exhausted — no card to place.", "warning")
                msgs.append("WARM: Warm deck empty — no card placed.")

        elif level == CompetitionLevel.NEUTRAL:
            msgs.append("NEUTRAL: No competition adjustment.")
            self.state.log("Competition NEUTRAL → no adjustment.", "restructuring")

        elif level == CompetitionLevel.COOL:
            card = self.state.cool_deck.draw()
            if card:
                self.state.action_deck.place_under(card)
                msgs.append("COOL: Cool card placed under Action Deck.")
                self.state.log(
                    "Competition COOL → placed Cool card under deck.", "restructuring"
                )
            else:
                self.state.log("Cool deck exhausted — no card to place.", "warning")
                msgs.append("COOL: Cool deck empty — no card placed.")

        elif level == CompetitionLevel.COLD:
            card1 = self.state.cool_deck.draw()
            card2 = self.state.cool_deck.draw()
            if card1:
                self.state.action_deck.place_on_top(card1)
                msgs.append("COLD: Cool card placed on top of Action Deck.")
            else:
                self.state.log(
                    "Cool deck exhausted — cannot place card on top.", "warning"
                )
                msgs.append("COLD: Cool deck empty — no card placed on top.")
            if card2:
                self.state.action_deck.place_under(card2)
                msgs.append("Cool card placed under Action Deck.")
            else:
                self.state.log(
                    "Cool deck exhausted — cannot place card under.", "warning"
                )
                msgs.append("Cool deck empty — no card placed under.")
            self.state.tracks.competition = CompetitionLevel.COOL
            msgs.append("Competition moved to COOL.")
            self.state.log(
                "Competition COLD → placed Cool card on top + under. Moved to COOL.",
                "restructuring",
            )

        return msgs

    def _check_resolve_competition(self, card: Card) -> Optional[str]:
        """Step 3: If competition card on top matches track, resolve it."""
        level = self.state.tracks.competition

        should_resolve = False
        if card.card_type == CardType.WARM and level in (
            CompetitionLevel.WARM,
            CompetitionLevel.HOT,
        ):
            should_resolve = True
        elif card.card_type == CardType.COOL and level in (
            CompetitionLevel.COOL,
            CompetitionLevel.COLD,
        ):
            should_resolve = True

        # Optional rule: always resolve warm
        if card.card_type == CardType.WARM and self.state.optional_rules.get(
            "aggressive_restructuring"
        ):
            should_resolve = True

        # Store the competition card data so the UI can display it
        comp_card_data = card.to_dict()
        comp_card_data["resolved"] = should_resolve
        comp_card_data["competition_level"] = level.label()
        self.state.current_competition_card = comp_card_data

        if should_resolve:
            # Remove from action deck and resolve
            self.state.action_deck.draw()  # Remove it
            msg = self._resolve_competition_card(card)
            comp_card_data["resolution_summary"] = msg
            self.state.current_competition_card = comp_card_data
            # Place back under its own deck
            if card.card_type == CardType.WARM:
                self.state.warm_deck.place_under(card)
            else:
                self.state.cool_deck.place_under(card)
            return msg
        else:
            # Don't resolve; place under the action deck
            self.state.action_deck.draw()
            self.state.action_deck.place_under(card)
            self.state.log(
                f"Competition card (#{card.card_number} {card.card_type.value}) on top "
                f"does not match track ({level.label()}). Placed under action deck.",
                "restructuring",
            )
            return f"Competition card not resolved (track is {level.label()})."

    def _resolve_competition_card(self, card: Card) -> str:
        """Resolve a competition card's effect.

        Immediate effects (tracks, inventory, flags) are applied now.
        Deferred effects that need user interaction (demand prompts,
        restaurant placement) are queued in pending_competition_actions
        and processed after the restructuring loop finishes.
        """
        if not card.competition_effect:
            return "No effect."

        effect = card.competition_effect
        msgs = []
        food_amount = self.state.tracks.get_food_amount()

        # Apply food adjustments (with module/fallback support)
        for adj in effect.food_adjustments:
            item = adj["item"]
            multiplier = adj.get("amount", 1)
            module = adj.get("module")
            fallback = adj.get("fallback")

            if item in ("all_demand", "most_demand"):
                # Queue deferred action — needs user input about demand on map
                self.state.pending_competition_actions.append(
                    {
                        "action": "competition_demand_info",
                        "demand_type": item,
                        "multiplier": multiplier,
                        "food_amount": food_amount,
                    }
                )
                msgs.append(
                    f"{item.replace('_', ' ').title()}: will ask for demand info"
                )
            else:
                # Specific item: use R&T track food_amount × multiplier
                actual_amount = food_amount * multiplier
                if module and not self.state.modules.get(module, False):
                    if fallback:
                        self.state.inventory.add(fallback, actual_amount)
                        msgs.append(
                            f"+{actual_amount} {fallback} (fallback, {module} not in play)"
                        )
                    else:
                        msgs.append(f"Skipped {item} ({module} not in play)")
                elif not _is_item_available(item, self.state.modules):
                    msgs.append(f"Skipped {item} (module not in play)")
                else:
                    self.state.inventory.add(item, actual_amount)
                    msgs.append(f"+{actual_amount} {item}")

        # Type-specific effects
        if effect.effect_type == "expand_chain":
            if len(self.state.restaurants) < self.state.max_restaurants:
                # Queue deferred action — needs user to place restaurant
                self.state.pending_competition_actions.append(
                    {
                        "action": "competition_expand_chain",
                        "map_tile": effect.map_tile,
                    }
                )
                msgs.append(
                    f"EXPAND CHAIN → will ask to place restaurant (tile {effect.map_tile})"
                )
            else:
                msgs.append("EXPAND CHAIN → max restaurants reached, skipped.")

        elif effect.effect_type == "coffee_shop_or_expand":
            if self.state.modules.get("coffee"):
                msgs.append("COFFEE SHOP → place a coffee shop if available.")
            elif len(self.state.restaurants) < self.state.max_restaurants:
                self.state.pending_competition_actions.append(
                    {
                        "action": "competition_expand_chain",
                        "map_tile": effect.map_tile,
                    }
                )
                msgs.append(
                    "EXPAND CHAIN → will ask to place restaurant (coffee not in play)."
                )

        elif effect.effect_type == "bonus_cash":
            self.state.bonus_cash_multiplier = 1.5
            msgs.append("+50% CASH earned this turn!")

        elif effect.effect_type == "no_driveins":
            self.state.no_driveins_this_turn = True
            msgs.append("NO DRIVE-INS this turn!")
            for item in effect.inventory_loss_items:
                self.state.inventory.clear_item(item)
                msgs.append(f"INVENTORY LOSS: all {item} removed.")

        elif effect.effect_type == "fire_employees":
            # Return all employees from pile to pool
            fired = list(self.state.employee_pile)
            self.state.employee_pile.clear()
            for slot in self.state.marketeer_slots:
                if slot.marketeer:
                    fired.append(slot.marketeer)
                    slot.marketeer = None
                    slot.is_busy = False
                    slot.market_item = None
                    slot.campaign_number = None
                    slot.campaigns_left = None
                    slot.placed_turn = None
            msgs.append(
                f"FIRE ALL EMPLOYEES: {', '.join(fired) if fired else 'none to fire'}."
            )
            for item in effect.inventory_loss_items:
                self.state.inventory.clear_item(item)
                msgs.append(f"INVENTORY LOSS: all {item} removed.")

        elif effect.effect_type == "pay_per_employee":
            emp_count = len(self.state.employee_pile) + sum(
                1 for s in self.state.marketeer_slots if s.marketeer
            )
            cost = emp_count * 10
            msgs.append(f"PAY $10 PER EMPLOYEE: {emp_count} employees × $10 = ${cost}.")
            for item in effect.inventory_loss_items:
                self.state.inventory.clear_item(item)
                msgs.append(f"INVENTORY LOSS: all {item} removed.")

        # Inventory boost (independent of effect type)
        if effect.inventory_boost:
            boost_details = self.state.inventory.inventory_boost()
            if boost_details:
                msgs.append(f"INVENTORY BOOST: {', '.join(boost_details)}")
            else:
                msgs.append("INVENTORY BOOST: no items on bottom row.")

        # Inventory drop (independent of effect type)
        if effect.inventory_drop:
            drop_details = self.state.inventory.inventory_drop()
            if drop_details:
                msgs.append(f"INVENTORY DROP: {', '.join(drop_details)}")
            else:
                msgs.append("INVENTORY DROP: no items on top row.")

        # Track adjustments
        for ta in effect.track_adjustments:
            ta_type = ta["type"]
            ta_value = ta["value"]

            if ta_type == "move_distance":
                old, new, _ = self.state.tracks.price_distance.move(ta_value)
                msgs.append(f"Distance: {old}→{new}")
                self.state.log(
                    f"Competition card: Price+Distance {old} → {new}", "competition"
                )
                self._check_track_milestones()
            elif ta_type == "move_waitress":
                old, new, _ = self.state.tracks.waitresses.move(ta_value)
                msgs.append(f"Waitress: {old}→{new}")
                self.state.log(
                    f"Competition card: Waitresses {old} → {new}", "competition"
                )
            elif ta_type == "move_recruit_train":
                old, new, crossed = self.state.tracks.recruit_train.move(ta_value)
                msgs.append(f"R&T: {old}→{new}")
                self.state.log(
                    f"Competition card: Recruit & Train {old} → {new}", "competition"
                )
                self._check_track_milestones()
                if crossed:
                    self.state.reshuffle_deck()
                    msgs.append("ACTION DECK SHUFFLED!")
                    self.state.log(
                        "SHUFFLE triggered by R&T track crossing!", "competition"
                    )
                    # Ensure no competition card on top after shuffle
                    top = self.state.action_deck.peek()
                    while top and top.card_type in (CardType.WARM, CardType.COOL):
                        self.state.reshuffle_deck()
                        self.state.log(
                            "Competition card on top after shuffle — reshuffling.",
                            "competition",
                        )
                        top = self.state.action_deck.peek()

        result = " | ".join(msgs)
        self.state.log(
            f"Resolved {card.card_type.value} card #{card.card_number}: {result}",
            "competition",
        )
        return result

    def _process_pending_competition_actions(self) -> Optional[dict]:
        """Process the next queued competition card action.

        Returns a 'waiting' result dict if user interaction is needed,
        or None if the queue is empty (caller should continue normal flow).
        """
        if not self.state.pending_competition_actions:
            return None

        action = self.state.pending_competition_actions.pop(0)
        action_type = action.get("action", "")

        if action_type == "competition_expand_chain":
            map_tile = action.get("map_tile", 1)
            self.state.pending_input = {
                "type": "competition_restaurant_placed",
                "prompt": (
                    f"🏗️ Competition card: EXPAND CHAIN!\n"
                    f"Place a new restaurant. Target map tile: {map_tile}"
                ),
                "prompt_es": (
                    f"🏗️ Carta de competencia: ¡EXPANDIR CADENA!\n"
                    f"Coloca un nuevo restaurante. Casilla objetivo: {map_tile}"
                ),
                "fields": [
                    {
                        "name": "tile",
                        "label": "Map tile placed on",
                        "label_es": "Casilla donde se coloca",
                        "type": "number",
                        "min": 1,
                        "max": 9,
                        "default": map_tile,
                    }
                ],
            }
            self.state.phase = GamePhase.WAITING_FOR_INPUT
            return {
                "status": "waiting",
                "message": f"Competition card: Place restaurant on tile {map_tile}.",
                "input_needed": self.state.pending_input,
            }

        elif action_type == "competition_demand_info":
            demand_type = action.get("demand_type", "most_demand")
            multiplier = action.get("multiplier", 1)
            food_amount = action.get("food_amount", 2)

            fields = [
                {
                    "name": "items_with_demand",
                    "label": "Items with demand on map",
                    "label_es": "Items con demanda en el mapa",
                    "type": "multiselect",
                    "options": [
                        fi.value
                        for fi in FoodItem
                        if _is_item_available(fi.value, self.state.modules)
                    ],
                },
            ]

            if demand_type == "most_demand":
                fields.append(
                    {
                        "name": "most_demand_items",
                        "label": "Item(s) with MOST demand tokens (select all tied items)",
                        "label_es": "Item(s) con MÁS fichas de demanda (selecciona todos los empatados)",
                        "type": "multiselect",
                        "options": [
                            fi.value
                            for fi in FoodItem
                            if _is_item_available(fi.value, self.state.modules)
                        ],
                    }
                )

            self.state.pending_input = {
                "type": "competition_demand_info",
                "prompt": (
                    f"🍔 Competition card: Get food ({demand_type.replace('_', ' ')})!\n"
                    f"Which food items have demand tokens on the map?"
                ),
                "prompt_es": (
                    f"🍔 Carta de competencia: ¡Obtener comida ({demand_type.replace('_', ' ')})!\n"
                    f"¿Qué items de comida tienen fichas de demanda en el mapa?"
                ),
                "demand_type": demand_type,
                "multiplier": multiplier,
                "food_amount": food_amount,
                "fields": fields,
            }
            self.state.phase = GamePhase.WAITING_FOR_INPUT
            return {
                "status": "waiting",
                "message": f"Competition card: Need demand info ({demand_type.replace('_', ' ')}).",
                "input_needed": self.state.pending_input,
            }

        # Unknown action type — skip it
        self.state.log(f"Unknown competition action: {action_type}", "warning")
        return self._process_pending_competition_actions()

    def _resume_after_competition(self) -> dict:
        """Check for more pending competition actions, or resume normal phase flow."""
        # More actions queued?
        next_action = self._process_pending_competition_actions()
        if next_action:
            return next_action

        # All competition actions done — restore phase flow
        self.state.current_competition_card = None
        resume_phase = self.state.phase_after_competition or "order_of_business"
        self.state.phase_after_competition = None
        self.state.phase = GamePhase(resume_phase)

        return {
            "status": "ok",
            "message": "Competition card effects resolved. Continuing...",
            "next_phase": resume_phase,
        }

    def _resolve_competition_demand(self, input_data: dict) -> dict:
        """Resolve demand info from a competition card effect."""
        pending = self.state.pending_input or {}
        demand_type = input_data.get("demand_type") or pending.get(
            "demand_type", "most_demand"
        )
        multiplier = pending.get("multiplier", 1)
        food_amount = pending.get("food_amount", self.state.tracks.get_food_amount())

        items_with_demand = input_data.get("items_with_demand", [])
        most_demand_items = input_data.get("most_demand_items", [])

        # If only one item has demand, it is automatically the most demanded
        if (
            demand_type == "most_demand"
            and len(items_with_demand) == 1
            and not most_demand_items
        ):
            most_demand_items = list(items_with_demand)

        added = []
        if demand_type == "all_demand":
            for item in items_with_demand:
                amount = food_amount * multiplier
                self.state.inventory.add(item, amount)
                added.append(f"+{amount} {item}")
                self.state.log(
                    f"Competition all demand: +{amount} {item}", "competition"
                )
        elif demand_type == "most_demand":
            if len(most_demand_items) == 1:
                item = most_demand_items[0]
                amount = food_amount * multiplier
                self.state.inventory.add(item, amount)
                added.append(f"+{amount} {item}")
                self.state.log(
                    f"Competition most demand: +{amount} {item}", "competition"
                )
            elif len(most_demand_items) > 1:
                # Tie — ask for house demand to break it
                self.state.pending_input = {
                    "type": "competition_demand_tiebreak",
                    "prompt": f"Tie between {', '.join(most_demand_items)}! How many demand tokens on HOUSES for each?",
                    "prompt_es": f"¡Empate entre {', '.join(most_demand_items)}! ¿Cuántas fichas de demanda en CASAS para cada uno?",
                    "tied_items": most_demand_items,
                    "multiplier": multiplier,
                    "food_amount": food_amount,
                    "fields": [
                        {
                            "name": f"house_demand_{item}",
                            "label": f"Demand on houses: {item}",
                            "label_es": f"Demanda en casas: {item}",
                            "type": "number",
                            "min": 0,
                            "max": 50,
                            "default": 0,
                        }
                        for item in most_demand_items
                    ],
                }
                self.state.phase = GamePhase.WAITING_FOR_INPUT
                return {
                    "status": "waiting",
                    "message": f"Competition card: Tie for most demand between {', '.join(most_demand_items)}.",
                    "input_needed": self.state.pending_input,
                }
            else:
                self.state.log(
                    "Competition card: No most demand item selected.", "competition"
                )

        msg = f"Competition card food: {', '.join(added) if added else 'none'}"
        self.state.log(msg, "competition")
        return self._resume_after_competition()

    def _resolve_competition_demand_tiebreak(self, input_data: dict) -> dict:
        """Resolve tie in most demand for a competition card effect."""
        pending = self.state.pending_input or {}
        tied_items = pending.get("tied_items", [])
        multiplier = pending.get("multiplier", 1)
        food_amount = pending.get("food_amount", self.state.tracks.get_food_amount())

        house_counts = {}
        for item in tied_items:
            house_counts[item] = input_data.get(f"house_demand_{item}", 0)

        max_count = max(house_counts.values()) if house_counts else 0
        winners = [item for item, count in house_counts.items() if count == max_count]

        if len(winners) == 1:
            winner = winners[0]
            self.state.log(
                f"Competition tiebreak by houses: {winner} ({max_count} on houses)",
                "competition",
            )
        else:
            winner = random.choice(winners)
            self.state.log(
                f"Competition tiebreak random: {winner} (still tied on houses)",
                "competition",
            )

        amount = food_amount * multiplier
        self.state.inventory.add(winner, amount)
        self.state.log(f"Competition most demand: +{amount} {winner}", "competition")

        self.state.pending_input = None
        msg = f"Competition card: +{amount} {winner} (most demand)"
        return self._resume_after_competition()

    # ─── Recruit & Train ─────────────────────────────────────────────────

    def _do_recruit_train(self) -> dict:
        """RECRUIT & TRAIN phase: execute actions based on open slots."""
        self.state.log(f"=== RECRUIT & TRAIN ===", "phase")

        # Clear competition card from UI once we've moved past restructuring
        self.state.current_competition_card = None

        # Turn 1: The Chain does not take any R&T actions
        if self.state.turn_number == 1:
            self.state.pending_stars = []
            self.state.log(
                "Turn 1: The Chain does not take Recruit & Train actions.",
                "recruit_train",
            )
            self.state.phase = GamePhase.INITIATE_MARKETING
            hint = self._worktime_turn_hint()
            return {
                "status": "ok",
                "message": "Turn 1: Chain skips Recruit & Train." + hint,
                "next_phase": "initiate_marketing",
            }

        front_card_data = self.state.current_front_card
        if not front_card_data or "front" not in front_card_data:
            self.state.phase = GamePhase.INITIATE_MARKETING
            hint = self._worktime_turn_hint()
            return {
                "status": "ok",
                "message": "No front card available. Skipping Recruit & Train." + hint,
                "next_phase": "initiate_marketing",
            }

        open_slots = self.state.tracks.get_open_slots()
        actions = front_card_data["front"]["actions"]

        # Actions are listed ascending [S1, S2, S3, S4] (bottom to top on card)
        # Open slots are the LOWEST slots on the card:
        #   1 slot  → only S1
        #   2 slots → S1, S2   (executed top-down: S2 then S1)
        #   3 slots → S1–S3    (executed top-down: S3, S2, S1)
        #   4 slots → all      (executed top-down: S4, S3, S2, S1)
        # Execution order is always descending (highest open slot first).

        active_actions = actions[:open_slots]  # Take the N lowest slots
        # Execute in descending order (highest slot number first)
        active_actions_reversed = list(reversed(active_actions))

        result_msgs = []
        for action_data in active_actions_reversed:
            msg = self._execute_recruit_action(action_data)
            result_msgs.append(msg)

        self.state.log(
            f"Open slots: {open_slots}. Executed {len(active_actions)} actions.",
            "recruit_train",
        )

        # Collect stars only from the active (open) slots
        stars = [a["star"] for a in active_actions if a.get("star")]
        self.state.pending_stars = stars

        self.state.phase = GamePhase.INITIATE_MARKETING
        hint = self._worktime_turn_hint()
        return {
            "status": "ok",
            "message": f"Recruit & Train complete ({open_slots} open slots). "
            + " | ".join(result_msgs)
            + hint,
            "actions_taken": result_msgs,
            "next_phase": "initiate_marketing",
        }

    def _execute_recruit_action(self, action_data: dict) -> str:
        """Execute a single Recruit & Train action."""
        action_type = action_data["type"]
        target = action_data["target"]
        fallback = action_data.get("fallback_food")
        requires = action_data.get("requires_module")

        # Check if module is required but not active
        if requires and not self.state.modules.get(requires, False):
            if fallback:
                food_amount = self.state.tracks.get_food_amount()
                foods = fallback if isinstance(fallback, list) else [fallback]
                for f in foods:
                    self.state.inventory.add(f, food_amount)
                names = ", ".join(foods)
                self.state.log(
                    f"Module '{requires}' not in play. Getting +{food_amount} {names} instead.",
                    "recruit_train",
                )
                return f"GET FOOD: +{food_amount} {names} (module not in play)"
            return f"Skipped (module '{requires}' not in play)"

        if action_type == "recruit_marketeer":
            return self._recruit_marketeer(target)
        elif action_type == "recruit_employee":
            return self._recruit_employee(target)
        elif action_type == "move_distance":
            delta = int(target)
            old, new, crossed = self.state.tracks.price_distance.move(delta)
            self.state.log(f"Price+Distance: {old} → {new}", "recruit_train")
            self._check_track_milestones()
            return f"Price+Distance: {old} → {new}"
        elif action_type == "move_waitress":
            delta = int(target)
            old, new, _ = self.state.tracks.waitresses.move(delta)
            self.state.log(f"Waitresses: {old} → {new}", "recruit_train")
            if new == 4:
                if (
                    self.state.modules.get("movie_stars")
                    and not self.state.chain_movie_star
                ):
                    # Recruit highest available movie star: B > C > D
                    for rank in self.MOVIE_STAR_RANKS:
                        self.state.chain_movie_star = rank
                        self.state.log(
                            f"Waitresses reached 4! The Chain recruits a {rank}-movie star!",
                            "recruit_train",
                        )
                        break
                else:
                    self.state.log(
                        "Waitresses reached 4! Recruit highest-ranking movie star.",
                        "recruit_train",
                    )
            # Milestone: first to have a waitress
            if (
                new > 0
                and "first_to_have_waitress" not in self.state.milestones_claimed
            ):
                self.state.milestones_claimed.append("first_to_have_waitress")
                self.state.log(
                    "Milestone claimed: First to Have a Waitress!", "milestone"
                )
            self._check_track_milestones()
            return f"Waitresses: {old} → {new}"
        elif action_type == "claim_milestone":
            if target not in self.state.milestones_claimed:
                self.state.milestones_claimed.append(target)
                self.state.log(f"Milestone claimed: {target}!", "milestone")
                return f"Milestone: {target}"
            return f"Milestone {target} already claimed"
        elif action_type == "get_food":
            food_amount = self.state.tracks.get_food_amount()
            self.state.inventory.add(target, food_amount)
            self.state.log(f"Get food: +{food_amount} {target}", "recruit_train")
            return f"GET FOOD: +{food_amount} {target}"

        return f"Unknown action: {action_type}"

    def _recruit_marketeer(self, name: str) -> str:
        """Recruit a marketeer to an open slot."""
        if name == "Mass Marketeer":
            if not self.state.mass_marketeer:
                self.state.mass_marketeer = True
                self.state.log(
                    f"Mass Marketeer recruited (placed next to Track Mat).",
                    "recruit_train",
                )
                return "Recruited: Mass Marketeer"
            else:
                self.state.log("Mass Marketeer already recruited.", "recruit_train")
                return "Mass Marketeer already in play"

        # Find an open marketeer slot
        for slot in self.state.marketeer_slots:
            if slot.marketeer is None:
                slot.marketeer = name
                self.state.log(
                    f"Recruited {name} to Marketeer slot {slot.slot_number}.",
                    "recruit_train",
                )
                # Gourmet Food Critic: also place 1 garden on the map
                if name == "Gourmet Food Critic":
                    map_tiles = (
                        self.state.current_front_card.get("map_tiles", {})
                        if self.state.current_front_card
                        else {}
                    )
                    dev_tile = map_tiles.get("develop_lobby", 1)
                    self.state.log(
                        f"Gourmet Food Critic: Place 1 garden on the map. Target tile: {dev_tile}",
                        "recruit_train",
                    )
                return f"Recruited: {name} (Marketeer slot {slot.slot_number})"

        # No open slots
        busy_count = sum(1 for s in self.state.marketeer_slots if s.is_busy)
        if busy_count >= 3:
            self.state.log(
                f"All marketeer slots full. Cannot recruit {name}.", "recruit_train"
            )
            return f"Cannot recruit {name}: all slots full"

        self.state.log(f"No empty marketeer slot for {name}.", "recruit_train")
        return f"No slot for {name}"

    def _recruit_employee(self, name: str) -> str:
        """Recruit an employee to the Employee Pile (or Marketeer spot for Brand Director)."""
        if name == "Brand Director":
            # Goes in marketeer spot instead
            for slot in self.state.marketeer_slots:
                if slot.marketeer is None:
                    slot.marketeer = "Brand Director"
                    self.state.log(
                        f"Brand Director placed in Marketeer slot {slot.slot_number}.",
                        "recruit_train",
                    )
                    return (
                        f"Recruited: Brand Director (marketeer slot {slot.slot_number})"
                    )
            self.state.log("No marketeer slot for Brand Director.", "recruit_train")
            return "No slot for Brand Director"

        self.state.employee_pile.append(name)
        self.state.log(f"Recruited {name} to Employee Pile.", "recruit_train")

        # Track-based milestones are checked centrally via _check_track_milestones()
        # which is called after every track movement.

        return f"Recruited: {name}"

    # ─── Get Food & Drinks ───────────────────────────────────────────────

    def _do_get_food(self) -> dict:
        """GET FOOD & DRINKS phase."""
        self.state.log(f"=== GET FOOD & DRINKS ===", "phase")

        back_card = self.state.current_back_card
        if not back_card or "back" not in back_card:
            self.state.phase = GamePhase.DEVELOP
            hint = self._worktime_turn_hint()
            return {
                "status": "ok",
                "message": "No back card. Skipping Get Food." + hint,
                "next_phase": "develop",
            }

        back = back_card["back"]
        demand_type = back.get("demand_type", "most_demand")
        food_items = back.get("food_items", [])
        multiplier = back.get("multiplier", 1)
        food_amount = self.state.tracks.get_food_amount()

        if demand_type == "specific":
            # Left box: add specific items
            for item in food_items:
                if item in [fi.value for fi in FoodItem]:
                    if _is_item_available(item, self.state.modules):
                        self.state.inventory.add(item, food_amount * multiplier)
                        self.state.log(
                            f"+{food_amount * multiplier} {item}", "get_food"
                        )
                    else:
                        self.state.log(
                            f"Skipped {item} (module not in play)", "get_food"
                        )
            # Right box: add food_item (with module/fallback)
            right_msg = self._add_right_box_food(back, food_amount)
            parts = []
            for item in food_items:
                if item in [fi.value for fi in FoodItem]:
                    if _is_item_available(item, self.state.modules):
                        parts.append(f"+{food_amount * multiplier} {item}")
            if right_msg:
                parts.append(right_msg)
            self.state.phase = GamePhase.DEVELOP
            hint = self._worktime_turn_hint()
            return {
                "status": "ok",
                "message": (
                    f"Food added: {', '.join(parts)}" if parts else "No food added."
                )
                + hint,
                "next_phase": "develop",
            }
        else:
            # Need player input about demand on the map
            self.state.pending_input = {
                "type": "demand_info",
                "prompt": f"Which food items have demand tokens on the map? (for {demand_type.replace('_', ' ')})",
                "prompt_es": f"¿Qué items de comida tienen fichas de demanda? (para {demand_type.replace('_', ' ')})",
                "demand_type": demand_type,
                "multiplier": multiplier,
                "food_amount": food_amount,
                "fields": [
                    {
                        "name": "items_with_demand",
                        "label": "Items with demand on map",
                        "label_es": "Items con demanda en el mapa",
                        "type": "multiselect",
                        "options": [
                            fi.value
                            for fi in FoodItem
                            if _is_item_available(fi.value, self.state.modules)
                        ],
                    },
                    {
                        "name": "most_demand_items",
                        "label": "Item(s) with MOST demand tokens (select all tied items)",
                        "label_es": "Item(s) con MÁS fichas de demanda (selecciona todos los empatados)",
                        "type": "multiselect",
                        "options": [
                            fi.value
                            for fi in FoodItem
                            if _is_item_available(fi.value, self.state.modules)
                        ],
                        "condition": demand_type == "most_demand",
                    },
                ],
            }
            self.state.phase = GamePhase.WAITING_FOR_INPUT
            return {
                "status": "waiting",
                "message": f"Need demand information for {demand_type.replace('_', ' ')}.",
                "input_needed": self.state.pending_input,
            }

    def _resolve_get_food(self, input_data: dict) -> dict:
        """Resolve Get Food phase after receiving demand info."""
        back = (
            self.state.current_back_card.get("back", {})
            if self.state.current_back_card
            else {}
        )
        demand_type = back.get("demand_type", "most_demand")
        multiplier = back.get("multiplier", 1)
        food_amount = self.state.tracks.get_food_amount()

        items_with_demand = input_data.get("items_with_demand", [])
        most_demand_items = input_data.get("most_demand_items", [])

        # If only one item has demand, it is automatically the most demanded
        if (
            demand_type == "most_demand"
            and len(items_with_demand) == 1
            and not most_demand_items
        ):
            most_demand_items = list(items_with_demand)

        added = []
        if demand_type == "all_demand":
            for item in items_with_demand:
                amount = food_amount * multiplier
                self.state.inventory.add(item, amount)
                added.append(f"+{amount} {item}")
                self.state.log(f"All demand: +{amount} {item}", "get_food")
        elif demand_type == "most_demand":
            if len(most_demand_items) == 1:
                # Single winner — no tie
                item = most_demand_items[0]
                amount = food_amount * multiplier
                self.state.inventory.add(item, amount)
                added.append(f"+{amount} {item}")
                self.state.log(f"Most demand: +{amount} {item}", "get_food")
            elif len(most_demand_items) > 1:
                # Tie! Ask for demand tokens on houses to break it
                self.state.pending_input = {
                    "type": "demand_tiebreak",
                    "prompt": f"Tie between {', '.join(most_demand_items)}! How many demand tokens on HOUSES for each?",
                    "prompt_es": f"¡Empate entre {', '.join(most_demand_items)}! ¿Cuántas fichas de demanda en CASAS para cada uno?",
                    "tied_items": most_demand_items,
                    "multiplier": multiplier,
                    "food_amount": food_amount,
                    "fields": [
                        {
                            "name": f"house_demand_{item}",
                            "label": f"Demand on houses: {item}",
                            "label_es": f"Demanda en casas: {item}",
                            "type": "number",
                            "min": 0,
                            "max": 50,
                            "default": 0,
                        }
                        for item in most_demand_items
                    ],
                }
                self.state.phase = GamePhase.WAITING_FOR_INPUT
                return {
                    "status": "waiting",
                    "message": f"Tie for most demand between: {', '.join(most_demand_items)}. Need house demand info.",
                    "input_needed": self.state.pending_input,
                }
            else:
                self.state.log("No most demand item selected.", "get_food")

        # Right box: add food_item (with module/fallback)
        right_msg = self._add_right_box_food(back, food_amount)
        if right_msg:
            added.append(right_msg)

        self.state.phase = GamePhase.DEVELOP
        hint = self._worktime_turn_hint()
        return {
            "status": "ok",
            "message": f"Food added: {', '.join(added) if added else 'none'}" + hint,
            "next_phase": "develop",
        }

    def _resolve_demand_tiebreak(self, input_data: dict) -> dict:
        """Resolve tie in most demand using demand tokens on houses, then random."""
        pending = self.state.pending_input or {}
        tied_items = pending.get("tied_items", [])
        multiplier = pending.get("multiplier", 1)
        food_amount = pending.get("food_amount", 1)

        # Collect house demand counts from user input
        house_counts = {}
        for item in tied_items:
            house_counts[item] = input_data.get(f"house_demand_{item}", 0)

        max_count = max(house_counts.values()) if house_counts else 0
        winners = [item for item, count in house_counts.items() if count == max_count]

        if len(winners) == 1:
            winner = winners[0]
            self.state.log(
                f"Tiebreak by houses: {winner} ({max_count} on houses)", "get_food"
            )
        else:
            winner = random.choice(winners)
            self.state.log(
                f"Tiebreak random: {winner} (still tied on houses)", "get_food"
            )

        amount = food_amount * multiplier
        self.state.inventory.add(winner, amount)
        self.state.log(f"Most demand: +{amount} {winner}", "get_food")

        # Right box: add food_item (with module/fallback)
        back = (
            self.state.current_back_card.get("back", {})
            if self.state.current_back_card
            else {}
        )
        right_msg = self._add_right_box_food(back, food_amount)

        self.state.pending_input = None
        self.state.phase = GamePhase.DEVELOP
        parts = [f"+{amount} {winner}"]
        if right_msg:
            parts.append(right_msg)
        hint = self._worktime_turn_hint()
        return {
            "status": "ok",
            "message": f"Food added: {', '.join(parts)}" + hint,
            "next_phase": "develop",
        }

    # ─── Marketing ───────────────────────────────────────────────────────

    def _add_right_box_food(self, back: dict, food_amount: int) -> Optional[str]:
        """Process the right-box food_item from the back card.

        Adds the indicated food/drink. If the item's module is inactive,
        uses the fallback item instead. If no fallback, skips.
        The right-box has its own multiplier (food_item_multiply), independent
        of the left-box multiplier.
        Returns a short description string for the main message, or None.
        """
        fi = back.get("food_item")
        if not fi:
            return None
        fi_module = back.get("food_item_module")
        fi_fallback = back.get("food_item_fallback")
        fi_multiply = back.get("food_item_multiply", 1)
        amount = food_amount * fi_multiply

        if fi_module and not self.state.modules.get(fi_module, False):
            # Module inactive — use fallback
            if fi_fallback:
                self.state.inventory.add(fi_fallback, amount)
                self.state.log(
                    f"+{amount} {fi_fallback} (fallback, {fi_module} not in play)",
                    "get_food",
                )
                return f"+{amount} {fi_fallback}"
            else:
                self.state.log(
                    f"Skipped {fi} ({fi_module} not in play, no fallback)",
                    "get_food",
                )
                return None
        else:
            self.state.inventory.add(fi, amount)
            self.state.log(f"+{amount} {fi}", "get_food")
            return f"+{amount} {fi}"

    # ─── Initiate Marketing ───────────────────────────────────────────

    def _do_initiate_marketing(self) -> dict:
        """INITIATE MARKETING phase: activate newly placed marketeers.

        If any marketeer is newly placed (not yet busy), we need to ask the
        player for campaign numbers before marking them busy. Otherwise we
        just list existing campaigns.
        """
        self.state.log(f"=== INITIATE MARKETING ===", "phase")

        # Get market tile and market item from current card
        map_tiles = (
            self.state.current_front_card.get("map_tiles", {})
            if self.state.current_front_card
            else {}
        )
        market_tile = map_tiles.get("market", 1)

        front = (
            self.state.current_front_card.get("front", {})
            if self.state.current_front_card
            else {}
        )
        market_item = front.get("market_item") or "unknown"

        # Find newly placed marketeers (in a slot, not busy yet)
        new_marketeers = [
            slot
            for slot in self.state.marketeer_slots
            if slot.marketeer and not slot.is_busy
        ]

        if not new_marketeers:
            # No new campaigns to set up
            campaigns = []
            for slot in self.state.marketeer_slots:
                if slot.marketeer and slot.is_busy:
                    left = (
                        "∞" if slot.campaigns_left == -1 else f"{slot.campaigns_left}"
                    )
                    campaigns.append(
                        f"{slot.marketeer} (slot {slot.slot_number}): "
                        f"{slot.market_item}, campaign #{slot.campaign_number}, "
                        f"{left} left"
                    )
            if self.state.mass_marketeer:
                campaigns.append("Mass Marketeer: additional marketing campaign")
                self.state.log(
                    "Mass Marketeer runs additional marketing campaign phase.",
                    "marketing",
                )

            self.state.phase = GamePhase.GET_FOOD
            hint = self._worktime_turn_hint()
            msg = (
                "Initiate Marketing: "
                + (
                    " | ".join(campaigns)
                    if campaigns
                    else "No new or active campaigns."
                )
                + hint
            )
            return {"status": "ok", "message": msg, "next_phase": "get_food"}

        # Build prompt fields — one campaign number field per new marketeer
        fields = []
        for slot in new_marketeers:
            duration = MARKETEER_DURATIONS.get(slot.marketeer, 3)
            if duration == -1:
                dur_label = "permanent"
                dur_label_es = "permanente"
            else:
                dur_label = f"{duration} campaigns"
                dur_label_es = f"{duration} campañas"
            fields.append(
                {
                    "name": f"campaign_slot_{slot.slot_number}",
                    "label": (
                        f"Campaign # for {slot.marketeer} "
                        f"(slot {slot.slot_number}, {market_item}, {dur_label})"
                    ),
                    "label_es": (
                        f"Campaña # para {slot.marketeer} "
                        f"(casilla {slot.slot_number}, {market_item}, {dur_label_es})"
                    ),
                    "type": "number",
                    "min": 1,
                    "max": 99,
                    "default": 1,
                }
            )

        # Store the market context so _resolve_initiate_marketing can use it
        self.state.pending_input = {
            "type": "initiate_marketing_campaigns",
            "market_item": market_item,
            "market_tile": market_tile,
            "prompt": (
                f"Assign marketing campaign numbers.\n"
                f"Market item: {market_item} | Target tile: {market_tile}"
            ),
            "prompt_es": (
                f"Asigna los números de campaña de marketing.\n"
                f"Artículo: {market_item} | Casilla objetivo: {market_tile}"
            ),
            "fields": fields,
        }
        self.state.phase = GamePhase.WAITING_FOR_INPUT
        return {
            "status": "waiting",
            "message": f"Marketing: assign campaign numbers for new marketeers.",
            "input_needed": self.state.pending_input,
        }

    def _resolve_initiate_marketing(self, input_data: dict) -> dict:
        """Process campaign number assignments from the user."""
        pending = self.state.pending_input or {}
        market_item = pending.get("market_item", "unknown")
        market_tile = pending.get("market_tile", 1)
        self.state.pending_input = None

        campaigns = []
        for slot in self.state.marketeer_slots:
            if slot.marketeer and not slot.is_busy:
                campaign_num = input_data.get(f"campaign_slot_{slot.slot_number}", 1)
                duration = MARKETEER_DURATIONS.get(slot.marketeer, 3)

                slot.is_busy = True
                slot.market_item = market_item
                slot.campaign_number = campaign_num
                slot.campaigns_left = duration  # -1 for eternal (Rural Marketeer)
                slot.placed_turn = self.state.turn_number

                dur_desc = "permanent" if duration == -1 else f"{duration} campaigns"
                campaigns.append(
                    f"{slot.marketeer} (slot {slot.slot_number}) markets "
                    f"{market_item} on tile {market_tile}, "
                    f"campaign #{campaign_num}, {dur_desc}"
                )
                self.state.log(
                    f"{slot.marketeer} markets {market_item}. "
                    f"Campaign #{campaign_num}. Target tile: {market_tile}. "
                    f"Duration: {dur_desc}.",
                    "marketing",
                )
                # Milestone: first to market
                if "first_to_market" not in self.state.milestones_claimed:
                    self.state.milestones_claimed.append("first_to_market")
                    self.state.log("Milestone claimed: First to Market!", "milestone")

        if self.state.mass_marketeer:
            campaigns.append("Mass Marketeer: additional marketing campaign")
            self.state.log(
                "Mass Marketeer runs additional marketing campaign phase.", "marketing"
            )

        self.state.phase = GamePhase.GET_FOOD
        hint = self._worktime_turn_hint()
        msg = (
            "Initiate Marketing: "
            + (" | ".join(campaigns) if campaigns else "No new campaigns.")
            + hint
        )
        return {"status": "ok", "message": msg, "next_phase": "get_food"}

    # ─── Develop, Lobby, Expand Chain (star actions) ─────────────────────

    def _do_develop(self) -> dict:
        """DEVELOP phase: place house/garden if star on card."""
        self.state.log(f"=== DEVELOP ===", "phase")

        stars = getattr(self.state, "pending_stars", [])
        back = (
            self.state.current_back_card.get("back", {})
            if self.state.current_back_card
            else {}
        )
        map_tiles = (
            self.state.current_front_card.get("map_tiles", {})
            if self.state.current_front_card
            else {}
        )
        dev_tile = map_tiles.get("develop_lobby", 1)

        has_develop = "develop" in stars
        dev_type = back.get("develop_type")
        dev_house = back.get("develop_house")
        if has_develop and dev_type:
            if dev_type == "garden":
                desc = (
                    f"Place garden next to house #{dev_house}"
                    if dev_house
                    else "Place garden"
                )
            else:
                desc = f"Place house #{dev_house}" if dev_house else "Place house"
            self.state.log(f"DEVELOP ★: {desc}. Target tile: {dev_tile}", "develop")
            self.state.phase = GamePhase.LOBBY
            hint = self._worktime_turn_hint()
            return {
                "status": "ok",
                "message": f"DEVELOP: {desc}. Target tile: {dev_tile}" + hint,
                "develop_type": dev_type,
                "develop_house": dev_house,
                "map_tile": dev_tile,
                "next_phase": "lobby",
            }

        self.state.phase = GamePhase.LOBBY
        hint = self._worktime_turn_hint()
        return {
            "status": "ok",
            "message": "No DEVELOP star. Skipping." + hint,
            "next_phase": "lobby",
        }

    def _do_lobby(self) -> dict:
        """LOBBY phase: place road/park if star on card."""
        self.state.log(f"=== LOBBY ===", "phase")

        stars = getattr(self.state, "pending_stars", [])
        back = (
            self.state.current_back_card.get("back", {})
            if self.state.current_back_card
            else {}
        )
        map_tiles = (
            self.state.current_front_card.get("map_tiles", {})
            if self.state.current_front_card
            else {}
        )
        dev_tile = map_tiles.get("develop_lobby", 1)

        lobby_type = back.get("lobby_type")
        lobby_house = back.get("lobby_house")
        if "lobby" in stars and lobby_type:
            if lobby_type == "park":
                desc = (
                    f"Place park next to house #{lobby_house}"
                    if lobby_house
                    else "Place park"
                )
            else:
                desc = "Place road"
            self.state.log(f"LOBBY ★: {desc}. Target tile: {dev_tile}", "lobby")
            self.state.phase = GamePhase.EXPAND_CHAIN
            hint = self._worktime_turn_hint()
            return {
                "status": "ok",
                "message": f"LOBBY: {desc}. Target tile: {dev_tile}" + hint,
                "lobby_type": lobby_type,
                "lobby_house": lobby_house,
                "map_tile": dev_tile,
                "next_phase": "expand_chain",
            }

        self.state.phase = GamePhase.EXPAND_CHAIN
        hint = self._worktime_turn_hint()
        return {
            "status": "ok",
            "message": "No LOBBY star. Skipping." + hint,
            "next_phase": "expand_chain",
        }

    def _do_expand_chain(self) -> dict:
        """EXPAND CHAIN phase: place new restaurant if star on card."""
        self.state.log(f"=== EXPAND CHAIN ===", "phase")

        stars = getattr(self.state, "pending_stars", [])
        map_tiles = (
            self.state.current_front_card.get("map_tiles", {})
            if self.state.current_front_card
            else {}
        )
        map_tile = map_tiles.get("expand_chain", 1)

        if (
            "expand_chain" in stars
            and len(self.state.restaurants) < self.state.max_restaurants
        ):
            self.state.pending_input = {
                "type": "restaurant_placed",
                "prompt": f"EXPAND CHAIN: Place a new restaurant. Target map tile: {map_tile}",
                "prompt_es": f"EXPANDIR CADENA: Coloca un nuevo restaurante. Casilla objetivo: {map_tile}",
                "fields": [
                    {
                        "name": "tile",
                        "label": "Map tile placed on",
                        "label_es": "Casilla donde se coloca",
                        "type": "number",
                        "min": 1,
                        "max": 9,
                        "default": map_tile,
                    }
                ],
            }
            self.state.phase = GamePhase.WAITING_FOR_INPUT
            return {
                "status": "waiting",
                "message": f"EXPAND CHAIN ★: Place restaurant on tile {map_tile}.",
                "input_needed": self.state.pending_input,
            }

        if "expand_chain" in stars:
            self.state.log("Max restaurants reached. Cannot expand.", "expand")
        else:
            self.state.log("No EXPAND CHAIN star.", "expand")

        # Coffee shop check
        if "coffee_shop" in stars and self.state.modules.get("coffee"):
            coffee_tile = map_tiles.get("coffee_shop", 1)
            self.state.log(
                f"COFFEE SHOP ★: Place a coffee shop if available. Target tile: {coffee_tile}",
                "expand",
            )
            self.state.phase = GamePhase.DINNERTIME
            hint = self._worktime_turn_hint(is_last_worktime=True)
            return {
                "status": "ok",
                "message": f"COFFEE SHOP: Place a coffee shop if available. Target tile: {coffee_tile}"
                + hint,
                "next_phase": "dinnertime",
            }

        self.state.phase = GamePhase.DINNERTIME
        hint = self._worktime_turn_hint(is_last_worktime=True)
        return {
            "status": "ok",
            "message": "No expansion. Proceeding to Dinnertime." + hint,
            "next_phase": "dinnertime",
        }

    def _continue_after_stars(self) -> dict:
        """Continue the phase flow after handling star actions."""
        stars = getattr(self.state, "pending_stars", [])

        # Check if we still need coffee shop
        if "coffee_shop" in stars and self.state.modules.get("coffee"):
            self.state.log("COFFEE SHOP ★: Place a coffee shop if available.", "expand")

        self.state.phase = GamePhase.DINNERTIME
        hint = self._worktime_turn_hint(is_last_worktime=True)
        return {
            "status": "ok",
            "message": "Proceeding to Dinnertime." + hint,
            "next_phase": "dinnertime",
        }

    # ─── Dinnertime ──────────────────────────────────────────────────────

    def _do_dinnertime_prompt(self) -> dict:
        """DINNERTIME: prompt player for earnings comparison."""
        self.state.log(f"=== DINNERTIME ===", "phase")

        price = self.state.tracks.price_distance.position
        waitresses = self.state.tracks.waitresses.position
        driveins = "NO" if self.state.no_driveins_this_turn else "YES"

        info = (
            f"Price+Distance: ${price} | Waitresses: {waitresses} | "
            f"Drive-ins: {driveins} | Cash multiplier: {self.state.bonus_cash_multiplier}x"
        )
        self.state.log(info, "dinnertime")

        self.state.pending_input = {
            "type": "dinnertime_result",
            "prompt": f"Enter dinnertime earnings. {info}",
            "prompt_es": f"Introduce las ganancias de la cena. {info}",
            "fields": [
                {
                    "name": "chain_earned",
                    "label": "Chain earned ($)",
                    "label_es": "La Cadena ganó ($)",
                    "type": "number",
                    "min": 0,
                },
                {
                    "name": "player_earned",
                    "label": "You earned ($)",
                    "label_es": "Tú ganaste ($)",
                    "type": "number",
                    "min": 0,
                },
            ],
        }
        self.state.phase = GamePhase.WAITING_FOR_INPUT
        return {
            "status": "waiting",
            "message": f"Dinnertime! {info}",
            "input_needed": self.state.pending_input,
        }

    # ─── Sold-items prompt helper ────────────────────────────────────────

    _FOOD_LABELS_ES = {
        "burger": "Hamburguesa",
        "pizza": "Pizza",
        "sushi": "Sushi",
        "noodle": "Fideos",
        "coffee": "Café",
        "kimchi": "Kimchi",
        "beer": "Cerveza",
        "lemonade": "Limonada",
        "softdrink": "Refresco",
    }

    def _build_sold_items_prompt(self) -> dict | None:
        """Build a WAITING_FOR_INPUT prompt asking which items were sold.

        Returns None if inventory is completely empty (nothing to sell).
        """
        fields = []
        for fi in FoodItem:
            item_key = fi.value
            count = self.state.inventory.total(item_key)
            if count <= 0:
                continue
            # Skip expansion items whose module is disabled
            if not _is_item_available(item_key, self.state.modules):
                continue
            label_en = f"{fi.label()} sold"
            label_es = f"{self._FOOD_LABELS_ES.get(item_key, fi.label())} vendido"
            fields.append(
                {
                    "name": item_key,
                    "label": label_en,
                    "label_es": label_es,
                    "type": "number",
                    "min": 0,
                    "max": count,
                    "default": 0,
                }
            )

        if not fields:
            return None

        self.state.pending_input = {
            "type": "dinnertime_sold_items",
            "prompt": "The Chain earned money! Indicate how many of each item were sold.",
            "prompt_es": "¡La Cadena ganó dinero! Indica cuántos de cada artículo se vendieron.",
            "fields": fields,
        }
        self.state.phase = GamePhase.WAITING_FOR_INPUT
        return {
            "status": "waiting",
            "message": "Indicate items sold by the Chain.",
            "input_needed": self.state.pending_input,
        }

    # ─── Payday ──────────────────────────────────────────────────────────

    def _do_payday(self) -> dict:
        """PAYDAY phase: the human player pays employee salaries.

        The Chain does not pay salaries and cannot claim the salary milestone.
        """
        self.state.log(f"=== PAYDAY ===", "phase")
        self.state.log(
            "Pay your employees their salaries. The Chain does not pay salaries.",
            "payday",
        )

        self.state.phase = GamePhase.MARKETING_CAMPAIGNS
        return {
            "status": "ok",
            "message": "Payday — Pay your employees. The Chain does not pay salaries.",
            "next_phase": "marketing_campaigns",
        }

    # ─── Marketing Campaigns (resolution) ────────────────────────────────

    def _do_marketing_campaigns(self) -> dict:
        """MARKETING CAMPAIGNS phase: resolve active campaigns.

        Decrement campaign counters and remove expired marketeers.
        This was previously done during Cleanup but belongs here per the rules.
        """
        self.state.log(f"=== MARKETING CAMPAIGNS ===", "phase")

        msgs = []
        for slot in self.state.marketeer_slots:
            if slot.marketeer and slot.is_busy and slot.campaigns_left is not None:
                # Skip eternal campaigns (Rural Marketeer: campaigns_left == -1)
                if slot.campaigns_left == -1:
                    self.state.log(
                        f"{slot.marketeer} (slot {slot.slot_number}): "
                        f"permanent campaign ({slot.market_item}, #{slot.campaign_number}).",
                        "marketing_campaigns",
                    )
                    msgs.append(
                        f"{slot.marketeer} (slot {slot.slot_number}): permanent"
                    )
                    continue
                slot.campaigns_left -= 1
                if slot.campaigns_left <= 0:
                    self.state.log(
                        f"{slot.marketeer} (slot {slot.slot_number}) campaign expired! "
                        f"Marketing {slot.market_item}, campaign #{slot.campaign_number}. "
                        f"Marketeer removed.",
                        "marketing_campaigns",
                    )
                    msgs.append(
                        f"{slot.marketeer} (slot {slot.slot_number}) campaign expired — removed"
                    )
                    slot.marketeer = None
                    slot.is_busy = False
                    slot.market_item = None
                    slot.campaign_number = None
                    slot.campaigns_left = None
                    slot.placed_turn = None
                else:
                    self.state.log(
                        f"{slot.marketeer} (slot {slot.slot_number}): "
                        f"{slot.campaigns_left} campaign(s) remaining "
                        f"({slot.market_item}, #{slot.campaign_number}).",
                        "marketing_campaigns",
                    )
                    msgs.append(
                        f"{slot.marketeer} (slot {slot.slot_number}): "
                        f"{slot.campaigns_left} left"
                    )

        if not msgs:
            self.state.log("No active marketing campaigns.", "marketing_campaigns")

        self.state.phase = GamePhase.CLEANUP
        return {
            "status": "ok",
            "message": "Marketing Campaigns: "
            + (" | ".join(msgs) if msgs else "No active campaigns."),
            "next_phase": "cleanup",
        }

    # ─── Cleanup ─────────────────────────────────────────────────────────

    def _do_cleanup(self) -> dict:
        """CLEANUP phase: apply all cleanup actions from the back card."""
        self.state.log(f"=== CLEANUP ===", "phase")

        back = (
            self.state.current_back_card.get("back", {})
            if self.state.current_back_card
            else {}
        )
        cleanup_actions = back.get("cleanup_actions", [])

        msgs = []
        shuffle_needed = False

        for ca in cleanup_actions:
            ca_type = ca["type"]
            ca_value = ca["value"]

            if ca_type == "get_kimchi" and ca_value != 0:
                # GET KIMCHI: if Kimchi Master is in employee pile and kimchi module active
                if (
                    "Kimchi Master" in [s.marketeer for s in self.state.marketeer_slots]
                    or "Kimchi Master" in self.state.employee_pile
                ):
                    if self.state.modules.get("kimchi"):
                        self.state.inventory.add("kimchi", 1)
                        msgs.append("Kimchi +1")
                        self.state.log("Kimchi Master: +1 kimchi.", "cleanup")

            elif ca_type == "move_distance" and ca_value != 0:
                old, new, _ = self.state.tracks.price_distance.move(ca_value)
                msgs.append(f"Distance: {old}→{new}")
                self.state.log(f"Cleanup: Price+Distance {old} → {new}", "cleanup")
                self._check_track_milestones()

            elif ca_type == "move_waitress" and ca_value != 0:
                old, new, _ = self.state.tracks.waitresses.move(ca_value)
                msgs.append(f"Waitress: {old}→{new}")
                self.state.log(f"Cleanup: Waitresses {old} → {new}", "cleanup")

            elif ca_type == "inventory_drop" and ca_value != 0:
                drop_details = self.state.inventory.inventory_drop()
                if drop_details:
                    msgs.append(f"Inventory drop: {', '.join(drop_details)}")
                    self.state.log(
                        f"Cleanup: Inventory drop — {', '.join(drop_details)}",
                        "cleanup",
                    )
                else:
                    msgs.append("Inventory drop (no items on top row)")
                    self.state.log(
                        "Cleanup: Inventory drop — nothing to drop.", "cleanup"
                    )

            elif ca_type == "move_recruit_train" and ca_value != 0:
                old, new, crossed = self.state.tracks.recruit_train.move(ca_value)
                msgs.append(f"R&T track: {old}→{new}")
                self.state.log(f"Cleanup: Recruit & Train {old} → {new}", "cleanup")
                self._check_track_milestones()
                if crossed:
                    shuffle_needed = True

        # Cap inventory (max 10, excluding coffee)
        cap_details = self.state.inventory.cap_inventory()
        if cap_details:
            msgs.append(f"Inventory capped: {', '.join(cap_details)}")
            self.state.log(
                f"Cleanup: Inventory capped — {', '.join(cap_details)}", "cleanup"
            )

        # Shuffle if needed
        if shuffle_needed:
            self.state.reshuffle_deck()
            self.state.log(
                "SHUFFLE triggered! Action Deck reshuffled with discard pile.",
                "cleanup",
            )
            msgs.append("ACTION DECK SHUFFLED!")

            # If competition card ends up on top after shuffle, shuffle again
            top = self.state.action_deck.peek()
            while top and top.card_type in (CardType.WARM, CardType.COOL):
                self.state.reshuffle_deck()
                self.state.log(
                    "Competition card on top after shuffle — reshuffling.", "cleanup"
                )
                top = self.state.action_deck.peek()

        # End of turn — campaign decrement is now handled in Marketing Campaigns phase
        # Advance to next turn
        self.state.turn_number += 1
        self.state.phase = GamePhase.RESTRUCTURING

        # Clear pending stars
        self.state.pending_stars = []

        result_msg = "Cleanup complete: " + (
            " | ".join(msgs) if msgs else "no adjustments"
        )
        self.state.log(
            f"Turn {self.state.turn_number - 1} complete. Starting Turn {self.state.turn_number}.",
            "phase",
        )

        return {
            "status": "ok",
            "message": result_msg,
            "next_phase": "restructuring",
        }

    # ─── Undo ────────────────────────────────────────────────────────────

    def undo(self) -> dict:
        """Undo the last action by restoring previous state snapshot."""
        if not self.state.history:
            return {"status": "error", "message": "Nothing to undo."}

        snapshot_json = self.state.history.pop()
        snapshot = __import__("json").loads(snapshot_json)

        # Preserve history stack
        history = self.state.history

        # Rebuild state from snapshot (simplified — restores key fields)
        self.state.turn_number = snapshot.get("turn_number", 0)
        self.state.phase = GamePhase(snapshot.get("phase", "setup"))
        self.state.bank_breaks = snapshot.get("bank_breaks", 0)
        self.state.current_front_card = snapshot.get("current_front_card")
        self.state.current_back_card = snapshot.get("current_back_card")
        self.state.current_competition_card = snapshot.get("current_competition_card")
        self.state.pending_input = snapshot.get("pending_input")
        self.state.is_first_turn = snapshot.get("is_first_turn", False)
        self.state.chain_cash_this_turn = snapshot.get("chain_cash_this_turn", 0)
        self.state.chain_total_cash = snapshot.get("chain_total_cash", 0)
        self.state.bonus_cash_multiplier = snapshot.get("bonus_cash_multiplier", 1.0)
        self.state.no_driveins_this_turn = snapshot.get("no_driveins_this_turn", False)
        self.state.milestones_claimed = snapshot.get("milestones_claimed", [])
        self.state.restaurants = snapshot.get("restaurants", [])
        self.state.employee_pile = snapshot.get("employee_pile", [])
        self.state.mass_marketeer = snapshot.get("mass_marketeer", False)
        self.state.pending_stars = snapshot.get("pending_stars", [])
        self.state.cards_drawn_this_cycle = snapshot.get("cards_drawn_this_cycle", 0)
        self.state.deck_cycles = snapshot.get("deck_cycles", 0)
        self.state.total_cards_drawn = snapshot.get("total_cards_drawn", 0)

        # Restore decks from snapshot card lists
        from .cards import create_all_decks as _create_all_decks

        _ad, _wd, _cd = _create_all_decks()
        _all_cards = {}
        for c in _ad.cards + _wd.cards + _cd.cards:
            _all_cards[(c.card_type.value, c.card_number)] = c

        for deck_key, deck_attr in [
            ("action_deck", "action_deck"),
            ("warm_deck", "warm_deck"),
            ("cool_deck", "cool_deck"),
        ]:
            deck_snap = snapshot.get(deck_key, {})
            card_list = deck_snap.get("cards", [])
            if card_list:
                new_deck = Deck(name=deck_snap.get("name", deck_key))
                for cd in card_list:
                    key = (cd["card_type"], cd["card_number"])
                    if key in _all_cards:
                        new_deck.cards.append(_all_cards[key])
                setattr(self.state, deck_attr, new_deck)

        # Restore tracks
        tracks_data = snapshot.get("tracks", {})
        if "recruit_train" in tracks_data:
            self.state.tracks.recruit_train.position = tracks_data["recruit_train"][
                "position"
            ]
        if "price_distance" in tracks_data:
            self.state.tracks.price_distance.position = tracks_data["price_distance"][
                "position"
            ]
        if "waitresses" in tracks_data:
            self.state.tracks.waitresses.position = tracks_data["waitresses"][
                "position"
            ]
        if "competition" in tracks_data:
            self.state.tracks.competition = CompetitionLevel(
                tracks_data["competition"]["level"]
            )

        # Restore inventory
        inv_data = snapshot.get("inventory", {})
        for item, vals in inv_data.items():
            if item in self.state.inventory.items:
                if isinstance(vals, dict):
                    # Migration: old format had {top, bottom}
                    self.state.inventory.items[item] = vals.get(
                        "count", vals.get("top", 0) + vals.get("bottom", 0)
                    )
                else:
                    self.state.inventory.items[item] = vals

        # Restore marketeer slots
        slots_data = snapshot.get("marketeer_slots", [])
        for i, sd in enumerate(slots_data):
            if i < len(self.state.marketeer_slots):
                self.state.marketeer_slots[i].marketeer = sd.get("marketeer")
                self.state.marketeer_slots[i].is_busy = sd.get("is_busy", False)

        self.state.history = history
        self.state.log("Undo performed.", "system")

        return {"status": "ok", "message": "Last action undone."}

    # ─── Quick mode ──────────────────────────────────────────────────────

    def quick_draw(self) -> dict:
        """Quick mode: just flip the next card and show it."""
        top_card = self.state.action_deck.draw()
        if not top_card:
            return {"status": "error", "message": "Deck is empty!"}

        self.state.current_back_card = top_card.to_dict()
        next_card = self.state.action_deck.peek()
        self.state.current_front_card = next_card.to_dict() if next_card else None
        self.state.action_deck.place_under(top_card)

        # Update deck progress counters
        self.state.total_cards_drawn += 1
        self.state.cards_drawn_this_cycle += 1
        if self.state.cards_drawn_this_cycle >= self.state.action_deck.size():
            self.state.deck_cycles += 1
            self.state.cards_drawn_this_cycle = 0

        return {
            "status": "ok",
            "back_card": self.state.current_back_card,
            "front_card": self.state.current_front_card,
            "deck_size": self.state.action_deck.size(),
        }

    def quick_update_track(self, track_name: str, value: int) -> dict:
        """Quick mode: manually set a track value."""
        if track_name == "recruit_train":
            self.state.tracks.recruit_train.position = max(1, min(4, value))
        elif track_name == "price_distance":
            self.state.tracks.price_distance.position = max(6, min(10, value))
        elif track_name == "waitresses":
            self.state.tracks.waitresses.position = max(0, min(4, value))
        elif track_name == "competition":
            self.state.tracks.competition = CompetitionLevel(max(0, min(4, value)))
        else:
            return {"status": "error", "message": f"Unknown track: {track_name}"}

        return {"status": "ok", "tracks": self.state.tracks.to_dict()}
