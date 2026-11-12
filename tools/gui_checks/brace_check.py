import os, sys, tempfile, tkinter as tk
from tkinter import messagebox
sys.path.insert(0, "/home/user/BFG"); os.chdir(tempfile.mkdtemp())
from src.models import Ship
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src.game_panel import GamePanel
from src.combat_dialog import _FireDialog
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
ASKED = []
def _ask(title, msg, **k):
    ASKED.append((title, msg)); return True
messagebox.askyesno = _ask
failures = []
def check(c, label):
    print(("  ok   " if c else "  FAIL ") + label)
    if not c: failures.append(label)
class Dice:
    mode = "auto"
    def __init__(self, r): self.r, self.i, self.labels = r, 0, []
    def roll_d6(self, n, label=""):
        out = self.r[self.i:self.i + n]; self.i += n; self.labels.append(label); return out
    def roll_2d6(self, label=""): v = self.r[self.i]; self.i += 1; self.labels.append(label); return v
    def roll_d3(self, label=""): v = self.r[self.i]; self.i += 1; return v
GUN = {"name": "Port Battery", "weapon_type": "battery", "strength": 6, "range_cm": 30,
       "arcs": ["front", "left", "right"]}
def mk(id, player, x, heading=0.0):
    return Ship(id=id, name=id, ship_class="T", faction="imperial_navy_gothic", player=player,
                ship_type="cruiser", base_size="small", x=x, y=50.0, heading=heading, speed=20,
                turn_angle=45, shields_max=0, armor_prow="6+", armor_side="5+", turrets=2,
                hits_max=8, leadership=7, weapons=[GUN], special_rules=[], upgrades=[],
                critical_damage=[])
def setup():
    root = tk.Tk(); gs = GameState(); gs.dice_mode = "auto"
    gs.add_ship(mk("p1", 1, 50.0)); gs.add_ship(mk("p2", 2, 70.0, 90.0))
    tc = TurnController(gs, DiceRoller(mode="auto")); tc.start_game(); gs.current_phase = "shooting"
    board = BoardView(root, gs); f = tk.Frame(board.side_panel); f.pack()
    return root, gs, GamePanel(f, tc, board, root)

print("1. Player fires at a (hot-seat) player ship: brace asked and rolled before the gunnery dice")
root, gs, panel = setup()
att, tgt = gs.get_ship_by_id("p1"), gs.get_ship_by_id("p2")
dlg = _FireDialog(panel.combat, att, [tgt], None, False, False, [], [(0, GUN)])
dlg.run(); root.update()
dlg.weapon_assignments[0][3].set(dlg.target_options_per_weapon[0][0])
dice = Dice([5] + [5] * 10); panel.ctx.dice = dice; panel.combat.ctx.dice = dice; dlg.ctx = panel.ctx
dlg._fire_all()
print("   rolls in order:", dice.labels[:3])
check(ASKED and "about to be attacked" in ASKED[0][1], "asked before the attack")
check("brace" in dice.labels[0] and "batteries" in dice.labels[1], "brace test came before the to-hit roll")
t = gs.get_ship_by_id("p2")
check(t.special_order == "brace_for_impact", "target braced")
root.destroy()

print("2. AI fires at the player's ship: the player is asked before the AI rolls")
ASKED.clear()
root, gs, panel = setup()
gs.ai_player = 2
from src.ai_player import AIPlayer
ai = AIPlayer(2, panel.ctx.tc, gs, None, "normal")
ai.brace_fn = (lambda att, tgt, exp, grp: panel.combat._brace_before_attack(
    att.id, att.name, tgt, exp, None, grp, att))
dice = Dice([5] + [5] * 10); ai.dice = dice; panel.ctx.dice = dice
ai._fire_ship(gs.get_ship_by_id("p2"))  # p2 is the AI ship firing at p1
print("   rolls in order:", dice.labels[:3])
check(ASKED and "p1" in ASKED[0][1], "player asked about the AI attack")
check("brace" in dice.labels[0], "brace test before the AI's to-hit roll")
root.destroy()
print("3. Batteries then lances: declined against the batteries, asked again before the lances")
ASKED.clear()
ANSWERS = [False, True]
def _ask2(title, msg, **k):
    ASKED.append((title, msg)); return ANSWERS.pop(0) if ANSWERS else True
messagebox.askyesno = _ask2
root, gs, panel = setup()
LANCE = {"name": "Port Lance", "weapon_type": "lance", "strength": 2, "range_cm": 30,
         "arcs": ["front", "left", "right"]}
att = gs.get_ship_by_id("p1"); att.weapons = [dict(LANCE), dict(GUN)]; gs.update_ship(att)
att, tgt = gs.get_ship_by_id("p1"), gs.get_ship_by_id("p2")
dlg = _FireDialog(panel.combat, att, [tgt], None, False, False, [], [(0, LANCE), (1, GUN)])
dlg.run(); root.update()
for wa in dlg.weapon_assignments:
    wa[3].set(dlg.target_options_per_weapon[wa[0]][0])
dice = Dice([5] * 60); panel.ctx.dice = dice; panel.combat.ctx.dice = dice; dlg.ctx = panel.ctx
dlg._fire_all()
labels = [l.lower() for l in dice.labels]
print("   rolls in order:", dice.labels[:6])
check(len(ASKED) == 2, "asked twice (before the batteries, then before the lances)")
ib = next((i for i, l in enumerate(labels) if "batter" in l), -1)
ibr = next((i for i, l in enumerate(labels) if "brace" in l), -1)
il = next((i for i, l in enumerate(labels) if "lance" in l), -1)
check(-1 < ib < ibr < il, "batteries rolled, then the brace test, then the lances")
check(gs.get_ship_by_id("p2").special_order == "brace_for_impact", "target braced for the lances")
saves = sum(1 for l in labels if "brace save" in l)
check(saves == 2, f"saves only for the 2 lance hits, none for the battery hits rolled before (got {saves})")
root.destroy()
messagebox.askyesno = _ask
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
