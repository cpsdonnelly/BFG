# BFG:XR SIMULATOR - PROJECT STATUS
# Updated after split fire + blast marker fixes

═══════════════════════════════════════════════════════════════════
## FULLY PLAYABLE (tested, working)
═══════════════════════════════════════════════════════════════════

### Movement Phase
- Special orders with command checks and roll feedback
- Fleet commander re-rolls on failed checks
- Full movement validation (speed, turn distance, turn count, ponderous)
- Movement preview path on canvas with ghost ship
- Quick buttons: Min Move, Pre-Turn, Full Speed, Remaining
- Quick turn buttons: ↶/↷ at 5°, 15°, 30°, 45°
- Anticlockwise/Clockwise naming
- Override option for unmoved ships
- Undo ship movement
- Disengagement (voluntary + involuntary off-table)

### Shooting Phase
- Per-weapon selection with individual target assignment (split fire)
- Split VOLLEY within a weapon (fire 1 of 2 lance shots at one target)
- Strength entry per weapon to allocate partial strength
- Auto: Full Volley at Closest button
- Weapons fired tracking (per-weapon, per-strength, allows return for remaining)
- Unfired weapons warning at end of shooting phase
- Target priority Ld test for non-closest target (skips blocked targets)
- Line of sight checking (planets, asteroids, warp rifts block; dust clouds shift)
- Lock On re-rolls for batteries and lances
- Nova cannon (scatter, template, proper rules)
- Column shifts (range, blast markers, dust clouds, targeting matrix, tracking systems)
- Tau tracking systems aura (Custodian 20cm, checks nearby allies)
- Brace For Impact (4+ save on hull hits only, not shields)
- Critical hits table with extra damage
- Crippled state halving
- Escort destruction (blast marker, no catastrophic table)
- Capital ship catastrophic damage (drifting hulk, burning hulk, explosion)

### Shields & Blast Markers
- Blast markers placed only for shield hits (not hull damage)
- Non-overlapping placement with 2.2cm minimum spacing
- Fanned around ship base, outside base radius
- Per-turn maximum (3-5 small base, 5-8 large base)
- Ship info shows actual shields reduced by touching blast markers
- Blast marker trefoil shape visible on board

### End Phase
- Fire damage (1 per unrepaired Fire! crit)
- Damage control (1D6 per HP, 6s repair, halved if in blast markers)
- Blast marker removal (D6 not touching ships)
- Brace expiry

### Other Systems
- Disengagement with Ld modifiers and re-roll option
- Victory Points (destroyed, crippled, scattered, holding field, hulks)
- Save/load game state (JSON directory)
- Match export/import (ZIP)
- Snapshot system for undo and replay
- Action recording with timestamps

### Board Viewer
- Ship circles with arc crosshairs and heading arrow
- Special order icons (geometric, matching rulebook style)
- HP bars, crippled/destroyed states
- Blast marker trefoil at correct scale
- Ordnance markers (torpedoes, fighters, bombers, mantas) team-colored
- Terrain (asteroid lattice, dust cloud shapes, planets with gravity wells, warp rifts)
- Compass rose with sunward direction
- Ruler tools with ship snap
- Arc view with range brackets
- Help menu with keyboard shortcuts
- Click-to-inspect with full ship stats


═══════════════════════════════════════════════════════════════════
## CODED BUT NEEDS TESTING / POLISH
═══════════════════════════════════════════════════════════════════

### Ordnance Phase Movement
- Code exists and is wired to phase transition
- Torpedoes move along heading
- Tau missile degradation
- Torpedo contact detection and resolution
- Bomber attacks on contact
- Blast marker destruction (D6=6)
- NEEDS: torpedo heading control at launch (currently launches at ship heading)
- NEEDS: attack craft wave composition picker in UI
- NEEDS: fighter intercept resolution during movement

### Manual Dice Input
- Mixed mode dialog (manual entry + auto-roll button)
- Fixed: removed grab_set conflict, added error handling
- NEEDS: thorough testing in live game

### Ship Database
- data/ship_database.json with full stats for:
  - Imperial Navy Gothic Sector (14 ship classes)
  - Tau Kor'or'vesh (5 ship classes)
- Includes costs, weapons, upgrades, composition rules
- NEEDS: fleet builder UI to use it


═══════════════════════════════════════════════════════════════════
## NOT YET BUILT (priority order)
═══════════════════════════════════════════════════════════════════

