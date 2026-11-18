"""Fire dialog (owner ruling, s.11 / s.13): a ship's two batteries at one
target make ONE Gunnery table roll on FP 8; the "fire different gunnery
weapons together" box appears only for a ship with two gunnery types."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship
import src.choice_dialog as cd
cd.yes_no = lambda root, title, text, best: False          # nobody braces
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.combat_dialog import _FireDialog
from src.tables import lookup_gunnery_dice
from src.combat import get_gunnery_column, gunnery_target_type
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: False
class Dice:
    mode = "auto"
    def __init__(self): self.calls = []
    def roll_d6(self, n, label=""): self.calls.append((n, label)); return [6] * n
    def roll_2d6(self, label=""): return 7
B1 = {"name": "Prow Battery", "weapon_type": "battery", "strength": 4, "range_cm": 45, "arcs": ["front"]}
B2 = dict(B1, name="Dorsal Battery")
BC = {"name": "Bombardment Cannon", "weapon_type": "battery", "strength": 3, "range_cm": 30,
      "arcs": ["front"], "hits_on": 4, "crit_on": 4}
def mk(id, player, x, weapons, **kw):
    d = dict(id=id, name=id, ship_class="T", faction="imperial_navy_gothic", player=player,
             ship_type="cruiser", base_size="small", x=x, y=50.0, heading=0.0 if player == 1 else 180.0,
             speed=20, turn_angle=45, shields_max=0, armor_prow="6+", armor_side="5+", turrets=2,
             hits_max=20, leadership=7, weapons=weapons, special_rules=[], upgrades=[], critical_damage=[])
    d.update(kw); return Ship(**d)
fails = []
for weapons, want_box in (([B1, B2], False), ([B1, B2, BC], True)):
    root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
    gs.add_ship(mk("att", 1, 50.0, weapons)); gs.add_ship(mk("tgt", 2, 70.0, []))
    tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game(); gs.current_phase = "shooting"
    board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
    panel = GamePanel(f, tc, board, root)
    att, tgt = gs.get_ship_by_id("att"), gs.get_ship_by_id("tgt")
    dlg = _FireDialog(panel.combat, att, [tgt], tgt, False, False, gs.get_blast_markers(),
                      list(enumerate(weapons)))
    dlg.run(); root.update()
    boxes = [w for w in dlg.dialog.winfo_children() if isinstance(w, tk.Checkbutton)]
    if bool(boxes) != want_box:
        fails.append(f"together box shown={bool(boxes)} want {want_box}")
    dice = Dice(); panel.ctx.dice = dice; dlg.ctx = panel.ctx
    dlg._fire_all(); root.update()
    rolls = [n for n, lbl in dice.calls if "batteries vs" in lbl]
    col = get_gunnery_column(gunnery_target_type(tgt), att.get_target_orientation(tgt))
    want = lookup_gunnery_dice(8, col, 0)
    if not rolls or rolls[0] != want:
        fails.append(f"first battery roll {rolls} want {want} dice (FP 4 + 4)")
    if want_box and len(rolls) != 2:
        fails.append(f"bombardment cannon should roll separately: {rolls}")
    print(f"  weapons {len(weapons)}: battery rolls {rolls} (FP8 -> {want}), box {bool(boxes)}")
    root.withdraw()
print("RESULT:", "ALL OK" if not fails else "FAIL " + "; ".join(fails))
