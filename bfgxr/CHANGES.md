# Changes since the first export

Updates are listed oldest first. Section numbers and booklet page numbers quoted in an update are
the ones at that time; later updates renumbered sections and moved pages, so check the current
`rules/` files for live numbers. Where a later update reverses an earlier one, the earlier entry
says so.

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
    differences (update 28 moved these into a separate "Remastered Blast Markers" section): whole-base contact, a column shift when the firing ship is in contact with
    blast markers, and a limit on blast markers spilling onto other ships.
  - Clarifications from Remastered pp.68-69 that agree with XR are marked "Clarification
    (Remastered ...)" (labels removed in update 11). Everything Remastered-only is labelled as such; the default game is XR.
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

# Eighth update: drifting hulks

- Appendix 5, Catastrophic Damage table, *Drifting hulk*: now the Rulebook p.23 wording. Hulks move
  4D6cm "in each of their subsequent movement phases" (the owning player's movement phases), not
  in every movement phase.
- Appendix 5, *Burning hulk*: rolls again "at the end of each of its movement phases" (its owner's
  movement phases, after it moves), not at the end of every movement phase.

# Ninth update: Inquisition and Chaos faction rules checked against the sourcebook

Inquisition (Ships of the Imperium pp.99-101, 108):
- Ordo upgrades now use the sourcebook wording. **Hellfire Sentry Guns moved from Ordo Hereticus
  to Ordo Xenos** (it was listed under the wrong Ordo). Added the Celestian restriction (no Space
  Marine honour guard or hit-and-run bonuses) and "instead of any other bonus" on every honour
  guard +2 result.
- Radical Hereticus: the Purgator's -2 Ld applies to every *capital ship* alongside it (it wrongly
  read "ships", which included escorts).
- Radical Xenos: reserves are any Demiurg capital ship, Corsair Eldar cruiser or Tau cruiser; the
  Xenos refit is bought by the ship carrying the Ordo Xenos Inquisitor; no duplicate refits.
- Fleet Detachment list: added Ordo Xenos options (hellfire sentry guns free, Deathwatch kill-team
  +15, Deathwatch Terminators +30), Purifiers +15, Celestians +5, inferno torpedoes +20; vortex
  torpedoes are an Inquisitor Lord option at +50 (they wrongly read "Malleus, +15"); free boarding
  torpedoes for Inquisition capital ships; gun-cutter swap limited to Navy / Mechanicus ships
  carrying an Inquisitor, halving their bays.
Chaos (Ships of the Imperium pp.20-24):
- Stormbirds: no other attack craft may be launched; +1 hit-and-run bonus.
- Daemonic Crew: no Warmaster or Lord "even if it is the largest ship in the fleet".
- Materialising in an asteroid field: a leadership test may avoid damage.
- Planet Killer: template placed touching the stem (was "prow"); exterminating a planet (low
  orbit, hit the planetary table edge, 60cm range on the low-orbit table); reloading only the
  torpedoes carries no malfunction risk; removed "must be charged before firing" (the gun starts
  loaded like any ordnance).
Spelling: "honor" is now "honour" throughout.

# Tenth update: Imperial Navy and Chaos fleet-list ordnance

- Imperial Navy fleet lists, *Ordnance*: now the sourcebook text (Imperium p.89) with the D3 table
  for the +50pt option (1 Seeking, 2 Melta, 3 Vortex; each usable once per game), which was
  missing. Upgrades apply to *capital ships* armed with torpedoes (it read "torpedo ships"); the
  power ram's effect (one automatic hit when ramming) is now stated.
- Chaos fleet lists, *Ordnance*: same correction (capital ships only); anointed munitions point to
  the Anointed Munitions table in the Chaos faction rules.

# Eleventh update: hedge and doc-talk fixes

- Shields (section 11): removed the "Clarification (Remastered p.69)" label; the sentence stays as
  a plain rule, alongside the matching sentence in Moving Through Blast Markers.
- Space Marines intro: Thunderhawks now point to the Thunderhawks faction rule (p.49), not the
  Chapter Tactics.
