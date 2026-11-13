"""Siren's Summon (Pleasure Fleet of Slaanesh): enemy vessels within 15cm can't
take any Leadership test; a forced test fails (07_chaos.md)."""
from src.disengage import attempt_disengage, squadron_disengage_test
from src.terrain_effects import resolve_asteroid_navigation, resolve_warp_rift_navigation
from src.game_state import GameState
from src.models import Ship
from tests.conftest import DiceStub


def _ship(id, player, x, rules=(), ship_type="cruiser", sq=""):
    return Ship(id=id, name=id, ship_class="T", faction="chaos", player=player,
                ship_type=ship_type, base_size="small", x=x, y=60.0, heading=0.0, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=1,
                hits_max=8, leadership=8, weapons=[], special_rules=list(rules), upgrades=[],
                critical_damage=[], points_value=180, squadron_id=sq)


def _gs(*ships):
    gs = GameState()
    for s in ships:
        gs.add_ship(s)
    return gs


def test_disengage_blocked_within_15cm():
    gs = _gs(_ship("a", 1, 50.0), _ship("s", 2, 60.0, ["sirens_summon"]))
    dice = DiceStub([2])
    r = attempt_disengage(gs.get_ship_by_id("a"), dice, gs)
    assert r["success"] is False and r.get("blocked")
    assert dice._idx == 0
    a = gs.get_ship_by_id("a")
    assert not a.is_disengaged and not a.disengage_failed_this_turn


def test_disengage_beyond_15cm_rolls():
    gs = _gs(_ship("a", 1, 30.0), _ship("s", 2, 60.0, ["sirens_summon"]))
    dice = DiceStub([2])
    r = attempt_disengage(gs.get_ship_by_id("a"), dice, gs)
    assert r["success"] and dice._idx == 1


def test_squadron_tests_from_an_unaffected_member():
    near = _ship("e1", 1, 50.0, ship_type="escort", sq="q")
    far = _ship("e2", 1, 20.0, ship_type="escort", sq="q")
    gs = _gs(near, far, _ship("s", 2, 60.0, ["sirens_summon"]))
    dice = DiceStub([2])
    r = squadron_disengage_test([near, far], dice, gs)
    assert r["success"] and dice._idx == 1
    gs2 = _gs(_ship("e1", 1, 50.0, ship_type="escort", sq="q"),
              _ship("e2", 1, 52.0, ship_type="escort", sq="q"),
              _ship("s", 2, 60.0, ["sirens_summon"]))
    dice2 = DiceStub([2])
    r2 = squadron_disengage_test(gs2.get_ships()[:2], dice2, gs2)
    assert not r2["success"] and r2.get("blocked") and dice2._idx == 0


def test_forced_navigation_tests_fail():
    gs = _gs(_ship("a", 1, 50.0), _ship("s", 2, 60.0, ["sirens_summon"]))
    gs.brace_hook = None
    # asteroid: auto-fail, then D6 damage (one die, shields stop it)
    dice = DiceStub([1])
    r = resolve_asteroid_navigation(gs.get_ship_by_id("a"), dice, gs)
    assert r["passed"] is False
    gs3 = _gs(_ship("a", 1, 50.0), _ship("s", 2, 60.0, ["sirens_summon"]))
    r3 = resolve_warp_rift_navigation(gs3.get_ship_by_id("a"), DiceStub([1]), gs3)
    assert r3["passed"] is False
