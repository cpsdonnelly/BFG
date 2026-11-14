"""Many AI-vs-AI games in parallel, as fast as the engine goes (CLAUDE.md To do 16).

Each game runs the real GamePanel in fast mode (no pacing pauses, no board
drawing) in its own process; one virtual display serves them all, so run it
under xvfb-run:

    xvfb-run -a /usr/bin/python3.12 tools/headless_runner.py \
        --fleet1 data/fleets/imperial_navy_demo.json \
        --fleet2 data/fleets/tau_kororvesh_demo.json \
        --games 8 --procs 4 --difficulty normal --turns 12 [--system aa]

Prints one line per game (winner, VP, turns, seconds) and a summary: win
rates, mean VP margin and games per hour. Each game is seeded (--seed + its
index) for the dice; the AI's own choices aren't seeded yet (To do 17), so
games aren't exactly repeatable.

Still needs a display: the game flow (ordnance contacts, the end phase,
alternate activation) lives in the Tk panels. Moving it into the engine, so
games run with no Tk at all, is part of To do 18.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def play(args) -> dict:
    """One game; returns its result. Runs in a worker process."""
    fleet1, fleet2, difficulty, turns, system, seed, timeout = args
    os.environ["BFG_FAST"] = "1"
    import random
    import tempfile
    import tkinter as tk
    from tkinter import messagebox
    random.seed(seed)
    os.chdir(tempfile.mkdtemp())
    import src.choice_dialog as cd
    from src.game_state import GameState
    from src.dice import DiceRoller
    from src.turn_controller import TurnController
    from src.board_view import BoardView
    from src import game_panel as gp_mod
    from src.game_panel import GamePanel
    from src.fleet_loader import load_fleet_file, fleet_to_ships, roll_starting_leadership
    from src.victory_points import calculate_victory_points

    errors = []
    for name in ("showinfo", "showwarning"):
        setattr(messagebox, name, lambda *a, **k: None)
    messagebox.showerror = lambda title, msg="", **k: errors.append(f"{title}: {msg}")
    messagebox.askyesno = lambda *a, **k: False
    gp_mod.messagebox = messagebox
    cd.yes_no = lambda root, title, text, best: best
    cd.choose = lambda root, title, text, options, best, *a, **k: best

    root = tk.Tk()
    root.withdraw()
    gs = GameState()
    gs.dice_mode = "auto"
    gs.ai_spectator = True
    gs.ai_difficulty = difficulty
    gs.turn_limit = turns
    gs.turn_system = system
    for p, f in ((1, fleet1), (2, fleet2)):
        for sh in fleet_to_ships(load_fleet_file(os.path.join(ROOT, f)), p):
            gs.add_ship(sh)
    dice = DiceRoller(mode="auto")
    roll_starting_leadership(gs, dice, ai_dice=dice)
    tc = TurnController(gs, dice)
    board = BoardView(root, gs)
    board.redraw = lambda *a, **k: None          # no drawing
    frame = tk.Frame(board.side_panel)
    frame.pack()
    panel = GamePanel(frame, tc, board, root)
    over = []
    panel._show_game_over_dialog = lambda w, **k: over.append(w)
    start = time.time()
    panel._begin_turn1()
    while not panel._game_over and time.time() - start < timeout:
        root.update()
    vp = calculate_victory_points(gs)
    res = {"seed": seed, "winner": over[0] if over else None, "finished": bool(over),
           "vp1": vp[1]["total"], "vp2": vp[2]["total"], "turns": gs.turn_number,
           "seconds": round(time.time() - start, 1), "errors": errors[:3]}
    root.destroy()
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fleet1", default="data/fleets/imperial_navy_demo.json")
    ap.add_argument("--fleet2", default="data/fleets/tau_kororvesh_demo.json")
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--difficulty", default="normal")
    ap.add_argument("--turns", type=int, default=12, help="turn limit (player turns, AA rounds)")
    ap.add_argument("--system", default="igougo", choices=("igougo", "aa"))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=600.0, help="seconds per game")
    ap.add_argument("--json", help="write the results to this file")
    a = ap.parse_args()
    jobs = [(a.fleet1, a.fleet2, a.difficulty, a.turns, a.system, a.seed + i, a.timeout)
            for i in range(a.games)]
    t0 = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=a.procs) as ex:
        for r in ex.map(play, jobs):
            results.append(r)
            print(f"seed {r['seed']}: winner={r['winner']} VP {r['vp1']}-{r['vp2']} "
                  f"turns={r['turns']} {r['seconds']}s"
                  + (f" ERRORS {r['errors']}" if r["errors"] else ""), flush=True)
    wall = time.time() - t0
    done = [r for r in results if r["finished"]]
    wins = {p: sum(1 for r in done if r["winner"] == p) for p in (1, 2)}
    margin = sum(r["vp1"] - r["vp2"] for r in results) / max(1, len(results))
    print(f"\n{len(results)} games ({len(done)} finished) in {wall:.0f}s with {a.procs} "
          f"processes: {3600 * len(results) / max(1e-9, wall):.0f} games/hour; "
          f"mean {sum(r['seconds'] for r in results) / max(1, len(results)):.1f}s a game")
    print(f"wins: player 1 {wins[1]}, player 2 {wins[2]}, other {len(results) - wins[1] - wins[2]}; "
          f"mean VP margin (1 - 2) {margin:+.0f}")
    if a.json:
        json.dump(results, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
