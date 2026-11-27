"""Build a random fleet with the AI list builder (To do 24) and save it as a
fleet file (with its log of random choices, To do 31).

    python tools/random_fleet.py --list navy_gothic --points 1000 \\
        [--personality carrier] [--seed 7] [--out data/fleets/random.json]

Personalities: carrier, cruiser, light_cruiser, escort, heavy_cruiser,
grand_cruiser, battleship, random (the default). List keys: --lists."""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.fleet_lists import ALL_LISTS                      # noqa: E402
from src.list_builder import build_random_fleet, PERSONALITIES  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", help="fleet list key")
    ap.add_argument("--points", type=int, default=1000)
    ap.add_argument("--personality", default="random",
                    choices=["random"] + list(PERSONALITIES))
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", default="")
    ap.add_argument("--lists", action="store_true", help="print the fleet list keys")
    a = ap.parse_args()
    if a.lists or not a.list:
        for fl in ALL_LISTS:
            if fl.get("kind", "fleet") == "fleet":
                print(f"{fl['key']:28} {fl['name']}")
        return
    data = build_random_fleet(a.list, a.points, a.personality, a.seed)
    print(f"{data['fleet_name']}: {data['total_points']} pts, "
          f"{len(data['ships'])} ships ({data['personality']} heavy)")
    for s in data["ships"]:
        print(f"  {s['name']:40} {s['points_value']:4} pts  {s.get('squadron_id', '')}")
    for p in data["problems"]:
        print("  PROBLEM:", p)
    out = a.out or os.path.join("data", "fleets", f"random_{a.list}_{a.points}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("->", out)
    sys.exit(1 if data["problems"] else 0)


if __name__ == "__main__":
    main()
