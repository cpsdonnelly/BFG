# Handoff brief for the next Claude session

Read this first, then `CLAUDE.md` (the living source: every owner ruling, conventions, module
notes) and `bfgxr/CLAUDE.md` (rules authority). This file is a snapshot at the end of a long
session.

## Workflow rules (owner's standing instructions)

- Branch `claude/battlefleet-gothic-simulator-3sUkl`; commit and push there
  (`git push -u origin claude/battlefleet-gothic-simulator-3sUkl`). `main` untouched.
  **No pull requests unless asked.**
- Commit trailers: the `Co-Authored-By:` and `Claude-Session:` lines from the session reminder.
  No model identifiers in commits or code.
- `bfgxr/` is the rules authority. Each new booklet zip the owner sends **replaces `bfgxr/`
  wholesale** (extract into the scratchpad, `diff -rq`, read the new part of `CHANGES.md`,
  diff `data/ships.json` by ship, then `rm -rf bfgxr && cp -a <new> bfgxr`). Never hand-edit it.
  The current install is zip 10 (CHANGES.md: thirty-eighth update).
- **Never invent rules.** If the booklet is silent or ambiguous, ask the owner (AskUserQuestion
  works well), then record the answer under the matching heading in `CLAUDE.md`.
- Check what an audit or helper agent reports against the booklet yourself before acting on it.
- Owner style: short directives ("go", "continue", "yes"). Finish each turn with what is left and
  a proposed next step; ask about readings rather than guess. They answer rules questions
  precisely and sometimes paste sourcebook text.
- Web client and LAN multiplayer are on hold.

## Testing

- `pytest -q`: **909 tests pass** at handoff. `tests/conftest.py` `DiceStub` with realistic rolls
  listed one by one; assert `dice._idx == len(rolls)`.
- `flake8 --select=E9,F src/` (pytest never imports the Tk files).
- GUI checks drive the real panels: `xvfb-run -a /usr/bin/python3.12 tools/gui_checks/<name>.py`
  (that Python has tkinter). Run the ones touching what you changed; full AI games:
  `gui_spectator_demo.py normal`, `gui_spectator_sm.py normal`, `gui_ai_check.py` (its
  "Traceback ... boom" is a deliberate crash test). New this session: `torpedo_types_check`,
  `fleet_list_check`, `wave_check`, `combined_fire_check`.

## Done this session (all committed and pushed)

- Hulks drift only in their owner's phase; "+D6cm on AAF" sources stack (Sigils of Quickening).
- Chapter tactics: all ten checked against the booklet; Wings of Fury re-roll is the owner's
  choice per raid.
