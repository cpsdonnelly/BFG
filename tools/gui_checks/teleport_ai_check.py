"""The AI decides its own teleport attacks in its end phase (s.31): no dialog
for a human; it raids the eligible target worth most per raid."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
for n in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, n, lambda *a, **k: None)
ASKED = []
messagebox.askyesno = lambda *a, **k: (ASKED.append(a), True)[1]
class Dice:
    mode = "auto"
    def roll_d6(self, n, label=""): return [4] * n
    def roll_2d6(self, label=""): return 7
    def roll_d3(self, label=""): return 2
def ship(i, player, x, hits, shields, pts):
    return Ship(id=i, name=i, ship_class="T", faction="imperial_navy_gothic", player=player,
                ship_type="cruiser", base_size="small", x=x, y=60.0, heading=90.0, speed=20,
                turn_angle=45, shields_max=shields, armor_prow="6+", armor_side="5+", turrets=2,
                hits_max=hits, leadership=8, weapons=[], special_rules=[], upgrades=[],
                critical_damage=[], points_value=pts)
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
gs.add_ship(ship("raider", 1, 50.0, 8, 2, 180))
gs.add_ship(ship("cheap", 2, 57.0, 6, 0, 60))
gs.add_ship(ship("prize", 2, 43.0, 6, 0, 240))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
gs.ai_player = 1; gs.active_player = 1; gs.current_phase = "end"
gs.rule_teleport = True        # teleport attacks are an optional rule (off by default)
gs.rule_hit_and_run = True     # and teleports are raids: both rules needed (owner)
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root)
LOG = []
orig = panel.ctx.log
panel.ctx.log = lambda t: (LOG.append(t), orig(t))
panel.ctx.dice = Dice()
panel.end_phase._resolve_teleport_attacks(); root.update()
lines = [t for t in LOG if "teleports against" in t]
attack_q = [a for a in ASKED if a and a[0] == "Teleport Attack"]   # (the human target may brace)
ok = not attack_q and len(lines) == 1 and "prize" in lines[0]
print("   ", lines, "attack dialogs:", len(attack_q))
print(("  ok   " if ok else "  FAIL ") + "AI teleported against the more valuable target, no dialog")
root.destroy()
print("RESULT: ALL OK" if ok else "RESULT: FAIL")
