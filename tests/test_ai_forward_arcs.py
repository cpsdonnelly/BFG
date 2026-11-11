"""Tau-style (L/F), (R/F) mounts: both sides' weapons bear on a target ahead
(owner: some factions fire all weapons forward). Checked in the AI's planners."""
from tests.conftest import make_ship, make_gs
from src.ship_catalog import find_ship_class
from src.models import Ship


def _tau(x=0.0, y=0.0, heading=0.0, player=2):
    d = find_ship_class("Protector Class Cruiser").to_ship_dict("Tau", player, ship_id="tau")
    d.update(x=x, y=y, heading=heading, leadership=8)
    return Ship.from_dict(d)


def test_tau_forward_mounts_all_bear_ahead():
    from src.ai_hazards import _mount_bears
    from src.combat import check_weapon_in_arc
    tau = _tau()
    ahead = make_ship(id="t", player=1, x=25.0, y=0.0)
    guns = [w for w in tau.weapons if w["weapon_type"] in ("battery", "lance")]
    assert len(guns) == 5
    assert all(check_weapon_in_arc(tau, w, ahead.x, ahead.y) for w in guns)
    assert all(_mount_bears(tau, w, ahead) for w in guns)
    # Abeam to port: only the port (L/F) mounts bear as it lies...
    port = make_ship(id="p", player=1, x=0.0, y=25.0)
    now = {w["name"] for w in guns if check_weapon_in_arc(tau, w, port.x, port.y)}
    assert now == {"Port Railguns", "Port Ion Cannons"}
    # ...but the threat model allows its next move's 45-degree turn, which brings
    # the target onto the front arc's edge for the R/F and prow mounts too
    assert all(_mount_bears(tau, w, port) for w in guns)
    # (A 45-degree turn can also swing a broadside onto a ship astern; out of
    # range + its move nothing bears)
    behind = make_ship(id="b", player=1, x=-80.0, y=0.0)
    assert not any(_mount_bears(tau, w, behind) for w in guns)


def test_enemy_fire_plan_puts_both_sides_on_a_target_ahead():
    from src.ai_hazards import enemy_fire_plan
    ahead = make_ship(id="t", player=1, x=25.0, y=0.0, shields_max=0, points_value=150)
    plan = enemy_fire_plan(make_gs([_tau(), ahead]), 1)
    tau = _tau()
    full = sum((w["strength"] or 0) * (0.5 if w["weapon_type"] == "lance" else 0.35)
               for w in tau.weapons if w["weapon_type"] in ("battery", "lance"))
    assert abs(plan["t"] - full) < 1e-9


def test_ai_tau_move_score_counts_every_forward_mount():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    from tests.conftest import DiceStub
    tau = _tau(player=1)
    t = make_ship(id="t", player=2, x=25.0, y=0.0)
    gs = make_gs([tau, t])
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    total = sum(w["strength"] for w in tau.weapons if w["weapon_type"] in ("battery", "lance"))
    assert ai._arc_score(tau, 0.0, 0.0, 0.0, t) == total


def test_turn_allowance_uses_each_ships_turn_angle():
    """Owner: the Protector turns 90 degrees, the Hero 45. A target 120 degrees
    off the bow (port quarter) is only reachable for the prow railguns by a ship
    that can turn 90."""
    import math
    from src.ai_hazards import _mount_bears
    protector = _tau()
    assert protector.turn_angle == 90
    hero_like = Ship.from_dict({**protector.to_dict(), "turn_angle": 45})
    a = math.radians(120)
    t = make_ship(id="q", player=1, x=30 * math.cos(a), y=30 * math.sin(a))
    prow = next(w for w in protector.weapons if w["name"] == "Prow Railguns")
    assert _mount_bears(protector, prow, t)
    assert not _mount_bears(hero_like, prow, t)
    hero = find_ship_class("Hero Class Cruiser").to_ship_dict("Hero", 2)
    assert hero["turn_angle"] == 45
