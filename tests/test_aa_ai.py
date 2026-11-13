"""The AI playing alternate activation (To do 13): orders in the command phase,
one unit at a time in shooting and movement, the System 3 choice."""
import random

from tests.conftest import make_gs, DiceStub
from src.models import Ship
from src.ship_catalog import find_ship_class
from src.ai_player import AIPlayer
from src.aa_turn import AATurn
from src.turn_controller import TurnController
from src.dice import DiceRoller


def _ship(name, player, x, y, h, i=0):
    d = find_ship_class(name).to_ship_dict(name, player, ship_id=f"{name[:4]}{player}{i}")
    d.update(x=x, y=y, heading=h, leadership=8)
    return Ship.from_dict(d)


def test_ai_plays_an_aa_round():
    ships = [_ship("Lunar Class Cruiser", 1, 40.0, 40.0 + 30 * i, 0.0, i) for i in range(2)]
    ships += [_ship("Lunar Class Cruiser", 2, 110.0, 45.0 + 30 * i, 180.0, i) for i in range(2)]
    gs = make_gs(ships)
    gs.table_width, gs.table_height = 180.0, 120.0
    dice = DiceRoller(mode="auto")
    tc = TurnController(gs, dice)
    ais = {p: AIPlayer(p, tc, gs, dice) for p in (1, 2)}
    for a in ais.values():
        a.difficulty = "normal"
    aa = AATurn(tc, rng=random.Random(3),
                choose_first=lambda holder, ph: holder if ais[holder].aa_choose_first(ph)
                else (3 - holder))
    aa.start_game()
    start = {s.id: (s.x, s.y) for s in gs.get_ships()}
    acted = {"shooting": [], "movement": []}
    for _ in range(6):
        ph = aa.phase
        if ph == "command":
            for p in (1, 2):
                gs.active_player = p
                ais[p].aa_command_phase()
        elif ph in acted:
            for a in ais.values():
                a.aa_phase_start(ph)
            while (nxt := aa.next_activation()) is not None:
                p, key = nxt
                unit = ais[p].aa_pick_unit(ph, aa.remaining_units(p))
                (ais[p].aa_shoot_unit if ph == "shooting" else ais[p].aa_move_unit)(
                    unit.ship_ids)
                aa.activated(p, unit.key)
                acted[ph].append(unit.key)
        aa.advance()
    assert sorted(acted["movement"]) == sorted(start)
    assert len(acted["shooting"]) == 4
    moved = [sid for sid, xy in start.items()
             if (gs.get_ship_by_id(sid).x, gs.get_ship_by_id(sid).y) != xy]
    assert sorted(moved) == sorted(start)
    assert aa.round == 2


def test_unit_values_favour_shots_now_and_late_moves():
    a = _ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)
    near = _ship("Lunar Class Cruiser", 2, 75.0, 82.0, 0.0)
    far = _ship("Lunar Class Cruiser", 1, 20.0, 110.0, 0.0, 1)
    gs = make_gs([a, near, far])
    tc = TurnController(gs, DiceStub([]))
    ai = AIPlayer(1, tc, gs, DiceStub([]))
    ai.difficulty = "normal"
    from src.activation import Unit
    ua, uf = Unit(1, [a.id], 8, 8), Unit(1, [far.id], 8, 8)
    assert ai.aa_pick_unit("shooting", [uf, ua]).key == a.id      # the shot in reach now
    assert ai.aa_pick_unit("movement", [ua, uf]).key == far.id    # the engaged ship waits
