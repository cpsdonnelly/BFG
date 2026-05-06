# BFG:XR SIMULATOR - MASTER PLANNING NOTEBOOK
# Consolidation of all design requirements, ideas, and outstanding work

## TABLE OF CONTENTS
1. Architecture Overview
2. Map & Setup System
3. Deployment Phase
4. Turn-by-Turn Game Loop
5. Movement Phase
6. Shooting Phase
7. Ordnance Phase
8. End Phase
9. Game Recording & Replay System
10. Play-by-Mail / Async Multiplayer
11. GUI & Visual Design
12. Scatter Dice & Player Input
13. AI Commander Mode
14. Outstanding Questions & Missing Rules
15. Implementation Priority Order

---

## 1. ARCHITECTURE OVERVIEW

### Core Principle
The game recording, replay, play-by-mail export, and board state merging all
share the same underlying system: a sequence of snapshots and actions that can
be saved, loaded, replayed, and merged. Think of it like a chess PGN file
combined with board state FEN snapshots.

### File Format: Match Record
A match is a directory containing:
```
match_name/
├── match_meta.json        # Game settings, players, factions, board size
├── map.json               # Celestial phenomena layout (shared by both players)
├── snapshots/
│   ├── setup_start.json   # Empty board
│   ├── deploy_p1_01.json  # After P1 places first unit
│   ├── deploy_p2_01.json  # After P2 places first unit
│   ├── ...
│   ├── t1_start.json      # Start of turn 1
│   ├── t1_movement.json   # After movement phase
│   ├── t1_shooting.json   # After shooting phase
│   ├── t1_ordnance.json   # After ordnance phase
│   ├── t1_end.json        # After end phase
│   ├── t2_start.json      # Start of turn 2
│   └── ...
├── actions_log.json       # Every action taken, dice rolled, in order
└── export.bfg             # Single-file compressed export for sharing
```

### Actions Log Format
Each action is a dict:
```json
{
  "turn": 1,
  "phase": "movement",
  "player": 1,
  "action_type": "move_ship",
  "ship_id": "imp_mars",
  "details": {
    "commands": [{"action": "forward", "value": 10}, {"action": "turn_left", "value": 45}, ...],
    "special_order": "lock_on",
    "command_check_roll": [3, 2],
    "command_check_passed": true
  },
  "result": {
    "final_position": [70.0, 25.0],
    "final_heading": 135.0,
    "distance_moved": 18.5
  },
  "timestamp": "2026-04-27T15:30:00"
}
```

This lets us:
- Replay the game step by step (like a chess match viewer)
- Export the current state to send to a friend (play by mail)
- Merge deployment states from two players
- Undo moves within a phase (revert to last snapshot)

---

## 2. MAP & SETUP SYSTEM

### Map is Separate from Everything Else
Two players cannot merge deployment if using different maps.
The map must be agreed upon before deployment begins.

### Board Size
- Default: 120cm x 120cm
- Custom sizes should be supported (e.g. 180x120 for larger games)
- Input via setup dialog

### Sunward Direction
- The Sun is NOT a coordinate point, it is a DIRECTION (an edge of the board)
- Options: North, South, East, West edge
- Compass rose on the GUI should always show Sunward prominently
- All directional references (scatter, solar sails if Eldar added later) 
  use Sunward as the primary reference

### Celestial Phenomena Generation
Two modes:

#### Auto Mode (Random Generation)
1. Determine battlefield location (D6):
   1=Flare Region, 2=Mercurial Zone, 3=Inner Biosphere,
   4=Primary Biosphere, 5=Outer Reaches, 6=Deep Space
2. Roll on the corresponding phenomena table
3. Place phenomena according to placement rules
4. Both players agree on the map before deployment

Rules from the PDF:
- Setting up: Each player alternates placing phenomena
- Phenomena placed in the 4x4 grid of the table
- Max one planet, reroll if second generated
- Phenomena types: Solar Flare, Radiation Burst, Asteroid Field,
  Gas/Dust Cloud, Planet (small/medium/large with moons/rings), Warp Rift
- Asteroid fields: D6x5cm x D6x5cm rectangles
- Gas/Dust clouds: D3 individual clouds, each D6x5cm x D6x5cm
- Planets: small (5cm template), medium (GW large blast), large (CD-sized)
- Gravity wells: small +10cm, medium +15cm, large +30cm from edge
- Moons: roll D6, on 6 planet has a moon
- Rings: large planets roll D6, on 5-6 has rings

