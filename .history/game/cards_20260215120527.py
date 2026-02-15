"""All 44 card definitions for The Chain automa.

Card data is encoded from the Cartas.pdf contents:
- 20 Action Deck cards (front: RECRUIT & TRAIN, back: GET FOOD & DRINKS / CLEANUP)
- 12 Warm Competition cards
- 12 Cool Competition cards
"""

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


def build_action_deck() -> list[Card]:
    """Build all 20 Action Deck cards with front and back data."""
    cards = []

    # ── Card 1 ──────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=1,
            card_type=CardType.ACTION,
            card_number=1,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1, "recruit_marketeer", "Zeppelin Pilot", fallback_food="burger"
                    ),
                    ActionSlot(2, "recruit_employee", "Burger Chef"),
                    ActionSlot(3, "move_waitress", "+1"),
                    ActionSlot(
                        4,
                        "recruit_employee",
                        "Gourmet Food Critic",
                        requires_module="coffee",
                        fallback_food="burger",
                    ),
                ],
                stars=["coffee_shop", "expand_chain"],
                map_tile=1,
            ),
            back=CardBack(
                demand_type="most_demand",
                multiplier=2,
                cleanup_actions=[
                    CleanupAction("move_distance", +1),
                    CleanupAction("move_waitress", -1),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", 0),
                ],
                develop_target="house_25",
                lobby_target="park",
                map_tile=5,
            ),
        )
    )

    # ── Card 2 ──────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=2,
            card_type=CardType.ACTION,
            card_number=2,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1, "recruit_marketeer", "Zeppelin Pilot", fallback_food="pizza"
                    ),
                    ActionSlot(
                        2,
                        "recruit_employee",
                        "Sushi Chef",
                        requires_module="sushi",
                        fallback_food="pizza",
                    ),
                    ActionSlot(3, "move_waitress", "+1"),
                    ActionSlot(4, "recruit_employee", "Campaign Manager"),
                ],
                stars=["develop", "lobby"],
                map_tile=2,
            ),
            back=CardBack(
                demand_type="most_demand",
                multiplier=2,
                cleanup_actions=[
                    CleanupAction("move_distance", 0),
                    CleanupAction("move_waitress", -3),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", +2),
                ],
                develop_target="house_5",
                lobby_target="park_pi",
                map_tile=6,
            ),
        )
    )

    # ── Card 3 ──────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=3,
            card_type=CardType.ACTION,
            card_number=3,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1, "recruit_marketeer", "Zeppelin Pilot", fallback_food="sushi"
                    ),
                    ActionSlot(2, "recruit_employee", "Night Shift Manager"),
                    ActionSlot(3, "move_distance", "-1"),
                    ActionSlot(4, "claim_milestone", "first_cart_operator"),
                ],
                stars=["expand_chain"],
                map_tile=3,
            ),
            back=CardBack(
                demand_type="most_demand",
                multiplier=2,
                cleanup_actions=[
                    CleanupAction("move_distance", -3),
                    CleanupAction("move_waitress", 0),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", +2),
                ],
                develop_target="house_6",
                lobby_target="park_22",
                map_tile=7,
            ),
        )
    )

    # ── Card 4 ──────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=4,
            card_type=CardType.ACTION,
            card_number=4,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1, "recruit_marketeer", "Mass Marketeer", fallback_food="noodle"
                    ),
                    ActionSlot(2, "recruit_employee", "Guru"),
                    ActionSlot(3, "move_distance", "-3"),
                    ActionSlot(4, "recruit_employee", "Marketing Trainee"),
                ],
                stars=["expand_chain", "lobby"],
                map_tile=4,
            ),
            back=CardBack(
                demand_type="most_demand",
                multiplier=2,
                cleanup_actions=[
                    CleanupAction("move_distance", +1),
                    CleanupAction("move_waitress", -2),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", 0),
                ],
                develop_target="house_6",
                lobby_target="park_4",
                map_tile=8,
            ),
        )
    )

    # ── Card 5 ──────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=5,
            card_type=CardType.ACTION,
            card_number=5,
            front=CardFront(
                actions=[
                    ActionSlot(1, "recruit_employee", "Guru"),
                    ActionSlot(2, "move_waitress", "+1"),
                    ActionSlot(3, "recruit_employee", "Marketing Trainee"),
                    ActionSlot(4, "claim_milestone", "first_discount_manager"),
                ],
                stars=["lobby", "expand_chain"],
                map_tile=5,
            ),
            back=CardBack(
                demand_type="most_demand",
                multiplier=2,
                cleanup_actions=[
                    CleanupAction("move_distance", +2),
                    CleanupAction("move_waitress", 0),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", 0),
                ],
                develop_target="house_19",
                lobby_target="park_18",
                map_tile=9,
            ),
        )
    )

    # ── Card 6 ──────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=6,
            card_type=CardType.ACTION,
            card_number=6,
            front=CardFront(
                actions=[
                    ActionSlot(1, "recruit_employee", "Guru"),
                    ActionSlot(2, "move_distance", "-3"),
                    ActionSlot(3, "recruit_employee", "Campaign Manager"),
                    ActionSlot(4, "get_food", "burger"),
                ],
                stars=["coffee_shop"],
                map_tile=6,
            ),
            back=CardBack(
                demand_type="specific",
                food_items=["burger", "pizza", "lemonade"],
                multiplier=1,
                cleanup_actions=[
                    CleanupAction("move_distance", +1),
                    CleanupAction("move_waitress", -2),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", 0),
                ],
                develop_target="house_11",
                lobby_target="park_7",
                map_tile=1,
            ),
        )
    )

    # ── Card 7 ──────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=7,
            card_type=CardType.ACTION,
            card_number=7,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1,
                        "recruit_marketeer",
                        "Lead Barista",
                        requires_module="coffee",
                        fallback_food="coffee",
                    ),
                    ActionSlot(2, "recruit_employee", "Executive VP"),
                    ActionSlot(3, "move_waitress", "+1"),
                    ActionSlot(4, "recruit_employee", "Campaign Manager"),
                ],
                stars=["develop", "expand_chain"],
                map_tile=7,
            ),
            back=CardBack(
                demand_type="all_demand",
                multiplier=2,
                cleanup_actions=[
                    CleanupAction("move_distance", 0),
                    CleanupAction("move_waitress", -1),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", -1),
                ],
                develop_target="house_14",
                lobby_target="park_15",
                map_tile=2,
            ),
        )
    )

    # ── Card 8 ──────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=8,
            card_type=CardType.ACTION,
            card_number=8,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1,
                        "recruit_marketeer",
                        "Rural Marketeer",
                        fallback_food="burger",
                    ),
                    ActionSlot(2, "recruit_employee", "Pizza Chef"),
                    ActionSlot(3, "move_distance", "-1"),
                    ActionSlot(4, "recruit_employee", "Executive VP"),
                ],
                stars=["coffee_shop"],
                map_tile=8,
            ),
            back=CardBack(
                demand_type="all_demand",
                multiplier=2,
                cleanup_actions=[
                    CleanupAction("move_distance", 0),
                    CleanupAction("move_waitress", +1),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", 0),
                ],
                develop_target="house_14",
                lobby_target="park_9",
                map_tile=3,
            ),
        )
    )

    # ── Card 9 ──────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=9,
            card_type=CardType.ACTION,
            card_number=9,
            front=CardFront(
                actions=[
                    ActionSlot(1, "recruit_employee", "Executive VP"),
                    ActionSlot(2, "move_distance", "-3"),
                    ActionSlot(
                        3,
                        "recruit_employee",
                        "Gourmet Food Critic",
                        requires_module="coffee",
                        fallback_food="pizza",
                    ),
                    ActionSlot(4, "claim_milestone", "first_to_throw_away"),
                ],
                stars=["coffee_shop", "expand_chain"],
                map_tile=9,
            ),
            back=CardBack(
                demand_type="all_demand",
                multiplier=2,
                cleanup_actions=[
                    CleanupAction("move_distance", +2),
                    CleanupAction("move_waitress", 0),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", -2),
                ],
                develop_target="house_17",
                lobby_target="park_12",
                map_tile=4,
            ),
        )
    )

    # ── Card 10 ─────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=10,
            card_type=CardType.ACTION,
            card_number=10,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1, "recruit_marketeer", "Rural Marketeer", fallback_food="pizza"
                    ),
                    ActionSlot(2, "recruit_employee", "Burger Chef"),
                    ActionSlot(3, "move_distance", "-1"),
                    ActionSlot(4, "recruit_employee", "CFO"),
                ],
                stars=["develop"],
                map_tile=1,
            ),
            back=CardBack(
                demand_type="specific",
                food_items=["sushi", "noodle", "beer"],
                multiplier=1,
                cleanup_actions=[
                    CleanupAction("move_distance", +3),
                    CleanupAction("move_waitress", -2),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", 0),
                ],
                develop_target="house_19",
                lobby_target="park_10",
                map_tile=5,
            ),
        )
    )

    # ── Card 11 ─────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=11,
            card_type=CardType.ACTION,
            card_number=11,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1,
                        "recruit_marketeer",
                        "Kimchi Master",
                        requires_module="kimchi",
                        fallback_food="kimchi",
                    ),
                    ActionSlot(2, "recruit_employee", "CFO"),
                    ActionSlot(3, "recruit_employee", "Brand Manager"),
                    ActionSlot(4, "recruit_employee", "Luxuries Manager"),
                ],
                stars=["coffee_shop"],
                map_tile=2,
            ),
            back=CardBack(
                demand_type="most_demand",
                multiplier=1,
                cleanup_actions=[
                    CleanupAction("move_distance", +3),
                    CleanupAction("move_waitress", +3),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", 0),
                ],
                develop_target="garden_2",
                lobby_target="road",
                map_tile=6,
            ),
        )
    )

    # ── Card 12 ─────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=12,
            card_type=CardType.ACTION,
            card_number=12,
            front=CardFront(
                actions=[
                    ActionSlot(1, "recruit_employee", "Pizza Chef"),
                    ActionSlot(2, "move_waitress", "+1"),
                    ActionSlot(3, "recruit_employee", "Campaign Manager"),
                    ActionSlot(4, "recruit_employee", "HR Director"),
                ],
                stars=["coffee_shop", "expand_chain"],
                map_tile=3,
            ),
            back=CardBack(
                demand_type="most_demand",
                multiplier=1,
                cleanup_actions=[
                    CleanupAction("move_distance", +2),
                    CleanupAction("move_waitress", +2),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", 0),
                ],
                develop_target="garden_5",
                lobby_target="road",
                map_tile=7,
            ),
        )
    )

    # ── Card 13 ─────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=13,
            card_type=CardType.ACTION,
            card_number=13,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1,
                        "recruit_employee",
                        "Sushi Chef",
                        requires_module="sushi",
                        fallback_food="sushi",
                    ),
                    ActionSlot(2, "move_waitress", "+1"),
                    ActionSlot(3, "recruit_employee", "Marketing Trainee"),
                    ActionSlot(4, "recruit_employee", "HR Director"),
                ],
                stars=["lobby", "coffee_shop"],
                map_tile=4,
            ),
            back=CardBack(
                demand_type="most_demand",
                multiplier=1,
                cleanup_actions=[
                    CleanupAction("move_distance", +2),
                    CleanupAction("move_waitress", +1),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", 0),
                ],
                develop_target="garden_8",
                lobby_target="road",
                map_tile=8,
            ),
        )
    )

    # ── Card 14 ─────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=14,
            card_type=CardType.ACTION,
            card_number=14,
            front=CardFront(
                actions=[
                    ActionSlot(1, "recruit_employee", "Regional Manager"),
                    ActionSlot(2, "move_waitress", "+1"),
                    ActionSlot(3, "recruit_employee", "Campaign Manager"),
                    ActionSlot(4, "move_distance", "-3"),
                ],
                stars=["develop", "coffee_shop"],
                map_tile=5,
            ),
            back=CardBack(
                demand_type="most_demand",
                multiplier=1,
                cleanup_actions=[
                    CleanupAction("move_distance", 0),
                    CleanupAction("move_waitress", -1),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", -2),
                ],
                develop_target="garden_10",
                lobby_target="road",
                map_tile=9,
            ),
        )
    )

    # ── Card 15 ─────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=15,
            card_type=CardType.ACTION,
            card_number=15,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1,
                        "recruit_marketeer",
                        "Noodle Chef",
                        requires_module="noodle",
                        fallback_food="noodle",
                    ),
                    ActionSlot(2, "recruit_employee", "Regional Manager"),
                    ActionSlot(3, "move_waitress", "+1"),
                    ActionSlot(4, "recruit_employee", "Marketing Trainee"),
                ],
                stars=["expand_chain"],
                map_tile=6,
            ),
            back=CardBack(
                demand_type="most_demand",
                multiplier=1,
                cleanup_actions=[
                    CleanupAction("move_distance", +3),
                    CleanupAction("move_waitress", -3),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", 0),
                ],
                develop_target="garden_12",
                lobby_target="road",
                map_tile=1,
            ),
        )
    )

    # ── Card 16 ─────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=16,
            card_type=CardType.ACTION,
            card_number=16,
            front=CardFront(
                actions=[
                    ActionSlot(1, "recruit_employee", "Regional Manager"),
                    ActionSlot(2, "move_distance", "-1"),
                    ActionSlot(3, "recruit_employee", "Brand Manager"),
                    ActionSlot(4, "claim_milestone", "first_cart_operator"),
                ],
                stars=["develop", "lobby"],
                map_tile=7,
            ),
            back=CardBack(
                demand_type="specific",
                food_items=["burger", "sushi", "coffee"],
                multiplier=1,
                cleanup_actions=[
                    CleanupAction("move_distance", +3),
                    CleanupAction("move_waitress", 0),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", -2),
                ],
                develop_target="garden_13",
                lobby_target="road",
                map_tile=2,
            ),
        )
    )

    # ── Card 17 ─────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=17,
            card_type=CardType.ACTION,
            card_number=17,
            front=CardFront(
                actions=[
                    ActionSlot(1, "recruit_employee", "Night Shift Manager"),
                    ActionSlot(2, "move_distance", "-1"),
                    ActionSlot(3, "recruit_employee", "Brand Director"),
                    ActionSlot(4, "recruit_employee", "Burger Chef"),
                ],
                stars=["develop", "coffee_shop"],
                map_tile=8,
            ),
            back=CardBack(
                demand_type="all_demand",
                multiplier=2,
                cleanup_actions=[
                    CleanupAction("move_distance", +3),
                    CleanupAction("move_waitress", +2),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", 0),
                ],
                develop_target="garden_15",
                lobby_target="road",
                map_tile=3,
            ),
        )
    )

    # ── Card 18 ─────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=18,
            card_type=CardType.ACTION,
            card_number=18,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1,
                        "recruit_marketeer",
                        "Lead Barista",
                        requires_module="coffee",
                        fallback_food="coffee",
                    ),
                    ActionSlot(2, "recruit_employee", "Brand Director"),
                    ActionSlot(3, "claim_milestone", "first_errand_boy"),
                    ActionSlot(4, "get_food", "pizza"),
                ],
                stars=["develop", "coffee_shop"],
                map_tile=9,
            ),
            back=CardBack(
                demand_type="all_demand",
                multiplier=2,
                cleanup_actions=[
                    CleanupAction("move_distance", 0),
                    CleanupAction("move_waitress", -2),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", -2),
                ],
                develop_target="garden_16",
                lobby_target="road",
                map_tile=4,
            ),
        )
    )

    # ── Card 19 ─────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=19,
            card_type=CardType.ACTION,
            card_number=19,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1, "recruit_marketeer", "Mass Marketeer", fallback_food="burger"
                    ),
                    ActionSlot(2, "recruit_employee", "Pizza Chef"),
                    ActionSlot(3, "move_distance", "-1"),
                    ActionSlot(4, "recruit_employee", "Brand Director"),
                ],
                stars=["develop", "expand_chain"],
                map_tile=1,
            ),
            back=CardBack(
                demand_type="specific",
                food_items=["pizza", "noodle", "kimchi"],
                multiplier=1,
                cleanup_actions=[
                    CleanupAction("move_distance", +1),
                    CleanupAction("move_waitress", 0),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", -2),
                ],
                develop_target="garden_18",
                lobby_target="road",
                map_tile=5,
            ),
        )
    )

    # ── Card 20 ─────────────────────────────────────────────────────────
    cards.append(
        Card(
            id=20,
            card_type=CardType.ACTION,
            card_number=20,
            front=CardFront(
                actions=[
                    ActionSlot(
                        1,
                        "recruit_marketeer",
                        "Noodle Chef",
                        requires_module="noodle",
                        fallback_food="noodle",
                    ),
                    ActionSlot(2, "recruit_employee", "Luxuries Manager"),
                    ActionSlot(3, "recruit_employee", "Marketing Trainee"),
                    ActionSlot(4, "claim_milestone", "first_to_pay_20_salary"),
                ],
                stars=["develop"],
                map_tile=2,
            ),
            back=CardBack(
                demand_type="specific",
                food_items=["sushi", "beer", "lemonade"],
                multiplier=1,
                cleanup_actions=[
                    CleanupAction("move_distance", 0),
                    CleanupAction("move_waitress", -1),
                    CleanupAction("inventory_drop", 0),
                    CleanupAction("move_recruit_train", -3),
                ],
                develop_target="garden_21",
                lobby_target="road",
                map_tile=6,
            ),
        )
    )

    return cards


