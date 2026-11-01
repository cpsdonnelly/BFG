"""Space Marine Chapter Tactics (Space Marines faction rules)."""
import pytest
from tests.conftest import make_ship, make_gs, DiceStub
from src.chapter_tactics import (apply_fleet_tactics, weapon_range, pack_hunter_bonus,
                                 shadow_engines_hidden, reduce_for_movement_order)
from src.combat import (effective_battery_firepower, get_column_shifts, apply_damage,
                        resolve_siege_cannons)
from src.movement import get_max_turns, validate_movement, MoveCommand, blast_markers_to_slow
from src.hit_and_run import check_teleport_eligibility, resolve_raids
from src.ship_catalog import find_ship_class
from src.booklet_options import tactical_flexibility_refund, ship_option_errors

SM = ["space_marine_crew", "teleport_assault"]


def tac(key):
    return SM + [f"chapter_tactic:{key}"]


MACRO = {"name": "Port Macrobatteries", "weapon_type": "battery", "strength": 6,
         "range_cm": 30, "arcs": ["left", "front", "right"]}
BC = {"name": "Dorsal Bombardment Cannon", "weapon_type": "battery", "strength": 4,
      "range_cm": 30, "arcs": ["left", "front", "right"], "hits_on": 4, "crit_on": 4}


# ── Fleet builder and game start ─────────────────────────────────────────────

def test_chapter_tactic_option_and_tactical_flexibility():
    bb = find_ship_class("Space Marine Battle Barge")
    names = [u.name for u in bb.upgrades_available]
    assert "Chapter tactic: Siege Cannons" in names
    assert ship_option_errors(bb, ["Chapter tactic: Siege Cannons"])           # needs MoF
    assert ship_option_errors(bb, ["Master of the Fleet (Ld 10)", "Chapter tactic: Siege Cannons",
                                   "Chapter tactic: Wings of Fury"])           # one only
    sc = find_ship_class("Strike Cruiser")
    variant = ["Variant: macrobatteries to launch bays", "Variant: prow Bombardment Cannon"]
    assert tactical_flexibility_refund([[], variant], [bb, sc]) == 0
    assert tactical_flexibility_refund(
        [["Master of the Fleet (Ld 10)", "Chapter tactic: Siege Cannons"], variant], [bb, sc]) == 20


def test_apply_fleet_tactics_spreads_and_fixes_effects():
    bb = find_ship_class("Space Marine Battle Barge").to_ship_dict(
        "B", 1, upgrades=["Master of the Fleet (Ld 10)", "Chapter tactic: Wings of Fury"])
    sc = find_ship_class("Strike Cruiser").to_ship_dict("S", 1)
    rsv = find_ship_class("Sword Rapid Strike Vessel").to_ship_dict("R", 1)
    gs = make_gs([])
    gs.ships = [bb, sc, rsv]
    assert apply_fleet_tactics(gs) == ["Player 1 Chapter tactic: Wings of Fury"]
    assert "chapter_tactic:wings_of_fury" in gs.ships[1]["special_rules"]
    assert "chapter_tactic:wings_of_fury" not in gs.ships[2]["special_rules"]   # no SM rules
    bay = next(w for w in gs.ships[1]["weapons"] if w["weapon_type"] == "launch_bay")
    assert bay["craft_speeds"]["thunderhawk"] == 30


def test_dark_age_caps_capital_speed():
    vg = find_ship_class("Vanguard Cruiser").to_ship_dict("V", 1)
    bb = find_ship_class("Space Marine Battle Barge").to_ship_dict(
        "B", 1, upgrades=["Master of the Fleet (Ld 10)", "Chapter tactic: Dark Age Plasma Batteries"])
    gs = make_gs([])
    gs.ships = [bb, vg]
    apply_fleet_tactics(gs)
    assert gs.ships[1]["speed"] == 20 and gs.ships[0]["speed"] == 20