#### Manual Mode (Map Editor)
- Player clicks to place phenomena on the board
- Select type from a palette (asteroid, dust, planet, etc.)
- Drag to size for rectangular phenomena
- Set planet size via dropdown
- Save/load map layouts independently of games

### Map File (map.json)
```json
{
  "board_width": 120,
  "board_height": 120,
  "sunward_edge": "west",
  "battlefield_zone": "primary_biosphere",
  "phenomena": [
    {"type": "asteroid_field", "x": 40, "y": 60, "width": 25, "height": 15},
    {"type": "planet_medium", "x": 80, "y": 50, "radius": 5},
    {"type": "gas_dust_cloud", "x": 20, "y": 30, "width": 20, "height": 10},
    ...
  ]
}
```

---

## 3. DEPLOYMENT PHASE

### Standard Cruiser Clash Deployment
- Players alternate placing ships/squadrons
- Escorts in squadrons are placed together
- Ships deploy within 15cm of their table edge
- Strategic consideration: place least important ships first,
  react with important ships (e.g. hiding from nova cannon behind asteroids)

### Ships Start Off-Board
- Before deployment, all ships exist in the roster but have no position
- During deployment, player selects a ship/squadron and places it
- Show ghost preview before confirming placement
- Validate: within deployment zone, not overlapping other ships

### Board State Merging for Play-by-Mail Deployment
Workflow:
1. Both players open the program with the same map loaded
2. Player 1 places a ship, saves/exports their state
3. Sends to Player 2
4. Player 2 loads/merges, sees P1's ship, places their own ship
5. Sends back
6. Repeat until all ships placed
7. Final merge creates the starting board state

Merge logic:
- Map must be identical (hash check)
- Each player's ships are identified by player number
- Merge = take P1's ship positions + P2's ship positions
- Conflict detection: ships overlapping
- After merge, save as the "game start" snapshot

### Alternate: Simultaneous Deployment
- Both players submit full deployment at once
- Merge at the end
- Faster but less tactical

---

## 4. TURN-BY-TURN GAME LOOP

### Turn Sequence (per the rules)
1. MOVEMENT PHASE (active player only)
   - Remove previous special orders (except Brace)
   - For each ship: declare special order (command check), then move
   - If any check fails, no more checks that turn (except Brace)
2. SHOOTING PHASE (active player only)
   - Fire weapons at targets
   - Launch ordnance at END of shooting phase
3. ORDNANCE PHASE (BOTH players)
   - Active player moves ordnance first, then opponent
   - Resolve interactions on contact
4. END PHASE (BOTH players)
   - Boarding/teleport (advanced rules)
   - Damage control (repair crits)
   - Remove blast markers (D6 not touching ships)
   - Remove Brace orders

### Snapshots
Save a snapshot:
- At the start of each turn
- After each phase completes
- Before and after any player decision point (e.g. Brace declaration)

### Undo System
- During movement phase: can undo a ship's movement before phase ends
  (revert ship to its pre-move position from the phase-start snapshot)
- During ordnance placement: ghost positioning before confirming
- Undo does NOT work after a phase is finalized
- Undo button in the GUI, or Ctrl+Z

---

## 5. MOVEMENT PHASE (detailed)

### Two Input Modes

#### Exact Instruction Mode
Player types/selects commands:
- "FORWARD 10" -> move 10cm straight
- "TURN LEFT 45" -> turn 45 degrees port
- "FORWARD 10" -> move another 10cm
System validates in real time and shows preview path

#### Drag-and-Drop Mode
1. Click ship to select
2. Drag to show projected path
3. Click to set turn waypoint
4. System enforces minimum distance before turn
5. Confirm with right-click or Enter
6. Ghost ship shown at projected final position

### Validation Rules (enforced in both modes)
- Ships MUST move unless on Burn Retros
- Minimum move = half speed
- Minimum distance before turning: BS 15cm, CR 10cm, Escort 0cm
- Turn angle <= ship's max (45° or 90°)
- Max turns: 1 normally, 0 on AAF/LockOn, 2 on CtNH
- Ponderous ships cannot use CtNH
- Moving through blast markers: -5cm speed (once, not per marker)
- Ship moved <5cm counts as Defenses on gunnery table
- AAF: must move full distance (speed + 4D6), no turns
- Burn Retros: 0 to half speed, can be stationary

### Gravity Well Free Turns
- Ship starting or ending in gravity well gets free turn toward planet
- No minimum distance needed
- Works on AAF and Lock On
- Stacks with CtNH

