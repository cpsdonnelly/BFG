# BFG:XR Simulator

A digital play aid for Battlefleet Gothic: Extended Rules (BFG:XR): a Tkinter board with the
full rules engine, an expected-VP AI and a fleet builder. The rules and ship stats come from the
BFG:XR companion booklet export in `bfgxr/`.

## Requirements
- Python 3.8+
- Tkinter (included with standard Python on Windows; on Debian / Ubuntu `apt install python3-tk`)

## Quick Start
```bash
python run.py
```

This opens the setup wizard. Its defaults start a demo game: the 1000pt Gothic Sector
Imperial Navy fleet against the 1000pt Tau Merchant fleet, on the demo terrain (an asteroid
field, a dust cloud and a planet). Each player deploys (or presses Auto-Place), then the turns
begin. In the wizard you can instead:

- pick any fleet in `data/fleets/` for either player, or build one in the fleet builder;
- play hot seat, against the AI (Player 2), or watch the AI play itself (spectator mode,
  each side with its own difficulty);
- choose a scenario (31 booklet scenarios, with sub-plots), random or blank terrain, the
  dice mode (rolled for you, or typed in from real dice), and the advanced rules (boarding,
  ramming, teleports, hit-and-run raids, celestial effects, Remastered options, alternate
  activation).

## The 1000pt fleets
`data/fleets/` holds fifteen 1000pt-or-under fleets, each built and validated in the fleet
builder against its booklet fleet list: 13th Black Crusade (Chaos), Gothic Sector, Bakka
Sector, Tau Merchant, Tau Protector, Space Marine Crusade, Mechanicus Explorator, Ork Green
Tide, Necron Dynasty (with and without the War refit), Corsair Eldar, Dark Eldar Raiders and
three Tyranid fleets (Gestating, Vanguard, Hive). `tools/build_owner_fleets.py` rebuilds them.

## Controls
- **Left click** a ship to select and inspect it (stats in the right panel)
- **Right click** a ship for its context menu (Show Arcs, Show Info); in deployment it turns a
  placed ship
- **R key** - ruler (click two points to measure in cm)
- **A key** - arc view (click a ship to show its fire arcs and range brackets)
- **Ctrl+Z** - in deployment, take back the last placed group
- **Escape** - clear the active tool
- The phase panel's buttons give each phase's actions (move, special orders, fire, launch
  ordnance, attack craft orders, end phase)

## Features
- Every core rules section the engine plays: movement and special orders, direct fire on the
  Gunnery table, lances, nova cannon, shields and blast markers, ordnance (torpedo types,
  attack craft, waves, CAP, mines, torpedo bombers), squadrons, ramming, boarding, hit-and-run
  raids and teleports, damage, criticals and catastrophic damage, disengaging, victory points
- Every faction in the booklet, with fleet lists, commanders, refits and options: Imperial Navy,
  Chaos, Adeptus Mechanicus, Space Marines, Inquisition / Grey Knights, Orks, Tau (and
  Demiurg), Rogue Traders, Eldar (MMS v2.0), Dark Eldar, Necrons and Tyranids
- Fleet builder with live fleet-list checking and a ship card for every ship
- The booklet's scenarios and sub-plots, low orbit, planets, asteroid fields and other terrain
- AI opponents (easy, normal, expert) that choose by expected victory points; "Auto" on every
  choice prompt picks what the AI would
- Alternate activation, an optional ruleset (three activation-order systems)
- Seeded, recorded dice and decisions: games can be saved, loaded and replayed exactly
- A headless runner for AI-vs-AI games in bulk (`tools/headless_runner.py`)

## Running the tests
```bash
pytest -q                              # the rules engine and AI (no Tk needed)
flake8 --select=E9,F src/              # the Tk files compile
python tools/headless_runner.py --no-display --games 4   # AI-vs-AI games, no window
```

## Project Structure
```
├── run.py                  # Launch script
├── bfgxr/                  # The rules authority: the booklet export (rules, ships.json)
├── src/
│   ├── main.py             # Entry point and setup wizard
│   ├── models.py           # Ship, ordnance and terrain data classes
│   ├── game_state.py       # Game state, save / load
│   ├── movement.py, combat.py, ordnance.py, end_phase.py, ...   # the rules engine
│   ├── ship_catalog.py     # Ships built from bfgxr/data/ships.json
│   ├── fleet_lists.py      # Fleet lists (s.4)
│   ├── fleet_builder.py    # Fleet builder window
│   ├── ai_player.py, ai_hazards.py, lookahead_ai.py   # the AI
│   └── board_view.py, game_panel.py, ...              # Tkinter board and panels
├── data/fleets/            # Saved fleets
├── tests/                  # pytest suite
└── tools/                  # Headless runner, fleet builder script, GUI checks
```

`CLAUDE.md` and `docs/HANDOFF.md` hold the detailed status, owner rulings and the to-do list.

## Color Options for Teams
red, blue, green, yellow, purple, orange, black, white, pink
