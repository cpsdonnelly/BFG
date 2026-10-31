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
  00_core-rules.md            the 38 core rules sections, including Movement (7),
                              Ramming (9), Ordnance: Launching, Moving & Attacking (12),
                              Attack Craft (15), Hit-and-Run Raids with teleport attacks
                              (28) and Boarding Actions (29)
  01_imperial-navy.md ... 09_tau-allies.md
                              faction rules, ship rosters, special rules, fleet lists
  10_scenarios.md             scenarios, with deployment maps
  11_campaigns.md
  12-18_appendix-*.md         campaign tables, refits, damage tables, leadership,
                              special orders, gunnery table
  media/                      scenario deployment maps, special-order icons
  _index.txt                  file -> section title list (regenerated)
data/
  ships.json                  every ship, stats parsed, weapons parsed (see below)
  ships.csv                   one row per ship, raw cell text
  weapons.csv                 one row per weapon entry, flattened
  parse_report.md             what could not be parsed and is kept as raw text only
CHANGES.md                    what changed since the first export (two updates; read both)
source/                       copy of the .docx this export was built from
tools/                        the export scripts
```

Grep `rules/` for a rule by name; each file is a single section, so read only the one needed.

## Ship data: `data/ships.json`

One object per roster row (174 ships). Every parsed field keeps its original cell text in a
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
