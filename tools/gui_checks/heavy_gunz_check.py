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
from src import combat_panel
from src.combat_dialog import _FireDialog
from src.tables import lookup_gunnery_dice, get_gunnery_column
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: False
class Dice:
    mode = "auto"
    def __init__(self, r): self.r, self.i = r, 0
    def roll_d6(self, n, label=""):
        out = self.r[self.i:self.i + n]; self.i += n; print(f"    roll {label!r}: {out}"); return out
    def roll_2d6(self, label=""): v = self.r[self.i]; self.i += 1; return v
HEAVY = {"name": "Heavy Gunz", "weapon_type": "battery", "strength": 6, "strength_close": 10,
         "range_cm": 30, "arcs": ["front", "left", "right"]}
def mk(id, player, x, heading, **kw):
    b = dict(id=id, name=id, ship_class="T", faction="orks", player=player, ship_type="cruiser",
             base_size="small", x=x, y=50.0, heading=heading, speed=20, turn_angle=45, shields_max=0,
             armor_prow="6+", armor_side="6+", turrets=2, hits_max=20, leadership=7, weapons=[],
             special_rules=[], upgrades=[], critical_damage=[])
    b.update(kw); return Ship(**b)
ok = True
for dist in (10.0, 20.0):
    root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
    gs.add_ship(mk("ork", 1, 50.0, 0.0, weapons=[HEAVY]))
    gs.add_ship(mk("target", 2, 50.0 + dist, 90.0))
    tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game(); gs.current_phase = "shooting"
    board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
    panel = GamePanel(f, tc, board, root)
    att = gs.get_ship_by_id("ork"); tgt = gs.get_ship_by_id("target")
    dlg = _FireDialog(panel.combat, att, [tgt], None, False, False, [], [(0, HEAVY)])
    dlg.run(); root.update()
    def walk(w):
        yield w
        for c in w.winfo_children(): yield from walk(c)
    labels = [w.cget("text") for w in walk(dlg.dialog) if isinstance(w, tk.Label)]
    entries = [w for w in walk(dlg.dialog) if isinstance(w, tk.Entry)]
    fp = 10 if dist < 15 else 6
    col = get_gunnery_column("capital", att.get_target_orientation(tgt))
    n = lookup_gunnery_dice(fp, col, -1 if dist < 15 else 0)
    panel.ctx.dice = Dice([1] * n); panel.combat.ctx.dice = panel.ctx.dice; dlg.ctx = panel.ctx
    dlg.weapon_assignments[0][3].set(dlg.target_options_per_weapon[0][0])
    dlg._fire_all()
    shown = any("(10 within 15cm)" in t for t in labels)
    print(f"{dist}cm: label shows close FP {shown}; split entry {bool(entries)}; dice {panel.ctx.dice.i} (expected {n} for FP{fp})")
    ok &= shown and bool(entries) and panel.ctx.dice.i == n   # split entry: Heavy Gunz split ruling
    root.destroy()
print("RESULT:", "OK" if ok else "FAIL")
