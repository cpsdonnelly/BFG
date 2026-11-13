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
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: False
combat_panel.messagebox = messagebox
class Dice:
    mode = "auto"
    def __init__(self, r): self.r, self.i = r, 0
    def roll_d6(self, n, label=""):
        out = self.r[self.i:self.i + n]; self.i += n; return out
    def roll_2d6(self, label=""): v = self.r[self.i]; self.i += 1; return v
WEAPON = {"name": "Port Battery", "weapon_type": "battery", "strength": 4, "range_cm": 30,
          "arcs": ["front", "left", "right"]}
def ship(id, x, y, heading, player=2, **kw):
    b = dict(id=id, name=id, ship_class="Sword", faction="imperial_navy_gothic", player=player,
             ship_type="escort", base_size="small", x=x, y=y, heading=heading, speed=25, turn_angle=90,
             shields_max=0, armor_prow="4+", armor_side="4+", turrets=1, hits_max=1, leadership=7,
             weapons=[], special_rules=[], upgrades=[], critical_damage=[], squadron_id="sq")
    b.update(kw); return Ship(**b)
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
att = Ship(id="att", name="Gothic", ship_class="T", faction="imperial_navy_gothic", player=1,
           ship_type="cruiser", base_size="small", x=50.0, y=50.0, heading=0.0, speed=20, turn_angle=45,
           shields_max=2, armor_prow="6+", armor_side="5+", turrets=2, hits_max=8, leadership=7,
           weapons=[WEAPON], special_rules=[], upgrades=[], critical_damage=[])
gs.add_ship(att)
gs.add_ship(ship("Sword A", 57.0, 50.0, 180.0))     # closing, 7cm
gs.add_ship(ship("Sword B", 50.0, 58.0, 0.0))       # abeam, 8cm
gs.add_ship(ship("Sword C", 40.0, 50.0, 0.0))       # behind: out of arc
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game(); gs.current_phase = "shooting"
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root)
enemies = [s for s in gs.get_ships() if s.player == 2]
dlg = _FireDialog(panel.combat, gs.get_ship_by_id("att"), enemies, None, False, False,
                  gs.get_blast_markers(), [(0, WEAPON)])
dlg.run(); root.update()
opts = dlg.target_options_per_weapon[0]
print("TARGET OPTIONS:"); [print("  " + o) for o in opts]
opt_b = next(o for o in opts if o.startswith("Sword B"))
menu = [w for w in dlg.dialog.winfo_children()[2].winfo_children()[1].winfo_children() if isinstance(w, tk.Menubutton)][0]
dlg.weapon_assignments[0][3].set(opt_b)
menu.event_generate("<Enter>"); root.update()
tips = [w for w in menu.winfo_children() if isinstance(w, tk.Toplevel)]
print("HOVER TOOLTIP WINDOW SHOWN:", bool(tips))
menu.event_generate("<Leave>"); root.update()
print("TOOLTIP for Sword B:"); print(dlg._squadron_tooltip(WEAPON, opt_b, None))
# Fire at Sword B's (abeam) aspect: 1 die, a 5 -> the hit goes to the nearest eligible ship, Sword A
panel.ctx.dice = Dice([5]); panel.combat.ctx.dice = panel.ctx.dice; dlg.ctx = panel.ctx
dlg.weapon_assignments[0][3].set(opt_b)
dlg._fire_all()
st = {i: gs.get_ship_by_id(i).status for i in ("Sword A", "Sword B", "Sword C")}
print("AFTER FIRE:", st)
ok = (st == {"Sword A": "destroyed", "Sword B": "active", "Sword C": "active"}
      and "abeam: hits can go to 2/3 squadron members" in opt_b)
print("RESULT:", "OK" if ok else "FAIL")
