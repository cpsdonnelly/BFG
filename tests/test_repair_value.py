"""Damage control repairs by expected VP (To do 11 e / 9)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.end_phase import resolve_damage_control

PORT = {"name": "Port Lances", "weapon_type": "lance", "range_cm": 30, "strength": 4,
        "arcs": ["left"]}


def _ship(**kw):
    crits = [{"crit_type": "fire", "description": "Fire!", "repairable": True},
             {"crit_type": "port_armament", "description": "Port Armament Damaged",
              "repairable": True}]
    return make_ship(id="s", player=1, x=0.0, y=0.0, heading=0.0, hits_max=8,
                     hits_remaining=1, points_value=120, weapons=[dict(PORT)],
                     critical_damage=crits, **kw)


def test_repairs_the_guns_that_threaten_a_valuable_enemy():
    foe = make_ship(id="e", player=2, x=0.0, y=20.0, points_value=400, hits_max=8)
    gs = make_gs([_ship(), foe])
    s = gs.get_ship_by_id("s")
    resolve_damage_control(s, DiceStub([6]), gs)
    left = [c["crit_type"] for c in gs.get_ship_by_id("s").critical_damage]
    assert left == ["fire"]


def test_puts_the_fire_out_when_the_guns_threaten_nothing():
    gs = make_gs([_ship(), make_ship(id="e", player=2, x=150.0, y=150.0, points_value=400)])
    s = gs.get_ship_by_id("s")
    resolve_damage_control(s, DiceStub([6]), gs)
    left = [c["crit_type"] for c in gs.get_ship_by_id("s").critical_damage]
    assert left == ["port_armament"]


def test_end_phase_removes_the_markers_in_our_way_first():
    from src.models import BlastMarker
    from src.end_phase import remove_blast_markers
    me = make_ship(id="m", player=1, x=0.0, y=0.0, speed=20)
    foe = make_ship(id="f", player=2, x=100.0, y=0.0, speed=20)
    gs = make_gs([me, foe])
    gs.active_player = 1
    gs.add_blast_marker(BlastMarker(id="near_foe", x=95.0, y=10.0))
    gs.add_blast_marker(BlastMarker(id="near_us", x=12.0, y=0.0))
    remove_blast_markers(gs, DiceStub([1]))
    assert [b["id"] for b in gs.blast_markers] == ["near_foe"]
