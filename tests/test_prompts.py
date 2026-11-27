"""To do 18 / 17: the questions asked during play go through ctx.prompt;
answers are recorded and replay in order."""
import pytest

from src import recorder
from src.prompts import Prompter, ReplayPrompter, ReplayDivergence


def test_headless_prompter_takes_best_and_records():
    recorder.start_recording()
    p = Prompter()
    assert p.choose("Pick", "?", [("A", "a"), ("B", "b")], "b") == "b"
    assert p.yes_no("Brace?", "?", True) is True
    assert p.yes_no("Plain?", "?") is False             # no best: no
    assert p.number("Turn", "?", 15.0, -45, 45) == 15.0
    assert p.pick_many("Repair", "?", ["x", "y"], 1, ["y"]) == ["y"]
    evs = recorder.events()
    assert [e["ask"] for e in evs] == ["choose", "yes_no", "yes_no", "number", "pick_many"]
    recorder.stop_recording()


def test_replay_prompter_answers_from_the_record():
    recorder.start_recording()
    p = Prompter()
    p.choose("Pick", "?", [("A", ("t", 1)), ("B", "b")], ("t", 1))
    p.yes_no("Brace?", "?", False)
    rec = recorder.events()
    r = ReplayPrompter(rec)
    assert r.choose("Pick", "?", [("A", ("t", 1)), ("B", "b")], "b") == ("t", 1)
    assert r.yes_no("Brace?", "?", True) is False       # the record, not the best
    with pytest.raises(ReplayDivergence):
        r.yes_no("Another", "?", True)
    recorder.stop_recording()
