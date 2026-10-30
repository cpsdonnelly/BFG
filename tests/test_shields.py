"""Shields everywhere they are checked: the Shields Collapse crit, crippling
and blast markers must give the same answer in every rule that asks."""
from src.ai_player import ai_should_brace
from src.combat import apply_damage
from src.geometry import current_shields
from src.hit_and_run import check_teleport_eligibility
from src.models import BlastMarker
from src.terrain_effects import resolve_asteroid_navigation, resolve_gas_dust_contact
from tests.conftest import make_ship, make_gs, DiceStub

COLLAPSED = [{"crit_type": "shields_collapse", "description": "Shields Collapse",
              "repairable": False, "turn_inflicted": 1}]


def _markers_on(gs, ship, n):
    for i in range(n):
        gs.add_blast_marker(BlastMarker(id=f"bm{i}", x=ship.x, y=ship.y,
                                        heading=60.0 * i))


# ── current_shields ───────────────────────────────────────────────────────────

def test_current_shields_full():
    ship = make_ship(shields_max=3)
    assert current_shields(ship, []) == 3


def test_current_shields_crippled_halves_rounding_up():
    ship = make_ship(shields_max=3, hits_max=8, hits_remaining=4)
    assert current_shields(ship, []) == 2


def test_current_shields_collapse_crit_is_zero():
    ship = make_ship(shields_max=4, critical_damage=list(COLLAPSED))
    assert current_shields(ship, []) == 0


def test_current_shields_blast_markers_knock_down_never_below_zero():
    ship = make_ship(shields_max=2)
    gs = make_gs([ship])
    _markers_on(gs, ship, 1)
    assert current_shields(ship, gs.get_blast_markers()) == 1
    _markers_on(gs, ship, 3)
    assert current_shields(ship, gs.get_blast_markers()) == 0


# ── Every rule that checks shields respects the collapse crit ────────────────

def test_damage_skips_collapsed_shields():
    ship = make_ship(shields_max=2, hits_max=8, critical_damage=list(COLLAPSED))
    gs = make_gs([ship])
    r = apply_damage(ship, 2, DiceStub([1]), gs)
    assert r["shield_hits"] == 0
    assert r["hull_hits"] == 2


def test_teleport_allowed_against_collapsed_shields():
    attacker = make_ship(id="a", player=1, hits_max=8)
    target = make_ship(id="t", player=2, x=8.0, hits_max=6, shields_max=2,
                       critical_damage=list(COLLAPSED))
    assert check_teleport_eligibility(attacker, target, make_gs([attacker, target]))[0]


def test_teleport_allowed_when_blast_markers_knock_shields_down():
    attacker = make_ship(id="a", player=1, hits_max=8)
    target = make_ship(id="t", player=2, x=8.0, hits_max=6, shields_max=2)
    gs = make_gs([attacker, target])
    _markers_on(gs, target, 2)
    assert check_teleport_eligibility(attacker, target, gs) == (True, "")


def test_teleport_refused_while_a_shield_is_still_up():
    attacker = make_ship(id="a", player=1, hits_max=8)
    target = make_ship(id="t", player=2, x=8.0, hits_max=6, shields_max=2)
    gs = make_gs([attacker, target])
    _markers_on(gs, target, 1)
    ok, reason = check_teleport_eligibility(attacker, target, gs)
    assert not ok
    assert "1 shield" in reason


def test_ai_brace_sees_collapsed_shields():
    target = make_ship(id="t", player=2, shields_max=2, hits_max=8,
                       critical_damage=list(COLLAPSED))
    # 2 hits straight to hull >= 8/4 threshold -> brace
    assert ai_should_brace(make_gs([target]), target, incoming_hits=2) is True


def test_asteroid_damage_not_absorbed_by_knocked_down_shields():
    ship = make_ship(id="s", leadership=6, shields_max=2, hits_max=8)
    gs = make_gs([ship])
    _markers_on(gs, ship, 2)
    # 2D6 = 9 > Ld 6 -> fail; D6 = 3 damage, no shields left to absorb it
    resolve_asteroid_navigation(ship, DiceStub([4, 5, 3]), gs)
    assert ship.hits_remaining == 5


def test_asteroid_damage_collapsed_shields_absorb_nothing():
    ship = make_ship(id="s", leadership=6, shields_max=2, hits_max=8,
                     critical_damage=list(COLLAPSED))
    gs = make_gs([ship])
    resolve_asteroid_navigation(ship, DiceStub([4, 5, 3]), gs)
    assert ship.hits_remaining == 5


def test_gas_dust_damages_ship_with_collapsed_shields():
    ship = make_ship(id="s", shields_max=2, hits_max=8, critical_damage=list(COLLAPSED))
    gs = make_gs([ship])
    r = resolve_gas_dust_contact(ship, DiceStub([6]), gs)
    assert r["damage"] == 1
