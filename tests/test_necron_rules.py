"""Necron first slice (To do 14; bfgxr/rules/09_necrons.md)."""
from types import SimpleNamespace

from tests.conftest import DiceStub
from src import necrons


def test_reactive_hulls_and_brace():
    assert necrons.parse_reactive_hull("RH 4+") == 4 and necrons.parse_reactive_hull("2") is None
    assert necrons.hull_save(5, braced=False) == 5 and necrons.hull_save(5, braced=True) == 2
    assert necrons.armour_when_braced(6, True) == 4 and necrons.armour_when_braced(6, False) == 6
    assert not necrons.order_allowed("reload_ordnance")
    assert necrons.order_allowed("reload_ordnance", tomb_complex=True)


def test_alert_levels_and_awakening():
    assert necrons.starting_alert(1500, 1000) == 3
    assert necrons.starting_alert(1000, 1000, hostile_specials=1) == 2
    a = necrons.AlertTracker(1)
    assert a.ld_required() == 10 and not a.may_awaken(9)
    a.unsaved_hit(2)
    assert a.ld_required() == 8 and a.may_awaken(8)
    a.unsaved_hit(5)
    assert a.level == 5 and a.may_awaken(1)
    cap = SimpleNamespace(special_rules=["necron"], ship_type="cruiser")
    esc = SimpleNamespace(special_rules=["necron"], ship_type="escort")
    assert necrons.conserving_power(cap) and not necrons.conserving_power(esc)
    cap.special_rules.append("necron_awake")
    assert not necrons.conserving_power(cap) and necrons.vp_multiplier(cap) == 2.0


def test_inertialess_drive_and_weapons():
    assert necrons.inertialess_extra(4) == 40 and necrons.inertialess_turns(45) == 2
    assert necrons.field_usable(False, "lock_on") and not necrons.field_usable(True, "")
    assert not necrons.field_usable(False, "all_ahead_full")
    dice = DiceStub([5, 4])
    assert necrons.nightmare_field(dice, 8) and dice._idx == 2       # 9 > Ld 8: failed
    dice = DiceStub([4, 3, 6])
    assert necrons.field_ordnance_kills(dice, ["a", "b", "c"], "x") == ["a", "c"]
    dice = DiceStub([6, 4])
    assert necrons.star_pulse_hits(dice, [6, 5]) == [True, False]
    dice = DiceStub([6, 4, 2])
    assert necrons.particle_whip(dice, 3) == (2, 1)
    assert necrons.portal_strength(3, 1) == 1 and necrons.portal_strength(4, 2) == 1


def test_necron_catalog():
    """Necron profiles read: no shields, the reactive hull save as a rule,
    lightning arcs (batteries) and particle whips (lances) flagged, star pulse
    generators and portals as their own weapon types."""
    from src.ship_catalog import find_ship_class
    e = find_ship_class("Scythe Class Harvest Ship")
    d = e.to_ship_dict("s", 1)
    assert d["shields_max"] == 0 and {"necron", "reactive_hull:5"} <= set(d["special_rules"])
    kinds = {w["name"]: w for w in d["weapons"]}
    assert kinds["Lightning Arc"]["weapon_type"] == "battery" and kinds["Lightning Arc"]["lightning_arc"]
    assert kinds["Particle Whip"]["weapon_type"] == "lance" and kinds["Particle Whip"]["particle_whip"]
    assert kinds["Star Pulse Generator"]["weapon_type"] == "star_pulse"
    assert kinds["Portals"]["weapon_type"] == "portal" and kinds["Portals"]["strength"] == 3
    assert not e.unsupported                                   # playable now


def test_reactive_hull_saves_and_braced_armour():
    from tests.conftest import make_ship
    from src.combat import apply_damage
    from src.game_state import GameState
    gs = GameState()
    t = make_ship(id="n", player=2, shields_max=0, hits_max=8,
                  special_rules=["necron", "reactive_hull:5"])
    gs.add_ship(t)
    # 3 hits: saves on 5+ (5, 2, 6) -> 1 hull hit, then its crit check (1)
    dice = DiceStub([5, 2, 6, 1])
    out = apply_damage(gs.get_ship_by_id("n"), 3, dice, gs)
    assert out["brace_saves"] == 2 and out["hull_hits"] == 1 and dice._idx == 4
    # braced: 2+ instead (2, 1) -> 1 hull hit, crit check (1); Armour drops to 4+
    dice = DiceStub([2, 1, 1])
    out = apply_damage(gs.get_ship_by_id("n"), 2, dice, gs, target_braced=True)
    assert out["brace_saves"] == 1 and dice._idx == 3
    n = gs.get_ship_by_id("n")
    assert n.armor_vs(n.x + 10, n.y) == 6
    n.special_order = "brace_for_impact"
    assert n.armor_vs(n.x + 10, n.y) == 4


