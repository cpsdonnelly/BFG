"""Tau Emissary configurations and the Deflector (12_tau-allies.md): ion
cannons for the hooks, a gravitic launcher or mine launchers for the bays
(not both), a Deflector lost to a prow critical."""
from src.ship_catalog import get_ship_class
from src.booklet_options import ship_option_errors
from src.models import Ship


def _e():
    return get_ship_class("tau_kororvesh", "Emissary Light Cruiser")


def test_owner_emissary_build():
    ups = ["Configuration: ion cannons for the gravitic hooks",
           "Mine launchers (replace all launch bays)", "Deflector"]
    assert ship_option_errors(_e(), ups) == []
    s = Ship.from_dict(_e().to_ship_dict("E", 1, ship_id="E", upgrades=ups))
    assert s.points_value == 130 and s.armor_prow == "6+"
    kinds = sorted(w["weapon_type"] for w in s.weapons)
    assert kinds == ["battery", "battery", "lance", "lance", "mine_launcher"]
    assert not any(r.startswith("hooks:") for r in s.special_rules)
    assert ship_option_errors(_e(), ["Mine launchers (replace all launch bays)",
                                     "Configuration: prow gravitic launcher for the launch bays"])


def test_deflector_lost_to_a_prow_crit():
    s = Ship.from_dict(_e().to_ship_dict("E", 1, ship_id="E", upgrades=["Deflector"]))
    assert s.armor_for_arc("front") == 6
    s.critical_damage = [{"crit_type": "prow_armament"}]
    assert s.armor_for_arc("front") == 5
    hero = get_ship_class("tau_kororvesh", "Hero Starship")
    assert "deflector" in hero.special_rules
