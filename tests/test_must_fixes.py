"""The owner's must-fix AI values (To do 33), re-added one at a time:
(a) boarding crits valued on the target's own table; (b) raids on Dark Eldar ships; (c) a commander re-roll in
the pass chance."""
import json

from src.fleet_loader import fleet_to_ships
from src.game_state import GameState
from src.hit_and_run import raid_result_value, superstructure_value
from src.ai_rerolls import with_reroll, spend_bar
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


def _de_gs():
    import glob
    de = fleet_to_ships(json.load(open("data/fleets/owner_dark_eldar_tortures_1000.json")), 2)
    go = fleet_to_ships(json.load(open(sorted(glob.glob("data/fleets/owner_gothic*.json"))[0])), 1)
    gs = GameState()
    for i, s in enumerate(go):
        s.x, s.y, s.heading, s.leadership = 40 + 8 * i, 40, 0, 8
        gs.add_ship(s)
    for i, s in enumerate(de):
        s.x, s.y, s.heading, s.leadership = 40 + 8 * i, 75, 180, 8
        gs.add_ship(s)
    gs.turn_limit = 6
    return gs


def test_raids_on_a_dark_eldar_ship_are_worth_something():
    gs = _de_gs()
    torture = next(s for s in gs.get_ships() if s.player == 2 and "Torture" in s.name)
    # keel armament: its launch bays (they were valued at 0)
    assert crit_type_value("keel_armament", torture, gs, 1) > 1.0
    assert raid_result_value(3, torture, gs, 1) > 1.0
    for ct in ("graviton_harness", "bladevanes", "prow_armament"):
        assert crit_type_value(ct, torture, gs, 1) > 0
    # superstructure: the cheaper of turning and risking a hit, or not turning
    sv = superstructure_value(torture, "de_superstructure", gs, 1)
    assert 0 < sv <= crit_type_value("graviton_harness", torture, gs, 1) + 1e-9


def _flagship_gs(rerolls=1):
    flag = make_ship(id="f", player=1, x=0.0, y=0.0, heading=0.0, speed=20, hits_max=8,
                     points_value=1500, is_flagship=True, rerolls_remaining=rerolls,
                     weapons=[dict(BAT)])
    ship = make_ship(id="s", player=1, x=10.0, y=0.0, heading=0.0, speed=20, hits_max=8,
                     points_value=200, weapons=[dict(BAT)])
    foe = make_gunship(player=2, x=40.0, y=0.0, heading=180.0, id="e")
    return ship, make_gs([flag, ship, foe])


def test_a_reroll_lifts_an_order_worth_spending_one_on():
    ship, gs = _flagship_gs(rerolls=1)
    bar = spend_bar(ship, gs, 1)
    p = 0.58                                  # Ld 7 on 2D6
    big = 4 * bar
    # worth a re-roll: p g + (1 - p)(p g - the re-roll's worth)
    assert abs(with_reroll(ship, gs, p, big) - (p * big + (1 - p) * (p * big - bar))) < 1e-9
    # not worth spending one on: no lift
    assert with_reroll(ship, gs, p, 0.5 * bar) == p * 0.5 * bar
    # no re-rolls left: no lift
    ship0, gs0 = _flagship_gs(rerolls=0)
    assert with_reroll(ship0, gs0, p, big) == p * big
    # the later orders a failure would block count towards spending one
    assert with_reroll(ship, gs, p, 0.5 * bar, extra=2 * bar) > p * 0.5 * bar
