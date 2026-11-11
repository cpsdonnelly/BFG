"""Wings of Fury re-rolls by expected value (owner guidance) and armament
criticals silencing weapons for the AI."""
from tests.conftest import make_ship, make_gs
from src.hit_and_run import best_raid_reroll, raid_result_value, raid_crit_preview
from src.combat import weapon_disabled_by_crit

PORT = {"name": "Port Weapons Battery", "weapon_type": "battery", "range_cm": 45,
        "strength": 6, "arcs": ["left"]}
STBD = {"name": "Starboard Weapons Battery", "weapon_type": "battery", "range_cm": 45,
        "strength": 6, "arcs": ["right"]}
PROW = {"name": "Prow Lance", "weapon_type": "lance", "range_cm": 30,
        "strength": 2, "arcs": ["front"]}
DORSAL = {"name": "Dorsal Lances", "weapon_type": "lance", "range_cm": 60,
          "strength": 2, "arcs": ["left", "front", "right"]}


def _setup(friend_xy=(0.0, 20.0), weapons=None):
    target = make_ship(id="t", player=2, points_value=180,
                       weapons=weapons or [dict(PORT), dict(STBD), dict(PROW), dict(DORSAL)])
    friend = make_ship(id="f", player=1, points_value=200, x=friend_xy[0], y=friend_xy[1])
    return target, make_gs([target, friend])


def test_escorts_space_marines_reroll_1_and_2_only():
    esc = make_ship(id="e", player=2, ship_type="escort", hits_max=1, points_value=40)
    gs = make_gs([esc])
    for roll, want in ((1, True), (2, True), (3, False), (5, False)):
        assert best_raid_reroll(roll, roll + 1, esc, gs, owner=1) is want, roll


def test_armament_crit_valued_by_what_bears_on_friends():
    target, gs = _setup()                         # friend in the target's port arc only
    assert raid_crit_preview(3, target) == "starboard_armament"
    assert raid_crit_preview(4, target) == "port_armament"
    port = raid_result_value(4, target, gs, 1)
    stbd = raid_result_value(3, target, gs, 1)
    assert port > 3 * stbd
    assert best_raid_reroll(3, 3, target, gs, 1) is True      # starboard faces nothing
    assert best_raid_reroll(4, 4, target, gs, 1) is False     # port bears on the friend


def test_engine_room_kept_and_ablative_prow_rerolled():
    target, gs = _setup()
    assert raid_crit_preview(6, target) == "engine_room"
    assert best_raid_reroll(6, 6, target, gs, 1) is False
    target.special_rules.append("ablative_prow_armor")
    assert raid_result_value(5, target, gs, 1) == 0.0          # prow crit absorbed
    assert best_raid_reroll(5, 5, target, gs, 1) is True


def test_already_disabled_location_is_worth_nothing():
    target, gs = _setup()
    target.critical_damage.append({"crit_type": "port_armament", "repairable": True})
    assert raid_result_value(4, target, gs, 1) == 0.0
    assert best_raid_reroll(4, 4, target, gs, 1) is True


def test_long_heavy_weapons_worth_more():
    # Friend ahead, 50cm away: only the 60cm dorsal lances reach in arc
    target, gs = _setup(friend_xy=(50.0, 0.0))
    assert raid_result_value(2, target, gs, 1) > raid_result_value(5, target, gs, 1)


def test_weapon_disabled_by_crit_names_and_arcs():
    s = make_ship(critical_damage=[{"crit_type": "port_armament"}])
    assert weapon_disabled_by_crit(s, PORT) and not weapon_disabled_by_crit(s, STBD)
    assert weapon_disabled_by_crit(s, {"name": "Gunz", "arcs": ["left"]})
    s.critical_damage = [{"crit_type": "prow_armament"}]
    assert weapon_disabled_by_crit(s, {"name": "Torpedoes", "arcs": ["front"]})
    assert not weapon_disabled_by_crit(s, DORSAL)
    s.critical_damage = [{"crit_type": "dorsal_armament"}]
    assert weapon_disabled_by_crit(s, {"name": "Lances", "arcs": ["left", "front", "right"]})
