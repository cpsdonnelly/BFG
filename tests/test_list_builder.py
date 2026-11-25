"""The AI list builder (To do 24) and its random-choice log (To do 31)."""
import collections
import pytest
from src.list_builder import build_random_fleet, ListBuilder, ship_size, _shortfall
from src.fleet_lists import ALL_LISTS
from src.fleet_loader import fleet_to_ships


@pytest.mark.parametrize("key", [fl["key"] for fl in ALL_LISTS
                                 if fl.get("kind", "fleet") == "fleet"][::4])
def test_random_fleets_keep_their_list_rules(key):
    d = build_random_fleet(key, 1000, seed=1)
    assert d["problems"] == [], d["problems"]
    assert 0 < d["total_points"] <= 1000
    assert fleet_to_ships(d, 1)                 # the game loads it


def test_the_same_seed_builds_the_same_fleet_and_logs_its_choices():
    a = build_random_fleet("navy_gothic", 1000, seed=5)
    b = build_random_fleet("navy_gothic", 1000, seed=5)
    assert [s["name"] for s in a["ships"]] == [s["name"] for s in b["ships"]]
    whats = {c["what"] for c in a["random_choices"]}
    assert {"personality", "escorts", "ship"} & whats and "attempt" in whats


def test_carrier_heavy_takes_the_biggest_carrier_and_its_requirements():
    d = build_random_fleet("navy_gothic", 1000, "carrier", seed=3)
    names = collections.Counter(s["name"] for s in d["ships"])
    assert names["Emperor Battleship"] == 1 and d["problems"] == []
    # escorts: 2D3 of at most two classes (owner), not padding
    esc = {s["name"] for s in d["ships"] if s["ship_type"] == "escort"}
    assert len(esc) <= 2


def test_an_impossible_personality_is_replaced_and_logged():
    b = ListBuilder("tau_demiurg_war_host", 1000, "grand_cruiser", seed=1)
    b.build()
    assert any(c.get("unavailable") == "grand_cruiser" for c in b.choices)


def test_shortfall_reads_how_far_a_rule_is_from_being_met():
    assert _shortfall("X (Xenos p.13): 3 capital ship(s) need at least 9 escorts (5 taken).") == 4
    assert _shortfall("Sword of Eldanesh (Alaitoc): 3 taken, at most 1.") == 2
    assert _shortfall("5 towed dhow(s) but gravitic hooks for only 0.") == 5


def test_ship_sizes():
    from src.ship_catalog import find_ship_class
    assert ship_size(find_ship_class("Emperor Battleship")) == "battleship"
    assert ship_size(find_ship_class("Mars Battlecruiser")) == "heavy_cruiser"
    assert ship_size(find_ship_class("Dauntless Light Cruiser")) == "light_cruiser"
