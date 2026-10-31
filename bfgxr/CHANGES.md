# Changes since the first export

Three updates, oldest first. Section numbers quoted in the first update are the numbers at
that time; the third update renumbered the core rules again (see its table).

The booklet gained rules it was missing. Core rules sections were renumbered: there are now 34
(previously 30). Re-read `rules/00_core-rules.md`; any code or notes that refer to core rules by
section number need updating.

## New core sections
- **7. Movement** (Rulebook p.13): ships move one at a time, up to their Speed; must move at
  least half Speed unless on Burn Retros, else the maximum they can; fewer than 5cm counts as
  Defences on the Gunnery Table; one turn per move, up to the Turn value (45° or 90°), after
  moving straight ahead 15cm (battleship) / 10cm (cruiser) / any point (escort), counting only
  forward movement made in the current movement phase.
- **9. Ramming** (Rulebook p.37): All Ahead Full only; declare before the speed roll; course
  Leadership test on 3D6 / 2D6 / 1D6 by relative size; damage both ways by starting hits vs
  Armour, not stopped by shields.
- **24. Hit-and-Run Raids** (Rulebook pp.31, 33, 42): raids from boarding torps, assault boats
  and teleport attacks; roll a single D6 on the Critical Hits table; 4+ for 1 damage vs escorts;
  brace saves; full teleport attack rules, with faction exceptions listed.
- **25. Boarding Actions** (Rulebook pp.41-42): troop rating, troop-rating bonus table,
  modifiers, results table with critical hit requirements, drawn combats, multiple attackers,
  escorts, faction boarding rules listed.

## Additions to existing sections
- **5. Squadrons**: new subsections *Maneuvering Squadrons* and *Shooting at Squadrons*
  (Rulebook p.44): target aspect, hit allocation to the nearest eligible ship, exceptions, and
  rolling critical damage before a ship counts as destroyed.
- **31. Victory Points**: now includes *Enemies Scattered* (10% for disengaged non-crippled
  units) and *Holding the Field* (if your fleet holds the field: 50% of the value of every hulk on the table,
  friendly or enemy), as in the Scenarios chapter.
- **10. Direct Fire & Gunnery**: the minimum-move text moved to section 7; a short
  *Stationary Targets* pointer remains.

## Other files (first update)
Faction, campaign and appendix files changed only in page references to the appendices.

# Second update: ship rules wording and new data fields

## Wording standardised in the roster Notes (`rules/` and `data/`)
- **Ponderous** is always written `Ponderous (no Come to New Heading)`.
- **Ablative Prow Armour** always carries its explanation.
- **Improved Thrusters**: built in, `Improved Thrusters (+D6cm on All Ahead Full)` (Dauntless,
  Siluria, Vanguard, Slaverer, as the sources name it); as a refit, `Improved Thrusters (+D6cm on
  All Ahead Full) +5pts`. Ships whose sources give the same bonus without the name (Relictor,
  Slaughter, Fanatic, Schismatic, Heretic, Grey Knights Strike Cruiser) read
  `+D6cm on All Ahead Full`. Treat the two forms as the same effect.
- Spelling: `defence` everywhere (British, as in the 40K sources; was mixed with `defense`),
  including headings and table columns such as "High Orbit Defences", "21. Defence Turrets" and
  the Gunnery Table's "Defences" column. Code that matched `defense` must change.
- Stryxis Caravan Vessel: stray Markdown asterisks removed; the auto-pass on All Ahead Full is
  cited as `(Remastered p.197; not in the XR profile)`.

## New content
- **The Planet Killer** (Chaos Ship Special Rules): its scenario variants (Raiders, Surprise
  Attack, Convoy, Exterminatus; Imperium p.24) were missing and are now in the entry. The
  roster Notes no longer point to a nonexistent section.

## `data/ships.json`: new and fixed fields
- `roster_group` is now always the short label above the table. It was wrong for the six
  Venerable Battle Barges, the three Rogue Trader special ships, the Demiurg and the Nicassar,
  which held the intro paragraph instead.
- `roster_group_notes` (new): that intro paragraph, which carries rules for the whole group
  (e.g. all Venerable Battle Barges are Ponderous; Nicassar never board or teleport). Null for
  most groups.
- `faction_rules` (new): list of factions whose faction-wide rules the ship follows. Defaults to
  its own faction; overridden where the Notes say so (Grey Knights ships -> `Grey Knights`;
  Mechanicus escorts sharing Navy or Space Marine profiles -> `Adeptus Mechanicus`; commandeered
  Inquisition escorts -> `Inquisition & Grey Knights`; Space Marine Rapid Strike Vessels -> `[]`,
  as their Notes say no Space Marine rules apply). `faction_rules_basis` quotes the Notes phrase.
- `profile_from` (new): the profile a ship shares or reprints, e.g. `Imperial Navy Firestorm`.
- `ships.csv` gains the same columns.

# Third update: missing ordnance rules

The core rules lacked the general ordnance rules from Rulebook pp.26, 28-31 and 45. Core rules
now have **38 sections** (previously 34), so sections from Torpedoes onward are renumbered again.

## New core sections
- **12. Ordnance: Launching, Moving & Attacking** (Rulebook pp.26, 45): launching at the end of
  the shooting phase and reloading; ships with both attack craft and torpedoes or mines; ordnance
  staying loaded; the fleet attack craft limit (markers in play <= launch bays remaining);
  recalling attack craft; combining ordnance in squadrons; moving ordnance (phasing player moves
  first); ordnance attacks (ignore shields unless stated; contact during a ship's own move
  counts); **ordnance must attack the first valid target it contacts**, and the attacker picks
  between visually overlapping ships.
- **15. Attack Craft** (p.28): one squadron per launch bay per turn; owner picks craft types at
  launch; free movement; may pick out a small ship hiding under a large ship's base (the only
  exception to first contact).
- **18. Torpedo Bombers** (p.31): count as bombers vs ordnance; replaced by a strength-2 salvo at
  the start of a later ordnance phase; salvo removed at the end of that phase.
- **19. Assault Boats** (p.31): one hit-and-run raid per squadron vs ships; avoid ordnance other
  than fighters.

## Additions to existing sections
- **13. Torpedoes**: new subsections *Splitting Torpedo Salvos*, *Firing Through Allies*,
  *Turning Torpedoes* and *Torpedo Types* (standard, boarding, short burn, barrage bombs, guided,
  seeking, melta, vortex; pp.29-30). The faction refitted-torpedo tables name these types.
- **27. Shooting at Ordnance**: target aspects are ignored, but column shifts for range, blast
  markers and special rules apply.

## Core section numbers now

| Old (2nd update) | New | Section |
|---|---|---|
| 1-11 | 1-11 | unchanged |
| - | 12 | Ordnance: Launching, Moving & Attacking (new) |
| 12, 13 | 13, 14 | Torpedoes, Mines |
| - | 15 | Attack Craft (new) |
| 14, 15 | 16, 17 | Fighters, Bombers |
| - | 18, 19 | Torpedo Bombers, Assault Boats (new) |
| 16-34 | 20-38 | Resilient Attack Craft ... Orbit & Atmosphere (+4), e.g. Hit-and-Run Raids 24 -> 28, Boarding Actions 25 -> 29, Victory Points 31 -> 35 |

## Other files
Faction, campaign and appendix files changed only in page references to the appendices (+2
pages). Ship data (`data/`) is unchanged.
