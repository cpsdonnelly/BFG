"""Critical hits valued by their effect on the ship, measured, not a share of
its value (owner: "bad and lazy" judgement calls): hit_and_run.crit_effect_value."""
from tests.conftest import make_gunship, make_ship, make_gs
from src.hit_and_run import crit_effect_value, crit_type_value

BAT = {"name": "Port Battery", "weapon_type": "battery", "range_cm": 30, "strength": 8,
       "arcs": ["left", "front", "right"]}


def _gs(dist=45.0, our_guns=True):
    target = make_ship(id="t", player=2, x=0.0, y=0.0, heading=0.0, speed=20, hits_max=8,
                       shields_max=2, points_value=200, weapons=[dict(BAT)])
    ours = make_ship(id="o", player=1, x=dist, y=0.0, heading=180.0, speed=20, hits_max=8,
                     points_value=200, weapons=[dict(BAT)] if our_guns else [])
    # more of our guns within reach: the target's damage short of a kill is
    # worth the chance it is finished (ai_hazards.hits_vp)
    return target, make_gs([target, ours] + ([make_gunship(player=1, x=dist, y=12.0, heading=180.0,
                                                           id="g1")] if our_guns else []))


def test_effects_worth_nothing_with_no_enemy_on_the_table():
    target = make_ship(id="t", player=2, points_value=200, weapons=[dict(BAT)])
    gs = make_gs([target])
    for ct in ("thrusters_damaged", "engine_room", "shields_collapse"):
        assert crit_effect_value(target, ct, gs, 1) == 0.0


def test_thrusters_cost_the_reach_it_needed():
    # 45cm: its 30cm guns need its move to bear; slowed by 10cm they don't
    target, gs = _gs(45.0)
    assert crit_effect_value(target, "thrusters_damaged", gs, 1) > 0
    # already within range of each other: the speed changes nothing it needs
    target, gs = _gs(10.0)
    near = crit_effect_value(target, "thrusters_damaged", gs, 1)
    target, gs = _gs(45.0)
    assert near < crit_effect_value(target, "thrusters_damaged", gs, 1)


def test_several_thruster_hits_keep_the_system_down_until_all_are_repaired():
    # "not cumulative; all thruster hits must be repaired": a second hit adds
    # what it adds to the chance the system is still down, exactly
    # (p_system_down: 8 dice, one 6 fixes one crit, so a lone crit is usually
    # repaired but two need two sixes)
    from src.hit_and_run import p_system_down
    target, gs = _gs(45.0)
    assert abs(p_system_down(target, gs, 1, 1, 0) - (5 / 6) ** 8) < 1e-9
    assert p_system_down(target, gs, 1, 2, 0) > 2 * p_system_down(target, gs, 1, 1, 0)
    first = crit_effect_value(target, "thrusters_damaged", gs, 1)
    two = crit_effect_value(target, "thrusters_damaged", gs, 1, count=2)
    hurt = make_ship(id="t", player=2, x=0.0, y=0.0, heading=0.0, speed=20, hits_max=8,
                     shields_max=2, points_value=200, weapons=[dict(BAT)],
                     critical_damage=[{"crit_type": "thrusters_damaged", "repairable": True}])
    gs2 = make_gs([hurt, gs.get_ship_by_id("o"), gs.get_ship_by_id("g1")])
    second = crit_effect_value(hurt, "thrusters_damaged", gs2, 1)
    assert 0 < first < two
    assert abs(second - (two - first)) < 0.01      # (phases under 0.5% are skipped)


def test_shields_collapse_worth_our_fire_past_the_shields():
    target, gs = _gs(25.0)
    with_guns = crit_effect_value(target, "shields_collapse", gs, 1)
    target, gs = _gs(25.0, our_guns=False)
    assert with_guns > 0 and crit_effect_value(target, "shields_collapse", gs, 1) == 0.0


def test_extra_damage_on_the_hull_hit_scale_and_effect_added():
    from src.ai_hazards import hits_vp
    target, gs = _gs(45.0)
    v = crit_type_value("thrusters_damaged", target, gs, 1)
    eff = crit_effect_value(target, "thrusters_damaged", gs, 1)
    assert abs(v - (hits_vp(target, gs, 1) + eff)) < 1e-9      # exactly one extra hit
