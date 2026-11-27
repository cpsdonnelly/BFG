"""Owner: ships that help friends in range move to cover as many as they can,
unless that costs VP elsewhere (the term is VP in the move score)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ai_player import AIPlayer
from src.turn_controller import TurnController


def _game():
    ships = [make_ship(id="h", player=1, x=60.0, y=60.0, points_value=200,
                       special_rules=["tyranid", "synapse:8:30"])]
    ships += [make_ship(id=f"c{i}", player=1, x=20.0 + 3 * i, y=60.0 + 9 * i,
                        points_value=100, special_rules=["tyranid"]) for i in range(3)]
    ships.append(make_ship(id="e", player=2, x=60.0, y=150.0))
    gs = make_gs(ships)
    return gs, AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))


def test_synapse_creature_values_ends_near_its_friends():
    gs, ai = _game()
    h, e = gs.get_ship_by_id("h"), gs.get_ship_by_id("e")
    near = ai._buff_term(h, 40.0, 70.0, e)
    far = ai._buff_term(h, 100.0, 70.0, e)
    assert near > 0 and far == 0.0


def test_buff_ships_move_after_the_friends_they_help():
    gs, ai = _game()
    order = [s.id for s in ai._coordinated_order(gs.player_ships(1))]
    assert order[-1] == "h"


def test_very_easy_ignores_it():
    gs, ai = _game()
    ai.difficulty = "very_easy"
    assert ai._buff_term(gs.get_ship_by_id("h"), 40.0, 70.0, gs.get_ship_by_id("e")) == 0.0