def test_lightning_arcs_fire_as_against_closing_targets():
    from tests.conftest import make_ship
    from src.combat import _battery_orientation, get_column_shifts
    shooter = make_ship(id="s", player=1, x=0.0, y=0.0, heading=0.0)
    # a target to the side, moving away: abeam / moving away for ordinary batteries
    tgt = make_ship(id="t", player=2, x=20.0, y=0.0, heading=0.0, special_rules=["holofield"])
    arc = {"weapon_type": "battery", "lightning_arc": True}
    assert _battery_orientation(shooter, tgt, arc, "capital") == "closing"
    assert _battery_orientation(shooter, tgt, {"weapon_type": "battery"}, "capital") != "closing"
    assert _battery_orientation(shooter, tgt, arc, "defense") != "closing"
    # and they ignore the holofield's right shift
    assert get_column_shifts(shooter, tgt, [], weapon=arc) == \
        get_column_shifts(shooter, tgt, [], weapon={"weapon_type": "battery"}) - 1


def test_particle_whip_sixes_bypass_shields():
    from tests.conftest import make_ship
    from src.combat import resolve_lances, apply_damage
    from src.game_state import GameState
    gs = GameState()
    a = make_ship(id="a", player=1, x=0.0, y=0.0)
    t = make_ship(id="t", player=2, x=20.0, y=0.0, shields_max=2, hits_max=8)
    gs.add_ship(a); gs.add_ship(t)
    whip = {"name": "Particle Whip", "weapon_type": "lance", "strength": 3, "particle_whip": True}
    dice = DiceStub([6, 4, 1])
    sr = resolve_lances(a, gs.get_ship_by_id("t"), whip, dice)
    assert sr.hits == 2 and sr.bypass_hits == 1 and dice._idx == 3
    # 2 hits, 1 bypassing: the other goes into a shield; one hull hit, its crit check (1)
    dice = DiceStub([1])
    out = apply_damage(gs.get_ship_by_id("t"), sr.hits, dice, gs, bypass_hits=sr.bypass_hits)
    assert out["shield_hits"] == 1 and out["hull_hits"] == 1 and dice._idx == 1


def test_necron_critical_hits():
    from tests.conftest import make_ship, make_gs
    from src.combat import _resolve_crit_cascade, weapon_disabled_by_crit, roll_critical_hit
    from src.movement import get_max_turns
    from src.turn_controller import TurnController
    n = make_ship(id="n", player=1, leadership=8, speed=30,
                  special_rules=["necron", "reactive_hull:5", "necron_awake"])
    gs = make_gs([n])
    assert _resolve_crit_cascade(10, gs.get_ship_by_id("n"), gs)["crit_type"] == "command_core"
    s = gs.get_ship_by_id("n")
    dice = DiceStub([10])                             # 2D6 = 10: command core, -3 Ld
    roll_critical_hit(s, dice, gs)
    assert s.leadership == 5 and s.critical_damage[-1]["crit_type"] == "command_core"
    arc = {"name": "Lightning Arc", "weapon_type": "battery", "lightning_arc": True}
    whip = {"name": "Particle Whip", "weapon_type": "lance", "particle_whip": True}
    s = gs.get_ship_by_id("n")
    s.critical_damage = [{"crit_type": "main_capacitors"}]
    assert weapon_disabled_by_crit(s, arc) and not weapon_disabled_by_crit(s, whip)
    s.critical_damage = [{"crit_type": "power_flow"}]
    assert weapon_disabled_by_crit(s, arc) and weapon_disabled_by_crit(s, whip)
    s.critical_damage = [{"crit_type": "main_drive"}]
    assert get_max_turns("", s) == 0
    s.critical_damage = [{"crit_type": "impulse_power"}]
    assert s.effective_speed == 25
    s.critical_damage = [{"crit_type": "inertialess_drive"}]
    gs.update_ship(s)
    tc = TurnController(gs, DiceStub([]))
    assert "Inertialess" in tc.issue_special_order(gs.get_ship_by_id("n"), "all_ahead_full")["error"]
    assert "Reload" in tc.issue_special_order(gs.get_ship_by_id("n"), "reload_ordnance")["error"]


