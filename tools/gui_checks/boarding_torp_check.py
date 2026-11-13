"""Boarding torpedoes through the real panels: launch dialog choice, then raids."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG")
os.chdir(tempfile.mkdtemp())

from src.models import Ship
import src.choice_dialog as _cd_yn
_cd_yn.yes_no = lambda root, title, text, best: messagebox.askyesno(title, text)
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel

for n in ("showinfo", "showwarning"):
    setattr(messagebox, n, lambda *a, **k: None)
messagebox.showerror = lambda *a, **k: print("   [error]", a)
asked = []
def _ask(title, msg, **k):
    asked.append(msg); return True              # target braces
messagebox.askyesno = _ask
from tkinter import simpledialog
turn_prompts = []
def _askfloat(title, prompt, **k):
    turn_prompts.append((prompt, k.get("initialvalue"))); return TURN[0]
simpledialog.askfloat = _askfloat
TURN = [0.0]

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
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=2,
                hits_max=8, leadership=7, upgrades=[], critical_damage=[], special_rules=[],
                weapons=[])
    base.update(kw)
    return Ship(**base)


root = tk.Tk()
gs = GameState()
gs.rule_hit_and_run = True
gs.dice_mode = "auto"
torps = {"name": "Prow Torps", "weapon_type": "torpedo", "strength": 6, "range_cm": 30,
         "arcs": ["front"], "torpedo_type": "standard", "torpedo_speed": 30,
         "boarding_torpedoes": True}
gs.add_ship(ship("barge", 1, 20.0, 0.0, special_rules=["space_marine_crew"], weapons=[torps]))
gs.add_ship(ship("target", 2, 70.0, 90.0))
tc = TurnController(gs, DiceRoller(mode="auto"))
tc.start_game()
gs.active_player = 1
gs.current_phase = "shooting"
board = BoardView(root, gs)
frame = tk.Frame(board.side_panel); frame.pack()
panel = GamePanel(frame, tc, board, root)

print("1. Launch dialog offers boarding torpedoes")
panel.ordnance._launch_ordnance_dialog(preselected_ship=gs.get_ship_by_id("barge"))
root.update()
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]

def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)

radios = [w for w in walk(dlg) if isinstance(w, tk.Radiobutton)]
check(any("Boarding" in r.cget("text") for r in radios), "boarding option shown")
[r for r in radios if "Boarding" in r.cget("text")][0].invoke()
[b for b in walk(dlg) if isinstance(b, tk.Button) and b.cget("text").startswith("Launch Torp")][0].invoke()
root.update()
check(len(gs.ordnance) == 1 and gs.ordnance[0]["ordnance_type"] == "torpedo_boarding",
      f"marker launched: {[o['ordnance_type'] for o in gs.ordnance]}")
check(gs.ordnance and gs.ordnance[0]["special_rules"] == ["space_marine_crew"],
      "launcher's Space Marine raid bonus carried")

print("2. Ordnance phase: hits become raids, target braces first")
gs.ordnance[0] = {**gs.ordnance[0], "x": 40.0, "y": 60.0, "heading": 0.0,
                  "launched_turn": gs.turn_number - 1}
gs.current_phase = "ordnance"
rolls = [5,                 # brace Ld test (2D6 <= 7), now before turrets (s.7): passed
         1, 1,              # turrets miss
         6, 5, 1, 1, 1, 1,  # vs side armour 5+: two hits -> two raids
         5, 3,              # raid 1: 5+1 = 6 Engine Room; repel 3 fails
         1, 2]              # raid 2: 1+1 = 2 -> crit roll 2; repel 2 fails
dice = Dice(rolls)
panel.ctx.dice = dice
panel.ordnance._resolve_ordnance_movement()
t = gs.get_ship_by_id("target")
crits = [c["crit_type"] for c in t.critical_damage]
check(dice.i == len(rolls), f"dice used {dice.i}/{len(rolls)}")
check(len(asked) == 1 and "about to be attacked" in asked[0], "brace asked once, before any roll")
check(len(crits) == 2 and crits[0] == "engine_room", f"two raid crits: {crits}")
check(t.special_order == "brace_for_impact", "target now on Brace for Impact")
print("   remaining marker:", [(o["ordnance_type"], o["strength"]) for o in gs.ordnance])
check(gs.ordnance and gs.ordnance[0]["strength"] == 4, "4 torps pass through")

check(len(turn_prompts) == 1, f"owner asked once how to turn the salvo: {turn_prompts[:1]}")

print("3. Boarding torps pass over a friendly ship; standard torps hit it")
gs.add_ship(ship("friend", 1, 70.0, 90.0, y=100.0))
for kind, expect_rolls in (("torpedo_boarding", 0), ("torpedo_standard", 8)):
    gs.ordnance = [{**gs.ordnance[0], "ordnance_type": kind, "x": 40.0, "y": 100.0,
                    "heading": 0.0, "strength": 6, "launch_exempt_ships": []}] if gs.ordnance else []
    dice = Dice([1] * 30)
    panel.ctx.dice = dice
    panel.ordnance._resolve_ordnance_movement()
    f = gs.get_ship_by_id("friend")
    check((dice.i == 0) == (expect_rolls == 0),
          f"{kind}: {dice.i} dice rolled against the friendly ship")
print("4. Owner turns a boarding salvo 45 degrees onto a target it would otherwise miss")
gs.ordnance = []
gs.add_ship(ship("t2", 2, 60.0, 90.0, y=30.0))
gs.ordnance = [{"id": "bt2", "ordnance_type": "torpedo_boarding", "owner_player": 1,
                "launched_by": "barge", "x": 40.0, "y": 10.0, "heading": 0.0, "strength": 2,
                "speed": 28.28427, "launched_turn": gs.turn_number - 1, "wave_id": "",
                "cap_ship_id": "", "resilient_save": 0, "resilient_used": False,
                "can_turn": False, "turn_angle": 0, "special_rules": [],
                "moved_this_phase": False, "launch_exempt_ships": []}]
TURN[0] = 45.0
turn_prompts.clear()
dice = Dice([1, 1, 6, 6, 1, 1])     # turrets miss; 2 hits; raids 1, 1 fail... no brace (asked -> True, Ld roll)
messagebox.askyesno = lambda *a, **k: False
panel.ctx.dice = dice
panel.ordnance._resolve_ordnance_movement()
t2 = gs.get_ship_by_id("t2")
print("   prompts:", turn_prompts)
check(len(turn_prompts) == 1 and turn_prompts[0][1] == 45, "suggested turn +45 toward the nearest enemy")
check(dice.i == 6, f"salvo turned, reached t2 and attacked ({dice.i} dice)")
root.destroy()
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