### Priority 1: Map Editor (drag-and-drop terrain placement)
- [done] Random celestial phenomena generation from rulebook tables
- [done] Battlezone selection and auto-generation
- [done] Blank board option
- [done] Custom board dimensions
- [done] Setup dialog at launch
- [ ] Manual terrain placement: drag-and-drop terrain objects onto board
- [ ] Terrain palette sidebar (asteroid field, dust cloud, planet S/M/L, warp rift)
- [ ] Mouse wheel to rotate terrain objects
- [ ] Resize terrain by dragging handles
- [ ] Delete terrain by right-click
- [ ] Save maps separately from games (already have save_map/load_map in map_maker.py)
- [ ] Load saved maps from setup dialog

### Priority 2: Drag-and-Drop Ship Movement
- [ ] Click ship, drag to move along heading
- [ ] Ship snaps to min-move distance (half speed) when dragging
- [ ] Optional snap to min-move-before-turn distance
- [ ] Mouse wheel to execute turns during drag (clockwise/anticlockwise)
- [ ] Visual: show movement path trail during drag
- [ ] Visual: show remaining movement budget during drag
- [ ] Validate movement on release (speed limits, turn count, min distances)
- [ ] Confirm/cancel dialog on release
- [ ] Works alongside existing exact-instruction mode (player chooses which)

### Priority 3: Deployment Zones
- [ ] Players take turns placing ships on their side
- [ ] Escorts placed as squadrons
- [ ] Ships start off-board in staging area
- [ ] Drag-and-drop ship placement onto deployment zone
- [ ] Mouse wheel to set initial heading
- [ ] Board state merging for async deployment
- [ ] Strategic placement (least important ships first)

### Priority 4: Fleet Builder
- [ ] Use ship_database.json to build lists
- [ ] Points calculator
- [ ] Composition rule validation (BB per cruisers, BC per cruisers, etc.)
- [ ] Commander selection and re-roll purchase
- [ ] Upgrade selection (targeting matrix, deflectors, etc.)
- [ ] Save/load fleet lists

### Priority 5: Squadron Coherency
- 15cm coherency check between squadron members
- Chain display on board (connected/broken indicators)
- Largest group keeps benefits when coherency breaks
- Group move order for escort squadrons
- Squadron combined movement (All Ahead Full rolls once for squadron)

### Priority 5: Match Replay
- Step through snapshots turn-by-turn
- Forward/back controls
- Show action log per step
- Board state visualization at each point

### Priority 6: AI Commander
- Simple decision making per phase
- Auto-play mode for spectator (AI vs AI)
- Global auto-RNG setting
- Evaluates weapon assignments, movement, ordnance

### Other Backlog
- Scatter dice manual input (draw arrow direction on compass)
- Torpedo heading control within forward arc at launch
- Attack craft wave composition choice (mix of fighters/bombers/mantas)
- Shooting at ordnance markers (torps/craft as valid targets)
- Boarding actions (advanced rules toggle)
- Ramming (advanced rules toggle)
- Teleport attacks (advanced rules toggle)
- Additional factions beyond Imperial/Tau
- Play-by-mail brace handling (save between attacker and defender decisions)


═══════════════════════════════════════════════════════════════════
## FILE INVENTORY (16 source files, ~6000 lines)
═══════════════════════════════════════════════════════════════════

src/
  models.py            - Ship, Ordnance, BlastMarker, Phenomenon data classes
  tables.py            - Gunnery, crit, catastrophic lookup tables
  game_state.py        - Save/load, ship CRUD, turn logging
  board_view.py        - Tkinter canvas with all visual rendering + tools
  dice.py              - Dice roller (auto/manual/mixed modes)
  movement.py          - Movement validation, execution, command checks
  combat.py            - Shooting resolution, damage, blast markers, LoS integration
  ordnance.py          - Torpedo/craft launch, movement, attacks, intercepts
  end_phase.py         - Fires, repairs, blast marker removal
  turn_controller.py   - Phase sequencing, snapshots, re-rolls, match export
  game_panel.py        - GUI controls (movement, shooting, ordnance, disengage dialogs)
  los.py               - Line of sight through terrain and blast markers
  disengage.py         - Voluntary/involuntary disengagement with Ld modifiers
  victory_points.py    - End-of-game scoring with full breakdown
  main.py              - Entry point, demo fleet definitions
  __init__.py          - Package marker

data/
  ship_database.json   - Full stats for Imperial Navy + Tau (19 ship classes)
  gunnery_table.csv    - FP 1-20 lookup table
  critical_hits_table.csv
  catastrophic_damage_table.csv
  special_orders_reference.csv
  rules_cheatsheet.txt

docs/
  README.md
  MOVEMENT_DESIGN.md
  PROJECT_NOTEBOOK.md
  PROJECT_STATUS.md    (this file)
  BUGFIXES.md
