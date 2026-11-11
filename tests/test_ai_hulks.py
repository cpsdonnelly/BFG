"""AI shooting enemy hulks when their re-rolled catastrophic damage would
blow up among enemy ships (CLAUDE.md To do 1: when hulks are worth shooting)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ai_hazards import hulk_shot_vp

LANCE = {"name": "Prow Lances", "weapon_type": "lance", "range_cm": 25, "strength": 4,
         "arcs": ["front"]}


def _hulk(**kw):
    base = dict(id="h", player=2, x=20.0, y=0.0, hits_max=12, points_value=300,
                status="drifting_hulk", hits_remaining=0, shields_max=0)
    base.update(kw)
    return make_ship(**base)


def test_hulk_shot_value_sign():
    h = _hulk()
    e1 = make_ship(id="e1", player=2, x=24.0, y=3.0, shields_max=1, points_value=180)
    e2 = make_ship(id="e2", player=2, x=24.0, y=-3.0, shields_max=1, points_value=180)
    gs = make_gs([h, e1, e2])
    assert hulk_shot_vp(h, gs, 1) > 0                 # enemies around it
    ours = make_ship(id="o", player=1, x=23.0, y=0.0, shields_max=1, points_value=250)
    gs2 = make_gs([h, ours])
    assert hulk_shot_vp(h, gs2, 1) < 0                # our own ship would suffer
    assert hulk_shot_vp(h, make_gs([h]), 1) == 0.0    # nobody near: no reason


def test_ai_fires_at_hulk_among_enemies_not_near_friends():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController

    def run(friend_near):
        shooter = make_ship(id="s", player=1, x=0.0, y=0.0, weapons=[dict(LANCE)])
        ships = [shooter, _hulk(),
                 # within blast reach of the hulk (~12cm), beyond our 25cm lances
                 make_ship(id="e1", player=2, x=30.0, y=6.0, shields_max=1, points_value=180),
                 make_ship(id="e2", player=2, x=30.0, y=-6.0, shields_max=1, points_value=180)]
        if friend_near:
            ships.append(make_ship(id="f", player=1, x=22.0, y=8.0, shields_max=1,
                                   points_value=250))
        gs = make_gs(ships)
        gs.current_phase = "shooting"
        dice = DiceStub([1] * 4)                       # the lance shots all miss
        ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
        ai.difficulty = "normal"
        ai._committed = {}
        return ai._hulk_shot(gs.get_ship_by_id("s"), LANCE)
    assert run(False) is not None and run(False).id == "h"
    assert run(True) is None


def test_ai_hulk_shot_end_to_end_rerolls_catastrophic():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    shooter = make_ship(id="s", player=1, x=0.0, y=0.0, weapons=[dict(LANCE)])
    gs = make_gs([shooter, _hulk(),
                  make_ship(id="e1", player=2, x=30.0, y=6.0, shields_max=1, points_value=180),
                  make_ship(id="e2", player=2, x=30.0, y=-6.0, shields_max=1, points_value=180)])
    gs.current_phase = "shooting"
    rolls = [4, 1, 1, 1,   # lances vs the hulk (4+): one hit
             3]            # catastrophic re-roll (2D6 total 3): still a drifting hulk
    dice = DiceStub(rolls)
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    ai._committed = {}
    ai._fire_ship(gs.get_ship_by_id("s"))
    assert dice._idx == len(rolls)
    assert any("shooting the hulk" in line for line in gs.log)
    assert any("Catastrophic Damage on Test Ship" in line for line in gs.log)
