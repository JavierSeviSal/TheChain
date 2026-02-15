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
    FoodItem,
)
from .cards import create_all_decks


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

    def advance_phase(self) -> dict:
        """Advance to the next phase and execute it. Returns result dict."""
        self.state.save_snapshot()
        phase = self.state.phase

        handlers = {
            GamePhase.SETUP: self._do_first_turn,
            GamePhase.RESTRUCTURING: self._do_restructuring,
            GamePhase.RECRUIT_TRAIN: self._do_recruit_train,
            GamePhase.GET_FOOD: self._do_get_food,
            GamePhase.MARKETING: self._do_marketing,
            GamePhase.DEVELOP: self._do_develop,
            GamePhase.LOBBY: self._do_lobby,
            GamePhase.EXPAND_CHAIN: self._do_expand_chain,
            GamePhase.DINNERTIME: self._do_dinnertime_prompt,
            GamePhase.CLEANUP: self._do_cleanup,
            GamePhase.GAME_OVER: lambda: {
                "status": "game_over",
                "message": "The game has ended.",
            },
        }

        handler = handlers.get(phase)
        if handler:
            return handler()
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
            self.state.turn_number = 1
            self.state.phase = GamePhase.RESTRUCTURING
            return {
                "status": "ok",
                "message": "First restaurant placed. Begin Turn 1!",
                "next_phase": "restructuring",
            }

        elif input_type == "dinnertime_result":
            chain_earned = input_data.get("chain_earned", 0)
            player_earned = input_data.get("player_earned", 0)

            # Apply bonus cash multiplier
            chain_earned = int(chain_earned * self.state.bonus_cash_multiplier)
            self.state.chain_cash_this_turn = chain_earned

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

            self.state.phase = GamePhase.CLEANUP
            return {
                "status": "ok",
                "message": "Dinnertime resolved. Proceeding to Cleanup.",
                "next_phase": "cleanup",
            }

        elif input_type == "demand_info":
            # Player provides which food items have demand on the map
            self.state.pending_input = None
            return self._resolve_get_food(input_data)

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

        return {"status": "error", "message": f"Unknown input type: {input_type}"}

    # ─── First turn ──────────────────────────────────────────────────────

    def _do_first_turn(self) -> dict:
        """Handle the Chain's first turn: just place first restaurant."""
        self.state.log("=== THE CHAIN'S FIRST TURN ===", "phase")
        self.state.log("The Chain is first in turn order.", "setup")

        self.state.pending_input = {
            "type": "first_restaurant_placed",
            "prompt": "Place The Chain's first restaurant on the board.",
            "prompt_es": "Coloca el primer restaurante de La Cadena en el tablero.",
            "fields": [
                {
                    "name": "tile",
                    "label": "Map tile (1-9)",
                    "label_es": "Casilla del mapa (1-9)",
                    "type": "number",
                    "min": 1,
                    "max": 9,
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

        # Place the flipped card under the deck (it's been used)
        self.state.action_deck.place_under(top_card)

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

        # STEP 3: Check if competition card is now on top
        top_after = self.state.action_deck.peek()
        if top_after and top_after.card_type in (CardType.WARM, CardType.COOL):
            resolved = self._check_resolve_competition(top_after)
            if resolved:
                result_msgs.append(resolved)
            # Update the front card to whatever is now on top
            next_after = self.state.action_deck.peek()
            if next_after:
                self.state.current_front_card = next_after.to_dict()

        self.state.phase = GamePhase.RECRUIT_TRAIN
        return {
            "status": "ok",
            "message": "Restructuring complete. " + " ".join(result_msgs),
            "next_phase": "recruit_train",
            "current_back_card": self.state.current_back_card,
            "current_front_card": self.state.current_front_card,
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
            if card2:
                self.state.action_deck.place_under(card2)
                msgs.append(f"Warm card placed under Action Deck.")
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

        elif level == CompetitionLevel.COLD:
            card1 = self.state.cool_deck.draw()
            card2 = self.state.cool_deck.draw()
            if card1:
                self.state.action_deck.place_on_top(card1)
                msgs.append("COLD: Cool card placed on top of Action Deck.")
            if card2:
                self.state.action_deck.place_under(card2)
                msgs.append("Cool card placed under Action Deck.")
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

        if should_resolve:
            # Remove from action deck and resolve
            self.state.action_deck.draw()  # Remove it
            msg = self._resolve_competition_card(card)
            # Place back under its own deck
            if card.card_type == CardType.WARM:
                self.state.warm_deck.place_under(card)
            else:
                self.state.cool_deck.place_under(card)
            return msg
        else:
            # Don't resolve; move under action deck
            self.state.action_deck.draw()
            self.state.action_deck.place_under(card)
            self.state.log(
                f"Competition card (#{card.card_number} {card.card_type.value}) on top "
                f"does not match track ({level.label()}). Placed under Action Deck.",
                "restructuring",
            )
            return f"Competition card not resolved (track is {level.label()})."

    def _resolve_competition_card(self, card: Card) -> str:
        """Resolve a competition card's effect."""
        if not card.competition_effect:
            return "No effect."

        effect = card.competition_effect
        msgs = []

        # Apply food adjustments
        for adj in effect.food_adjustments:
            item = adj["item"]
            amount = adj["amount"]
            if item == "all_demand":
                # Will be resolved during GET FOOD
                msgs.append(f"All demand +{amount}")
            elif item == "most_demand":
                msgs.append(f"Most demand +{amount}")
            else:
                self.state.inventory.add(item, amount)
                msgs.append(f"+{amount} {item}")

        # Type-specific effects
        if effect.effect_type == "expand_chain":
            if len(self.state.restaurants) < self.state.max_restaurants:
                self.state.pending_input = {
                    "type": "restaurant_placed",
                    "prompt": f"Place a new restaurant (EXPAND CHAIN from Warm card). Target tile: {effect.map_tile}",
                    "prompt_es": f"Coloca un nuevo restaurante (EXPANDIR CADENA por carta Cálida). Casilla objetivo: {effect.map_tile}",
                    "fields": [
                        {
                            "name": "tile",
                            "label": "Map tile",
                            "label_es": "Casilla del mapa",
                            "type": "number",
                            "min": 1,
                            "max": 9,
                            "default": effect.map_tile,
                        }
                    ],
                }
                msgs.append(
                    f"EXPAND CHAIN → place restaurant on tile {effect.map_tile}"
                )
            else:
                msgs.append("EXPAND CHAIN → max restaurants reached, skipped.")

        elif effect.effect_type == "coffee_shop_or_expand":
            if self.state.modules.get("coffee"):
                msgs.append("COFFEE SHOP → place a coffee shop if available.")
            elif len(self.state.restaurants) < self.state.max_restaurants:
                msgs.append(f"EXPAND CHAIN → place restaurant (coffee not in play).")
            if effect.inventory_boost:
                self.state.inventory.inventory_boost()
                msgs.append("INVENTORY BOOST: moved tokens from bottom to top row.")

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

        result = " | ".join(msgs)
        self.state.log(
            f"Resolved {card.card_type.value} card #{card.card_number}: {result}",
            "competition",
        )
        return result

    # ─── Recruit & Train ─────────────────────────────────────────────────

    def _do_recruit_train(self) -> dict:
        """RECRUIT & TRAIN phase: execute actions based on open slots."""
        self.state.log(f"=== RECRUIT & TRAIN ===", "phase")

        front_card_data = self.state.current_front_card
        if not front_card_data or "front" not in front_card_data:
            self.state.phase = GamePhase.GET_FOOD
            return {
                "status": "ok",
                "message": "No front card available. Skipping Recruit & Train.",
                "next_phase": "get_food",
            }

        open_slots = self.state.tracks.get_open_slots()
        actions = front_card_data["front"]["actions"]
        stars = front_card_data["front"]["stars"]

        # Determine which actions to take based on open slots
        # 4 slots: all 4 actions (descending: 4,3,2,1)
        # 3 slots: skip top, take 3 descending (4,3,2)
        # 2 slots: skip top 2, take 2 descending (4,3)
        # 1 slot: skip top 3, take bottom only (4)

        skip = 4 - open_slots
        active_actions = actions[skip:]  # Take from skip index to end
        # Execute in descending order (bottom to top of the selected ones)
        active_actions_reversed = list(reversed(active_actions))

        result_msgs = []
        for action_data in active_actions_reversed:
            msg = self._execute_recruit_action(action_data)
            result_msgs.append(msg)

        self.state.log(
            f"Open slots: {open_slots}. Executed {len(active_actions)} actions.",
            "recruit_train",
        )

        # Store stars for later phases
        self.state._pending_stars = stars  # Will check in develop/lobby/expand

        self.state.phase = GamePhase.GET_FOOD
        return {
            "status": "ok",
            "message": f"Recruit & Train complete ({open_slots} open slots). "
            + " | ".join(result_msgs),
            "actions_taken": result_msgs,
            "next_phase": "get_food",
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
                self.state.log(
                    f"Module '{requires}' not in play. Getting {fallback} instead.",
                    "recruit_train",
                )
                self.state.inventory.add(fallback, 1)
                return f"GET FOOD: +1 {fallback} (module not in play)"
            return f"Skipped (module '{requires}' not in play)"

        if action_type == "recruit_marketeer":
            return self._recruit_marketeer(target)
        elif action_type == "recruit_employee":
            return self._recruit_employee(target)
        elif action_type == "move_distance":
            delta = int(target)
            old, new, crossed = self.state.tracks.price_distance.move(delta)
            self.state.log(f"Price+Distance: {old} → {new}", "recruit_train")
            # Check milestone: first to lower prices
            if (
                new < 10
                and "first_to_lower_prices" not in self.state.milestones_claimed
            ):
                self.state.milestones_claimed.append("first_to_lower_prices")
                self.state.log("Milestone claimed: First to Lower Prices!", "milestone")
            return f"Price+Distance: {old} → {new}"
        elif action_type == "move_waitress":
            delta = int(target)
            old, new, _ = self.state.tracks.waitresses.move(delta)
            self.state.log(f"Waitresses: {old} → {new}", "recruit_train")
            if new == 4:
                self.state.log(
                    "Waitresses reached 4! Recruit highest-ranking movie star.",
                    "recruit_train",
                )
            return f"Waitresses: {old} → {new}"
        elif action_type == "claim_milestone":
            if target not in self.state.milestones_claimed:
                self.state.milestones_claimed.append(target)
                self.state.log(f"Milestone claimed: {target}!", "milestone")
                return f"Milestone: {target}"
            return f"Milestone {target} already claimed"
        elif action_type == "get_food":
            self.state.inventory.add(target, 1)
            self.state.log(f"Get food: +1 {target}", "recruit_train")
            return f"GET FOOD: +1 {target}"

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
                return f"Recruited: {name} (slot {slot.slot_number})"

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

        # Check milestones
        if (
            self.state.tracks.get_open_slots() >= 2
            and "first_to_train" not in self.state.milestones_claimed
        ):
            self.state.milestones_claimed.append("first_to_train")
            self.state.log("Milestone claimed: First to Train Someone!", "milestone")

        if (
            self.state.tracks.get_open_slots() >= 3
            and "first_to_hire_3" not in self.state.milestones_claimed
        ):
            self.state.milestones_claimed.append("first_to_hire_3")
            self.state.log(
                "Milestone claimed: First to Hire 3 People in 1 Turn!", "milestone"
            )

        return f"Recruited: {name}"

    # ─── Get Food & Drinks ───────────────────────────────────────────────

    def _do_get_food(self) -> dict:
        """GET FOOD & DRINKS phase."""
        self.state.log(f"=== GET FOOD & DRINKS ===", "phase")

        back_card = self.state.current_back_card
        if not back_card or "back" not in back_card:
            self.state.phase = GamePhase.MARKETING
            return {
                "status": "ok",
                "message": "No back card. Skipping Get Food.",
                "next_phase": "marketing",
            }

        back = back_card["back"]
        demand_type = back.get("demand_type", "most_demand")
        food_items = back.get("food_items", [])
        multiplier = back.get("multiplier", 1)
        food_amount = self.state.tracks.get_food_amount()

        if demand_type == "specific":
            # Add specific items
            for item in food_items:
                if item in [fi.value for fi in FoodItem]:
                    if self.state.modules.get(item, True):  # Check module active
                        self.state.inventory.add(item, food_amount * multiplier)
                        self.state.log(
                            f"+{food_amount * multiplier} {item}", "get_food"
                        )
            self.state.phase = GamePhase.MARKETING
            return {
                "status": "ok",
                "message": f"Added {food_amount}× of: {', '.join(food_items)}",
                "next_phase": "marketing",
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
                            if self.state.modules.get(fi.value, True)
                        ],
                    },
                    {
                        "name": "most_demand_item",
                        "label": "Item with MOST demand tokens",
                        "label_es": "Item con MÁS fichas de demanda",
                        "type": "select",
                        "options": [
                            fi.value
                            for fi in FoodItem
                            if self.state.modules.get(fi.value, True)
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
        most_demand_item = input_data.get("most_demand_item", "")

        added = []
        if demand_type == "all_demand":
            for item in items_with_demand:
                amount = food_amount * multiplier
                self.state.inventory.add(item, amount)
                added.append(f"+{amount} {item}")
                self.state.log(f"All demand: +{amount} {item}", "get_food")
        elif demand_type == "most_demand":
            if most_demand_item:
                amount = food_amount * multiplier
                self.state.inventory.add(most_demand_item, amount)
                added.append(f"+{amount} {most_demand_item}")
                self.state.log(f"Most demand: +{amount} {most_demand_item}", "get_food")

        self.state.phase = GamePhase.MARKETING
        return {
            "status": "ok",
            "message": f"Food added: {', '.join(added) if added else 'none'}",
            "next_phase": "marketing",
        }

    # ─── Marketing ───────────────────────────────────────────────────────

    def _do_marketing(self) -> dict:
        """MARKETING phase: activate newly placed marketeers."""
        self.state.log(f"=== MARKETING ===", "phase")

        campaigns = []
        for slot in self.state.marketeer_slots:
            if slot.marketeer and not slot.is_busy:
                slot.is_busy = True
                campaigns.append(
                    f"{slot.marketeer} (slot {slot.slot_number}) initiates marketing campaign"
                )
                self.state.log(
                    f"{slot.marketeer} starts a marketing campaign.", "marketing"
                )

        if self.state.mass_marketeer:
            campaigns.append("Mass Marketeer runs additional marketing campaign")
            self.state.log(
                "Mass Marketeer runs additional marketing campaign phase.", "marketing"
            )

        # Check for stars from current card
        self.state.phase = GamePhase.DEVELOP
        msg = "Marketing: " + (
            " | ".join(campaigns) if campaigns else "No new campaigns."
        )
        return {"status": "ok", "message": msg, "next_phase": "develop"}

    # ─── Develop, Lobby, Expand Chain (star actions) ─────────────────────

    def _do_develop(self) -> dict:
        """DEVELOP phase: place house/garden if star on card."""
        self.state.log(f"=== DEVELOP ===", "phase")

        stars = getattr(self.state, "_pending_stars", [])
        back = (
            self.state.current_back_card.get("back", {})
            if self.state.current_back_card
            else {}
        )

        if "develop" in stars and back.get("develop_target"):
            target = back["develop_target"]
            self.state.log(f"DEVELOP ★: Place {target}.", "develop")
            self.state.phase = GamePhase.LOBBY
            return {
                "status": "ok",
                "message": f"DEVELOP: Place {target.replace('_', ' ')}.",
                "instruction": target,
                "next_phase": "lobby",
            }

        self.state.phase = GamePhase.LOBBY
        return {
            "status": "ok",
            "message": "No DEVELOP star. Skipping.",
            "next_phase": "lobby",
        }

    def _do_lobby(self) -> dict:
        """LOBBY phase: place road/park if star on card."""
        self.state.log(f"=== LOBBY ===", "phase")

        stars = getattr(self.state, "_pending_stars", [])
        back = (
            self.state.current_back_card.get("back", {})
            if self.state.current_back_card
            else {}
        )

        if "lobby" in stars and back.get("lobby_target"):
            target = back["lobby_target"]
            self.state.log(f"LOBBY ★: Place {target}.", "lobby")
            self.state.phase = GamePhase.EXPAND_CHAIN
            return {
                "status": "ok",
                "message": f"LOBBY: Place {target.replace('_', ' ')}.",
                "instruction": target,
                "next_phase": "expand_chain",
            }

        self.state.phase = GamePhase.EXPAND_CHAIN
        return {
            "status": "ok",
            "message": "No LOBBY star. Skipping.",
            "next_phase": "expand_chain",
        }

    def _do_expand_chain(self) -> dict:
        """EXPAND CHAIN phase: place new restaurant if star on card."""
        self.state.log(f"=== EXPAND CHAIN ===", "phase")

        stars = getattr(self.state, "_pending_stars", [])
        front = (
            self.state.current_front_card.get("front", {})
            if self.state.current_front_card
            else {}
        )
        map_tile = front.get("map_tile", 1)

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
            self.state.log("COFFEE SHOP ★: Place a coffee shop if available.", "expand")
            self.state.phase = GamePhase.DINNERTIME
            return {
                "status": "ok",
                "message": "COFFEE SHOP: Place a coffee shop if available.",
                "next_phase": "dinnertime",
            }

        self.state.phase = GamePhase.DINNERTIME
        return {
            "status": "ok",
            "message": "No expansion. Proceeding to Dinnertime.",
            "next_phase": "dinnertime",
        }

    def _continue_after_stars(self) -> dict:
        """Continue the phase flow after handling star actions."""
        stars = getattr(self.state, "_pending_stars", [])

        # Check if we still need coffee shop
        if "coffee_shop" in stars and self.state.modules.get("coffee"):
            self.state.log("COFFEE SHOP ★: Place a coffee shop if available.", "expand")

        self.state.phase = GamePhase.DINNERTIME
        return {
            "status": "ok",
            "message": "Proceeding to Dinnertime.",
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

        # GET KIMCHI: if Kimchi Master is in employee pile
        if (
            "Kimchi Master" in [s.marketeer for s in self.state.marketeer_slots]
            or "Kimchi Master" in self.state.employee_pile
        ):
            if self.state.modules.get("kimchi"):
                self.state.inventory.add("kimchi", 1)
                msgs.append("Kimchi +1")
                self.state.log("Kimchi Master: +1 kimchi.", "cleanup")

        shuffle_needed = False

        for ca in cleanup_actions:
            ca_type = ca["type"]
            ca_value = ca["value"]

            if ca_type == "move_distance" and ca_value != 0:
                old, new, _ = self.state.tracks.price_distance.move(ca_value)
                msgs.append(f"Distance: {old}→{new}")
                self.state.log(f"Cleanup: Price+Distance {old} → {new}", "cleanup")

            elif ca_type == "move_waitress" and ca_value != 0:
                old, new, _ = self.state.tracks.waitresses.move(ca_value)
                msgs.append(f"Waitress: {old}→{new}")
                self.state.log(f"Cleanup: Waitresses {old} → {new}", "cleanup")

            elif ca_type == "inventory_drop":
                self.state.inventory.inventory_drop()
                msgs.append("Inventory drop (top→bottom)")
                self.state.log("Cleanup: Inventory drop.", "cleanup")

            elif ca_type == "move_recruit_train" and ca_value != 0:
                old, new, crossed = self.state.tracks.recruit_train.move(ca_value)
                msgs.append(f"R&T track: {old}→{new}")
                self.state.log(f"Cleanup: Recruit & Train {old} → {new}", "cleanup")
                if crossed:
                    shuffle_needed = True

        # Cap inventory
        self.state.inventory.cap_inventory()

        # Shuffle if needed
        if shuffle_needed:
            self.state.action_deck.shuffle()
            self.state.log("SHUFFLE triggered! Action Deck reshuffled.", "cleanup")
            msgs.append("ACTION DECK SHUFFLED!")

            # If competition card ends up on top after shuffle, shuffle again
            top = self.state.action_deck.peek()
            while top and top.card_type in (CardType.WARM, CardType.COOL):
                self.state.action_deck.shuffle()
                self.state.log(
                    "Competition card on top after shuffle — reshuffling.", "cleanup"
                )
                top = self.state.action_deck.peek()

        # End of turn — return marketeers whose campaigns ended
        for slot in self.state.marketeer_slots:
            if slot.marketeer and slot.is_busy:
                # In a full implementation, we'd track campaign duration
                # For now, marketeers stay busy until manually released
                pass

        # Advance to next turn
        self.state.turn_number += 1
        self.state.phase = GamePhase.RESTRUCTURING

        # Clear pending stars
        if hasattr(self.state, "_pending_stars"):
            delattr(self.state, "_pending_stars")

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
        self.state.pending_input = snapshot.get("pending_input")
        self.state.is_first_turn = snapshot.get("is_first_turn", False)
        self.state.chain_cash_this_turn = snapshot.get("chain_cash_this_turn", 0)
        self.state.bonus_cash_multiplier = snapshot.get("bonus_cash_multiplier", 1.0)
        self.state.no_driveins_this_turn = snapshot.get("no_driveins_this_turn", False)
        self.state.milestones_claimed = snapshot.get("milestones_claimed", [])
        self.state.restaurants = snapshot.get("restaurants", [])
        self.state.employee_pile = snapshot.get("employee_pile", [])
        self.state.mass_marketeer = snapshot.get("mass_marketeer", False)

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
                self.state.inventory.items[item]["top"] = vals.get("top", 0)
                self.state.inventory.items[item]["bottom"] = vals.get("bottom", 0)

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

        return {
            "status": "ok",
            "back_card": self.state.current_back_card,
            "front_card": self.state.current_front_card,
            "deck_size": self.state.action_deck.size(),
        }

    def quick_update_track(self, track_name: str, value: int) -> dict:
        """Quick mode: manually set a track value."""
        if track_name == "recruit_train":
            self.state.tracks.recruit_train.position = max(1, min(7, value))
        elif track_name == "price_distance":
            self.state.tracks.price_distance.position = max(6, min(10, value))
        elif track_name == "waitresses":
            self.state.tracks.waitresses.position = max(0, min(4, value))
        elif track_name == "competition":
            self.state.tracks.competition = CompetitionLevel(max(0, min(4, value)))
        else:
            return {"status": "error", "message": f"Unknown track: {track_name}"}

        return {"status": "ok", "tracks": self.state.tracks.to_dict()}
