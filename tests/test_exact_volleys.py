"""Exact hit distributions for the AI's re-roll and order values (owner: the
real Gunnery table, not 0.6 a battery point): ai_hazards.weapon_hit_pmf /
volley_hull_pmf / hits_vp and ai_rerolls.firepower_outcomes / importance."""
from tests.conftest import make_ship, make_gs
from src.ai_hazards import weapon_hit_pmf, volley_hull_pmf, battery_hits, hits_vp
from src.combat import lance_expected

BAT = {"name": "Prow Battery", "weapon_type": "battery", "range_cm": 30, "strength": 6,
       "arcs": ["front"]}
LANCE = {"name": "Prow Lance", "weapon_type": "lance", "range_cm": 30, "strength": 3,
         "arcs": ["front"]}


def _pair(**kw):
    a = make_ship(id="a", player=1, x=0.0, y=0.0, heading=0.0, weapons=[dict(BAT), dict(LANCE)])
    t = make_ship(id="t", player=2, x=25.0, y=0.0, heading=180.0, hits_max=8, points_value=180,
                  **kw)
    return a, t, make_gs([a, t])


def _mean(pmf):
    return sum((r + b) * q for (r, b), q in pmf.items())


def test_pmfs_match_the_expected_hits():
    a, t, _gs = _pair()
    assert abs(_mean(weapon_hit_pmf(a, BAT, t)) - battery_hits(a, BAT, t)) < 1e-9
    assert abs(_mean(weapon_hit_pmf(a, LANCE, t)) - lance_expected(a, LANCE, t, now=False)[0]) < 1e-9
    for flag in ("phantom", "de_phantom", "pulsar", "particle_whip"):
        w = dict(LANCE, **{flag: True})
        assert abs(_mean(weapon_hit_pmf(a, w, t)) - lance_expected(a, w, t, now=False)[0]) < 1e-9
    assert abs(sum(weapon_hit_pmf(a, BAT, t).values()) - 1.0) < 1e-9


def test_shields_take_the_first_stoppable_hits():
    a, t, _gs = _pair()
    pmf = volley_hull_pmf([(a, LANCE, 1.0, False)], t, 2)
    p = 0.5
    # 3 lance dice at 4+: only three hits get one past two shields
    assert abs(pmf[1] - p ** 3) < 1e-9 and abs(sum(pmf) - 1.0) < 1e-9


def test_halved_guns_lose_value_and_firepower_outcomes_use_the_table():
    from src.ai_rerolls import firepower_outcomes
    a, t, gs = _pair()
    full, outs = firepower_outcomes(gs.get_ship_by_id("a"), gs)
    half, _ = firepower_outcomes(gs.get_ship_by_id("a"), gs, halve=True)
    assert full > half > 0
    assert abs(sum(q for q, _v in outs) - 1.0) < 1e-6


def test_asteroid_reroll_worth_the_d6_damage_past_shields():
    from src.ai_rerolls import importance
    a, t, gs = _pair(shields_max=2)
    want = sum(hits_vp(t, gs, max(0, r - 2)) for r in range(1, 7)) / 6.0
    assert abs(importance(t, "asteroid navigation", gs) - want) < 1e-9


def test_mines_worth_what_they_can_reach():
    from src.ai_hazards import mine_value
    t = make_ship(id="t", player=2, x=25.0, y=0.0, heading=180.0, speed=20, hits_max=8,
                  points_value=180, turrets=0)
    gs = make_gs([t])
    near = mine_value(0.0, 0.0, gs, 1)
    assert near > 0
    # far beyond 4 ordnance phases of 10cm plus its moves: nothing
    assert mine_value(-200.0, 0.0, gs, 1) == 0.0
    # two mines: the second's hits come on top of the first's (they may
    # cross the cripple line, so it can be worth more than the first)
    assert mine_value(0.0, 0.0, gs, 1, n=2) > near
