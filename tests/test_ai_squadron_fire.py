"""AI Shooting by Squadrons (s.8): combined battery volleys (CLAUDE.md To do 1)."""
from tests.conftest import make_ship, make_gs, DiceStub

BAT = {"name": "Prow Battery", "weapon_type": "battery", "range_cm": 30, "strength": 3,
       "arcs": ["front"]}


def _scene():
    a = make_ship(id="a", player=1, x=0.0, y=0.0, heading=0.0, ship_type="escort",
                  hits_max=1, squadron_id="sq", weapons=[dict(BAT)], points_value=35)
    b = make_ship(id="b", player=1, x=0.0, y=4.0, heading=0.0, ship_type="escort",
                  hits_max=1, squadron_id="sq", weapons=[dict(BAT)], points_value=35)
    t = make_ship(id="t", player=2, x=25.0, y=2.0, heading=90.0, armor_side="5+",
                  armor_prow="6+", points_value=180)
    return make_gs([a, b, t])


def test_ai_squadron_fires_one_combined_volley():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    from src.combat import plan_squadron_volley, squadron_group
    gs = _scene()
    gs.current_phase = "shooting"
    a, b, t = gs.get_ship_by_id("a"), gs.get_ship_by_id("b"), gs.get_ship_by_id("t")
    plan = plan_squadron_volley([(a, BAT), (b, BAT)], squadron_group(t, gs.get_ships()),
                                gs.get_blast_markers(), gs.get_phenomena(), gs.get_ships())
    n = sum(x["dice"] for x in plan["attacks"])
    sep = sum(sum(x["dice"] for x in plan_squadron_volley(
        [pr], [t], gs.get_blast_markers(), gs.get_phenomena(), gs.get_ships())["attacks"])
        for pr in [(a, BAT), (b, BAT)])
    assert n >= sep and n > 0
    rolls = [1] * n                         # all miss (no damage rolls follow)
    dice = DiceStub(rolls)
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai.brace_fn = None
    ai.run_shooting_phase()
    assert dice._idx == len(rolls)          # one volley, the batteries didn't fire again
    assert any("combined batteries" in line for line in gs.log)


def test_best_aspect_choice_beats_the_old_default():
    """Combine Squadron Fire's "Best for expected hits" default (combat.best_aspect_choice):
    against an escort squadron with one ship abeam and one closing, the aspect
    that gives the most expected hits, not just the hardest one present."""
    from src.combat import plan_squadron_volley, best_aspect_choice, volley_expected_hits
    bat = {"name": "Dorsal Battery", "weapon_type": "battery", "range_cm": 45, "strength": 8,
           "arcs": ["left", "front", "right"]}
    f = make_ship(id="f", player=1, x=0.0, y=0.0, heading=0.0, weapons=[dict(bat)])
    a = make_ship(id="a", player=2, x=30.0, y=0.0, heading=90.0, ship_type="escort",
                  hits_max=1, squadron_id="s", armor_prow="5+", armor_side="5+")
    b = make_ship(id="b", player=2, x=34.0, y=0.0, heading=180.0, ship_type="escort",
                  hits_max=1, squadron_id="s", armor_prow="5+", armor_side="5+")
    gs = make_gs([f, a, b])
    args = (gs.get_blast_markers(), gs.get_phenomena(), gs.get_ships())
    plan = plan_squadron_volley([(f, bat)], [a, b], *args)
    (view, present), = plan["views"].items()
    old_default = volley_expected_hits(plan)                       # hardest present
    best = best_aspect_choice([(f, bat)], [a, b], *args)
    got = volley_expected_hits(plan_squadron_volley([(f, bat)], [a, b], *args,
                                                    aspect_choice=best))
    assert got >= max(volley_expected_hits(plan_squadron_volley(
        [(f, bat)], [a, b], *args, aspect_choice={view: p})) for p in present) - 1e-9
    assert got > old_default
