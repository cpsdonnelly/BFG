"""Tests for ordnance utility functions in src/ordnance.py."""
from tests.conftest import make_ship, make_gs, make_marker, make_phenomenon, DiceStub
from src.ordnance import (resolve_mine_contact, check_ordnance_vs_phenomena,
                          compute_torpedo_launch_exempt, launch_torpedoes,
                          launch_attack_craft, reload_ship_ordnance)
from src.models import OrdnanceMarker


# ── resolve_mine_contact ──────────────────────────────────────────────────────

def test_mine_turret_success_reduces_to_4d6():
    # Target has 2 turrets; DiceStub gives [4,1] → one 4+ → reduces to 4D6
    # Then 4 attack rolls: [5,5,5,5] → armor 5+ → 4 hits
    target = make_ship(id="t", x=0, y=0, heading=0, turrets=2,
                       armor_prow="5+", armor_side="5+", shields_max=0,
                       hits_max=8)
    mine = make_marker(ordnance_type="mine_field", x=10, y=0)
    gs = make_gs([target])
    dice = DiceStub([4, 1, 5, 5, 5, 5])  # turret rolls then attack rolls
    r = resolve_mine_contact(mine, target, dice, gs)
    assert r["attack_dice"] == 4
    assert r["hits"] == 4


def test_mine_turret_failure_keeps_8d6():
    # Turrets roll all miss, so mine attacks with full 8D6
    target = make_ship(id="t", x=0, y=0, heading=0, turrets=2,
                       armor_prow="5+", armor_side="5+", shields_max=0,
                       hits_max=8)
    mine = make_marker(ordnance_type="mine_field", x=10, y=0)
    gs = make_gs([target])
    # 2 turret rolls fail, then 8 attack rolls (all miss)
    dice = DiceStub([1, 2, 1, 1, 1, 1, 1, 1, 1, 1])
    r = resolve_mine_contact(mine, target, dice, gs)
    assert r["attack_dice"] == 8
    assert r["hits"] == 0


def test_mine_no_turrets_uses_8d6():
    target = make_ship(id="t", x=0, y=0, heading=0, turrets=0,
                       armor_prow="5+", armor_side="5+", shields_max=0,
                       hits_max=8)
    mine = make_marker(ordnance_type="mine_field", x=10, y=0)
    gs = make_gs([target])
    dice = DiceStub([5, 5, 5, 5, 5, 5, 5, 5])
    r = resolve_mine_contact(mine, target, dice, gs)
    assert r["attack_dice"] == 8
    assert r["hits"] == 8


def test_mine_hits_ignore_shields():
    # Core rules s.14: mines ignore shields
    target = make_ship(id="t", x=0, y=0, heading=0, turrets=0,
                       armor_prow="5+", armor_side="5+",
                       shields_max=2, hits_max=12)
    mine = make_marker(ordnance_type="mine_field", x=10, y=0)
    gs = make_gs([target])
    rolls = [5] * 8 + [1] * 8     # 8D6 all hit at 5+; 8 hull hits, 8 crit checks
    dice = DiceStub(rolls)
    r = resolve_mine_contact(mine, target, dice, gs)
    assert r["hits"] == 8
    assert dice._idx == len(rolls)
    assert gs.get_ship_by_id("t").hits_remaining == 4    # all 8 to the hull
    assert gs.get_blast_markers() == []                 # no shield impacts


# ── check_ordnance_vs_phenomena ───────────────────────────────────────────────

def test_torp_in_asteroid_field_auto_destroyed():
    marker = make_marker(ordnance_type="torpedo_standard", x=50, y=0)
    p = make_phenomenon("asteroid_field", x=50, y=0, width=20, height=20, radius=0)
    dice = DiceStub([1])
    destroyed, reason = check_ordnance_vs_phenomena(marker, [p], dice)
    assert destroyed is True
    assert reason == "asteroid_field"


def test_torp_in_warp_rift_auto_destroyed():
    marker = make_marker(ordnance_type="torpedo_standard", x=50, y=0)
    p = make_phenomenon("warp_rift", x=50, y=0, width=20, height=20, radius=0)
    dice = DiceStub([1])
    destroyed, _ = check_ordnance_vs_phenomena(marker, [p], dice)
    assert destroyed is True


