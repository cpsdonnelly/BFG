"""Prevented damage and catastrophic explosions in the AI's values (owner):
killing / crippling removes / halves a ship's threat; a destroyed ship may
blow up among nearby ships; positioning avoids being caught, and a dying ship
gains by hugging enemies."""
from tests.conftest import make_ship, make_gs
from src.ai_hazards import (damage_vp, ship_threat_vp, death_explosion_vp, explosion_odds,
                            explosion_position_vp)

GUNS = [{"name": "Prow Lances", "weapon_type": "lance", "range_cm": 30, "strength": 4,
         "arcs": ["front", "left", "right"]}]


def test_killing_an_armed_ship_is_worth_more():
    ours = make_ship(id="o", player=1, x=0.0, y=0.0, points_value=200)
    armed = make_ship(id="a", player=2, x=20.0, y=0.0, heading=180.0, points_value=150,
                      hits_remaining=2, weapons=[dict(w) for w in GUNS])
    unarmed = make_ship(id="u", player=2, x=20.0, y=40.0, heading=180.0, points_value=150,
                        hits_remaining=2)
    gs = make_gs([ours, armed, unarmed])
    assert ship_threat_vp(armed, gs) > 0 and ship_threat_vp(unarmed, gs) == 0
    assert damage_vp(armed, gs, 2.0) > damage_vp(unarmed, gs, 2.0)


def test_kill_explosion_near_our_ship_counts_against_us():
    near_us = make_ship(id="o", player=1, x=0.0, y=0.0, points_value=200, shields_max=0)
    target = make_ship(id="t", player=2, x=6.0, y=0.0, points_value=150, hits_max=12,
                       hits_remaining=1)
    gs = make_gs([near_us, target])
    assert death_explosion_vp(target, gs, 1) < 0
    other_enemy = make_ship(id="e", player=2, x=6.0, y=6.0, points_value=150, shields_max=0)
    gs2 = make_gs([make_ship(id="o", player=1, x=-60.0, y=0.0), target, other_enemy])
    assert death_explosion_vp(target, gs2, 1) > 0
    esc = make_ship(id="x", player=2, ship_type="escort", hits_max=1)
    assert explosion_odds(esc) == (0.0, 0.0)


def test_positioning_away_from_a_dying_ship_and_hugging_when_dying():
    me = make_ship(id="me", player=1, x=0.0, y=0.0, points_value=200, shields_max=1,
                   hits_max=8, hits_remaining=8)
    dying_enemy = make_ship(id="d", player=2, x=40.0, y=0.0, points_value=200, hits_max=12,
                            hits_remaining=1)
    gs = make_gs([me, dying_enemy])
    our_hits = {"d": 6.0}
    near = explosion_position_vp(me, 36.0, 0.0, gs, {}, our_hits)
    far = explosion_position_vp(me, 0.0, 0.0, gs, {}, our_hits)
    assert near < far <= 0.0
    # Our badly hurt ship, likely to die: next to enemies is worth more than next to friends
    wounded = make_ship(id="w", player=1, x=0.0, y=0.0, points_value=200, hits_max=12,
                        hits_remaining=1)
    foe = make_ship(id="f", player=2, x=50.0, y=0.0, points_value=200, shields_max=0)
    friend = make_ship(id="g", player=1, x=-50.0, y=0.0, points_value=200, shields_max=0)
    gs2 = make_gs([wounded, foe, friend])
    plan = {"w": 4.0}
    assert (explosion_position_vp(wounded, 45.0, 0.0, gs2, plan, {})
            > explosion_position_vp(wounded, -45.0, 0.0, gs2, plan, {}))
