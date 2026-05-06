# BFG:XR Simulator

A turn-by-turn Battlefleet Gothic: Expanded Revised simulator with a graphical board viewer.

## Requirements
- Python 3.8+
- Tkinter (included with standard Python on Windows and most Linux)

## Quick Start
```bash
python run.py
```

This launches the board viewer with a demo 800pt Imperial Navy vs Tau Kor'or'vesh game.

## Controls
- **Left click** a ship to select and inspect it (stats shown in right panel)
- **Right click** a ship for context menu (Show Arcs, Show Info)
- **R key** - Toggle ruler tool (click two points to measure distance in cm)
- **A key** - Toggle arc view tool (click a ship to show its fire arcs and range brackets)
- **Escape** - Clear active tool

## Features (Current)
- Graphical board with grid (10cm squares)
- Ships displayed as colored circles with arc crosshairs and forward arrow
- Battleships shown larger than cruisers, cruisers larger than escorts
- Click-to-inspect with full ship stats, weapons, damage, ordnance status
- Arc visualization with range bracket circles and enemy arc highlighting
- Distance measurement ruler with 10cm notch marks
- Blast marker, ordnance, and terrain rendering
- Planet gravity well indicators
- Save/load game state to JSON directory

## Features (Planned)
- Turn-by-turn game logic (movement, shooting, ordnance, end phase)
- Dice rolling (manual entry or computer RNG)
- Two-player async play (save/load at any phase)
- Single-player vs-self mode
- AI commander for spectator mode
- Boarding, ramming, teleport (advanced rules toggle)
- Fleet list builder

## Project Structure
```
bfg_project/
├── run.py                  # Launch script
├── src/
│   ├── main.py             # Entry point with demo fleets
│   ├── models.py           # Ship, Ordnance, Terrain data classes
│   ├── tables.py           # Gunnery, Critical, Catastrophic lookups
│   ├── game_state.py       # Save/load game state
│   └── board_view.py       # Tkinter board viewer
├── data/                   # Reference tables (CSV)
└── saves/                  # Saved games
```

## Color Options for Teams
red, blue, green, yellow, purple, orange, black, white, pink