def test_torp_in_planet_auto_destroyed():
    marker = make_marker(ordnance_type="torpedo_standard", x=50, y=0)
    p = make_phenomenon("planet_small", x=50, y=0, radius=20)
    dice = DiceStub([1])
    destroyed, _ = check_ordnance_vs_phenomena(marker, [p], dice)
    assert destroyed is True


def test_torp_clear_of_phenomena_not_destroyed():
    marker = make_marker(ordnance_type="torpedo_standard", x=0, y=0)
    p = make_phenomenon("asteroid_field", x=100, y=100, width=20, height=20, radius=0)
    dice = DiceStub([1])
    destroyed, _ = check_ordnance_vs_phenomena(marker, [p], dice)
    assert destroyed is False


def test_craft_in_asteroid_on_6_destroyed():
    marker = make_marker(ordnance_type="fighter", x=50, y=0)
    p = make_phenomenon("asteroid_field", x=50, y=0, width=20, height=20, radius=0)
    destroyed, _ = check_ordnance_vs_phenomena(marker, [p], DiceStub([6]))
    assert destroyed is True


def test_craft_in_asteroid_not_on_6_survives():
    marker = make_marker(ordnance_type="fighter", x=50, y=0)
    p = make_phenomenon("asteroid_field", x=50, y=0, width=20, height=20, radius=0)
    destroyed, _ = check_ordnance_vs_phenomena(marker, [p], DiceStub([5]))
    assert destroyed is False


def test_craft_in_warp_rift_auto_destroyed():
    marker = make_marker(ordnance_type="bomber", x=50, y=0)
    p = make_phenomenon("warp_rift", x=50, y=0, width=20, height=20, radius=0)
    destroyed, _ = check_ordnance_vs_phenomena(marker, [p], DiceStub([1]))
    assert destroyed is True


# ── compute_torpedo_launch_exempt ─────────────────────────────────────────────

def test_launcher_always_exempt():
    launcher = make_ship(id="launcher", x=50, y=50, player=1)
    gs = make_gs([launcher])
    exempt = compute_torpedo_launch_exempt(launcher, gs)
    assert "launcher" in exempt


def test_nearby_friendly_ship_not_exempt_individual_launch():
    # Individual launches only exempt the launcher itself.
    # Combined squadron launches (handled by the ordnance panel) exempt the whole group.
    launcher = make_ship(id="launcher", x=50, y=50, player=1, base_size="small")
    ally = make_ship(id="ally", x=52, y=50, player=1, base_size="small")
    gs = make_gs([launcher, ally])
    exempt = compute_torpedo_launch_exempt(launcher, gs)
    assert "ally" not in exempt
    assert "launcher" in exempt


def test_enemy_ship_not_exempt():
    launcher = make_ship(id="launcher", x=50, y=50, player=1)
    enemy = make_ship(id="enemy", x=52, y=50, player=2)
    gs = make_gs([launcher, enemy])
    exempt = compute_torpedo_launch_exempt(launcher, gs)
    assert "enemy" not in exempt


# ── launch_torpedoes ──────────────────────────────────────────────────────────

def test_launch_torpedoes_creates_marker():
    ship = make_ship(id="s", x=50, y=50, heading=0, player=1)
    gs = make_gs([ship])
    weapon = {"strength": 6, "torpedo_type": "standard", "torpedo_speed": 30}
    marker = launch_torpedoes(ship, weapon, gs)
    assert marker.ordnance_type == "torpedo_standard"
    assert marker.strength == 6
    assert len(gs.ordnance) == 1


def test_launch_guided_torpedo_creates_guided_marker():
    ship = make_ship(id="s", x=50, y=50, heading=0, player=1)
    gs = make_gs([ship])
    weapon = {"strength": 4, "torpedo_type": "guided", "torpedo_speed": 20}
    marker = launch_torpedoes(ship, weapon, gs)
    assert marker.ordnance_type == "torpedo_guided"
    assert marker.can_turn is True


def test_launch_torpedoes_default_heading_is_ship_heading():
    ship = make_ship(id="s", x=50, y=50, heading=30, player=1)
    gs = make_gs([ship])
    weapon = {"strength": 6, "torpedo_type": "standard", "torpedo_speed": 30}
    marker = launch_torpedoes(ship, weapon, gs)
    assert marker.heading == 30


