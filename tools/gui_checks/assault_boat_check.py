"""Assault boats must survive turrets before raiding (core rules s.20, s.23)."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG")
os.chdir(tempfile.mkdtemp())

from src.models import Ship
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.ordnance import launch_attack_craft

for n in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: False          # target declines to brace


class Dice:
    def __init__(self, rolls): self.rolls, self.i, self.mode = rolls, 0, "auto"
    def _n(self):
        v = self.rolls[self.i]; self.i += 1; return v
    def roll_d6(self, n, label=""):
        out = [self._n() for _ in range(n)]
        print(f"    roll {label!r}: {out}")
        return out
    def roll_2d6(self, label=""): return self._n()
    def roll_d3(self, label=""): return self._n()


def ship(id, player, x, heading, **kw):
    base = dict(id=id, name=id, ship_class="T", faction="imperial_navy_gothic", player=player,
                ship_type="cruiser", base_size="small", x=x, y=60.0, heading=heading, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=2,
                hits_max=8, leadership=7, upgrades=[], critical_damage=[], special_rules=[],
                weapons=[{"name": "Prow Torps", "weapon_type": "torpedo", "strength": 6,
                          "range_cm": 30, "arcs": ["front"]}])
    base.update(kw)
    return Ship(**base)


root = tk.Tk()
gs = GameState()
gs.rule_hit_and_run = True
gs.dice_mode = "auto"
target = ship("target", 1, 60.0, 0.0)
carrier = ship("carrier", 2, 20.0, 0.0, weapons=[{"name": "Bays", "weapon_type": "launch_bay",
                                                  "strength": 2}])
gs.add_ship(target)
gs.add_ship(carrier)
tc = TurnController(gs, DiceRoller(mode="auto"))
tc.start_game()
board = BoardView(root, gs)
frame = tk.Frame(board.side_panel); frame.pack()
panel = GamePanel(frame, tc, board, root)

# Two Shark squadrons 30cm (one move) short of the target, flying straight at it
boats = launch_attack_craft(gs.get_ship_by_id("carrier"), carrier.weapons[0],
                            "shark_assault_boat", 2, gs)
for i, b in enumerate(gs.ordnance):
    gs.ordnance[i] = {**b, "x": 30.0, "y": 60.0 + 0.5 * i, "heading": 0.0}
from src.waves import form_wave
form_wave(gs, [b.id for b in boats], "close")          # launched as one wave (s.25)
gs.active_player = 2
gs.current_phase = "ordnance"

rolls = [
    4, 1,   # target's 2 turrets vs the wave: one 4+ -> one assault boat destroyed
    5,      # surviving squadron's single hit-and-run raid: 5 -> Prow Armament damaged
]
dice = Dice(rolls)
panel.ctx.dice = dice
panel.ordnance.ctx.dice = dice

panel.ordnance._resolve_ordnance_movement()

t = gs.get_ship_by_id("target")
crits = [c["crit_type"] for c in t.critical_damage]
print("dice used:", dice.i, "of", len(rolls))
print("target crits:", crits, "| ordnance left:", [o["ordnance_type"] for o in gs.ordnance])
ok = dice.i == len(rolls) and crits == ["prow_armament"] and gs.ordnance == []
print("RESULT:", "OK" if ok else "FAIL")
sys.exit(0 if ok else 1)
