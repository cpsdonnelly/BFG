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

print("4. Guided torpedoes: owner passes Ld and is asked how to turn")
from tkinter import simpledialog
asked = []
simpledialog.askfloat = lambda title, prompt, **k: (asked.append((title, k.get("initialvalue"))), 30.0)[1]
gs.blast_markers = []
base = {"owner_player": 1, "launched_by": "lunar", "y": 60.0, "heading": 0.0,
        "strength": 2, "speed": 30.0, "launched_turn": gs.turn_number - 1, "wave_id": "",
        "cap_ship_id": "", "resilient_save": 0, "resilient_used": False, "can_turn": False,
        "turn_angle": 0, "special_rules": [], "moved_this_phase": False,
        "launch_exempt_ships": []}
gs.ordnance = [{**base, "id": "g", "ordnance_type": "torpedo_guided_ld", "x": 40.0}]
dice = Dice([6])                       # launcher Ld 7: passed
panel.ctx.dice = dice
panel.ordnance._resolve_ordnance_movement()
check(dice.i == 1, f"one Ld test ({dice.i})")
check([a[0] for a in asked] == ["Guided Torpedoes"], f"owner asked: {asked}")
check(gs.ordnance and abs(gs.ordnance[0]["heading"] - 30.0) < 0.01,
      f"turned 30: {[o['heading'] for o in gs.ordnance]}")

print("4b. Launcher fails; the enemy player picks a ship to take control")
picked = []
simpledialog.askinteger = lambda title, prompt, **k: (picked.append(title), 1)[1]
gs.ordnance = [{**base, "id": "g2", "ordnance_type": "torpedo_guided_ld", "x": 40.0,
                "heading": 0.0}]
asked.clear()
dice = Dice([9,       # launcher Ld 7 fails (no re-rolls in this fleet)
             5])      # target (Ld 7), chosen by player 2, takes control
panel.ctx.dice = dice
panel.ordnance._resolve_ordnance_movement()
check(picked == ["Guided Torpedoes - Take Control?"], f"enemy asked to choose: {picked}")
check(dice.i == 2 and [a[0] for a in asked] == ["Guided Torpedoes"],
      f"enemy then turns the salvo ({dice.i} dice, {asked})")

print("5. Seeking torpedoes turn by themselves at the nearest enemy")
asked.clear()
gs.ordnance = [{**base, "id": "sk", "ordnance_type": "torpedo_seeking", "x": 40.0, "y": 20.0}]
dice = Dice([])
panel.ctx.dice = dice
panel.ordnance._resolve_ordnance_movement()
check(not asked and dice.i == 0, "no prompt, no dice")
import math
want = math.degrees(math.atan2(60.0 - 20.0, 95.0 - 40.0))     # 36°: within 45, so straight at it
check(gs.ordnance and abs(gs.ordnance[0]["heading"] - want) < 0.01,
      f"turned {want:.1f} straight at the target: {[o['heading'] for o in gs.ordnance]}")

print("6. A once-per-game salvo leaves the Load list after launching")
gs.ordnance = []
gs.current_phase = "shooting"
lun = gs.get_ship_by_id("lunar")
lun.special_rules = ["torpedo_type:vortex"]
lun.ordnance_loaded_torps = True
gs.update_ship(lun)
panel.ordnance._launch_ordnance_dialog(preselected_ship=gs.get_ship_by_id("lunar"))
root.update()
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
radios = [w for w in walk(dlg) if isinstance(w, tk.Radiobutton)]
check(any("Vortex" in r.cget("text") for r in radios), "vortex offered")
[r for r in radios if "Vortex" in r.cget("text")][0].invoke()
[b for b in walk(dlg) if isinstance(b, tk.Button)
 and b.cget("text").startswith("Launch Torp")][0].invoke()
root.update()
check([o["ordnance_type"] for o in gs.ordnance] == ["torpedo_vortex"], "vortex salvo launched")
check(gs.get_ship_by_id("lunar").once_torps_used == ["vortex"], "vortex used up")
from src.ordnance import torpedo_kind_options
check([k for k, _ in torpedo_kind_options(gs.get_ship_by_id("lunar"), torps)] == ["standard"],
      "no longer offered")
root.destroy()
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