def test_necron_immunities_and_repairs():
    from tests.conftest import make_ship, make_gs
    from src.movement import blast_markers_to_slow, do_command_check, _blast_marker_damage
    from src.terrain_effects import resolve_gas_dust_contact
    from src.celestial import _immune
    from src.end_phase import get_repair_info
    n = make_ship(id="n", player=1, leadership=8, shields_max=0,
                  special_rules=["necron", "reactive_hull:5"])
    gs = make_gs([n])
    s = gs.get_ship_by_id("n")
    assert blast_markers_to_slow(s) > 100 and _immune(s)
    assert not _blast_marker_damage(s, gs, DiceStub([]))
    assert resolve_gas_dust_contact(s, DiceStub([]), gs)["speed_penalty"] == 0
    # Under Fire doesn't apply: 8 passes on Ld 8
    assert do_command_check(s, "lock_on", DiceStub([8]), in_blast=True, gs=gs)["passed"]
    # repairs on 4+: 8 hits -> 8 dice, two crits; 4 and 5 repair
    s.critical_damage = [{"crit_type": "main_drive", "repairable": True,
                          "description": "Main Drive Damaged"},
                         {"crit_type": "impulse_power", "repairable": True,
                          "description": "Impulse Power Disrupted"}]
    info = get_repair_info(s, DiceStub([4, 5, 1, 1, 1, 1, 1, 1]), gs)
    assert info["sixes"] == 2


def test_awakening_alert_and_double_vp():
    from tests.conftest import make_ship, make_gs
    from src.turn_controller import TurnController
    from src.combat import apply_damage
    from src.victory_points import calculate_victory_points as calculate_vp
    cap = make_ship(id="c", player=1, leadership=8, hits_max=8, points_value=275, shields_max=0,
                    special_rules=["necron", "reactive_hull:5"])
    esc = make_ship(id="e", player=1, ship_type="escort", hits_max=2, points_value=60,
                    special_rules=["necron", "reactive_hull:6"])
    foe = make_ship(id="f", player=2, points_value=300)
    gs = make_gs([cap, esc, foe])
    tc = TurnController(gs, DiceStub([]))
    assert gs.get_ship_by_id("c").is_crippled and not gs.get_ship_by_id("c").damage_crippled
    assert not gs.get_ship_by_id("e").is_crippled              # escorts never conserve power
    gs.active_player = 1
    tc._necron_awakening(1)
    # enemy has more points on the table (300 > 335? no): alert 1 -> Ld 10 needed
    assert gs.necron_alert["1"] == 1 and "necron_awake" not in gs.get_ship_by_id("c").special_rules
    # two unsaved hits (saves 1, 2 fail; crit checks 1, 1) raise the alert to 3: Ld 8+ awakens
    apply_damage(gs.get_ship_by_id("c"), 2, DiceStub([1, 2, 1, 1]), gs)
    assert gs.necron_alert["1"] == 3
    tc._necron_awakening(1)
    c = gs.get_ship_by_id("c")
    assert "necron_awake" in c.special_rules and not c.is_crippled
    c.hits_remaining = 0
    c.status = "destroyed"
    gs.update_ship(c)
    assert calculate_vp(gs)[2]["destroyed"] == 550             # awake: double


def test_without_a_trace_disengages_without_a_test():
    from tests.conftest import make_ship, make_gs
    from src.disengage import attempt_disengage, squadron_disengage_test
    n = make_ship(id="n", player=1, special_rules=["necron", "reactive_hull:5", "necron_awake"])
    e1 = make_ship(id="e1", player=1, ship_type="escort", squadron_id="q",
                   special_rules=["necron", "reactive_hull:6"])
    e2 = make_ship(id="e2", player=1, ship_type="escort", squadron_id="q",
                   special_rules=["necron", "reactive_hull:6"])
    gs = make_gs([n, e1, e2])
    dice = DiceStub([])
    assert attempt_disengage(gs.get_ship_by_id("n"), dice, gs)["success"] and dice._idx == 0
    assert gs.get_ship_by_id("n").is_disengaged
    r = squadron_disengage_test([gs.get_ship_by_id("e1"), gs.get_ship_by_id("e2")], dice, gs)
    assert r["success"] and dice._idx == 0


