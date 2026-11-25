"""Eldar fleet building (MMS v2.0, 09_eldar.md): the Corsair and Craftworld
fleet lists, their commanders and upgrades, and the effects in play
(Gryphon Knights, Aspect Warriors, the +1 boarding bodyguards)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ship_catalog import get_ship_class
from src.fleet_lists import fleet_list_errors
from src.boarding import _crew_damage_bonus
from src.hit_and_run import _raid_roll_modifier
from src.turn_controller import TurnController


def _e(name):
    return get_ship_class("eldar", name)


def _row(name, ups=(), key="eldar_corsair"):
    return {"entry": _e(name), "upgrades": list(ups), "list": key}


def test_the_owners_corsair_fleet_is_valid():
    rows = ([_row("Eclipse Class Cruiser", ["Shadow Prince (Ld 9)"])]
            + [_row("Hemlock Class Destroyer")] * 4 + [_row("Nightshade Class Destroyer")] * 5
            + [_row("Aconite Class Frigate")] * 4)
    assert fleet_list_errors("eldar_corsair", rows, 1000) == []
    d = _e("Eclipse Class Cruiser").to_ship_dict(name="e", player=1,
                                                 upgrades=["Shadow Prince (Ld 9)"])
    assert d["leadership"] == 9 and d["rerolls_remaining"] == 1 and d["points_value"] == 310
    # over 750 points without a Lord
    assert any("fleet commander" in e for e in fleet_list_errors("eldar_corsair", rows[1:], 760))


def test_list_limits_and_list_only_options():
    assert any("Hero" in e for e in fleet_list_errors(
        "eldar_corsair", [_row("Void Dragon Class Grand Cruiser", ["Dragon Prince (Ld 10)"])], 420))
    assert fleet_list_errors("eldar_corsair", [_row("Void Dragon Class Grand Cruiser", [
        "Dragon Prince (Ld 10)", "Dragon Prince: Hero"])], 470) == []
    # a Supernova needs two cruisers
    assert any("Supernova" in e for e in fleet_list_errors(
        "eldar_corsair", [_row("Supernova Class Grand Cruiser"), _row("Eclipse Class Cruiser")], 530))
    # over 2000 points a Dragon Prince is needed
    big = [_row("Eclipse Class Cruiser", ["Shadow Prince (Ld 9)"])] + [_row("Eclipse Class Cruiser")] * 7
    assert any("Dragon Prince" in e for e in fleet_list_errors("eldar_corsair", big, 2130))
    # Craftworld options aren't Corsair ones
    errs = fleet_list_errors("eldar_corsair", [_row("Eclipse Class Cruiser", ["Admiral (Ld 9)"])], 310)
    assert any("isn't available" in e for e in errs)
    names = [u.name for u in _e("Wyrm Class Battleship").upgrades_available]
    assert "Aspect Warriors" in names
    assert "Aspect Warriors" not in [u.name for u in _e("Eclipse Class Cruiser").upgrades_available]


def test_bodyguard_aspect_warriors_and_gryphon_knights():
    assert _crew_damage_bonus(make_ship(special_rules=["eldar_bodyguard", "aspect_warriors"])) == 2
    assert _raid_roll_modifier(["aspect_warriors"], make_ship()) == 1
    a = make_ship(id="a", player=1, leadership=10)
    b = make_ship(id="b", player=1, leadership=10, special_rules=["gryphon_knight"])
    gs = make_gs([a, b])
    gs.active_player = 1
    tc = TurnController(gs, DiceStub([12]))
    tc.command_check_failed = True
    assert not tc.can_issue_special_order(gs.get_ship_by_id("a"))
    assert tc.can_issue_special_order(gs.get_ship_by_id("b"))


# The Craftworld ships with either / or armament (MMS v2.0): one weapon choice
# per location is required; Ghostships and the Shadowhunter's own rules.
from src.booklet_options import ship_option_errors
from src.boarding import _get_ship_modifier
from src.hit_and_run import check_teleport_eligibility
from src.combat import fire_at_ordnance


def test_either_or_craftworld_ships_are_playable_with_their_choices():
    dragon = _e("Dragonship Class Battle Cruiser")
    assert not dragon.unsupported
    assert sorted(ship_option_errors(dragon, [])) == ["Choose one Eldar Keel.", "Choose one Eldar Prow."]
    ups = ["Prow: Pulsar Lance FP3", "Keel: Launch Bays S4 with Vampires"]
    assert ship_option_errors(dragon, ups) == []
    assert ship_option_errors(dragon, ups + ["Prow: Weapons Battery FP12"]) != []
    d = dragon.to_ship_dict(name="d", player=1, upgrades=ups)
    kinds = {w["weapon_type"]: w for w in d["weapons"]}
    assert kinds["lance"]["pulsar"] and kinds["lance"]["strength"] == 3
    assert "vampire_assault_boat" in kinds["launch_bay"]["craft_types"]
    assert d["points_value"] == 280
    g = _e("Ghost Wraith (Ghostship)").to_ship_dict(
        name="g", player=1, upgrades=["Prow Pulsar Lance FP2 + Keel Battery FP4"])
    assert sorted(w["strength"] for w in g["weapons"]) == [2, 4]
    s = _e("Shadowhunter Class Destroyer").to_ship_dict(
        name="s", player=1, upgrades=["Prow: Phantom Lance FP1"])
    assert s["weapons"][0]["phantom"]


def test_ghostship_rules():
    gs = make_gs()
    gs.rule_hit_and_run = gs.rule_teleport = True
    ghost = make_ship(special_rules=["ghostship", "fragile"])
    assert _get_ship_modifier(ghost, gs) == 1           # enemy boarding +1
    assert _raid_roll_modifier([], ghost) == 1          # enemy raids +1
    ok, why = check_teleport_eligibility(ghost, make_ship(id="t", player=2), gs)
    assert not ok and "Ghostship" in why


def test_shadowhunter_hits_ordnance_on_4plus():
    gs = make_gs()
    gs.ordnance = [{"id": "m1", "ordnance_type": "torpedo", "x": 20, "y": 0, "owner_player": 2,
                    "strength": 2, "heading": 180}]
    sh = make_ship(id="s", x=0, y=0, heading=0, special_rules=["ordnance_shots_4plus"])
    w = {"name": "Prow Phantom Lance", "weapon_type": "lance", "range_cm": 30,
         "strength": 1, "arcs": ["front"]}
    dice = DiceStub([4])
    out = fire_at_ordnance(sh, w, "m1", gs, dice, 1)
    assert out["hits"] == 1 and dice._idx == 1
