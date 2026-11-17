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


def test_brace_is_a_command_phase_order_in_aa():
    """AA notes: Brace is declared in the command phase, so no reactive
    prompts; the AI declares it there when its priced value is positive."""
    from src.aa_turn import brace_is_reactive
    from src.combat import offer_brace
    me = _ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)
    me.hits_remaining = 4                     # crippled, under three enemy cruisers
    foes = [_ship("Lunar Class Cruiser", 2, 75.0, 75.0 + 5 * i, 180.0, i) for i in range(3)]
    gs = make_gs([me] + foes)
    assert brace_is_reactive(gs)
    gs.turn_system = "aa"
    assert not brace_is_reactive(gs)
    asked = []
    gs.brace_hook = lambda *a: asked.append(a) or True
    assert offer_brace(gs, gs.get_ship_by_id(me.id), "x", "x", 3.0) is False and not asked
    gs.aa_settings = {"brace_in_command_phase": False}
    assert brace_is_reactive(gs)
    gs.aa_settings = {}
    dice = DiceRoller(mode="auto")
    tc = TurnController(gs, dice)
    ai = AIPlayer(1, tc, gs, dice)
    ai.difficulty = "normal"
    assert ai._aa_brace_worth_it(gs.get_ship_by_id(me.id))
    safe = gs.get_ship_by_id(me.id)
    safe.x, safe.y = 5.0, 5.0                  # out of every enemy's reach
    safe.hits_remaining = 8
    gs.update_ship(safe)
    for f in foes:
        far = gs.get_ship_by_id(f.id)
        far.x = 175.0
        gs.update_ship(far)
    assert not ai._aa_brace_worth_it(gs.get_ship_by_id(me.id))


def test_ai_passes_only_in_movement_while_the_enemy_has_units_left():
    gs = make_gs([_ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)])
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    assert ai.aa_decline("movement", 2) and not ai.aa_decline("movement", 0)
    assert not ai.aa_decline("shooting", 3)
