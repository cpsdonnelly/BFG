# BFG:XR SIMULATOR - PROJECT NOTEBOOK
# Consolidation of all plans, feature requests, design decisions, and TODOs
# Last updated: Session building game logic modules

═══════════════════════════════════════════════════════════════════
## 1. COMPLETED WORK
═══════════════════════════════════════════════════════════════════

### Core Data Model (models.py)
- Ship class with full stat tracking, arcs, orientation, damage
- OrdnanceMarker class (torpedoes, attack craft)
- BlastMarker class
- Phenomenon class (planets, asteroids, dust, warp rifts)
- All position/heading math (bearing, arc detection, orientation)

### Reference Tables (tables.py)
- Gunnery table (FP 1-20, 5 columns, handles FP>20 via split)
- Column shift logic (<15cm left, >30cm right, blast markers right)
- Critical hits table (2D6 with extra damage and repairability)
- Catastrophic damage table (2D6)
- Leadership table (D6 at game start)

### Game State Manager (game_state.py)
- Save/load to JSON directory (ships, ordnance, blast markers, phenomena)
- Ship CRUD operations
- Turn logging

### Board Viewer GUI (board_view.py)
- Tkinter canvas with cm-precision coordinate system
- Ships as colored circles with arc crosshairs and forward arrow
- Battleships rendered larger than cruisers/escorts
- HP bars, special order indicators, crippled/destroyed states
- Click-to-inspect with full ship details in side panel
- Ruler tool (R) with ship snap and persistent lines
- Ship distance tool (D) with snap
- Right-click "Measure to all enemies"
- Arc view tool (A) showing fire arcs and range brackets
- Clear rulers (C)
- Grid, terrain, blast markers, ordnance rendering
- Planet gravity well indicators

### Dice System (dice.py)
- Auto (computer RNG), Manual (player types results), Mixed (popup with both options)
- D6, 2D6, D3, scatter die
- Roll logging

### Movement Phase (movement.py)
- MoveCommand sequence (forward/turn_left/turn_right)
- Full validation: min distance before turning (15cm BB, 10cm CA, 0 escort)
- Speed limits per special order
- Turn count limits (0 for AAF/LO, 1 normal, 2 CtNH)
- Ponderous restriction (no CtNH)
- Blast marker slowdown
- Mandatory movement (must move unless Burn Retros)
- <5cm = Defenses on gunnery table
- Table boundary checking

### Combat System (combat.py)
- Weapons battery resolution (gunnery table, column shifts, armor)
- Lance resolution (4+ to hit, ignores armor)
- Nova cannon (template, scatter by range bracket, D6 center hits)
- Lock On re-rolls for batteries and lances
- Damage application (shields via blast markers, hull HP, crit checks)
- Crippled state effects (halve everything)
- Special order effects on firepower
- Catastrophic damage resolution
- Critical damage: fire, engine room, thrusters, bridge, shields, armament

### Ordnance Phase (ordnance.py)
- Torpedo launch and movement
- Tau guided missile turn + degradation (D6 per strength, 1=lose 1)
- Torpedo vs ship (turrets defend, roll vs armor, bypass shields)
- Bomber attack (D6 attacks minus turrets, vs lowest armor)
- Fighter intercept (mutual destruction)
- Resilient saves (Mantas 4+, once per phase)
- Ordnance vs blast markers (destroyed on 6)
- Attack craft launch from bays

### End Phase (end_phase.py)
- Fire damage (1 per unrepaired Fire! crit)
- Damage control (1D6 per remaining HP, 6s repair crits)
- Blast marker contact halves repair dice
- Blast marker removal (D6 not touching ships)
- Brace order removal

### Turn Controller (turn_controller.py)
- Phase sequencing: Movement -> Shooting -> Ordnance -> End
- Turn advancement with player swap
- Snapshot system for undo
- Action recording with timestamps
- Match export/import (zip file)
- Special order issuance with command checks

### Game Panel GUI (game_panel.py)
- Phase indicator (turn, phase, active player)
- Movement dialog (special order + move commands)
- Shooting dialog (pick ship, pick weapon, pick target)
- Launch ordnance dialog
- End Phase button with unmoved ship warnings
- Game log display
- Undo ship movement

### Demo Fleets (main.py)
- Imperial Navy 800pts (Mars + 2 Lunars + 3 Cobras)
- Tau Kor'or'vesh 800pts (Custodian + 2 Emissaries + 3 Wardens + Castellan)
- Full weapon/stat definitions


═══════════════════════════════════════════════════════════════════
## 2. FEATURE ROADMAP (ordered by priority)
═══════════════════════════════════════════════════════════════════

### Priority A: Core Gameplay (needed for a playable game)