- "Already in the booklet", "in booklet" and "reprinted for convenience" replaced with booklet page
  references (Mechanicus Gifts p.44, Mechanicus rules p.43, Imperial Refits p.162, Space Marine
  rules / Tactical Flexibility / Thunderhawks p.49, Space Marine escorts p.52, Grey Knights rules
  and Gun-Cutters p.57).
- Inquisition intro: leftover build note on Gun-Cutters replaced with a pointer to the faction rule.
- Orks intro: "rolled as printed" replaced with the random firepower/strength timing rule
  (Ships of the Xenos p.52, verbatim).
- Appendices moved one page later; internal page references updated.
- Held for the author's decision: blast marker clarifications (Placing Blast Markers), the
  optional modern blast marker structure, the Inner Biosphere roll of 4, the Stryxis note, and
  the Appendix 2 appeals note.

# Twelfth update: Inner Biosphere table

- Inner Biosphere phenomena, roll of 1: now "Roll a D6: 1-3 radiation burst, 4-6 solar flare".
  XR printed "1-3 Solar Flare, 5-6 Radiation Burst"; the XR author confirmed this was a typo and
  the intended result is the one Remastered prints (p.107). The footnote about the missing 4 is
  removed.

# Thirteenth update: Inquisition fleet lists (Ships of the Imperium pp.108-109)

Both Inquisition fleet lists are now the sourcebook text (flavour removed, page refs pointed at
the booklet). Earlier copies of this package had an Ordo Malleus "vortex torpedoes +15": that was
wrong and is gone.

Vortex torpedoes (+50):
- Banisher fleet: only "if an Ordo Malleus Inquisitor Lord's ship is armed with torpedoes".
- Fleet Detachment: "an Inquisitor Lord's vessel may equip its torpedo tubes with vortex
  torpedoes for +50 points" (any Ordo).