def build_warm_deck() -> list[Card]:
    """Build all 12 Warm (red) Competition cards."""
    cards = []

    # Set 1 (cards 1-4): EXPAND CHAIN effect
    for i, card_num in enumerate([1, 2, 3, 4]):
        food_adjs = [
            [{"item": "burger", "amount": 2}, {"item": "pizza", "amount": 2}],
            [{"item": "all_demand", "amount": 2}],
            [{"item": "sushi", "amount": 2}, {"item": "noodle", "amount": 2}],
            [{"item": "most_demand", "amount": 2}],
        ]
        cards.append(
            Card(
                id=100 + card_num,
                card_type=CardType.WARM,
                card_number=card_num,
                competition_effect=CompetitionEffect(
                    effect_type="expand_chain",
                    food_adjustments=food_adjs[i],
                    map_tile=(i % 9) + 1,
                ),
            )
        )

    # Set 2 (cards 5-8): COFFEE SHOP / EXPAND CHAIN effect
    for i, card_num in enumerate([5, 6, 7, 8]):
        food_adjs = [
            [{"item": "all_demand", "amount": 2}],
            [{"item": "burger", "amount": 2}, {"item": "lemonade", "amount": 2}],
            [{"item": "most_demand", "amount": 2}],
            [{"item": "pizza", "amount": 2}, {"item": "beer", "amount": 2}],
        ]
        cards.append(
            Card(
                id=100 + card_num,
                card_type=CardType.WARM,
                card_number=card_num,
                competition_effect=CompetitionEffect(
                    effect_type="coffee_shop_or_expand",
                    food_adjustments=food_adjs[i],
                    inventory_boost=True,
                    map_tile=(i % 9) + 5,
                ),
            )
        )

    # Set 3 (cards 9-12): +50% CASH EARNED THIS TURN
    for i, card_num in enumerate([9, 10, 11, 12]):
        food_adjs = [
            [{"item": "most_demand", "amount": 2}],
            [{"item": "sushi", "amount": 2}, {"item": "kimchi", "amount": 2}],
            [{"item": "all_demand", "amount": 2}],
            [{"item": "noodle", "amount": 2}, {"item": "coffee", "amount": 2}],
        ]
        cards.append(
            Card(
                id=100 + card_num,
                card_type=CardType.WARM,
                card_number=card_num,
                competition_effect=CompetitionEffect(
                    effect_type="bonus_cash",
                    food_adjustments=food_adjs[i],
                    map_tile=(i % 9) + 1,
                ),
            )
        )

    return cards