def test_launch_torpedoes_aim_heading_within_arc_is_honored():
    ship = make_ship(id="s", x=50, y=50, heading=0, player=1)
    gs = make_gs([ship])
    weapon = {"strength": 6, "torpedo_type": "standard", "torpedo_speed": 30}
    marker = launch_torpedoes(ship, weapon, gs, heading=30)
    assert marker.heading == 30


def test_launch_torpedoes_aim_heading_clamped_to_forward_arc():
    ship = make_ship(id="s", x=50, y=50, heading=0, player=1)
    gs = make_gs([ship])
    weapon = {"strength": 6, "torpedo_type": "standard", "torpedo_speed": 30}
    # 90° is outside the ±45° forward arc → clamp to 45°
    marker = launch_torpedoes(ship, weapon, gs, heading=90)
    assert marker.heading == 45
    # Likewise -90° (i.e. 270°) clamps to -45° (i.e. 315°)
    marker2 = launch_torpedoes(ship, weapon, gs, heading=270)
    assert marker2.heading == 315


# ── launch_attack_craft ───────────────────────────────────────────────────────

def test_launch_attack_craft_creates_markers():
    ship = make_ship(id="s", x=50, y=50, heading=0, player=1)
    gs = make_gs([ship])
    weapon = {"name": "Launch Bay", "strength": 2}
    markers = launch_attack_craft(ship, weapon, "fury_fighter", 2, gs)
    assert len(markers) == 2
    for m in markers:
        assert m.ordnance_type == "fighter"


# ── reload_ship_ordnance ──────────────────────────────────────────────────────

def test_reload_sets_torps_when_ship_has_torpedoes():
    ship = make_ship(id="s", weapons=[{"name": "Torps", "weapon_type": "torpedo",
                                        "strength": 6}])
    ship.ordnance_loaded_torps = False
    logs = reload_ship_ordnance(ship)
    assert ship.ordnance_loaded_torps is True
    assert any("torpedoes" in line for line in logs)


def test_reload_sets_craft_when_ship_has_launch_bay():
    ship = make_ship(id="s", weapons=[{"name": "Bay", "weapon_type": "launch_bay",
                                       "strength": 2}])
    ship.ordnance_loaded_craft = False
    logs = reload_ship_ordnance(ship)
    assert ship.ordnance_loaded_craft is True
    assert any("attack craft" in line for line in logs)


def test_reload_sets_both_when_ship_has_both():
    ship = make_ship(id="s", weapons=[
        {"name": "Torps", "weapon_type": "torpedo", "strength": 6},
        {"name": "Bay", "weapon_type": "launch_bay", "strength": 2},
    ])
    ship.ordnance_loaded_torps = False
    ship.ordnance_loaded_craft = False
    logs = reload_ship_ordnance(ship)
    assert ship.ordnance_loaded_torps is True
    assert ship.ordnance_loaded_craft is True
    assert any("torpedoes" in line and "attack craft" in line for line in logs)


def test_reload_already_loaded_returns_already_loaded_log():
    ship = make_ship(id="s", weapons=[{"name": "Torps", "weapon_type": "torpedo",
                                       "strength": 6}])
    # default ordnance_loaded_torps is True
    logs = reload_ship_ordnance(ship)
    assert ship.ordnance_loaded_torps is True
    assert any("already loaded" in line for line in logs)


def test_reload_ship_without_ordnance_weapons_returns_empty():
    ship = make_ship(id="s", weapons=[{"name": "Battery", "weapon_type": "battery",
                                       "strength": 4}])
    ship.ordnance_loaded_torps = False
    ship.ordnance_loaded_craft = False
    logs = reload_ship_ordnance(ship)
    assert logs == []
    # Flags untouched (no ordnance weapons to reload)
    assert ship.ordnance_loaded_torps is False
    assert ship.ordnance_loaded_craft is False


def test_reload_only_sets_types_the_ship_has():
    # Torpedo-only ship: torps reload, craft flag left at its prior value
    ship = make_ship(id="s", weapons=[{"name": "Torps", "weapon_type": "torpedo",
                                       "strength": 6}])
    ship.ordnance_loaded_torps = False
    ship.ordnance_loaded_craft = False
    reload_ship_ordnance(ship)
    assert ship.ordnance_loaded_torps is True
    assert ship.ordnance_loaded_craft is False  # no launch bay → unchanged