Inferno torpedoes (+20): Fleet Detachment, Ordo Hereticus Upgrades, available only to a fleet
accompanied by an Ordo Hereticus Inquisitor; bought per Inquisition vessel ("Inquisition vessels
may ... equip their torpedo tubes with inferno torpedoes for +20 points"). A capital ship that
embarks an Inquisitor or Elite Captain may buy upgrades as if it were an Inquisition vessel; a
ship cannot take upgrades from more than one Ordo.

Banisher fleet, newly present: Master Daemonhunter must go on a battleship/battle barge if one is
present; Grand Master gets Paladins free; Ordo Malleus Inquisitor (Ld9, 30) as an Elite
Daemonhunter; Inquisitorial battleship needs an Inquisitor Lord (non-unique Imperial Navy
battleship at normal cost); the 3-cruiser caps; Interceptors (battle barge / strike cruiser
only) and Purifiers (ship with a Brother-Captain or Inquisitor Lord only); Inquisitorial escorts
(Firestorm 35, Sword 35, Cobra 30) and the mixed-squadron Ld rule; blessing of Chaos; sub-plots;
no detachments, reserves or allies.

Fleet Detachment, newly present: joins IN/AdMech/SM fleets, never allies of convenience; Inquisitor
re-roll costs; Elite Captains need a fleet led by an Inquisitor, +15 re-roll; Inquisitorial
cruisers 0-3 (one per three of the joined fleet's cruisers, count against battlecruiser limit);
each Ordo's upgrades require an Inquisitor of that Ordo. Removed the incorrect "as allies of
convenience" for the Ordo Malleus Grey Knights ships.

Layout: one page longer; appendices and their internal page refs moved one page later.

# Fourteenth update: open-question decisions

- Inner Biosphere: footnote marking the correction from the XR printing.
- Stryxis Caravan: "(Remastered p.197; missing from the XR profile, p.123, in error)".
- Terminus Est footnote now says where 430 and 420 come from; 420 is used.
- Mines: minefields paragraph rewritten plainly, pointing to Minefield (p.75) and Asteroid
  Fields (p.31).
- Appendix 2 refit rolling now uses the Campaigns D6 (1-2 Ship, 3-4 Engine, 5-6 Weapon); the D3
  method and the note comparing them are gone. One method everywhere.
- Section 5: "All commanders must be assigned to an appropriate ship during deployment (see the
  players' fleet lists for details)."
- Mechanicus: Leadership table caption uses the source sentence; appeal refits use the Imperial
  Refits table (not Gifts); multiple Gifts on the flagship only, per commander renown (p.154).
- Demiurg: commerce vessels lose 1 Ld per point of damage (minimum Ld5); Bridge Smashed causes
  one extra damage instead of -3 Ld. They never roll for Ld (Stronghold 10, Bastion 9, Citadel 9).

# Fifteenth update: Space Marine battle barges

- Crusade and Dominion fleet lists (Imperium pp.148-149): Battle barges, one per 1000pts (or
  portion thereof); the fleet must be worth 1000+pts to include the Chapter flagship.
  (0-1) Chapter Flagship: Venerable Battle Barge (varies), Ultima Battle Barge 450, Space Marine
  Battle Barge 425; (0-2) Command Ships: Space Marine Battle Barge 425. The Venerable Battle Barge
  was missing from both lists, and the Dominion list was missing the Chapter flagship entirely.

Rulings for the fleet builder (from the sourcebooks):
- Points-based limits use the fleet's actual total ("if your fleet is worth at least",
  "for every 750 points in your fleet"), not the game's points limit. "For every full 750" rounds
  down; "(or portion thereof)" rounds up.
- Chaos ratios count cruisers and heavy cruisers only, as each list says; light cruisers are a
  separate 0-6 section and do not count.
- Imperial Renegades (Chaos Renegades list only) "are treated as Chaos ships in all respects", so a
  renegade cruiser counts as a cruiser for the Chaos ratios. They do not count against reserves.
- Imperial Renegades "six escorts and/or one cruiser" per full 750pts: both are allowed.
- A Rogue Trader Fleet Detachment may join any fleet except Necrons or Tyranids, Orks included.
  A detachment is not a reserve, and Orks are not natural enemies of Rogue Traders.
- Any Space Marine fleet list may be a Rogue Trader Expedition's supporting fleet; if one is
  chosen, no Demiurg, Kroot or other xenos ships may be present.
- Nicassar: every Rig requires four Dhows to be bought with it. The Rig is a Defense/4 stationary
  defence (placeable anywhere in the deployment zone) with gravitic hooks of capacity 4 Dhows;
  Dhows are limited to one per gravitic hook configured to carry Dhows.

# Sixteenth update: venerable strike cruisers

- Crusade and Dominion fleet lists, Strike Cruisers (0-10): "If the fleet is worth at least 1000
  points, it may include up to one venerable strike cruiser for every three standard strike
  cruisers (including any strike cruiser variants), to a maximum of two." (Imperium pp.148-149.)
  The Crusade table had no condition; the Dominion table had a shortened one.

# Seventeenth update: Imperial Navy audit (Ships of the Imperium pp.63-94)

Data changes (ships.json notes):
- Lunar Cruiser: refit added, prow torpedoes -> prow nova cannon +20pts.
- Mercury Battlecruiser: always rolls 3D6 on the Catastrophic Damage table (results over 12 count as 12).
- Exorcist Grand Cruiser: may drop its macrobatteries to 30cm range for FP10, no cost.
- Grand cruiser refits (Exorcist, Vengeance, Avenger; Chaos Retaliator, Nephilim, Executor):
  "May buy one of" the listed upgrades, not all of them.

Fleet list changes (rules/01_imperial-navy.md):
- Bakka escorts are Havoc, Viper, Firestorm, Sword (no Cobra). Bakka battleships one per 750pts
  (or portion thereof). Starred Bakka classes have +1 Turret, cost included. Veteran Captains
  (+1 Ld, max 10) 30pts, +15 re-roll. Forgeworld of Bakka: Mechanicus cruisers may replace
  battlecruiser slots as normal fleet ships; IN capital ships may buy Fleet Defence Turrets. Bakka
  has no mine launcher upgrade.
- Admiral may be assigned to any ship; "Admiral" covers all three ranks.
- Strategic Commander re-roll only for their own ship or squadron.
- Armageddon: Admiral needs an IN capital ship and cannot board a Space Marine ship; Master of
  the Fleet needs and must ride a Battle Barge. Torpedo upgrades and power rams there are for IN
  capital ships only.
- Endurance/Defiant limit: 2 per 500pts (or portion thereof).
- Cadia veteran captains may (not must) be assigned after rolling Leadership.
- Obscura: unreliable ships disengage toward the nearest table edge.
- Ramilies: quadrant hit is traced from the firing ship's stem (was "prow"); as a planet its
  high-orbit range is 30cm from the stem of its base.

Booklet is one page longer; sections from Adeptus Mechanicus onward moved one page later.

# Eighteenth update: Space Marines audit (Ships of the Imperium pp.132-149)

- Dominion nova cannon limit: one per 1000pts (or portion thereof), not the usual one per 500.
- Dominion escorts: Sword rapid strike vessel (35) added; rapid strike vessels are not allies of
  convenience, and mixed squadrons use the Space Marine Ld table (-1Ld if all Space Marine
  members are lost).
- Dominion reserves rewritten from the source: IN reserves only by these ratios (battleship/grand
  cruiser per 3 strike cruisers vs battle barge limit; battlecruiser/cruiser/light cruiser per 2
  strike cruisers vs strike cruiser limit), even with a detachment; AdMech reserves normally,
  always allies of convenience.
- Dominion Space Marine Captains: the ship uses the Space Marine Ld table and is not an ally of
  convenience. Veteran honour guard +10 on any SM capital ship or Captain's ship.
- Crusade upgrades added: veteran honour guard +10 per SM capital ship; mine launchers on up to two
  cruisers.
- Master of the Fleet: must be on a battle barge (the Chapter flagship if present) only if the
  fleet has one; otherwise any capital ship (Dominion: any Space Marine capital ship).
- Tactical Flexibility covers specialist torpedoes, not secondary shields. Only Space Marine
  fleets may use Chapter tactics.
- Venerable strike cruiser: any grand cruiser, battlecruiser or heavy cruiser ("non-unique" removed).
- Strike cruiser torpedoes: boarding free, short-burn +5, barrage bombs +10.
- Fortress-Monastery: stem targeting; D6 blast markers removed per model; a quadrant at 0 hits takes
  no further damage and is an asteroid field; hit-and-run per quadrant; opposing player spreads
  basilica damage; auto-reload every two complete turns docked. Ramilies: same last two fixes.

# Nineteenth update: Adeptus Mechanicus audit (Ships of the Imperium pp.4-17)

- Quest for Knowledge: an Explorator fleet takes one random Quest for Knowledge sub-plot IN
  ADDITION to its normal sub-plots (the booklet wrongly said "instead of").
- Archmagos re-rolls: up to two, 25 / 50 points (no free re-roll).
- Omnissiah's Victory requires a fleet of 1000+ points and counts against battleships.
- Torpedo-armed ships carry ordinary torpedoes as well as any refitted torpedoes.
- All list escorts may squadron together in any mix.
- Vault of Technology: rolled at game start, Gift is free.
- The Prize: no renown either way if the target explodes or is detonated after becoming a hulk.
- Experimental Ship: changes are in addition to normal refits; re-roll inapplicable results.
- Sacred Technology: a crippled reserve ship that fails to disengage moves towards the nearest
  table edge.

# Twentieth update: Man O' War example builds

- Rogue Traders: new "Example Builds" subsection after Man O' War Configuration, with six worked
  examples (brig, two galleons, two grand galleons, ship of the line). These are NOT sourcebook
  ships; they illustrate the configuration rules. Do not add them to ships.json as real classes.
  Readings used: a ship with 10+ hits may take both +1 and +2 Shields; the 1-squadron and
  2-squadron launch bay options are separate weapons and may both be taken.
- Prow Weapon is optional: "A man o' war may choose one of the following options" (source wording).
- Booklet is two pages longer from Rogue Traders onward; page refs updated.

# Twenty-first update: Rogue Traders audit (Ships of the Imperium pp.113-129)

Data changes (ships.json):
- Three new rows: Pthuxutl War Cruiser, Fra'al Raider, Nekulli Whip (Notable Xenos profiles for
  xenos cutter squadrons; 35pts per ship plus 30pts per squadron).
