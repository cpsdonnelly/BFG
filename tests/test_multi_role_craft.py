"""Multi-role attack craft (s.24) and random launch bay strength."""
import pytest
from tests.conftest import make_ship, make_gs, DiceStub
from src.models import OrdnanceMarker, OrdnanceType as OT
from src.ordnance import (craft_roles, is_fighter_type, attacks_ships,
                          friendly_ordnance_contact, resolve_ordnance_interactions,
                          resolve_bomber_attack, bay_launch_capacity,
                          fleet_craft_slots, mr_attack_mode_ai, craft_stats,
                          launch_attack_craft)


def _m(id, otype, player=1, x=50.0, y=50.0, **kw):
    return OrdnanceMarker(id=id, ordnance_type=otype, owner_player=player,
                          launched_by="s", x=x, y=y, **kw)


@pytest.mark.parametrize("otype,roles,fighter,attacks", [
    (OT.THUNDERHAWK, ("fighter", "bomber", "assault_boat"), True, True),
    (OT.GUN_CUTTER, ("fighter", "assault_boat"), True, True),
    (OT.FIGHTA_BOMMER, ("fighter", "bomber"), True, True),
    (OT.FIGHTER, ("fighter",), True, False),
    (OT.MANTA, ("bomber",), False, True),
])
def test_roles(otype, roles, fighter, attacks):
    assert craft_roles(otype.value) == roles
    assert is_fighter_type(_m("x", otype.value)) == fighter
    assert attacks_ships(otype.value) == attacks


def test_craft_stats():
    assert craft_stats("thunderhawk", []) == (OT.THUNDERHAWK.value, 20, 4)
    assert craft_stats("gun_cutter", []) == (OT.GUN_CUTTER.value, 20, 4)
    assert craft_stats("fighta_bommer", [{"craft_speeds": {"fighta_bommer": 25}}]) == (
        OT.FIGHTA_BOMMER.value, 25, 0)


def test_mr_fighters_must_intercept_friendly_torpedoes():
    assert friendly_ordnance_contact(_m("1", OT.THUNDERHAWK.value),
                                     _m("2", OT.TORPEDO_STANDARD.value)) == "intercept"
    assert friendly_ordnance_contact(_m("1", OT.FIGHTA_BOMMER.value),
                                     _m("2", OT.BOMBER.value)) is None


def test_enemy_fighter_vs_thunderhawk_resilient_save():
    gs = make_gs([])
    gs.add_ordnance(_m("f", OT.FIGHTER.value, player=1))
    gs.add_ordnance(_m("th", OT.THUNDERHAWK.value, player=2, resilient_save=4))
    rolls = [5]                                  # Thunderhawk passes its 4+ save
    dice = DiceStub(rolls)
    resolve_ordnance_interactions(gs, dice)
    assert dice._idx == len(rolls)
    assert [o["id"] for o in gs.ordnance] == ["th"]


def test_mr_fighter_intercepts_enemy_bomber():
    gs = make_gs([])
    gs.add_ordnance(_m("fb", OT.FIGHTA_BOMMER.value, player=1))
    gs.add_ordnance(_m("b", OT.BOMBER.value, player=2))
    resolve_ordnance_interactions(gs, DiceStub([1]))
    assert gs.ordnance == []


# ── Fighta-Bommerz: D3+1 attacks, never below 1 ─────────────────────────────

def test_fighta_bommerz_attacks_d3_plus_1_minus_turrets():
    target = make_ship(id="t", player=2, turrets=2, armor_prow="6+", armor_side="5+")
    gs = make_gs([target])
    rolls = [3,          # D3 = 3 -> 4 attacks - 2 turrets = 2
             5, 4]       # vs lowest armour 5+: one hit
    dice = DiceStub(rolls + [1])               # + crit check for the hit
    r = resolve_bomber_attack(_m("fb", OT.FIGHTA_BOMMER.value), target, dice, gs)
    assert r["attacks"] == 2 and r["hits"] == 1
    assert dice._idx == len(rolls) + 1


