"""The owner's must-fix AI values (To do 33), re-added one at a time:
(a) boarding crits valued on the target's own table."""
from tests.conftest import make_gunship, make_ship, make_gs
from src.hit_and_run import boarding_crit_value, crit_type_value

BAT = {"name": "Port Battery", "weapon_type": "battery", "range_cm": 30, "strength": 8,
       "arcs": ["left", "front", "right"]}


def test_boarding_crit_on_the_targets_own_table():
    target = make_ship(id="t", player=2, x=0.0, y=0.0, speed=20, hits_max=8, shields_max=2,
                       points_value=200, weapons=[dict(BAT)])
    gun = make_gunship(player=1, x=25.0, y=0.0, heading=180.0, id="g")
    gs = make_gs([target, gun])
    plain = boarding_crit_value(target, gs, 1)
    assert plain > 0
    # the D6 on the raid table (at least 2), each result by its own value
    from src.hit_and_run import raid_crit_preview
    vals = [crit_type_value(raid_crit_preview(max(2, r), target), target, gs, 1)
            for r in range(1, 7)]
    assert abs(plain - sum(vals) / 6.0) < 1e-9
    # Haemonculi: a Fire
    assert abs(boarding_crit_value(target, gs, 1, ["dark_eldar", "haemonculi"])
               - crit_type_value("fire", target, gs, 1)) < 1e-9
    # Pain Frenzy (a Wych Cult counts every capital ship as crippled): a
    # re-roll of the weaker results is worth more
    assert boarding_crit_value(target, gs, 1, ["dark_eldar", "wych_cult"]) > plain
    # an escort takes 1 damage
    esc = make_ship(id="x", player=2, ship_type="escort", hits_max=1, points_value=40)
    gs3 = make_gs([esc, gun])
    from src.ai_hazards import escort_hits_vp
    assert boarding_crit_value(esc, gs3, 1) == escort_hits_vp(esc, gs3, 1)