- Xenos Cutter notes: allies of convenience with everyone; cannot squadron with other types.
- Repair Tender and Sloop notes extended.

Rules changes (rules/05_rogue-traders.md):
- Business as Usual: Punitive Strike, Colony Settlement, Reclamation Crusade, Expeditionary Group
  and Treasure Haul apply to sloops, caravels and carracks only. Reclamation Crusade sets their
  weapon range TO 30cm (was wrongly +30cm). Trooping the Colour, Colony Settlement, Expeditionary
  Group and Treasure Haul given in full.
- Convoy Fortune: only Rogue Trader convoy ships add Fortune.
- Fleet Detachment: attack rating unaffected; convoy ships cannot mix with generic fleet-support
  convoy ships in transport-capacity scenarios; Business as Usual applies otherwise.
- Expedition and Pirate lists: ordinary torpedoes, Business as Usual sub-plot rule; Pirate limits
  use "(or portion thereof)".
- New subsection: High-Risk Convoys (four alternative Convoy Run threat tables).
- Booklet is two to three pages longer from Rogue Traders onward; page refs updated.

# Twenty-second update: Support Assets, Orks, Tau & Allies audits

Support Assets: convoy ships from a regular fleet list follow the normal transport-capacity rules
in scenarios that set a requirement.

Orks: Ork Boss and Nob limits are per 500pts (or portion thereof), each assigned to any ship;
one Space Hulk per FULL 1500pts; clan affiliations are fixed at fleet selection; the Hammer's
Kustom Kannon must Reload Ordnance after firing in either mode.

