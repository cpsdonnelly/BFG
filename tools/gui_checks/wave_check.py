"""Waves of attack craft through the real panels: launch as a wave, one blast
roll, one turret roll for the wave, fighter suppression, whole wave removed."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG")
os.chdir(tempfile.mkdtemp())

from src.models import Ship, OrdnanceMarker, BlastMarker
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel

for n in ("showinfo", "showwarning"):
    setattr(messagebox, n, lambda *a, **k: None)
messagebox.showerror = lambda *a, **k: print("   [error]", a)
messagebox.askyesno = lambda *a, **k: False

failures = []
def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond: failures.append(label)


class Dice:
    def __init__(self, rolls): self.rolls, self.i, self.mode = rolls, 0, "auto"
    def _n(self):
        v = self.rolls[self.i]; self.i += 1; return v
    labels = []
    def roll_d6(self, n, label=""):
        out = [self._n() for _ in range(n)]; print(f"    roll {label!r}: {out}")
        Dice.labels.append((label, n)); return out
    def roll_2d6(self, label=""):
        v = self._n(); print(f"    roll {label!r}: {v}"); return v
    def roll_d3(self, label=""):
        v = self._n(); print(f"    roll {label!r}: {v}"); return v


def ship(id, player, x, heading, **kw):
    base = dict(id=id, name=id, ship_class="T", faction="imperial_navy_gothic", player=player,
                ship_type="cruiser", base_size="small", x=x, y=60.0, heading=heading, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=2,
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
gs.dice_mode = "auto"
bays = {"name": "Launch Bays", "weapon_type": "launch_bay", "strength": 4,
        "craft_types": ["fury_fighter", "starhawk_bomber"], "arcs": []}
gs.add_ship(ship("carrier", 1, 20.0, 0.0, weapons=[bays]))
gs.add_ship(ship("target", 2, 80.0, 90.0))
tc = TurnController(gs, DiceRoller(mode="auto"))
tc.start_game()
gs.active_player = 1
gs.current_phase = "shooting"
board = BoardView(root, gs)
frame = tk.Frame(board.side_panel); frame.pack()
panel = GamePanel(frame, tc, board, root)

print("1. Launch 2 fighters + 2 bombers as one close wave")
panel.ordnance._launch_ordnance_dialog(preselected_ship=gs.get_ship_by_id("carrier"))
root.update()
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
entries = {}
for w in walk(dlg):
    if isinstance(w, tk.Entry) and isinstance(w.master, tk.Frame):
        ls = [c.cget("text") for c in w.master.winfo_children() if isinstance(c, tk.Label)]
        if ls: entries[ls[0]] = w
print("   rows:", list(entries))
for key, n in (("Fury", "2"), ("Starhawk", "2")):
    e = next(v for k, v in entries.items() if k.startswith(key))
    e.delete(0, tk.END); e.insert(0, n)
check(any(isinstance(w, tk.Checkbutton) and w.cget("text") == "Launch as one wave"
          for w in walk(dlg)), "wave option shown")
[b for b in walk(dlg) if isinstance(b, tk.Button) and b.cget("text") == "Launch Attack Craft"][0].invoke()
root.update()
w = sorted((OrdnanceMarker.from_dict(o) for o in gs.ordnance), key=lambda m: m.wave_order)
check(len(w) == 4 and len({m.wave_id for m in w}) == 1 and w[0].wave_id,
      f"one wave of four: {[(m.ordnance_type, m.wave_order) for m in w]}")
check([m.ordnance_type for m in w][:2] == ["fighter", "fighter"], "fighters lead")
check(len({(m.x, m.y) for m in w}) == 1, "stacked on the lead")

print("2. Ordnance phase: moves at 20cm (bombers), one blast marker roll, attacks")
gs.current_phase = "ordnance"
for i, o in enumerate(gs.ordnance):
    gs.ordnance[i] = {**o, "x": 60.0, "y": 60.0, "heading": 0.0}
gs.add_blast_marker(BlastMarker(id="bm", x=80.0, y=60.0))   # where the wave ends up
dice = Dice([3, 4, 1] + [1] * 30)   # blast: survives; turrets: one success
panel.ctx.dice = dice
panel.ordnance._resolve_ordnance_movement()
labels = Dice.labels
blast = [l for l in labels if "blast marker" in l[0]]
turrets = [l for l in labels if "interception" in l[0]]
attack_rolls = [l for l in labels if l[0].startswith("Bomber attacks")]
hits = [l for l in labels if l[0].startswith("Bomber hits")]
check(len(blast) == 1, f"one blast marker roll for the wave: {blast}")
check(turrets == [(turrets[0][0], 2)] and "4 attack craft" in turrets[0][0],
      f"turrets fire once at all four: {turrets}")
check(len(attack_rolls) == 1, "only the unsuppressed bomber rolls its attacks")
check(hits and hits[0][1] == 3 and len(hits) == 1,
      f"suppressed bomber makes exactly 3 attacks; the other rolled 1 - 2 turrets = 0: {hits}")
check(gs.ordnance == [], f"whole wave removed: {[o['ordnance_type'] for o in gs.ordnance]}")
board.redraw()
root.destroy()
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
