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
    assert port > 0 and stbd == 0
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
    # Friend ahead, 60cm away: after the target's 20cm move only the 60cm dorsal
    # lances can reach (prow lance 30 + 20 = 50cm)
    target, gs = _setup(friend_xy=(60.0, 0.0))
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


def test_port_disable_rerolled_when_no_ally_threatened():
    # Friend in the port arc but beyond the 45cm battery + the target's 20cm move
    target, gs = _setup(friend_xy=(0.0, 70.0))
    assert raid_result_value(4, target, gs, 1) == 0.0
    assert best_raid_reroll(4, 4, target, gs, 1) is True
    # Friend in range but in the starboard arc: the port disable threatens nothing
    target, gs = _setup(friend_xy=(0.0, -20.0))
    assert raid_result_value(4, target, gs, 1) == 0.0
    assert best_raid_reroll(4, 4, target, gs, 1) is True
    assert best_raid_reroll(3, 3, target, gs, 1) is False      # starboard bears: keep


def test_next_shooting_phase_reach_and_repairs():
    from src.hit_and_run import p_crit_unrepaired
    # 50cm away in the port arc: out of range now, within reach after the
    # target's 20cm move, so the port disable is worth something
    target, gs = _setup(friend_xy=(0.0, 50.0))
    gs.active_player = 1                       # raid lands in the raider's turn
    v1 = raid_result_value(4, target, gs, 1)
    assert v1 > 0 and best_raid_reroll(4, 4, target, gs, 1) is False
    # Damage control: 8 hits, one crit -> (5/6)^8 survives one end phase
    assert abs(p_crit_unrepaired(target, gs, 1) - (5 / 6) ** 8) < 1e-9
    # Landing in the target's own turn: two end phases before it shoots again
    gs.active_player = 2
    v2 = raid_result_value(4, target, gs, 1)
    assert 0 < v2 < v1
    assert abs(p_crit_unrepaired(target, gs, 2) - ((5 / 6) ** 8) ** 2) < 1e-9


def test_repairs_halved_by_blast_markers():
    from tests.conftest import make_blast
    from src.hit_and_run import p_crit_unrepaired
    target, gs = _setup()
    clear = p_crit_unrepaired(target, gs, 1)
    gs.add_blast_marker(make_blast(x=target.x, y=target.y))
    assert abs(p_crit_unrepaired(target, gs, 1) - (5 / 6) ** 4) < 1e-9 and clear < (5 / 6) ** 4