Tau & Allies:
- NEW fleet list: Demiurg War Host (Xenos p.101). Re-rolls 25 / 75pts (not 50).
- NEW ship row: Courier Transport (Tau, Free, convoy ship, transport capacity 1; only in
  scenarios with a transport capacity requirement).
- Tau commander required when the fleet is worth MORE than 750pts; re-rolls 25/50.
- Demiurg, Nicassar and Kroot in a Tau fleet are allies of convenience.
- Messenger limit per 500pts (or portion thereof).
- Notes changed in ships.json: Explorer (Tiger Sharks +20 with Bor'kan), Merchant (TC 2 only in
  TC scenarios, max 50% of fleet TC), Nicassar Caravan, Nicassar Rig, Kroot Warsphere.
- Booklet two pages longer from Scenarios onward; page refs updated.

# Twenty-third update: Demiurg special rules (Xenos p.91)

- Mercenaries: unless the fleet is entirely Demiurg, crippled Demiurg ships must try to disengage
  every turn (moving towards the nearest table edge if they fail). If the opposing fleet includes
  any Ork vessels, they start this only at 2 or fewer hits remaining instead of when crippled.
- Absorber/Repulsor Fields corrected: Demiurg ships are NOT immune to blast markers in general.
  They take no speed penalty from them; are immune to solar flares, radiation bursts and gas/dust
  clouds; collect every blast marker their base touches while moving. Markers in contact at the
  start of the move are collected first, so they don't affect a command check made then; command
  checks at other times are affected normally.
- Cutting beam: two collected markers may instead raise its range to 30cm; unused markers are
  lost at the end of each turn.

# Twenty-fourth update: Kroot Warsphere assault points

- In Planetary Assault, each attacking Warsphere that lands scores +3 assault points; Warspheres
  never score assault points any other way (Xenos p.97).

# Twenty-fifth update: Chaos second pass, Appendix 2

Chaos fleet lists (Imperium pp.54-61):
- 13th Black Crusade battleships include the Relictor (300); it was missing.
- Planet Killer counts as a battleship for fleet requirements and restrictions.
- Crusade: ships with Stormbird gunships cannot buy mine launchers.
- Incursion: Marks of Chaos (any vessel led by a Lord, Warmaster or aspiring champion; Undivided
  25 on the commander's ship only, others 15).
- Renegades: (0-1) Chaos Space Hulk 650 (must be the flagship); CSM strike cruiser limit is per
  500pts (or portion thereof); CSM battle barges / strike cruisers are Chaos ships, not allies of
  convenience; Chaos Terminators +25 on CSM battleships, battle barges, grand cruisers, strike
  cruisers.
- Reserves for Incursion, Crusade and Renegades (each may take from the other two; no Planet
  Killer, no space hulk).
- God-dedicated fleets: NOT identical to the Crusade list. No Abaddon, no Planet Killer, no space
  hulk; only their own god's dedicated battleship; CSM crew +35 on any capital ship (Terminators
  +25 on battleships/grand cruisers with CSM); only their own god's Mark (+15).
