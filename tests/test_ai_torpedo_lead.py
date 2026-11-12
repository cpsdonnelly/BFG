"""Owner: lead the target with straight-running torpedoes. The salvo moves now,
sits while the enemy moves (a ship moving into it is attacked, s.15) and moves
again in the enemy's ordnance phase; the target must move at least half speed,
straight for its turning distance before its one turn (s.10), unless it passes
Burn Retros (s.7). Hardest abeam, easiest closing."""
import math

from tests.conftest import make_ship, make_gs, DiceStub
from src.ai_player import AIPlayer
from src.turn_controller import TurnController
from src.ai_hazards import p_sum_at_most, DODGE_WEIGHT

TORP = {"name": "Prow Torpedoes", "weapon_type": "torpedo", "range_cm": 30, "strength": 6,
        "arcs": ["front"], "torpedo_type": "standard", "torpedo_speed": 30}


def _plan(tx, ty, theading, ld=8, speed=20):
    me = make_ship(id="me", player=1, x=0.0, y=0.0, heading=0.0, weapons=[dict(TORP)])
    tgt = make_ship(id="t", player=2, x=tx, y=ty, heading=theading, speed=speed,
                    leadership=ld, armor_prow="5+", armor_side="5+", points_value=150)
    gs = make_gs([me, tgt])
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._ord_committed = {}
    plan = ai._torp_lead_plan(gs.get_ship_by_id("me"), TORP, gs.get_ship_by_id("t"))
    assert dice._idx == 0
    return plan


def test_closing_target_easier_than_abeam():
    """Close in, a closing ship can't avoid the parked salvo without Burn Retros;
    further out its turn lets it sidestep about as well as an abeam ship's speed
    spread does (about level near 50cm); at 60cm closing is easier again.
    Receding targets are the hardest."""
    for x in (40.0, 60.0):
        closing, abeam = _plan(x, 0.0, 180.0), _plan(x, 0.0, 90.0)
        assert closing["p_hit"] > abeam["p_hit"] > 0
        assert closing["value"] > abeam["value"]
    assert _plan(45.0, 0.0, 0.0)["p_hit"] < _plan(45.0, 0.0, 90.0)["p_hit"]


def test_abeam_target_is_led():
    """Moving to +y, the best heading points ahead of it (positive bearing)."""
    plan = _plan(50.0, 0.0, 90.0)
    assert 2.0 < plan["heading"] < 45.0


def test_salvo_inside_the_minimum_move_only_burn_retros_escapes():
    """The salvo stops 10cm ahead of a speed-20 cruiser coming at us: it must
    move 10cm straight (half speed, and before turning), so only Burn Retros
    (a Leadership test) saves it, if it tries (DODGE_WEIGHT)."""
    for ld in (8, 10):
        plan = _plan(40.0 + 1.6 + 1.25 - 1.0, 0.0, 180.0, ld=ld)
        p_pass = p_sum_at_most(2, ld)
        expect = (1 - DODGE_WEIGHT) + DODGE_WEIGHT * (1 - p_pass)
        assert abs(plan["p_hit"] - expect) < 1e-9
    assert _plan(41.85, 0.0, 180.0, ld=8)["p_hit"] > _plan(41.85, 0.0, 180.0, ld=10)["p_hit"]


def test_beyond_two_moves_falls_back():
    """Out of reach this turn and the enemy's: the long-range intercept is used."""
    assert _plan(120.0, 0.0, 0.0) is None


def test_turning_salvo_steers_ahead_of_its_target():
    """A guided salvo out of reach steers for where the target will be."""
    from tests.conftest import make_marker
    me = make_ship(id="me", player=1, x=0.0, y=0.0)
    tgt = make_ship(id="t", player=2, x=60.0, y=0.0, heading=90.0, speed=20)
    gs = make_gs([me, tgt])
    gs.add_ordnance(make_marker(id="m", ordnance_type="torpedo_standard", owner_player=1,
                                x=0.0, y=0.0, heading=0.0, speed=20, can_turn=True,
                                turn_angle=45))
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    from src.models import OrdnanceMarker
    m = OrdnanceMarker.from_dict(gs.ordnance[0])
    ai._steer_guided_missile(m, gs.get_ship_by_id("t"))
    h = OrdnanceMarker.from_dict(gs.ordnance[0]).heading
    assert 5.0 < h < 45.0              # turned towards +y, ahead of the target


def _plan_base(tx, theading, base, ship_type="cruiser"):
    me = make_ship(id="me", player=1, x=0.0, y=0.0, heading=0.0, weapons=[dict(TORP)])
    tgt = make_ship(id="t", player=2, x=tx, y=0.0, heading=theading, speed=20, leadership=8,
                    armor_prow="5+", armor_side="5+", points_value=150, base_size=base,
                    ship_type=ship_type)
    gs = make_gs([me, tgt])
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai._ord_committed = {}
    return ai._torp_lead_plan(gs.get_ship_by_id("me"), TORP, gs.get_ship_by_id("t"))["p_hit"]


def test_large_bases_are_easier_to_hit():
    """Owner: large bases (60mm, s.4: battleships, 3+ shields or 10+ hits) are
    bigger torpedo targets; battleships also turn only after 15cm (s.10), so a
    closing one can't sidestep the lane."""
    for x, h in ((50.0, 90.0), (60.0, 90.0), (50.0, 180.0), (60.0, 180.0)):
        assert _plan_base(x, h, "large") > _plan_base(x, h, "small")
    assert _plan_base(60.0, 180.0, "large", "battleship") > _plan_base(60.0, 180.0, "large")
