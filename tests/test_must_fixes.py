"""The owner's must-fix AI values (To do 33), re-added one at a time:
(a) boarding crits valued on the target's own table; (b) raids on Dark Eldar ships; (c) a commander re-roll in
the pass chance; (d) Brace and Leadership crits cost the order the AI last planned."""
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


def test_brace_counts_the_order_it_forbids():
    """(d): Brace gives up the order the ship's own AI last planned (stored on
    the game state, carried over), at its pass chance from its Ld now."""
    from src import ai_player
    target = make_ship(id="t", player=1, x=0.0, y=0.0, heading=0.0, speed=20, hits_max=4,
                       shields_max=1, points_value=200, weapons=[dict(BAT)], leadership=6)
    foe = make_gunship(player=2, x=20.0, y=0.0, heading=180.0, id="e")
    gs = make_gs([target, foe])
    gs.planned_orders = {"t": [None, 0.0]}               # planned: no order
    base = ai_player.brace_value(gs, target, 8)
    gs.planned_orders = {"t": ["reload_ordnance", 40.0]}
    p = ai_player.order_reader(gs, 1)._pass_chance(target, "reload_ordnance")
    assert abs(ai_player.next_order_vp(gs, target) - p * 40.0) < 1e-9
    # lost only if the brace passes (also Ld 6 here: the same chance p)
    assert ai_player.brace_value(gs, target, 8) < base - 0.9 * p * p * 40.0
    # the game's last turn: nothing to give up
    gs.turn_limit = gs.turn_number
    assert ai_player.next_order_vp(gs, target) == 0.0
    gs.turn_limit = None
    # a lower Ld (a Leadership crit) costs the order its pass chance
    import copy
    low = copy.copy(target)
    low.leadership = 4
    assert ai_player.next_order_vp(gs, target, ld_ship=low) < p * 40.0
    # no plan yet: Lock On's re-roll gain on the guns that bear now
    gs.planned_orders = {}
    assert ai_player.next_order(gs, target)[0] == "lock_on"
    assert ai_player.next_order(gs, target)[1] == ai_player.lock_on_estimate(gs, target) > 0


def test_the_ai_order_plan_is_stored():
    ship, gs = _flagship_gs()
    from src.ai_player import AIPlayer
    ai = AIPlayer(1, ai_player_reader(gs), gs, None)
    ai._plan_orders([ship])
    assert "s" in gs.planned_orders
    assert "planned_orders" in gs.to_snapshot()


def ai_player_reader(gs):
    from src.ai_player import order_reader
    return order_reader(gs, 1).tc


def test_the_master_ai_values_the_order_afresh():
    """Owner: the master AI uses the slower, more accurate value: a fresh
    order plan from where the ship stands, not the stored one."""
    from src import ai_player
    ship = make_ship(id="m", player=2, x=0.0, y=0.0, heading=0.0, speed=20, hits_max=8,
                     points_value=200, weapons=[dict(BAT)], leadership=8)
    foe = make_gunship(player=1, x=25.0, y=0.0, heading=180.0, id="e")
    gs = make_gs([ship, foe])
    gs.planned_orders = {"m": ["reload_ordnance", 999.0]}
    gs.ai_difficulty = "normal"
    assert not ai_player.master_ai(gs, 2)
    assert ai_player.next_order(gs, ship) == ("reload_ordnance", 999.0)
    gs.ai_difficulty = "master"
    assert ai_player.master_ai(gs, 2) and not ai_player.master_ai(gs, 1)
    assert ai_player.next_order(gs, ship, full=True)[1] != 999.0


def test_no_plan_a_spent_torpedo_ship_counts_reload():
    """No stored plan: a ship whose ordnance is spent counts Reload Ordnance
    when it is worth more than Lock On (torpedo boats, carriers)."""
    from src import ai_player
    torp = {"name": "Prow Torpedoes", "weapon_type": "torpedo", "range_cm": 30,
            "strength": 6, "arcs": ["front"]}
    ship = make_ship(id="t", player=1, x=0.0, y=0.0, heading=0.0, speed=20, hits_max=6,
                     points_value=150, weapons=[torp], leadership=8)
    ship.ordnance_loaded_torps = False
    foe = make_ship(id="e", player=2, x=40.0, y=0.0, heading=180.0, hits_max=8,
                    points_value=200, weapons=[dict(BAT)])
    gs = make_gs([ship, foe])
    order, g = ai_player.next_order(gs, gs.get_ship_by_id("t"))
    assert order == "reload_ordnance" and g > 0


def test_a_squadron_bracing_gives_up_its_one_order_and_every_members_fire():
    """s.8: a squadron tests once and braces together, so the brace costs every
    member's halved fire and the squadron's one order (the order its members
    planned worth most in total, at the best Leadership's pass chance)."""
    from src import ai_player
    a = make_ship(id="a", player=1, x=0.0, y=0.0, heading=0.0, hits_max=4, shields_max=1,
                  points_value=200, weapons=[dict(BAT)], leadership=7, squadron_id="sq")
    b = make_ship(id="b", player=1, x=6.0, y=0.0, heading=0.0, hits_max=4, shields_max=1,
                  points_value=200, weapons=[dict(BAT)], leadership=8, squadron_id="sq")
    foe = make_gunship(player=2, x=20.0, y=0.0, heading=180.0, id="e")
    gs = make_gs([a, b, foe])
    gs.planned_orders = {"a": ["lock_on", 10.0], "b": ["lock_on", 10.0]}
    ta, tb = gs.get_ship_by_id("a"), gs.get_ship_by_id("b")
    p_b = ai_player.order_reader(gs, 1)._pass_chance(tb, "lock_on")
    assert abs(ai_player.squadron_order_vp(gs, [ta, tb]) - 20.0 * p_b) < 1e-9
    lone = ai_player.brace_value(gs, ta, 8)
    sq = ai_player.brace_value(gs, ta, 8, group=[ta, tb])
    assert sq < lone
