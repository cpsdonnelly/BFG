"""Staged moves and blast markers through the real movement panel."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG")
os.chdir(tempfile.mkdtemp())

from src.models import Ship, BlastMarker
import src.choice_dialog as _cd_yn
_cd_yn.yes_no = lambda root, title, text, best: messagebox.askyesno(title, text)
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.movement import MoveCommand

for n in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, n, lambda *a, **k: print("   [dialog]", a))
messagebox.askyesno = lambda *a, **k: False

failures = []
def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        failures.append(label)


def ship(id, x, y, **kw):
    base = dict(id=id, name=id, ship_class="T", faction="imperial_navy_gothic", player=1,
                ship_type="cruiser", base_size="small", x=x, y=y, heading=0.0, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=2,
                hits_max=8, leadership=7, weapons=[], special_rules=[], upgrades=[],
                critical_damage=[])
    base.update(kw)
    return Ship(**base)


def build(*ships, markers=()):
    root = tk.Tk()
    gs = GameState()
    gs.dice_mode = "auto"
    for s in ships:
        gs.add_ship(s)
    gs.add_ship(ship("enemy", 110.0, 110.0, player=2))
    for m in markers:
        gs.add_blast_marker(m)
    tc = TurnController(gs, DiceRoller(mode="auto"))
    tc.start_game()
    tc.begin_phase("movement")
    board = BoardView(root, gs)
    frame = tk.Frame(board.side_panel); frame.pack()
    panel = GamePanel(frame, tc, board, root)
    panel._update_phase_display()
    return root, gs, tc, board, panel


fwd = lambda cm: MoveCommand("forward", cm)

print("1. Staged drag moves count distance already moved")
root, gs, tc, board, panel = build(ship("a", 20.0, 60.0))
board.commit_drag_fn(gs.get_ship_by_id("a"), [fwd(10)])
a = gs.get_ship_by_id("a")
check(abs(a.distance_moved_this_turn - 10) < 0.01 and "a" not in tc.ships_moved,
      f"stage 1: moved {a.distance_moved_this_turn}cm, not locked yet")
board.commit_drag_fn(a, [fwd(2), MoveCommand("turn_left", 45), fwd(3)])
a = gs.get_ship_by_id("a")
check(abs(a.distance_moved_this_turn - 15) < 0.01 and a.heading == 45.0,
      f"stage 2 (turn straight away) accepted: total {a.distance_moved_this_turn}cm, hdg {a.heading}")
board.commit_drag_fn(a, [fwd(10)])
a = gs.get_ship_by_id("a")
check(abs(a.distance_moved_this_turn - 15) < 0.01, "stage past the 20cm maximum rejected")
board.commit_drag_fn(a, [fwd(5)])
check("a" in tc.ships_moved, "ship locked once its 20cm budget is used")
root.destroy()

print("2. Ship touching a blast marker is slowed to 15cm and then locked")
s = ship("b", 20.0, 60.0)
marker = BlastMarker(id="bm", x=20.0, y=60.0 - (s.base_radius + 1.2))
root, gs, tc, board, panel = build(s, markers=[marker])
board.commit_drag_fn(gs.get_ship_by_id("b"), [fwd(20)])
check(gs.get_ship_by_id("b").distance_moved_this_turn == 0, "20cm move rejected")
board.commit_drag_fn(gs.get_ship_by_id("b"), [fwd(15)])
b = gs.get_ship_by_id("b")
check(b.distance_moved_this_turn == 15 and b.crossed_blast_this_turn, "15cm move accepted")
check("b" in tc.ships_moved, "ship marked fully moved after 15cm (End Phase won't complain)")
root.destroy()

print("3. Space min-move tops a part-moved ship up to half speed, no further")
root, gs, tc, board, panel = build(ship("c", 20.0, 60.0))
board.commit_drag_fn(gs.get_ship_by_id("c"), [fwd(10)])     # first stage: 10cm
c = gs.get_ship_by_id("c")
c.distance_moved_this_turn = 5.0      # pretend only 5cm were moved so far
gs.update_ship(c)
panel.movement._min_move_all_ships()
c = gs.get_ship_by_id("c")
check(abs(c.distance_moved_this_turn - 10) < 0.01,
      f"total after Space: {c.distance_moved_this_turn}cm (needs 10cm, was 5cm)")
root.destroy()

print("4. Move dialog budget shows the blast penalty")
s = ship("d", 20.0, 60.0)
root, gs, tc, board, panel = build(s, markers=[BlastMarker(id="bm", x=20.0, y=60.0 - (s.base_radius + 1.2))])
from src.movement_dialog import _MoveShipDialog
dlg = _MoveShipDialog.__new__(_MoveShipDialog)
try:
    panel.movement._move_ship_dialog_for = None
except Exception:
    pass
from src.movement import movement_budget
check(movement_budget(gs.get_ship_by_id("d"), "none", 0, gs.get_blast_markers()) == (10, 15),
      "budget for touching ship is 10-15cm")
root.destroy()

print("5. Come to New Heading: minimum distance before the second turn, across stages")
root, gs, tc, board, panel = build(ship("e", 20.0, 60.0, speed=25))
_e = gs.get_ship_by_id("e"); _e.special_order = "come_to_new_heading"; gs.update_ship(_e)
board.commit_drag_fn(gs.get_ship_by_id("e"), [fwd(10), MoveCommand("turn_left", 45), fwd(3)])
e = gs.get_ship_by_id("e")
check(e.turns_used_this_turn == 1 and e.distance_since_last_turn == 3,
      f"stage 1: 1 turn, {e.distance_since_last_turn}cm since it")
board.commit_drag_fn(e, [MoveCommand("turn_left", 45), fwd(2)])
e = gs.get_ship_by_id("e")
check(e.heading == 45.0 and e.distance_moved_this_turn == 13, "second turn after 3cm rejected")
board.commit_drag_fn(e, [fwd(7), MoveCommand("turn_left", 45), fwd(2)])
e = gs.get_ship_by_id("e")
check(e.heading == 90.0 and e.distance_moved_this_turn == 22,
      f"second turn after 10cm accepted (hdg {e.heading}, {e.distance_moved_this_turn}cm)")
root.destroy()

print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
sys.exit(1 if failures else 0)
