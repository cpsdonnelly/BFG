"""Spectator mode's "auto-roll every pop-up" (owner request): dice roll
automatically and every prompt takes its Auto answer, its messages logged."""
from tests.conftest import make_gs
from src.dice import mode_for, spectating_auto
from src.prompts import TkPrompter


def test_dice_mode_follows_the_spectator_setting():
    gs = make_gs([])
    gs.dice_mode = "mixed"
    assert mode_for(gs) == "mixed"
    gs.ai_spectator = True
    assert mode_for(gs) == "auto" and spectating_auto(gs)
    gs.spectator_auto = False
    assert mode_for(gs) == "mixed"


def test_prompts_answer_themselves_without_a_window():
    gs = make_gs([])
    gs.ai_spectator = True
    p = TkPrompter(root=None, gs=gs)
    assert p.choose("Radiation", "?", [("a", 1), ("b", 2)], 2) == 2
    assert p.yes_no("Brace?", "?", True) is True
    assert p.number("How far", "?", 5.0, 0, 10) == 5.0
    assert p.pick_many("Repairs", "?", ["x", "y"], 1, ["y"]) == ["y"]
    p.notify("Radiation burst", "every ship -3 Ld")
    assert any("Radiation burst" in line for line in gs.log)
