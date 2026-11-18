"""Dark Eldar, slice 1 (CLAUDE.md To do 19): the catalog, Kabal Variants
(exactly one per ship), the Dread Archon / Dracons / crew upgrades, the
Raiders fleet list, Dark Eldar craft, plasma and leech torpedoes."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.models import OrdnanceMarker, OrdnanceType
from src.ordnance import resolve_torpedo_attack, CRAFT_STATS
from src.ship_catalog import get_ship_class
from src.booklet_options import ship_option_errors
from src.fleet_lists import fleet_list_errors


def _entry(name):
    return get_ship_class("dark_eldar", name)


def _names(entry):
    return [u.name for u in entry.upgrades_available]


def test_ships_carry_dark_eldar_rules_and_weapon_flags():
    e = _entry("Torture Class Cruiser")
    rules = e.special_rules
    assert "dark_eldar" in rules and "shadowfield" in rules
    corsair = _entry("Corsair Class Frigate")
    assert any(w.get("de_phantom") or w.get("de_battery") for w in corsair.weapons) or \
        corsair.weapons == []


def test_kabal_variant_is_required_and_only_one():
    e = _entry("Subjugation Class Raider")
    variants = [n for n in _names(e) if n.startswith("Kabal Variant:")]
    assert len(variants) == 2
    assert "Choose one Kabal Variant." in ship_option_errors(e, [])
    assert ship_option_errors(e, [variants[0]]) == []
    assert ship_option_errors(e, variants)          # two from one group


def test_succubus_burning_scale_with_voidravens_costs_170():
    e = _entry("Succubus Class Light Cruiser")
    pick = [u for u in e.upgrades_available
            if u.name.startswith("Kabal Variant") and "Voidraven" in u.name]
    assert pick and e.points_cost + pick[0].points_cost == 170


def test_archon_dracons_and_crew_are_offered():
    names = _names(_entry("Torture Class Cruiser"))
    assert "Dread Archon (+2 Ld)" in names and "Dracon (+1 Ld)" in names
    assert {"Wych Cult", "Incubi", "Haemonculi Coven"} <= {n.split(" (")[0] for n in names}
    assert not any(n.startswith("Dread Archon") for n in _names(_entry("Corsair Class Frigate")))


def test_raiders_list_needs_archon_three_escorts_a_capital_ship_and_mortalis_ratio():
    def row(c, up=()):
        return {"entry": _entry(c), "upgrades": list(up), "list": "dark_eldar_raiders"}
    ok = [row("Succubus Class Light Cruiser", ["Dread Archon (+2 Ld)"])] + \
        [row("Corsair Class Frigate")] * 3
    assert fleet_list_errors("dark_eldar_raiders", ok, 320) == []
    bad = fleet_list_errors("dark_eldar_raiders",
                            [row("Mortalis Class Grand Cruiser"), row("Torture Class Cruiser")], 530)
    assert any("Grand Cruisers" in e for e in bad)
    assert any("fleet commander" in e for e in bad)
    assert any("at least 6 escorts" in e for e in bad)


def test_dark_eldar_craft():
    assert CRAFT_STATS["raptor"][2] == 4
    assert {k: CRAFT_STATS[k][1] for k in ("raptor", "razorwing", "slavebringer",
                                                  "voidraven")} == \
        {"raptor": 30, "razorwing": 20, "slavebringer": 30, "voidraven": 20}


def _marker(o_type, rules):
    return OrdnanceMarker(id="tp", ordnance_type=o_type, owner_player=1, launched_by="a",
                          x=50.0, y=55.0, heading=270.0, strength=3, special_rules=rules)


def _target():
    return make_ship(id="t", player=2, x=50.0, y=50.0, heading=0.0, hits_max=8, turrets=0,
                     shields_max=0, armor_prow="6+", armor_side="5+")


def test_plasma_torpedoes_reroll_misses():
    gs = make_gs([_target()])
    rolls = [5, 2, 1,      # vs 5+: one hit
             6, 3,         # misses re-rolled: one more
             2, 3]         # crit checks
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_STANDARD.value, ["dark_eldar"]),
                               gs.get_ship_by_id("t"), dice, gs)
    assert dice._idx == len(rolls) and r["hits"] == 2
    assert gs.get_ship_by_id("t").hits_remaining == 6


def test_leech_torpedoes_give_thrusters_crits_no_damage():
    gs = make_gs([_target()])
    rolls = [5, 6, 1,      # two hits
             2]            # plasma re-roll of the miss? leech isn't standard: no re-roll
    dice = DiceStub(rolls[:3])
    r = resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_LEECH.value, ["dark_eldar"]),
                               gs.get_ship_by_id("t"), dice, gs)
    assert dice._idx == 3 and r["hits"] == 2
    t = gs.get_ship_by_id("t")
    assert t.hits_remaining == 8
    assert [c["crit_type"] for c in t.critical_damage] == ["thrusters_damaged"] * 2
