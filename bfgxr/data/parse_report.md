# Parse report

Source: `BFGXR_XR_Companion.docx`

- Ships: 174
- Weapon entries: 457
- Parsed and round-tripped exactly: 456
- Not parsed (kept as raw text only): 1
- Ships whose Armament cell is not a weapon list: 5

## Weapons kept as raw text

- Tau & Allies / Bastion Commerce Vessel: `Dorsal Modular Launch Bays S2 or S4 Torps (All Round; ASF 30cm / BMR 20cm / AB 30cm / torps 30cm)`

## Stat cells kept as raw text only (not plain numbers)

- Rogue Traders / Stryxis Caravan Vessel: `turn_raw` = `Special`
- Support Assets / Conventional Transport: `points_raw` = `Free`
- Support Assets / Activated Blackstone Fortress: `turn_raw` = `Special`
- Chaos / Chaos Space Hulk: `turn_raw` = `Special`
- Chaos / Terminus Est (Death Guard): `points_raw` = `420*`
- Orks / Ork Space Hulk: `turn_raw` = `Special`
- Orks / Ork Rok: `turn_raw` = `None`
- Tau & Allies / Nicassar Caravan: `turn_raw` = `Special`
- Tau & Allies / Kroot Warsphere: `turn_raw` = `Special`
- Orks / Terror Ship: `armour_raw` = `6+/5+/4+`
- Orks / Kill Kroozer: `armour_raw` = `6+/5+/4+`
- Orks / Basha Lite Kroozer: `armour_raw` = `6+/5+/4+`
- Tau & Allies / Explorer Starship: `armour_raw` = `5+ / 4+R`

## Ships with no weapon list (Armament cell kept in `armament_raw`)

- Rogue Traders / Rogue Trader Man O' War (base Brig): `Built to order; port and starboard armament empty at base`
- Support Assets / Minefield: `Area terrain-defence; no stat block. Rules: see Support Ship Special Rules`
- Support Assets / Orbital Mine: `Deployed mine; no stat block. Rules: see Support Ship Special Rules`
- Support Assets / Fire Ship: `-`
- Support Assets / Fast Clipper: `-`
