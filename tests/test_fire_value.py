"""A Fire's value (owner question): its exact burn over the end phases left
(ai_hazards.fire_burn_dist / fire_value): damage control's D6 per remaining
hit puts fires out on 6s, each fire left burns a hit, which costs a die."""
import random

from tests.conftest import make_gs, make_ship
from src.ai_hazards import fire_burn_dist, fire_value, FIRE_HORIZON


def _ship(hits, fires=0, **kw):
    s = make_ship(id="t", player=1, ship_type="cruiser", hits_max=8, **kw)
    s.hits_remaining = hits
    s.critical_damage = [{"crit_type": "fire", "repairable": True}] * fires
    return s


def _mc(hits, fires, phases, n=40000, seed=1):
    rng, total = random.Random(seed), 0.0
    for _ in range(n):
        h, f = hits, fires
        for _p in range(phases):
            if f == 0 or h <= 0:
                break
            sixes = sum(rng.randint(1, 6) == 6 for _ in range(h))
            f = max(0, f - sixes)
            h = max(0, h - f)
        total += hits - h
    return total / n


def test_burn_matches_simulation():
    gs = make_gs([_ship(4)])
    for hits, fires in ((8, 1), (4, 1), (4, 2)):
        d = fire_burn_dist(_ship(hits), gs, fires)
        exact = sum(k * p for k, p in d.items())
        assert abs(sum(d.values()) - 1) < 1e-9
        assert abs(exact - _mc(hits, fires, FIRE_HORIZON)) < 0.03


def test_fire_worth_more_on_damaged_and_burning_ships():
    gs = make_gs([_ship(8)])
    fresh = fire_value(_ship(8), gs)
    hurt = fire_value(_ship(4), gs)
    burning = fire_value(_ship(4, fires=1), gs)
    assert 0 < fresh < hurt < burning


def test_repairing_a_fire_valued_by_its_burn():
    from src.ai_hazards import repair_value
    s = _ship(4, fires=2)
    gs = make_gs([s])
    assert repair_value(s, s.critical_damage[0], gs) > repair_value(_ship(8, fires=1),
                                                                    {"crit_type": "fire"}, gs)