# ── Dark Age Plasma Batteries ────────────────────────────────────────────────

def test_dark_age_range_and_no_long_range_shift():
    ship = make_ship(id="a", x=0.0, y=0.0, special_rules=tac("dark_age_plasma"), weapons=[MACRO])
    far = make_ship(id="t", player=2, x=40.0, y=0.0)
    ship.distance_moved_this_turn = 10
    assert weapon_range(ship, MACRO) == 45 and weapon_range(ship, BC) == 30
    assert get_column_shifts(ship, far, [], weapon=MACRO) == 0
    ship.distance_moved_this_turn = 12
    assert weapon_range(ship, MACRO) == 30
    assert get_column_shifts(ship, far, [], weapon=MACRO) == 1


# ── Lightning Thrusters ──────────────────────────────────────────────────────

def test_lightning_thrusters_vanguard_on_aaf():
    vg = make_ship(id="v", ship_class="Vanguard Cruiser", turn_angle=90, speed=25,
                   special_rules=tac("lightning_thrusters"), special_order="all_ahead_full")
    assert get_max_turns("all_ahead_full", vg) == 1
    ok = validate_movement(vg, [MoveCommand("forward", 10), MoveCommand("turn_left", 45),
                                MoveCommand("forward", 25)], "all_ahead_full", aaf_bonus=10)
    assert ok.valid
    too_far = validate_movement(vg, [MoveCommand("forward", 10), MoveCommand("turn_left", 90),
                                     MoveCommand("forward", 25)], "all_ahead_full", aaf_bonus=10)
    assert not too_far.valid
    assert effective_battery_firepower(vg, MACRO) == 6          # didn't turn: full
    vg.turns_used_this_turn = 1
    assert effective_battery_firepower(vg, MACRO) == 3
    target = make_ship(id="t", player=2, hits_max=6, shields_max=0, x=5.0, y=0.0)
    gs = make_gs([vg, target])
    assert check_teleport_eligibility(vg, target, gs)[0]


# ── Pack Hunter Protocols ────────────────────────────────────────────────────

def test_pack_hunter_bonus():
    def esc(i, sq="a"):
        return make_ship(id=f"e{i}", ship_type="escort", squadron_id=sq,
                         special_rules=tac("pack_hunter"))
    cruiser = make_ship(id="c", player=2, ship_type="cruiser")
    assert pack_hunter_bonus([esc(1), esc(2), esc(3)], cruiser) == 3
    assert pack_hunter_bonus([esc(1)], cruiser) == 0                       # not combined
    assert pack_hunter_bonus([esc(1), esc(2, "b")], cruiser) == 0          # other squadron
    assert pack_hunter_bonus([esc(1), esc(2)], make_ship(ship_type="escort")) == 0   # not larger


# ── Siege Cannons ────────────────────────────────────────────────────────────

def test_siege_cannons_combined_roll_and_alone_shift():
    barge = make_ship(id="b", ship_type="battleship", x=0.0, y=0.0, heading=0.0,
                      special_rules=tac("siege_cannons"), weapons=[MACRO, BC])
    target = make_ship(id="t", player=2, x=20.0, y=0.0, heading=90.0,
                       armor_prow="6+", armor_side="6+")
    assert get_column_shifts(barge, target, [], weapon=MACRO) == 1      # macros alone
    assert get_column_shifts(barge, target, [], weapon=BC) == 0
    from src.tables import lookup_gunnery_dice, get_gunnery_column
    n = lookup_gunnery_dice(10, get_gunnery_column("capital", barge.get_target_orientation(target)), 0)
    macro_n = max(0, n - 4)
    rolls = [5] * macro_n + [4] * (n - macro_n)
    dice = DiceStub(rolls)
    m, b = resolve_siege_cannons(barge, target, [MACRO], [BC], dice, [])
    assert dice._idx == n
    assert m.hits == 0 and b.hits == n - macro_n        # 5s miss 6+ armour; 4s hit for the cannons


