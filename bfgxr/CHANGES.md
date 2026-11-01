# Changes since the first export

Five updates, oldest first. Section numbers quoted in the first update are the numbers at
that time; the third and fifth updates renumbered the core rules (see their tables).

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

# Fourth update: shields and blast markers

Core rules lacked the XR shield and blast-marker rules (Rulebook pp.21-24). No renumbering.

- **8. Shields & Blast Markers** (renamed from *Moving Through Blast Markers*; the old text is
  now its *Moving Through Blast Markers* subsection). New subsections:
  - *Shields*: one hit blocked per shield point, one blast marker placed per hit blocked;
    shield strength -1 per blast marker touching the base; restored on leaving contact; what
    bypasses shields (boarding, ramming, torpedoes, attack craft).
  - *Placing Blast Markers*: when markers are placed; fanning shield-impact markers; markers
    touching other ships in base contact.
  - *Shooting Through Blast Markers*: right column shift; lances and nova cannon unaffected.
  - *Optional: Modern Blast Markers*: XR's optional rules (intervening blasts, overlapping
    bases), which Battlefleet Gothic Remastered uses as standard, followed by Remastered's
    differences: whole-base contact, a column shift when the firing ship is in contact with
    blast markers, and a limit on blast markers spilling onto other ships.
  - Clarifications from Remastered pp.68-69 that agree with XR are marked "Clarification
    (Remastered ...)". Everything Remastered-only is labelled as such; the default game is XR.
- **31. Catastrophic Damage**: added *Exploding vessels* and *Moving drifting and blazing hulks*
  (Rulebook p.24), and a source line.

Faction, campaign and appendix files changed only in page references to the appendices (+2
pages). Ship data is unchanged.

# Fifth update: rulebook coverage audit, gaps filled

Every rule in the XR Rulebook was checked against the booklet; missing rules were added. Core
rules now have **41 sections** (previously 38) and are renumbered.

## New core sections
- **1. Basics** (Rulebook pp.3-6): measuring stem to stem, pre-measuring, base contact, no
  collisions, dice conventions, D3, re-rolls, unit types (defences with 1-2 hits follow escort
  rules, 3+ capital), comparing ship size, and a key to the roster columns.
- **2. The Turn** (pp.10-11, 34-35): game turn vs player turn, first turn, ending the battle,
  acting out of turn, and the turn sequence (movement, shooting, ordnance, end phase).
- **4. Assembling the Fleet** (pp.57-60): points, fleet lists, writing and revealing lists,
  ship class variants, playing without lists, base sizes (60mm if 3+ shields or more than 10
  hits; Tractor Fields), allies of convenience with the faction / sub-faction table, reserves
  (1 per 3 of a type; no reserves of reserves), alternative reserves with the natural-enemies
  table, fleet detachments.

## Additions and corrections in existing sections
- **5. Fleet Commanders:** re-rolls are once per game, one per test, for a failed command check
  or leadership test; **lost on a Bridge Smashed critical or when the ship is destroyed** (the
  booklet previously gave only the destroyed case); commander/ship rules combine; secondary commanders; one commander per
  ship or squadron; 750-point fleets need a capital ship if the commander can't ride an escort.
- **6/7. Command Checks and Special Orders:** full rules for All Ahead Full (incl. mixed-dice
  squadrons), Come to New Heading, Burn Retros, Lock On and Reload Ordnance (previously only
  flavour text plus the Appendix 6 summary); Brace for Impact declaration timing; *Other
  leadership tests* (several per turn, never the same test twice, no Under Fire / Enemy Contacts).
- **8. Squadrons:** mixed armour when shooting at squadrons; new *Shooting by Squadrons*
  subsection (combining and halving firepower, different aspects/ranges, squadron vs squadron).
- **13. Direct Fire:** firing order; Gunnery Table notes (defences and ordnance ignore
  orientation).
- **25. Waves of Attack Craft:** forming and splitting, open information, wave movement,
  shooting at waves, waves against ordnance and against ships.
- **33. Damage & Critical Hits:** repeated and impossible critical hits.
- **34. Catastrophic Damage:** hulks in gravity wells and hulks in combat.
- **36. Damage Control:** end phase order.
- **37. Disengaging:** squadrons disengaging.
- **39. Terrain:** setting up the battlefield, battlezone selection, setting the table, the six
  battlezone phenomena tables, and warp rifts. (The rulebook's Inner Biosphere table gives no
  result for a roll of 4 on its first line; the booklet says so.)
- **Support Assets** (faction file 06): the general Fleet Support rules now replace the old
  pointer to the rulebook: who may use the list, limits, ordnance (generic craft only), Ld 7,
  special orders (+3D6cm AAF), squadrons, deployment, damage, including planetary defences
  (planet-type table) and convoy ships / transport capacity.
- **Orks, Fighta-Bommerz:** clarified that the minimum of 1 attack applies to the per-turret
  reduction of a surviving squadron's attacks; squadrons shot down by turrets make no attacks.
- **Appendix 3:** Space Station Critical Hits table. **Appendix 6:** now points to section 7
  instead of rulebook pages.

## Core section numbers now

| Old (4th update) | New |
|---|---|
| - | 1 Basics, 2 The Turn (new) |
| 1 Leadership | 3 |
| - | 4 Assembling the Fleet (new) |
| 2 Fleet Commanders | 5 |
| 3-38 | 6-41 (+3), e.g. Special Orders 4 -> 7, Squadrons 5 -> 8, Movement 7 -> 10, Ordnance 12 -> 15, Hit-and-Run Raids 28 -> 31, Boarding Actions 29 -> 32, Victory Points 35 -> 38 |

Faction, campaign and appendix files otherwise changed only in page references. Ship data is
unchanged.

# Sixth update: deletions on review

- Section 1 (Basics): the *Dice* and *D3* paragraphs were removed (badly explained; "add the
  dice together" is wrong for attack rolls such as 4D6 vs Armour).
- Section 4 (Assembling the Fleet): *Ship Class Variants* is now the rulebook's verbatim text.
  Fleet-list limits (such as one nova-cannon ship per 500 points) still apply.
- Section 8 (Squadrons): two flavour paragraphs removed.
- Section 7 and Appendix 6, Brace for Impact: now use the Rulebook p.21 wording ("may be used any
  time the ship faces damage (but before the result is rolled)"), replacing the p.8-9 summary
  wording that limited it to the ordnance phase or the opponent's turn.
- Policy from here on: any wording not taken verbatim from a sourcebook is approved by Ciarán
  before it goes into the booklet.

# Seventh update: Chapter Tactics

- Space Marines faction rules: the nine Chapter Tactics now have their rules, verbatim from
  Ships of the Imperium p.133 (only "weapon batteries" renamed to "macrobatteries"; flavour text
  left out). Previously only the names were listed.
