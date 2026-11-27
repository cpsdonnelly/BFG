"""The quick demo (To do 26, owner): a Cruiser Clash on random terrain, each
side's fleet chosen from the saved fleets or built at random by the AI list
builder (To do 24), and the mode: player vs AI (the default), player vs player
or AI vs AI. No window here: `demo_setup` returns the set-up the game starts
from, the same dict the setup wizard makes (main.main reads it)."""
import json
import os
import random
from typing import Optional

RANDOM = "random"          # a fleet choice: built by the list builder
MODES = ("vs_ai", "hot_seat", "spectator")
RANDOM_DIR = os.path.join("data", "fleets", "random")


def fleet_lists():
    """The fleet lists a random fleet may come from (main fleet lists, not
    detachments)."""
    from .fleet_lists import ALL_LISTS
    return [fl["key"] for fl in ALL_LISTS if fl.get("kind", "fleet") == "fleet"]


def random_fleet_file(rng: random.Random, points: int = 1000, list_key: Optional[str] = None,
                      out_dir: str = RANDOM_DIR, tries: int = 6) -> str:
    """A random fleet built by the list builder (a random list unless given,
    a random personality), saved under data/fleets/random/; the first one
    that keeps its list's rules (another list is drawn after a failure)."""
    from .list_builder import build_random_fleet
    os.makedirs(out_dir, exist_ok=True)
    data = None
    for _ in range(tries):
        key = list_key or rng.choice(fleet_lists())
        seed = rng.randrange(1 << 30)
        data = build_random_fleet(key, points, None, seed)
        if not data["problems"]:
            break
    path = os.path.join(out_dir, f"random_{key}_{seed}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return path


def demo_setup(p1_fleet: str, p2_fleet: str, mode: str = "vs_ai", difficulty: str = "normal",
               rng: Optional[random.Random] = None, base: Optional[dict] = None,
               points: int = 1000) -> dict:
    """The demo's set-up: random terrain in a random battlezone (D6, s.39's
    table), the booklet's Cruiser Clash (p.84: its zones, eight turns, damage
    points), the two fleets (RANDOM builds one) and the mode. `base`: other
    set-up values to keep (board size, dice mode, the advanced rules)."""
    rng = rng or random.Random()
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    fleets = [p1_fleet, p2_fleet]
    for i, f in enumerate(fleets):
        if f == RANDOM:
            fleets[i] = random_fleet_file(rng, points)
    setup = dict(base or {})
    setup.update({
        "mode": "demo",
        "terrain": "random",
        "battlezone": rng.randint(1, 6),
        "scenario_mode": "cruiser_clash",
        "p1_fleet": fleets[0],
        "p2_fleet": fleets[1],
        "ai_player": None if mode == "hot_seat" else 2,
        "ai_spectator": mode == "spectator",
        "ai_difficulty": difficulty,
        "ai_difficulty_p1": difficulty if mode == "spectator" else None,
    })
    setup.setdefault("width", 120.0)
    setup.setdefault("height", 120.0)
    setup.setdefault("sunward", "north")
    setup.setdefault("dice_mode", "auto" if mode == "spectator" else "mixed")
    setup.setdefault("spectator_auto", True)
    return setup
