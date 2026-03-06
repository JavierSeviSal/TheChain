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
    BASE_MILESTONES,
    EXPANSION_MILESTONES,
    MODULE_MILESTONES,
    EXPANSION_TURN2_EXPIRY,
    BASE_TO_EXPANSION_MAP,
    CAMPAIGN_TYPE_MILESTONES,
    MARKETEER_MILESTONE_MAP,
    SOLD_ITEM_MILESTONES,
    PRODUCED_ITEM_MILESTONES,
    DRINK_ITEMS,
    EMPLOYEE_EXTRA_COPIES,
    get_campaign_type,
    get_valid_campaign_numbers,
    get_active_milestones,
    is_milestone_in_active_set,
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

        # Secretly pick one of the three bank reserve cards (revealed on first bank break)
        if self.state.modules.get("reserve_prices"):
            # Reserve Prices module: use alternate Base Price cards ($5/$10/$20)
            self.state.bank_reserve_card = random.choice(["5", "10", "20"])
            self.state.log(
                "Reserve Prices module active — using alternate Base Price reserve cards.",
                "setup",
            )
        else:
            self.state.bank_reserve_card = random.choice(["100", "200", "300"])

        # Initialize milestone system based on active modules
        if self.state.modules.get("milestones"):
            self.state.milestones_turn2_tokens = list(EXPANSION_TURN2_EXPIRY)
            self.state.log(
                "Expansion Milestones active. Turn-2 tokens placed on: "
                + ", ".join(sorted(EXPANSION_TURN2_EXPIRY)),
                "setup",
            )
        else:
            self.state.milestones_turn2_tokens = []

        active_ms = get_active_milestones(self.state.modules)
        ms_type = "Expansion" if self.state.modules.get("milestones") else "Base"
        self.state.log(
            f"Milestone set: {ms_type} ({len(active_ms)} milestones)", "setup"
        )

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

    # Human-readable milestone labels — built dynamically from milestone definitions
    @staticmethod
    def _build_milestone_labels() -> dict[str, tuple[str, str]]:
        """Build a dict of milestone_key -> (en_label, es_label) from all milestone sets."""
        labels = {}
        for m in BASE_MILESTONES + EXPANSION_MILESTONES + MODULE_MILESTONES:
            labels[m["key"]] = (m["label_en"], m["label_es"])
        return labels

    MILESTONE_LABELS = {
        m["key"]: (m["label_en"], m["label_es"])
        for m in BASE_MILESTONES + EXPANSION_MILESTONES + MODULE_MILESTONES
    }

    def _milestone_skip_set(self) -> set[str]:
        """Return the set of milestone keys that should be skipped (already resolved)."""
        return (
            set(self.state.milestones_claimed)
            | set(self.state.milestones_unavailable)
            | set(self.state.milestones_expired)
            | set(self.state.pending_milestone_checks)  # legacy save compatibility
        )

    def _try_queue_milestone(self, key: str, log_label: str | None = None) -> bool:
        """Auto-claim a milestone for The Chain if it's in the active set and not already resolved.

        Adds the key to both milestones_claimed and milestones_claimed_this_round so the
        end-of-round cleanup roundup can announce it to the player.
        Returns True if the milestone was claimed.
        """
        if key in self._milestone_skip_set():
            return False
        if not is_milestone_in_active_set(key, self.state.modules):
            return False
        # Check chain_can_claim
        for m in BASE_MILESTONES + EXPANSION_MILESTONES + MODULE_MILESTONES:
            if m["key"] == key and not m.get("chain_can_claim", True):
                return False
        self.state.milestones_claimed.append(key)
        self.state.milestones_claimed_this_round.append(key)
        label = log_label or self.MILESTONE_LABELS.get(key, (key,))[0]
        self.state.log(
            f"Milestone auto-claimed: {label} (will be announced at cleanup).",
            "milestone",
        )
        return True

    def _check_track_milestones(self):
        """Queue track-based milestones for user confirmation after any track movement.

        FIRST TO TRAIN SOMEONE: R&T track reaches 2 OPEN SLOTS (position 2).
        FIRST TO HIRE 3 PEOPLE IN 1 TURN: R&T track reaches 3 OPEN SLOTS (position 3).
        FIRST TO LOWER PRICES: Price+Distance < 10 AND has inventory to serve at least one house.

        Instead of auto-claiming, milestones are queued into pending_milestone_checks
        so the user can confirm whether the milestone is still available (not already
        claimed by the human player).
        """
        open_slots = self.state.tracks.get_open_slots()

        if open_slots >= 2:
            self._try_queue_milestone("first_to_train")

        if open_slots >= 3:
            self._try_queue_milestone("first_to_hire_3")

        pd_pos = self.state.tracks.price_distance.position
        if pd_pos < 10:
            has_food = any(
                count > 0
                for item, count in self.state.inventory.items.items()
                if _is_item_available(item, self.state.modules)
            )
            if has_food:
                self._try_queue_milestone("first_to_lower_prices")

    def _prompt_pending_milestones(self, result: dict) -> dict:
        """Legacy milestone interrupt — no longer used for mid-round confirmation.

        The milestone system now auto-claims for The Chain and presents a single
        roundup prompt at the end of cleanup.  Any milestones that ended up in
        pending_milestone_checks from an older save are silently migrated into
        milestones_claimed + milestones_claimed_this_round here so they appear
        in the cleanup roundup.
        """
        # Migrate any legacy pending checks left over from old saves
        for key in list(self.state.pending_milestone_checks):
            if (
                key not in self.state.milestones_claimed
                and key not in self.state.milestones_unavailable
            ):
                self.state.milestones_claimed.append(key)
                if key not in self.state.milestones_claimed_this_round:
                    self.state.milestones_claimed_this_round.append(key)
            self.state.pending_milestone_checks.remove(key)
        # Restore legacy phase if it was saved
        if self.state.phase_before_milestone:
            self.state.phase = GamePhase(self.state.phase_before_milestone)
            self.state.phase_before_milestone = None
        return result

    def _chain_has_employee(self, name: str) -> bool:
        """Check if The Chain already has this employee/Brand Director.

        Most employees are unique (max 1 copy).  Some employees allow
        extra copies when a module is active (see EMPLOYEE_EXTRA_COPIES).
        """
        count = self.state.employee_pile.count(name)
        count += sum(1 for s in self.state.marketeer_slots if s.marketeer == name)
        count += sum(1 for c in self.state.pending_employee_checks if c["name"] == name)

        max_copies = 1
        extra = EMPLOYEE_EXTRA_COPIES.get(name)
        if extra and any(self.state.modules.get(m, False) for m in extra["modules"]):
            max_copies += extra["extra"]

        return count >= max_copies

    def _prompt_pending_employee_checks(self, result: dict) -> dict:
        """If employee availability checks are pending, intercept with a prompt."""
        if not self.state.pending_employee_checks:
            return result
        if result.get("status") in ("waiting", "game_over", "error"):
            return result

        check = self.state.pending_employee_checks[0]
        name = check["name"]

        if self.state.phase_before_employee_check is None:
            self.state.phase_before_employee_check = self.state.phase.value

        self.state.pending_input = {
            "type": "employee_available_confirm",
            "employee_check": check,
            "prompt": (
                f"🧑‍💼 The Chain wants to recruit: {name}.\n"
                f"Is this employee available? (Does the player NOT have it?)"
            ),
            "prompt_es": (
                f"🧑‍💼 La Cadena quiere reclutar: {name}.\n"
                f"¿Está este empleado disponible? (¿El jugador NO lo tiene?)"
            ),
            "fields": [
                {
                    "name": "available",
                    "label": f"Is {name} available for The Chain?",
                    "label_es": f"¿Está {name} disponible para La Cadena?",
                    "type": "select",
                    "options": ["yes", "no"],
                },
            ],
        }
        self.state.phase = GamePhase.WAITING_FOR_INPUT

        # Preserve the original R&T phase message across chained employee prompts.
        # On first entry rt_phase_message is set by _finalize_rt_partial();
        # on subsequent prompts (after user answered one) we keep using it
        # instead of the short "Recruited: X" confirmation message.
        phase_message = self.state.rt_phase_message or result.get("message", "")
        return {
            "status": "waiting",
            "message": f"Employee availability check: {name}",
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

        # Resume after a delayed phase transition (input resolved, user reviewed)
        if phase == GamePhase.WAITING_FOR_INPUT and self.state.next_phase_after_input:
            next_p = self.state.next_phase_after_input
            self.state.next_phase_after_input = None
            self.state.phase = GamePhase(next_p)
            self.state.display_phase = next_p
            phase = self.state.phase  # update local var for handler lookup

        # Resume competition card flow after the user reviewed the resolution
        elif (
            phase == GamePhase.WAITING_FOR_INPUT
            and self.state.phase_after_competition is not None
            and self.state.pending_input is None
        ):
            result = self._resume_after_competition()
            result = self._prompt_pending_employee_checks(result)
            return self._prompt_pending_milestones(result)

        # Track the phase being executed for display purposes
        # (handlers transition state.phase to the NEXT phase, but the UI
        # should show the phase that is currently running)
        elif phase != GamePhase.WAITING_FOR_INPUT:
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
            result = self._prompt_pending_employee_checks(result)
            return self._prompt_pending_milestones(result)
        return {"status": "error", "message": f"Unknown phase: {phase.value}"}

    # Input types that should auto-advance (setup flow, not game phase transitions)
    _AUTO_ADVANCE_INPUTS = {
        "first_restaurant_placed",
        "player_first_restaurant_placed",
        "milestone_confirm",  # legacy
        "milestone_player_roundup",
        "employee_available_confirm",
        "acknowledge",
        "bank_break",
    }

    def process_input(self, input_data: dict) -> dict:
        """Process player input (e.g., dinnertime earnings comparison).

        After resolving an input that completes a game phase, the phase
        transition is delayed: the result is shown to the player, and they
        must click Advance to proceed to the next phase.
        """
        self.state.save_snapshot()
        result = self._dispatch_input(input_data)

        # Delay phase transitions so the player can review results
        input_type = input_data.get("type", "")
        if (
            input_type not in self._AUTO_ADVANCE_INPUTS
            and result.get("status") == "ok"
            and result.get("next_phase")
        ):
            self.state.next_phase_after_input = result["next_phase"]
            self.state.phase = GamePhase.WAITING_FOR_INPUT
            self.state.pending_input = None

        return result

    def _dispatch_input(self, input_data: dict) -> dict:
        """Route input to the appropriate handler."""
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

            # Milestone: first to have $20 / $100 (Base milestones)
            if self.state.chain_total_cash >= 20:
                self._try_queue_milestone("first_to_have_20")
            if self.state.chain_total_cash >= 100:
                self._try_queue_milestone("first_to_have_100")

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
                        # Milestone: first item sold (Expansion milestones)
                        if key in SOLD_ITEM_MILESTONES:
                            self._try_queue_milestone(SOLD_ITEM_MILESTONES[key])

            if sold_msgs:
                self.state.log(f"Sold: {', '.join(sold_msgs)}", "dinnertime")
            else:
                self.state.log("No items sold from inventory.", "dinnertime")

            # Ketchup module milestone: Someone Sells your Demand
            # Triggers when the player earns money AND The Chain has active marketing campaigns
            if self.state.modules.get("ketchup"):
                player_earned = (
                    self.state.pending_input.get("player_earned", 0)
                    if self.state.pending_input
                    else 0
                )
                # Check using chain_cash_this_turn > 0 as a proxy for Chain having campaigns
                has_campaigns = any(s.is_busy for s in self.state.marketeer_slots)
                if has_campaigns:
                    self._try_queue_milestone("someone_sells_demand")

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
            if len(self.state.restaurants) >= self.state.max_restaurants:
                self.state.log(
                    "Competition card: max restaurants already reached, placement skipped.",
                    "competition",
                )
                self.state.pending_input = None
                return self._resume_after_competition()
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
            # First bank break — reveal the secretly chosen reserve card
            is_rp = bool(self.state.modules.get("reserve_prices"))
            if is_rp:
                self.state.log(
                    f"Reserve Prices: The Chain's base price card is ${self.state.bank_reserve_card}. "
                    f"Add $400 to the bank (2 players × $200).",
                    "game",
                )
            return {
                "status": "ok",
                "message": f"Bank break #{self.state.bank_breaks} recorded.",
                "reveal_reserve_card": self.state.bank_reserve_card,
                "reserve_prices_module": is_rp,
            }

        elif input_type == "acknowledge_competition_card":
            self.state.pending_input = None
            resolution_detail = ""
            # Resolve the competition card the player was just shown
            top = self.state.action_deck.peek()
            if top and top.card_type in (CardType.WARM, CardType.COOL):
                card_label = top.card_type.value.upper()
                card_number = top.card_number
                msg = self._check_resolve_competition(top)
                self.state.log(f"Resolved competition card: {msg}", "competition")
                comp_data = self.state.current_competition_card or {}
                was_resolved = comp_data.get("resolved", False)
                if was_resolved:
                    resolution_detail = (
                        f"{card_label} Competition Card #{card_number} resolved: {msg} "
                        f"Card placed under {card_label} deck."
                    )
                else:
                    resolution_detail = (
                        f"{card_label} Competition Card #{card_number}: "
                        f"not matched. Placed face down under the Action Deck."
                    )
                # If yet another competition card is on top, queue it
                next_top = self.state.action_deck.peek()
                if next_top and next_top.card_type in (CardType.WARM, CardType.COOL):
                    self.state.pending_competition_actions.append(
                        {"action": "check_stacked_competition"}
                    )
                final_top = self.state.action_deck.peek()
                if final_top:
                    self.state.current_front_card = final_top.to_dict()

            # Pause here so the user can review the resolution details.
            # The Advance button will call _resume_after_competition()
            # to continue with any remaining cards or the next phase.
            self.state.phase = GamePhase.WAITING_FOR_INPUT
            # pending_input stays None → advance button is enabled
            return {
                "status": "ok",
                "message": resolution_detail or "Competition card processed.",
                "competition_resolution": resolution_detail,
                "current_front_card": self.state.current_front_card,
                "current_competition_card": self.state.current_competition_card,
            }

        elif input_type == "restaurant_placed":
            tile = input_data.get("tile", 1)
            if len(self.state.restaurants) >= self.state.max_restaurants:
                self.state.log("Max restaurants reached. Placement skipped.", "expand")
                self.state.pending_input = None
                return self._continue_after_stars()
            self.state.restaurants.append(
                {"tile": tile, "position": input_data.get("position", "")}
            )
            self.state.log(f"New restaurant placed on tile {tile}.", "expand")
            # Milestone: first new restaurant (Expansion milestone)
            self._try_queue_milestone("first_new_restaurant")
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

        elif input_type == "milestone_player_roundup":
            # End-of-round milestone reconciliation.
            # joint_claims  — chain-claimed milestones the player ALSO claimed (no X token)
            # player_claims — available milestones the player claimed independently
            joint_claims = input_data.get("chain_jointly_claimed", [])
            player_claims = input_data.get("player_claimed", [])

            summary_parts = []

            for key in player_claims:
                en_name, _ = self.MILESTONE_LABELS.get(key, (key, key))
                if (
                    key not in self.state.milestones_unavailable
                    and key not in self.state.milestones_claimed
                ):
                    self.state.milestones_unavailable.append(key)
                    self.state.log(
                        f"Milestone claimed by player: {en_name}.", "milestone"
                    )
                    summary_parts.append(f"👤 {en_name}")

            for key in joint_claims:
                en_name, _ = self.MILESTONE_LABELS.get(key, (key, key))
                self.state.log(
                    f"Milestone joint claim: {en_name} (both Chain and player).",
                    "milestone",
                )
                summary_parts.append(f"🤝 {en_name}")

            # Announce chain-only claims (ones the chain claimed but player did not)
            for key in self.state.milestones_claimed_this_round:
                if key not in joint_claims:
                    en_name, _ = self.MILESTONE_LABELS.get(key, (key, key))
                    summary_parts.append(f"🏆 {en_name} (Chain only — place X token)")

            self.state.milestones_claimed_this_round.clear()
            self.state.pending_input = None

            if summary_parts:
                msg = "Milestone roundup: " + " | ".join(summary_parts)
            else:
                msg = "Milestone roundup: no changes."

            self.state.phase = GamePhase.RESTRUCTURING
            return {"status": "ok", "message": msg, "next_phase": "restructuring"}

        elif input_type == "employee_available_confirm":
            check = (self.state.pending_input or {}).get("employee_check", {})
            name = check.get("name", "")
            recruit_type = check.get("type", "employee")
            available = input_data.get("available", "yes")
            self.state.pending_input = None

            # Remove from pending checks
            if check in self.state.pending_employee_checks:
                self.state.pending_employee_checks.remove(check)

            if available == "yes":
                if recruit_type == "brand_director":
                    placed = False
                    for slot in self.state.marketeer_slots:
                        if slot.marketeer is None:
                            slot.marketeer = "Brand Director"
                            self.state.log(
                                f"Brand Director placed in Marketeer slot {slot.slot_number}.",
                                "recruit_train",
                            )
                            placed = True
                            # Milestone: Brand Director used (Expansion)
                            self._try_queue_milestone("first_brand_director_used")
                            self._try_queue_milestone("first_marketeer_used")
                            break
                    if not placed:
                        self.state.log(
                            "No marketeer slot for Brand Director.", "recruit_train"
                        )
                    msg = (
                        "Recruited: Brand Director"
                        if placed
                        else "No slot for Brand Director"
                    )
                else:
                    self.state.employee_pile.append(name)
                    self.state.log(
                        f"Recruited {name} to Employee Pile.", "recruit_train"
                    )
                    msg = f"Recruited: {name}"
            else:
                self.state.log(
                    f"{name} not available (player has it). Skipping.",
                    "recruit_train",
                )
                msg = f"{name} not available (player has it)"

            # Update the R&T result message for this employee
            self._update_rt_employee_result(name, msg)

            # If more employee checks pending, prompt next one
            if self.state.pending_employee_checks:
                return self._prompt_pending_employee_checks(
                    {"status": "ok", "message": msg}
                )

            # All employee checks resolved — restore phase
            if self.state.phase_before_employee_check:
                self.state.phase = GamePhase(self.state.phase_before_employee_check)
                self.state.phase_before_employee_check = None

            # If there are remaining R&T actions, resume step-by-step execution
            if self.state.pending_rt_actions:
                return self._resume_rt_actions()

            # All R&T actions done — finalize if we were mid-R&T
            if self.state.rt_result_msgs:
                result = self._finalize_rt_complete()
                return self._prompt_pending_milestones(result)

            # Check for pending milestones that may have queued during recruit_train
            return self._prompt_pending_milestones({"status": "ok", "message": msg})

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
        self.state.inventory.reset_delta()

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

        # ── Build structured step messages ──
        step_msgs = []

        # Step 1 summary
        step1 = f"STEP 1 — Flipped card #{top_card.card_number}."
        if next_card:
            step1 += f" Next card: #{next_card.card_number}."
        step_msgs.append(step1)

        # STEP 2: Competition Adjustment
        adj_msgs = self._competition_adjustment()
        step2 = "STEP 2 — Competition Adjustment: " + " ".join(adj_msgs)
        step_msgs.append(step2)

        # STEP 3: Queue each competition card on top for individual
        # acknowledgment so the user sees and confirms one at a time.
        top_after = self.state.action_deck.peek()
        if top_after and top_after.card_type in (CardType.WARM, CardType.COOL):
            self.state.pending_competition_actions.append(
                {"action": "check_stacked_competition"}
            )
            card_label = top_after.card_type.value.upper()
            step_msgs.append(
                f"STEP 3 — A {card_label} Competition Card (#{top_after.card_number}) "
                f"is on top of the Action Deck. Resolving next…"
            )
        else:
            step_msgs.append("STEP 3 — No competition card on top of the Action Deck.")

        # Update the front card to whatever is now on top
        final_top = self.state.action_deck.peek()
        if final_top:
            self.state.current_front_card = final_top.to_dict()

        # Turn 1: skip Order of Business — Chain is first automatically
        is_first_turn = self.state.turn_number == 1
        next_after_restructuring = (
            "recruit_train" if is_first_turn else "order_of_business"
        )

        restructuring_msg = " | ".join(step_msgs)

        # Check if any competition card effects need user interaction
        if self.state.pending_competition_actions:
            self.state.phase_after_competition = next_after_restructuring
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
                "message": restructuring_msg
                + " Turn 1: Chain goes first (Order of Business skipped).",
                "next_phase": "recruit_train",
                "current_back_card": self.state.current_back_card,
                "current_front_card": self.state.current_front_card,
            }

        self.state.phase = GamePhase.ORDER_OF_BUSINESS
        return {
            "status": "ok",
            "message": restructuring_msg,
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
            card_label = card.card_type.value.upper()
            msg = (
                f"{card_label} Competition Card #{card.card_number} does not match "
                f"track ({level.label()}). Placed face down under the Action Deck."
            )
            comp_card_data["resolution_summary"] = msg
            self.state.current_competition_card = comp_card_data
            self.state.log(
                f"Competition card (#{card.card_number} {card.card_type.value}) on top "
                f"does not match track ({level.label()}). Placed under action deck.",
                "restructuring",
            )
            return msg

    # ── Competition card helpers (DRY) ─────────────────────────────

    def _apply_single_food_adj(self, adj: dict, food_amount: int) -> Optional[str]:
        """Apply one non-demand food adjustment. Returns a log message."""
        item = adj["item"]
        multiplier = adj.get("amount", 1)
        module = adj.get("module")
        fallback = adj.get("fallback")
        actual_amount = food_amount * multiplier

        if module and not self.state.modules.get(module, False):
            if fallback:
                self.state.inventory.add(fallback, actual_amount)
                return f"+{actual_amount} {fallback} (fallback, {module} not in play)"
            else:
                return f"Skipped {item} ({module} not in play)"
        elif not _is_item_available(item, self.state.modules):
            return f"Skipped {item} (module not in play)"
        else:
            self.state.inventory.add(item, actual_amount)
            return f"+{actual_amount} {item}"

    def _apply_inventory_boost(self) -> Optional[str]:
        """Apply inventory boost. Returns a log message."""
        boost_details = self.state.inventory.inventory_boost()
        if boost_details:
            return f"INVENTORY BOOST: {', '.join(boost_details)}"
        return "INVENTORY BOOST: no items on bottom row."

    def _apply_track_adjustments(self, track_adjustments: list) -> list[str]:
        """Apply a list of track adjustments in order. Returns log messages."""
        msgs: list[str] = []
        for ta in track_adjustments:
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
                    f"Competition card: Recruit & Train {old} → {new}",
                    "competition",
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
        return msgs

    def _resolve_competition_card(self, card: Card) -> str:
        """Resolve a competition card's effect.

        Immediate effects (tracks, inventory, flags) are applied now.
        Deferred effects that need user interaction (demand prompts,
        restaurant placement) are queued in pending_competition_actions
        and processed after the restructuring loop finishes.

        When a demand-based food adjustment (all_demand / most_demand)
        is encountered, ALL subsequent actions (remaining food items,
        inventory boost, track adjustments) are bundled into the
        deferred action so they execute in the correct card order
        after the user provides demand info.

        Order of actions follows the card descriptions:
          Cool: effect_type → inventory_drop → inventory_loss → tracks
          Warm: effect_type → food_adjustments → inventory_boost → tracks
        """
        if not card.competition_effect:
            return "No effect."

        effect = card.competition_effect
        msgs = []
        food_amount = self.state.tracks.get_food_amount()

        # ── Step 1: Type-specific effects (always first) ──────────────
        if effect.effect_type == "expand_chain":
            if len(self.state.restaurants) < self.state.max_restaurants:
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

        elif effect.effect_type == "fire_employees":
            # Fire all employees from pile (marketeers with active campaigns stay)
            fired = list(self.state.employee_pile)
            self.state.employee_pile.clear()
            msgs.append(
                f"FIRE ALL EMPLOYEES: {', '.join(fired) if fired else 'none to fire'}."
            )

        elif effect.effect_type == "pay_per_employee":
            emp_count = len(self.state.employee_pile) + sum(
                1 for s in self.state.marketeer_slots if s.marketeer == "Brand Director"
            )
            cost = emp_count * 10
            actual_paid = min(cost, self.state.chain_total_cash)
            self.state.chain_total_cash = max(0, self.state.chain_total_cash - cost)
            short = cost - actual_paid
            detail = f" (only ${actual_paid} available)" if short > 0 else ""
            msgs.append(
                f"PAY $10 PER EMPLOYEE: {emp_count} employees × $10 = ${cost}{detail}. "
                f"Chain cash: ${self.state.chain_total_cash}."
            )
            self.state.log(
                f"Competition pay_per_employee: −${actual_paid} from chain cash "
                f"(was ${self.state.chain_total_cash + actual_paid}, now ${self.state.chain_total_cash}).",
                "competition",
            )

        # ── Step 2: Food adjustments (warm cards) ─────────────────────
        deferred_remaining = False
        for i, adj in enumerate(effect.food_adjustments):
            item = adj["item"]
            multiplier = adj.get("amount", 1)

            if item in ("all_demand", "most_demand"):
                # Defer this demand action AND all subsequent steps so
                # they execute in card order after the user responds.
                remaining_food = [
                    a
                    for a in effect.food_adjustments[i + 1 :]
                    if a["item"] not in ("all_demand", "most_demand")
                ]
                self.state.pending_competition_actions.append(
                    {
                        "action": "competition_demand_info",
                        "demand_type": item,
                        "multiplier": multiplier,
                        "food_amount": food_amount,
                        "remaining_food_adjustments": remaining_food,
                        "inventory_boost": effect.inventory_boost,
                        "track_adjustments": [
                            {"type": ta["type"], "value": ta["value"]}
                            for ta in effect.track_adjustments
                        ],
                    }
                )
                msgs.append(
                    f"{item.replace('_', ' ').title()}: will ask for demand info "
                    f"(remaining actions deferred)"
                )
                deferred_remaining = True
                break
            else:
                msg = self._apply_single_food_adj(adj, food_amount)
                if msg:
                    msgs.append(msg)

        # ── Step 3: Inventory drop (cool cards, before inventory loss) ─
        if effect.inventory_drop:
            drop_details = self.state.inventory.inventory_drop()
            if drop_details:
                msgs.append(f"INVENTORY DROP: {', '.join(drop_details)}")
            else:
                msgs.append("INVENTORY DROP: no items on top row.")

        # ── Step 4: Inventory loss (cool cards, after drop) ───────────
        for item in effect.inventory_loss_items:
            self.state.inventory.clear_item(item)
            msgs.append(f"INVENTORY LOSS: all {item} removed.")

        # ── Step 5 & 6: Only if not deferred by a demand action ───────
        if not deferred_remaining:
            # ── Step 5: Inventory boost (warm cards) ──────────────────
            if effect.inventory_boost:
                msgs.append(self._apply_inventory_boost())

            # ── Step 6: Track adjustments (always last) ───────────────
            msgs.extend(self._apply_track_adjustments(effect.track_adjustments))

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

            available_items = [
                fi.value
                for fi in FoodItem
                if _is_item_available(fi.value, self.state.modules)
                and fi != FoodItem.COFFEE
            ]

            if demand_type == "most_demand":
                # Simplified: ask only which item(s) have the MOST demand
                fields = [
                    {
                        "name": "most_demand_items",
                        "label": "Item(s) with MOST demand (select all tied)",
                        "label_es": "Item(s) con MÁS demanda (selecciona todos los empatados)",
                        "type": "multiselect",
                        "options": available_items,
                    },
                ]
                prompt_en = (
                    f"🍔 Competition card: Get food (most demand)!\n"
                    f"Which item(s) have the MOST demand tokens on the map?"
                )
                prompt_es = (
                    f"🍔 Carta de competencia: ¡Obtener comida (más demanda)!\n"
                    f"¿Qué item(s) tienen MÁS fichas de demanda en el mapa?"
                )
            else:
                # all_demand: ask which items have any demand
                fields = [
                    {
                        "name": "items_with_demand",
                        "label": "Items with demand on map",
                        "label_es": "Items con demanda en el mapa",
                        "type": "multiselect",
                        "options": available_items,
                    },
                ]
                prompt_en = (
                    f"🍔 Competition card: Get food ({demand_type.replace('_', ' ')})!\n"
                    f"Which food items have demand tokens on the map?"
                )
                prompt_es = (
                    f"🍔 Carta de competencia: ¡Obtener comida ({demand_type.replace('_', ' ')})!\n"
                    f"¿Qué items de comida tienen fichas de demanda en el mapa?"
                )

            self.state.pending_input = {
                "type": "competition_demand_info",
                "prompt": prompt_en,
                "prompt_es": prompt_es,
                "demand_type": demand_type,
                "multiplier": multiplier,
                "food_amount": food_amount,
                "fields": fields,
                # Carry deferred actions so they execute in card order
                # after the user provides demand info.
                "remaining_food_adjustments": action.get(
                    "remaining_food_adjustments", []
                ),
                "inventory_boost": action.get("inventory_boost", False),
                "track_adjustments": action.get("track_adjustments", []),
            }
            self.state.phase = GamePhase.WAITING_FOR_INPUT
            return {
                "status": "waiting",
                "message": f"Competition card: Need demand info ({demand_type.replace('_', ' ')}).",
                "input_needed": self.state.pending_input,
            }

        elif action_type == "check_stacked_competition":
            top = self.state.action_deck.peek()
            if not top or top.card_type not in (CardType.WARM, CardType.COOL):
                # No longer a competition card (e.g. after a shuffle) — skip
                return self._process_pending_competition_actions()

            # Pre-compute whether this card matches the current track
            level = self.state.tracks.competition
            card_label = top.card_type.value.upper()
            will_resolve = False
            if top.card_type == CardType.WARM and level in (
                CompetitionLevel.WARM,
                CompetitionLevel.HOT,
            ):
                will_resolve = True
            elif top.card_type == CardType.COOL and level in (
                CompetitionLevel.COOL,
                CompetitionLevel.COLD,
            ):
                will_resolve = True
            if top.card_type == CardType.WARM and self.state.optional_rules.get(
                "aggressive_restructuring"
            ):
                will_resolve = True

            # Show the card to the player before resolving it
            comp_card_data = top.to_dict()
            comp_card_data["resolved"] = False
            comp_card_data["will_resolve"] = will_resolve
            comp_card_data["competition_level"] = level.label()
            self.state.current_competition_card = comp_card_data
            self.state.current_front_card = comp_card_data

            # Build detailed prompt explaining the match/mismatch
            if will_resolve:
                prompt_en = (
                    f"📋 STEP 3 — COMPETITION CARD\n\n"
                    f"A {card_label} Competition Card (#{top.card_number}) "
                    f"is on top of the Action Deck.\n\n"
                    f"Competition track is at {level.label()} → MATCHES!\n\n"
                    f"Press Confirm to resolve this card's actions. "
                    f"The card will then be placed face down under the "
                    f"{card_label} Competition Card deck."
                )
                prompt_es = (
                    f"📋 PASO 3 — CARTA DE COMPETENCIA\n\n"
                    f"Una carta de competencia {card_label} (#{top.card_number}) "
                    f"está encima del Mazo de Acción.\n\n"
                    f"La pista de competencia está en {level.label()} → ¡COINCIDE!\n\n"
                    f"Presiona Confirmar para resolver las acciones de esta carta. "
                    f"La carta se colocará boca abajo bajo el mazo de cartas "
                    f"de competencia {card_label}."
                )
            else:
                prompt_en = (
                    f"📋 STEP 3 — COMPETITION CARD\n\n"
                    f"A {card_label} Competition Card (#{top.card_number}) "
                    f"is on top of the Action Deck.\n\n"
                    f"Competition track is at {level.label()} → Does NOT match.\n\n"
                    f"Press Confirm to place this card face down under "
                    f"the Action Deck without resolving its actions."
                )
                prompt_es = (
                    f"📋 PASO 3 — CARTA DE COMPETENCIA\n\n"
                    f"Una carta de competencia {card_label} (#{top.card_number}) "
                    f"está encima del Mazo de Acción.\n\n"
                    f"La pista de competencia está en {level.label()} → NO coincide.\n\n"
                    f"Presiona Confirmar para colocar esta carta boca abajo "
                    f"bajo el Mazo de Acción sin resolver sus acciones."
                )

            self.state.pending_input = {
                "type": "acknowledge_competition_card",
                "prompt": prompt_en,
                "prompt_es": prompt_es,
                "will_resolve": will_resolve,
                "card_type": top.card_type.value,
                "card_number": top.card_number,
                "fields": [],
            }
            self.state.phase = GamePhase.WAITING_FOR_INPUT
            return {
                "status": "waiting",
                "message": (
                    f"STEP 3: {card_label} Competition Card #{top.card_number} "
                    f"on top of the deck. Track: {level.label()}. "
                    f"{'Matches — will resolve.' if will_resolve else 'Does not match — will place under deck.'}"
                ),
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
        """Resolve demand info from a competition card effect.

        After applying demand-based food, this also applies any
        remaining actions (food adjustments, inventory boost, tracks)
        that were deferred to preserve the card's intended action order.
        """
        pending = self.state.pending_input or {}
        demand_type = input_data.get("demand_type") or pending.get(
            "demand_type", "most_demand"
        )
        multiplier = pending.get("multiplier", 1)
        food_amount = pending.get("food_amount", self.state.tracks.get_food_amount())

        items_with_demand = input_data.get("items_with_demand", [])
        most_demand_items = input_data.get("most_demand_items", [])

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
                # Multiple items tied — pick one randomly
                winner = random.choice(most_demand_items)
                amount = food_amount * multiplier
                self.state.inventory.add(winner, amount)
                added.append(f"+{amount} {winner}")
                self.state.log(
                    f"Competition most demand tie between {', '.join(most_demand_items)} "
                    f"— random pick: {winner}",
                    "competition",
                )
            else:
                self.state.log(
                    "Competition card: No most demand item selected.", "competition"
                )

        msg = f"Competition card food: {', '.join(added) if added else 'none'}"
        self.state.log(msg, "competition")

        # ── Apply deferred remaining actions in card order ────────────
        remaining_food = pending.get("remaining_food_adjustments", [])
        for adj in remaining_food:
            result = self._apply_single_food_adj(adj, food_amount)
            if result:
                self.state.log(f"Competition deferred food: {result}", "competition")

        if pending.get("inventory_boost", False):
            boost_msg = self._apply_inventory_boost()
            self.state.log(f"Competition deferred: {boost_msg}", "competition")

        deferred_tracks = pending.get("track_adjustments", [])
        if deferred_tracks:
            track_msgs = self._apply_track_adjustments(deferred_tracks)
            for tm in track_msgs:
                self.state.log(f"Competition deferred track: {tm}", "competition")

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

        # Collect stars only from the active (open) slots
        stars = [a["star"] for a in active_actions if a.get("star")]
        self.state.rt_pending_stars = stars

        # Store actions for step-by-step execution (pause when input needed)
        self.state.pending_rt_actions = active_actions_reversed
        self.state.rt_result_msgs = []
        self.state.rt_open_slots = open_slots
        self.state.rt_phase_message = None

        return self._execute_rt_actions_stepwise()

    def _execute_rt_actions_stepwise(self) -> dict:
        """Execute pending R&T actions one at a time, pausing when user input is needed."""
        while self.state.pending_rt_actions:
            action_data = self.state.pending_rt_actions.pop(0)
            msg = self._execute_recruit_action(action_data)
            self.state.rt_result_msgs.append(msg)

            # If this action queued an employee availability check, pause now
            # so the user can answer before remaining actions execute.
            if self.state.pending_employee_checks:
                return self._finalize_rt_partial()

        # All actions done, no pending prompts
        return self._finalize_rt_complete()

    def _update_rt_employee_result(self, name: str, msg: str) -> None:
        """Replace the 'pending availability' entry for *name* in rt_result_msgs
        with the actual outcome *msg*, and refresh rt_phase_message."""
        pending_label = f"{name}: pending availability"
        for i, m in enumerate(self.state.rt_result_msgs):
            if m == pending_label:
                self.state.rt_result_msgs[i] = msg
                break
        # Rebuild rt_phase_message so subsequent prompts show updated text
        if self.state.rt_result_msgs:
            hint = self._worktime_turn_hint()
            self.state.rt_phase_message = (
                f"Recruit & Train ({self.state.rt_open_slots} open slots). "
                + " | ".join(self.state.rt_result_msgs)
                + hint
            )

    def _finalize_rt_partial(self) -> dict:
        """Build an interim R&T result when pausing for employee input."""
        open_slots = self.state.rt_open_slots
        hint = self._worktime_turn_hint()
        message = (
            f"Recruit & Train ({open_slots} open slots). "
            + " | ".join(self.state.rt_result_msgs)
            + hint
        )
        # Store as the authoritative phase message so employee prompts don't overwrite it
        self.state.rt_phase_message = message
        return {
            "status": "ok",
            "message": message,
            "actions_taken": list(self.state.rt_result_msgs),
        }

    def _finalize_rt_complete(self) -> dict:
        """Finalize R&T when all actions (and employee checks) are resolved."""
        open_slots = self.state.rt_open_slots
        result_msgs = list(self.state.rt_result_msgs)

        self.state.log(
            f"Open slots: {open_slots}. Executed actions.",
            "recruit_train",
        )

        self.state.pending_stars = list(self.state.rt_pending_stars)

        # Clean up R&T step-by-step state
        self.state.pending_rt_actions = []
        self.state.rt_result_msgs = []
        self.state.rt_pending_stars = []
        self.state.rt_phase_message = None
        self.state.rt_open_slots = 0

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

    def _resume_rt_actions(self) -> dict:
        """Resume R&T execution after an employee availability check is resolved.

        Called from the employee_available_confirm input handler once all
        pending employee checks are answered. Continues executing remaining
        R&T actions (if any) or finalizes the phase.
        """
        if self.state.pending_rt_actions:
            # More actions to execute — continue step-by-step
            result = self._execute_rt_actions_stepwise()
            # If stepwise returned because of another employee check, intercept
            result = self._prompt_pending_employee_checks(result)
            return self._prompt_pending_milestones(result)
        else:
            # No more actions — finalize R&T
            return self._finalize_rt_complete()

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
            # Milestone: first waitress (Base: first_waitress_played, Expansion: first_waitress_used)
            if new > 0:
                self._try_queue_milestone("first_waitress_played")
                self._try_queue_milestone("first_waitress_used")
            self._check_track_milestones()
            return f"Waitresses: {old} → {new}"
        elif action_type == "claim_milestone":
            # Remap card milestone targets when Expansion milestones are active
            actual_target = target
            if self.state.modules.get("milestones"):
                # Expansion active: remap Base keys to Expansion equivalents
                actual_target = BASE_TO_EXPANSION_MAP.get(target, target)
                if actual_target == target and not is_milestone_in_active_set(
                    target, self.state.modules
                ):
                    # Base-only milestone with no Expansion equivalent — skip
                    label = self.MILESTONE_LABELS.get(target, (target,))[0]
                    self.state.log(
                        f"Milestone {label} not in Expansion set. Skipped.",
                        "milestone",
                    )
                    return f"Milestone {label} not in active set"
            label = self.MILESTONE_LABELS.get(actual_target, (actual_target,))[0]
            if is_milestone_in_active_set(actual_target, self.state.modules):
                self._try_queue_milestone(actual_target)
            else:
                self.state.log(
                    f"Milestone {label} not in active set. Skipped.",
                    "milestone",
                )
            return f"Milestone: {label}"
        elif action_type == "get_food":
            food_amount = self.state.tracks.get_food_amount()
            self.state.inventory.add(target, food_amount)
            self.state.log(f"Get food: +{food_amount} {target}", "recruit_train")
            # Milestone: first burger/pizza produced (Base milestones)
            if target in PRODUCED_ITEM_MILESTONES:
                self._try_queue_milestone(PRODUCED_ITEM_MILESTONES[target])
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

        # Brand Director is unique — check availability like regular employees
        if name == "Brand Director":
            if self._chain_has_employee("Brand Director"):
                self.state.log(
                    "Brand Director already recruited. Skipping.", "recruit_train"
                )
                return "Brand Director: already in Chain's roster"
            has_slot = any(s.marketeer is None for s in self.state.marketeer_slots)
            if not has_slot:
                self.state.log("No marketeer slot for Brand Director.", "recruit_train")
                return "No slot for Brand Director"
            self.state.pending_employee_checks.append(
                {
                    "name": "Brand Director",
                    "type": "brand_director",
                }
            )
            self.state.log(
                "Brand Director recruitment pending availability check.",
                "recruit_train",
            )
            return "Brand Director: pending availability"

        # Find an open marketeer slot
        for slot in self.state.marketeer_slots:
            if slot.marketeer is None:
                slot.marketeer = name
                self.state.log(
                    f"Recruited {name} to Marketeer slot {slot.slot_number}.",
                    "recruit_train",
                )
                # Milestone: specific marketeer used (Expansion) + generic first_marketeer_used
                if name in MARKETEER_MILESTONE_MAP:
                    self._try_queue_milestone(MARKETEER_MILESTONE_MAP[name])
                self._try_queue_milestone("first_marketeer_used")
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
        """Recruit an employee to the Employee Pile (or Marketeer spot for Brand Director).

        All employees and Brand Directors are unique — the Chain cannot recruit
        duplicates. If the Chain doesn't already have the employee, a prompt is
        queued to ask the player whether the employee is available.
        """
        # Check if Chain already has this employee
        if self._chain_has_employee(name):
            self.state.log(f"{name} already recruited. Skipping.", "recruit_train")
            return f"{name}: already in Chain's roster"

        if name == "Brand Director":
            # Check if there's an open marketeer slot
            has_slot = any(s.marketeer is None for s in self.state.marketeer_slots)
            if not has_slot:
                self.state.log("No marketeer slot for Brand Director.", "recruit_train")
                return "No slot for Brand Director"

        # Queue availability check — actual recruitment happens on confirmation
        self.state.pending_employee_checks.append(
            {
                "name": name,
                "type": "brand_director" if name == "Brand Director" else "employee",
            }
        )
        self.state.log(
            f"{name} recruitment pending availability check.", "recruit_train"
        )
        return f"{name}: pending availability"

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
                        # Milestone: first burger/pizza produced
                        if item in PRODUCED_ITEM_MILESTONES:
                            self._try_queue_milestone(PRODUCED_ITEM_MILESTONES[item])
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
            available_items = [
                fi.value
                for fi in FoodItem
                if _is_item_available(fi.value, self.state.modules)
                and fi != FoodItem.COFFEE
            ]
            if demand_type == "most_demand":
                # Simplified: ask only which item(s) have the MOST demand
                fields = [
                    {
                        "name": "most_demand_items",
                        "label": "Item(s) with MOST demand (select all tied)",
                        "label_es": "Item(s) con MÁS demanda (selecciona todos los empatados)",
                        "type": "multiselect",
                        "options": available_items,
                    },
                ]
                prompt_en = "Which item(s) have the MOST demand tokens on the map?"
                prompt_es = "¿Qué item(s) tienen MÁS fichas de demanda en el mapa?"
            else:
                # all_demand: ask which items have any demand
                fields = [
                    {
                        "name": "items_with_demand",
                        "label": "Items with demand on map",
                        "label_es": "Items con demanda en el mapa",
                        "type": "multiselect",
                        "options": available_items,
                    },
                ]
                prompt_en = f"Which food items have demand tokens on the map? (for {demand_type.replace('_', ' ')})"
                prompt_es = f"¿Qué items de comida tienen fichas de demanda? (para {demand_type.replace('_', ' ')})"

            self.state.pending_input = {
                "type": "demand_info",
                "prompt": prompt_en,
                "prompt_es": prompt_es,
                "demand_type": demand_type,
                "multiplier": multiplier,
                "food_amount": food_amount,
                "fields": fields,
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

        added = []
        if demand_type == "all_demand":
            for item in items_with_demand:
                amount = food_amount * multiplier
                self.state.inventory.add(item, amount)
                added.append(f"+{amount} {item}")
                self.state.log(f"All demand: +{amount} {item}", "get_food")
                # Milestone: first burger/pizza produced
                if item in PRODUCED_ITEM_MILESTONES:
                    self._try_queue_milestone(PRODUCED_ITEM_MILESTONES[item])
        elif demand_type == "most_demand":
            if len(most_demand_items) == 1:
                # Single winner — no tie
                item = most_demand_items[0]
                amount = food_amount * multiplier
                self.state.inventory.add(item, amount)
                added.append(f"+{amount} {item}")
                self.state.log(f"Most demand: +{amount} {item}", "get_food")
                # Milestone: first burger/pizza produced
                if item in PRODUCED_ITEM_MILESTONES:
                    self._try_queue_milestone(PRODUCED_ITEM_MILESTONES[item])
            elif len(most_demand_items) > 1:
                # Multiple items tied — pick one randomly
                winner = random.choice(most_demand_items)
                amount = food_amount * multiplier
                self.state.inventory.add(winner, amount)
                added.append(f"+{amount} {winner}")
                self.state.log(
                    f"Most demand tie between {', '.join(most_demand_items)} "
                    f"— random pick: {winner}",
                    "get_food",
                )
                # Milestone: first burger/pizza produced
                if winner in PRODUCED_ITEM_MILESTONES:
                    self._try_queue_milestone(PRODUCED_ITEM_MILESTONES[winner])
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
        # Milestone: first burger/pizza produced
        if winner in PRODUCED_ITEM_MILESTONES:
            self._try_queue_milestone(PRODUCED_ITEM_MILESTONES[winner])

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
                # Milestone: first burger/pizza produced
                if fi_fallback in PRODUCED_ITEM_MILESTONES:
                    self._try_queue_milestone(PRODUCED_ITEM_MILESTONES[fi_fallback])
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
            # Milestone: first burger/pizza produced
            if fi in PRODUCED_ITEM_MILESTONES:
                self._try_queue_milestone(PRODUCED_ITEM_MILESTONES[fi])
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
            # No new campaigns to set up — skip silently
            self.state.phase = GamePhase.GET_FOOD
            hint = self._worktime_turn_hint()
            msg = "Initiate Marketing: No new marketeers to initiate." + hint
            return {"status": "ok", "message": msg, "next_phase": "get_food"}

        # ── Auto-activate Rural Marketeers (no campaign number) ──────────
        rural_activated = []
        for slot in new_marketeers:
            if slot.marketeer == "Rural Marketeer":
                slot.is_busy = True
                slot.market_item = market_item
                slot.campaign_number = None  # Giant billboards have no number
                slot.campaigns_left = -1  # Eternal
                slot.placed_turn = self.state.turn_number
                self.state.log(
                    f"Rural Marketeer (slot {slot.slot_number}): permanent Giant Billboard "
                    f"marketing {market_item} on tile {market_tile}.",
                    "marketing",
                )
                rural_activated.append(
                    f"Rural Marketeer (slot {slot.slot_number}) Giant Billboard "
                    f"{market_item}, permanent"
                )
                self._try_queue_milestone("first_to_market")
                if "Rural Marketeer" in MARKETEER_MILESTONE_MAP:
                    self._try_queue_milestone(
                        MARKETEER_MILESTONE_MAP["Rural Marketeer"]
                    )

        # Remaining new marketeers that still need campaign number input
        prompt_marketeers = [
            slot for slot in new_marketeers if slot.marketeer != "Rural Marketeer"
        ]

        if not prompt_marketeers:
            # Only Rural Marketeers were new — already auto-activated
            # Fire per-item milestones if any rural campaigns went active
            if rural_activated:
                _mkt_key = (
                    "first_burger_marketed"
                    if market_item == "burger"
                    else (
                        "first_pizza_marketed"
                        if market_item == "pizza"
                        else (
                            "first_drink_marketed"
                            if market_item in DRINK_ITEMS
                            else None
                        )
                    )
                )
                if _mkt_key:
                    self._try_queue_milestone(_mkt_key)
            self.state.phase = GamePhase.GET_FOOD
            hint = self._worktime_turn_hint()
            msg = "Initiate Marketing: " + " | ".join(rural_activated) + hint
            return {"status": "ok", "message": msg, "next_phase": "get_food"}

        # Build prompt fields — one campaign select field per new marketeer
        # Collect currently active campaign numbers to exclude from options
        active_numbers: set[int] = set()
        for s in self.state.marketeer_slots:
            if s.is_busy and s.campaign_number is not None:
                active_numbers.add(int(s.campaign_number))

        fields = []
        for slot in prompt_marketeers:
            duration = MARKETEER_DURATIONS.get(slot.marketeer, 3)
            if duration == -1:
                dur_label = "permanent"
                dur_label_es = "permanente"
            else:
                dur_label = f"{duration} campaigns"
                dur_label_es = f"{duration} campañas"

            # Get valid campaign numbers for this marketeer type
            valid_numbers = get_valid_campaign_numbers(slot.marketeer, active_numbers)

            if not valid_numbers:
                # No valid campaign numbers available — skip this marketeer
                self.state.log(
                    f"No campaign numbers available for {slot.marketeer} "
                    f"(slot {slot.slot_number}). Skipping.",
                    "marketing",
                )
                continue

            # Build select options with labels showing campaign type
            options = []
            for num in valid_numbers:
                ctype = get_campaign_type(num)
                options.append({"value": str(num), "label": f"#{num} ({ctype})"})

            # Reserve the default (lowest) number so the next marketeer
            # in the same prompt won't be offered the same number
            active_numbers.add(valid_numbers[0])

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
                    "type": "select",
                    "options": options,
                    "default": str(valid_numbers[0]),
                }
            )

        # Store the market context so _resolve_initiate_marketing can use it
        self.state.pending_input = {
            "type": "initiate_marketing_campaigns",
            "market_item": market_item,
            "market_tile": market_tile,
            "rural_activated": rural_activated,
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
        rural_activated = pending.get("rural_activated", [])
        self.state.pending_input = None

        # Collect active campaign numbers for validation
        active_numbers: set[int] = set()
        for s in self.state.marketeer_slots:
            if s.is_busy and s.campaign_number is not None:
                active_numbers.add(int(s.campaign_number))

        campaigns = list(rural_activated)  # Start with any auto-activated Rural msgs
        for slot in self.state.marketeer_slots:
            if slot.marketeer and not slot.is_busy:
                raw_val = input_data.get(f"campaign_slot_{slot.slot_number}")
                if raw_val is None:
                    # No input for this slot (e.g. skipped due to no valid numbers)
                    continue
                try:
                    campaign_num = int(raw_val)
                except (ValueError, TypeError):
                    campaign_num = None

                duration = MARKETEER_DURATIONS.get(slot.marketeer, 3)

                # Validate against allowed numbers for this marketeer type
                valid_numbers = get_valid_campaign_numbers(
                    slot.marketeer, active_numbers
                )
                if campaign_num not in valid_numbers:
                    # Fallback to lowest valid number
                    campaign_num = valid_numbers[0] if valid_numbers else 1

                slot.is_busy = True
                slot.market_item = market_item
                slot.campaign_number = campaign_num
                slot.campaigns_left = duration  # -1 for eternal (Rural Marketeer)
                slot.placed_turn = self.state.turn_number
                # Track this number as active for subsequent slots
                active_numbers.add(campaign_num)

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
                # Milestone: first to market (legacy/always)
                self._try_queue_milestone("first_to_market")

                # Campaign type milestones (Base: billboard, airplane, radio)
                try:
                    cnum = int(campaign_num)
                    ctype = get_campaign_type(cnum)
                    if ctype and ctype in CAMPAIGN_TYPE_MILESTONES:
                        self._try_queue_milestone(CAMPAIGN_TYPE_MILESTONES[ctype])
                except (ValueError, TypeError):
                    pass

        # Per-item first-marketed milestones (Base milestones — now always checked, not Hard Choices only)
        if campaigns:
            _mkt_key = (
                "first_burger_marketed"
                if market_item == "burger"
                else (
                    "first_pizza_marketed"
                    if market_item == "pizza"
                    else "first_drink_marketed" if market_item in DRINK_ITEMS else None
                )
            )
            if _mkt_key:
                self._try_queue_milestone(_mkt_key)

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
            # Milestone: first house built (Expansion milestone)
            if dev_type == "house":
                self._try_queue_milestone("first_house_built")
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

        # Lobby action requires the Lobbyists module expansion
        if not self.state.modules.get("lobbyists"):
            self.state.phase = GamePhase.EXPAND_CHAIN
            hint = self._worktime_turn_hint()
            return {
                "status": "ok",
                "message": "Lobbyists module not active. Skipping LOBBY." + hint,
                "next_phase": "expand_chain",
            }

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
            # Milestone: first lobbyist used (Module milestone)
            self._try_queue_milestone("first_lobbyist_used")
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

        # Build inventory display for items with count > 0
        inventory_display = []
        food_icons = {
            "burger": "🍔",
            "pizza": "🍕",
            "beer": "🍺",
            "lemonade": "🍋",
            "softdrink": "🥤",
            "sushi": "🍣",
            "noodle": "🍜",
            "coffee": "☕",
            "kimchi": "🥬",
        }
        for item, count in self.state.inventory.items.items():
            if count > 0:
                inventory_display.append(
                    {"item": item, "count": count, "icon": food_icons.get(item, "")}
                )

        self.state.pending_input = {
            "type": "dinnertime_result",
            "prompt": f"Enter dinnertime earnings. {info}",
            "prompt_es": f"Introduce las ganancias de la cena. {info}",
            "inventory_display": inventory_display,
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

        All active campaigns fire their effects (place demand on the board).
        If the Chain has a Mass Marketeer, an additional round of campaign
        effects fires (all campaigns resolve twice).  Duration markers are
        only decremented once, after all rounds are complete.  The Mass
        Marketeer is then returned to the employee pool.
        """
        self.state.log("=== MARKETING CAMPAIGNS ===", "phase")

        active_slots = [
            slot
            for slot in self.state.marketeer_slots
            if slot.marketeer and slot.is_busy and slot.campaigns_left is not None
        ]

        msgs: list[str] = []

        if not active_slots:
            self.state.log("No active marketing campaigns.", "marketing_campaigns")
            # Even with no regular campaigns, Mass Marketeer has nothing to double
            if self.state.mass_marketeer:
                self.state.mass_marketeer = False
                self.state.log(
                    "Mass Marketeer returned to employee pool (no campaigns to run).",
                    "marketing_campaigns",
                )
                msgs.append("Mass Marketeer returned to pool (no campaigns)")
            self.state.phase = GamePhase.CLEANUP
            return {
                "status": "ok",
                "message": "Marketing Campaigns: "
                + (" | ".join(msgs) if msgs else "No active campaigns."),
                "next_phase": "cleanup",
            }

        # ── Round 1: Normal campaign resolution ──────────────────────────
        self.state.log("--- Campaign Round 1 ---", "marketing_campaigns")
        for slot in active_slots:
            camp_num = (
                f"#{slot.campaign_number}"
                if slot.campaign_number is not None
                else "Giant Billboard"
            )
            if slot.campaigns_left == -1:
                self.state.log(
                    f"{slot.marketeer} (slot {slot.slot_number}): "
                    f"permanent campaign ({slot.market_item}, {camp_num}).",
                    "marketing_campaigns",
                )
            else:
                self.state.log(
                    f"{slot.marketeer} (slot {slot.slot_number}): "
                    f"campaign fires ({slot.market_item}, {camp_num}), "
                    f"{slot.campaigns_left} duration marker(s) before decrement.",
                    "marketing_campaigns",
                )

        # ── Round 2: Mass Marketeer extra campaign round ─────────────────
        has_mass = self.state.mass_marketeer
        if has_mass:
            self.state.log(
                "--- EXTRA Campaign Round (Mass Marketeer) ---",
                "marketing_campaigns",
            )
            for slot in active_slots:
                camp_num = (
                    f"#{slot.campaign_number}"
                    if slot.campaign_number is not None
                    else "Giant Billboard"
                )
                self.state.log(
                    f"{slot.marketeer} (slot {slot.slot_number}): "
                    f"EXTRA campaign fires ({slot.market_item}, {camp_num}).",
                    "marketing_campaigns",
                )

        # ── Decrement duration markers & expire (once, after all rounds) ─
        # Build one combined message per slot: "Name (slot N): item #num, X left"
        for slot in active_slots:
            camp_num = (
                f"#{slot.campaign_number}"
                if slot.campaign_number is not None
                else "Giant Billboard"
            )
            slot_prefix = f"{slot.marketeer} (slot {slot.slot_number})"

            # Eternal campaigns (Rural Marketeer) — never decrement
            if slot.campaigns_left == -1:
                msgs.append(f"{slot_prefix}: {slot.market_item} {camp_num}, permanent")
                continue

            slot.campaigns_left -= 1
            if slot.campaigns_left <= 0:
                expired_name = slot.marketeer
                self.state.log(
                    f"{expired_name} (slot {slot.slot_number}) campaign expired! "
                    f"Marketing {slot.market_item}, "
                    f"campaign #{slot.campaign_number}. Marketeer removed.",
                    "marketing_campaigns",
                )
                # Brand Director goes to employee pile when campaign expires
                if expired_name == "Brand Director":
                    self.state.employee_pile.append("Brand Director")
                    self.state.log(
                        "Brand Director placed in employee pile.",
                        "marketing_campaigns",
                    )
                    msgs.append(
                        f"{slot_prefix}: {slot.market_item} {camp_num}, expired — to employee pile"
                    )
                else:
                    msgs.append(
                        f"{slot_prefix}: {slot.market_item} {camp_num}, expired — removed"
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
                    f"({slot.market_item}, "
                    f"{'Giant Billboard' if slot.campaign_number is None else '#' + str(slot.campaign_number)}).",
                    "marketing_campaigns",
                )
                msgs.append(
                    f"{slot_prefix}: {slot.market_item} {camp_num}, "
                    f"{slot.campaigns_left} left"
                )

        # Mass Marketeer note (appended after per-slot summaries)
        if has_mass:
            msgs.append("Mass Marketeer: All campaigns fired twice")

        # ── Return Mass Marketeer to employee pool ───────────────────────
        if has_mass:
            self.state.mass_marketeer = False
            self.state.log(
                "Mass Marketeer returned to employee pool.",
                "marketing_campaigns",
            )
            msgs.append("Mass Marketeer returned to employee pool")

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

        # 1. Inventory cap (max 10, excluding coffee)
        cap_details = self.state.inventory.cap_inventory()
        if cap_details:
            msgs.append(f"Inventory capped: {', '.join(cap_details)}")
            self.state.log(
                f"Cleanup: Inventory capped — {', '.join(cap_details)}", "cleanup"
            )

        # Coffee cannot be stored — discard all coffee at end of turn
        if self.state.modules.get("coffee"):
            coffee_count = self.state.inventory.items.get("coffee", 0)
            if coffee_count > 0:
                self.state.inventory.clear_item("coffee")
                msgs.append(f"Coffee lost: {coffee_count} (cannot be stored)")
                self.state.log(
                    f"Cleanup: {coffee_count} coffee discarded (cannot be stored).",
                    "cleanup",
                )

        # 2. Cleanup actions from the active back card
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

        # Hard Choices: expire milestones at end of turn 2 and turn 3 (Base milestones only)
        if self.state.optional_rules.get("hard_choices") and not self.state.modules.get(
            "milestones"
        ):
            completed_turn = self.state.turn_number - 1
            if completed_turn == 2:
                expire_candidates = [
                    "first_to_train",
                    "first_burger_marketed",
                    "first_pizza_marketed",
                    "first_drink_marketed",
                ]
            elif completed_turn == 3:
                expire_candidates = ["first_to_hire_3"]
            else:
                expire_candidates = []
            for key in expire_candidates:
                if (
                    key not in self.state.milestones_claimed
                    and key not in self.state.milestones_unavailable
                    and key not in self.state.milestones_expired
                    and is_milestone_in_active_set(key, self.state.modules)
                ):
                    self.state.milestones_expired.append(key)
                    en_name, _ = self.MILESTONE_LABELS.get(key, (key, key))
                    msgs.append(f"\u23f3 '{en_name}' expired (Hard Choices)!")
                    self.state.log(
                        f"Hard Choices: '{en_name}' milestone expired at end of turn {completed_turn}.",
                        "milestone",
                    )

        # Expansion Milestones: "Remove after turn 2" — expire tokens at end of turn 2
        if self.state.modules.get("milestones"):
            completed_turn = self.state.turn_number - 1
            if completed_turn == 2 and self.state.milestones_turn2_tokens:
                for key in list(self.state.milestones_turn2_tokens):
                    if (
                        key not in self.state.milestones_claimed
                        and key not in self.state.milestones_unavailable
                        and key not in self.state.milestones_expired
                    ):
                        self.state.milestones_expired.append(key)
                        en_name, _ = self.MILESTONE_LABELS.get(key, (key, key))
                        msgs.append(f"✖ '{en_name}' expired (turn 2 token removed)!")
                        self.state.log(
                            f"Expansion Milestones: '{en_name}' expired — turn 2 token removed.",
                            "milestone",
                        )
                self.state.milestones_turn2_tokens.clear()

        # Hard Choices + Expansion Milestones: apply turn-2 expiry from Expansion rules
        if self.state.optional_rules.get("hard_choices") and self.state.modules.get(
            "milestones"
        ):
            completed_turn = self.state.turn_number - 1
            # The Expansion turn-2 expiry already handled the 3 token milestones above.
            # Hard Choices doesn't add extra expiry when Expansion milestones are active.

        # Clear pending stars now so they don't linger into the roundup prompt
        self.state.pending_stars = []

        result_msg = "Cleanup complete: " + (
            " | ".join(msgs) if msgs else "no adjustments"
        )
        self.state.log(
            f"Turn {self.state.turn_number - 1} complete. Starting Turn {self.state.turn_number}.",
            "phase",
        )

        # ── End-of-round milestone roundup ──────────────────────────────
        # Build the two lists for the cleanup prompt:
        #   chain_claimed  — milestones The Chain auto-claimed this round
        #   still_available — milestones available for the player to claim
        #                     (active, not chain-claimed, not player-claimed, not expired)
        resolved = (
            set(self.state.milestones_claimed)
            | set(self.state.milestones_unavailable)
            | set(self.state.milestones_expired)
        )
        active_ms = get_active_milestones(self.state.modules)

        # Build a quick lookup for color from the active milestone definitions
        color_lookup = {m["key"]: m.get("color", "") for m in active_ms}

        chain_claimed_info = []
        for key in self.state.milestones_claimed_this_round:
            en, es = self.MILESTONE_LABELS.get(key, (key, key))
            chain_claimed_info.append(
                {
                    "key": key,
                    "label_en": en,
                    "label_es": es,
                    "color": color_lookup.get(key, ""),
                }
            )

        still_available_info = []
        for m in active_ms:
            key = m["key"]
            if key not in resolved:
                still_available_info.append(
                    {
                        "key": key,
                        "label_en": m["label_en"],
                        "label_es": m["label_es"],
                        "color": m.get("color", ""),
                    }
                )

        if chain_claimed_info or still_available_info:
            # Build prompt text
            chain_names_en = ", ".join(i["label_en"] for i in chain_claimed_info)
            chain_names_es = ", ".join(i["label_es"] for i in chain_claimed_info)
            if chain_claimed_info:
                prompt_en = (
                    f"🏆 Milestone Roundup\n"
                    # f"The Chain claimed: {chain_names_en}.\n"
                    # f"Check any milestones that you ALSO claimed this round\n"
                    # f"(joint claims keep the 🏆 — no X token needed).\n"
                    # f"Also check any available milestones you claimed on your own."
                )
                prompt_es = (
                    f"🏆 Resumen de Hitos\n"
                    # f"La Cadena reclamó: {chain_names_es}.\n"
                    # f"Marca los hitos que TÚ TAMBIÉN reclamaste este turno\n"
                    # f"(reclamación conjunta — no coloca ficha X).\n"
                    # f"También marca los hitos disponibles que reclamaste tú solo."
                )
            else:
                prompt_en = (
                    "🏆 Milestone Roundup\n"
                    "Did you claim any milestones this round?\n"
                    "Check the ones you claimed so they can be deactivated."
                )
                prompt_es = (
                    "🏆 Resumen de Hitos\n"
                    "¿Reclamaste algún hito este turno?\n"
                    "Marca los que hayas reclamado para desactivarlos."
                )

            self.state.pending_input = {
                "type": "milestone_player_roundup",
                "prompt": prompt_en,
                "prompt_es": prompt_es,
                "chain_claimed": chain_claimed_info,
                "available": still_available_info,
            }
            self.state.phase = GamePhase.WAITING_FOR_INPUT
            return {
                "status": "waiting",
                "message": result_msg,
                "input_needed": self.state.pending_input,
            }

        # Nothing to reconcile — clear round tracking and proceed directly
        self.state.milestones_claimed_this_round.clear()
        self.state.phase = GamePhase.RESTRUCTURING
        return {
            "status": "ok",
            "message": result_msg,
            "next_phase": "restructuring",
        }

    # ─── Undo ────────────────────────────────────────────────────────────

    def undo(self) -> dict:
        """Undo the last action by restoring previous state snapshot.

        Uses _deserialize_full_state from save_manager for a complete,
        reliable restore that covers all fields (decks, discard pile,
        tracks, inventory, marketeers, competition state, etc.).
        """
        if not self.state.history:
            return {"status": "error", "message": "Nothing to undo."}

        snapshot_json = self.state.history.pop()
        snapshot = __import__("json").loads(snapshot_json)

        # Preserve the current history stack (snapshots don't include it)
        history = self.state.history

        # Full restore via the same deserializer used by save/load
        from .save_manager import _deserialize_full_state

        self.state = _deserialize_full_state(snapshot)
        self.state.history = history

        # Clear any pending input / overlay state so undo never lands on a
        # blocking prompt.  Re-advancing will regenerate the prompt cleanly.
        self.state.pending_input = None
        self.state.next_phase_after_input = None
        self.state.pending_employee_checks = []
        self.state.pending_milestone_checks = []
        self.state.pending_competition_actions = []
        self.state.phase_before_milestone = None
        self.state.phase_before_employee_check = None
        self.state.phase_after_competition = None

        if self.state.phase == GamePhase.WAITING_FOR_INPUT:
            # Roll back to the display phase (the phase shown to the user)
            # so the player can re-advance into the prompt from scratch.
            fallback = self.state.display_phase or "restructuring"
            self.state.phase = GamePhase(fallback)

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

    def quick_shuffle_deck(self, deck_name: str) -> dict:
        """Quick mode: shuffle a named deck.
        For the action deck, the discard pile is merged back in before shuffling."""
        deck = self._resolve_deck(deck_name)
        if deck is None:
            return {"status": "error", "message": f"Unknown deck: {deck_name}"}
        if deck_name == "action":
            self.state.reshuffle_deck()
            self.state.log(
                "Shuffled Action Deck (discard pile merged back in).", "system"
            )
        else:
            deck.shuffle()
            self.state.log(f"Shuffled {deck.name}.", "system")
        return {"status": "ok", "deck": deck.to_dict()}

    def quick_discard(self, deck_name: str) -> dict:
        """Quick mode: draw the top card from a deck and move it to the discard pile."""
        deck = self._resolve_deck(deck_name)
        if deck is None:
            return {"status": "error", "message": f"Unknown deck: {deck_name}"}
        card = deck.draw()
        if not card:
            return {"status": "error", "message": f"{deck.name} is empty!"}
        self.state.discard_pile.place_under(card)
        card_label = f"{card.card_type.value} #{card.card_number}"
        self.state.log(f"Discarded {card_label} from {deck.name}.", "system")
        return {
            "status": "ok",
            "card": card.to_dict(),
            "deck": deck.to_dict(),
            "discard_pile": self.state.discard_pile.to_dict(),
        }

    def quick_draw_competition(self, deck_name: str) -> dict:
        """Quick mode: draw the top card from warm/cool deck and hold it for resolve decision."""
        deck = self._resolve_deck(deck_name)
        if deck is None:
            return {"status": "error", "message": f"Unknown deck: {deck_name}"}
        card = deck.draw()
        if not card:
            return {"status": "error", "message": f"{deck.name} is empty!"}
        self.state._pending_competition_card = card
        self.state._pending_competition_deck = deck_name
        card_label = f"{card.card_type.value} #{card.card_number}"
        self.state.log(f"Drew {card_label} from {deck.name}.", "system")
        return {
            "status": "ok",
            "card": card.to_dict(),
            "deck": deck.to_dict(),
        }

    def quick_resolve_competition(self, deck_name: str, resolved: bool) -> dict:
        """Quick mode: resolve or not-resolve a drawn competition card.
        Resolved: card goes back to bottom of its warm/cool deck.
        Not resolved: card goes to bottom of action deck."""
        card = getattr(self.state, "_pending_competition_card", None)
        if card is None:
            return {"status": "error", "message": "No competition card pending."}
        deck = self._resolve_deck(deck_name)
        if deck is None:
            return {"status": "error", "message": f"Unknown deck: {deck_name}"}
        card_label = f"{card.card_type.value} #{card.card_number}"
        if resolved:
            deck.place_under(card)
            self.state.log(
                f"{card_label} resolved \u2014 returned to bottom of {deck.name}.",
                "system",
            )
        else:
            self.state.action_deck.place_under(card)
            self.state.log(
                f"{card_label} not resolved \u2014 placed on bottom of Action Deck.",
                "system",
            )
        self.state._pending_competition_card = None
        self.state._pending_competition_deck = None
        return {
            "status": "ok",
            "source_deck": deck.to_dict(),
            "action_deck": self.state.action_deck.to_dict(),
        }

    def quick_place_on_action(self, deck_name: str, position: str) -> dict:
        """Quick mode: draw top card from warm/cool deck and place on action deck."""
        deck = self._resolve_deck(deck_name)
        if deck is None:
            return {"status": "error", "message": f"Unknown deck: {deck_name}"}
        card = deck.draw()
        if not card:
            return {"status": "error", "message": f"{deck.name} is empty!"}
        if position == "top":
            self.state.action_deck.place_on_top(card)
        else:
            self.state.action_deck.place_under(card)
        label = "top" if position == "top" else "bottom"
        card_label = f"{card.card_type.value} #{card.card_number}"
        self.state.log(
            f"Placed {card_label} from {deck.name} on {label} of Action Deck.", "system"
        )
        return {
            "status": "ok",
            "card": card.to_dict(),
            "source_deck": deck.to_dict(),
            "action_deck": self.state.action_deck.to_dict(),
        }

    def _resolve_deck(self, deck_name: str):
        """Return the Deck object for a given name, or None."""
        mapping = {
            "warm": self.state.warm_deck,
            "cool": self.state.cool_deck,
            "action": self.state.action_deck,
            "discard": self.state.discard_pile,
        }
        return mapping.get(deck_name)
