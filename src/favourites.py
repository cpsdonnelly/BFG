"""Favourite fleets (To do 27, owner): on quitting, mid-game or at the end, each
player may save the fleet they played to a favourites section of the fleet
lists: a copy of the fleet file as it was chosen (not the battle damage) in
data/fleets/favourites/, listed first in the setup wizard with a star. No
window here: favourites_ui asks."""
import json
import os
import re
from typing import List, Optional

FAV_DIR = os.path.join("data", "fleets", "favourites")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "fleet").lower()).strip("_") or "fleet"


def is_favourite(path: str, fav_dir: Optional[str] = None) -> bool:
    fav_dir = fav_dir or FAV_DIR
    return os.path.abspath(os.path.dirname(path)) == os.path.abspath(fav_dir)


def save_favourite(path: str, fav_dir: Optional[str] = None, name: Optional[str] = None) -> str:
    """Copy the fleet file into the favourites (named after the fleet; an
    existing favourite with the same contents is reused, a different one gets
    a number). Returns the favourite's path."""
    fav_dir = fav_dir or FAV_DIR
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    os.makedirs(fav_dir, exist_ok=True)
    base = _slug(name or data.get("fleet_name", os.path.splitext(os.path.basename(path))[0]))
    data["favourite"] = True
    n = 0
    while True:
        out = os.path.join(fav_dir, f"{base}{'' if not n else f'_{n}'}.json")
        if not os.path.exists(out):
            break
        with open(out, encoding="utf-8") as fh:
            if json.load(fh) == data:
                return out                 # already a favourite
        n += 1
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return out


def favourite_fleets(fav_dir: Optional[str] = None) -> List[str]:
    fav_dir = fav_dir or FAV_DIR
    if not os.path.isdir(fav_dir):
        return []
    return sorted(os.path.join(fav_dir, f) for f in os.listdir(fav_dir) if f.endswith(".json"))


def to_offer(files: dict, fav_dir: Optional[str] = None) -> dict:
    """{player: path} of the fleets played that aren't favourites yet."""
    fav_dir = fav_dir or FAV_DIR
    return {p: f for p, f in (files or {}).items()
            if f and os.path.exists(f) and not is_favourite(f, fav_dir)}
