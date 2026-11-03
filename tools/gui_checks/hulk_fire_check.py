import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
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
    def roll_2d6(self, label=""): v = self.r[self.i]; self.i += 1; print(f"    2d6 {label!r}: {v}"); return v
    def roll_d3(self, label=""): v = self.r[self.i]; self.i += 1; return v
GUN = {"name": "Battery", "weapon_type": "battery", "strength": 6, "range_cm": 45,
       "arcs": ["front", "left", "right"]}
def mk(id, player, x, **kw):
    b = dict(id=id, name=id, ship_class="T", faction="imperial_navy_gothic", player=player,
             ship_type="cruiser", base_size="small", x=x, y=50.0, heading=90.0, speed=20,
             turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=2,
             hits_max=8, leadership=7, weapons=[GUN], special_rules=[], upgrades=[], critical_damage=[])
    b.update(kw); return Ship(**b)
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
gs.add_ship(mk("me", 1, 20.0, heading=0.0))
hulk = mk("hulk", 2, 35.0); hulk.status = "drifting_hulk"; hulk.hits_remaining = 0
gs.add_ship(hulk); gs.add_ship(mk("behind", 2, 50.0))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game(); gs.current_phase = "shooting"
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root)
from src.combat_dialog import _FireDialog
att = gs.get_ship_by_id("me")
enemies = [gs.get_ship_by_id("hulk"), gs.get_ship_by_id("behind")]
# build via the real _fire_dialog filter
import src.combat_dialog as cd
seen = {}
orig = cd._FireDialog.__init__
def spy(self, panel_, attacker, enemies_, closest, *a, **k):
    seen["enemies"] = [e.name for e in enemies_]; seen["closest"] = closest.name if closest else None
    orig(self, panel_, attacker, enemies_, closest, *a, **k)
cd._FireDialog.__init__ = spy
panel.ctx.pick_ship = lambda ships, title: att
panel.combat._fire_dialog(); root.update()
print("   enemies offered:", seen.get("enemies"), "closest:", seen.get("closest"))
check(seen.get("enemies") == ["hulk", "behind"], "enemy hulk offered as a target")
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
inst = [o for o in __import__("gc").get_objects() if isinstance(o, cd._FireDialog)][-1]
opts = inst.target_options_per_weapon[0]
print("   options:", opts)
check(any(o.startswith("behind") and "NO LOS" in o and "hulk" in o for o in opts),
      "ship behind the hulk: no line of fire")
inst.weapon_assignments[0][3].set(next(o for o in opts if o.startswith("hulk")))
from src.tables import lookup_gunnery_dice, get_gunnery_column
n = lookup_gunnery_dice(6, get_gunnery_column("capital", att.get_target_orientation(gs.get_ship_by_id("hulk"))), 0)
dice = Dice([6] * n + [8]); panel.ctx.dice = dice; panel.combat.ctx.dice = dice; inst.ctx = panel.ctx
inst._log = lambda m: print("   log:", m)
print("   before:", gs.get_ship_by_id("hulk").status, gs.get_ship_by_id("hulk").hits_remaining)
inst._fire_all()
print("   after:", gs.get_ship_by_id("hulk").status, gs.get_ship_by_id("hulk").hits_remaining, gs.log[-3:])
h = gs.get_ship_by_id("hulk")
check(dice.i == n + 1 and h.status == "burning_hulk", f"hits on the hulk -> one catastrophic re-roll ({h.status})")
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
