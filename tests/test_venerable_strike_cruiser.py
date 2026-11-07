"""Designing a Venerable Strike Cruiser (Imperium p.137, 03_space-marines.md)
and its fleet-list limit (owner ruling, both Space Marine lists)."""
from src.ship_catalog import find_ship_class
from src.booklet_options import ship_option_errors
from src.fleet_lists import fleet_list_errors
from src.ordnance import torpedo_kind_options


def vsc(base):
    return find_ship_class(f"Venerable Strike Cruiser ({base})")


def test_cost_crew_and_faction_rules():
    e = vsc("Avenger Grand Cruiser")
    assert e.faction == "space_marines" and e.points_cost == 200 + 25
    assert {"space_marine_crew", "teleport_assault", "venerable"} <= set(e.special_rules)
    assert e.leadership_table == "Astartes"
    assert not any(u.name.startswith("Torpedoes: short burn (40cm") for u in e.upgrades_available)


def test_thunderhawks_only_bay_strength_halved_rounding_up():
    e = vsc("Exorcist Grand Cruiser")          # port S3 + stbd S3 -> 2 + 2 (each halved)
    bays = [w for w in e.weapons if w["weapon_type"] == "launch_bay"]
    assert [w["strength"] for w in bays] == [2, 2]
    assert all(w["craft_types"] == ["thunderhawk"] for w in bays)


def test_nova_cannon_ships_take_the_strike_cruiser_prow_for_10_less():
    e = vsc("Mars Battlecruiser")              # 260, already 6+ prow: prow free, -10
    assert e.points_cost == 260 + 25 - 10
    assert not any(w["weapon_type"] == "nova_cannon" for w in e.weapons)
    torps = [w for w in e.weapons if w["weapon_type"] == "torpedo"]
    assert torps[0]["strength"] == 6 and torps[0]["boarding_torpedoes"]
    assert not any(u.name == "Strike Cruiser Prow" for u in e.upgrades_available)


def test_strike_cruiser_prow_option_and_torpedo_choices():
    e = vsc("Cardinal Battlecruiser")          # 5+ prow: the prow costs 25
    prow = next(u for u in e.upgrades_available if u.name == "Strike Cruiser Prow")
    assert prow.points_cost == 25
    d = e.to_ship_dict("V", 1, upgrades=["Strike Cruiser Prow"])
    assert d["armor_prow"] == "6+" and "Prow Macrobatteries" not in [w["name"] for w in d["weapons"]]
    sb = "Torpedoes: short burn torpedoes (instead of boarding torpedoes)"
    assert ship_option_errors(e, [sb])                       # needs torpedoes first
    assert not ship_option_errors(e, ["Strike Cruiser Prow", sb])
    six = vsc("Overlord Battlecruiser")       # already 6+ prow and torps: free prow
    assert next(u for u in six.upgrades_available if u.name == "Strike Cruiser Prow").points_cost == 0


def test_boarding_torpedoes_free_unless_short_burn_or_barrage():
    from tests.conftest import make_ship
    e = vsc("Armageddon Battlecruiser")
    torps = next(w for w in e.weapons if w["weapon_type"] == "torpedo")
    plain = make_ship(special_rules=e.special_rules)
    assert [k for k, _ in torpedo_kind_options(plain, torps)] == ["standard", "boarding"]
    d = e.to_ship_dict("V", 1, upgrades=["Torpedoes: barrage bombs (instead of boarding torpedoes)"])
    alt = make_ship(special_rules=d["special_rules"])
    assert [k for k, _ in torpedo_kind_options(alt, torps)] == ["standard", "barrage"]


def _row(name, mof=False):
    return {"entry": find_ship_class(name), "list": "sm_crusade",
            "upgrades": ["Master of the Fleet (Ld 10)"] if mof else []}


def test_one_venerable_per_three_strike_cruisers_max_two_at_1000():
    base = [_row("Space Marine Battle Barge", True)] + [_row("Strike Cruiser")] * 3
    ven = [_row("Venerable Strike Cruiser (Hades Heavy Cruiser)")]
    assert fleet_list_errors("sm_crusade", base + ven, 1200) == []
    assert any("1000pts" in e for e in fleet_list_errors("sm_crusade", base + ven, 999))
    two = base + ven * 2
    assert any("Venerable" in e for e in fleet_list_errors("sm_crusade", two, 1500))
    many = [_row("Space Marine Battle Barge", True)] + [_row("Strike Cruiser")] * 9 + ven * 3
    assert any("two in all" in e for e in fleet_list_errors("sm_crusade", many, 3000))


def test_own_special_rules_apply_ablative_prow_lost_with_prow_torpedoes():
    assert "ablative_prow_armor" in find_ship_class("Exorcist Grand Cruiser").special_rules
    e = vsc("Exorcist Grand Cruiser")
    assert "ablative_prow_armor" in e.special_rules
    d = e.to_ship_dict("V", 1, upgrades=["Strike Cruiser Prow"])
    assert "ablative_prow_armor" not in d["special_rules"]
