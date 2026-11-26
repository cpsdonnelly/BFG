# BFG:XR Simulator

A digital play aid for Battlefleet Gothic: Extended Rules (BFG:XR). The desktop app is
Tkinter (`python run.py`); the rules engine is pure Python in `src/`.

Owner: keep this file small; it is read in full every session. Detail lives in `docs/`
and is read only when the work needs it:
- `docs/RULINGS.md`: every owner ruling and the notes per rules area (Brace, faction rules,
  ship options and commanders, blast markers, squadron fire, waves, fleet lists, torpedo
  types, engine gaps, booklet update 62, answered questions). Read the section for the area
  you change before changing it.
- `docs/TODO.md`: the full To do list (items 1-34; numbers are IDs cited in code).
- `docs/STATUS.md`: session status and history, latest first.
- `docs/AI_DECIDES.md`: how the AI decides, in detail; `docs/AI_DESIGN.md` the plain-language
  design (keep both in step with the code).
- `docs/HANDOFF.md`: longer design notes and the handoff.
Update those files as work is done; keep this one to the summary below.

## Rules source of truth

- **`bfgxr/` is the rules authority.** Read `bfgxr/CLAUDE.md` before changing any rule or ship
  stat. It is an export of the BFG:XR companion booklet: `bfgxr/rules/` (one Markdown file
  per section) and `bfgxr/data/ships.json`. Never edit those generated files by hand; the
  `.docx` in `bfgxr/source/` is the master. `bfgxr/CHANGES.md` lists what each export changed
  (read it after every new export; after one, diff the built catalog, since notes text is
  matched in code). Sections are numbered in `bfgxr/rules/00_core-rules.md`.
- Never invent rules, stats or values. If the booklet doesn't cover something, say so and
  ask the owner. Owner rulings fill gaps: `docs/RULINGS.md`.
- `data/rules_cheatsheet.txt` and `data/*.csv` are an older hand-written summary; `bfgxr/`
  wins where they disagree.
- The ship catalog (`src/ship_catalog.py`) is built at import from `bfgxr/data/ships.json` by
  `src/booklet_ships.py`. Ships using rules the engine can't play yet carry
  `entry.unsupported` reasons and are greyed out in the fleet builder.

## Standing owner instructions (short form; details in docs/RULINGS.md)

- Learned evaluation and weight tuning (To do 12 and 1): on hold until the owner says so;
  when built, a separate AI that never replaces the current one.
- A disabled optional rule is off for players and the AI alike (never valued or attempted).
- Compute values from the rules, exactly where possible; no guessed weights where the rules
  give an answer, no sampling where an exact answer costs about the same.
- Every AI choice is in expected VP; the player prompts' "Auto" picks what the AI would
  (labelled "Auto", never "best").
- Replays must stay exact (seeded dice, recorded decisions, caches that depend on the state
  only). Slow thinking is acceptable for the master AI; broken replays are not.
- Victory points and scenario win conditions matter more than pure elimination.
- Before the Rust port, only minimal Tk versions of new windows; the full ones are built
  once, in the browser.

## Current status (details in docs/STATUS.md)

- Ten factions playable plus Dark Eldar and Tyranids; 31 booklet scenarios; both turn
  systems (IGOUGO and alternate activation); the expected-VP AI at six difficulties
  (search depth 0 / 0 / 2 / 3 / 5 / 10 turns); every phase recorded and replayable.
- Latest: the four must-fixes (To do 33) all back in. (d): Brace and Leadership crits cost
  the order the ship's own AI last planned (`GameState.planned_orders`, recorded); no plan:
  the better of Lock On and, when spent, Reload; the master AI plans afresh (its replay
  check is in progress, see docs/STATUS.md). Plain game: a fleet gone is decided by the
  mode's condition, else VP.
- Next: (d)'s two fixes (a squadron's one order; the lost order's gain on the guns a brace
  halves), then team play (To do 22).

## Agreed order (details in docs/TODO.md)

Done: To do 15-18 (mostly), 24-29, 31, and most of 2, 3, 6, 7. Remaining, in order:
team play (22); Dark Eldar / Tyranid gaps (19); Eldar / Necron gaps (14); daemonships,
Ordos, Inquisitors, special movement units (4, 5); a small comparison of the AA order
systems (13); the small gaps incl. the Decoy (7, 9); the replay standard and golden games
(21); then, fixed by the owner: third last the Rust port (20), second last online play
(23), last the ML-trained AI (12, then 1). Alongside: the remaining guessed AI values
(33), the strategy planner's follow-ups (34), To do 18's leftovers.