def test_inertialess_all_ahead_full():
    from tests.conftest import make_ship
    from src.movement import resolve_aaf_speed, validate_movement, MoveCommand
    n = make_ship(id="n", player=1, speed=25, heading=0.0, x=10.0, y=60.0,
                  special_rules=["necron", "reactive_hull:5", "necron_awake"])
    dice = DiceStub([4])
    assert resolve_aaf_speed(n, dice) == 40 and dice._idx == 1
    ok = [MoveCommand("forward", 20), MoveCommand("turn_left", 45), MoveCommand("forward", 20),
          MoveCommand("turn_right", 45), MoveCommand("forward", 25)]
    assert validate_movement(n, ok, "all_ahead_full", aaf_bonus=40,
                             table_width=180, table_height=120).valid
    early = [MoveCommand("forward", 10), MoveCommand("turn_left", 45),
             MoveCommand("forward", 55)]
    assert not validate_movement(n, early, "all_ahead_full", aaf_bonus=40,
                                 table_width=180, table_height=120).valid


def test_star_pulse_generator():
    from tests.conftest import make_ship, make_gs
    from src.combat import resolve_star_pulse
    from src.models import OrdnanceMarker
    n = make_ship(id="n", player=1, x=50.0, y=50.0,
                  special_rules=["necron", "reactive_hull:5", "necron_awake"])
    near = make_ship(id="a", player=2, x=60.0, y=50.0, shields_max=0, armor_side="5+",
                     armor_prow="5+")
    far = make_ship(id="b", player=2, x=100.0, y=50.0)
    gs = make_gs([n, near, far])
    gs.ordnance.append(OrdnanceMarker(id="t", ordnance_type="torpedo_standard", owner_player=2,
                                      launched_by="b", x=55.0, y=50.0).to_dict())
    # star pulse vs "a" (5+): 6 hits, crit check 1; ordnance 4+: 5 -> destroyed
    dice = DiceStub([6, 1, 5])
    out = resolve_star_pulse(gs.get_ship_by_id("n"), gs, dice)
    assert out["hits"] == {"a": 1} and out["ordnance_destroyed"] == 1 and dice._idx == 3
    assert gs.get_ship_by_id("a").hits_remaining == gs.get_ship_by_id("a").hits_max - 1
    sleepy = gs.get_ship_by_id("n")
    sleepy.special_rules = ["necron", "reactive_hull:5"]           # conserving power
    assert "error" in resolve_star_pulse(sleepy, gs, DiceStub([]))


def test_portals_raid_like_teleports():
    from tests.conftest import make_ship, make_gs_raids
    from src.hit_and_run import check_teleport_eligibility, portal_raid_count
    portal = {"name": "Portals", "weapon_type": "portal", "range_cm": 10, "strength": 3,
              "arcs": []}
    n = make_ship(id="n", player=1, x=50.0, y=50.0, hits_max=8, weapons=[dict(portal)],
                  special_rules=["necron", "reactive_hull:5", "necron_awake"])
    big = make_ship(id="b", player=2, x=58.0, y=50.0, hits_max=12, shields_max=0)
    gs = make_gs_raids([n, big])
    ok, why = check_teleport_eligibility(gs.get_ship_by_id("n"), gs.get_ship_by_id("b"), gs)
    assert ok, why                                          # more hits than us: allowed
    assert portal_raid_count(gs.get_ship_by_id("n")) == 3
    s = gs.get_ship_by_id("n")
    s.special_order = "all_ahead_full"                      # allowed, but halved down
    assert portal_raid_count(s) == 1
    s.special_rules = ["necron", "reactive_hull:5"]         # also conserving power: 0
    assert portal_raid_count(s) == 0
    far = make_ship(id="f", player=2, x=75.0, y=50.0, shields_max=0)
    gs.add_ship(far)
    assert not check_teleport_eligibility(gs.get_ship_by_id("n"), gs.get_ship_by_id("f"), gs)[0]
