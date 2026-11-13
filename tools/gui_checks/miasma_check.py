"""Miasma of Pestilence (Nurgle boon): ordnance attacking the ship counts as
passing through blast markers (destroyed on a 6), even with standard blast
marker rules. A torpedo salvo touching the Miasma ship rolls a 6 and is gone."""
import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship, OrdnanceMarker
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.optional_rules import blast_rules
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
failures = []
def check(c, label):
    print(("  ok   " if c else "  FAIL ") + label)
    if not c: failures.append(label)

def ship(id, player, x, rules):
    return Ship(id=id, name=id, ship_class="T", faction="chaos", player=player,
                ship_type="cruiser", base_size="small", x=x, y=60.0, heading=0.0, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=0,
                hits_max=8, leadership=7, weapons=[], special_rules=rules, upgrades=[],
                critical_damage=[], points_value=180)

class Six(DiceRoller):
    def __init__(self):
        super().__init__(mode="auto"); self.rolls = []
    def roll_d6(self, n=1, *a, **k):
        self.rolls.append(("d6", n, a[0] if a else "")); return [6] * n

for rules, gone_expected in ((["miasma"], True),):
    root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
    gs.add_ship(ship("a", 1, 20.0, []))
    gs.add_ship(ship("n", 2, 100.0, rules))
    tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game()
    board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
    panel = GamePanel(f, tc, board, root); root.update()
    check(blast_rules() == "standard", "standard blast marker rules")
    gs.ordnance.append(OrdnanceMarker(id="t1", ordnance_type="torpedo", owner_player=1,
                                      x=100.0, y=60.0, heading=0.0, speed=30,
                                      strength=1, launched_by="a").to_dict())
    dice = Six(); panel.ctx.dice = dice
    try:
        panel.ordnance._resolve_ship_contacts(gs.get_ships(), mover=1)
    except Exception as ex:   # the rest of the resolution may want more set-up
        print("  (after the miasma roll:", type(ex).__name__, ex, ")")
    n = gs.get_ship_by_id("n")
    if gone_expected:
        check(n.hits_remaining == n.hits_max, "Miasma: salvo destroyed before attacking")
        check(any("blast markers (6" in str(r[2]) for r in dice.rolls), "Miasma: the 6 rolled")
        check(not any(o["id"] == "t1" for o in gs.ordnance), "Miasma: salvo removed on a 6")
    else:
        check(not any("blast markers (6" in str(r[2]) for r in dice.rolls),
              "no Miasma: no blast marker roll")
    root.destroy()
print("RESULT: ALL OK" if not failures else "RESULT: FAIL")
