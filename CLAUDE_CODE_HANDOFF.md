# BFG:XR SIMULATOR - HANDOFF DOCUMENT FOR CLAUDE CODE

## Project Overview
Python/Tkinter turn-by-turn tactical simulator for Battlefleet Gothic: Expanded Revised (BFG:XR). ~8,764 lines across 19 modules. Designed for hotseat play, async play-by-mail, match replay, and eventually AI opponents.

The primary ruleset is BFG:XR. Some optional rules offer a toggle between XR and BFG Remastered variants (e.g., turret suppression).

## Architecture

```
bfg_project/
├── run.py                          # Launch script
├── TASK_LIST.md                    # LOCKED priority list (read this first)
├── src/
│   ├── main.py                     # Entry point, setup dialog, demo fleet defs
│   ├── models.py                   # Ship, OrdnanceMarker, BlastMarker, Phenomenon dataclasses
│   ├── tables.py                   # Gunnery table (6 cols), crit table, catastrophic table
│   ├── game_state.py               # Save/load JSON, ship CRUD, individual rule toggles
│   ├── board_view.py               # Tkinter canvas: ships, terrain, ordnance, blast markers
│   ├── game_panel.py               # GUI dialogs: movement, shooting, ordnance, disengage, repair
│   ├── turn_controller.py          # Phase sequencing, snapshots, re-rolls, match export
│   ├── dice.py                     # Auto/manual/mixed dice
│   ├── movement.py                 # Signed net rotation validation, terrain contact checks
│   ├── combat.py                   # Batteries, lances, nova cannon, damage with crit cascade
│   ├── ordnance.py                 # Torpedo/craft launch, movement, attacks, fighter intercept
│   ├── end_phase.py                # Fires, repairs (player choice), blast removal, brace expiry, hulk drift
│   ├── los.py                      # Line of sight through planets/asteroids/dust/warp rifts
│   ├── disengage.py                # Voluntary/involuntary with Ld modifiers
│   ├── victory_points.py           # Destroyed/crippled/scattered/holding field scoring
│   ├── terrain_effects.py          # Asteroid nav, warp rift nav, dust contact, solar flares, radiation
│   ├── map_maker.py                # Random gen from battlezone tables, moon/ring gen, save/load maps
│   └── map_editor.py               # Drag-drop terrain, mousewheel rotate, right-click resize
├── data/
│   ├── ship_database.json          # 14 Imperial + 5 Tau ship classes with full stats
│   └── gunnery_table.csv, critical_hits_table.csv, catastrophic_damage_table.csv
```

## Reference PDFs (user has these)
- `BFGXR_-_RULEBOOK.pdf` (152 pages) - PRIMARY ruleset
- `BFGXR_-_SHIPS_OF_THE_IMPERIUM.pdf` - Imperial ship stats
- `BFGXR_-_SHIPS_OF_THE_XENOS.pdf` - Xenos ship stats (including Tau)
- `BFG_blastmarkers-torpedo-compass-nova.pdf` - Templates and markers
- `BFG-Remastered-Official-Fleets_WIP.pdf` - Alternative ruleset fleets (for cross-reference and optional variant rules)

## Demo Fleets (800pts each)
**Imperial Navy:** Mars BC (350pts, targeting matrix, Vice Admiral Ld8, 1 reroll) + 2x Lunar CA (180pts each) + 3x Cobra DD (30pts each)
**Tau Kor'or'vesh:** Custodian BB (425pts, Kor'O Ld9, 2 rerolls, tracking_systems_20, ponderous) + 2x Emissary LC (120pts each, Bor'kan + deflector) + 3x Warden (30pts, towed) + 1x Castellan (45pts)

---

## LOCKED TASK PRIORITY LIST (from TASK_LIST.md)
See TASK_LIST.md for current status markers. Items 1-4, 7-10 are DONE. Items 5, 9 are DONE. Item 6 is IN PROGRESS. Item 11 is PENDING.

---

## KEY RULES DECISIONS AND IMPLEMENTATIONS

### Gunnery Table (6 columns, 0-5)
```
Col 0: Initial Firepower (= FP value, left-shift cap)
Col 1: Defenses (ships that moved <5cm)
Col 2: Closing Capital Ships
Col 3: Closing Escorts / Moving Away Capital Ships (SHARED)
Col 4: Moving Away Escorts / Abeam Capital Ships (SHARED)
Col 5: Abeam Escorts / Ordnance Waves (SHARED)
```
- Left shift past col 0 = FP value (maximum dice)
- Right shift past col 5 = 0 (impossible to hit)
- Column shifts: range (<15cm = -1 left, >30cm = +1 right), blast markers in LoS (+1 right), dust clouds (+1 right), targeting matrix (-1 left)
- Lances do NOT use the gunnery table (roll strength dice, hit on 4+)

### Movement System
- Uses **signed net angular displacement**. 45CW + 45CCW + 5CCW = net 5° = one turn.
- Overshoot and correct is allowed (60CW + 15CCW = net 45°, valid for 45° ship).
- Turn only validated when finalized (forward movement or end of commands).
- Forward between turns = separate turn actions (needs CtNH for >1).
- Burn Retros: no minimum distance before turning.

