# BFG:XR companion: rules and ship data

This folder is a machine-readable export of Ciarán's BFG:XR companion booklet
(`BFGXR_XR_Companion.docx`), a condensed rules reference for Battlefleet Gothic: Extended
Rules. It is meant as the rules source for a digital play aid.

**If you have worked with an earlier copy of this folder, read `CHANGES.md` first.** It lists
what changed in the rules and the data (newest update last), including renamed fields, new
fields and spelling changes that can break existing code.

## Source of truth

- **The .docx is the master.** Everything in `rules/` and `data/` is generated from it by
  `tools/build_export.py`. Do not edit generated files by hand: changes are lost on the next
  export and the two copies drift apart. Rule changes go into the .docx, then re-export:
  `python3 tools/build_export.py source/BFGXR_XR_Companion.docx` (needs python3 and pandoc).
  Replace `source/BFGXR_XR_Companion.docx` with the newest version of the booklet first.
- Do **not** use the older `BFGXR_Merged_Book.md` from the booklet build pipeline. It silently
  lost data (no Base column; Hits merged into a "Type/Hits" field).
- Content is real rules text. Never invent rules, stats or values. If something isn't in
  these files, say so rather than filling the gap.

## Layout

```
rules/        one Markdown file per top-level section of the booklet
  00_core-rules.md            the 41 core rules sections: Basics (1), The Turn (2),
                              Assembling the Fleet (4), Special Orders (7), Movement (10),
                              Shields & Blast Markers (11), Ramming (12), Ordnance (15),
                              Hit-and-Run Raids (31), Boarding Actions (32) and the rest;
                              grep the '## N.' headings for the full list
  01_imperial-navy.md ... 13_tyranids.md
                              faction rules, ship rosters, special rules, fleet lists
                              (08_dark-eldar.md; 09_eldar.md uses the fan Eldar MMS v2.0
                              rules; 10_necrons.md; 13_tyranids.md)
  14_scenarios.md             scenarios, with deployment maps
  15_campaigns.md
  16-22_appendix-*.md         campaign tables, refits, damage tables, leadership,
                              special orders, gunnery table
  media/                      scenario deployment maps, special-order icons
  _index.txt                  file -> section title list (regenerated)
data/
  ships.json                  every ship, stats parsed, weapons parsed (see below)
  ships.csv                   one row per ship, raw cell text
  weapons.csv                 one row per weapon entry, flattened
  parse_report.md             what could not be parsed and is kept as raw text only
CHANGES.md                    what changed since the first export, newest update last
notes/                        design notes for the simulator (not booklet rules):
  AI_DESIGN_feedback.md       review of AI_DESIGN.md: 12 prioritised tasks, ML plan
  AI_movement_target_directed_candidates.md   owner's movement-candidate design (supersedes task 2b)
  AA_activation_order_notes_for_Claude_Code.md   alternate activation: build all three ordering
                              systems; owner slightly favours System 3 (default)
  BFGXR_Alternate_Activation_Draft.pdf   owner-facing AA draft with all the numbers
  BFGXR_AltActivation_Notes.md           AA working notes (framework, open items)
  Remastered_rulings_for_engine.md       Remastered turret suppression and escort VP scoring
  OWNER_SIGNOFF_answers.md   booklet-side answers to the simulator's OWNER_SIGNOFF.md
  AI_terrain_and_learning_questions.md   terrain rule checks, missing move terms, learned-eval
                              features, luck-adjusted fitness, game-count estimates
source/                       copy of the .docx this export was built from
tools/                        the export scripts
```

Grep `rules/` for a rule by name; each file is a single section, so read only the one needed.

## Standing rulings (apply these in code)

Ciarán has ruled on these. They override any reading of the rule text alone. `CHANGES.md` gives the details.

- **Commander re-rolls** are lost for the rest of the battle if the commander's ship suffers a
  Bridge Smashed critical hit **or is destroyed**. This applies to fleet and secondary
  commanders (update 33). The core rules paragraph says so; Appendix 5's Bridge Smashed row
  reprints only the rulebook's -3 Ld text.
