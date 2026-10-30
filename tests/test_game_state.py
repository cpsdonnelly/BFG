"""Tests for GameState save/load and in-place restore."""
from src.game_state import GameState
from src.turn_controller import TurnController
from tests.conftest import make_ship, make_gs, DiceStub


def test_save_load_round_trip(tmp_path):
    gs = make_gs([make_ship(id="a", x=12.5, y=40.0, heading=90.0)])
    gs.turn_number = 5
    gs.current_phase = "shooting"
    gs.active_player = 2
    gs.artefact_token_pos = (30.0, 30.0)
    gs.add_log("hello")
    gs.save(str(tmp_path))

    loaded = GameState.load(str(tmp_path))
    assert loaded.turn_number == 5
    assert loaded.current_phase == "shooting"
    assert loaded.active_player == 2
    assert loaded.artefact_token_pos == (30.0, 30.0)
    assert loaded.ships == gs.ships
    assert loaded.log == gs.log


def test_restore_from_mutates_in_place_so_shared_references_see_load(tmp_path):
    saved = make_gs([make_ship(id="saved_ship")])
    saved.turn_number = 7
    saved.save(str(tmp_path))

    gs = make_gs([make_ship(id="old_ship")])
    tc = TurnController(gs, DiceStub([4]), save_dir=str(tmp_path / "run"))
    gs.restore_from(GameState.load(str(tmp_path)))

    assert tc.gs is gs
    assert tc.gs.turn_number == 7
    assert [s.id for s in tc.gs.get_ships()] == ["saved_ship"]


def test_undo_after_load_does_not_return_to_pre_load_game(tmp_path):
    saved = make_gs([make_ship(id="saved_ship")])
    saved.save(str(tmp_path))

    gs = make_gs([make_ship(id="old_ship")])
    tc = TurnController(gs, DiceStub([4]), save_dir=str(tmp_path / "run"))
    tc.begin_phase("movement")            # undo anchor = pre-load game
    tc.ships_moved.append("old_ship")
    tc.command_check_failed = True

    gs.restore_from(GameState.load(str(tmp_path)))
    tc.reset_after_load()

    assert tc.ships_moved == []
    assert tc.command_check_failed is False
    tc.undo_to_phase_start()
    assert [s.id for s in gs.get_ships()] == ["saved_ship"]