A1. SCATTER DICE SYSTEM
    - 2/6 chance of hit, 4/6 chance of scatter
    - Auto mode: random angle 0-360 degrees
    - Manual mode: player draws an arrow direction on a mini-canvas
      with a compass rose matching the board's sunward orientation
    - The compass/sunward direction is a board-wide reference
      (sun is a DIRECTION, not a coordinate point)
    - Already partially implemented in dice.py, needs manual input mode

A2. ORDNANCE GHOST POSITIONING
    - Before confirming torpedo/craft launch, show a ghost marker
    - Player can drag the ghost to adjust launch angle
    - Confirm button to finalize placement
    - This applies during the shooting phase (ordnance placed at end)

A3. DEPLOYMENT PHASE
    - Players take turns placing ships onto the board
    - Escorts in squadrons placed together
    - Ships start OFF-BOARD (in a staging area)
    - Strategic element: place least important ships first
    - Need a deployment UI: ship list -> click board to place -> confirm
    - Board state merging (see A4)

A4. BOARD STATE MERGING
    - Two players each have the program open during deployment
    - Each places ships on their side
    - Export deployment -> send to opponent -> merge
    - Merge = combine two partial board states into one complete game
    - Must validate: ships stay on their deployment zone side
    - Uses the same snapshot/export system as match recording

A5. CELESTIAL PHENOMENA GENERATION
    - Located in rulebook at print page 48 (digital page 53)
    - Random generation using the tables in the book
    - Six zone types with different generation tables
    - Auto mode: roll on tables, place randomly
    - Manual/editor mode: player places terrain pieces freely
    - Blank board should also be an option
    - MAP IS THE FOUNDATION: two players can't merge deployment
      if using different maps, so map must be established first
    - Map maker should be SEPARATE from game play
    - Custom board size option

A6. CUSTOM BOARD SIZE
    - Default 120x120cm
    - Allow arbitrary dimensions
    - Scale viewer accordingly


### Priority B: Match Recording & Replay

B1. MATCH RECORDING (like chess PGN)
    - Record every action with dice results
    - Format: "T1 Movement: INS Throne Eternal issues Lock On (2D6=4, pass)"
    - "T1 Shooting: INS Sword of Bakka fires Port Battery at Or'es El'leath,
      FP6 vs closing capital, 5 dice vs 5+, rolled [3,5,6,2,4] = 2 hits"
    - Record initial positions (start of each turn saved as snapshot)
    - Save final orders at end of each phase
    - Already partially implemented via ActionRecord in turn_controller

B2. MATCH REPLAY / SLIDESHOW
    - Load a recorded match
    - Step through turn-by-turn, phase-by-phase
    - Show board state at each snapshot point
    - Forward/back controls like a chess engine
    - Display the action log for each step
    - "What happened here" annotations

B3. PLAY-BY-MAIL EXPORT
    - Export game state at any save point
    - Import and continue play
    - Same underlying system as match recording
    - Brace For Impact handling: save -> send to opponent ->
      they input brace decision -> save -> send back -> continue
    - MUST save after every phase and after every significant decision point

B4. UNDO SYSTEM
    - Movement phase: undo individual ship movements (already built)
    - Pre-launch: ghost positioning before confirming ordnance
    - Initial positions preserved (not overwritten) for replay
    - Snapshot at start of each phase


### Priority C: Visual & UI Polish

