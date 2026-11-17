"""A human (player 1) against the AI (player 2) in an alternate activation game
(To do 13) through the real GamePanel: the human's command phase, launches and
activations are each ended with End Phase; during an activation only one
unit's ships can act; the game plays through three rounds."""
import os, sys, tempfile, time, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
import src.choice_dialog as _cd_yn
_cd_yn.yes_no = lambda root, title, text, best: False
_cd_yn.choose = lambda root, title, text, options, best: best
from src.models import Ship
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src import game_panel as gp_mod
from src.game_panel import GamePanel
errs = []
for n in ("showinfo", "showwarning"):
    setattr(messagebox, n, lambda *a, **k: None)
messagebox.showerror = lambda *a, **k: errs.append(a)
messagebox.askyesno = lambda *a, **k: True
gp_mod.messagebox = messagebox
failures = []
def check(c, label):
    print(("  ok   " if c else "  FAIL ") + label)
    if not c: failures.append(label)
GUN = [{"name": "Port", "weapon_type": "battery", "strength": 6, "range_cm": 30, "arcs": ["left"]},
       {"name": "Stbd", "weapon_type": "battery", "strength": 6, "range_cm": 30, "arcs": ["right"]}]
def ship(id, p, x, y):
    return Ship(id=id, name=id, ship_class="T", faction="imperial_navy_gothic", player=p,
                ship_type="cruiser", base_size="small", x=x, y=y, heading=0.0 if p == 1 else 180.0,
                speed=20, turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+",
                turrets=2, hits_max=8, leadership=8, weapons=[dict(w) for w in GUN],
                special_rules=[], upgrades=[], critical_damage=[], points_value=180)
root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
gs.table_width, gs.table_height = 180.0, 120.0
gs.ai_player = 2; gs.ai_difficulty = "normal"; gs.turn_limit = 3
gs.turn_system = "aa"; gs.aa_settings = {"order_mode": "bag"}
for i in range(2):
    gs.add_ship(ship(f"h{i}", 1, 30.0, 40.0 + 30 * i))
    gs.add_ship(ship(f"e{i}", 2, 140.0, 40.0 + 30 * i))
tc = TurnController(gs, DiceRoller(mode="auto"))
board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
panel = GamePanel(f, tc, board, root)
panel._begin_turn1()
seen, restricted = set(), []
start = time.time()
while not panel._game_over and time.time() - start < 60:
    root.update(); time.sleep(0.01)
    w = panel._aa_waiting
    if w is None:
        continue
    ph, p = w
    seen.add(ph)
    if ph == "movement":
        before = {s.id for s in tc.get_unmoved_ships()}
        mover = sorted(before)[0]
        tc.mark_ship_moved(mover)              # stands in for a real move
        after = {s.id for s in tc.get_unmoved_ships()}
        restricted.append(not (after & (before - {mover})))
    panel._end_phase()
print("round", gs.turn_number, [(s.id, s.status, s.hits_remaining) for s in gs.get_ships()])
check({"command", "shooting", "movement"} <= seen, f"the human was asked for {sorted(seen)}")
check(restricted and all(restricted), "after one ship moved, no other unit's ship could act")
check(panel._game_over, "the game reached its turn limit")
check(not errs, f"no error dialogs {errs[:1]}")
print("RESULT: ALL OK" if not failures else "RESULT: FAIL")