## Open questions for the owner

1. Answered and built: VP and win conditions over elimination (see docs/RULINGS.md).
2. **Should the value horizon shrink with the difficulty?** Open; owner: "it depends",
   circle back later and don't spend test games on it now. Today every level values a hit
   over the turns left or 6, while the search depth is 0 / 0 / 2 / 3 / 5 / 10 turns. A
   shorter value horizon at low levels would weaken them (damage short of a cripple or kill
   undervalued: spread fire, fewer braces, later disengaging); a longer one changes nothing
   at master (the turn limit caps it). Claude's recommendation: keep it the same.

## Running and testing

- `python run.py` starts the desktop game (needs Tk; on Debian/Ubuntu `apt install python3-tk`).
- `pytest -q` runs the test suite; it does not need Tk. It also never imports the Tkinter
  files, so check they compile: `flake8 --select=E9,F src/` (plain `--select=F` misses
  syntax errors).
- The Tkinter panels can't be unit-tested here; drive the real `GamePanel` under `xvfb-run`
  with a Python that has tkinter when a change touches UI flow.

### How much to test (owner: keep it lean)

- One full `pytest -q` run per slice (about 50s), not test files one by one first; only on a
  failure, run the failing files alone. Read only the last lines of the output.
- The headless runner plays with every advanced rule on by default (`--rules all`, or
  `none` / a list); `tools/refactor_check.sh` uses `--rules none`. One seeded game with
  `--replay-check` checks a change to the AI (`tools/headless_runner.py --no-display
  --games 1 --procs 1 --seed 1 --replay-check`, ~160s a game, ~320s with the replay);
  ask the owner before longer runs.
- `tools/refactor_check.sh` (16 games, minutes) only for pure refactors.
- GUI / spectator games only when a change touches the game flow or the window, at most one
  or two. The full GUI sweep only before a merge to main.
- The ordnance coverage sweep (`BFG_SWEEP=1 pytest -q tests/test_ordnance_coverage.py`,
  ~70s) after any change to ordnance and before a merge.

## Code layout

- Pure-logic engine (no Tk, unit-tested): `models.py`, `game_state.py`, `movement.py`,
  `combat.py`, `ordnance.py`, `end_phase.py`, `boarding.py`, `hit_and_run.py`,
  `turn_controller.py`, `scenario.py`, `victory_points.py`, `geometry.py`, `ai_player.py`,
  `lookahead_ai.py`, and friends; the game flow in `game_flow.py`, recorded actions in
  `actions.py`, replay in `replay.py`, a window-free game in `headless_game.py`.
- Tkinter UI: `game_panel.py` (game flow, AI driver), `board_view.py`, and the
  `*_panel.py` / `*_dialog.py` / `*_ui.py` mixins.
- On hold: the browser client (`web/`, `src/web_*.py`, `netlify.toml`) and LAN multiplayer
  (`network.py`). Don't extend them unless asked.

## Conventions that have caused bugs

- `GameState` stores ships and ordnance as dicts. `get_ships()` / `get_ship_by_id()` return
  copies. Re-read a ship right before changing it and write it back with `gs.update_ship()`.
  Saving an old copy silently undoes newer changes (this caused the fleet re-roll and
  chain-explosion bugs).
- Shields: always use `geometry.current_shields(ship, blast_markers)`. It covers the Shields
  Collapse crit, crippling and blast markers in one place.
- Threads: only the Tk main thread may touch widgets, `ctx.log()` or `board.redraw()`. The
  expert AI search runs on a worker thread that must not call Tk; the main thread polls it.
- Human input during the AI's turn is blocked through `GameContext.actions_locked()`.
- Caches must be pure functions of the game state, never call order (replays); the
  `_state_stamp` memo keeps its records alive (Python reuses ids).
- Tests: use `tests/conftest.py`'s `DiceStub` with realistic die values listed roll by roll,
  and assert every roll was consumed (`dice._idx == len(rolls)`). Impossible rolls (a 12 on
  a D6) once hid a real bug. Set a ship's fields before `make_gs` (it stores copies).

## Git

Work happens on `claude/battlefleet-gothic-simulator-3sUkl`; `main` is the owner's original
upload plus one early merge.
