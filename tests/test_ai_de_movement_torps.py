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