def test_fighta_bommerz_always_get_one_attack():
    target = make_ship(id="t", player=2, turrets=5, armor_prow="6+", armor_side="5+")
    gs = make_gs([target])
    rolls = [1,          # D3 = 1 -> 2 attacks - 5 turrets -> minimum 1
             2]
    dice = DiceStub(rolls)
    r = resolve_bomber_attack(_m("fb", OT.FIGHTA_BOMMER.value), target, dice, gs,
                              suppressed_by_fighter=True)   # can't be suppressed
    assert r["attacks"] == 1 and dice._idx == len(rolls)


def test_mr_attack_mode_ai():
    assert mr_attack_mode_ai(make_ship(turrets=3)) == "assault_boat"
    assert mr_attack_mode_ai(make_ship(turrets=2)) == "bomber"


# ── Random launch bays: rolled at launch, max counts for the craft limit ────

BAYS = [{"name": "Dorsal Launch Bays", "weapon_type": "launch_bay", "strength": 4,
         "strength_dice": "D3+1", "craft_types": ["fighta_bommer", "assault_boat"],
         "craft_speeds": {"fighta_bommer": 25, "assault_boat": 30}},
        {"name": "Port Launch Bays", "weapon_type": "launch_bay", "strength": 2,
         "craft_types": ["fighta_bommer", "assault_boat"],
         "craft_speeds": {"fighta_bommer": 25, "assault_boat": 30}}]


def test_bay_capacity_rolls_random_bays_then_halves():
    ship = make_ship(id="o", player=1, weapons=BAYS)
    rolls = [2]                                  # D3 = 2 -> 3 + 2 fixed = 5
    dice = DiceStub(rolls)
    cap, log = bay_launch_capacity(ship, BAYS, dice)
    assert cap == 5 and dice._idx == 1 and "rolled D3+1 = 3" in log[0]
    ship.special_order = "brace_for_impact"
    assert bay_launch_capacity(ship, BAYS, DiceStub([2]))[0] == 3


def test_fleet_craft_slots_count_random_bays_at_maximum():
    ship = make_ship(id="o", player=1, weapons=BAYS)
    gs = make_gs([ship])
    assert fleet_craft_slots(gs, 1) == 6
    launch_attack_craft(ship, BAYS[0], "fighta_bommer", 2, gs)
    assert fleet_craft_slots(gs, 1) == 4
    assert {o["ordnance_type"] for o in gs.ordnance} == {OT.FIGHTA_BOMMER.value}
    assert gs.ordnance[0]["speed"] == 25


# ── Owner ruling: "5+ / 4+R" ─────────────────────────────────────────────────

def test_explorer_rear_armour():
    from src.ship_catalog import find_ship_class
    e = find_ship_class("Explorer Starship")
    assert e.playable and (e.armor_prow, e.armor_side, e.armor_rear) == ("5+", "5+", "4+")


# ── Recalling attack craft (s.15) ────────────────────────────────────────────
from src.ordnance import fleet_craft_excess, recall_craft, ai_craft_to_recall


def test_recall_frees_capacity_and_excess_after_losses():
    ship = make_ship(id="o", player=1, weapons=[dict(BAYS[1])])      # 2 bays
    gs = make_gs([ship])
    launch_attack_craft(ship, BAYS[1], "fighta_bommer", 2, gs)
    assert fleet_craft_slots(gs, 1) == 0 and fleet_craft_excess(gs, 1) == 0
    ids = [o["id"] for o in gs.ordnance]
    assert recall_craft(gs, 1, ids[:1]) == 1 and fleet_craft_slots(gs, 1) == 1
    assert recall_craft(gs, 2, ids[1:]) == 0                         # not your craft
    s = gs.get_ship_by_id("o")
    s.status = "destroyed"
    gs.update_ship(s)
    assert fleet_craft_excess(gs, 1) == 1                            # bays lost


def test_ai_recalls_oldest_and_keeps_cap():
    gs = make_gs([])
    gs.add_ordnance(_m("old", OT.BOMBER.value, launched_turn=1))
    gs.add_ordnance(_m("new", OT.BOMBER.value, launched_turn=3))
    gs.add_ordnance(_m("cap", OT.FIGHTER.value, launched_turn=0, cap_ship_id="x"))
    assert ai_craft_to_recall(gs, 1, 2) == ["old", "new"]
