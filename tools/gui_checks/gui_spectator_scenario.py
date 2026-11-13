"""AI-vs-AI booklet scenario (To do 7), Chaos attacking Imperial Navy, through
the real GamePanel until game over. Usage: gui_spectator_scenario.py
[igougo|aa] [ambush|rescue|warp_storm|confrontation]."""
import os
import sys
import tempfile
import time
import math
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, "/home/user/BFG")
os.chdir(tempfile.mkdtemp())

from src.models import Ship
import src.choice_dialog as _cd_yn
_cd_yn.yes_no = lambda root, title, text, best: messagebox.askyesno(title, text)
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src import game_panel as gp_mod
from src.game_panel import GamePanel

dialogs = []
for name in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, name,
            (lambda n: lambda title, msg="", **k: dialogs.append((n, title, msg)))(name))
messagebox.askyesno = lambda *a, **k: False
gp_mod.messagebox = messagebox

system = sys.argv[1] if len(sys.argv) > 1 else "igougo"
mode, phase_order = "bag_adjusted", "shoot_first"
difficulty = "normal"
WEAPONS = [
    {"name": "Port Battery", "weapon_type": "battery", "strength": 6, "range": 45, "arcs": ["left"]},
    {"name": "Stbd Battery", "weapon_type": "battery", "strength": 6, "range": 45, "arcs": ["right"]},
    {"name": "Prow Lance", "weapon_type": "lance", "strength": 2, "range": 60, "arcs": ["front"]},
]


def ship(id, player, x, y):
    return Ship(id=id, name=id, ship_class="Test", faction="imperial_navy_gothic",
                player=player, ship_type="cruiser", base_size="small",
                x=x, y=y, heading=0.0 if player == 1 else 180.0, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+",
                turrets=2, hits_max=8, leadership=8, weapons=[dict(w) for w in WEAPONS],
                special_rules=[], upgrades=[], critical_damage=[], points_value=180)


root = tk.Tk()
gs = GameState()
gs.dice_mode = "mixed"          # the default the bug report was about
gs.ai_spectator = True
gs.ai_difficulty = difficulty
gs.turn_limit = 6
gs.turn_system = system
gs.aa_settings = {"order_mode": mode, "phase_order": phase_order}
from src.ship_catalog import find_ship_class
from src.fleet_loader import roll_starting_leadership
def cat(name, player, i, x, y, sq=""):
    d = find_ship_class(name).to_ship_dict(name, player, ship_id=f"p{player}_{i}")
    d.update(x=x, y=y, heading=0.0 if player == 1 else 180.0, squadron_id=sq)
    return Ship.from_dict(d)
gs.table_width, gs.table_height = 180.0, 120.0
scenario = sys.argv[2] if len(sys.argv) > 2 else "ambush"
gs.scenario_mode = scenario
gs.rule_subplots = "subplots" in sys.argv
gs.scenario_attacker = 1
gs.turn_limit = 12
from src import scenarios as sc
imp = ["Lunar Class Cruiser", "Gothic Class Cruiser", "Dominator Class Cruiser",
       "Dauntless Class Light Cruiser"]
chs = ["Slaughter Class Cruiser", "Carnage Class Cruiser", "Murder Class Cruiser",
       "Infidel Class Raider"]
if scenario in ("ambush", "raiders", "blockade_run", "rearguard"):
    chs = chs[:2]                       # the attacker has half the points
if scenario == "line_breaker":
    imp = imp[:3] + ["Orbital Weapons Platform"] * 3 + ["Orbital Defence Laser Platform"] * 2
if scenario == "convoy_matched":
    # 3 warships (180 + 185? the list's costs) -> capacity by the points; filled below
    imp = imp[:2]
if scenario == "space_assault":
    imp = imp[:3] + ["Space Station", "Orbital Weapons Platform"]
for p, names in ((1, chs), (2, imp)):
    for i, n in enumerate(names):
        s_ = cat(n, p, i, 0.0, 0.0)
        if p == 2 and i == 0:
            s_.is_flagship = True
        if s_.speed == 0:
            s_.heading = 90.0
        gs.add_ship(s_)
