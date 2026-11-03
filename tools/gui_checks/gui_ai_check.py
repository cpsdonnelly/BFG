"""Drive the real Tkinter GamePanel through AI-turn scenarios."""
import os
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import messagebox, filedialog

sys.path.insert(0, "/home/user/BFG")
os.chdir(tempfile.mkdtemp())

from src.models import Ship
from src.game_state import GameState
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.board_view import BoardView
from src import game_panel as gp_mod
from src.game_panel import GamePanel
from src.ai_player import AIPlayer
from src.lookahead_ai import LookaheadAI

dialogs = []
for name in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, name,
            (lambda n: lambda title, msg="", **k: dialogs.append((n, title)))(name))
messagebox.askyesno = lambda *a, **k: True
gp_mod.messagebox = messagebox

failures = []


def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        failures.append(label)


def ship(id, player, x):
    return Ship(id=id, name=id, ship_class="Test", faction="imperial_navy_gothic",
                player=player, ship_type="cruiser", base_size="small",
                x=x, y=60.0, heading=0.0 if player == 1 else 180.0, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+",
                turrets=2, hits_max=8, leadership=7, weapons=[], special_rules=[],
                upgrades=[], critical_damage=[], points_value=100)


def build(difficulty="normal", dice_mode="mixed"):
    dialogs.clear()
    root = tk.Tk()
    gs = GameState()
    gs.dice_mode = dice_mode
    gs.ai_player = 2
    gs.ai_difficulty = difficulty
    gs.add_ship(ship("p1", 1, 20.0))
    gs.add_ship(ship("p2", 2, 100.0))
    dice = DiceRoller(mode=dice_mode)
    tc = TurnController(gs, dice)
    tc.start_game()
    board = BoardView(root, gs)
    frame = tk.Frame(board.side_panel)
    frame.pack()
    panel = GamePanel(frame, tc, board, root)
    return root, gs, tc, board, panel