C1. TERRAIN VISUALS
    - Asteroid fields: lattice of small brown circles
    - Dust clouds: cloud-shaped outlines (like a child's cloud drawing)
    - Planets: filled circles with gravity well ring (already done)
    - Warp rifts: purple swirl area (already basic)

C2. ORDNANCE VISUALS
    - Torpedoes: small triangles pointing in heading direction (already done)
    - Fighters: small diamond shapes
    - Bombers: small square shapes (already basic)
    - Mixed waves: grouped markers with type indicators
    - Mantas: slightly larger squares (resilient indicator?)
    - Color-coded by player

C3. COMPASS ROSE
    - On-board compass showing sunward direction
    - Fixed position (corner of board)
    - Used as reference for scatter dice manual input
    - Rotates based on which edge is sunward

C4. MOVEMENT PATH PREVIEW
    - When entering move commands, show dotted path preview
    - Ghost ship at projected position
    - Show remaining movement budget
    - Highlight valid turn zones (where minimum distance is met)
    - Two modes: exact instructions OR drag-and-drop (from MOVEMENT_DESIGN.md)


### Priority D: Advanced Rules & AI

D1. BOARDING ACTIONS (toggle: advanced_rules)
    - Attacker moves into base contact
    - Troop rating comparison
    - D6 + modifiers
    - Loser takes damage

D2. RAMMING (toggle: advanced_rules)
    - Requires All Ahead Full
    - Leadership test to hit
    - Mutual damage

D3. TELEPORT ATTACKS (toggle: advanced_rules)
    - Shields must be down
    - Within 10cm
    - Hit-and-run raid

D4. AI COMMANDER
    - Simple decision making per phase
    - Auto-play mode for spectator games
    - Global auto-RNG setting for AI vs AI

D5. SIMULTANEOUS ALTERNATE ACTIVATIONS
    - Optional alternate ruleset (for later)
    - Instead of IGOUGO, players alternate activating individual ships
    - Would use the board state merging infrastructure


### Priority E: Fleet Building & Faction Support

E1. FLEET LIST BUILDER
    - Points calculator
    - Composition rule validation
    - Ship database with stats
    - Imperial Navy + Tau Kor'or'vesh first

E2. ADDITIONAL FACTIONS
    - Each faction adds non-standard rules
    - Start with Imperial + Tau only
    - Framework should be extensible


═══════════════════════════════════════════════════════════════════
## 3. DESIGN DECISIONS & NOTES
═══════════════════════════════════════════════════════════════════

### Sunward Direction
- The sun is a DIRECTION (edge), not a point on the board
- Expressed as which board edge is sunward: north/south/east/west
- Affects Eldar solar sail movement (not relevant for current factions)
- Used as compass reference for scatter dice and general orientation
- All angular references should be expressible relative to sunward

### Board Coordinate System
- Origin (0,0) at bottom-left corner
- X increases rightward, Y increases upward
- All measurements in cm with float precision
- Heading: 0° = east/right, 90° = north/up, 180° = west/left, 270° = south/down

### Save System Architecture
- Every game uses a directory under saves/
- Snapshots taken at: start of each phase, before/after significant actions
- Snapshots are numbered sequentially with descriptive labels
- Match recording = ordered list of snapshots + action records
- Export = zip of entire save directory
- Import = unzip + load
- Merge = load two states, combine ship lists, validate no conflicts

### Blast Marker Tracking
- Each blast marker has x,y position (NOT just "touching ship X")
- Ships check contact with blast markers by distance to base
- Blast markers from shield hits placed touching ship base,
  oriented toward the attack origin
- Max around a base per turn: 3-5 (small base), 5-8 (large base)

### Tau Special Rules Implemented
- Kor'or'vesh: no boarding penalty, cannot teleport
- Kor'vattra: halve troop rating for boarding, cannot teleport
- Guided missiles: 20-40cm speed, 45° turn, degradation
- Mantas: resilient 4+ save, count as fighter+bomber
- Tracking systems: 10cm standard, 20cm Custodian
- Deflector: prow armor equivalent
- Ponderous (Custodian): no Come to New Heading

### Imperial Special Rules Implemented
- Standard torpedoes: dumb fire, 30cm, no turning
- Targeting Matrix (Mars): extra left column shift on batteries
- Lock On: re-roll misses for lances AND gunnery
- Nova cannon: not affected by Lock On or Reload Ordnance


═══════════════════════════════════════════════════════════════════
## 4. KNOWN ISSUES & QUESTIONS TO RESOLVE
═══════════════════════════════════════════════════════════════════

- Need to verify: turret range (standard turrets have no listed range
  in core rules - they just fire at ordnance attacking the ship)
- Need to clarify: exact interaction of torpedo movement timing
  with ship movement within the ordnance phase
- Need to verify: can a ship brace vs ordnance in the ordnance phase?
  (Yes - Brace can be declared before any combat rolls)
- Tracking systems aura: need to check nearby Tau ships in shooting,
  not just the ship itself
- Wave formation mechanics need more detail from rulebook
- Splitting fire for batteries (FP 2+ after modifiers can split)
- Target priority test for secondary targets
- Disengagement rules (ships leaving the table)
- Crippled + Braced double-halving of armaments


═══════════════════════════════════════════════════════════════════
## 5. FILE INVENTORY
═══════════════════════════════════════════════════════════════════

src/
  __init__.py          - Package marker
  main.py              - Entry point, demo fleet definitions, GUI launch
  models.py            - Data classes (Ship, Ordnance, BlastMarker, Phenomenon)
  tables.py            - Gunnery, crit, catastrophic lookup tables
  game_state.py        - Save/load, ship CRUD, turn logging
  board_view.py        - Tkinter canvas board viewer with tools
  dice.py              - Dice roller (auto/manual/mixed)
  movement.py          - Movement validation and execution
  combat.py            - Shooting resolution (batteries, lances, nova cannon, damage)
  ordnance.py          - Torpedo/craft launch, movement, attacks, intercepts
  end_phase.py         - Fires, repairs, blast removal
  turn_controller.py   - Phase sequencing, snapshots, action recording, export
  game_panel.py        - GUI controls for turn flow, movement/shooting dialogs

data/
  gunnery_table.csv
  critical_hits_table.csv
  catastrophic_damage_table.csv
  special_orders_reference.csv
  rules_cheatsheet.txt

docs/
  README.md
  MOVEMENT_DESIGN.md
  PROJECT_PLAN.md        (superseded by this notebook)
  PROJECT_NOTEBOOK.md    (this file)

run.py                   - Launch script