- Torpedo types (s.16): short burn, barrage bombs, guided (Ld test, fleet re-roll, enemy player
  picks the ship that tries to take control), seeking, melta, vortex (one salvo per ship per
  game; launcher-crit explosions don't use the salvo up), inferno; Navy / Chaos / Mechanicus /
  Ork / Inquisition purchase options and game-start rolls. Melta: escorts' fires repair
  normally, hulks become burning hulks. Fix: torpedoes now attack ships anywhere along their
  move.
- Ork torpedo launcha swaps; Inquisitorial Cruiser refits, Inquisitor Lord (+re-rolls).
- Booklet exports 8, 13 and 15 installed (capital-ship-only torpedo upgrades, Chaos boarding
  torps, Space Marine battle barge sections, Demiurg fixed Ld and Bridge Smashed rule).
- **Fleet lists** (s.4) for all factions in the fleet builder (`src/fleet_lists.py`,
  `src/fleet_list_data_other.py`): list choice, list costs, section limits and ratios,
  per-points limits on the fleet's actual total, reserves, detachments, list-only options,
  towed escorts and gravitic hooks. Owner rulings recorded in CLAUDE.md.
- **Waves of attack craft** (s.25, `src/waves.py`): launch as a wave, move as one, lead-first
  ordnance interactions, one turret roll per wave, fighter turret suppression, whole wave
  removed; craft orders and splitting.
- **Venerable Strike Cruisers** (Imperium p.137): 17 designed catalog entries with all design
  options; each hangar halved separately; Ablative Prow Armour now read from profiles.
- **Shooting by Squadrons** (s.8, `combat.plan_squadron_volley`): groups by aspect, range and
  armour; squadron vs squadron with aspect choice. Fix: the Combine Squadron Fire dialog had
  crashed whenever it was opened.
- Squadron volley ruling: shields knocked down by one group stay down; only column shifts
  ignore blast markers placed during the volley.
- Torpedo rulings applied: guided (re-roll on the test, enemy chooses the ship that tries to
  take control, AI uses guided), exploding melta/vortex salvos not used up, melta burns hulks.
- **Fleet commanders for every faction** (`booklet_options.COMMANDERS`, `ORK_BOSSES`,
  `fleet_commander_options`): Navy Admirals, Chaos Lord/Warmaster, Archmagos, Tau Kor'el/Kor'O,
  Rogue Trader captains, Ork Bosses with titles (Kaptin +1 Ld). Fleet lists check the required
  commander (`fleet_lists._attach_commanders`: 750+, Explorator 1000+, Orks one per 500pts,
  RT detachment always) and a Tau Custodian needs a Kor'O. Values for the Archmagos and Tau
  re-roll costs and Ork Boss Ld came from the owner; export 31 confirms them.

- **Commander re-rolls on more Leadership tests** (Brace for Impact, target priority, asteroid
  and warp rift navigation; `movement.fleet_reroll_offered`, `GameState.ld_reroll_hook`) and
  **secondary commanders** for Navy, Chaos and Mechanicus with ship/squadron-only re-rolls
  (`Ship.own_rerolls`, `booklet_options.SECONDARY`, `fleet_max:` option restriction).

## Waiting on the owner

- Nothing. Export 31 settled the 750-point commander threshold and confirmed the Archmagos /
  Tau re-roll costs.

## Owner guidance on AI play (from the end of this session)

- **AI re-rolls:** holding one back is right, but only so it can be spent on something
  important. Replace the fixed "2+ left" rule (`GamePanel._ld_reroll_hook`, `_guided_reroll`,
  AI command checks) with an importance score. Important examples from the owner: a failed
  test (e.g. Lock On, target priority) on a ship that could finish off an enemy ship or push it
  past its cripple threshold, especially when it is one of the last ships still to shoot; also
  think of others (Brace for Impact on a ship about to be destroyed or crippled; disengaging a
  crippled ship worth many VP; the flagship's own checks; asteroid / warp rift tests that
  risk losing a ship). Spend the last re-roll only on high-importance tests.
- **Commander's ship (owner ruling, booklet updates 33-34):** re-rolls are lost when the
  commander's ship is destroyed as well as on Bridge Smashed: **done in code** (fleet and
  secondary commanders, tested). The opponent scores the commander's cost; it is in the
  ship's `points_value`, which `victory_points` scores (tested). For the AI:
  protecting the commander's ship matters (keep it out of harm, brace it), and when that
  ship is about to be lost its remaining re-rolls should be spent rather than wasted.

## Readings to confirm (my choices, not owner rulings)

- Resilient squadrons don't stop or split off a wave (s.23); CAP fighters intercept a wave's
  squadrons in order after its turret roll (order of turrets vs CAP not stated).
- Melta / vortex launcher location taken from the torpedo weapon's arc.
- Sensors (Emperor, Oberon, both Mechanicus versions) and the grand cruisers' Comms Uplink:
  "+1 Ld at all times (max 10)" is added after the starting roll **and** after a commander's
  own Ld (a Fleet Admiral's Ld 9 on an Emperor becomes 10) (`ld_always:1`,
  `fleet_loader.roll_starting_leadership`). It stacks with a secondary commander's +1.
- Bakka "Mechanicus cruisers" for battlecruiser places: the four Mechanicus cruisers
  (Dictator, Gothic, Lunar, Tyrant) at their Explorator list costs, not the light cruisers.
