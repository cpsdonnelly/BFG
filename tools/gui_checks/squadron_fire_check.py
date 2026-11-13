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
from src.combat import allocate_squadron_hits
from src import combat_panel
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: False      # targets decline to brace
combat_panel.messagebox = messagebox
class Dice:
    mode = "auto"
    def __init__(self, r): self.r, self.i = r, 0
    def roll_d6(self, n, label=""):
        out = self.r[self.i:self.i + n]; self.i += n; return out
    def roll_2d6(self, label=""): v = self.r[self.i]; self.i += 1; return v
def ship(id, x, **kw):
    b = dict(id=id, name=id, ship_class="Sword", faction="imperial_navy_gothic", player=2, ship_type="escort",
             base_size="small", x=x, y=60.0, heading=0.0, speed=25, turn_angle=90, shields_max=1,
             armor_prow="5+", armor_side="4+", turrets=2, hits_max=1, leadership=7, weapons=[],
             special_rules=[], upgrades=[], critical_damage=[], squadron_id="sq"); b.update(kw); return Ship(**b)
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
attacker = Ship(id="att", name="att", ship_class="T", faction="imperial_navy_gothic", player=1, ship_type="cruiser",
                base_size="small", x=10.0, y=60.0, heading=0.0, speed=20, turn_angle=45, shields_max=2,
                armor_prow="6+", armor_side="5+", turrets=2, hits_max=8, leadership=7, weapons=[],
                special_rules=[], upgrades=[], critical_damage=[])
gs.add_ship(attacker); gs.add_ship(ship("e1", 30.0)); gs.add_ship(ship("e2", 50.0)); gs.add_ship(ship("e3", 70.0))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root)
panel.ctx.dice = Dice([]); panel.combat.ctx.dice = panel.ctx.dice
log = []
def apply_to(m, n):
    fresh = gs.get_ship_by_id(m.id)
    if not fresh or fresh.is_destroyed: return n, True
    return panel.combat._apply_hits_to_target(gs.get_ship_by_id("att"), fresh, n, log.append)
eligible = [gs.get_ship_by_id(i) for i in ("e1", "e2", "e3")]
applied = allocate_squadron_hits([5] * 5, eligible, lambda m: 4, apply_to)
status = {i: gs.get_ship_by_id(i).status for i in ("e1", "e2", "e3")}
print("applied:", applied, "| status:", status, "| wrecks:", sorted(b["id"] for b in gs.blast_markers if b["id"].startswith("wreck")))
ok = applied == {"e1": 2, "e2": 2, "e3": 1} and status["e1"] == status["e2"] == "destroyed" and status["e3"] == "active"
print("RESULT:", "OK" if ok else "FAIL")
