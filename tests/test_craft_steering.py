"""Attack craft turn freely and move in any direction up to their speed (s.18)."""
import pytest
from tests.conftest import make_ship, make_gs
from src.models import OrdnanceMarker, OrdnanceType as OT
from src.ordnance import (move_ordnance, move_craft_toward, ai_craft_target,
                          assign_ai_craft_targets)


def _craft(id="c", otype=OT.BOMBER.value, player=1, x=10.0, y=10.0, heading=0.0,
           speed=20.0, **kw):
    return OrdnanceMarker(id=id, ordnance_type=otype, owner_player=player,
                          launched_by="s", x=x, y=y, heading=heading, speed=speed, **kw)


def test_move_toward_turns_and_moves_up_to_speed():
    m = _craft(heading=0.0)
    assert move_craft_toward(m, 10.0, 60.0) == 20.0
    assert (m.x, m.y) == pytest.approx((10.0, 30.0)) and m.heading == pytest.approx(90.0)


def test_move_toward_stops_at_a_close_target():
    m = _craft()
    assert move_craft_toward(m, 13.0, 14.0) == pytest.approx(5.0)
    assert (m.x, m.y) == pytest.approx((13.0, 14.0))


def test_craft_home_on_their_target_ship():
    target = make_ship(id="e", player=2, x=10.0, y=25.0)
    gs = make_gs([target])
    m = _craft(heading=0.0, craft_target_id="e")
    move_ordnance(m, gs)
    assert (m.x, m.y) == pytest.approx((10.0, 25.0))     # 15cm away: reaches it


def test_craft_home_on_an_ordnance_marker():
    gs = make_gs([])
    gs.add_ordnance(_craft(id="t", otype=OT.TORPEDO_STANDARD.value, player=2, x=40.0, y=10.0))
    m = _craft(otype=OT.FIGHTER.value, craft_target_id="t", speed=30.0)
    move_ordnance(m, gs)
    assert (m.x, m.y) == pytest.approx((40.0, 10.0))


def test_target_gone_carries_straight_on():
    gone = make_ship(id="e", player=2, x=10.0, y=25.0)
    gone.status = "destroyed"
    gs = make_gs([gone])
    m = _craft(heading=0.0, craft_target_id="e")
    move_ordnance(m, gs)
    assert (m.x, m.y) == pytest.approx((30.0, 10.0)) and m.craft_target_id == ""


def test_craft_without_orders_fly_straight():
    gs = make_gs([])
    m = _craft(heading=90.0)
    move_ordnance(m, gs)
    assert (m.x, m.y) == pytest.approx((10.0, 30.0))


def test_torpedoes_ignore_craft_orders():
    gs = make_gs([make_ship(id="e", player=2, x=10.0, y=25.0)])
    t = _craft(otype=OT.TORPEDO_STANDARD.value, heading=0.0, craft_target_id="e")
    move_ordnance(t, gs)
    assert (t.x, t.y) == pytest.approx((30.0, 10.0))


def test_ai_targets():
    near = make_ship(id="near", player=2, x=20.0, y=10.0)
    far = make_ship(id="far", player=2, x=90.0, y=90.0)
    hulk = make_ship(id="hulk", player=2, x=12.0, y=10.0)
    hulk.status = "drifting_hulk"
    gs = make_gs([near, far, hulk])
    assert ai_craft_target(_craft(), gs) == "near"                 # bombers: nearest ship
    gs.add_ordnance(_craft(id="torp", otype=OT.TORPEDO_STANDARD.value, player=2,
                           x=30.0, y=30.0))
    fighter = _craft(otype=OT.FIGHTER.value, speed=30.0)
    assert ai_craft_target(fighter, gs) == "torp"                  # intercept within 2 moves
    assert ai_craft_target(_craft(otype=OT.THUNDERHAWK.value, speed=20.0), gs) == "torp"
    assert ai_craft_target(_craft(), gs) == "near"                 # bombers still go for ships


def test_assign_skips_cap_and_other_players():
    gs = make_gs([make_ship(id="e", player=2, x=20.0, y=10.0)])
    gs.add_ordnance(_craft(id="a"))
    gs.add_ordnance(_craft(id="cap", otype=OT.FIGHTER.value, cap_ship_id="x"))
    gs.add_ordnance(_craft(id="theirs", player=2))
    assert assign_ai_craft_targets(gs, 1) == 1
    by_id = {o["id"]: o for o in gs.ordnance}
    assert by_id["a"]["craft_target_id"] == "e"
    assert by_id["cap"]["craft_target_id"] == "" and by_id["theirs"]["craft_target_id"] == ""
