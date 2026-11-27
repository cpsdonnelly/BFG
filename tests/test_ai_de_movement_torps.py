"""The AI and Dark Eldar (owner questions): its move planner turns them with
no turning distance and no minimum move, Come to New Heading passes
automatically and halves only batteries and lances, and torpedo loads
(plasma / standard, boarding, leech) are chosen by expected VP."""
import copy

from tests.conftest import make_gs_raids, DiceStub
from src.fleet_loader import load_fleet_file, fleet_to_ships
from src.ai_player import AIPlayer, auto_pass
from src.turn_controller import TurnController
from src.movement import turn_distance


def _fleets():
    g = fleet_to_ships(load_fleet_file("data/fleets/owner_gothic_1000.json"), 1)
    d = fleet_to_ships(load_fleet_file("data/fleets/owner_dark_eldar_succubi_990.json"), 2)
    return g, d


def _ai(ships):
    gs = make_gs_raids(ships)
    dice = DiceStub([])
    return gs, AIPlayer(2, TurnController(gs, dice), gs, dice)


def test_turning_distance_rule_is_shared():
    g, d = _fleets()
    lunar = next(s for s in g if "Lunar" in s.ship_class)
    tort = next(s for s in d if "Torture" in s.ship_class)
    assert turn_distance(lunar) == 10 and turn_distance(lunar, "burn_retros") == 0
    assert turn_distance(tort) == 0


def test_dark_eldar_cruiser_candidates_turn_at_once_and_move_short():
    g, d = _fleets()
    tort = copy.deepcopy(next(s for s in d if "Torture" in s.ship_class))
    tort.x, tort.y, tort.heading, tort.leadership = 60.0, 30.0, 90.0, 8
    lunar = copy.deepcopy(next(s for s in g if "Lunar" in s.ship_class))
    lunar.x, lunar.y, lunar.heading, lunar.leadership = 60.0, 90.0, 270.0, 8
    gs, ai = _ai([lunar, tort])
    t = gs.get_ship_by_id(tort.id)
    cands = ai._move_candidates(t, gs.get_ship_by_id(lunar.id), "", 0)
    assert any(c[2] == 0 and abs(c[0]) > 0.5 for c in cands)      # a turn at the start
    assert min(c[1] for c in cands) < t.speed * 0.5                # shorter than half speed


def test_come_to_new_heading_passes_for_dark_eldar():
    g, d = _fleets()
    tort = next(s for s in d if "Torture" in s.ship_class)
    lunar = next(s for s in g if "Lunar" in s.ship_class)
    assert auto_pass(tort, "come_to_new_heading") and not auto_pass(lunar, "come_to_new_heading")
    assert not auto_pass(tort, "lock_on")


def test_torpedo_load_by_value():
    g, d = _fleets()
    raider = copy.deepcopy(next(s for s in d if "Subjugation" in s.ship_class
                                and any(w.get("weapon_type") == "torpedo" for w in s.weapons)))
    raider.x, raider.y, raider.heading, raider.leadership = 50.0, 75.0, 90.0, 8
    lunar = copy.deepcopy(next(s for s in g if "Lunar" in s.ship_class))
    lunar.x, lunar.y, lunar.heading, lunar.leadership = 50.0, 50.0, 270.0, 8
    gs, ai = _ai([lunar, raider])
    w = next(w for w in raider.weapons if w.get("weapon_type") == "torpedo")
    a, t = gs.get_ship_by_id(raider.id), gs.get_ship_by_id(lunar.id)
    # plasma's re-roll and a hull hit beat a raid or a leech crit here
    assert ai._torpedo_kind_by_value(a, w, t) == ""
    # where raids are worth more than hull hits, boarding torpedoes; where
    # neither is worth anything, leech
    import src.ai_hazards as ah
    import src.waves as wv
    orig_h, orig_r = ah.hull_hits_vp, wv.raid_squadron_value
    try:
        ah.hull_hits_vp = lambda *a_, **k: 0.0
        wv.raid_squadron_value = lambda *a_, **k: 100.0
        assert ai._torpedo_kind_by_value(a, w, t) == "boarding"
        wv.raid_squadron_value = lambda *a_, **k: 0.0
        assert ai._torpedo_kind_by_value(a, w, t) == "leech"
        gs.rule_hit_and_run = False             # boarding torpedoes off with raids
        wv.raid_squadron_value = lambda *a_, **k: 100.0
        assert ai._torpedo_kind_by_value(a, w, t) != "boarding"
    finally:
        ah.hull_hits_vp, wv.raid_squadron_value = orig_h, orig_r


