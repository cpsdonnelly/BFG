# BFG:XR Simulator

A digital play aid for Battlefleet Gothic: Extended Rules (BFG:XR). The desktop app is
Tkinter (`python run.py`); the rules engine is pure Python in `src/`.

## Rules source of truth

- **`bfgxr/` is the rules authority.** Read `bfgxr/CLAUDE.md` before changing any rule or ship
  stat. It is an export of the BFG:XR companion booklet: `bfgxr/rules/` (one Markdown file
  per section) and `bfgxr/data/ships.json` (174 ships, stats and weapons parsed). Never edit
  those generated files by hand; the `.docx` in `bfgxr/source/` is the master.
- Never invent rules, stats or values. If the booklet doesn't cover something, say so and
  ask the owner.
- The booklet is condensed and does **not** cover: boarding actions, the base teleport rules
  (range, which ships may teleport), how many raids assault boats and boarding torpedoes
  make, what boarding torpedoes do on contact, or ramming. Ask before implementing these.
- `data/rules_cheatsheet.txt` and `data/*.csv` (plus the copies in the repo root) are an
  older hand-written summary. Where they disagree with `bfgxr/`, `bfgxr/` wins.
- `src/ship_catalog.py` (hard-coded Imperial Navy and Tau ships) predates the booklet and
  disagrees with it on many stats and weapons.

## Running and testing

- `python run.py` starts the desktop game (needs Tk; on Debian/Ubuntu `apt install python3-tk`).
- `pytest -q` runs the test suite; it does not need Tk.
- The Tkinter panels can't be unit-tested here; drive the real `GamePanel` under `xvfb-run`
  with a Python that has tkinter when a change touches UI flow.

## Code layout

- Pure-logic engine (no Tk, unit-tested): `models.py`, `game_state.py`, `movement.py`,
  `combat.py`, `ordnance.py`, `end_phase.py`, `boarding.py`, `hit_and_run.py`,
  `turn_controller.py`, `scenario.py`, `victory_points.py`, `geometry.py`, `ai_player.py`,
  `lookahead_ai.py`, and friends.
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
- Tests: use `tests/conftest.py`'s `DiceStub` with realistic die values listed roll by roll,
  and assert every roll was consumed (`dice._idx == len(rolls)`). Impossible rolls (a 12 on
  a D6) once hid a real bug.

## Git

Work happens on `claude/battlefleet-gothic-simulator-3sUkl`; `main` is the owner's original
upload plus one early merge.
