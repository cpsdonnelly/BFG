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
class Dice:
    mode = "auto"
    def __init__(self, r): self.r, self.i = r, 0
    def roll_d6(self, n, label=""):
        out = self.r[self.i:self.i + n]; self.i += n; print(f"    roll {label!r}: {out}"); return out
    def roll_2d6(self, label=""): v = self.r[self.i]; self.i += 1; return v
    def roll_d3(self, label=""): v = self.r[self.i]; self.i += 1; return v
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
d = find_ship_class("Strike Cruiser").to_ship_dict("Spear", 1, ship_id="sc")
d.update(x=50.0, y=50.0, heading=90.0, leadership=9)
d["special_rules"].append("chapter_tactic:siege_cannons")
gs.add_ship(Ship.from_dict(d))
gs.add_ship(Ship(id="t", name="Heretic", ship_class="T", faction="chaos", player=2, ship_type="cruiser",
                 base_size="small", x=70.0, y=50.0, heading=90.0, speed=20, turn_angle=45,
                 shields_max=0, armor_prow="6+", armor_side="6+", turrets=2, hits_max=20,
                 leadership=7, weapons=[], special_rules=[], upgrades=[], critical_damage=[]))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game(); gs.current_phase = "shooting"
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root)
att = gs.get_ship_by_id("sc"); tgt = gs.get_ship_by_id("t")
# Starboard macrobatteries (target is to the right of a north-facing ship) + prow BC FP3
ws = [(i, w) for i, w in enumerate(att.weapons) if w["name"] in ("Starboard Macrobatteries", "Prow Bombardment Cannon")]
print([w["name"] for _, w in ws], "target arc:", att.get_target_arc(tgt.x, tgt.y))
dlg = _FireDialog(panel.combat, att, [tgt], None, False, False, [], ws)
dlg.run(); root.update()
for k, (w_idx, w, en, tv, sv, av) in enumerate(dlg.weapon_assignments):
    tv.set(dlg.target_options_per_weapon[w_idx][0])
print("options:", [dlg.target_options_per_weapon[i][0] for i, _ in ws])
n = lookup_gunnery_dice(7, get_gunnery_column("capital", att.get_target_orientation(tgt)), 0)
rolls = [4] * n + [1] * 20
dice = Dice(rolls); panel.ctx.dice = dice; panel.combat.ctx.dice = dice; dlg.ctx = panel.ctx
logs = []; dlg._log = lambda m: (logs.append(m), print("   log:", m))
dlg._fire_all()
ok = any("Siege Cannons: FP 4+3" in m for m in logs)
print("RESULT:", "OK" if ok else "FAIL")
