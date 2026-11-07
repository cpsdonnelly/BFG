"""Combined squadron fire through the real dialog (s.8): different aspects
make separate gunnery lookups and one attack per Armour value; firing at a
squadron offers an aspect choice and allocates hits nearest first."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox, ttk
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
messagebox.askyesno = lambda *a, **k: False          # no braces

failures = []
def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond: failures.append(label)


class Dice:
    labels = []
    def __init__(self, rolls): self.rolls, self.i, self.mode = rolls, 0, "auto"
    def _n(self):
        v = self.rolls[self.i]; self.i += 1; return v
    def roll_d6(self, n, label=""):
        out = [self._n() for _ in range(n)]; print(f"    roll {label!r}: {out}")
        Dice.labels.append((label, n)); return out
    def roll_2d6(self, label=""): return self._n()
    def roll_d3(self, label=""): return self._n()


BAT = {"name": "Macrobatteries", "weapon_type": "battery", "strength": 4, "range_cm": 30,
       "arcs": ["front", "left", "right", "rear"]}


def ship(id, player, x, y, heading, **kw):
    base = dict(id=id, name=id, ship_class="T", faction="imperial_navy_gothic", player=player,
                ship_type="escort", base_size="small", x=x, y=y, heading=heading, speed=25,
                turn_angle=90, shields_max=1, armor_prow="5+", armor_side="5+", turrets=1,
                hits_max=1, leadership=8, upgrades=[], critical_damage=[], special_rules=[],
                weapons=[dict(BAT)], squadron_id="sq1")
    base.update(kw)
    return Ship(**base)


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def build(ships):
    root = tk.Tk()
    gs = GameState()
    gs.dice_mode = "auto"
    for s in ships:
        gs.add_ship(s)
    tc = TurnController(gs, DiceRoller(mode="auto"))
    tc.start_game()
    gs.active_player = 1
    gs.current_phase = "shooting"
    board = BoardView(root, gs)
    frame = tk.Frame(board.side_panel); frame.pack()
    return root, gs, GamePanel(frame, tc, board, root)


print("1. Two frigates, one ahead of a cruiser and one behind: two attacks")
cruiser = dict(ship_type="cruiser", hits_max=8, shields_max=0, armor_prow="6+",
               armor_side="5+", squadron_id="", weapons=[])
root, gs, panel = build([ship("f_front", 1, 70.0, 50.0, 180.0),
                         ship("f_back", 1, 30.0, 50.0, 0.0),
                         ship("target", 2, 50.0, 50.0, 0.0, **cruiser)])
picks = iter(["f_front", "target"])
panel.ctx.pick_ship = lambda cands, title="": next(
    (c for c in cands if c.id == next(picks)), None)
panel.combat._combine_squadron_fire_dialog()
root.update()
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
dice = Dice([6] * 20)
panel.ctx.dice = dice
[b for b in walk(dlg) if isinstance(b, tk.Button) and b.cget("text") == "Fire!"][0].invoke()
root.update()
volleys = [l for l in Dice.labels if l[0].startswith("Squadron volley")]
check(len(volleys) == 2 and {"6+" in v[0] for v in volleys} == {True, False},
      f"one attack vs 6+ (front), one vs 5+ (behind): {[v[0][:40] for v in volleys]}")
t = gs.get_ship_by_id("target")
check(t.hits_remaining < 8, f"hits applied together ({t.hits_remaining}/8)")
root.destroy()

print("2. Firing at an enemy squadron: aspect choice, hits nearest first")
Dice.labels.clear()
e = dict(squadron_id="esq", weapons=[])
root, gs, panel = build([ship("a1", 1, 50.0, 50.0, 0.0), ship("a2", 1, 50.0, 53.0, 0.0),
                         ship("e_close", 2, 70.0, 50.0, 180.0, **e),     # coming at them
                         ship("e_abeam", 2, 72.0, 52.0, 90.0, **e)])
picks = iter(["a1", "e_close"])
panel.ctx.pick_ship = lambda cands, title="": next(
    (c for c in cands if c.id == next(picks)), None)
panel.combat._combine_squadron_fire_dialog()
root.update()
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
combos = [w for w in walk(dlg) if isinstance(w, ttk.Combobox)]
check(combos and set(combos[0].cget("values")) == {"closing", "abeam"},
      f"aspect choice offered: {[c.cget('values') for c in combos]}")
for c in combos:
    c.set("closing")                 # better column, but only the closing escort counts
dice = Dice([6] * 20)
panel.ctx.dice = dice
[b for b in walk(dlg) if isinstance(b, tk.Button) and b.cget("text") == "Fire!"][0].invoke()
root.update()
check(gs.get_ship_by_id("e_close").is_destroyed and not gs.get_ship_by_id("e_abeam").is_destroyed,
      "only the closing escort could be hit")
root.destroy()
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