# ── Wings of Fury ────────────────────────────────────────────────────────────

def test_wings_of_fury_rerolls_failed_raids():
    target = make_ship(id="t", player=2)
    gs = make_gs([target])
    rolls = [1,          # 1 +1 SM = 2: crit result 2... not a failure; use a 0-effect case
             ]
    small = make_ship(id="s", player=2, ship_type="escort", hits_max=1)
    gs = make_gs([small])
    rolls = [1,          # 1+1 = 2 < 4 vs a small escort: no effect -> re-roll
             4]          # 4+1 = 5: 1 damage
    dice = DiceStub(rolls)
    r = resolve_raids(1, small, False, dice, gs, attacker_rules=["space_marine_crew"],
                      reroll_failed=True)
    assert dice._idx == len(rolls) and r["damage"] == 1 and r["raid_rolls"] == [4]


# ── Shadow Engines ───────────────────────────────────────────────────────────

def test_shadow_engines_hidden_beyond_30_unless_closest():
    shooter = make_ship(id="a", player=1, x=0.0, y=0.0)
    near = make_ship(id="n", player=2, x=20.0, y=0.0)
    hidden = make_ship(id="h", player=2, x=40.0, y=0.0, ship_type="escort",
                       special_rules=tac("shadow_engines"))
    assert shadow_engines_hidden(shooter, hidden, [near, hidden])
    assert not shadow_engines_hidden(shooter, hidden, [hidden])          # closest target
    close = make_ship(id="c", player=2, x=25.0, y=0.0, ship_type="escort",
                      special_rules=tac("shadow_engines"))
    assert not shadow_engines_hidden(shooter, close, [near, close])     # within 30cm


# ── Tactical Reserves ────────────────────────────────────────────────────────

def test_tactical_reserves():
    barge = make_ship(ship_type="battleship", special_rules=tac("tactical_reserves"),
                      special_order="all_ahead_full")
    assert reduce_for_movement_order(barge, 12, gunnery=True) == 9
    assert reduce_for_movement_order(barge, 5, gunnery=True) == 4      # 3.75 rounded up
    from src.combat import resolve_lances
    lance = {"name": "Lances", "weapon_type": "lance", "strength": 4, "range_cm": 30,
             "arcs": ["front"]}
    tgt = make_ship(id="t", player=2, x=10.0, y=0.0)
    barge.x, barge.y, barge.heading = 0.0, 0.0, 0.0
    rolls = [1, 1, 1]                                                 # lances 4 -> 3 dice
    dice = DiceStub(rolls)
    resolve_lances(barge, tgt, lance, dice)
    assert dice._idx == len(rolls)                                    # owner ruling: lances too
    barge.special_order = "come_to_new_heading"
    assert reduce_for_movement_order(barge, 12, gunnery=True) == 6
    assert blast_markers_to_slow(barge) == 2
    assert blast_markers_to_slow(make_ship(special_rules=SM)) == 1


# ── Heed the Machine Spirit ──────────────────────────────────────────────────

def test_machine_spirit_saves_one_failed_brace_once_per_attacker():
    t = make_ship(id="t", player=2, hits_max=10, shields_max=0,
                  special_rules=tac("machine_spirit"))
    gs = make_gs([t])
    rolls = [1, 2,       # brace saves: both fail
             7,          # Ld 7 test passed: one save succeeds
             1]          # crit check for the one hit left
    dice = DiceStub(rolls)
    r = apply_damage(t, 2, dice, gs, target_braced=True, attacker_key="A")
    assert dice._idx == len(rolls) and r["brace_saves"] == 1 and r["hull_hits"] == 1
    rolls = [1, 1]       # same attacker again: no second test
    dice = DiceStub(rolls)
    r = apply_damage(t, 1, dice, gs, target_braced=True, attacker_key="A")
    assert dice._idx == len(rolls) and r["brace_saves"] == 0
