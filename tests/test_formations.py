"""Owner: formation by armament. Impaler / torpedo escorts gain from base
contact (their ordnance combines and meets the turrets once), gun escorts
don't; group size and deployment follow the same value."""
import random
from tests.conftest import make_ship, make_gs
from src.formations import survivors, combine_gain, needs_contact, load

IMPALER = {"name": "Impaler", "weapon_type": "launch_bay", "strength": 1,
           "impaler_bay": True, "craft_types": ["impaler"]}
GUNS = {"name": "Guns", "weapon_type": "battery", "strength": 2, "range_cm": 30,
        "arcs": ["front"]}
TORPS = {"name": "Torps", "weapon_type": "torpedo", "strength": 2, "range_cm": 30,
         "arcs": ["front"]}


def _esc(i, w, rules=None):
    return make_ship(id=f"e{i}", player=1, ship_type="escort", squadron_id="sq",
                     x=10.0 + 3 * i, y=20.0, weapons=[dict(w)],
                     special_rules=rules or ["dark_eldar"])


def test_survivors_exact():
    # 1 die at 1/2: one squadron survives half the time; two together 1.5
    assert survivors(1, 1, 0.5) == 0.5 and survivors(2, 1, 0.5) == 1.5
    assert survivors(3, 0, 0.5) == 3


def test_impalers_gain_by_combining_more_against_more_turrets():
    one = make_ship(id="t1", player=2, turrets=1, x=60, y=60)
    four = make_ship(id="t4", player=2, turrets=4, x=60, y=60)
    e = _esc(0, IMPALER)
    gs = make_gs([e, one, four])
    g1 = combine_gain(e, "impaler", [1] * 4, gs.get_ship_by_id("t1"), gs)
    g4 = combine_gain(e, "impaler", [1] * 4, gs.get_ship_by_id("t4"), gs)
    assert g4 > g1 > 0


def test_gun_escorts_need_no_contact_but_impalers_do():
    foe = make_ship(id="foe", player=2, turrets=2, x=60, y=60)
    guns = [_esc(i, GUNS, ["imperial_navy"]) for i in range(3)]
    imps = [_esc(i, IMPALER) for i in range(3)]
    gs = make_gs(guns + [foe])
    assert not needs_contact(guns, gs.get_ship_by_id("foe"), gs)
    gs2 = make_gs(imps + [foe])
    assert needs_contact(imps, gs2.get_ship_by_id("foe"), gs2)
    assert load(imps[0], "impaler") == 1 and load(guns[0], "impaler") == 0


def test_ordnance_escorts_take_the_largest_squadrons():
    from src.ship_catalog import find_ship_class
    from src.fleet_model import make_fleet_row
    from src.squadrons import organize_escorts, fleet_squadron_errors
    rows = [make_fleet_row(find_ship_class("Cobra Class Destroyer")) for _ in range(6)]
    assert organize_escorts(rows, rng=random.Random(3)) == []
    assert len({r["squadron_id"] for r in rows}) == 1          # torpedoes: one of 6
    swords = [make_fleet_row(find_ship_class("Sword Class Frigate")) for _ in range(12)]
    organize_escorts(swords, rng=random.Random(3))
    assert fleet_squadron_errors(swords) == []


def test_combined_salvo_action():
    from src.actions import combine_salvos
    gs = make_gs([make_ship(id="a", player=1), make_ship(id="b", player=1)])
    gs.ordnance = [
        {"id": "m1", "ordnance_type": "torpedo_standard", "owner_player": 1, "strength": 2,
         "launched_by": "a", "x": 0, "y": 0, "special_rules": ["x", "y"]},
        {"id": "m2", "ordnance_type": "torpedo_standard", "owner_player": 1, "strength": 2,
         "launched_by": "b", "x": 1, "y": 0, "special_rules": ["x"]}]
    combine_salvos(gs, "m1", ["m1", "m2"])
    assert len(gs.ordnance) == 1 and gs.ordnance[0]["strength"] == 4
    assert gs.ordnance[0]["special_rules"] == ["x"] and "b" in gs.ordnance[0]["launch_exempt_ships"]


def test_incubi_and_wych_raise_raid_values():
    """Incubi's 2D6-choose-one and Pain Frenzy's re-roll (a Wych Cult counts
    capital ships as crippled) are in the AI's raid values (dark_eldar.raid_value)."""
    from src.dark_eldar import raid_value
    from src.fleet_loader import load_fleet_file, fleet_to_ships
    gothic = fleet_to_ships(load_fleet_file("data/fleets/owner_gothic_1000.json"), 1)
    lunar = next(s for s in gothic if "Lunar" in s.ship_class)
    lunar.x = lunar.y = 50.0
    lunar.leadership = 8
    gs = make_gs([lunar, make_ship(id="d", player=2)])
    t = gs.get_ship_by_id(lunar.id)
    base = raid_value(["dark_eldar"], t, gs, 2)
    assert raid_value(["dark_eldar", "incubi"], t, gs, 2) > base
    assert raid_value(["dark_eldar", "wych_cult"], t, gs, 2) > base