### Critical Hits
- **Non-cumulative effects**: Thrusters Damaged = -10cm total regardless of count. But ALL instances must be repaired.
- **Cascade**: If rolled crit can't apply (no weapons in slot), cascade to next highest. Unrepairable duplicates cascade.
- **Ablative Prow Armor**: Absorbs prow armament crits entirely (no cascade). Lost if ship has prow torpedoes.
- **Player chooses repairs**: Interactive dialog lets player pick which crits to repair with successful rolls.
- Fire IS cumulative: 2 Fire crits = 2 damage per end phase.
- Bridge Smashed: -3 Ld, permanent.
- Shields Collapse: shields = 0, permanent.

### Crippled Ships (IMPORTANT - partially implemented)
When a capital ship (or defense with 3+ starting hits) loses half its HP:
- Halve shields, turrets, ordnance strength, gunnery FP, lance strength (ALL round up)
- Reduce speed by 5cm
- Cannot fire nova cannon
- **Brace + Crippled is MULTIPLICATIVE**: halve again on top of cripple halving. So a crippled braced ship has ~25% effective weapons. Round up at each step.
- Crippled ships cannot make teleport attacks
- Crippled + braced ships cannot fire inside asteroid fields
- Crippled ships that disengage give enemy 25% VP (vs 10% for healthy disengage)

### Rounding
- **Default is round UP** for halving (shields, turrets, FP, ordnance, etc.)
- Code uses `(value + 1) // 2` for round-up halving
- A few specific cases round down (check rules text for each)

### Brace For Impact (complex, partially implemented)
- Requires Leadership test to declare
- Per weapon, per attacker: if brace fails, can't retry for THAT attacker's remaining weapons
- CAN retry against a DIFFERENT attacker
- Previous order effects persist: AAF speed stays, Reload keeps ordnance reloaded
- Ship model has `previous_order` field to track this
- Brace persists through end of ship's NEXT turn (tracked via `brace_set_on_turn`)
- Brace halves FP, ordnance, lance strength. Blocks nova cannon. Turrets and shields unaffected.
- Brace DOES protect against hit-and-run/teleport attacks (unique crit table save case)
- Brace does NOT save against crits caused by unsaved weapon hits
- Ordnance launch strength is halved when braced (cumulative with cripple) - NOT YET IMPLEMENTED (item 11)

### Special Orders
```
Order          | Speed        | Turns | Shooting    | Ordnance | Nova Cannon
---------------|--------------|-------|-------------|----------|------------
None           | Half-Full    | 1     | Full        | Full     | Yes
Lock On        | Half-Full    | 0     | Full+reroll | Full     | Yes (no benefit)
Reload         | Half-Full    | 1     | Full        | Full+reload | Yes
AAF            | Full+4D6     | 0     | Half        | Full     | No
CtNH           | Half-Full    | 2     | Half        | Full     | No
Burn Retros    | 0-Half       | 1*    | Half        | Full     | No
Brace          | (persists)   | 1     | Half        | Half     | No
```
*Burn Retros: no minimum distance before turning

