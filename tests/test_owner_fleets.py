"""To do 25 / 32: the owner's fleets load into a game, deploy automatically,
and the Mechanicus refits they use exist."""
import json
import os

import pytest

from src.fleet_loader import load_fleet_file, fleet_to_ships
from src.game_state import GameState
from src.ship_catalog import find_ship_class, get_upgrades_for_ship

FLEETS = {"owner_chaos_1000.json": 1000, "owner_gothic_1000.json": 1000,
          "owner_bakka_1000.json": 1000, "owner_tau_merchant_1000.json": 990,
          "owner_space_marines_1000.json": 1000, "owner_mechanicus_1000.json": 990,
          "owner_dark_eldar_1000.json": 990, "owner_tyranid_gestating_990.json": 990,
          "owner_tyranid_vanguard_1000.json": 1000, "owner_tyranid_hive_980.json": 980,
          "owner_tau_protector_980.json": 980, "owner_orks_980.json": 980,
          "owner_necrons_1000.json": 1000, "owner_necrons_war_1000.json": 1000,
          "owner_eldar_1000.json": 1000}
DIR = os.path.join(os.path.dirname(__file__), "..", "data", "fleets")


@pytest.mark.parametrize("fname,total", FLEETS.items())
def test_owner_fleet_files_load_with_their_totals(fname, total):
    data = load_fleet_file(os.path.join(DIR, fname))
    assert data["total_points"] == total
    ships = fleet_to_ships(data, 1)
    assert len({s.id for s in ships}) == len(ships)          # builder files have no ids
    # a Tyranid Vanguard fleet has no hive ship to lead it
    assert sum(s.is_flagship for s in ships) == (0 if "vanguard" in fname else 1)


def test_builder_saved_fleets_get_stable_ids_and_auto_deploy():
    from src.deployment import deployment_state, auto_place
    gs = GameState()
    for p, f in ((1, "owner_gothic_1000.json"), (2, "owner_chaos_1000.json")):
        for s in fleet_to_ships(load_fleet_file(os.path.join(DIR, f)), p):
            gs.add_ship(s)
    assert [s["id"] for s in gs.ships][:2] == ["p1_s1", "p1_s2"]
    assert auto_place(gs, deployment_state(gs)) == []       # squadrons stay coherent
    assert len({(round(s["x"]), round(s["y"])) for s in gs.ships}) == len(gs.ships)


def test_mechanicus_tyrant_refits():
    from src.booklet_options import ship_option_errors
    e = find_ship_class("Mechanicus Tyrant Cruiser")
    names = {u.name: u.points_cost for u in get_upgrades_for_ship(e)}
    nova, guns = ("Refit: prow nova cannon for the torpedoes",
                  "Refit: plasma-boosted gunnery (30cm macrobatteries to 45cm)")
    assert names[nova] == 20 and names[guns] == 10
    d = e.to_ship_dict("t", 1, upgrades=[nova, guns])
    assert d["points_value"] == 245                            # the owner's 245
    assert {w["range_cm"] for w in d["weapons"] if w["weapon_type"] == "battery"} == {45}
    assert any(w["weapon_type"] == "nova_cannon" for w in d["weapons"])
    assert not any(w["weapon_type"] == "torpedo" for w in d["weapons"])
    # "or refitted torpedoes instead"
    assert ship_option_errors(e, [nova, "Refitted Torpedoes (D6 at game start)"])


@pytest.mark.parametrize("fname,total", FLEETS.items())
def test_ship_values_add_up_to_the_fleet_total(fname, total):
    """Victory points score each ship's own value, so the values must carry
    every cost (commanders, re-rolls, list prices, lost Tactical Flexibility)."""
    data = load_fleet_file(os.path.join(DIR, fname))
    assert sum(s["points_value"] for s in data["ships"]) == total


def test_space_marines_every_strike_cruiser_has_the_secondary_shield():
    """Owner: all five take it (any number may, +15 each); two also swap their
    macrobatteries for launch bays, 180 each with Wings of Fury taken."""
    data = load_fleet_file(os.path.join(DIR, "owner_space_marines_1000.json"))
    sc = [s for s in data["ships"] if s["ship_class"] == "Strike Cruiser"]
    assert len(sc) == 5
    assert all("Secondary Shield (+1 Shield)" in s["upgrades"] and s["shields_max"] == 2
               for s in sc)
    bays = [s for s in sc if "Variant: macrobatteries to launch bays" in s["upgrades"]]
    assert [s["points_value"] for s in bays] == [180, 180]
