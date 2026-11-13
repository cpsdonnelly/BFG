"""Export 13: Eldar (MMS v2.0, update 49) and Necrons (update 48) in the catalog.
Eldar are playable (MMS v2.0); Necrons are listed but unsupported until their rules are built."""
from src.ship_catalog import find_ship_class, get_faction_ships
from src.booklet_options import ship_option_errors


def test_eldar_and_necron_ships_are_listed_but_unsupported():
    eldar = get_faction_ships("eldar", include_unsupported=True)
    necrons = get_faction_ships("necrons", include_unsupported=True)
    assert len(eldar) == 24 and len(necrons) == 10
    # Eldar MMS v2.0 rules are built: the ships are playable except those with
    # either/or armament or no fixed points cost
    playable = [e for e in eldar if not e.unsupported]
    assert len(playable) >= 18
    assert not any(any("MMS" in r for r in e.unsupported) for e in eldar)
    assert all(any("Necron rules" in r for r in e.unsupported) for e in necrons)
    assert not get_faction_ships("necrons")          # nothing playable yet


def test_leadership_columns():
    assert find_ship_class("Eclipse Class Cruiser").leadership_table == "Eldar"
    assert find_ship_class("Scythe Class Harvest Ship").leadership_table == "Default"


def test_obelisk_keeps_the_rolled_leadership_and_one_free_reroll():
    """Owner ruling (update 55): no Ld of its own, the ship rolls Ld as normal;
    as a Monument it still has a free re-roll and may buy more."""
    scythe = find_ship_class("Scythe Class Harvest Ship")
    d = scythe.to_ship_dict("S", 1, upgrades=["Monument: Obelisk"])
    assert d["leadership_table"] == "Default" and d["leadership"] == 0
    assert d["rerolls_remaining"] == 1 and "fleet_commander" in d["special_rules"]
    d = scythe.to_ship_dict("S", 1, upgrades=["Monument: Obelisk", "Commander: 2 extra re-rolls"])
    assert d["rerolls_remaining"] == 3 and d["points_value"] == scythe.points_cost + 75
    d = scythe.to_ship_dict("S", 1, upgrades=["Monument: Monolith"])
    assert d["leadership"] == 9 and not d["leadership_table"]
    names = {u.name for u in scythe.upgrades_available}
    assert "Monument: Sepulchre" not in names                 # needs a tombship
    assert "Monument: Sepulchre" in {u.name for u in find_ship_class("Cairn Class Tombship")
                                     .upgrades_available}
    assert ship_option_errors(scythe, ["Commander: 1 extra re-roll"])    # needs a commander