if scenario == "planet_strike":
    pts = sum(s_.points_value for s_ in gs.get_ships() if s_.player == 1)
    for k in range(-(-pts // 200)):
        gs.add_ship(cat("Heavy Transport", 1, 20 + k, 0.0, 0.0))
    gs.add_ship(cat("Orbital Weapons Platform", 2, 30, 0.0, 0.0))
if scenario == "alien_intervention":
    gs.add_ship(cat("Protector Cruiser", 2, 40, 0.0, 0.0))     # the alien allies
if scenario == "convoy_matched":
    pts = sum(s_.points_value for s_ in gs.get_ships() if s_.player == 2)
    for k in range(-(-pts // 100)):
        c = cat("Conventional Transport", 2, 10 + k, 0.0, 0.0)
        c.squadron_id = "convoy_a" if k < 3 else "convoy_b"
        gs.add_ship(c)
sc.setup_scenario(gs)
fixed = sc.fixed_placements(gs)
zones = {z.player: z for z in sc.deployment_zones(gs)}
placed = []
for p in (1, 2):
    z = zones[p]
    idx = 0
    for s_ in [x for x in gs.get_ships() if x.player == p and not sc.is_reserve(x)]:
        if s_.id in fixed:
            s_.x, s_.y, s_.heading = fixed[s_.id]
        else:
            pos = sc.auto_positions(gs, [s_], z, placed, idx)
            if pos is None:
                r = z.rects()[0]
                cx, cy = (r.x_min + r.x_max) / 2, (r.y_min + r.y_max) / 2
                pos = [(cx + 10 * ((idx % 4) - 1.5) * (1 if r.x_max - r.x_min > 40 else 0.3),
                        cy + 10 * ((idx % 4) - 1.5) * (0.3 if r.x_max - r.x_min > 40 else 1)
                        + 4 * (idx // 4))]
            s_.x, s_.y = pos[0]
            s_.heading = 0.0 if s_.x < gs.table_width / 2 else 180.0
            if scenario in ("line_breaker", "space_assault", "confrontation", "convoy_matched",
                            "chance_encounter"):
                s_.heading = 270.0 if p == 1 else 90.0
            if scenario == "cruiser_clash":
                s_.heading = 270.0 if z.y_min > gs.table_height / 2 else 90.0
            if scenario == "planet_strike":
                s_.heading = 0.0 if p == 1 else 180.0
                if "immobile" in s_.special_rules:
                    pl = sc.strike_planet(gs)
                    s_.x, s_.y = pl.x - 20.0, pl.y + 15.0
            if scenario in ("ambush", "raiders") and p == 2:
                s_.heading = 90.0
            if scenario == "rearguard" and p == 2:
                s_.heading = 180.0
            if scenario == "the_bait" and p == 1:
                s_.heading = 0.0
            if scenario == "alien_intervention":
                s_.heading = 0.0 if s_.x < gs.table_width / 2 else 180.0
                if p == 2:
                    s_.heading = 90.0
            if scenario == "surprise_attack" and p == 2 and sc.on_standby(gs, s_):
                pl_ = next(q for q in gs.get_phenomena() if q.id == "scenario_planet")
                s_.heading = (math.degrees(math.atan2(s_.y - pl_.y, s_.x - pl_.x)) + 90) % 360
            if scenario in ("raiders", "rearguard", "surprise_attack") and p == 1:
                s_.heading = 90.0 if s_.y < gs.table_height / 2 else 270.0   # onto the table
            if scenario == "blockade_run":
                s_.heading = 90.0 if p == 1 else 270.0
            idx += 1
        assert z.contains(s_.x, s_.y) or s_.id in fixed, (s_.name, s_.x, s_.y)
        placed.append(s_)
        gs.update_ship(s_)
for p in (1, 2):
    assert not sc.division_errors(gs, p), sc.division_errors(gs, p)
assert not sc.force_errors(gs), sc.force_errors(gs)
gs.first_player = sc.first_player(gs) or sc.first_turn_chooser(gs) or 1
dice = DiceRoller(mode=gs.dice_mode)
print('Leadership:', roll_starting_leadership(gs, dice, ai_dice=DiceRoller(mode='auto'))[:3])
tc = TurnController(gs, dice)
board = BoardView(root, gs)
frame = tk.Frame(board.side_panel)
frame.pack()
panel = GamePanel(frame, tc, board, root)

game_over = []
orig_dialog = panel._show_game_over_dialog
panel._show_game_over_dialog = lambda w, **k: (game_over.append((w, k)), orig_dialog(w, **k))

# Count dice popups: in mixed mode each would be a Toplevel window
popups = []
orig_mixed = DiceRoller._mixed_input if hasattr(DiceRoller, "_mixed_input") else None
if orig_mixed:
    DiceRoller._mixed_input = lambda self, *a, **k: (popups.append(1), orig_mixed(self, *a, **k))[1]

panel._roll_subplots()
panel._begin_turn1()
start = time.time()
phases_seen = set()
while not panel._game_over and time.time() - start < 240:
    root.update()
    phases_seen.add((gs.turn_number, gs.current_phase))
    time.sleep(0.01)

import os
if os.environ.get("DUMP_LOG"):
    open(os.environ["DUMP_LOG"], "w").write("\n".join(gs.log))
hp = {s.id: s.hits_remaining for s in gs.get_ships()}
print(f"[{scenario} {system}] game over={panel._game_over} after {time.time()-start:.1f}s, "
      f"reached turn {gs.turn_number}, phases visited={len(phases_seen)}")
print(f"[{scenario} {system}] hits remaining: {hp}")
print(f"[{scenario} {system}] game-over dialogs: {len(game_over)} winner={game_over[0][0] if game_over else None}")
print(f"[{scenario} {system}] dice popups: {len(popups)}; error dialogs: "
      f"{[d for d in dialogs if d[0] == 'showerror']}")
print(f"[{scenario} {system}] dice mode after game: {dice.mode}")
aa_log = [l for l in gs.log if "[AA]" in l]
print(f"[{scenario} {system}] result: {game_over[0][1] if game_over else None}")
if scenario == "cruiser_clash":
    print(f"[{scenario} {system}] damage points: {sc.damage_points(gs, 1)} - "
          f"{sc.damage_points(gs, 2)}")
if scenario == "chance_encounter":
    print(f"[{scenario} {system}] result by the scenario: {sc.chance_result(gs)}; "
          f"exits {gs.scenario_state.get('exits')}")
for l in gs.log:
    if any(k in l for k in ("[Ambush]", "[Rescue]", "[Warp Storm]", "Rescue:", "caught unawares",
                             "Space Assault", "Station", "Platform", "Convoy:", "Transport", "Planet Strike", "Cruiser Clash", "Chance Encounter", "Raiders", "Blockade", "broke through", "Reinforcements", "Bait", "Rearguard", "Alien", "Surprise", "Sub-plot", "holds position", "DISENGAG", "off the table",
                             "isengag")):
        print("  LOG", l)
print(f"[{scenario} {system}] AA log lines: {len(aa_log)}; phases: "
      f"{sorted({p for _t, p in phases_seen})}")
ok = (panel._game_over and len(game_over) == 1 and not popups
      and not [d for d in dialogs if d[0] == "showerror"] and dice.mode == "mixed")
print(f"[{scenario} {system}] RESULT:", "OK" if ok else "FAIL")
sys.exit(0 if ok else 1)