- Aspiring champion re-roll only for his own ship or squadron.

Appendix 2: Imperial crew skills are used by AdMech, Chaos, IN, Inquisition, Rogue Trader and
Space Marine ships; Xenos crew skills by Dark Eldar, Eldar, Ork and Tau (Necrons and Tyranids
gain none).

# Twenty-sixth update: core rules 1-25 in rulebook wording

Ciarán's rule: where the XR rulebook says the same thing as the booklet, use the rulebook's
wording. Sections 1-25 of the core rules are now rulebook text, in British spelling, for 131
paragraphs. Corrections made on the way:
- Special orders are declared ship by ship, each just before that ship moves (not all at the
  start of the movement phase).
- Ships in a squadron, capital ships included, combine their firepower.
- (Corrected in the thirty-third update: fleet commander re-rolls are lost on Bridge Smashed OR when the commander's ship is destroyed. This is Ciaran's ruling, and it stands.)
- Capital ship squadron page ref: rulebook p.58, "Forming Squadrons". (Superseded by update 30: it now points to Forming Squadrons at the end of section 8.)
- Broken cross-refs "sections 16-1922 / 19-1922 / 23-2326" are now 16-22 / 19-22 / 23-26.
- Unit types: the rulebook's type list and defence rule (no "stations").
The booklet is now 186 pages; the TOC and internal page refs are shifted +4 (Rogue Traders 68).

Follow-up: the Armament row went back to "firepower for gunnery weapons (FP) or strength for launching ordnance markers (S)", because the booklet lists lances as FP. (Superseded by update 28: it now says "direct-fire weapons such as macrobatteries and lances".)

# Twenty-seventh update: core rules 26-41 in rulebook wording

32 more paragraphs swapped to rulebook text (hit-and-run, teleport, boarding, critical hits, hulks, disengaging, battlefield set-up, battlezones, warp rifts, planet note). The contents page now matches the render for sections 28, 35, 36, 38, 40 and campaign rules 4-6, with Rogue Traders at 69. The booklet is 187 pages; internal refs are +1.

# Twenty-eighth update

- Armament row: "firepower for direct-fire weapons such as macrobatteries and lances (FP) or strength for launching ordnance markers (S)".
- Lance values are called firepower everywhere in the core rules (special orders, Brace for Impact, lance firing, crippled ships); ordnance keeps strength.
- Fixed-Ld pointer added to section 3 and Appendix 4.
- Blast markers: the XR optional modern rules and the Remastered rules are now separate sections. "Remastered Blast Markers" has its own heading, and the Remastered no-limit-when-stacked rule moved out of the XR Overlapping Bases rule into the Remastered spill-over exceptions.

# Twenty-ninth update

Remastered "Limit on spill-over" rewritten: the rulebook placement sentence (p.68), then the two-ship limit and its two exceptions as numbered paragraphs. Exception 2 now covers ships overlapping any ship in contact with blast markers, not only the target.

# Thirtieth update: core rules wording fixes 1-8, 10-15

Ciaran-approved rewordings of awkward rulebook passages: reserves limit, 750-point commander rule, Ld modifier limits, a typo, Burn Retros speed, Forming Squadrons refs, Dauntless example, different aspects, moving through blast markers, weapons batteries label, splitting fire, nova cannon placement, scatter and centre hole (the centre hole gives D6 hits instead of the 1 hit). The section 7 TOC entry is now 8.

# Thirty-first update: core rules wording fixes 9, 16, 18-25

Squadron against squadron and combining torpedoes (contiguous base contact) use Ciaran's wording; turning torpedoes keeps the rulebook text. Rulebook page refs in the attack craft rules now point to sections 25/26. The bomber attack rule is clarified and the rulebook example restored. CAP movement and leaving CAP, the hulk gravity-well pronouns and asteroid shields/slowing are reworded. The sunward edge roll is written out (the booklet had no diagram). American spellings in core rules are British. The TOC matches the render.

Follow-up: Squadron against squadron now says separate target sets come from range, arc or target aspect.

# Thirty-second update: scenario/campaign source restorations