def build_cool_deck() -> list[Card]:
    """Build all 12 Cool (green) Competition cards."""
    cards = []

    # Set 1 (cards 1-4): NO DRIVE-INS THIS TURN
    for i, card_num in enumerate([1, 2, 3, 4]):
        loss_items = [
            ["burger"],
            ["pizza"],
            ["sushi"],
            ["noodle"],
        ]
        cards.append(
            Card(
                id=200 + card_num,
                card_type=CardType.COOL,
                card_number=card_num,
                competition_effect=CompetitionEffect(
                    effect_type="no_driveins",
                    inventory_loss_items=loss_items[i],
                    map_tile=(i % 9) + 1,
                ),
            )
        )

    # Set 2 (cards 5-8): FIRE ALL EMPLOYEES
    for i, card_num in enumerate([5, 6, 7, 8]):
        loss_items = [
            ["beer"],
            ["lemonade"],
            ["coffee"],
            ["kimchi"],
        ]
        cards.append(
            Card(
                id=200 + card_num,
                card_type=CardType.COOL,
                card_number=card_num,
                competition_effect=CompetitionEffect(
                    effect_type="fire_employees",
                    inventory_loss_items=loss_items[i],
                    map_tile=(i % 9) + 5,
                ),
            )
        )

    # Set 3 (cards 9-12): PAY $10 PER EMPLOYEE
    for i, card_num in enumerate([9, 10, 11, 12]):
        loss_items = [
            ["burger", "beer"],
            ["pizza", "lemonade"],
            ["sushi", "coffee"],
            ["noodle", "kimchi"],
        ]
        cards.append(
            Card(
                id=200 + card_num,
                card_type=CardType.COOL,
                card_number=card_num,
                competition_effect=CompetitionEffect(
                    effect_type="pay_per_employee",
                    inventory_loss_items=loss_items[i],
                    map_tile=(i % 9) + 1,
                ),
            )
        )

    return cards


def create_all_decks() -> tuple[Deck, Deck, Deck]:
    """Create and return (action_deck, warm_deck, cool_deck)."""
    action_cards = build_action_deck()
    warm_cards = build_warm_deck()
    cool_cards = build_cool_deck()

    action_deck = Deck(cards=action_cards, name="Action Deck")
    warm_deck = Deck(cards=warm_cards, name="Warm Competition")
    cool_deck = Deck(cards=cool_cards, name="Cool Competition")

    return action_deck, warm_deck, cool_deck
