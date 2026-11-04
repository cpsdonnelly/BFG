"""Short burn torpedoes and barrage bombs through the real panels: the launch
dialog offers the bought type, short burn salvos move 40cm and may run out of
fuel, barrage bombs are stopped by shields."""
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

for n in ("showinfo", "showwarning"):
    setattr(messagebox, n, lambda *a, **k: None)
messagebox.showerror = lambda *a, **k: print("   [error]", a)
messagebox.askyesno = lambda *a, **k: False          # nobody braces

failures = []
def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond: failures.append(label)


class Dice:
    def __init__(self, rolls): self.rolls, self.i, self.mode = rolls, 0, "auto"
    def _n(self):
        v = self.rolls[self.i]; self.i += 1; return v
    def roll_d6(self, n, label=""):
        out = [self._n() for _ in range(n)]; print(f"    roll {label!r}: {out}"); return out
    def roll_2d6(self, label=""):
        v = self._n(); print(f"    roll {label!r}: {v}"); return v
    def roll_d3(self, label=""): return self._n()


def ship(id, player, x, heading, **kw):
    base = dict(id=id, name=id, ship_class="T", faction="imperial_navy_gothic", player=player,
                ship_type="cruiser", base_size="small", x=x, y=60.0, heading=heading, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=0,
                hits_max=8, leadership=7, upgrades=[], critical_damage=[], special_rules=[],
                weapons=[])
    base.update(kw)
    return Ship(**base)


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


root = tk.Tk()
gs = GameState()
gs.rule_hit_and_run = True
gs.dice_mode = "auto"
torps = {"name": "Prow Torps", "weapon_type": "torpedo", "strength": 6, "range_cm": 30,
         "arcs": ["front"], "torpedo_type": "standard", "torpedo_speed": 30}
gs.add_ship(ship("lunar", 1, 20.0, 0.0, special_rules=["torpedo_type:short_burn"],
                 weapons=[torps]))
gs.add_ship(ship("target", 2, 95.0, 90.0))
tc = TurnController(gs, DiceRoller(mode="auto"))
tc.start_game()
gs.active_player = 1
gs.current_phase = "shooting"
board = BoardView(root, gs)
frame = tk.Frame(board.side_panel); frame.pack()
panel = GamePanel(frame, tc, board, root)

print("1. Launch dialog offers short burn torpedoes")
panel.ordnance._launch_ordnance_dialog(preselected_ship=gs.get_ship_by_id("lunar"))
root.update()
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
radios = [w.cget("text") for w in walk(dlg) if isinstance(w, tk.Radiobutton)]
check(radios == ["Standard torpedoes", "Short burn torpedoes (40cm, out of fuel on a 6)"],
      f"loads: {radios}")
[r for r in walk(dlg) if isinstance(r, tk.Radiobutton) and "Short" in r.cget("text")][0].invoke()
[b for b in walk(dlg) if isinstance(b, tk.Button)
 and b.cget("text").startswith("Launch Torp")][0].invoke()
root.update()
check([(o["ordnance_type"], o["speed"]) for o in gs.ordnance] == [("torpedo_short_burn", 40)],
      f"marker: {[(o['ordnance_type'], o['speed']) for o in gs.ordnance]}")

print("2. Ordnance phase: moves 40cm, misses nothing, then the fuel roll")
gs.current_phase = "ordnance"
x0 = gs.ordnance[0]["x"]
dice = Dice([6])                       # out of fuel
panel.ctx.dice = dice
panel.ordnance._resolve_ordnance_movement()
check(dice.i == 1, f"one fuel roll ({dice.i})")
check(gs.ordnance == [], "salvo removed")
bms = gs.get_blast_markers()
check(len(bms) == 1 and abs(bms[0].x - (x0 + 40)) < 0.01,
      f"blast marker where it stopped: {[(round(b.x, 2), b.y) for b in bms]}")

print("3. Barrage bombs hit the target: shields stop the hits")
gs.blast_markers = []
gs.ordnance = [{"id": "bb", "ordnance_type": "torpedo_barrage", "owner_player": 1,
                "launched_by": "lunar", "x": 80.0, "y": 60.0, "heading": 0.0, "strength": 3,
                "speed": 30.0, "launched_turn": gs.turn_number - 1, "wave_id": "",
                "cap_ship_id": "", "resilient_save": 0, "resilient_used": False,
                "can_turn": False, "turn_angle": 0, "special_rules": [],
                "moved_this_phase": False, "launch_exempt_ships": []}]
rolls = [6, 5, 5]                      # three hits vs 5+; both shields stop two, one damage
rolls += [3]                           # crit check
dice = Dice(rolls)
panel.ctx.dice = dice
panel.ordnance._resolve_ordnance_movement()
t = gs.get_ship_by_id("target")
check(dice.i == len(rolls), f"dice used {dice.i}/{len(rolls)}")
check(t.hits_remaining == 7, f"one damage gets through ({t.hits_remaining}/8)")
check(len(gs.get_blast_markers()) == 2, f"two shield impacts ({len(gs.get_blast_markers())})")
print("   ordnance after:", [(o["ordnance_type"], round(o["x"],1), o["strength"]) for o in gs.ordnance]); print("   bms", len(gs.get_blast_markers()))
root.destroy()
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
