"""To do 26: the quick demo's set-up (Cruiser Clash, random terrain, fleets
chosen or random, the mode)."""
import json
import random
from src.demo import demo_setup, random_fleet_file, RANDOM


def test_demo_setup_modes():
    s = demo_setup("a.json", "b.json", "vs_ai", rng=random.Random(1))
    assert s["scenario_mode"] == "cruiser_clash" and s["terrain"] == "random"
    assert 1 <= s["battlezone"] <= 6 and s["ai_player"] == 2 and not s["ai_spectator"]
    assert demo_setup("a", "b", "hot_seat")["ai_player"] is None
    sp = demo_setup("a", "b", "spectator", "easy")
    assert sp["ai_spectator"] and sp["ai_difficulty_p1"] == "easy"


def test_random_fleet_is_valid_and_loads(tmp_path):
    from src.fleet_loader import load_fleet_file, fleet_to_ships
    path = random_fleet_file(random.Random(5), 1000, "navy_gothic", out_dir=str(tmp_path))
    data = json.load(open(path))
    assert not data["problems"] and data["total_points"] <= 1000
    assert fleet_to_ships(load_fleet_file(path), 1)


def test_random_choice_builds_a_file(tmp_path, monkeypatch):
    import src.demo as demo
    monkeypatch.setattr(demo, "RANDOM_DIR", str(tmp_path))
    monkeypatch.setattr(demo, "random_fleet_file",
                        lambda rng, points: str(tmp_path / "x.json"))
    s = demo_setup(RANDOM, "b.json", rng=random.Random(2))
    assert s["p1_fleet"].endswith("x.json") and s["p2_fleet"] == "b.json"
