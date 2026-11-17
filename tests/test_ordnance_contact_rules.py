"""Ordnance rules from booklet export 3: s.15-19 (first contact, splitting salvos,
torpedo types, attack craft vs ordnance)."""
import pytest
from tests.conftest import make_ship, make_gs, DiceStub
from src.models import OrdnanceMarker, OrdnanceType as OT
from src.ordnance import (friendly_ordnance_contact, resolve_ordnance_interactions,
                          torpedo_split_error, craft_stats, boarding_torp_may_turn,
                          boarding_torp_suggested_turn, turn_boarding_torp)


def _m(id, otype, player=1, x=50.0, y=50.0, heading=0.0, **kw):
    return OrdnanceMarker(id=id, ordnance_type=otype, owner_player=player,
                          launched_by="s", x=x, y=y, heading=heading, **kw)


# ── Friendly markers (s.16, s.17, s.19, s.20, s.22) ─────────────────────────

@pytest.mark.parametrize("a,b,expected", [
    (OT.TORPEDO_STANDARD, OT.TORPEDO_STANDARD, "collide"),     # torps hit torps
    (OT.TORPEDO_BOARDING, OT.TORPEDO_STANDARD, "collide"),     # boarding still detonate
    (OT.FIGHTER, OT.TORPEDO_STANDARD, "intercept"),            # fighters: friend or foe
    (OT.TORPEDO_STANDARD, OT.BARRACUDA, "intercept"),
    (OT.FIGHTER, OT.TORPEDO_BOARDING, None),                   # boarding ignore friendly craft
    (OT.BOMBER, OT.TORPEDO_STANDARD, None),                    # bombers avoid
    (OT.ASSAULT_BOAT, OT.TORPEDO_STANDARD, None),              # assault boats avoid
    (OT.MINE_FIELD, OT.TORPEDO_STANDARD, None),                # mines ignore ordnance
    (OT.MINE_FIELD, OT.FIGHTER, None),                         # ...except enemy fighters
    (OT.TORPEDO_BOMBER, OT.TORPEDO_STANDARD, None),            # torpedo bombers are craft
    (OT.FIGHTER, OT.BOMBER, None),
])
def test_friendly_ordnance_contact(a, b, expected):
    assert friendly_ordnance_contact(_m("1", a.value), _m("2", b.value)) == expected
    assert friendly_ordnance_contact(_m("1", b.value), _m("2", a.value)) == expected


def test_friendly_bomber_and_torpedo_both_stay():
    gs = make_gs([])
    gs.add_ordnance(_m("b", OT.BOMBER.value))
    gs.add_ordnance(_m("t", OT.TORPEDO_STANDARD.value))
    dice = DiceStub([1])
    resolve_ordnance_interactions(gs, dice)
    assert sorted(o["id"] for o in gs.ordnance) == ["b", "t"]
    assert dice._idx == 0


def test_friendly_fighter_intercepts_standard_but_not_boarding_torps():
    gs = make_gs([])
    gs.add_ordnance(_m("f", OT.FIGHTER.value))
    gs.add_ordnance(_m("bt", OT.TORPEDO_BOARDING.value))
    resolve_ordnance_interactions(gs, DiceStub([1]))
    assert sorted(o["id"] for o in gs.ordnance) == ["bt", "f"]

    gs = make_gs([])
    gs.add_ordnance(_m("f", OT.FIGHTER.value))
    gs.add_ordnance(_m("t", OT.TORPEDO_STANDARD.value))
    resolve_ordnance_interactions(gs, DiceStub([1]))
    assert gs.ordnance == []


def test_resilient_friendly_fighter_may_save_against_torpedoes():
    gs = make_gs([])
    gs.add_ordnance(_m("f", OT.FIGHTER.value, resilient_save=4))
    gs.add_ordnance(_m("t", OT.TORPEDO_STANDARD.value))
    rolls = [4]
    dice = DiceStub(rolls)
    resolve_ordnance_interactions(gs, dice)
    assert dice._idx == len(rolls)
    assert [o["id"] for o in gs.ordnance] == ["f"]
    assert gs.ordnance[0]["resilient_used"] is True


# ── Splitting torpedo salvos (s.16) ─────────────────────────────────────────

def test_split_rules():
    assert torpedo_split_error(8, 8, 0, None) is None            # not split
    assert torpedo_split_error(6, 3, 0, 20) is not None          # Str 7+ only
    assert "at least 3" in torpedo_split_error(8, 2, 0, 20)
    assert "at least 3" in torpedo_split_error(8, 6, 0, 20)
    assert "different directions" in torpedo_split_error(8, 4, 10, 10)
    assert "different directions" in torpedo_split_error(8, 4, 10, None)
    assert torpedo_split_error(8, 4, 10, 30) is None
    assert torpedo_split_error(7, 3, 350, 20) is None


# ── Attack craft launched as their own type (s.18) ──────────────────────────

def test_craft_stats_use_booklet_types_and_speeds():
    bays = [{"weapon_type": "launch_bay", "craft_speeds": {"shark_assault_boat": 30,
                                                          "starhawk_bomber": 20}}]
    assert craft_stats("shark_assault_boat", bays) == (OT.ASSAULT_BOAT.value, 30, 0)
    assert craft_stats("bomber", [{"craft_speeds": {"bomber": 25}}]) == (OT.BOMBER.value, 25, 0)
    assert craft_stats("assault_boat", []) == (OT.ASSAULT_BOAT.value, 30, 0)


