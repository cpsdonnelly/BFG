"""Many AI-vs-AI games in parallel, as fast as the engine goes (CLAUDE.md To do 16).

Each game runs the real GamePanel in fast mode (no pacing pauses, no board
drawing) in its own process; one virtual display serves them all, so run it
under xvfb-run:

    xvfb-run -a /usr/bin/python3.12 tools/headless_runner.py \
        --fleet1 data/fleets/owner_gothic_1000.json \
        --fleet2 data/fleets/owner_tau_merchant_1000.json \
        --games 8 --procs 4 --difficulty normal --turns 12 [--system aa]

Prints one line per game (winner, VP, turns, seconds) and a summary: win
rates, mean VP margin and games per hour. Each game is seeded (--seed + its
index) for the dice, and its rolls are recorded (--json keeps them;
--replay-check replays every game from its record and compares the final
state); the AI's own choices aren't seeded yet (To do 17), so
games repeat only with a fixed PYTHONHASHSEED and the normal AI (the
expert's time budget cuts its search at different points). Each result
carries a hash of the final state (ships, ordnance, blast markers, log) to
check that a change left play unchanged.

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


# The set-up's "All advanced rules on / off" switch (main._show_setup_dialog)
ADVANCED_RULES = ("fighting_sunward", "solar_flares", "radiation_bursts", "boarding",
                  "ramming", "teleport", "hit_and_run", "subplots")


def play(args) -> dict:
    """One game; returns its result. Runs in a worker process."""
    fleet1, fleet2, difficulty, turns, system, seed, timeout = args[:7]
    replay = args[7] if len(args) > 7 else None
    display = args[8] if len(args) > 8 else True
    os.environ["BFG_FAST"] = "1"
    import random
    import tempfile
    random.seed(seed)
    os.chdir(tempfile.mkdtemp())
    from src.game_state import GameState
    from src.dice import DiceRoller
    from src.turn_controller import TurnController
    from src.fleet_loader import load_fleet_file, fleet_to_ships, roll_starting_leadership
    from src.victory_points import calculate_victory_points
    errors = []
    from src.dice import start_game_dice, set_source, DiceSource
    from src.recorder import start_recording, events
    start_recording()
    if replay is None:
        start_game_dice(seed)
    else:                                # the recorded dice, in order (To do 17)
        set_source(DiceSource(seed, replay=replay))
    gs = GameState()
    gs.game_seed = seed
    gs.dice_mode = "auto"
    gs.ai_spectator = True
    gs.ai_difficulty = difficulty
    gs.ai_difficulty_p1 = os.environ.get("BFG_DIFFICULTY1") or None   # --difficulty1
    for r in filter(None, os.environ.get("BFG_RULES", "").split(",")):   # --rules
        setattr(gs, f"rule_{r.strip()}", True)
    gs.turn_limit = turns
    gs.turn_system = system
    if os.environ.get("BFG_SCENARIO"):                 # --scenario (the generic modes)
        gs.scenario_mode = os.environ["BFG_SCENARIO"]
    unplaced = False
    for p, f in ((1, fleet1), (2, fleet2)):
        data = load_fleet_file(os.path.join(ROOT, f))
        unplaced |= any("spawn_x" not in r and "x" not in r for r in data.get("ships", []))
        for sh in fleet_to_ships(data, p):
            gs.add_ship(sh)
    if unplaced:
        # Fleets saved by the fleet builder carry no positions: deploy both
        # fleets as the AI does in the window (ai_deployment, To do 28)
        from src.deployment import deployment_state
        from src.ai_deployment import ai_deploy_all
        from src.squadrons import ai_form_squadrons
        for p in (1, 2):                    # before deployment (s.8)
            ai_form_squadrons(gs, p)
        problems = ai_deploy_all(gs, deployment_state(gs))
        if problems:
            errors.extend(problems)
    dice = DiceRoller(mode="auto")
    roll_starting_leadership(gs, dice, ai_dice=dice)
    tc = TurnController(gs, dice)
    over = []
    start = time.time()
    if display:
        _play_in_window(tc, over, errors, timeout, start)
    else:                                # no window, no Tk (To do 18)
        from src.headless_game import HeadlessGame
        from src.prompts import Prompter

        class _Errors(Prompter):
            def _notify(self, title, text, level):
                if level == "error":
                    errors.append(f"{title}: {text}")
        game = HeadlessGame(tc)
        game.ctx.prompt = _Errors()
        game._roll_subplots()                # with sub-plots on, as the window does
        res = game.play(timeout)
        if res is not None:
            over.append(res["winner"])
    vp = calculate_victory_points(gs)
    import hashlib
    state = json.dumps({"ships": gs.ships, "ordnance": gs.ordnance,
                        "blast": gs.blast_markers, "log": gs.log}, sort_keys=True, default=str)
    if os.environ.get("BFG_DUMP_STATE"):
        with open(f"{os.environ['BFG_DUMP_STATE']}_{seed}.json", "w") as fh:
            fh.write(state)
    from src.dice import current_source
    res = {"record": current_source().record, "events": events(), "hash": hashlib.sha256(state.encode()).hexdigest()[:16],"seed": seed, "winner": over[0] if over else None, "finished": bool(over),
           "vp1": vp[1]["total"], "vp2": vp[2]["total"], "turns": gs.turn_number,
           "seconds": round(time.time() - start, 1), "errors": errors[:3]}
    return res


def _play_in_window(tc, over, errors, timeout, start):
    """The real GamePanel in fast mode on a hidden window (needs a display)."""
    import tkinter as tk
    from tkinter import messagebox
    import src.choice_dialog as cd
    from src.board_view import BoardView
    from src import game_panel as gp_mod
    from src.game_panel import GamePanel
    for name in ("showinfo", "showwarning"):
        setattr(messagebox, name, lambda *a, **k: None)
    messagebox.showerror = lambda title, msg="", **k: errors.append(f"{title}: {msg}")
    messagebox.askyesno = lambda *a, **k: False
    gp_mod.messagebox = messagebox
    cd.yes_no = lambda root, title, text, best: best
    cd.choose = lambda root, title, text, options, best, *a, **k: best
    root = tk.Tk()
    root.withdraw()
    board = BoardView(root, tc.gs)
    board.redraw = lambda *a, **k: None          # no drawing
    frame = tk.Frame(board.side_panel)
    frame.pack()
    panel = GamePanel(frame, tc, board, root)
    panel._show_game_over_dialog = lambda w, **k: over.append(w)
    panel._roll_subplots()                   # with sub-plots on, as GamePanel._start_game
    panel._begin_turn1()
    while not panel._game_over and time.time() - start < timeout:
        root.update()
    root.destroy()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fleet1", default="data/fleets/owner_gothic_1000.json")
    ap.add_argument("--fleet2", default="data/fleets/owner_tau_merchant_1000.json")
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--difficulty", default="normal", help="Player 2's AI (and Player 1's)")
    ap.add_argument("--difficulty1", default="", help="Player 1's AI, if different")
    ap.add_argument("--rules", default="all",
                    help="optional rules on: 'all' (the default: every advanced rule, as the "
                         "set-up's 'All advanced rules' switch), 'none', or a list such as "
                         "hit_and_run,boarding")
    ap.add_argument("--turns", type=int, default=12, help="turn limit (player turns, AA rounds)")
    ap.add_argument("--system", default="igougo", choices=("igougo", "aa"))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--scenario", default="",
                    help="GameState.scenario_mode, e.g. kill_admiral (generic modes)")
    ap.add_argument("--timeout", type=float, default=600.0, help="seconds per game")
    ap.add_argument("--json", help="write the results to this file")
    ap.add_argument("--no-display", action="store_true",
                    help="play with no window and no Tk (headless_game.HeadlessGame)")
    ap.add_argument("--replay-check", action="store_true",
                    help="replay each game from its recorded dice and check the final state matches")
    a = ap.parse_args()
    if a.difficulty1:
        os.environ["BFG_DIFFICULTY1"] = a.difficulty1   # inherited by the workers
    if a.scenario:
        os.environ["BFG_SCENARIO"] = a.scenario
    rules = {"all": ",".join(ADVANCED_RULES), "none": ""}.get(a.rules, a.rules)
    os.environ["BFG_RULES"] = rules
    print(f"optional rules on: {rules or 'none'}", flush=True)
    jobs = [(a.fleet1, a.fleet2, a.difficulty, a.turns, a.system, a.seed + i, a.timeout,
             None, not a.no_display) for i in range(a.games)]
    t0 = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=a.procs) as ex:
        for r in ex.map(play, jobs):
            results.append(r)
            print(f"seed {r['seed']}: winner={r['winner']} VP {r['vp1']}-{r['vp2']} "
                  f"turns={r['turns']} {r['seconds']}s hash={r['hash']}"
                  + (f" ERRORS {r['errors']}" if r["errors"] else ""), flush=True)
    if a.replay_check:
        again = [j[:7] + (r["record"], j[8]) for j, r in zip(jobs, results)]
        with ProcessPoolExecutor(max_workers=a.procs) as ex:
            for r, r2 in zip(results, ex.map(play, again)):
                same = r2["hash"] == r["hash"]
                print(f"replay seed {r['seed']}: {'same' if same else 'DIFFERENT'} "
                      f"({len(r['record'])} rolls)"
                      + (f" ERRORS {r2['errors']}" if r2["errors"] else ""), flush=True)
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
        json.dump(results, open(a.json, "w"), indent=1)   # each with its dice record


if __name__ == "__main__":
    main()
