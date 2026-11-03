import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship, OrdnanceMarker
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: False
failures = []
def check(c, label):
    print(("  ok   " if c else "  FAIL ") + label)
    if not c: failures.append(label)
def walk(w):
    yield w
    for c in w.winfo_children(): yield from walk(c)
class Dice:
    mode = "auto"
    def __init__(self, r): self.r, self.i = r, 0
    def roll_d6(self, n, label=""):
        out = self.r[self.i:self.i + n]; self.i += n; print(f"    roll {label!r}: {out}"); return out
    def roll_2d6(self, label=""): v = self.r[self.i]; self.i += 1; return v
    def roll_d3(self, label=""): v = self.r[self.i]; self.i += 1; return v
def ship(id, player, x, y):
    return Ship(id=id, name=id, ship_class="T", faction="imperial_navy_gothic", player=player,
                ship_type="cruiser", base_size="small", x=x, y=y, heading=90.0, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=1,
                hits_max=8, leadership=7, weapons=[], special_rules=[], upgrades=[], critical_damage=[])
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
gs.add_ship(ship("carrier", 1, 20.0, 20.0)); gs.add_ship(ship("target", 2, 20.0, 35.0))
gs.add_ship(ship("other", 2, 60.0, 20.0))
tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
gs.active_player = 1; gs.current_phase = "ordnance"
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root); panel._update_phase_display()
gs.add_ordnance(OrdnanceMarker(id="bomb1", ordnance_type="bomber", owner_player=1,
                               launched_by="carrier", x=20.0, y=20.0, heading=0.0,
                               speed=20.0, launched_turn=gs.turn_number))
print("1. Button shown in the ordnance phase; dialog lists targets")
check(panel.craft_orders_btn.winfo_ismapped() or bool(panel.craft_orders_btn.winfo_manager()), "Attack Craft Orders button packed")
panel.ordnance._craft_orders_dialog(); root.update()
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
menus = [w for w in walk(dlg) if isinstance(w, tk.OptionMenu)]
opts = [menus[0]["menu"].entrycget(i, "label") for i in range(menus[0]["menu"].index("end") + 1)]
print("   options:", opts)
choice = next(o for o in opts if o.startswith("Attack target"))
check("(in reach)" in choice, "target 15cm away marked in reach")
# set the OptionMenu's variable through its menu command
menus[0]["menu"].invoke(opts.index(choice))
[b for b in walk(dlg) if isinstance(b, tk.Button) and b.cget("text") == "Apply"][0].invoke()
check(gs.ordnance[0]["craft_target_id"] == "target", "order stored")
print("2. Ordnance phase: the bomber turns 90 degrees, reaches the target and attacks")
rolls = [1,        # Phase 1: 1 turret vs the bomber, misses
         4,        # bomber attacks D6 = 4 - 1 turret = 3
         6, 6, 1]  # vs 5+: two hits
dice = Dice(rolls + [1] * 6); panel.ctx.dice = dice
panel.ordnance._resolve_ordnance_movement()
t = gs.get_ship_by_id("target")
check(t.hits_remaining == 6 and gs.ordnance == [], f"bomber hit the target twice (hits left {t.hits_remaining})")
root.destroy()
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