# ── Boarding torpedoes turn up to 45° before moving (s.16) ──────────────────

def test_boarding_torps_turn_only_after_launch_turn():
    m = _m("bt", OT.TORPEDO_BOARDING.value, launched_turn=2)
    assert not boarding_torp_may_turn(m, 2)
    assert boarding_torp_may_turn(m, 3)
    std = _m("t", OT.TORPEDO_STANDARD.value, launched_turn=1)
    assert not boarding_torp_may_turn(std, 3)


def test_boarding_torp_suggested_turn_points_at_nearest_enemy_up_to_45():
    m = _m("bt", OT.TORPEDO_BOARDING.value, heading=0.0)
    near = make_ship(id="e1", player=2, x=60.0, y=60.0)       # 45° anticlockwise
    far = make_ship(id="e2", player=2, x=50.0, y=10.0)
    friend = make_ship(id="f", player=1, x=52.0, y=48.0)
    assert boarding_torp_suggested_turn(m, [far, near, friend]) == pytest.approx(45.0)
    behind = make_ship(id="e3", player=2, x=40.0, y=50.0)     # 180°: clamped
    assert abs(boarding_torp_suggested_turn(m, [behind])) == pytest.approx(45.0)


def test_turn_boarding_torp_clamps_to_45():
    m = _m("bt", OT.TORPEDO_BOARDING.value, heading=10.0)
    turn_boarding_torp(m, -90)
    assert m.heading == pytest.approx(325.0)


# ── Torpedoes: once per full turn, launch-turn arc (s.16) ───────────────────
from src.ordnance import torpedo_may_attack


def _torp_gs(turn, launched_turn, target_xy=(80.0, 50.0)):
    torps = {"name": "Prow Torps", "weapon_type": "torpedo", "strength": 6,
             "arcs": ["front"]}
    launcher = make_ship(id="L", player=1, x=50.0, y=50.0, heading=0.0, weapons=[torps])
    target = make_ship(id="T", player=2, x=target_xy[0], y=target_xy[1])
    gs = make_gs([launcher, target])
    gs.turn_number = turn
    m = _m("t", OT.TORPEDO_STANDARD.value, x=target_xy[0], y=target_xy[1],
           launched_turn=launched_turn)
    m.launched_by = "L"
    return gs, m, gs.get_ship_by_id("T")


def test_launch_turn_target_must_be_in_the_launch_arc():
    gs, m, t = _torp_gs(turn=3, launched_turn=3, target_xy=(80.0, 50.0))   # ahead
    assert torpedo_may_attack(m, t, gs)
    gs, m, t = _torp_gs(turn=3, launched_turn=3, target_xy=(50.0, 80.0))   # abeam
    assert not torpedo_may_attack(m, t, gs)
    gs, m, t = _torp_gs(turn=4, launched_turn=3, target_xy=(50.0, 80.0))   # next turn
    assert torpedo_may_attack(m, t, gs)


def test_salvo_attacks_a_ship_at_most_once_per_full_turn():
    gs, m, t = _torp_gs(turn=5, launched_turn=2)
    m.attacked_turns = {"T": 5}
    assert not torpedo_may_attack(m, t, gs)          # same player-turn
    gs.turn_number = 6
    assert not torpedo_may_attack(m, t, gs)          # opponent's turn: same full turn
    gs.turn_number = 7
    assert torpedo_may_attack(m, t, gs)


# ── Ships moving into ordnance during their own move (s.15) ─────────────────
from src.movement import ordnance_touched_along_path, validate_movement, execute_movement, MoveCommand


def test_path_contacts_in_order_reached():
    ship = make_ship(id="s", player=1, x=10.0, y=50.0, heading=0.0)
    gs = make_gs([ship])
    gs.add_ordnance(_m("far", OT.BOMBER.value, player=2, x=40.0, y=50.0))
    gs.add_ordnance(_m("near", OT.TORPEDO_STANDARD.value, player=2, x=20.0, y=50.0,
                       heading=180.0))
    gs.add_ordnance(_m("off", OT.BOMBER.value, player=2, x=30.0, y=80.0))
    gs.add_ordnance(_m("cap", OT.FIGHTER.value, player=2, x=30.0, y=50.0, cap_ship_id="x"))
    path = [(10.0, 50.0), (45.0, 50.0)]
    assert ordnance_touched_along_path(ship, path, gs) == ["near", "far"]


def test_execute_movement_records_markers_passed_through():
    ship = make_ship(id="s", player=1, x=10.0, y=50.0, heading=0.0, speed=20)
    gs = make_gs([ship])
    gs.add_ordnance(_m("b", OT.BOMBER.value, player=2, x=20.0, y=50.0))   # passed, not at end
    r = validate_movement(ship, [MoveCommand("forward", 20)], "none")
    execute_movement(ship, r, gs)
    assert gs.get_ship_by_id("s").pending_ordnance_contacts == ["b"]
