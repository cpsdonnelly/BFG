"""Remastered turret suppression (p.82) through the real ordnance phase: an
Emperor-style wave of 5 fighters + 3 bombers hits a 3-turret ship, no CAP;
the turrets kill three fighters; each bomber rolls D6 - 3 and the wave gets
+3 bonus attacks (5 fighters capped at 3 bombers), added once."""
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
    def roll_d6(self, n, label=""):
        if "interception" in label:
            return [4] * n                 # every turret die hits: 3 kills
        if "Bomber attacks" in label:
            return [5] * n                 # 5 - 3 turrets = 2 each
        return [1] * n                     # all to-hit dice miss (no damage)
    def roll_2d6(self, label=""): return 7
    def roll_d3(self, label=""): return 1
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
gs.rule_turret_suppression_remastered = True
gs.add_ship(Ship(id="t", name="Devastation", ship_class="T", faction="chaos", player=2,
                 ship_type="cruiser", base_size="small", x=70.0, y=60.0, heading=90.0, speed=20,
                 turn_angle=45, shields_max=2, armor_prow="5+", armor_side="5+", turrets=3,
                 hits_max=8, leadership=7, weapons=[], special_rules=[], upgrades=[],
                 critical_damage=[]))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
gs.active_player = 1; gs.current_phase = "ordnance"
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root)
def mk(i, kind):
    return OrdnanceMarker(id=i, ordnance_type=kind, owner_player=1, launched_by="x",
                          x=69.0, y=60.0, heading=0.0, strength=1, speed=20,
                          launched_turn=0).to_dict()
ids = [f"f{i}" for i in range(5)] + [f"b{i}" for i in range(3)]
gs.ordnance = [mk(i, "fighter" if i[0] == "f" else "bomber") for i in ids]
form_wave(gs, ids, "close")
for o in gs.ordnance:
    o["craft_target_id"] = "t"; o["x"] = 55.0
LOG = []
orig = panel.ctx.log
panel.ctx.log = lambda t: (LOG.append(t), orig(t))
panel.ctx.dice = Dice()
panel.ordnance._resolve_ordnance_movement(); root.update()
killed = [t for t in LOG if "destroyed by turrets" in t]
bonus_line = [t for t in LOG if "fighter(s) in the wave add" in t]
attacks = [t for t in gs.log if "Remastered suppression: roll" in str(t)]
xr_line = [t for t in LOG if "suppress turrets for" in t]     # the XR message: not here
ok = (not xr_line and len(killed) == 3 and all("fighter" in t for t in killed)
      and bonus_line and "add 3 attack(s)" in bonus_line[0]
      and len(attacks) == 1 and "+ 3 from the wave's fighters = 5 attacks" in str(attacks[0]))
print("   ", killed, bonus_line, attacks)
print(("  ok   " if ok else "  FAIL ") + "turrets took 3 fighters; +3 bonus attacks added once")
root.destroy()
print("RESULT: ALL OK" if ok else "RESULT: FAIL")