- Fleet Defence Turrets: a crippled ship still gives its +1 (only base-contact massed turrets
  say crippled ships can't contribute); hulks don't. Distance is base edge to base edge.
- Master of the Fleet with only Space Marine Battle Barges (no Ultima or Venerable Battle
  Barge): any battle barge counts as the Chapter flagship.
- Emergency Energy Reserves "reduce by 25% (round down)": the 25% loss is rounded down
  (shields 2 stay 2, firepower 8 becomes 6), like "half rounding up" keeps the larger value.
  Its "Speed cannot drop below 15cm" applies while crippled, after a Thrusters crit too.
- Navy profile refits with no "one of" wording (Mercury's two, Tyrant's two, Mars / Overlord's
  two) may all be taken together; the grand cruisers' "may buy one of" is one only.

## Booklet export bug to report

- `ships.json` `profile_from` is still cut off for the three Grey Knights escorts
  ("Space Marine Nova (p", "... Gladius (p", "... Hunter (p"). The game doesn't use the field.

## Booklet zip 10 (updates 37-38, installed last)

Faction sections and appendices now use sourcebook wording; 46 American spellings became
British (Armor -> Armour). The built catalog (stats, weapons, rules, options) is identical
before and after, so no code matched the old spellings. Rule changes, none of them modelled
yet (notes for when they are):
- Inquisitorial Fleet Detachment retinue (+15): only an Inquisitorial cruiser or a vessel
  embarking an Inquisitor of any rank.
- Daemonship materialising: no special orders, Brace for Impact included, until the END of
  its next turn.
- Ramilies / Fortress-Monastery: nova cannon / Armageddon gun D6 hits go against the quadrant
  most under the centre hole; quadrants are crippled at 6 Damage Points.
- Battlefleet Cadia: ships with a veteran captain must be squadroned; a captain may go on an
  escort squadron (whole squadron gets the bonus, lost if the marked escort is destroyed).
- Nicassar Caravan moves exactly 10cm in any direction each movement phase (still listed as
  unsupported special movement).
- Support Assets: "all must be the same type" applies only to Blackstone Fortresses (the
  engine doesn't check support asset limits).

## Booklet export 36

Updates 32-36: scenario/campaign restorations (capital ships count ½ transport capacity in
Planetary Assault / Craftworld assault), the re-roll correction above, lance values are
"firepower" everywhere, scenario and campaign wording (Extended Duty -1 to command checks
for Lock On / Reload Ordnance; campaign crippled ships -1 Ld min 6; Planetary / Craftworld
Assault subtract 1 per 500 defender VP or portion). Scenarios and campaigns aren't modelled
in detail, so these are notes for when they are.

## Booklet export 31 (CHANGES.md updates 16-31)

Done from it: commander needed for **more than 750 points** (core s.5; lists with their own
wording keep it); re-rolls lost only on Bridge Smashed; venerable strike cruisers from any
grand cruiser / battlecruiser / heavy cruiser ("non-unique" removed); Bakka escorts (Havoc,
Viper, Firestorm, Sword), Bakka battleships and Endurance/Defiant limits "or portion thereof";
Ork Bosses one per 500pts or portion; Tau Messengers per 500 or portion; Relictor in the 13th
Black Crusade; 178 booklet ships (3 Notable Xenos cutters, Courier Transport). The Archmagos /
Tau re-roll costs and the Ork Boss rules match what was built.

**Still to do from it (read the CHANGES.md entry before each):**
- Navy (update 17): **profile refits done** (`booklet_options.navy_refit_options`, each
  matched on its note text: Victory / Mercury / Dauntless torpedoes, Lunar / Tyrant /
  Armageddon nova cannon, macrobattery range and firepower changes, Targeting Matrix, Extra
  Turrets, grand cruisers' one of Prow Torps / Comms Uplink / Improved Thrusters, Cobra
  improved sensor array, assault boats +5), Mercury 3D6 catastrophic and Sensors +1 Ld.
  Not yet: torpedo bomber purchases ("TB 20cm +Npts", Navy, Mechanicus, Chaos: torpedo
  bombers can't fire their salvo yet, s.21), the Cobra's "whole squadron must match".
  **Bakka done:** starred classes +1 Turret (`fleet_lists.list_stat_changes`, applied when the
  fleet builder saves a ship taken from the Bakka list), Veteran Captains instead of Strategic
  Commanders (`list_options` / `list_excludes`), Fleet Defence Turrets on Navy capital ships
  (-2 Turrets, +1 massed turret to friendly ships within 15cm including itself, max +3,
  `ordnance.get_massed_turret_bonus`), Mechanicus cruisers in the battlecruiser places at
  Explorator costs. No mine launcher upgrade exists to remove. Still to do: Lord Admiral Rath
  (named commander, random Pride of Bakka refits). **Armageddon done:** Master of the Fleet
  (on the Battle Barge) may be the commander; no Chapter tactics (`list_excludes`) and no
  Tactical Flexibility (`no_tactical_flexibility`: its Strike Cruiser Variants pay full
  price, in the fleet total and the saved ship's points). Admirals already go on Navy
  capital ships only; no Space Marine ship has torpedo upgrades, and power rams don't exist.
- Space Marines (18): **done:** Dominion nova cannons one per 1000pts or portion, Navy lists
  one per 500 (`nova_per_points`, refits counted); Sword RSV; Dominion reserves (Navy: big
  ships per 3 strike cruisers, cruisers per 2, no escorts; Mechanicus normally at 3:1; both
  counted against the battle barge and 0-10 strike cruiser limits); Crusade 0-10 strike
  cruisers; mixed RSV + Space Marine escort squadrons roll on the Astartes table; Space Marine
  Captains (Dominion, 25, Astartes table) and veteran honour guards (+10, Crusade / Dominion,
  `group:honour_guard` with the Terminator one); Master of the Fleet on any Space Marine
  capital ship, but on a battle barge if there is one, the Chapter flagship (Ultima or a
  Venerable Battle Barge) if present (`fleet_option_errors`); specialist torpedoes (strike
  cruiser +5 / +10 less Tactical Flexibility, needs the prow torpedo variant; battle barges
  +5 / +10; Vanguard free / +5); Chapter tactics only in Space Marine fleets
  (`fleet_lists.option_allowed`). Not yet: mine launcher swaps (Navy, Crusade, Dominion),
  the -1 Ld for a mixed squadron whose Space Marine members are all destroyed, allies of
  convenience effects (attack rating), the Fortress-Monastery.
- Mechanicus (19): **done:** Mechanicus Gifts, one per capital ship
  (`booklet_options.MECHANICUS_GIFTS`): Emergency Energy Reserves (`Ship.crippled_value`:
  crippled loses 25%, the loss rounded down; speed floor 15cm), Fleet Defence Turrets,
  Advanced Engines (+5cm, `secondary_reactors` +2D6 AAF), Advanced Shields (Overloaded
  Shield Capacitors in `combat.apply_damage`, not for explosions; right column shift while
  shields are up), Advanced Weapons (Targeting Matrix, +1 dorsal lance FP), Vault of
  Technology (`mechanicus.roll_vault_of_technology` at game start; a 6 lets the owner choose,
  the AI takes Advanced Shields). Omnissiah's Victory needs 1000+pts. Already true: ordinary
  torpedoes alongside refitted ones, escort classes mixing in squadrons. Not modelled:
  Quest for Knowledge, The Prize, Experimental Ship, Sacred Technology (campaign / scenario).
- Rogue Traders (20-21): **done:** Notable Xenos cutter profiles in every list with xenos
  cutters (35 per ship, +30 per squadron: `fleet_lists.notable_xenos_cost`, saved on the
  squadron's first ship), cutters squadron only with their own type, Pthuxutl not with Ork
  vessels, Fra'al Raider not with Imperial Navy vessels, the Fra'al targeting matrix
  (`fraal_targeting`: every target closing, no right shift beyond 30cm); Wolf-Pack limits
  "(or portion thereof)". Not modelled: Man O' War configuration (the example builds aren't
  ships), Business as Usual and High-Risk Convoys (scenarios), the Nekulli's "opposing
  Tyranids" limit (no Tyranids), Pthuxutl's disruptor cannon (a lance that may also
  shoot at attacking ordnance; unsupported; the Nekulli's whisperlance is now a lance), xenos refits (10pts or less per squadron),
  the torpedo variant for generic cutters.
- Tau (22-23): new Demiurg War Host fleet list (re-rolls 25 / 75); Courier Transport; Demiurg
  Mercenaries / Absorber fields / cutting beam; Demiurg, Nicassar and Kroot are allies of
  convenience in a Tau fleet.
- Chaos (25): Planet Killer counts as a battleship; Renegades Space Hulk 650 (flagship), CSM ships,
  Terminators; reserves among Incursion / Crusade / Renegades; god-dedicated fleets differ from
  the Crusade list (CSM crew +35, own Mark only); Incursion Marks.
- Core (26-31, rulebook wording): special orders are declared ship by ship just before each
  moves (the game declares them in a batch); capital ships in a squadron combine firepower
  (check `plan_squadron_volley`); squadron-vs-squadron target sets from range, arc or aspect;
  nova cannon centre hole D6 hits; blast marker optional / Remastered sections split. Re-read
  s.8, s.11 and s.14 against the code.

## Known limitations of this session's work

- Several Ork Bosses: each gets `flagship` from its option, but the engine keeps one re-roll
  pool (the first flagship's). Boss titles on other ships aren't usable yet.
- Ork kustom upgrades, clans and Nobz; named commanders (Lord Admiral Rath, Abaddon,
  Kor'O'Mesme); Space Marine Captains on Dominion reserves; Rogue Trader Bond-Captains;
  Inquisition Inquisitors (non-Lord), Elite Captains / Daemonhunters, retinues, honour guards
  and Ordos are not in the fleet builder.
- The AI uses fleet re-rolls on Leadership tests only while it has 2+ left; it never takes
  secondary commanders' re-rolls into account beyond that (they are spent first automatically).

## Remaining work (agreed order)

0. **First: the "Still to do" list from booklet export 31 above** (faction audits and the core
   rules now in rulebook wording). Work through it faction by faction, reading each CHANGES.md
   entry; ask the owner only where the text is unclear.

1. **MOSTLY DONE (task 1, commander re-rolls and secondary commanders):** fleet re-rolls now
   also on Brace for Impact, target priority, asteroid / warp rift navigation
   (`movement.fleet_reroll_offered`, `GameState.ld_reroll_hook` set by GamePanel); secondary
   commanders for Navy, Chaos and Mechanicus with ship/squadron-only re-rolls
   (`Ship.own_rerolls`, `booklet_options.SECONDARY`). Left: other factions' secondaries
   (Inquisition Elite Captains / Daemonhunters, Ork Nobz, Rogue Trader Bond-Captains, Space
   Marine Captains on Dominion reserves) and separate re-roll pools for several Ork Bosses.
2. **AI:** shoot at enemy hulks; use combined squadron fire (`combat.plan_squadron_volley`)
   with expected-hits / VP target scoring (see "Owner guidance on AI play"); importance-based
   re-roll spending; the "Best for expected hits" tool in the Combine Squadron Fire dialog.
3. **Disengaging (s.37):** shared escort-squadron test for a voluntary disengage, forced
   disengagement at Ld 1 or less, celestial phenomena measured to their edge.
4. **The ordinary profiles' own refits** from ships.json notes, one at a time (Mars Targeting
   Matrix, Exorcist prow torps, Repulsive extra shield, ...); Ork kustom upgrades and clans.
5. **Rules gap the owner flagged:** multi-role fighter-bombers (Thunderhawks) in a wave must be
   offered s.27's choice to suppress turrets instead of attacking, chosen before the turrets
   fire, the suppressors at the front of the wave (`waves.ship_attack_plan` already takes an
   `mr_suppress` map; add the prompt in `ordnance_movement._resolve_ship_contacts` and an AI
   choice). Fighta-Bommerz still never suppress.
6. **Smaller gaps** (see CLAUDE.md): attack craft flying straight / torpedo collisions checked
   only at the end of the move; resilient wave
   splitting; low orbit and planetary assaults (barrage bomb assault points); named commanders;
   unplayable ships (Zzapp Gunz, Kustom Kannon, special movement, fortress weapons).

Watch the context window: read rules sections with targeted `sed -n` ranges, delegate long
transcriptions (as done for the Chaos/Ork/Tau/RT fleet lists) and verify a sample against the
booklet yourself.