### Movement Recording
Each ship movement is recorded as:
```json
{
  "ship_id": "imp_mars",
  "start_pos": [60, 15],
  "start_heading": 90,
  "commands": [...],
  "end_pos": [60, 35],
  "end_heading": 135,
  "distance": 22.5,
  "special_order": "lock_on",
  "crossed_blast_markers": false
}
```

---

## 6. SHOOTING PHASE

### Weapons Battery Resolution
1. Choose target
2. Check arc and range
3. Calculate total firepower (halve if crippled/on certain orders)
4. Determine target orientation (closing/abeam/moving_away)
5. Look up dice on gunnery table with column shifts
6. Roll dice vs armor value
7. Lock On: reroll misses
8. Each hit past shields: D6 for crit (6 = crit, roll 2D6 on crit table)

### Lance Resolution
- Hit on 4+ regardless of armor
- NOT affected by blast marker column shifts
- Affected by Lock On rerolls

### Nova Cannon
- Template placement, scatter based on range bracket
- Any base touching template: 1 auto hit
- Base touching center hole: D6 hits (ignores armor)
- Not affected by any special orders
- Crippled ships cannot fire

### Brace For Impact
- Declared per attacker, before their combat rolls
- 4+ save per hull hit (not shield hits)
- Replaces current special orders
- Lasts until end of NEXT turn
- Halves all offensive output next turn
- In async play: attacker fires, saves state, asks defender if they brace,
  defender responds, then damage is applied

### Shooting Recording
Each shot recorded with full dice results:
```json
{
  "attacker_id": "imp_mars",
  "target_id": "tau_custodian",
  "weapon": "Port Weapons Battery",
  "firepower": 6,
  "dice_rolled": [1, 3, 4, 5, 5, 6],
  "rerolls": [2, 5],
  "hits": 4,
  "shield_absorbed": 3,
  "hull_damage": 1,
  "crit_roll": 3,
  "crit_result": null
}
```

---

## 7. ORDNANCE PHASE

### Torpedo Movement
- Imperial: dumb fire, 30cm straight, no turning
- Tau missiles: guided, 20-40cm speed, can turn 45° at start
- Tau missile degradation: each ordnance phase, roll 1D6 per strength
  for salvos from PREVIOUS turns, each 1 = -1 strength

### Attack Craft
- Fighters: mutual destruction on contact with ordnance
- Bombers: D6 attacks per squadron vs lowest armor, turrets reduce attacks
- Mantas (Tau): resilient 4+ save when intercepted, count as fighter+bomber
- Barracudas (Tau): fighters
- Waves: multiple squadrons in formation, turrets fire once vs whole wave

### Ghost Positioning for Ordnance
- Before confirming launch, show ghost markers at intended positions
- Player can drag/adjust ghost markers
- Torps: show projected path (straight line for Imperial, arc for Tau guided)
- Confirm with Enter/right-click
- Can cancel and reposition before confirming

### Ordnance Interaction Matrix
| Attacker     | vs Fighter | vs Bomber | vs Torpedo | vs Ship |
|-------------|------------|-----------|------------|---------|
| Fighter     | Both die   | Bomber dies| Both die  | No effect|
| Bomber      | Bomber dies| Both pass | Both pass  | Attack  |
| Assault Boat| AB dies    | Both pass | Both pass  | Hit&Run |
| Manta       | 4+ save    | 4+ save   | 4+ save   | Attack  |
| Torpedo     | Both die   | Both pass | Both die   | Attack  |

---

## 8. END PHASE

### Damage Control (Repair Crits)
- Each capital ship rolls 1D6 per remaining HP
- Each 6 repairs one repairable crit
- Ships touching blast markers: half dice (round up)
- Fire crits: each unrepaired fire deals 1 damage

### Blast Marker Removal
- Active player rolls D6
- Remove that many blast markers NOT touching any ship

### Boarding Actions (Advanced Rules, default OFF)
- Ship in base contact declares boarding
- Compare troop ratings + modifiers
- Loser takes damage = difference in scores
- Tau Kor'vattra halve troop rating; Kor'or'vesh don't

### Teleport Attacks (Advanced Rules, default OFF)
- Within 10cm, target shields must be down
- Resolved as hit-and-run raid

---

## 9. GAME RECORDING & REPLAY SYSTEM

### Design: Like a Chess Match Viewer

The recording is the actions_log.json file containing every action in order.
Combined with periodic snapshots, this allows:

1. Step forward/backward through the game
2. See each ship's movement path
3. See each dice roll result
4. See the board at any point in time

