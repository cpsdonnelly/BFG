"""Eldar MMS v2.0 first slice (To do 14; bfgxr/rules/08_eldar.md)."""
from tests.conftest import DiceStub
from src import eldar


def test_speeds_and_aspects():
    sp = eldar.parse_speeds("10/15/20")
    assert sp == (10, 15, 20)
    assert eldar.parse_holofield("2+H") == 2 and eldar.parse_holofield("2") is None
    # sunward edge north (90 degrees): into the sun, away, abeam
    assert eldar.speed_for(sp, 90.0) == 10
    assert eldar.speed_for(sp, 270.0) == 15
    assert eldar.speed_for(sp, 0.0) == 20 and eldar.speed_for(sp, 135.0) == 20
    assert eldar.sun_aspect(0.0, "east") == eldar.SUN


def test_two_moves_turning_on_the_spot():
    sp = (10, 15, 20)
    ok = [(0.0, 20.0), (45.0, 10.0)]      # abeam 20, then turn into the sun at 45 -> abeam
    assert eldar.validate_mms_move(sp, 0.0, 45.0, ok) == []
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(90.0, 5.0)])         # beyond 45
    assert eldar.validate_mms_move(sp, 90.0, 45.0, [(0.0, 12.0)])        # into the sun: 10
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(0, 1), (0, 1), (0, 1)])
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(0.0, 5.0)], order="burn_retros")
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(10.0, 5.0)], order="lock_on")
    # All Ahead Full: +5D6 on one move only, no turns
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(0, 35.0), (0, 20.0)],
                                   order="all_ahead_full", aaf_bonus=17.0) == []
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(0, 35.0), (0, 30.0)],
                                   order="all_ahead_full", aaf_bonus=17.0)
    # Come to New Heading: one extra turn at the end of the second move
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(0, 10), (0, 10)],
                                   order="come_to_new_heading", extra_turn=45.0) == []
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(0, 10)], extra_turn=45.0)
    x, y, h = eldar.mms_end(0.0, 0.0, 0.0, [(0.0, 10.0), (90.0, 10.0)])
    assert abs(x - 10) < 1e-9 and abs(y - 10) < 1e-9 and abs(h - 90) < 1e-9


def test_holofields_and_fragile():
    assert eldar.holofield_gunnery_shift(14.9) == 0 and eldar.holofield_gunnery_shift(20) == 1
    assert eldar.holofield_save(31) == 5 and eldar.holofield_save(30) == 6
    assert eldar.holofield_save(10) is None
    dice = DiceStub([5, 6, 4])
    assert eldar.holofield_saves(dice, 3, 25.0) == 1 and dice._idx == 3
    assert abs(eldar.p_holofield_save(40) - 1 / 3) < 1e-9

    class S:
        special_rules = ["fragile"]
    assert eldar.crit_threshold(S()) == 5
    S.special_rules = ["fragile", "ghostship"]
    assert eldar.crit_threshold(S()) == 6


def test_eldar_catalog_stats():
    """The catalog reads the MMS profiles: three speeds (max as the speed), the
    holofield as the shields, Fragile / holofield / MMS rules, Eldar weapon
    flags and keel launch bays. Still unsupported until the rules are wired."""
    from src.ship_catalog import find_ship_class
    e = find_ship_class("Eclipse Class Cruiser")
    d = e.to_ship_dict("Eclipse Class Cruiser", 1)
    assert d["speed"] == 25 and d["shields_max"] == 2 and d["turn_angle"] == 45
    assert {"eldar_mms", "fragile", "holofield", "eldar_speeds:10/20/25"} <= set(d["special_rules"])
    lance = next(w for w in d["weapons"] if w["weapon_type"] == "lance")
    bays = next(w for w in d["weapons"] if w["weapon_type"] == "launch_bay")
    assert lance.get("pulsar") and bays["craft_types"] == ["eldar_fighter", "eldar_bomber"]
    assert bays["strength"] == 4
    shadow = find_ship_class("Shadow Class Cruiser").to_ship_dict("s", 1)
    assert any(w.get("eldar_battery") for w in shadow["weapons"])
    assert any(w.get("eldar_torpedo") for w in shadow["weapons"])
    assert any("MMS" in u for u in e.unsupported)


def _eldar_pair(dist=40.0):
    from src.ship_catalog import find_ship_class
    from src.models import Ship
    from tests.conftest import make_ship
    e = Ship.from_dict(find_ship_class("Eclipse Class Cruiser").to_ship_dict("Eclipse Class Cruiser", 1,
                                                                             ship_id="ecl"))
    e.x, e.y, e.heading = 0.0, 0.0, 0.0
    t = make_ship(id="t", player=2, x=dist, y=0.0, special_rules=["holofield", "fragile"])
    return e, t


def test_holofield_and_eldar_battery_shifts():
    from src.combat import get_column_shifts
    from tests.conftest import make_ship
    shooter = make_ship(id="s", player=1, x=0.0, y=0.0)
    far = make_ship(id="f", player=2, x=20.0, y=0.0, special_rules=["holofield"])
    near = make_ship(id="n", player=2, x=10.0, y=0.0, special_rules=["holofield"])
    plain = make_ship(id="p", player=2, x=20.0, y=0.0)
    assert get_column_shifts(shooter, far, []) == get_column_shifts(shooter, plain, []) + 1
    assert get_column_shifts(shooter, near, []) == -1           # within 15cm: no holofield
    assert get_column_shifts(shooter, plain, [], weapon={"eldar_battery": True}) == \
        get_column_shifts(shooter, plain, []) - 1


def test_pulsar_chain_and_holofield_save():
    from src.combat import resolve_lances
    e, t = _eldar_pair(40.0)
    lance = {"name": "Prow Pulsar Lance", "weapon_type": "lance", "strength": 2, "pulsar": True,
             "range_cm": 30}
    # dice 5 (hit) -> follow-ups 4 (hit), 2 (stop); 3 (miss); holofield 5+ at 40cm: 5, 1
    dice = DiceStub([5, 3, 4, 2, 5, 1])
    r = resolve_lances(e, t, lance, dice)
    assert r.hits == 1 and dice._idx == 6           # 2 hits, one thwarted
    # third hit caps the chain: 6 -> 6, 6 (3 hits), second die 1; no holofield target
    t.special_rules = []
    dice = DiceStub([6, 1, 6, 6])
    assert resolve_lances(e, t, lance, dice).hits == 3 and dice._idx == 4
    # Lock On re-rolls only the first miss: 1 (re-roll 5 -> follow-up 1), 2 stays a miss
    dice = DiceStub([1, 2, 5, 1])
    assert resolve_lances(e, t, lance, dice, lock_on=True).hits == 1 and dice._idx == 4


def test_phantom_lances_and_fragile():
    from src.combat import resolve_lances, apply_damage
    from src.game_state import GameState
    e, t = _eldar_pair(10.0)                         # within 15cm: no holofield save
    t.special_rules = []
    lance = {"name": "Prow Phantom Lance", "weapon_type": "lance", "strength": 3, "phantom": True}
    dice = DiceStub([6, 4, 3])
    assert resolve_lances(e, t, lance, dice).hits == 3 and dice._idx == 3
    gs = GameState()
    t.shields_max = 0
    t.special_rules = ["fragile"]
    gs.add_ship(t)
    dice = DiceStub([5])                              # 5 is a crit for a Fragile ship
    out = apply_damage(gs.get_ship_by_id("t"), 1, dice, gs, ignores_shields=True)
    assert out["hull_hits"] == 1 and len(out["crits"]) == 1
