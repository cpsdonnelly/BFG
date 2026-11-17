"""Fixes from the code review (CLAUDE.md To do 15)."""
from src.hit_and_run import _apply_raid_crit, raid_crit_preview, describe_raid_result
from tests.conftest import DiceStub, make_gs, make_ship


def test_raid_crit_path_applies_bridge_smashed():
    # The raid / boarding crit path applies every crit effect, as roll_critical_hit does
    s = make_ship(leadership=8)
    gs = make_gs([s])
    crit = _apply_raid_crit(9, s, gs, DiceStub([]))
    assert crit["crit_type"] == "bridge_smashed"
    assert gs.get_ship_by_id("t1").leadership == 5


def test_necron_raid_crit_loses_leadership():
    # Necron Main Drive Damaged (6): -1 Ld each time (Xenos p.41)
    s = make_ship(leadership=9, special_rules=["necron"])
    gs = make_gs([s])
    crit = _apply_raid_crit(6, s, gs, DiceStub([]))
    assert crit["crit_type"] == "main_drive"
    assert gs.get_ship_by_id("t1").leadership == 8


def test_raid_preview_uses_the_targets_own_table():
    eldar = make_ship(special_rules=["eldar_mms"])
    assert raid_crit_preview(2, eldar) == "infinity_circuit"
    assert describe_raid_result(2, eldar) == "critical hit: Infinity Circuit Damaged"
    necron = make_ship(special_rules=["necron"])
    assert raid_crit_preview(6, necron) == "main_drive"


def test_sunward_change_reaches_eldar_speeds():
    from src import eldar
    from src.optional_rules import set_sunward
    set_sunward(False, "south")
    assert eldar.sunward_edge() == "south"
    set_sunward(True, "north")
    assert eldar.sunward_edge() == "north"


def test_marker_ids_are_unique_serials():
    gs = make_gs([])
    a, b = gs.next_serial(), gs.next_serial()
    assert a != b and b == a + 1


def test_prow_crit_cascades_past_a_dorsal_only_ship():
    # A dorsal L/F/R weapon isn't a prow weapon: the prow crit would disable
    # nothing, so it cascades (it used to land and do nothing)
    s = make_ship(weapons=[{"name": "Dorsal Lances", "weapon_type": "lance", "strength": 2,
                            "arcs": ["left", "front", "right"]}])
    assert not s.has_armament_slot("prow_armament")
    assert s.has_armament_slot("dorsal_armament")
    p = make_ship(weapons=[{"name": "Prow Torpedoes", "weapon_type": "torpedo", "strength": 6,
                            "arcs": ["front"]}])
    assert p.has_armament_slot("prow_armament")


def test_save_load_round_trip_keeps_every_field(tmp_path):
    from dataclasses import fields
    from src.game_state import GameState
    gs = make_gs([make_ship()])
    gs.id_serial, gs.scenario_mode, gs.kill_credit = 7, "domination", [{"by": "a"}]
    gs.save(str(tmp_path))
    back = GameState.load(str(tmp_path))
    for f in fields(GameState):
        if f.name not in ("log",):
            assert getattr(back, f.name) == getattr(gs, f.name), f.name


def test_transient_scratch_cleared_on_restore():
    gs = make_gs([])
    gs.__dict__["_zzapp_blast"] = {(1, "x")}
    gs.brace_hook = print
    gs.clear_transient()
    assert "_zzapp_blast" not in vars(gs) and gs.brace_hook is print


def test_expected_hits_over_a_random_firepower():
    from src.combat import expected_hits, dice_distribution, dice_value_mean
    from src.tables import lookup_gunnery_dice, get_gunnery_column
    assert dice_value_mean("D6+1") == 4.5
    assert abs(sum(p for _v, p in dice_distribution("2D6")) - 1.0) < 1e-9
    a = make_ship(id="a", player=1, x=0, y=0, heading=0)
    t = make_ship(id="b", player=2, x=20, y=0, heading=180)      # closing, 6+ prow facing a
    gun = {"name": "Gunz", "weapon_type": "battery", "strength": 4, "strength_dice": "D6+1",
           "arcs": ["front"], "range": 30}
    want = sum(lookup_gunnery_dice(v, get_gunnery_column("capital", "closing"), 0)
               for v in range(2, 8)) / 6 * (7 - t.armor_vs(0, 0)) / 6
    assert abs(expected_hits(a, gun, t) - want) < 1e-9
    lance = {"name": "Zzapp", "weapon_type": "lance", "strength": 2, "strength_dice": "D3",
             "hits_on": 5, "arcs": ["front"], "range": 30}
    assert abs(expected_hits(a, lance, t) - 2.0 * 2 / 6) < 1e-9


def test_crit_on_4_weapons_worth_more_as_targets_choice():
    from src.ai_hazards import shot_vp
    a = make_ship(id="a", player=1, x=0, y=0, heading=0)
    t = make_ship(id="b", player=2, x=20, y=0, heading=90, shields_max=0, points_value=180)
    gs = make_gs([a, t])
    plain = {"name": "Batteries", "weapon_type": "battery", "strength": 6, "arcs": ["front"],
             "range": 30, "hits_on": 4}
    bc = dict(plain, name="Bombardment Cannon", crit_on=4)
    assert shot_vp(a, bc, t, gs) > shot_vp(a, plain, t, gs)


def test_meteor_storm_wreck_rolls_catastrophic_after_deployment():
    # After deployment every ship is on the table, so the blast reaches them all
    from src.subplots import deployed_wrecks, WRECK_RULE
    wreck = make_ship(id="w", hits_remaining=0, x=50, y=50, special_rules=[WRECK_RULE])
    a = make_ship(id="a", player=2, x=55, y=50)
    b = make_ship(id="b", player=2, x=52, y=50)
    gs = make_gs([wreck, a, b])
    # 2D6 = 12: a warp drive implosion, then its radius and the blast's rolls
    dice = DiceStub([12] + [4] * 33)
    res = deployed_wrecks(gs, dice)
    assert res == ["warp_drive_implosion"] and dice._idx == 34
    assert WRECK_RULE not in gs.get_ship_by_id("w").special_rules
    assert gs.get_ship_by_id("a").hits_remaining < gs.get_ship_by_id("a").hits_max
    assert gs.get_ship_by_id("b").hits_remaining < gs.get_ship_by_id("b").hits_max
    assert deployed_wrecks(gs, DiceStub([])) == []      # rolled once only
