import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.combat_dialog import _FireDialog
from src.ship_catalog import find_ship_class
from src.tables import lookup_gunnery_dice, get_gunnery_column
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: False
failures = []
def check(c, label):
    print(("  ok   " if c else "  FAIL ") + label)
    if not c: failures.append(label)
class Dice:
    mode = "auto"
    def __init__(self, r): self.r, self.i, self.labels = r, 0, []
    def roll_d6(self, n, label=""):
        out = self.r[self.i:self.i + n]; self.i += n; self.labels.append((label, out)); print(f"    roll {label!r}: {out}"); return out
    def roll_2d6(self, label=""): v = self.r[self.i]; self.i += 1; self.labels.append((label, v)); return v
    def roll_d3(self, label=""): v = self.r[self.i]; self.i += 1; return v
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
d = find_ship_class("Strike Cruiser").to_ship_dict("Spear of Vengeance", 1, ship_id="sc")
d.update(x=50.0, y=50.0, heading=0.0, leadership=9)
gs.add_ship(Ship.from_dict(d))
gs.add_ship(Ship(id="t", name="Heretic", ship_class="T", faction="chaos", player=2, ship_type="cruiser",
                 base_size="small", x=70.0, y=50.0, heading=180.0, speed=20, turn_angle=45,
                 shields_max=0, armor_prow="6+", armor_side="5+", turrets=2, hits_max=20,
                 leadership=7, weapons=[], special_rules=[], upgrades=[], critical_damage=[]))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game(); gs.current_phase = "shooting"
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root)
att = gs.get_ship_by_id("sc"); tgt = gs.get_ship_by_id("t")
weapons = [(i, w) for i, w in enumerate(att.weapons) if w["weapon_type"] == "battery"
           and ("Prow" in w["name"])]
print("1. Prow Bombardment Cannon at a closing 6+ prow target 20cm away")
dlg = _FireDialog(panel.combat, att, [tgt], None, False, False, [], weapons)
dlg.run(); root.update()
dlg.weapon_assignments[0][3].set(dlg.target_options_per_weapon[weapons[0][0]][0]) if isinstance(dlg.target_options_per_weapon, dict) and weapons[0][0] in dlg.target_options_per_weapon else dlg.weapon_assignments[0][3].set(list(dlg.target_options_per_weapon.values())[0][0])
n = lookup_gunnery_dice(3, get_gunnery_column("capital", "closing"), 0)
rolls = [4] * n + [4] * n + [6] * n     # all hit on 4+; crit checks 4+ all crit; 2D6 crit table 6s
dice = Dice(rolls + [1] * 20); panel.ctx.dice = dice; panel.combat.ctx.dice = dice; dlg.ctx = panel.ctx
dlg._fire_all()
t = gs.get_ship_by_id("t")
crit_checks = [l for l, _ in dice.labels if "Crit check" in l]
print("   crit checks:", crit_checks[:1])
check(t.hits_remaining <= 20 - n, f"{n} hits on a 6+ prow target with 4s (hits left {t.hits_remaining})")
check(crit_checks and "(4+)" in crit_checks[0] and len(t.critical_damage) >= 1, "crit checks on 4+, crits applied")
root.destroy()

print("2. Vanguard Cruiser All Ahead Full rolls 5D6 (Improved Thrusters)")
from src.movement import resolve_aaf_speed
v = Ship.from_dict(find_ship_class("Vanguard Cruiser").to_ship_dict("V", 1))
dice = Dice([1, 2, 3, 4, 5])
check(resolve_aaf_speed(v, dice) == 15 and dice.i == 5, "5 dice")
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
