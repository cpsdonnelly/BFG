import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship, OrdnanceMarker
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.ship_catalog import find_ship_class
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
ASK = []
def _ask(title, msg, **k):
    ASK.append((title, msg))
    if "Brace" in title:
        return False                     # targets don't brace in these checks
    return ANSWER[0]
messagebox.askyesno = _ask
ANSWER = [True]
import src.choice_dialog as _cd
SUPPRESS_ASKED = []
def _choose(root, title, text, options, best):
    SUPPRESS_ASKED.append(title)
    if "Suppress" in title:
        return 0                         # s.27: no multi-role squadron suppresses here
    if title == "Multi-role Attack Craft":
        ASK.append((title, text))
        return "bomber" if ANSWER[0] else "assault_boat"
    return ANSWER[0] if isinstance(best, bool) else best
_cd.choose = _choose
failures = []
def check(c, label):
    print(("  ok   " if c else "  FAIL ") + label)
    if not c: failures.append(label)
class Dice:
    mode = "auto"
    def __init__(self, r): self.r, self.i = r, 0
    def _n(self):
        v = self.r[self.i]; self.i += 1; return v
    def roll_d6(self, n, label=""):
        out = [self._n() for _ in range(n)]; print(f"    roll {label!r}: {out}"); return out
    def roll_2d6(self, label=""): v = self._n(); print(f"    2d6 {label!r}: {v}"); return v
    def roll_d3(self, label=""): v = self._n(); print(f"    d3 {label!r}: {v}"); return v
def walk(w):
    yield w
    for c in w.winfo_children(): yield from walk(c)
def enemy(x, y=60.0, turrets=2, player=2):
    return Ship(id="enemy", name="enemy", ship_class="T", faction="imperial_navy_gothic",
                player=player, ship_type="cruiser", base_size="small", x=x, y=y, heading=90.0,
                speed=20, turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+",
                turrets=turrets, hits_max=8, leadership=7, weapons=[], special_rules=[],
                upgrades=[], critical_damage=[])
def build(ships):
    root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"; gs.rule_hit_and_run = True
    for s in ships: gs.add_ship(s)
    tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
    gs.active_player = 1; gs.current_phase = "shooting"
    board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
    panel = GamePanel(f, tc, board, root)
    return root, gs, panel

print("1. Gorbag's Revenge launches: D3+1 dorsal bays rolled, one squadron per bay")
d = find_ship_class("Gorbag's Revenge (0-1)").to_ship_dict("Gorbag", 1, ship_id="g")
d.update(x=30.0, y=60.0, heading=0.0, leadership=7)
root, gs, panel = build([Ship.from_dict(d), enemy(110.0, 110.0)])
dice = Dice([2]); panel.ctx.dice = dice
panel.ordnance._launch_ordnance_dialog(preselected_ship=gs.get_ship_by_id("g")); root.update()
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
labels = [w.cget("text") for w in walk(dlg) if isinstance(w, tk.Label)]
print("   ", [t for t in labels if "launch" in t.lower()][:3])
rows = {}
for w in walk(dlg):
    if isinstance(w, tk.Entry) and isinstance(w.master, tk.Frame):
        ls = [c.cget("text") for c in w.master.winfo_children() if isinstance(c, tk.Label)]
        if ls: rows[ls[0]] = w
print("   rows:", list(rows))
fb = next(k for k in rows if k.startswith("Fighta"))
rows[fb].delete(0, tk.END); rows[fb].insert(0, "8")       # ask for 8 (max possible)
[b for b in walk(dlg) if isinstance(b, tk.Button) and b.cget("text") == "Launch Attack Craft"][0].invoke()
root.update()
got = [(o["ordnance_type"], o["speed"]) for o in gs.ordnance]
check(dice.i == 1 and len(got) == 7 and all(g == ("fighta_bommer", 25) for g in got),
      f"rolled D3=2 -> 3 + 2 + 2 = 7 Fighta-Bommerz at 25cm (got {len(got)})")
root.destroy()

print("2. Thunderhawks touching an enemy: owner picks assault boats after turrets fire")
def th(i, x):
    return OrdnanceMarker(id=f"th{i}", ordnance_type="thunderhawk", owner_player=1,
                          launched_by="sm", x=x, y=60.0, heading=0.0, strength=1,
                          speed=20, launched_turn=0, resilient_save=4,
                          special_rules=["space_marine_crew"]).to_dict()
root, gs, panel = build([enemy(70.0, turrets=2)])
gs.ordnance = [th(0, 50.0), th(1, 50.5)]
from src.waves import form_wave
form_wave(gs, ["th0", "th1"], "close")              # one wave (s.25)
gs.current_phase = "ordnance"
ANSWER[0] = False; ASK.clear()                      # No = assault boats
rolls = [1, 1,          # Phase 1: 2 turrets vs the wave, both miss
         5,             # raid 1: 5 +1 Space Marines = 6 Engine Room
         1]             # raid 2: 1 +1 = 2 -> crit roll 2 (cascades on a weaponless ship)
dice = Dice(rolls + [1] * 5); panel.ctx.dice = dice
panel.ordnance._resolve_ordnance_movement()
mr_q = [m for t, m in ASK if t == "Multi-role Attack Craft"]
print("   asked:", [m.splitlines()[0] for m in mr_q])
e = gs.get_ship_by_id("enemy")
check(len(mr_q) == 1 and "2 Thunderhawk" in mr_q[0], "one choice for the wave")
check(gs.ordnance == [] and any(c["crit_type"] == "engine_room" for c in e.critical_damage),
      f"two raids resolved (crits {[c['crit_type'] for c in e.critical_damage]})")
root.destroy()

print("3. Same, answering bombers: D6 attacks - turrets vs lowest armour")
root, gs, panel = build([enemy(70.0, turrets=2)])
gs.ordnance = [th(0, 50.0)]
gs.current_phase = "ordnance"
ANSWER[0] = True; ASK.clear()
rolls = [1, 1,          # turrets miss
         5,             # bomber attacks D6 = 5 - 2 turrets = 3
         5, 6, 1]       # vs 5+: 2 hits
dice = Dice(rolls + [1] * 6); panel.ctx.dice = dice
panel.ordnance._resolve_ordnance_movement()
e = gs.get_ship_by_id("enemy")
check(e.hits_remaining == 6, f"2 bomber hits (hits left {e.hits_remaining})")
root.destroy()
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
