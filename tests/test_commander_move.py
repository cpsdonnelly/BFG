"""To do 29 (owner): the fleet commander moves to another capital ship at
deployment, after the Ld roll, where the fleet list doesn't fix his ship."""
from src.fleet_loader import load_fleet_file, fleet_to_ships, roll_starting_leadership
from src.game_state import GameState
from tests.conftest import DiceStub
from src import commanders as C


def _gs():
    gs = GameState()
    for p, f in ((1, "owner_gothic_1000.json"), (2, "owner_chaos_1000.json")):
        for s in fleet_to_ships(load_fleet_file("data/fleets/" + f), p):
            gs.add_ship(s)
    roll_starting_leadership(gs, DiceStub([4] * 40))
    return gs


def test_navy_commander_moves_with_his_rerolls_points_and_ld():
    gs = _gs()
    before = sum(s.points_value for s in gs.player_ships(1))
    mars = next(s for s in gs.player_ships(1) if "Mars" in s.name)
    lunar = next(s for s in gs.player_ships(1) if "Lunar" in s.name)
    rr, cmd_ld = mars.rerolls_remaining, mars.leadership
    assert C.move_commander(gs, lunar.id, DiceStub([1]))
    mars, lunar = gs.get_ship_by_id(mars.id), gs.get_ship_by_id(lunar.id)
    assert lunar.is_flagship and not mars.is_flagship
    assert lunar.rerolls_remaining == rr and mars.rerolls_remaining == 0
    assert lunar.leadership == cmd_ld and "fleet_commander" in lunar.special_rules
    assert "fleet_commander" not in mars.special_rules
    assert mars.leadership == 6                     # rolled now: a 1 on the Default table
    assert sum(s.points_value for s in gs.player_ships(1)) == before
    # moving back gives the Lunar its own rolled Ld again
    assert C.move_commander(gs, mars.id, DiceStub([]))
    assert gs.get_ship_by_id(lunar.id).leadership == 8


def test_chaos_list_fixes_the_commander():
    gs = _gs()
    assert C.allowed_ships(gs, 2) == []             # the most expensive capital ship


def test_ai_places_by_lowest_ld():
    gs = _gs()
    best = C.best_ship(gs, 1)
    assert best is not None and best.ship_type != "escort"
