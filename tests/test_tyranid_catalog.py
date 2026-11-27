"""Tyranids, slice 1 (CLAUDE.md To do 19): catalog, gene templates, weapon
configurations, biomorphs, phage mines, synapse nodes and the fleet lists."""
from src.ship_catalog import get_ship_class
from src.booklet_options import ship_option_errors
from src.fleet_lists import fleet_list_errors
from src.movement import aaf_bonus_dice
from tests.conftest import make_ship


def _e(name):
    return get_ship_class("tyranids", name)


def _ship(entry, ups):
    return entry.to_ship_dict(name="t", player=1, upgrades=ups)


def test_profiles_fixed_ld_spore_cloud_and_proteus_armament():
    p = _e("Proteus Class Hive Ship")
    assert p.leadership == 10 and "synapse:10:60" in p.special_rules
    assert p.shields_max == p.turrets == 5
    kinds = sorted(w["weapon_type"] for w in p.weapons)
    assert kinds.count("launch_bay") == 2 and "feeder_tendrils" in kinds and "torpedo" in kinds
    assert _e("Escort Drone").leadership == 7 and p.leadership_table == ""
    k = _e("Kraken")
    assert k.armor_prow == "6+" and k.turrets == 0 and "bonded_exo_plating" in k.special_rules


def test_gene_templates_are_classes():
    g = _e("Tyranid Bio-Cruiser (Guardian)")
    assert g.points_cost == 70 and g.turrets == 1 and "living_barrier" in g.special_rules
    c = _e("Tyranid Bio-Cruiser (Carnivore)")
    assert c.points_cost == 95 and c.armor_prow == "6+" and c.turrets == 0
    assert [w["weapon_type"] for w in c.weapons] == ["massive_claws"]
    s = _e("Scylla Strain Bio-Cruiser w/ Synapse Node")
    assert s.points_cost == 100 and s.leadership == 8 and "synapse:8:30" in s.special_rules
    assert _e("Tyranid Bio-Cruiser") is None


def test_charybdis_configuration_and_combining():
    e = _e("Charybdis Class Hive Ship")
    assert any("choose 1 prow" in x for x in ship_option_errors(e, []))
    ups = ["Prow: Massive Claws", "Thorax: Launch Glands", "Port / Starboard: Launch Glands x2"]
    assert ship_option_errors(e, ups) == []
    d = _ship(e, ups)
    assert d["points_value"] == 165 + 15 + 20 + 40
    glands = {w["name"]: w["strength"] for w in d["weapons"] if w["weapon_type"] == "launch_bay"}
    assert glands == {"Thorax Launch Glands": 2, "Port Launch Glands": 2,
                      "Starboard Launch Glands": 2}
    # Booklet example: thorax glands + two sets of port / starboard glands pay +30
    assert "Phage mines (glands S6)" in [u.name for u in e.upgrades_available]
    assert ship_option_errors(e, ups + ["Phage mines (glands S6)"]) == []
    assert any("phage" in x for x in ship_option_errors(e, ups + ["Phage mines (glands S4)"]))
    four = ups[:2] + ["Port / Starboard: Launch Glands x2", "Port / Starboard: Pyro-acid Batteries x2"]
    assert any("port / starboard" in x for x in ship_option_errors(e, four))


def test_scylla_tendrils_combine_and_carnivore_two_thorax():
    e = _e("Tyranid Bio-Cruiser (Scylla)")
    ups = ["Prow: Feeder Tendrils", "Thorax: Pyro-acid Battery"]
    assert ship_option_errors(e, ups) == []
    tendrils = [w for w in _ship(e, ups)["weapons"] if w["weapon_type"] == "feeder_tendrils"]
    assert len(tendrils) == 1 and tendrils[0]["strength"] == 2
    c = _e("Tyranid Bio-Cruiser (Carnivore)")
    assert any("thorax" in x for x in ship_option_errors(c, ["Prow: Massive Claws",
                                                              "Thorax: Feeder Tendrils"]))
    assert ship_option_errors(c, ["Prow: Massive Claws", "Thorax: Feeder Tendrils",
                                  "Thorax: Excretion Ducts"]) == []
    names = [u.name for u in _e("Tyranid Bio-Cruiser (Prowler)").upgrades_available]
    assert "Thorax: Excretion Ducts" not in names


def test_biomorph_limits_and_minor_node():
    e = _e("Tyranid Bio-Cruiser (Scylla)")
    base = ["Prow: Feeder Tendrils", "Thorax: Pyro-acid Battery"]
    three = ["Biomorph: Solar Vanes", "Biomorph: Adrenaline Sacs", "Biomorph: Reinforced Carapace"]
    assert any("at most 2 biomorphs" in x for x in ship_option_errors(e, base + three))
    node = "Minor Synapse Node (Ld7, 30cm)"
    assert ship_option_errors(e, base + three + [node]) == []
    d = _ship(e, base + [node, "Biomorph: Reinforced Carapace"])
    assert d["leadership"] == 7 and d["hits_max"] == 8 and d["points_value"] == 85 + 5 + 10 + 5 + 20
    assert any("needs" in x for x in ship_option_errors(e, base + ["Hive Mind re-rolls: 1"]))
    k = _e("Kraken")
    assert any("at most 1 biomorph" in x for x in ship_option_errors(
        k, ["Weapon: Feeder Tendrils", "Biomorph: Solar Vanes", "Biomorph: Tenacity"]))


def test_adrenaline_sacs_and_proteus_aaf_dice():
    assert aaf_bonus_dice(make_ship(special_rules=["aaf_2d6"])) == 2
    assert aaf_bonus_dice(make_ship(special_rules=["adrenaline_sacs"])) == 6


def _row(cls, ups=(), key="tyranid_hive"):
    return {"entry": _e(cls), "upgrades": list(ups), "list": key}


def test_hive_fleet_list_limits():
    chary = _row("Charybdis Class Hive Ship")
    drones = [_row("Escort Drone", ["Weapon: Feeder Tendrils"])] * 6
    bio = [_row("Tyranid Bio-Cruiser (Guardian)")] * 3
    assert fleet_list_errors("tyranid_hive", [chary] + bio + drones, 600) == []
    errs = fleet_list_errors("tyranid_hive", [chary] + bio * 2 + drones[:5], 800)
    assert any("Bio-cruisers" in x for x in errs) and any("escort drones" in x for x in errs)
    errs = fleet_list_errors("tyranid_hive", [_row("Proteus Class Hive Ship")], 600)
    assert any("2000" in x for x in errs)
    assert any("primary hive ship" in x for x in fleet_list_errors("tyranid_hive", drones, 120))


def test_gestating_and_vanguard_lists():
    sc = _row("Scylla Strain Bio-Cruiser w/ Synapse Node", key="tyranid_gestating")
    drones = [_row("Escort Drone", key="tyranid_gestating")] * 4
    assert fleet_list_errors("tyranid_gestating", [sc] + drones, 180) == []
    bad = fleet_list_errors("tyranid_gestating",
                            [sc] + [_row("Tyranid Bio-Cruiser (Guardian)",
                                         key="tyranid_gestating")] * 3 + drones, 390)
    assert any("Bio-cruisers" in x for x in bad)
    assert fleet_list_errors("tyranid_vanguard",
                             [_row("Tyranid Bio-Cruiser (Prowler)", key="tyranid_vanguard")],
                             90) == []