### Shooting at Ordnance
- Both batteries AND lances can fire at ordnance markers
- ALL weapons hit on 6+ (not normal to-hit)
- ONE HIT kills the ENTIRE wave/salvo regardless of strength
- Batteries use Ordnance column (col 5) on gunnery table
- Lances roll strength dice at 6+
- Ordnance-only target priority (other ordnance = nearest enemy, ships don't count)
- Column shifts for range and blast markers still apply

### Fighter Interactions
- **Fighter vs torpedo/missile**: One fighter marker destroys entire salvo of any strength. Both removed. (A wave of 2 fighters vs Str 6 torps = 1 fighter lost + entire salvo lost, 1 fighter remains)
- **Fighter vs attack craft**: Mutual destruction. Resilient saves apply.
- **Fighters MUST intercept** enemy ordnance they contact (compulsory).
- Torpedo vs torpedo: both destroyed on contact.

### Defense Turrets
- vs Torpedoes: D6 per turret, 4+ reduces salvo strength by 1
- vs Attack Craft: D6 per turret, 4+ removes 1 attacking marker
- **Exclusive per phase**: If turrets fire at craft, cannot fire at torps that phase (and vice versa). Tracked via `turrets_used_vs` field.
- Massed turrets: base-contact allies add +1 each, max +3, crippled ships can't contribute (NOT YET IMPLEMENTED)

### Torpedo Rules
- Attack ALL ships they contact including friendly (FRIENDLY FIRE)
- Exception: can fire "through" an allied ship in base contact at launch
- Reduce strength by hits inflicted, continue if strength remains
- Split salvos: Str 7+ only, into exactly two salvos
- Tau guided missiles: player-controlled movement (20-40cm, optional 45° turn at start, degradation D6 per strength each turn on 1s)

### Terrain Effects
- **Asteroid fields**: Block LoS, destroy torpedoes, craft destroyed on D6=6, Ld test to navigate (3D6 if AAF, escorts re-roll), D6 damage on fail (shields absorb, no blast markers), max 10cm fire range inside, half FP, no fire if crippled/braced
- **Gas/dust clouds**: Act as single blast marker (-5cm speed, gunnery shift, shieldless D6=6 for 1 damage)
- **Warp rifts**: Block LoS, destroy torpedoes/craft, 3D6 Ld to navigate, pass = reposition 2D6x10cm, fail = lost in warp
- **Tabletop effects** (toggleable): Solar flares (once per game, blast on all ships), radiation bursts (-D6 Ld all ships), fighting sunward (double range shifts only, not other shifts)

### Teleport Attacks (NOT YET IMPLEMENTED - item 18)
Preconditions: within 10cm, target shields down, attacker not crippled, only on Lock On/Reload/None, escorts with <3 starting hits cannot, cannot target ship with more remaining HP than attacker, Tau CANNOT teleport. Target may attempt Brace. Resolved as hit-and-run (roll on crit table).

### Game Settings (independently togglable booleans in GameState)
```python
rule_fighting_sunward, rule_solar_flares, rule_radiation_bursts,
rule_boarding, rule_ramming, rule_teleport, rule_hit_and_run
```

### Ship Model Key Fields
```python
# Added beyond basic stats:
points_value, is_disengaged, status, disengage_failed_this_turn,
brace_set_on_turn, previous_order,
weapons_fired_indices, weapons_remaining (dict for split fire),
turrets_used_vs, brace_failed_vs, rotation (for Phenomenon)
```

---

## KNOWN BUGS AND INCOMPLETE IMPLEMENTATIONS

1. **Item 11 (PENDING)**: Brace does not halve ordnance launch strength yet. Should be cumulative with cripple.
2. **Brace per-weapon granularity**: Current implementation applies brace per-attacker (all weapons pooled). Rules say brace decision is per-weapon from each attacker.
3. **Crippled + Brace multiplicative halving**: Needs verification that the code applies both halvings correctly at each point where weapons/ordnance are calculated.
4. **Victory points for crippled disengage**: Needs to give 25% VP not 10%.
5. **Tau missile auto-move**: If player doesn't manually move missiles during ordnance phase, they auto-move at 20cm minimum. The `moved_this_phase` flag needs to be cleared at start of each ordnance phase.

---

## ROUNDING CONVENTION
The rules generally say "rounding up" when halving. The code should use:
```python
halved = (value + 1) // 2  # round up
```
This applies to: shields, turrets, firepower, lance strength, ordnance strength when crippled or braced. Check each halving operation in the codebase to ensure consistency.

---

## FIGHTING SUNWARD (NOT YET IMPLEMENTED - item 26)
Only the RANGE-BASED column shifts are doubled when firing into the sunward abeam arc:
- Target <15cm sunward: 2 left shifts (buff at close range)
- Target 15-30cm sunward: 0 (doubling zero)
- Target >30cm sunward: 2 right shifts (worse at long range)
Other shifts (blast markers, dust, targeting matrix) are NOT doubled.

---

## TURRET SUPPRESSION (NOT YET IMPLEMENTED - item 12)
Two modes toggled by game setting:

**XR mode (default)**: Each surviving fighter in a mixed wave lets one bomber make exactly 3 attacks instead of D6-turrets. Bombers that can re-roll attacks get 4 instead of 3. Multi-role craft (Mantas) choose fighter or bomber role before turret fire.

**Remastered mode (option)**: Each fighter in the wave adds +1 attack to total wave attack run, regardless of whether shot down by turrets. Cap = surviving bomber count. At least one bomber must survive turret fire. Fighters intercepted by defending fighters (including CAP) don't count.

---

## ADDITIONAL FACTIONS (item 25, collaborative)
Ship stats extraction from PDFs is unreliable. This task requires user verification for:
- Stat values (hits, speed, turns, shields, armor, weapons)
- Special rules per faction
- Faction-specific mechanics (Ork gunz randomness, Eldar holofields, Necron special rules, etc.)

The user has these PDFs:
- BFGXR Ships of the Imperium
- BFGXR Ships of the Xenos
- BFG Remastered Official Fleets WIP

---

## USEFUL CONTEXT FOR CONTINUING DEVELOPMENT

### The user
- Knows BFG:XR rules thoroughly and will catch misreadings
- Prefers direct communication, wants to be told when something is wrong
- Values correct rules implementation over features
- Wants scroll wheel turning for both ships and missiles as a QoL feature
- Wants drag-and-drop ship movement with snap-to-min-move option

### Common pitfalls from this project
1. Don't merge the shooting and ordnance phases - they are separate
2. Don't auto-aim Tau missiles - player controls them
3. Don't assume planet limit in map editor (only in random generation)
4. Net angular displacement for turns, not incremental tracking
5. Gunnery table has 6 columns (0-5), not 5
6. One hit kills entire ordnance wave, not per-strength
7. Crit effects don't stack, but all instances must be repaired
8. Brace is per-attacker per-weapon, not a global toggle
9. Torpedoes hit friendly ships (friendly fire)
10. Round UP when halving unless rules specifically say otherwise
