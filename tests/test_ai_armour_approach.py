"""Owner: salvos that can turn and roll against Armour (Tau missiles,
Leadership-guided and boarding torpedoes) may fire off to the side or take a
detour to come in on a weaker facing (torpedoes use the facing they hit, s.15;
they turn up to 45 degrees at the start of each later move, s.16)."""
from tests.conftest import make_ship, make_gs, make_marker, DiceStub
from src.ai_hazards import approach_plan, salvo_approach


def _ork_like(x=45.0, y=0.0, heading=90.0):
    # front / abeam / rear 6+ / 5+ / 4+ (Ork cruisers, Ship.armor_vs)
    return make_ship(id="t", player=2, x=x, y=y, heading=heading, speed=20, turrets=2,
                     armor_prow="6+", armor_side="5+", armor_rear="4+", points_value=150)


def test_detour_onto_the_rear_beats_the_straight_shot():
    t = _ork_like()
    gs = make_gs([t])
    best = approach_plan(0.0, 0.0, 0.0, 30.0, t, gs, 1, 6)
    # the best salvo that never turns (it may still be aimed off to the side)
    straight = approach_plan(0.0, 0.0, 0.0, 30.0, t, gs, 1, 6, max_turn=0.0)
    assert best["armour"] == 4 and straight["armour"] == 5
    assert best["value"] > straight["value"] > 0
    # Tau missiles (20-40cm a move, strength lost on 1s) find the rear too
    tau = approach_plan(0.0, 0.0, 0.0, 30.0, t, gs, 1, 6, tau=True, lengths=(20.0, 30.0, 40.0))
    assert tau["armour"] == 4


def test_closing_ship_meets_the_salvo_with_its_prow():
    """A ship that moves onto a waiting salvo takes it on the side it leads with."""
    t = _ork_like(heading=180.0)
    gs = make_gs([t])
    assert approach_plan(0.0, 0.0, 0.0, 30.0, t, gs, 1, 6)["armour"] == 6


def test_leadership_odds_discount_guided_turns():
    t = _ork_like()
    gs = make_gs([t])
    free = approach_plan(0.0, 0.0, 0.0, 30.0, t, gs, 1, 6)
    ld = approach_plan(0.0, 0.0, 0.0, 30.0, t, gs, 1, 6, p_turn=26 / 36)
    assert ld["value"] < free["value"]


def test_ai_tau_launch_follows_the_approach_and_records_its_target():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    tau_w = {"name": "Gravitic Launcher", "weapon_type": "torpedo", "range_cm": 30,
             "strength": 6, "arcs": ["front"], "torpedo_type": "guided", "torpedo_speed": 30}
    me = make_ship(id="me", player=1, x=0.0, y=0.0, heading=0.0, weapons=[dict(tau_w)])
    me.ordnance_loaded_torps = True
    t = _ork_like()
    gs = make_gs([me, t])
    gs.current_phase = "ordnance"
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._ord_committed = {}
    plan = ai._approach_for_launch(gs.get_ship_by_id("me"), tau_w, gs.get_ship_by_id("t"))
    assert plan["armour"] == 4
    ai._launch_ship_ordnance(gs.get_ship_by_id("me"))
    assert dice._idx == 0
    torps = [o for o in gs.ordnance if o["owner_player"] == 1]
    assert len(torps) == 1 and torps[0]["torp_target_id"] == "t"
    assert abs(((torps[0]["heading"] - plan["heading"]) + 180) % 360 - 180) < 1e-6


def test_salvo_in_flight_turns_for_the_weak_facing():
    t = _ork_like()
    gs = make_gs([t])
    gs.active_player = 1
    m = make_marker(id="b", ordnance_type="torpedo_boarding", owner_player=1, x=0.0, y=0.0,
                    heading=0.0, speed=30, strength=6)
    m.torp_target_id = "t"
    gs.add_ordnance(m)
    plan = salvo_approach(m, gs)
    assert plan is not None and plan["armour"] == 4