def pump(root, ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def start_ai_phase(panel, gs, phase):
    gs.active_player = 2
    gs.current_phase = phase
    panel._update_phase_display()
    panel._schedule_ai_phase(0)


# ── 1. AI rolls dice in auto mode, and the human's mode is restored ──────────
print("1. Dice mode during AI turn")
seen = []
orig_shoot = AIPlayer.run_shooting_phase
AIPlayer.run_shooting_phase = lambda self: seen.append(self.dice.mode)
root, gs, tc, board, panel = build(dice_mode="mixed")
start_ai_phase(panel, gs, "shooting")
pump(root, 800)
check(seen == ["auto"], f"AI rolled with dice mode {seen}")
check(panel.ctx.dice.mode == "mixed" and gs.dice_mode == "mixed",
      f"human dice mode restored to {panel.ctx.dice.mode}/{gs.dice_mode}")
check(gs.current_phase == "ordnance", f"advanced once to {gs.current_phase}")
check(not [d for d in dialogs if d[1] == "Unfired Weapons"],
      "no 'Unfired Weapons' popup about the AI's own ships")
AIPlayer.run_shooting_phase = orig_shoot
root.destroy()

# ── 2. Human input is locked during the AI's turn ────────────────────────────
print("2. Input lock on the AI's turn")
root, gs, tc, board, panel = build()
gs.active_player = 2
gs.current_phase = "movement"
panel._update_phase_display()
p2_before = gs.get_ship_by_id("p2").x
panel.movement._min_move_all_ships()          # Spacebar
check(gs.get_ship_by_id("p2").x == p2_before, "Spacebar can't move AI ships")
check(not board.can_drag_ship_fn(gs.get_ship_by_id("p2")), "can't drag AI ships")
check(str(panel.end_phase_btn["state"]) == "disabled", "End Phase button disabled")
check("(AI)" in panel.player_label["text"], f"label shows '{panel.player_label['text']}'")
gs.active_player = 1
panel._update_phase_display()
check(str(panel.end_phase_btn["state"]) == "normal", "End Phase re-enabled on human turn")
check(board.can_drag_ship_fn(gs.get_ship_by_id("p1")), "human can drag own ship")
root.destroy()

# ── 3. Expert AI thinking: locked, no Tk from thread, advances exactly once ──
print("3. Expert AI background search")
gate = threading.Event()
thread_names = []


def slow_move(self):
    thread_names.append(threading.current_thread() is threading.main_thread())
    gate.wait(5)


orig_look = LookaheadAI.run_movement_phase
LookaheadAI.run_movement_phase = slow_move
root, gs, tc, board, panel = build(difficulty="expert")
start_ai_phase(panel, gs, "movement")
pump(root, 300)
check(panel._ai_thinking, "AI marked as thinking")
check(panel.phase_label["text"] == "AI Thinking…", "label shows AI Thinking…")
check(thread_names == [False], "search ran off the main thread")
panel.end_phase_btn.invoke()                  # click End Phase mid-search
panel._save_game()
check(gs.current_phase == "movement", "End Phase click ignored while thinking")
check(("showinfo", "AI Thinking") in dialogs, "Save refused with a wait message")
gate.set()
pump(root, 1000)
check(not panel._ai_thinking, "thinking flag cleared")
check(gs.current_phase == "shooting", f"advanced exactly once, now {gs.current_phase}")
root.destroy()

# ── 4. AI crash ends its phase instead of freezing the game ──────────────────
print("4. AI error recovery")
gate.clear()
LookaheadAI.run_movement_phase = lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
root, gs, tc, board, panel = build(difficulty="expert", dice_mode="mixed")
start_ai_phase(panel, gs, "movement")
pump(root, 1000)
check(("showerror", "AI Error") in dialogs, "error shown to the player")
check(not panel._ai_thinking, "not stuck on AI Thinking")
check(panel.ctx.dice.mode == "mixed", "dice mode restored after crash")
check(gs.current_phase == "shooting",
      f"game moved on despite the unmoved AI ship, now {gs.current_phase}")
LookaheadAI.run_movement_phase = orig_look
root.destroy()

# ── 5. Game over stops play ──────────────────────────────────────────────────
print("5. Game over")
game_over_dialogs = []
root, gs, tc, board, panel = build()
panel._show_game_over_dialog = lambda *a, **k: game_over_dialogs.append(a)
gs.turn_limit = 1
gs.active_player = 1
gs.current_phase = "end"
panel._update_phase_display()
panel._end_phase()                            # human ends turn 1 -> limit hit
pump(root, 300)
state = (gs.turn_number, gs.current_phase, gs.active_player)
check(panel._game_over, "game marked over")
check(panel.phase_label["text"] == "GAME OVER", "label shows GAME OVER")
check(str(panel.end_phase_btn["state"]) == "disabled", "End Phase disabled")
panel._end_phase()
panel._schedule_ai_phase(0)
pump(root, 1200)
check((gs.turn_number, gs.current_phase, gs.active_player) == state,
      "no further phases or AI turns after game over")
check(len(game_over_dialogs) == 1, f"game-over dialog shown {len(game_over_dialogs)}x")

# ── 6. Loading a game clears game over and resumes the AI if it's its turn ──
print("6. Load resumes play")
save_dir = tempfile.mkdtemp()
fresh = GameState()
fresh.ai_player = 2
fresh.add_ship(ship("p1", 1, 20.0))
fresh.add_ship(ship("p2", 2, 100.0))
fresh.turn_number = 3
fresh.current_phase = "shooting"
fresh.active_player = 2
fresh.save(save_dir)
filedialog.askdirectory = lambda **k: save_dir
seen.clear()
AIPlayer.run_shooting_phase = lambda self: seen.append("shot")
panel._load_game()
pump(root, 1200)
check(not panel._game_over, "game-over cleared by load")
check(seen == ["shot"], "AI took its loaded turn")
check(gs.current_phase == "ordnance", f"advanced to {gs.current_phase}")
AIPlayer.run_shooting_phase = orig_shoot
root.destroy()

print("RESULT:", "ALL OK" if not failures else f"{len(failures)} FAILURES: {failures}")
sys.exit(1 if failures else 0)
