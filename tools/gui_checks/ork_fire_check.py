import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship
import src.choice_dialog as _cd_yn
_cd_yn.yes_no = lambda root, title, text, best: messagebox.askyesno(title, text)
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.combat_dialog import _FireDialog
from src.tables import lookup_gunnery_dice, get_gunnery_column
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: False
failures = []
def check(c, label):
    print(("  ok   " if c else "  FAIL ") + label)
    if not c: failures.append(label)
class Dice:
    mode = "auto"
    def __init__(self, r): self.r, self.i = r, 0
    def roll_d6(self, n, label=""):
        out = self.r[self.i:self.i + n]; self.i += n; print(f"    roll {label!r}: {out}"); return out
    def roll_2d6(self, label=""): v = self.r[self.i]; self.i += 1; return v
    def roll_d3(self, label=""): v = self.r[self.i]; self.i += 1; return v
HEAVY = {"name": "Heavy Gunz", "weapon_type": "battery", "strength": 6, "strength_close": 10,
         "range_cm": 30, "arcs": ["front", "left", "right"]}
GUNZ = {"name": "Gunz", "weapon_type": "battery", "strength": 4, "strength_dice": "D6+1",
        "range_cm": 30, "arcs": ["front", "left", "right"]}
def mk(id, player, x, y=50.0, heading=0.0, **kw):
    b = dict(id=id, name=id, ship_class="T", faction="orks", player=player, ship_type="cruiser",
             base_size="small", x=x, y=y, heading=heading, speed=20, turn_angle=45, shields_max=0,
             armor_prow="6+", armor_side="6+", turrets=2, hits_max=20, leadership=7, weapons=[],
             special_rules=[], upgrades=[], critical_damage=[])
    b.update(kw); return Ship(**b)
def setup(weapon):
    root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
    gs.add_ship(mk("ork", 1, 50.0, weapons=[weapon]))
    gs.add_ship(mk("near", 2, 60.0, heading=90.0))           # 10cm, abeam
    gs.add_ship(mk("far", 2, 50.0, y=70.0, heading=0.0))     # 20cm, abeam
    tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game(); gs.current_phase = "shooting"
    board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
    panel = GamePanel(f, tc, board, root)
    return root, gs, panel
def fire(panel, gs, weapon, target_name, amount, rolls):
    att = gs.get_ship_by_id("ork")
    enemies = [s for s in gs.get_ships() if s.player == 2]
    dlg = _FireDialog(panel.combat, att, enemies, None, False, False, [], [(0, weapon)])
    dlg.run(); panel.ctx.root.update()
    opts = dlg.target_options_per_weapon[0]
    dlg.weapon_assignments[0][3].set(next(o for o in opts if o.startswith(target_name)))
    dlg.weapon_assignments[0][4].set(amount)
    d = Dice(rolls); panel.ctx.dice = d; panel.combat.ctx.dice = d; dlg.ctx = panel.ctx
    logs = []
    dlg._log = lambda m: (logs.append(m), print("   log:", m))
    dlg._fire_all()
    return d, logs
def ndice(fp, shift): return lookup_gunnery_dice(fp, get_gunnery_column("capital", "abeam"), shift)

print("1. Heavy Gunz: 3 at the far target, then the rest (3, the 15cm+ pool) at the near one")
root, gs, panel = setup(HEAVY)
n1 = ndice(3, 0)
d, _ = fire(panel, gs, HEAVY, "far", "3", [1] * n1)
check(d.i == n1, f"far shot FP3: {d.i} dice (expected {n1})")
a = gs.get_ship_by_id("ork")
check(a.weapons_remaining == {"0": 3} and a.weapon_pool_mode == {"0": "long"}, f"3 left, long pool: {a.weapons_remaining} {a.weapon_pool_mode}")
n2 = ndice(3, -1)
d, _ = fire(panel, gs, HEAVY, "near", "all", [1] * n2)
check(d.i == n2, f"near shot FP3 (not 10-3): {d.i} dice (expected {n2})")
root.destroy()

print("2. Heavy Gunz: 5 of 10 at the near target, then the far target is refused")
root, gs, panel = setup(HEAVY)
n1 = ndice(5, -1)
d, _ = fire(panel, gs, HEAVY, "near", "5", [1] * n1)
check(d.i == n1, f"near shot FP5 of 10: {d.i} dice (expected {n1})")
d, logs = fire(panel, gs, HEAVY, "far", "all", [1] * 10)
check(d.i == 0 and any("far target first" in m for m in logs), "far shot refused, no dice")
check(gs.get_ship_by_id("ork").weapons_remaining == {"0": 5}, "still 5 left for near targets")
root.destroy()

print("3. Onslaught Gunz FP D6+1 rolled when fired")
root, gs, panel = setup(GUNZ)
n = ndice(5, 0)
d, logs = fire(panel, gs, GUNZ, "far", "all", [4] + [1] * n)
check(d.i == 1 + n and any("rolled D6+1 = 5" in m for m in logs), f"rolled 4+1=5, then {n} gunnery dice")
check(gs.get_ship_by_id("ork").weapons_remaining == {"0": 0}, "weapon spent")
root.destroy()
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