- **Commander's ship destroyed:** "The opponent scores the commander's VPs, & all commander
  rerolls are lost." (Ciarán, update 34.) The commander's VPs are the cost of the commander and
  his or her re-rolls and upgrades, which section 5 adds to the assigned ship's victory point
  value.
- **Inner Biosphere** phenomena, roll of 1: D6 1-3 radiation burst, 4-6 solar flare (XR typo
  corrected, update 12).
- **Fleet-builder limits:** "(or portion thereof)" rounds up, "for every full" rounds down, and
  both use the fleet's actual total; see update 15 for the Chaos ratio, Renegade and detachment
  rulings.
- **Lances** use FP (firepower) like macrobatteries; only ordnance uses S (update 28).
- **Nova cannon centre hole:** D6 hits instead of the single hit (update 30).
- **Combining torpedoes:** they don't hit ships in contiguous base contact with the combining
  group (update 31).
- **Tiger Shark salvos** (update 53): Tiger Sharks follow the torpedo bomber rules in full except
  that the salvo is a Tau missile salvo. At the start of any ordnance phase after launch, a
  squadron may be replaced by a strength-2 missile salvo placed facing any direction (a wave may
  combine salvos). It uses a torpedo marker and moves 20-40cm that phase (player's choice); the
  missile 45° turn is redundant. It is removed at the end of the ordnance phase in which it is
  fired, so the Tau missile strength-loss roll never applies. 4+ resilient, speed 20cm, treated
  as bombers versus other ordnance.
- **Ordnance in gas/dust clouds** (update 55): ordnance, attack craft included, moving through a gas or
  dust cloud tests as if moving through a blast marker (destroyed on a 6; seeking torpedoes on 5+;
  Thunderhawks exempt as for blast markers). XR's description says clouds "may destroy ordnance" but its
  Effects rule names only ships; Ciarán rules that an oversight, matching Remastered. Booklet wording is
  still pending.
- **Necron Obelisk** (update 55): it has no Ld of its own. The ship it is assigned to rolls for Ld as
  normal, and as a Monument it still gets one free re-roll and may buy more.
- **Necron Deadly Awakening applies to capital ships only** (update 59; Xenos p.41, easily missed).
  Only capital ships start conserving power (crippled for all purposes except scoring, phase out
  instead of becoming hulks), awaken, and are worth double VP once awake. Necron escorts operate
  normally all game at normal VP. An unsaved hit (or hit-and-run raid) on **any** Necron vessel,
  escorts included, still raises the alert level.
- **Light cruisers in "per N cruisers" limits** (update 58): a light cruiser counts as a cruiser when
  the fleet list places it in its Cruisers category (e.g. the Dark Eldar Succubus counts towards the
  Mortalis one-per-three-cruisers limit). A light cruiser listed as a type of cruiser is different from
  one listed in a separate class and list of ships; only the latter doesn't count. Applies to every
  faction.
- **Tyranid weapons** (update 58): massive claws and feeder tendrils use Strength, not FP. The Proteus
  hive ship's type is Defence, as printed (it moves as a battleship).

## Ship data: `data/ships.json`

One object per roster row (`ship_count` gives the total; 178 in this export). Every parsed field keeps its original cell text in a
`*_raw` sibling, so nothing is lost when a value isn't a plain number.

| field | meaning |
|---|---|
| `faction`, `source` | faction section and its sourcebook page reference |
| `roster_group` | the label above the table, e.g. "Battleships", "Escorts", "Kor'vattra (Merchant Fleet)" |
| `roster_group_notes` | intro paragraph under that label, if any; it holds rules for the whole group (e.g. all Venerable Battle Barges are Ponderous). Null otherwise |
| `faction_rules` | factions whose faction-wide rules apply to the ship: its own faction unless its Notes say otherwise (e.g. `["Grey Knights"]`; `[]` for Space Marine Rapid Strike Vessels). `faction_rules_basis` quotes the Notes phrase that set it |
| `profile_from` | profile the ship shares or reprints, e.g. "Imperial Navy Firestorm", else null |
| `name` | Class cell as printed |
| `hull_type` | only set when the booklet prints the hull type on its own line (e.g. "Escort"); otherwise it is part of `name` |
| `points`, `hits`, `shields`, `turrets` | integers, or null if the cell isn't a plain number (`-`, `Free`, `420*`) |
| `speed_cm`, `turn_deg` | integers, or null (`-`, `Special`, `None`) |
| `base` | base size as printed |
| `armour` | `{front, front_note, other}` from `6+P / 5+` style cells (`front_note`: `P` = prow armour, `D` = Tau prow deflector). Null for other forms such as `6+/5+/4+`; use `armour_raw` |
| `armament_raw` | the Armament cell exactly as printed |
| `weapons` | parsed list, below |
| `notes` | the Notes cell as plain text: special rules, refits and options. **Not parsed.** |

### Weapons

Each entry has `raw` (the original text), `parsed` (true if it round-trips exactly to `raw`),
`kind`, `group` and `location`.

- `kind: "weapon"`: `name`, `qualifier` (e.g. "standard or boarding"), `range_min_cm`
  (minimum range, only on weapons like the nova cannon `30-150cm`), `range_max_cm`, `stat`,
  `value`, `category`, `per_face`, `per_quadrant`, `mounts`.
- `kind: "launch_bays"`: `bays` (list of `{side, strength}`, with side `port`/`stbd`/`prow`/`dorsal`
  or null), `craft` (list of `{type, speed_cm}`, e.g. ASF 30cm, BMR 20cm), `stat: "S"`.
- `kind: "gravitic_hooks"` (Tau): `capacity` as printed, `sides`.
- `kind: "unparsed"`: kept as `raw` only; listed in `parse_report.md`.

Conventions the booklet uses (standardised so this parse is mechanical):

- **Weapon names:** Macrobatteries (called weapons batteries in older sources), Lances, Torps.
  Singular (Macrobattery, Lance, Railgun) when the value is 1.
- **`stat`:** `FP` for direct-fire weapons (shooting phase: macrobatteries, lances, railguns,
  ion cannons, gunz...), `S` for ordnance (torps, launch bays, gravitic launchers),
  `Template` for the nova cannon, `Special` where the profile says so. `category` is derived:
  FP/Template -> `direct`, S -> `ordnance`, else `special`.
- **`value`** is a string. Usually digits (`value_int` is then set), but some are dice or
  variable values as printed: `D6+6`, `2D6+6`, `6(10)`, `1+`, `Special`. Their meaning is in
  the faction rules text (`rules/`), not in the data.
- **`mounts`:** each bracket in the printed line is one mount at the full listed value.
  `(L), (R)` -> two mounts, `[{"arcs":["L"]},{"arcs":["R"]}]`, each firing separately.
  `(L/F/R)` -> one mount, `[{"arcs":["L","F","R"]}]`, firing once at one target.
  Arc codes: `L`, `R`, `F`, `Rear`, `All Round`. `(L/F), (R/F)` (Tau) is two mounts whose arcs
  overlap at the front.
- **`location`:** `Prow`, `Dorsal`, etc. when printed; null for side weapons.
- **`group`:** `Quadrant` / `Basilica` on star forts and fortress-monasteries, else null.
- **`per_face`:** true where the profile says "per face" (fires from each face listed).
- **`per_quadrant`:** true where the profile says "(per quadrant)" (Fortress-Monastery); these
  entries have no arc brackets.

### Known gaps (see `data/parse_report.md` for the live list)

- One weapon is an either/or choice and stays raw: the Tau Bastion's
  `Dorsal Modular Launch Bays S2 or S4 Torps (...)`.
- Five ships have no weapon list (Armament says "Built to order", "Deployed mine", `-`, etc.).
  Their rules are in the faction text.
- Refits, options and ship special rules live in `notes` and in each faction's
  "Ship Special Rules" section in `rules/`. They are prose, not data. Faction-wide rules (e.g.
  Space Marines +1 to hit-and-run raids) are in each faction file's rules section and apply to
  every ship whose `faction_rules` names that faction.
- Recurring Notes rules use fixed wording, so they can be matched as text:
  `Ponderous (no Come to New Heading)`, `Ablative Prow Armour (...)`,
  `Improved Thrusters (+D6cm on All Ahead Full)` (or the same bonus unnamed,
  `+D6cm on All Ahead Full`).