Planetary Assault and Assault on a Craftworld: capital ships count as having ½ a point of transport capacity (the ½ had been lost). Campaign build-up step 1 now points to Using Attack Ratings instead of rulebook p.78. Refits: "must roll on" restored.

# Thirty-third update: CORRECTION to the twenty-sixth update

The twenty-sixth update removed "or is destroyed" from the fleet commander re-roll rule. That was wrong and is reversed. **Ruling (Ciaran, standing): a commander's re-rolls are lost for the rest of the battle if the ship carrying them suffers a Bridge Smashed critical hit OR is destroyed.** This applies to fleet commanders and secondary commanders. The rulebook's campaign rules support it ("If the flagship is destroyed... He or she may not have any further effect in that game"). The booklet now reads: "If a ship suffers a Bridge Smashed critical hit or is destroyed, any re-rolls from an embarked commander are lost for the remainder of the battle." Code must remove the re-rolls in both cases. Do not drop the "destroyed" case again because the core rules paragraph doesn't mention it.

# Thirty-fourth update: commander's ship destroyed

Ruling (Ciarán, standing): "The opponent scores the commander's VPs, & all commander rerolls are
lost." When the ship carrying a commander is destroyed, the opponent scores the commander's cost
(the commander plus his or her re-rolls and upgrades, which section 5 adds to that ship's victory
point value), and every re-roll that commander has is lost for the rest of the battle. Code must
do both. Added to the Standing rulings in CLAUDE.md.

# Thirty-fifth update: lance values are firepower everywhere

The last places outside the core rules that still called lance values "strength" now say "firepower": the crippled-ship summary, the design guideline (lance firepower per arc 3-4), the +1 lance firepower refit, the Chaos rule on firing at the offending ship ("half its gunnery and lance firepower"), the Demiurg Cutting Beam (firepower 1 to 8, shown as FP1+ to match the profile; it said S1+), the Craftworld fortresses' "firepower 1 pulsar lance", and the Appendix 2 Dorsal Lance refit. Ordnance still uses strength. The weapons batteries label in section 13 is bold again.

# Thirty-sixth update: scenarios and campaigns wording (Ciarán-approved)

- Rulebook page references in scenario and campaign rules now point to booklet sections:
  celestial phenomena and battlezone tables section 39, low orbit and landing section 41, hulks
  section 34, mines section 17, advanced rules sections 12 and 31-37, commanders section 5,
  secret lists section 4, planetary defences, orbital mines and the General Fleet Support List
  Support Assets.
- Comma splices split in fourteen places. The Raids table label is its own line again.
- Extended Duty: -1 to command checks (it said Leadership tests) for Lock On and Reload Ordnance.
- Fleet Experience: the flagship must keep at least 75% of its starting hits.
- Fresh Captain: suffers -1 Leadership. Campaign crippled ships lose 1 Leadership (minimum 6).
- Enemy Plans: +1 to the D6 when boarding the enemy fleet commander's ship, 4+ finds the plans.
- Meteor Storm, Navigational Hazards, Surprise Attack: the sub-plot succeeds if you win the
  battle and fails if you lose.
- Decoy: an extra ship presented as a capital ship that uses conventional transport
  characteristics.
- Navigate the Storm: if only one player meets their objective, that player wins; otherwise
  (both or neither) the most transport capacity destroyed or evacuated wins; ties go to the
  attacker.
- Planetary Assault and Craftworld Assault: subtract 1 per 500 defender VP (or portion thereof).
- Grammar: Gates "deploys", appeals "depends", "fewer systems", "re-roll".

# Thirty-seventh update: faction sections and appendices in sourcebook wording

The same rule as the core rules: where the sourcebook says the same thing, its wording is used
(97 paragraphs; table cells unchanged). Rule changes that came with it:
- Inquisitorial Fleet Detachment retinue: only "Any Inquisitorial cruiser or vessel embarking
  an Inquisitor (of any rank)" may take one (+15).
- Daemonship materialising: no special orders until the END of its next turn, Brace for
  Impact included.
- Ramilies and Fortress-Monastery: nova cannon / Armageddon gun D6 hits go against the quadrant
  most under the centre hole; quadrants are crippled once reduced to 6 Damage Points.
- Battlefleet Cadia: ships with a veteran captain must be squadroned; a captain may go on an
  escort squadron (whole squadron gets the bonus).