def test_pass_chance_follows_the_engine_rule():
    """One pass chance from movement.command_check_ld: Under Fire -1 (not for
    Necrons), automatic passes, 0 once a check has failed this turn (s.2)."""
    from tests.conftest import make_ship
    from src.models import BlastMarker
    from src.ai_hazards import p_sum_at_most
    me = make_ship(id="m", player=2, x=50.0, y=50.0, leadership=8)
    nec = make_ship(id="n", player=2, x=80.0, y=50.0, leadership=8, special_rules=["necron"])
    gs, ai = _ai([me, nec, make_ship(id="e", player=1, x=150.0, y=50.0)])
    assert abs(ai._pass_chance(gs.get_ship_by_id("m"), "lock_on") - p_sum_at_most(2, 8)) < 1e-9
    gs.add_blast_marker(BlastMarker(id="b1", x=50.0, y=52.0))
    gs.add_blast_marker(BlastMarker(id="b2", x=80.0, y=52.0))
    assert abs(ai._pass_chance(gs.get_ship_by_id("m"), "lock_on") - p_sum_at_most(2, 7)) < 1e-9
    assert abs(ai._pass_chance(gs.get_ship_by_id("n"), "lock_on") - p_sum_at_most(2, 8)) < 1e-9
    ai.tc.command_check_failed = True
    assert ai._pass_chance(gs.get_ship_by_id("m"), "lock_on") == 0.0


def test_lock_on_reroll_gain_by_armour():
    """Re-rolling misses adds 1 - p a die: more against harder Armour."""
    from tests.conftest import make_ship
    bat = {"name": "B", "weapon_type": "battery", "strength": 6, "range_cm": 30,
           "arcs": ["front"]}
    me = make_ship(id="m", player=2, x=50.0, y=50.0, heading=0.0, weapons=[bat])
    t4 = make_ship(id="t4", player=1, x=70.0, y=50.0, armor_prow="4+", armor_side="4+")
    t6 = make_ship(id="t6", player=1, x=70.0, y=50.0, armor_prow="6+", armor_side="6+")
    gs, ai = _ai([me, t4, t6])
    m = gs.get_ship_by_id("m")
    g4 = ai._arc_score(m, 50.0, 50.0, 0.0, gs.get_ship_by_id("t4"), guns_only=True,
                       reroll_gain=True)
    g6 = ai._arc_score(m, 50.0, 50.0, 0.0, gs.get_ship_by_id("t6"), guns_only=True,
                       reroll_gain=True)
    assert abs(g4 - 6 * 0.5) < 1e-9 and abs(g6 - 6 * (5 / 6)) < 1e-9


def test_leech_value_is_the_thrusters_effect_only_no_damage():
    """Xenos p.6: each leech hit is an automatic Thrusters Damaged, "do not
    apply any extra damage": the AI's value is the effect alone over the
    salvo's exact hits (crit_effect_value), no hull hit."""
    g, d = _fleets()
    raider = copy.deepcopy(next(s for s in d if "Subjugation" in s.ship_class
                                and any(w.get("weapon_type") == "torpedo" for w in s.weapons)))
    raider.x, raider.y, raider.heading, raider.leadership = 50.0, 75.0, 90.0, 8
    lunar = copy.deepcopy(next(s for s in g if "Lunar" in s.ship_class))
    lunar.x, lunar.y, lunar.heading, lunar.leadership = 50.0, 50.0, 270.0, 8
    gs, ai = _ai([lunar, raider])
    w = next(w for w in raider.weapons if w.get("weapon_type") == "torpedo")
    a, t = gs.get_ship_by_id(raider.id), gs.get_ship_by_id(lunar.id)
    import src.hit_and_run as hr
    orig = hr.crit_effect_value
    try:
        # with the effect worth nothing, leech is worth nothing (no damage term)
        hr.crit_effect_value = lambda *a_, **k: 0.0
        import src.waves as wv
        orig_r = wv.raid_squadron_value
        wv.raid_squadron_value = lambda *a_, **k: 0.0
        assert ai._torpedo_kind_by_value(a, w, t) != "leech"
        wv.raid_squadron_value = orig_r
    finally:
        hr.crit_effect_value = orig