### Replay Controls (in GUI)
- Play/Pause button
- Step Forward (next action)
- Step Backward (previous action)
- Jump to Turn N
- Jump to Phase
- Speed slider for auto-play
- Show/hide movement trails

### Recording Content Per Action
- What happened (move, shoot, launch, repair, etc.)
- Who did it (ship ID)
- Full dice results
- Board state changes
- Narrative description for the log
  e.g. "INS Throne Eternal fired port lances at Or'es El'leath,
        rolled 2 & 3, both missed"

### Match Summary
At end of game, auto-generate:
- Total damage dealt per ship
- Kill counts
- VP tally
- Key moments (first blood, critical hits, catastrophic explosions)

---

## 10. PLAY-BY-MAIL / ASYNC MULTIPLAYER

### Workflow
1. Player A completes their turn phases
2. System saves snapshot + action log
3. Player A exports to a single .bfg file (compressed JSON archive)
4. Sends file to Player B (email, Discord, etc.)
5. Player B loads the file, sees the board after A's turn
6. If Brace decisions are needed, B is prompted
7. B takes their turn, exports, sends back

### Brace For Impact in Async
When A fires at B's ships:
1. A's shooting is resolved UP TO the damage application
2. State saved with pending damage
3. B loads state, sees incoming fire, decides to Brace or not per attacker
4. Damage applied based on B's Brace decisions
5. B's turn begins

### Export Format (.bfg file)
- ZIP archive containing the match directory
- Includes all snapshots up to current point
- Includes complete action log
- Includes the map
- Single file for easy sharing

---

## 11. GUI & VISUAL DESIGN

### Ship Rendering
- Ships are colored circles: Red team vs Blue team (configurable)
- Arc crosshair lines through the circle (4 quadrants: front/left/right/rear)
- Yellow arrow showing forward arc
- Battleships = larger circles (3cm radius), Cruisers = 1.6cm, Escorts = 1.2cm
- HP bar above ship
- Special order indicator label
- Click to inspect (stats popup in side panel)
- Crippled ships: darker fill color
- Destroyed ships: grey fill

### Color Options
red, blue, green, yellow, purple, orange, black, white, pink

### Ordnance Rendering
- Torpedoes: small triangles pointing in heading direction, colored by owner
  Strength number shown nearby