def test_launch_shark_assault_boats_creates_assault_boats():
    # Imperial Navy: Shark assault boats (AB, 30cm)
    ship = make_ship(id="s", x=50, y=50, heading=0, player=1)
    gs = make_gs([ship])
    weapon = {"name": "Port Launch Bays", "weapon_type": "launch_bay", "strength": 2}
    markers = launch_attack_craft(ship, weapon, "shark_assault_boat", 2, gs)
    assert [m.ordnance_type for m in markers] == ["assault_boat", "assault_boat"]
    assert all(m.speed == 30 for m in markers)


# ── Assault boats are not fighters: they never intercept other ordnance ─────

def _overlapping(gs, *markers):
    for m in markers:
        gs.add_ordnance(m)
    return gs


def test_assault_boat_does_not_intercept_an_enemy_torpedo():
    from src.ordnance import resolve_ordnance_interactions
    gs = _overlapping(
        make_gs([]),
        make_marker(id="ab", ordnance_type="assault_boat", owner_player=1,
                    x=50.0, y=50.0, strength=1, speed=30.0),
        make_marker(id="torp", ordnance_type="torpedo_standard", owner_player=2,
                    x=50.0, y=50.0),
    )
    dice = DiceStub([1])
    resolve_ordnance_interactions(gs, dice)
    assert sorted(o["id"] for o in gs.ordnance) == ["ab", "torp"]
    assert dice._idx == 0


def test_assault_boat_does_not_intercept_an_enemy_bomber():
    from src.ordnance import resolve_ordnance_interactions
    gs = _overlapping(
        make_gs([]),
        make_marker(id="ab", ordnance_type="assault_boat", owner_player=1,
                    x=50.0, y=50.0, strength=1, speed=30.0),
        make_marker(id="bmr", ordnance_type="bomber", owner_player=2,
                    x=50.0, y=50.0, strength=1, speed=20.0),
    )
    dice = DiceStub([1])
    resolve_ordnance_interactions(gs, dice)
    assert sorted(o["id"] for o in gs.ordnance) == ["ab", "bmr"]
    assert dice._idx == 0


def test_fighter_still_intercepts_an_assault_boat():
    from src.ordnance import resolve_ordnance_interactions
    gs = _overlapping(
        make_gs([]),
        make_marker(id="ab", ordnance_type="assault_boat", owner_player=1,
                    x=50.0, y=50.0, strength=1, speed=30.0),
        make_marker(id="ftr", ordnance_type="fighter", owner_player=2,
                    x=50.0, y=50.0, strength=1, speed=30.0),
    )
    resolve_ordnance_interactions(gs, DiceStub([1]))
    assert "ab" not in [o["id"] for o in gs.ordnance]


def test_generic_attack_craft_use_the_ships_booklet_speed():
    ship = make_ship(id="s", x=50, y=50, heading=0, player=1)
    gs = make_gs([ship])
    bay = {"name": "Port Launch Bays", "weapon_type": "launch_bay", "strength": 2,
           "craft_types": ["fighter", "bomber"], "craft_speeds": {"fighter": 30, "bomber": 20}}
    fighters = launch_attack_craft(ship, bay, "fighter", 1, gs)
    bombers = launch_attack_craft(ship, bay, "bomber", 1, gs)
    assert (fighters[0].ordnance_type, fighters[0].speed) == ("fighter", 30)
    assert (bombers[0].ordnance_type, bombers[0].speed) == ("bomber", 20)


def test_mines_reload_separately_from_attack_craft():
    # s.12: launching one type of ordnance does not affect the other
    ship = make_ship(id="s", weapons=[
        {"name": "Bay", "weapon_type": "launch_bay", "strength": 2},
        {"name": "Mines", "weapon_type": "mine_launcher", "strength": 2},
    ])
    ship.ordnance_loaded_mines = False          # laid mines; craft still loaded
    assert ship.ordnance_loaded_craft is True
    logs = reload_ship_ordnance(ship)
    assert ship.ordnance_loaded_mines is True and "mines" in logs[0]
