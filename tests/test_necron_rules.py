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
    generators and portals as their own weapon types. Still unsupported."""
    from src.ship_catalog import find_ship_class
    e = find_ship_class("Scythe Class Harvest Ship")
    d = e.to_ship_dict("s", 1)
    assert d["shields_max"] == 0 and {"necron", "reactive_hull:5"} <= set(d["special_rules"])
    kinds = {w["name"]: w for w in d["weapons"]}
    assert kinds["Lightning Arc"]["weapon_type"] == "battery" and kinds["Lightning Arc"]["lightning_arc"]
    assert kinds["Particle Whip"]["weapon_type"] == "lance" and kinds["Particle Whip"]["particle_whip"]
    assert kinds["Star Pulse Generator"]["weapon_type"] == "star_pulse"
    assert kinds["Portals"]["weapon_type"] == "portal" and kinds["Portals"]["strength"] == 3
    assert any("Necron rules" in u for u in e.unsupported)


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
