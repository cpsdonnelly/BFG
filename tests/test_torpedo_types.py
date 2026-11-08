"""Short burn torpedoes and barrage bombs (core rules s.16), Promethean
Unguents barrage bombs (Space Marine Chapter tactic), and the Imperial Navy /
Chaos option to buy them (owner ruling: one type per ship, carried in addition
to its other torpedoes, +5pts per torpedo strength)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.models import OrdnanceMarker, OrdnanceType
from src.ordnance import (resolve_torpedo_attack, launch_torpedoes, torpedo_kind_options,
                          torpedo_ordnance_type, short_burn_fuel_checks, resolve_mine_contact,
                          ordnance_turrets)
from src.ship_catalog import find_ship_class

TORPS = {"name": "Prow Torps", "weapon_type": "torpedo", "strength": 6,
         "range_cm": 30, "arcs": ["front"]}
BOARDING_TORPS = {**TORPS, "boarding_torpedoes": True}


def _marker(o_type, strength=3, rules=None):
    # Abeam of the target (side armour 5+)
    return OrdnanceMarker(id="tp", ordnance_type=o_type, owner_player=1, launched_by="a",
                          x=50.0, y=55.0, heading=270.0, strength=strength,
                          special_rules=list(rules or []))


def _target(**kw):
    base = dict(id="t", player=2, x=50.0, y=50.0, heading=0.0, hits_max=8, turrets=0,
                shields_max=0, armor_prow="6+", armor_side="5+")
    base.update(kw)
    return make_ship(**base)


# ── Loads and launching ──────────────────────────────────────────────────────

def test_kind_options_add_bought_type_to_standard_and_boarding():
    ship = make_ship(special_rules=["torpedo_type:short_burn"])
    assert [k for k, _ in torpedo_kind_options(ship, BOARDING_TORPS)] == [
        "standard", "boarding", "short_burn"]
    assert [k for k, _ in torpedo_kind_options(make_ship(), TORPS)] == ["standard"]
    assert torpedo_ordnance_type(TORPS, kind="barrage") == OrdnanceType.TORPEDO_BARRAGE.value
    assert torpedo_ordnance_type(TORPS, kind="") == OrdnanceType.TORPEDO_STANDARD.value


def test_short_burn_salvo_moves_40cm():
    ship = make_ship(id="a", special_rules=["torpedo_type:short_burn"], weapons=[TORPS])
    gs = make_gs([ship])
    m = launch_torpedoes(ship, ship.weapons[0], gs, kind="short_burn")
    assert m.ordnance_type == OrdnanceType.TORPEDO_SHORT_BURN.value and m.speed == 40
    assert m.strength == 6


# ── Short burn: out of fuel on a 6 ───────────────────────────────────────────

def test_short_burn_runs_out_of_fuel_on_a_6():
    gs = make_gs([])
    for i, oid in enumerate(("sb1", "sb2")):
        gs.add_ordnance(OrdnanceMarker(id=oid, ordnance_type=OrdnanceType.TORPEDO_SHORT_BURN.value,
                                       owner_player=1, launched_by="a", x=10.0 + i, y=20.0))
    gs.add_ordnance(OrdnanceMarker(id="std", ordnance_type=OrdnanceType.TORPEDO_STANDARD.value,
                                   owner_player=1, launched_by="a"))
    rolls = [6, 5]                     # sb1 out of fuel, sb2 carries on
    dice = DiceStub(rolls)
    short_burn_fuel_checks(gs, dice, player=1)
    assert dice._idx == len(rolls)
    assert [o["id"] for o in gs.ordnance] == ["sb2", "std"]
    bms = gs.get_blast_markers()
    assert len(bms) == 1 and (bms[0].x, bms[0].y) == (10.0, 20.0)


def test_short_burn_fuel_only_for_the_moving_player():
    gs = make_gs([])
    gs.add_ordnance(OrdnanceMarker(id="sb", ordnance_type=OrdnanceType.TORPEDO_SHORT_BURN.value,
                                   owner_player=2, launched_by="a"))
    dice = DiceStub([])
    short_burn_fuel_checks(gs, dice, player=1)
    assert dice._idx == 0 and len(gs.ordnance) == 1


# ── Barrage bombs: shields stop the hits ─────────────────────────────────────

def test_barrage_bomb_hits_are_stopped_by_shields():
    target = _target(shields_max=1)
    gs = make_gs([target])
    rolls = [5, 6, 2,      # vs side armour 5+: two hits
             4]            # one gets past the shield: crit check (needs 6)
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_BARRAGE.value), target, dice, gs)
    assert dice._idx == len(rolls)
    t = gs.get_ship_by_id("t")
    assert r["hits"] == 2 and t.hits_remaining == 7       # one blocked, one damage
    assert len(gs.get_blast_markers()) == 1               # the shield impact


def test_standard_torpedoes_still_ignore_shields():
    target = _target(shields_max=1)
    gs = make_gs([target])
    rolls = [5, 6, 2, 4, 3]
    dice = DiceStub(rolls)
    resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_STANDARD.value), target, dice, gs)
    assert dice._idx == len(rolls)
    assert gs.get_ship_by_id("t").hits_remaining == 6


# ── Promethean Unguents ──────────────────────────────────────────────────────

PROMETHEAN = ["space_marine_crew", "chapter_tactic:promethean_unguents"]


def test_promethean_barrage_hits_on_4_places_markers_no_damage():
    target = _target(armor_side="6+", turrets=3)
    gs = make_gs([target])
    rolls = [1, 2, 3,      # turrets vs the salvo: none shot down
             4, 5, 1]      # always hit on 4+ (armour 6+ ignored): two hits
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_BARRAGE.value, rules=PROMETHEAN),
                               target, dice, gs)
    assert dice._idx == len(rolls)
    t = gs.get_ship_by_id("t")
    assert r["hits"] == 2 and t.hits_remaining == 8
    assert len(gs.get_blast_markers()) == 2
    assert t.turrets_halved_turn == gs.turn_number
    assert ordnance_turrets(t, gs) == 2                    # 3 halved, rounding up


def test_promethean_halving_lasts_for_one_ordnance_attack_only():
    target = _target(turrets=3)
    target.turrets_halved_turn = 1
    gs = make_gs([target])
    gs.turn_number = 1
    rolls = [1, 1,         # halved turrets: 2 dice vs the next salvo
             1, 1, 1]      # attack: misses
    dice = DiceStub(rolls)
    resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_STANDARD.value),
                           gs.get_ship_by_id("t"), dice, gs)
    assert dice._idx == len(rolls)
    t = gs.get_ship_by_id("t")
    assert t.turrets_halved_turn == -1 and ordnance_turrets(t, gs) == 3
    # A later mine attack faces full turrets again
    rolls = [1, 1, 1] + [1] * 8
    dice = DiceStub(rolls)
    resolve_mine_contact(_marker(OrdnanceType.MINE_FIELD.value), t, dice, gs)
    assert dice._idx == len(rolls)


def test_halving_set_on_an_earlier_turn_does_not_apply():
    target = _target(turrets=3)
    target.turrets_halved_turn = 1
    gs = make_gs([target])
    gs.turn_number = 2
    assert ordnance_turrets(gs.get_ship_by_id("t"), gs) == 3


def test_barrage_without_promethean_uses_armour():
    target = _target(armor_side="6+")
    gs = make_gs([target])
    rolls = [4, 5, 1]      # no hits against 6+
    dice = DiceStub(rolls)
    r = resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_BARRAGE.value), target, dice, gs)
    assert dice._idx == len(rolls) and r["hits"] == 0


# ── Fleet builder option ─────────────────────────────────────────────────────

def test_navy_and_chaos_torpedo_ships_may_buy_one_type():
    lunar = find_ship_class("Lunar Cruiser")
    opts = {u.name: u for u in lunar.upgrades_available if u.name.startswith("Torpedoes:")}
    assert len(opts) == 4                              # short burn, barrage, guided, D3 roll
    assert sorted(u.points_cost for u in opts.values()) == [30, 30, 30, 50]   # S6 x 5; +50
    sb = next(u for u in opts.values() if "short burn" in u.name)
    d = lunar.to_ship_dict("L", 1, upgrades=[sb.name])
    assert "torpedo_type:short_burn" in d["special_rules"]
    assert d["points_value"] == lunar.points_cost + 30
    from src.booklet_options import ship_option_errors
    assert ship_option_errors(lunar, list(opts))        # only one type per ship
    # Capital ships only (export 10): escorts with torpedoes get none
    assert not [u for u in find_ship_class("Cobra Destroyer").upgrades_available
                if u.name.startswith("Torpedoes")]
    assert not find_ship_class("Infidel Raider").upgrades_available
    assert any(u.name.startswith("Torpedoes:")
               for u in find_ship_class("Desolator Battleship").upgrades_available)
    assert not any(u.name.startswith("Torpedoes:")
                   for u in find_ship_class("Murder Cruiser").upgrades_available)  # no torps


# ── AI ───────────────────────────────────────────────────────────────────────

def _ai_launch(distance):
    from src.ai_player import AIPlayer
    ship = make_ship(id="a", player=1, x=10.0, y=50.0, heading=0.0, weapons=[dict(TORPS)],
                     special_rules=["torpedo_type:short_burn"])
    ship.ordnance_loaded_torps = True
    enemy = make_ship(id="e", player=2, x=10.0 + distance, y=50.0, heading=180.0)
    gs = make_gs([ship, enemy])
    AIPlayer(player=1, tc=None, gs=gs, dice=DiceStub([]))._launch_ship_ordnance(
        gs.get_ship_by_id("a"))
    return gs.get_ordnance()


def test_ai_uses_short_burn_beyond_standard_reach():
    far = _ai_launch(45)
    assert [m.ordnance_type for m in far] == [OrdnanceType.TORPEDO_SHORT_BURN.value]
    near = _ai_launch(20)
    assert [m.ordnance_type for m in near] == [OrdnanceType.TORPEDO_STANDARD.value]


# ── Torpedoes attack what they touch anywhere along their move (s.15) ───────

def test_torpedo_first_contact_along_the_path():
    from src.geometry import torpedo_first_contact
    # Salvo moves 80 -> 110 along y=60, over a ship at x=95 (radius 2): touches it
    hit = torpedo_first_contact(95.0, 60.0, 2.0, 80.0, 60.0, 110.0, 60.0, 0.0)
    assert hit is not None and 80.0 < hit[0] < 95.0
    # The same move 10cm to the side never touches it
    assert torpedo_first_contact(95.0, 75.0, 2.0, 80.0, 60.0, 110.0, 60.0, 0.0) is None


# ── Seeking, guided, melta, vortex (s.16) ───────────────────────────────────

from src.ordnance import (seeking_turn, guided_control, roll_torpedo_types,  # noqa: E402
                          check_ordnance_vs_blast, torpedo_valid_target)
from src.models import BlastMarker  # noqa: E402


def test_seeking_turns_45_at_the_nearest_enemy_largest_on_a_tie():
    m = _marker(OrdnanceType.TORPEDO_SEEKING.value)
    m.x, m.y, m.heading = 0.0, 0.0, 0.0
    esc = make_ship(id="e", player=2, x=0.0, y=20.0, ship_type="escort")
    bs = make_ship(id="b", player=2, x=0.0, y=-20.0, ship_type="battleship")
    friend = make_ship(id="f", player=1, x=5.0, y=1.0)
    assert seeking_turn(m, [esc, bs, friend]) == -45.0          # the battleship, clamped
    assert not torpedo_valid_target(m, friend)
    assert torpedo_valid_target(m, bs)


def test_seeking_detonate_in_blast_markers_on_5():
    m = _marker(OrdnanceType.TORPEDO_SEEKING.value)
    bm = [BlastMarker(id="bm", x=m.x, y=m.y)]
    assert check_ordnance_vs_blast(m, bm, DiceStub([5]))
    std = _marker(OrdnanceType.TORPEDO_STANDARD.value)
    assert not check_ordnance_vs_blast(std, bm, DiceStub([5]))


def _guided_setup(launcher_ld=8, enemy_ld=7):
    a = make_ship(id="a", player=1, leadership=launcher_ld)
    e1 = make_ship(id="e1", player=2, leadership=enemy_ld, x=80.0)
    e2 = make_ship(id="e2", player=2, leadership=enemy_ld - 2, x=90.0)
    gs = make_gs([a, e1, e2])
    gs.turn_number = 3
    m = _marker(OrdnanceType.TORPEDO_GUIDED_LD.value)
    m.launched_turn = 1
    return gs, m


def test_guided_owner_turns_on_a_passed_leadership_test():
    gs, m = _guided_setup()
    dice = DiceStub([8])
    assert guided_control(m, gs, dice)[0] == 1 and dice._idx == 1


def test_guided_enemy_takes_control_with_its_best_leadership():
    gs, m = _guided_setup()
    dice = DiceStub([9,      # launcher fails (Ld 8)
                     7])     # e1 (Ld 7, the best) passes
    controller, logs = guided_control(m, gs, dice)
    assert controller == 2 and dice._idx == 2 and "takes control" in logs[-1]


def test_guided_nobody_turns_when_both_fail():
    gs, m = _guided_setup()
    dice = DiceStub([9, 8])
    assert guided_control(m, gs, dice)[0] is None and dice._idx == 2


def test_guided_cannot_turn_on_its_launch_turn():
    gs, m = _guided_setup()
    m.launched_turn = gs.turn_number
    dice = DiceStub([])
    assert guided_control(m, gs, dice)[0] is None and dice._idx == 0


def test_melta_hits_are_fire_crits_no_damage():
    target = _target(shields_max=2)
    gs = make_gs([target])
    rolls = [5, 6, 1]      # two hits vs 5+
    dice = DiceStub(rolls)
    resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_MELTA.value), target, dice, gs)
    t = gs.get_ship_by_id("t")
    assert dice._idx == len(rolls)
    assert t.hits_remaining == 8 and [c["crit_type"] for c in t.critical_damage] == ["fire", "fire"]


def test_melta_fire_crits_even_on_an_escort():
    esc = _target(ship_type="escort", hits_max=1)
    gs = make_gs([esc])
    dice = DiceStub([6, 1, 1])
    resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_MELTA.value), esc, dice, gs)
    assert [c["crit_type"] for c in gs.get_ship_by_id("t").critical_damage] == ["fire"]


def test_vortex_hits_deal_damage_and_automatic_crits():
    target = _target(weapons=[dict(TORPS)])
    gs = make_gs([target])
    rolls = [5, 1, 1,      # one hit
             8]            # automatic crit, no D6 check: 2D6 = 8 Thrusters Damaged (+1 damage)
    dice = DiceStub(rolls)
    resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_VORTEX.value), target, dice, gs)
    t = gs.get_ship_by_id("t")
    assert dice._idx == len(rolls)
    assert t.hits_remaining == 6 and [c["crit_type"] for c in t.critical_damage] == [
        "thrusters_damaged"]


def test_unused_melta_explodes_on_a_launcher_crit():
    from src.combat import apply_damage
    target = _target(weapons=[dict(TORPS)], special_rules=["torpedo_type:melta"])
    gs = make_gs([target])
    rolls = [6,            # crit check
             5,            # 2D6 = 5: Prow Armament Damaged (the torpedo launcher)
             2]            # D3 = 2 extra Fire crits
    dice = DiceStub(rolls)
    apply_damage(target, 1, dice, gs, ignores_shields=True)
    t = gs.get_ship_by_id("t")
    assert dice._idx == len(rolls)
    assert [c["crit_type"] for c in t.critical_damage] == ["prow_armament", "fire", "fire"]
    # Owner ruling: the explosion doesn't use up the salvo; only firing it does
    assert t.once_torps_used == []
    assert "melta" in [k for k, _ in torpedo_kind_options(t, TORPS)]


def test_unused_vortex_explodes_for_d3_damage_and_a_crit():
    from src.combat import apply_damage
    target = _target(weapons=[dict(TORPS)], special_rules=["torpedo_type:vortex"])
    gs = make_gs([target])
    rolls = [6, 5,         # crit: Prow Armament Damaged
             3,            # D3 = 3 extra damage
             7]            # automatic crit: Fire!
    dice = DiceStub(rolls)
    apply_damage(target, 1, dice, gs, ignores_shields=True)
    t = gs.get_ship_by_id("t")
    assert dice._idx == len(rolls)
    assert t.hits_remaining == 4                      # 1 hit + 3
    assert [c["crit_type"] for c in t.critical_damage] == ["prow_armament", "fire"]


def test_once_per_game_salvo_used_up_by_launching():
    ship = make_ship(id="a", weapons=[dict(TORPS)], special_rules=["torpedo_type:seeking"])
    gs = make_gs([ship])
    assert "seeking" in [k for k, _ in torpedo_kind_options(ship, TORPS)]
    launch_torpedoes(ship, ship.weapons[0], gs, kind="seeking")
    s = gs.get_ship_by_id("a")
    assert s.once_torps_used == ["seeking"]
    assert [k for k, _ in torpedo_kind_options(s, TORPS)] == ["standard"]


def test_game_start_torpedo_rolls():
    a = make_ship(id="a", player=1, special_rules=["torpedo_roll:d3_anointed"])
    b = make_ship(id="b", player=2, special_rules=["torpedo_roll:d6_refitted"])
    gs = make_gs([a, b])
    dice = DiceStub([2,      # D3 = 2: melta
                     3])     # D6 = 3: guided
    roll_torpedo_types(gs, dice)
    assert dice._idx == 2
    assert gs.get_ship_by_id("a").special_rules == ["torpedo_type:melta"]
    assert gs.get_ship_by_id("b").special_rules == ["torpedo_type:guided"]


def test_refitted_looted_and_anointed_options():
    cost = {u.name: u.points_cost for u in find_ship_class("Mechanicus Gothic Cruiser").upgrades_available}
    assert cost["Refitted Torpedoes (D6 at game start)"] == 20
    assert {u.points_cost for u in find_ship_class("Mechanicus Endeavour Light Cruiser").upgrades_available
            if u.name.startswith("Refitted")} == {10}
    assert "Looted Torpedoes (D6 at game start)" in [
        u.name for u in find_ship_class("Gorbag's Revenge (0-1)").upgrades_available]
    chaos = [u.name for u in find_ship_class("Desolator Battleship").upgrades_available]
    assert "Torpedoes: Anointed Munitions (D3 at game start)" in chaos
    lunar = {u.name: u.points_cost for u in find_ship_class("Lunar Cruiser").upgrades_available}
    assert lunar["Torpedoes: roll for Seeking / Melta / Vortex (D3 at game start)"] == 50
    assert lunar["Torpedoes: guided (turn 45° on a Leadership test)"] == 30


# ── Ork torpedo launcha swaps and looted torpedoes ───────────────────────────

def test_ork_torpedo_launcha_replaces_prow_heavy_gunz():
    from src.booklet_options import ship_option_errors
    kk = find_ship_class("Kill Kroozer")
    opts = {u.name: u for u in kk.upgrades_available}
    big = "Prow torpedo launcha (2D6+2, no side heavy gunz)"
    assert opts["Prow torpedo launcha (D6+2)"].points_cost == 10 and opts[big].points_cost == 10
    d = kk.to_ship_dict("K", 1, upgrades=[big, "Looted Torpedoes (D6 at game start)"])
    names = [w["name"] for w in d["weapons"]]
    assert "Prow Heavy Gunz" not in names and "Port Heavy Gunz" not in names
    torps = [w for w in d["weapons"] if w["weapon_type"] == "torpedo"]
    assert [w["strength_dice"] for w in torps] == ["2D6+2"]
    assert "torpedo_roll:d6_refitted" in d["special_rules"]
    assert d["points_value"] == kk.points_cost + 30
    # Looted torps need the launcha; only one launcha
    assert ship_option_errors(kk, ["Looted Torpedoes (D6 at game start)"])
    assert ship_option_errors(kk, ["Prow torpedo launcha (D6+2)", big])
    basha = find_ship_class("Basha Lite Kroozer")
    assert {u.name: u.points_cost for u in basha.upgrades_available}[
        "Prow torpedo launcha (D6+1)"] == 0


# ── Inquisition: cruiser refits, Inquisitor Lord, Inferno and vortex torpedoes ─

def test_inquisitorial_cruiser_torpedo_refit_inferno_and_vortex():
    from src.booklet_options import ship_option_errors
    ic = find_ship_class("Inquisitorial Cruiser")
    lord, refit = "Ordo Malleus Inquisitor Lord (Ld 10)", "Refit: launch bays to Torpedo Salvo"
    vortex = "Vortex Torpedoes (Inquisitor Lord's ship)"
    d = ic.to_ship_dict("I", 1, upgrades=[refit, lord, vortex])
    torps = [w for w in d["weapons"] if w["weapon_type"] == "torpedo"]
    assert len(torps) == 1 and torps[0]["strength"] == 6 and torps[0]["boarding_torpedoes"]
    assert not any(w["weapon_type"] == "launch_bay" for w in d["weapons"])
    assert d["leadership"] == 10 and d["rerolls_remaining"] == 1 and d["is_flagship"]
    assert "torpedo_type:vortex" in d["special_rules"]
    assert d["points_value"] == ic.points_cost + 75 + 50
    assert ship_option_errors(ic, [refit, vortex])            # needs the Inquisitor Lord
    assert ship_option_errors(ic, [lord, vortex])             # needs torpedoes
    assert ship_option_errors(ic, ["Inferno Torpedoes"])      # needs torpedoes
    assert not ship_option_errors(ic, [refit, "Inferno Torpedoes"])
    cobra = find_ship_class("Inquisitorial Cobra Destroyer")
    assert [(u.name, u.points_cost) for u in cobra.upgrades_available] == [("Inferno Torpedoes", 20)]


def test_inferno_torpedoes_are_reusable_melta():
    ship = make_ship(id="a", weapons=[dict(TORPS)], special_rules=["torpedo_type:inferno"])
    gs = make_gs([ship])
    m = launch_torpedoes(ship, ship.weapons[0], gs, kind="inferno")
    assert m.ordnance_type == OrdnanceType.TORPEDO_MELTA.value
    s = gs.get_ship_by_id("a")
    assert s.once_torps_used == [] and "inferno" in [k for k, _ in torpedo_kind_options(s, TORPS)]


def test_inferno_launcher_crit_inflicts_d6_fires():
    from src.combat import apply_damage
    target = _target(weapons=[dict(TORPS)], special_rules=["torpedo_type:inferno"])
    gs = make_gs([target])
    rolls = [6, 5,         # crit: Prow Armament Damaged
             4]            # D6 = 4 Fire results
    dice = DiceStub(rolls)
    apply_damage(target, 1, dice, gs, ignores_shields=True)
    t = gs.get_ship_by_id("t")
    assert dice._idx == len(rolls)
    assert [c["crit_type"] for c in t.critical_damage] == ["prow_armament"] + ["fire"] * 4


def test_chaos_torpedoes_carry_boarding_torpedoes():
    torps = [w for w in find_ship_class("Desolator Battleship").weapons
             if w["weapon_type"] == "torpedo"]
    assert torps and all(w.get("boarding_torpedoes") for w in torps)
    lunar = [w for w in find_ship_class("Lunar Cruiser").weapons if w["weapon_type"] == "torpedo"]
    assert not lunar[0].get("boarding_torpedoes")          # Navy: ordinary torpedoes only


def test_inquisitor_lord_extra_rerolls():
    ic = find_ship_class("Inquisitorial Cruiser")
    lord = "Ordo Malleus Inquisitor Lord (Ld 10)"
    d = ic.to_ship_dict("I", 1, upgrades=[lord, "Inquisitor Lord: 2 extra re-rolls"])
    assert d["rerolls_remaining"] == 3 and d["points_value"] == ic.points_cost + 75 + 50


# ── Owner rulings (torpedo readings) ─────────────────────────────────────────

def test_guided_reroll_on_a_failed_launcher_test():
    gs, m = _guided_setup()
    asked = []
    dice = DiceStub([10, 7])          # fails Ld 8, re-roll passes
    controller, _ = guided_control(m, gs, dice,
                                   reroll_fn=lambda p, s, r: asked.append((p, r)) or True)
    assert controller == 1 and dice._idx == 2 and asked == [(1, 10)]


def test_guided_enemy_player_chooses_which_ship_tries():
    gs, m = _guided_setup()
    chosen = []

    def choose(player, ships):
        chosen.append(player)
        return next(s for s in ships if s.id == "e2")     # not the best Ld
    dice = DiceStub([9, 6])           # launcher fails; e2 (Ld 5) fails too
    controller, logs = guided_control(m, gs, dice, choose_enemy_fn=choose)
    assert chosen == [2] and controller is None and dice._idx == 2
    dice = DiceStub([9])
    assert guided_control(m, gs, dice, choose_enemy_fn=lambda p, s: None)[0] is None
    assert dice._idx == 1             # declining: no enemy test


def test_guided_launcher_gone_no_turn_no_enemy_test():
    gs, m = _guided_setup()
    gs.ships = [s for s in gs.ships if s["id"] != "a"]
    dice = DiceStub([])
    assert guided_control(m, gs, dice)[0] is None and dice._idx == 0


def test_melta_sets_a_drifting_hulk_burning():
    hulk = _target()
    hulk.status, hulk.hits_remaining = "drifting_hulk", 0
    gs = make_gs([hulk])
    dice = DiceStub([5, 1, 1])
    resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_MELTA.value), hulk, dice, gs)
    assert dice._idx == 3 and gs.get_ship_by_id("t").status == "burning_hulk"


def test_escort_on_fire_from_melta_gets_damage_control():
    from src.end_phase import resolve_damage_control
    esc = _target(ship_type="escort", hits_max=1)
    gs = make_gs([esc])
    resolve_torpedo_attack(_marker(OrdnanceType.TORPEDO_MELTA.value), esc,
                           DiceStub([6, 1, 1]), gs)
    e = gs.get_ship_by_id("t")
    assert [c["crit_type"] for c in e.critical_damage] == ["fire"]
    dice = DiceStub([6])              # one die per hit remaining: a 6 puts it out
    resolve_damage_control(e, dice, gs)
    assert dice._idx == 1 and gs.get_ship_by_id("t").critical_damage == []


def test_ai_guides_its_torpedoes():
    from src.ai_player import AIPlayer
    ship = make_ship(id="a", player=1, x=10.0, y=50.0, heading=0.0, weapons=[dict(TORPS)],
                     special_rules=["torpedo_type:guided"])
    ship.ordnance_loaded_torps = True
    enemy = make_ship(id="e", player=2, x=30.0, y=50.0, heading=180.0)
    gs = make_gs([ship, enemy])
    AIPlayer(player=1, tc=None, gs=gs, dice=DiceStub([]))._launch_ship_ordnance(
        gs.get_ship_by_id("a"))
    assert [m.ordnance_type for m in gs.get_ordnance()] == [OrdnanceType.TORPEDO_GUIDED_LD.value]
