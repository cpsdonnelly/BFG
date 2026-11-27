"""Dark Eldar, slice 2 (CLAUDE.md To do 19; bfgxr/rules/08_dark-eldar.md):
shadowfields (gunnery shift, tracking marks, saves vs lances / ordnance,
ramming, nova cannon), their gunnery left shift, phantom lances,
flickerfields, movement, Spectral Plating and the critical hits table."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.models import OrdnanceMarker, OrdnanceType, SpecialOrder
from src.combat import get_column_shifts, apply_damage, resolve_lances, ram_ld_dice
from src.dark_eldar import shadowfield_need
from src.ordnance import resolve_torpedo_attack, turret_hit_on
from src.movement import get_effective_speed, validate_movement, MoveCommand, do_command_check
from src.tables import crit_table_for, DARK_ELDAR_CRITICAL_HITS
from src.end_phase import remove_brace_orders, resolve_damage_control

DE = ["dark_eldar", "shadowfield"]


def _de(**kw):
    base = dict(id="de", player=2, x=0.0, y=40.0, heading=180.0, hits_max=6,
                shields_max=0, special_rules=list(DE), armor_prow="5+", armor_side="5+",
                armor_rear="5+", turrets=0)
    base.update(kw)
    return make_ship(**base)


def _gun(**kw):
    base = dict(id="g", player=1, x=0.0, y=20.0, heading=0.0)
    base.update(kw)
    return make_ship(**base)


def test_shadowfield_shift_and_dark_eldar_battery_shift():
    de, gun = _de(), _gun()
    plain = get_column_shifts(gun, make_ship(id="x", player=2, x=0.0, y=40.0), [])
    assert get_column_shifts(gun, de, []) == plain + 1
    assert get_column_shifts(de, gun, [], weapon={"de_battery": True}) == \
        get_column_shifts(de, gun, []) - 1


def test_gunnery_hit_places_one_tracking_mark_per_attacker():
    de, gun = _de(), _gun()
    gs = make_gs([de, gun])
    dice = DiceStub([1, 1, 1, 1])            # crit checks
    apply_damage(gs.get_ship_by_id("de"), 2, dice, gs, attacker_key="g", gunnery=True)
    apply_damage(gs.get_ship_by_id("de"), 1, dice, gs, attacker_key="g", gunnery=True)
    t = gs.get_ship_by_id("de")
    assert t.tracking_marks == ["g"] and shadowfield_need(t) == 3
    apply_damage(t, 1, dice, gs, attacker_key="g")        # a lance: no mark
    assert gs.get_ship_by_id("de").tracking_marks == ["g"]
    remove_brace_orders(gs)
    assert gs.get_ship_by_id("de").tracking_marks == []


def test_tracking_marks_can_be_turned_off():
    """Owner option: with GameState.rule_tracking_marks off, gunnery hits place
    no marks, so the shadowfield keeps saving on 2+."""
    de, gun = _de(), _gun()
    gs = make_gs([de, gun])
    gs.rule_tracking_marks = False
    dice = DiceStub([1, 1])                  # crit checks
    apply_damage(gs.get_ship_by_id("de"), 2, dice, gs, attacker_key="g", gunnery=True)
    t = gs.get_ship_by_id("de")
    assert t.tracking_marks == [] and shadowfield_need(t) == 2


def test_lances_face_the_shadowfield_save():
    de, gun = _de(tracking_marks=["a", "b"]), _gun()
    lance = {"name": "Lance", "weapon_type": "lance", "strength": 3, "range_cm": 30}
    rolls = [4, 5, 2,        # two hits
             4, 3]           # save 4+ (two marks): one saved
    dice = DiceStub(rolls)
    sr = resolve_lances(gun, de, lance, dice)
    assert dice._idx == len(rolls) and sr.hits == 1


def test_dark_eldar_phantom_lance_hits():
    de, gun = _de(), _gun(special_rules=[])
    lance = {"name": "Phantom Lance", "weapon_type": "lance", "strength": 3, "range_cm": 30,
             "de_phantom": True}
    dice = DiceStub([4, 5, 6])                # 1 + 2 + 2
    assert resolve_lances(de, gun, lance, dice).hits == 5


def test_torpedoes_face_the_shadowfield_save():
    gs = make_gs([_de()])
    m = OrdnanceMarker(id="tp", ordnance_type=OrdnanceType.TORPEDO_STANDARD.value,
                       owner_player=1, launched_by="a", x=0.0, y=35.0, heading=90.0,
                       strength=2, special_rules=[])
    rolls = [5, 6,           # two hits vs 5+
             1, 2,           # shadowfield 2+: one saved
             1]              # crit check
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(m, gs.get_ship_by_id("de"), dice, gs)
    assert dice._idx == len(rolls) and r["hits"] == 1
    assert gs.get_ship_by_id("de").hits_remaining == 5


def test_flickerfields_make_turrets_need_plus_two_not_vs_mines():
    ship = make_ship()
    torp = OrdnanceMarker(id="a", ordnance_type=OrdnanceType.TORPEDO_STANDARD.value,
                          owner_player=2, launched_by="z", special_rules=["dark_eldar"])
    mine = OrdnanceMarker(id="b", ordnance_type=OrdnanceType.MINE_FIELD.value,
                          owner_player=2, launched_by="z", special_rules=["dark_eldar"])
    assert turret_hit_on(ship, torp) == 6 and turret_hit_on(ship, mine) == 4


def test_movement_no_minimum_no_turning_distance_ctnh_auto():
    de = _de(speed=25, heading=0.0, y=60.0)
    assert get_effective_speed(de, SpecialOrder.NONE.value)[0] == 0
    res = validate_movement(de, [MoveCommand("turn_left", 45), MoveCommand("forward", 5)],
                            SpecialOrder.NONE.value)
    assert res.valid, res.errors
    gs = make_gs([de])
    assert do_command_check(de, SpecialOrder.COME_TO_NEW_HEADING.value, DiceStub([12]), gs)["passed"]


def test_ram_test_plus_two_dice():
    assert ram_ld_dice("cruiser", "cruiser", _de()) == 4
    assert ram_ld_dice("cruiser", "cruiser", make_ship()) == 2


def test_crit_table_and_control_circuit_repair():
    de = _de()
    assert crit_table_for(de) is DARK_ELDAR_CRITICAL_HITS
    from src.combat import apply_crit_effects
    gs = make_gs([de])
    de.leadership = 8
    de.critical_damage = [{"crit_type": "control_circuit", "description": "Control Circuit Damaged",
                           "repairable": True}]
    apply_crit_effects(de, DARK_ELDAR_CRITICAL_HITS[2], gs)
    assert de.leadership == 7
    gs.update_ship(de)
    resolve_damage_control(gs.get_ship_by_id("de"), DiceStub([6] * 6), gs)
    t = gs.get_ship_by_id("de")
    assert t.leadership == 8 and t.critical_damage == []
    apply_crit_effects(t, DARK_ELDAR_CRITICAL_HITS[10], gs)
    assert "shadowfield" not in t.special_rules and shadowfield_need(t) is None


def test_critical_hits_roll_on_the_dark_eldar_table_from_every_source():
    from src.combat import roll_critical_hit
    from src.hit_and_run import _apply_raid_crit
    gs = make_gs([_de(weapons=[{"name": "Keel Phantom Lance", "weapon_type": "lance",
                                "strength": 2, "range_cm": 30, "arcs": ["front"]}])])
    s = gs.get_ship_by_id("de")
    roll_critical_hit(s, DiceStub([5]), gs)                  # gunnery / ordnance crit: 5
    assert s.critical_damage[-1]["crit_type"] == "graviton_harness"
    _apply_raid_crit(6, s, gs, DiceStub([]))                 # raids and boarding crits: 6
    assert s.critical_damage[-1]["crit_type"] == "bladevanes"


def test_tyranid_thorax_and_spore_crits_cascade_when_they_cant_apply():
    from src.combat import roll_critical_hit
    k = make_ship(id="k", player=2, hits_max=6, turrets=0, special_rules=["tyranid"],
                  weapons=[{"name": "Prow Pyro-Acid Battery", "weapon_type": "battery",
                            "strength": 4, "range_cm": 30, "arcs": ["front"]}])
    gs = make_gs([k])
    s = gs.get_ship_by_id("k")
    roll_critical_hit(s, DiceStub([2]), gs)        # spore cysts injured: none, cascades
    assert s.critical_damage[-1]["crit_type"] == "prow_armament"   # 3, 4 have no weapons
    roll_critical_hit(s, DiceStub([6]), gs)        # thorax: none, cascades to Deep Wound
    assert s.critical_damage[-1]["crit_type"] == "fire"
