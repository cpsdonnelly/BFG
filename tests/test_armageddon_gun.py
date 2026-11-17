"""The Planet Killer's Armageddon Gun (To do 5)."""
from tests.conftest import make_ship, make_gs, DiceStub, make_phenomenon
from src.combat import resolve_armageddon_gun, armageddon_ready
from src.ordnance import reload_ship_ordnance

GUN = {"name": "Armageddon Gun", "weapon_type": "armageddon_gun", "range_cm": 90,
       "strength": 0, "arcs": ["front"]}


def _scene():
    pk = make_ship(id="pk", player=1, x=0.0, y=0.0, heading=0.0, hits_max=14,
                   hits_remaining=14, weapons=[dict(GUN)])
    a = make_ship(id="a", player=2, x=40.0, y=0.0, shields_max=0, hits_max=8,
                  points_value=180)                                             # under the hole
    b = make_ship(id="b", player=2, x=60.0, y=3.5, shields_max=0, hits_max=8)   # template edge
    c = make_ship(id="c", player=2, x=60.0, y=20.0, shields_max=0, hits_max=8)  # missed
    return make_gs([pk, a, b, c])


def test_sweep_hits_along_the_track_then_needs_reloading():
    gs = _scene()
    dice = DiceStub([4] + [1] * 10)              # D6 hits on a; crit checks fail
    res = resolve_armageddon_gun(gs.get_ship_by_id("pk"), gs, dice)
    assert res["hits"] == {"a": 4, "b": 1}
    assert gs.get_ship_by_id("a").hits_remaining == 4
    pk = gs.get_ship_by_id("pk")
    assert armageddon_ready(pk) and "Reload" in armageddon_ready(pk)
    reload_ship_ordnance(pk)
    assert armageddon_ready(pk) is None


def test_blocked_by_an_asteroid_field():
    gs = _scene()
    gs.phenomena = [make_phenomenon("asteroid_field", x=25.0, y=0.0, width=6.0, height=6.0).to_dict()]
    res = resolve_armageddon_gun(gs.get_ship_by_id("pk"), gs, DiceStub([3]))
    assert res["blocked"] and not res["hits"] and len(gs.blast_markers) == 3


def test_ai_fires_only_when_worth_it():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    gs = _scene()
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    assert ai._armageddon_value(gs.get_ship_by_id("pk")) > 0
    gs2 = make_gs([make_ship(id="pk", player=1, x=0.0, y=0.0, weapons=[dict(GUN)]),
                   make_ship(id="f", player=1, x=40.0, y=0.0, points_value=200)])
    ai2 = AIPlayer(1, TurnController(gs2, DiceStub([])), gs2, DiceStub([]))
    assert ai2._armageddon_value(gs2.get_ship_by_id("pk")) <= 0
