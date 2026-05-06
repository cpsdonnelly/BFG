# BFG:XR SIMULATOR - PROJECT PLAN

## GOAL
A Python CLI tool for playing Battlefleet Gothic: XR turn-by-turn, supporting:
1. Two-player async play (save/load board state at any point)
2. Single-player vs-self mode (continuous play without pausing)
3. Manual dice entry OR computer RNG (per-roll toggle, or global auto-RNG setting)
4. AI vs AI spectator mode (global auto-RNG + AI decision making)

## ARCHITECTURE

### Directory Structure
```
bfg_project/
├── data/
│   ├── gunnery_table.csv
│   ├── critical_hits_table.csv
│   ├── catastrophic_damage_table.csv
│   ├── special_orders_reference.csv
│   └── rules_cheatsheet.txt
├── saves/
│   └── <game_name>/
│       ├── game_state.json          # Master state file
│       ├── ships.json               # All ship data
│       ├── ordnance.json            # All ordnance markers
│       ├── phenomena.json           # Celestial phenomena positions
│       ├── blast_markers.json       # All blast marker positions
│       └── turn_log.txt             # Human-readable log of actions
├── src/
│   ├── __init__.py
│   ├── main.py                      # Entry point, game loop
│   ├── game_state.py                # GameState class, save/load
│   ├── ship.py                      # Ship class with all stats
│   ├── ordnance.py                  # Torpedo, attack craft, mine classes
│   ├── board.py                     # Board/map, positions, LoS checks
│   ├── dice.py                      # Dice roller (manual input or RNG)
│   ├── combat.py                    # Shooting resolution, damage
│   ├── movement.py                  # Movement, turning, special orders
│   ├── ordnance_phase.py            # Ordnance movement and attacks
│   ├── end_phase.py                 # Repairs, boarding, teleport, blast removal
│   ├── tables.py                    # Lookup functions for gunnery/crit/catastrophic
│   ├── phenomena.py                 # Celestial phenomena effects
│   ├── los.py                       # Line of sight checking
│   ├── display.py                   # Board state display/printing
│   └── ai.py                        # AI decision making for auto-play mode
└── README.md
```

### Save State Design (JSON files in a directory per game)

**game_state.json:**
- game_name, turn_number, current_phase, active_player
- player1_faction, player2_faction
- points_limit, advanced_rules_enabled
- table_dimensions (width_cm, height_cm)
- sunward_edge
- dice_mode ("manual", "auto", "mixed")
- phase_state (tracks where within a phase we are)

**ships.json:** Array of ship objects:
- id, name, faction, player, ship_class, ship_type (battleship/cruiser/escort)
- base_size (small=32mm, large=60mm)
- position (x, y), heading_degrees
- stats: speed, turns_allowed, turn_angle, shields_max, armor_prow, armor_side, turrets, hits_max
- current: hits_remaining, shields_current, special_order, moved_this_turn
- weapons: array of {name, type, range, strength/firepower, arc, special_rules}
- critical_damage: array of active crits
- flags: is_crippled, is_braced, has_fired, has_launched_ordnance, ordnance_loaded_torps, ordnance_loaded_craft
- upgrades: array of upgrade names
- leadership, leadership_base
- towed_escorts: array of ship IDs (for gravitic hooks)
- squadron_id (if part of a squadron)

**ordnance.json:** Array of ordnance objects:
- id, type (torpedo/fighter/bomber/assault_boat/manta/barracuda/mine/torpedo_bomber)
- owner_player, launched_by_ship_id
- position (x, y), heading_degrees
- strength (for torpedoes), speed
- special: guided, resilient_save, turn_capability
- launched_turn (for Tau missile degradation)
- wave_id (if part of a wave)
- on_cap_for_ship_id (if on combat air patrol)

**blast_markers.json:** Array of {id, x, y}

**phenomena.json:** Array of:
- {type, x, y, width, height, special_rules}
- Types: asteroid_field, gas_dust_cloud, planet, moon, warp_rift, ring
- Planet-specific: size (small/medium/large), gravity_well_radius

## IMPLEMENTATION PHASES

### Phase 1: Core Data Model (FIRST)
- Ship class with full stat tracking
- Board representation (2D coordinate system, cm units)
- Save/load to JSON directory
- Dice module (manual input with auto-resolve button)
- Gunnery/crit/catastrophic table lookups

### Phase 2: Movement Phase
- Ship movement with facing/heading
- Turn restrictions (minimum distance, angle limits)
- Special order command checks
- Blast marker speed reduction
- Ponderous restriction

### Phase 3: Shooting Phase
- Weapons battery resolution (gunnery table lookup, column shifts)
- Lance resolution
- Nova cannon (template placement, scatter, damage)
- Target priority checks
- Damage application (shields via blast markers, HP reduction, crit checks)
- Brace for Impact declaration and resolution

### Phase 4: Ordnance Phase
- Torpedo movement and attacks
- Attack craft movement and interactions
- Fighter vs fighter/ordnance
- Bomber attack runs (turrets, D6 attacks)
- Wave formation and resolution
- Resilient saves
- Tau missile guidance and degradation
- CAP mechanics

### Phase 5: End Phase
- Damage control rolls
- Blast marker removal
- Boarding actions (Advanced, can be disabled)
- Teleport attacks (Advanced, can be disabled)

### Phase 6: Celestial Phenomena
- Line of sight blocking (asteroids, planets, warp rifts)
- Gas/dust cloud effects
- Asteroid field navigation tests
- Planet gravity wells and free turns
- Warp rift entry
- Solar flares and radiation bursts

### Phase 7: Display and UI
- ASCII board display (grid with ship positions and headings)
- Ship status summaries
- Turn log output

### Phase 8: AI Mode
- Simple AI for each phase (move toward enemy, Lock On when in range, etc.)
- AI fleet command decisions
- Auto-play loop for spectator mode

## QUESTIONS FOR USER BEFORE STARTING

1. Board scale: Should I use exact cm or would you prefer a scaled grid? Exact cm with floating point positions is more accurate but ASCII display gets messy. A grid (e.g. 1 cell = 5cm) simplifies display but loses precision on scatter/ranges.

2. Template handling: Nova cannon and base contact checks need geometric calculations. Should I implement proper circle-circle/circle-rectangle intersection, or simplify to center-point distances with base radius added?

3. Fire arc checking: This requires proper angular math relative to ship heading. I'll implement this with vector math. Any preference on how strict to be? (The tabletop uses a physical bearing compass overlay.)

4. How detailed should the ASCII display be? Simple coordinates list? Or actual grid map with symbols?

5. Do you want fleet list validation (checking points costs, composition rules like "one battlecruiser per two cruisers") built in, or should ships just be manually entered?

6. For the async two-player mode, is save-to-directory-then-share sufficient, or do you want some kind of file compression/single-file export?

7. Any faction-specific rules beyond Imperial Navy and Tau Kor'or'vesh that you want supported initially?

8. The Custodian's "tracking systems" giving turrets 20cm range - is this an actual rule or something I need to verify? Standard turret range isn't clearly defined in the core rules I extracted (turrets just fire at ordnance attacking the ship).

## IMMEDIATE NEXT STEPS
1. ✅ Created gunnery table CSV
2. ✅ Created critical hits table CSV
3. ✅ Created catastrophic damage table CSV
4. ✅ Created rules cheat sheet
5. ✅ Created special orders reference
6. ✅ Created this project plan
7. NEXT: Get answers to questions above
8. THEN: Start Phase 1 implementation
