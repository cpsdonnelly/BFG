"""Short burn torpedoes and barrage bombs (core rules s.16), Promethean
Unguents barrage bombs (Space Marine Chapter tactic), and the Imperial Navy /
Chaos option to buy them (owner ruling: one type per ship, carried in addition
to its other torpedoes, +5pts per torpedo strength)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.models import OrdnanceMarker, OrdnanceType
from src.ordnance import (resolve_torpedo_attack, launch_torpedoes, torpedo_kind_options,
                          torpedo_ordnance_type, short_burn_fuel_checks, resolve_mine_contact,
                          ordnance_turrets)
from src.ship_catalog import find_ship_class

TORPS = {"name": "Prow Torps", "weapon_type": "torpedo", "strength": 6,
         "range_cm": 30, "arcs": ["front"]}
BOARDING_TORPS = {**TORPS, "boarding_torpedoes": True}


def _marker(o_type, strength=3, rules=None):
    # Abeam of the target (side armour 5+)
    return OrdnanceMarker(id="tp", ordnance_type=o_type, owner_player=1, launched_by="a",
                          x=50.0, y=55.0, heading=270.0, strength=strength,
                          special_rules=list(rules or []))


def _target(**kw):
    base = dict(id="t", player=2, x=50.0, y=50.0, heading=0.0, hits_max=8, turrets=0,
                shields_max=0, armor_prow="6+", armor_side="5+")
    base.update(kw)
    return make_ship(**base)


# ── Loads and launching ──────────────────────────────────────────────────────

def test_kind_options_add_bought_type_to_standard_and_boarding():
    ship = make_ship(special_rules=["torpedo_type:short_burn"])
    assert [k for k, _ in torpedo_kind_options(ship, BOARDING_TORPS)] == [
        "standard", "boarding", "short_burn"]
    assert [k for k, _ in torpedo_kind_options(make_ship(), TORPS)] == ["standard"]
    assert torpedo_ordnance_type(TORPS, kind="barrage") == OrdnanceType.TORPEDO_BARRAGE.value
    assert torpedo_ordnance_type(TORPS, kind="") == OrdnanceType.TORPEDO_STANDARD.value


def test_short_burn_salvo_moves_40cm():
    ship = make_ship(id="a", special_rules=["torpedo_type:short_burn"], weapons=[TORPS])
    gs = make_gs([ship])
    m = launch_torpedoes(ship, ship.weapons[0], gs, kind="short_burn")
    assert m.ordnance_type == OrdnanceType.TORPEDO_SHORT_BURN.value and m.speed == 40
    assert m.strength == 6


# ── Short burn: out of fuel on a 6 ───────────────────────────────────────────

def test_short_burn_runs_out_of_fuel_on_a_6():
    gs = make_gs([])
    for i, oid in enumerate(("sb1", "sb2")):
        gs.add_ordnance(OrdnanceMarker(id=oid, ordnance_type=OrdnanceType.TORPEDO_SHORT_BURN.value,
                                       owner_player=1, launched_by="a", x=10.0 + i, y=20.0))
    gs.add_ordnance(OrdnanceMarker(id="std", ordnance_type=OrdnanceType.TORPEDO_STANDARD.value,
                                   owner_player=1, launched_by="a"))
    rolls = [6, 5]                     # sb1 out of fuel, sb2 carries on
    dice = DiceStub(rolls)
    short_burn_fuel_checks(gs, dice, player=1)
    assert dice._idx == len(rolls)
    assert [o["id"] for o in gs.ordnance] == ["sb2", "std"]
    bms = gs.get_blast_markers()
    assert len(bms) == 1 and (bms[0].x, bms[0].y) == (10.0, 20.0)


def test_short_burn_fuel_only_for_the_moving_player():
    gs = make_gs([])
    gs.add_ordnance(OrdnanceMarker(id="sb", ordnance_type=OrdnanceType.TORPEDO_SHORT_BURN.value,
                                   owner_player=2, launched_by="a"))
    dice = DiceStub([])
    short_burn_fuel_checks(gs, dice, player=1)
    assert dice._idx == 0 and len(gs.ordnance) == 1


# ── Barrage bombs: shields stop the hits ─────────────────────────────────────

def test_barrage_bomb_hits_are_stopped_by_shields():
    target = _target(shields_max=1)
    gs = make_gs([target])
    rolls = [5, 6, 2,      # vs side armour 5+: two hits
             4]            # one gets past the shield: crit check (needs 6)
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_BARRAGE.value), target, dice, gs)
    assert dice._idx == len(rolls)
    t = gs.get_ship_by_id("t")
    assert r["hits"] == 2 and t.hits_remaining == 7       # one blocked, one damage
    assert len(gs.get_blast_markers()) == 1               # the shield impact


def test_standard_torpedoes_still_ignore_shields():
    target = _target(shields_max=1)
    gs = make_gs([target])
    rolls = [5, 6, 2, 4, 3]
    dice = DiceStub(rolls)
    resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_STANDARD.value), target, dice, gs)
    assert dice._idx == len(rolls)
    assert gs.get_ship_by_id("t").hits_remaining == 6


# ── Promethean Unguents ──────────────────────────────────────────────────────

PROMETHEAN = ["space_marine_crew", "chapter_tactic:promethean_unguents"]


def test_promethean_barrage_hits_on_4_places_markers_no_damage():
    target = _target(armor_side="6+", turrets=3)
    gs = make_gs([target])
    rolls = [1, 2, 3,      # turrets vs the salvo: none shot down
             4, 5, 1]      # always hit on 4+ (armour 6+ ignored): two hits
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_BARRAGE.value, rules=PROMETHEAN),
                               target, dice, gs)
    assert dice._idx == len(rolls)
    t = gs.get_ship_by_id("t")
    assert r["hits"] == 2 and t.hits_remaining == 8
    assert len(gs.get_blast_markers()) == 2
    assert t.turrets_halved_turn == gs.turn_number
    assert ordnance_turrets(t, gs) == 2                    # 3 halved, rounding up


def test_promethean_halving_lasts_for_one_ordnance_attack_only():
    target = _target(turrets=3)
    target.turrets_halved_turn = 1
    gs = make_gs([target])
    gs.turn_number = 1
    rolls = [1, 1,         # halved turrets: 2 dice vs the next salvo
             1, 1, 1]      # attack: misses
    dice = DiceStub(rolls)
    resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_STANDARD.value),
                           gs.get_ship_by_id("t"), dice, gs)
    assert dice._idx == len(rolls)
    t = gs.get_ship_by_id("t")
    assert t.turrets_halved_turn == -1 and ordnance_turrets(t, gs) == 3
    # A later mine attack faces full turrets again
    rolls = [1, 1, 1] + [1] * 8
    dice = DiceStub(rolls)
    resolve_mine_contact(_marker(OrdnanceType.MINE_FIELD.value), t, dice, gs)
    assert dice._idx == len(rolls)


def test_halving_set_on_an_earlier_turn_does_not_apply():
    target = _target(turrets=3)
    target.turrets_halved_turn = 1
    gs = make_gs([target])
    gs.turn_number = 2
    assert ordnance_turrets(gs.get_ship_by_id("t"), gs) == 3


def test_barrage_without_promethean_uses_armour():
    target = _target(armor_side="6+")
    gs = make_gs([target])
    rolls = [4, 5, 1]      # no hits against 6+
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_BARRAGE.value), target, dice, gs)
    assert dice._idx == len(rolls) and r["hits"] == 0


# ── Fleet builder option ─────────────────────────────────────────────────────

def test_navy_and_chaos_torpedo_ships_may_buy_one_type():
    lunar = find_ship_class("Lunar Cruiser")
    opts = {u.name: u for u in lunar.upgrades_available if u.name.startswith("Torpedoes:")}
    assert len(opts) == 2 and {u.points_cost for u in opts.values()} == {30}   # S6 x 5
    sb = next(u for u in opts.values() if "short burn" in u.name)
    d = lunar.to_ship_dict("L", 1, upgrades=[sb.name])
    assert "torpedo_type:short_burn" in d["special_rules"]
    assert d["points_value"] == lunar.points_cost + 30
    from src.booklet_options import ship_option_errors
    assert ship_option_errors(lunar, list(opts))        # only one type per ship
    assert find_ship_class("Cobra Destroyer").upgrades_available[0].points_cost == 10
    assert any(u.name.startswith("Torpedoes:")
               for u in find_ship_class("Desolator Battleship").upgrades_available)
    assert not any(u.name.startswith("Torpedoes:")
                   for u in find_ship_class("Murder Cruiser").upgrades_available)  # no torps


# ── AI ───────────────────────────────────────────────────────────────────────

def _ai_launch(distance):
    from src.ai_player import AIPlayer
    ship = make_ship(id="a", player=1, x=10.0, y=50.0, heading=0.0, weapons=[dict(TORPS)],
                     special_rules=["torpedo_type:short_burn"])
    ship.ordnance_loaded_torps = True
    enemy = make_ship(id="e", player=2, x=10.0 + distance, y=50.0, heading=180.0)
    gs = make_gs([ship, enemy])
    AIPlayer(player=1, tc=None, gs=gs, dice=DiceStub([]))._launch_ship_ordnance(
        gs.get_ship_by_id("a"))
    return gs.get_ordnance()


def test_ai_uses_short_burn_beyond_standard_reach():
    far = _ai_launch(45)
    assert [m.ordnance_type for m in far] == [OrdnanceType.TORPEDO_SHORT_BURN.value]
    near = _ai_launch(20)
    assert [m.ordnance_type for m in near] == [OrdnanceType.TORPEDO_STANDARD.value]


# ── Torpedoes attack what they touch anywhere along their move (s.15) ───────

def test_torpedo_first_contact_along_the_path():
    from src.geometry import torpedo_first_contact
    # Salvo moves 80 -> 110 along y=60, over a ship at x=95 (radius 2): touches it
    hit = torpedo_first_contact(95.0, 60.0, 2.0, 80.0, 60.0, 110.0, 60.0, 0.0)
    assert hit is not None and 80.0 < hit[0] < 95.0
    # The same move 10cm to the side never touches it
    assert torpedo_first_contact(95.0, 75.0, 2.0, 80.0, 60.0, 110.0, 60.0, 0.0) is None