- Fighters: small diamond/chevron shape with "F" label
- Bombers: small diamond with "B" label
- Mantas: slightly larger diamond with "M" label (to show they're special)
- Barracudas: diamond with "Br" label
- Mixed waves: cluster of appropriate shapes together
- Torpedo waves: row of triangles

### Terrain Rendering
- Asteroid fields: lattice/scatter of small brown circles within the boundary
  (random positions within the rectangle, ~10-15 small circles)
- Gas/Dust clouds: soft-edged blob shape (like a child's cloud drawing)
  Semi-transparent blue-grey fill with puffy outline
- Planets: solid circle with color based on size
  Gravity well shown as dashed circle around planet
  Moon as small grey circle nearby if applicable
  Rings as an ellipse if applicable
- Warp Rifts: dark purple rectangle with "WARP RIFT" label, ominous styling
- Solar Flares / Radiation: these are events, not terrain, handled as
  per-turn effects rather than board objects

### Compass Rose
- Always visible on the board (corner)
- Shows N/S/E/W
- Sunward edge highlighted prominently
- Used as reference for scatter dice direction input

### Tools
- R: Ruler (point-to-point with ship snap)
- D: Ship distance (ship-to-point or ship-to-ship)
- A: Arc view (show fire arcs, range brackets, enemies in each arc)
- C: Clear rulers
- Escape: Clear active tool

### Planned Tools
- Movement preview tool (show projected path)
- Ordnance launch preview (ghost markers)
- LoS checker (draw line, show if obstructed by terrain)

---

## 12. SCATTER DICE & PLAYER INPUT

### Scatter Dice Simulation
- 2/6 chance of HIT (result stays in place)
- 4/6 chance of SCATTER (moves in arrow direction)
- Arrow direction: random angle 0-360°

### Computer RNG Mode
- Roll automatically, display result

### Manual Input Mode
For the scatter direction when player rolls physical dice:
- Open a separate input window
- Show the compass rose (matching the board compass, Sunward reference)
- Player draws a line/clicks a direction on the compass to indicate
  which way their physical scatter die arrow pointed
- System converts click angle to game heading

### Scatter Distance
- Based on range bracket: 1D6 (<45cm), 2D6 (45-60cm), 3D6 (60-150cm)
- Rolled separately after determining scatter direction

---

## 13. AI COMMANDER MODE

### Purpose
- Allow spectating AI vs AI games to evaluate fleet compositions
- Requires global auto-RNG mode (no manual dice input)
- Both fleets commanded by simple AI logic

### AI Decision Framework (simple, not trying to be perfect)
Movement: Close to weapon range, avoid presenting rear arc
Shooting: Prioritize targets by threat (most firepower, least HP)
Orders: Lock On when in range and facing target, AAF to close distance,
        Reload Ordnance after launching, Brace when heavily damaged
Ordnance: Launch bombers at biggest target, fighters to intercept

### Implementation: Last priority, after everything else works

---

## 14. OUTSTANDING QUESTIONS & POTENTIALLY MISSING RULES

### Things to verify against the PDF:
- [ ] Disengagement rules (voluntary withdrawal, leaving table edge)
- [ ] Escort squadron coherency rules (how close must they stay?)
- [ ] Target priority rules (must fire at closest unless passing Ld test)
- [ ] How do mines work? (mentioned in ordnance but not detailed)
- [ ] Reload Ordnance: does it let you launch SAME turn or NEXT turn?
      Answer from user: if you already have ordnance loaded, Reload gives
      no benefit. First launch doesn't need Reload.
- [ ] Leadership tests during the game (beyond command checks)
- [ ] Morale / disengagement tests when crippled?
- [ ] How exactly do attack craft waves interact with turrets?
- [ ] Can ships split battery fire between multiple targets?
      Answer: Yes, if FP >= 2 after modifiers, with target priority test
- [ ] How do Tau deflectors interact with different attack types?
- [ ] Exact rules for ship overlapping / stacking during movement
- [ ] Campaign rules (if ever wanted)

### Rules confirmed by Ciarán:
- Tau towed escorts don't count for VP
- Brace can always be attempted even after failed command check
- Each hit has potential crit (D6 per hit, 6 = crit)
- Ships cannot stay still without Burn Retros
- Custodian tracking systems: 20cm range (enhanced)
- Standard tracking systems: 10cm range
- Mantas are resilient (4+ save)
- Imperial torps are dumb fire, Tau missiles are guided
- Tau missiles degrade each ordnance phase

---

## 15. IMPLEMENTATION PRIORITY ORDER

### Phase 1: DONE
- [x] Data models (Ship, Ordnance, BlastMarker, Phenomenon)
- [x] Gunnery table, crit table, catastrophic table
- [x] Game state save/load
- [x] Board viewer GUI (ships, terrain, blast markers, ordnance)
- [x] Ruler tools (point-to-point, ship snap, ship distance, measure all)
- [x] Arc view tool
- [x] Rules cheat sheet

### Phase 2: IN PROGRESS
- [x] Dice roller module (manual/auto/mixed)
- [x] Movement validation engine
- [x] Combat resolution (batteries, lances, nova cannon)
- [x] Damage application (shields, hull, crits, catastrophic)
- [ ] Ordnance resolution module
- [ ] End phase module
- [ ] Turn flow controller (ties phases together)
- [ ] GUI integration: movement input dialogs
- [ ] GUI integration: shooting target selection
- [ ] GUI integration: ordnance placement

### Phase 3: RECORDING & REPLAY
- [ ] Snapshot system (save state at each phase boundary)
- [ ] Actions log (record every action with dice results)
- [ ] Replay viewer (step forward/backward through actions)
- [ ] Match export (.bfg file format)

### Phase 4: DEPLOYMENT & MAP
- [ ] Map editor (place phenomena manually)
- [ ] Celestial phenomena random generation
- [ ] Deployment phase (alternating ship placement)
- [ ] Board state merging (for async deployment)
- [ ] Compass rose with Sunward reference

### Phase 5: ASYNC MULTIPLAYER
- [ ] Export/import board state as single file
- [ ] Brace decision prompt on load
- [ ] Merge workflow for deployment

### Phase 6: POLISH
- [ ] Movement undo within phase
- [ ] Ghost ordnance positioning
- [ ] Movement trails on replay
- [ ] Match summary generation
- [ ] LoS checking tool
- [ ] Better terrain rendering (asteroid scatter, cloud blobs)

### Phase 7: ADVANCED & EXTRAS
- [ ] Boarding actions
- [ ] Ramming
- [ ] Teleport attacks
- [ ] AI commander mode
- [ ] Fleet list builder
- [ ] Additional factions
- [ ] Simultaneous activation alternate ruleset (experimental)