- Nicassar Caravan must move exactly 10cm in any direction each movement phase.
Other fixes: lance values (zzapp gunz, cutting beam, looted killkannon, Man O' War example
lances) are firepower, not strength. 39 cross-references into the Mechanicus / Space Marine /
Inquisition rules and the appendices were 1-6 pages out and are corrected. 46 American spellings
are now British (Armor -> Armour etc.; text matching in ship notes may need updating). The booklet
is 188 pages; Rogue Traders starts on p.70.

# Thirty-eighth update: faction wording fixes

Wording only, no rule changes:
- Support Assets limits: "all must be the same type" now applies only to Blackstone Fortresses
  (bracketed with the one-Activated-per-750-points limit).
- Radical Ordo Malleus: Marks of Chaos pointer now reads "see Marks of Chaos in the Chaos faction
  rules (p.88)".
- 13th Black Crusade Marks of Chaos: colon before the costs, semicolon between them.
- Killkannons: described as a salvaged bombardment cannon, a salvaged nova cannon, or a very large
  Ork-made gun (flavour only; the firing rules are unchanged).

# Thirty-ninth update: table cells in sourcebook wording

Long table cells (ship special rules, fleet list notes, scenario/campaign tables, refits and crew
skills, damage tables) now use the sourcebook's wording wherever it says the same thing (123
cells). Short stat cells are unchanged. Mostly wording; points to check in code:
- Lance values given as strength in the source are firepower: orbital defence laser option (+1
  lance firepower for -30cm range), Xenos Weapon Emplacement, Plasma Drive Overload / Warp Drive
  Implosion lance shots, space hulk "Target high-energy systems" (5-6: -1 firepower to all lances).
- Refit and crew skill text now
  matches Imperium p.151-152 / Xenos p.122-123 rule sentences (flavour omitted).
- The booklet is 189 pages: everything from Support Assets on moved one page later (Support Assets
  84, Chaos 89, Orks 100, Tau 110, Scenarios 119, Campaigns 163, Appendix 1-7 at
  175/177/182/185/186/187/188). Internal cross-references updated.

# Fortieth update: table wording decisions

Wording only. Xenos Logic Engine sub-plot VC now reads "VC: none; the sub-plot succeeds if you
win the battle and fails if you lose." Mimic Drive points to the booklet's Conventional Transport
entry (Convoy Ships table, p.87) instead of the BFG:XR Rulebook. Extended Duty keeps "command
checks".

# Forty-first update: Remastered blast marker clarifications in source wording

The three blast marker passages taken from Remastered (pp.68-69) now use the Remastered wording:
the base-contact clarification in section 11, "Whole-base contact" and "Firing ship in contact"
in the Remastered differences. No rule changes. Section 37 (Disengaging) now starts on p.32.

# Forty-second update: scenario diagrams corrected

Sixteen scenario maps redrawn (tools/diagrams.py regenerates them; table drawn as 180x120cm).
Rules content that changed:
- Cruiser Clash: Fleet A / Fleet B are 90cm-wide zones centred on the long edges, 30cm deep,
  60cm apart (was full-width strips).
- Fleet Engagement Set-up B: bottom divisions now Div. 3, Div. 2, Div. 1 from left to right.
- Escalating Engagement: table edges numbered for the random-edge roll (1 left, 2-3 top,
  4-5 bottom, 6 right).
- Domination 5: the two centre-line objectives are 30cm from the top and bottom edges (was 45cm).
- Surprise Attack: the full-alert area is 30cm from every edge (the old box was 20cm from the short
  edges while labelled 30cm).
Layout only: Navigate the Storm, Destroy the Docks, Fleet Engagement A/C/D, Ambush, Warp Storm,
Domination 1/2/3/6 (clipped and overlapping labels, "Centre Objective").

# Forty-third update: stat corrections from the full profile check

All 178 profiles were checked against the source books (stats, weapons, launch bays). Two cells changed:
- Onslaught Attack Ship: Speed 20cm (was 25cm), Turrets 2 (was 3), per Xenos p.67.
- Ork Rok: Turns "Special" (was "None"), per Xenos p.69. turn_raw is now "Special" like the hulks.
