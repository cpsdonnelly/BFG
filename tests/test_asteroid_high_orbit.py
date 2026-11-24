"""A carrier parked in high orbit inside an asteroid field (owner check):
s.41 high orbit needs no move; s.39 asteroid fields test only ships moving
through or into them, block direct fire from outside, let ships inside fire
at each other within 10cm at half firepower (no close range shift, never
crippled or braced), and attack craft moving out of one roll the 6."""
from tests.conftest import make_ship, make_gs, make_marker, DiceStub
from src.models import Phenomenon
from src.movement import validate_movement, execute_movement, MoveCommand
from src.combat import (check_los_clear, get_column_shifts, effective_battery_firepower)
from src.ordnance import check_ordnance_vs_phenomena

PLANET = Phenomenon(id="pl", phenomenon_type="planet_medium", x=60.0, y=60.0, radius=5.0)
FIELD = Phenomenon(id="ast", phenomenon_type="asteroid_field", x=60.0, y=75.0,
                   width=15.0, height=10.0)   # in the planet's 20cm gravity well
BATTERY = {"name": "Port Batteries", "weapon_type": "battery", "strength": 6,
           "range_cm": 30, "arcs": ["left", "right", "front"]}


def _game(*ships):
    gs = make_gs(list(ships))
    gs.add_phenomenon(PLANET)
    gs.add_phenomenon(FIELD)
    return gs


def _carrier(**kw):
    base = dict(id="c", player=1, x=60.0, y=75.0, heading=0.0, speed=20, weapons=[BATTERY])
    base.update(kw)
    return make_ship(**base)


def test_a_ship_in_high_orbit_may_stay_still():
    gs = _game(_carrier())
    c = gs.get_ship_by_id("c")
    assert not validate_movement(c, [], "").errors
    away = make_ship(id="far", player=1, x=10.0, y=10.0, speed=20)
    gs.add_ship(away)
    assert validate_movement(gs.get_ship_by_id("far"), [], "").errors


def test_no_asteroid_test_standing_still_but_one_moving_through():
    gs = _game(_carrier())
    c = gs.get_ship_by_id("c")
    execute_movement(c, validate_movement(c, [], ""), gs)
    assert "in_asteroid_field" not in gs.get_ship_by_id("c").special_rules
    s = make_ship(id="s", player=1, x=45.0, y=75.0, heading=0.0, speed=40)
    gs.add_ship(s)
    s = gs.get_ship_by_id("s")
    res = validate_movement(s, [MoveCommand("forward", 35.0)], "")
    assert res.valid and res.final_x > 70                 # through the field and out
    execute_movement(s, res, gs)
    assert "in_asteroid_field" in gs.get_ship_by_id("s").special_rules


def test_long_range_fire_blocked_close_fire_inside_at_half():
    gs = _game(_carrier())
    c = gs.get_ship_by_id("c")
    outside = make_ship(id="o", player=2, x=60.0, y=105.0, heading=180.0, weapons=[BATTERY])
    inside = make_ship(id="i", player=2, x=66.0, y=75.0, heading=180.0, weapons=[BATTERY])
    far_in = make_ship(id="f", player=2, x=53.0, y=72.0, heading=0.0, weapons=[BATTERY])
    phen = gs.get_phenomena()
    assert not check_los_clear(outside, c, phen)["clear"]
    los = check_los_clear(inside, c, phen)
    assert los["clear"] and los.get("in_asteroid_field")
    assert effective_battery_firepower(inside, BATTERY, c) == 3
    assert get_column_shifts(inside, c, [], phen, weapon=BATTERY) == 0   # no close range shift
    far_from = make_ship(id="c2", player=1, x=67.0, y=78.0, weapons=[BATTERY])
    assert far_from.distance_to(far_in) > 10                # both inside, too far apart
    assert "10cm" in check_los_clear(far_from, far_in, phen)["blocked_by"]
    inside.hits_remaining = 1                              # crippled: may not fire at all
    assert not check_los_clear(inside, c, phen)["clear"]


def test_bombers_leaving_the_field_roll_the_six():
    gs = _game(_carrier())
    m = make_marker(ordnance_type="bomber", x=60.0, y=95.0, heading=90.0, speed=20.0)
    assert check_ordnance_vs_phenomena(m, gs.get_phenomena(), DiceStub([])) == (False, "")
    dice = DiceStub([6])
    assert check_ordnance_vs_phenomena(m, gs.get_phenomena(), dice,
                                       start=(60.0, 75.0)) == (True, "asteroid_field")
    assert dice._idx == 1
