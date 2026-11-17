"""Ork Gunz are macrobatteries; Heavy Gunz use their bracketed firepower
within 15cm (Ork faction rules)."""
from tests.conftest import make_ship, DiceStub
from src.combat import effective_battery_firepower, resolve_batteries
from src.ship_catalog import find_ship_class
from src.tables import lookup_gunnery_dice, get_gunnery_column

HEAVY = {"name": "Heavy Gunz", "weapon_type": "battery", "strength": 6,
         "strength_close": 10, "range_cm": 30, "arcs": ["front", "left", "right"]}


def test_catalog_gunz_are_batteries():
    grunt = find_ship_class("Grunt Assault Ship")
    assert grunt.playable
    assert [(w["name"], w["weapon_type"], w["strength"]) for w in grunt.weapons] == [
        ("Gunz", "battery", 2)]


def test_catalog_heavy_gunz_keep_both_values():
    savage = find_ship_class("Savage Gunship")
    assert savage.playable
    w = savage.weapons[0]
    assert (w["weapon_type"], w["strength"], w["strength_close"]) == ("battery", 2, 6)


def _pair(dist):
    attacker = make_ship(id="a", player=1, x=0.0, y=0.0, heading=0.0, weapons=[HEAVY])
    target = make_ship(id="t", player=2, x=dist, y=0.0, heading=90.0)
    return attacker, target


def test_heavy_gunz_firepower_by_range():
    a, near = _pair(14.0)
    assert effective_battery_firepower(a, HEAVY, near) == 10
    a, far = _pair(15.0)
    assert effective_battery_firepower(a, HEAVY, far) == 6
    assert effective_battery_firepower(a, HEAVY) == 6      # no target: printed value


def test_heavy_gunz_close_value_is_halved_like_any_firepower():
    a, near = _pair(10.0)
    a.special_order = "brace_for_impact"
    assert effective_battery_firepower(a, HEAVY, near) == 5


def test_heavy_gunz_roll_close_firepower_within_15cm():
    a, near = _pair(10.0)
    col = get_gunnery_column("capital", a.get_target_orientation(near))
    n = lookup_gunnery_dice(10, col, -1)          # FP10, <15cm left shift
    rolls = [1] * n
    dice = DiceStub(rolls)
    r = resolve_batteries(a, near, HEAVY, dice, [])
    assert dice._idx == n and len(r.dice_rolled) == n


# ── Owner ruling: splitting Heavy Gunz shares the worse firepower ────────────
from src.combat import (weapon_fire_pool, shot_weapon, roll_dice_value,
                        dice_value_average, is_dice_value)


def test_heavy_gunz_first_shot_fixes_pool_by_range():
    a, near = _pair(10.0)
    assert weapon_fire_pool(a, HEAVY, 0, 10.0, DiceStub([1])) == (10, "close", None)
    assert weapon_fire_pool(a, HEAVY, 0, 20.0, DiceStub([1])) == (6, "long", None)


def test_heavy_gunz_split_far_first_shares_the_long_value():
    a, _ = _pair(10.0)
    a.weapons_remaining = {"0": 3}            # fired 3 of 6 at a far target
    a.weapon_pool_mode = {"0": "long"}
    assert weapon_fire_pool(a, HEAVY, 0, 10.0, DiceStub([1])) == (3, "long", None)


def test_heavy_gunz_split_near_first_cannot_then_fire_far():
    a, _ = _pair(10.0)
    a.weapons_remaining = {"0": 5}            # fired 5 of 10 at a near target
    a.weapon_pool_mode = {"0": "close"}
    pool, mode, err = weapon_fire_pool(a, HEAVY, 0, 20.0, DiceStub([1]))
    assert pool == 0 and "far target first" in err
    assert weapon_fire_pool(a, HEAVY, 0, 12.0, DiceStub([1])) == (5, "close", None)


def test_shot_weapon_fixes_strength():
    w = shot_weapon(HEAVY, 4)
    assert w["strength"] == 4 and "strength_close" not in w


# ── Owner ruling: random Ork values are rolled when used ─────────────────────
GUNZ_D6 = {"name": "Gunz", "weapon_type": "battery", "strength": 4,
           "strength_dice": "D6+1", "range_cm": 30, "arcs": ["front"]}


def test_dice_values():
    assert is_dice_value("D6+1") and is_dice_value("2D6+6") and is_dice_value("D3+3")
    assert not is_dice_value("6(10)") and not is_dice_value("6")
    assert dice_value_average("D6+1") == 4 and dice_value_average("2D6") == 7
    rolls = [5]
    dice = DiceStub(rolls)
    assert roll_dice_value("D6+1", dice) == 6 and dice._idx == 1
    dice = DiceStub([4, 2])
    assert roll_dice_value("2D6+6", dice) == 12 and dice._idx == 2
    dice = DiceStub([3])
    assert roll_dice_value("D3+1", dice) == 4 and dice._idx == 1


def test_random_firepower_rolled_on_first_shot_then_split_from_what_rolled():
    a, near = _pair(10.0)
    rolls = [3]
    dice = DiceStub(rolls)
    assert weapon_fire_pool(a, GUNZ_D6, 0, 20.0, dice) == (4, None, None)
    assert dice._idx == len(rolls)
    a.weapons_remaining = {"0": 2}            # 2 of the rolled 4 left: no new roll
    dice = DiceStub([6])
    assert weapon_fire_pool(a, GUNZ_D6, 0, 20.0, dice) == (2, None, None)
    assert dice._idx == 0


def test_catalog_random_values():
    ons = find_ship_class("Onslaught Attack Ship")
    assert ons.playable and ons.weapons[0]["strength_dice"] == "D6+1"
    rav = find_ship_class("Ravager Attack Ship")
    torps = [w for w in rav.weapons if w["weapon_type"] == "torpedo"][0]
    assert rav.playable and torps["strength_dice"] == "D6"


def test_random_torpedo_strength_rolled_at_launch_then_halved():
    from src.ordnance import launch_torpedoes, torpedo_launch_strength
    from tests.conftest import make_gs
    torps = {"name": "Torps", "weapon_type": "torpedo", "strength": 3,
             "strength_dice": "D6", "torpedo_type": "standard", "torpedo_speed": 30}
    ship = make_ship(id="r", player=1, x=50.0, y=50.0, weapons=[torps])
    assert torpedo_launch_strength(ship, torps, DiceStub([5])) == (5, 5)
    ship.special_order = "brace_for_impact"
    assert torpedo_launch_strength(ship, torps, DiceStub([5])) == (3, 5)
    ship.special_order = "none"
    gs = make_gs([ship])
    rolls = [6]
    dice = DiceStub(rolls)
    m = launch_torpedoes(ship, torps, gs, dice=dice)
    assert m.strength == 6 and dice._idx == len(rolls)
