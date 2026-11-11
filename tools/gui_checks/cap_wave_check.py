"""CAP meets a wave lead first before the turrets fire (s.26): 2 CAP fighters
remove the wave's fighter and first bomber; one bomber attacks."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship, OrdnanceMarker
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.waves import form_wave
for n in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: False
import src.choice_dialog as _cd
_cd.choose = lambda root, title, text, options, best: best
class Dice:
    mode = "auto"
    def __init__(self): self.calls = []
    def roll_d6(self, n, label=""):
        self.calls.append(label); return [1] * n
    def roll_2d6(self, label=""): self.calls.append(label); return 2
    def roll_d3(self, label=""): self.calls.append(label); return 1
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
gs.add_ship(Ship(id="t", name="Target", ship_class="T", faction="imperial_navy_gothic", player=2,
                 ship_type="cruiser", base_size="small", x=70.0, y=60.0, heading=90.0, speed=20,
                 turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=0,
                 hits_max=8, leadership=7, weapons=[], special_rules=[], upgrades=[],
                 critical_damage=[]))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
gs.active_player = 1; gs.current_phase = "ordnance"
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root)
def mk(i, kind, owner, x, cap=""):
    return OrdnanceMarker(id=i, ordnance_type=kind, owner_player=owner, launched_by="x",
                          x=x, y=60.0, heading=0.0, strength=1, speed=20, launched_turn=0,
                          cap_ship_id=cap).to_dict()
gs.ordnance = [mk("f1", "fighter", 1, 69.0), mk("b1", "bomber", 1, 69.0), mk("b2", "bomber", 1, 69.0),
               mk("c1", "fighter", 2, 70.0, cap="t"), mk("c2", "fighter", 2, 70.0, cap="t")]
form_wave(gs, ["f1", "b1", "b2"], "close")
for o in gs.ordnance:
    if o["id"] in ("f1", "b1", "b2"):
        o["craft_target_id"] = "t"; o["x"] = 55.0
LOG = []
orig = panel.ctx.log
panel.ctx.log = lambda t: (LOG.append(t), orig(t))
panel.ctx.dice = Dice()
panel.ordnance._resolve_ordnance_movement(); root.update()
attacks = [t for t in LOG if "attacks Target" in t]
cap_line = [t for t in LOG if "Target's CAP" in t]
ok = (not gs.ordnance and len(attacks) == 1 and cap_line
      and "2 of 2 lost, 2 of 3" in cap_line[0])
print("   ", cap_line, attacks)
print(("  ok   " if ok else "  FAIL ") + "CAP removed fighter + 1 bomber; one bomber attacked")
root.destroy()
print("RESULT: ALL OK" if ok else "RESULT: FAIL")
