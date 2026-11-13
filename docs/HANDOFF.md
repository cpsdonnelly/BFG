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
  The current install is zip 12 (CHANGES.md: forty-fifth update).
- **Never invent rules.** If the booklet is silent or ambiguous, ask the owner (AskUserQuestion
  works well), then record the answer under the matching heading in `CLAUDE.md`.
- Check what an audit or helper agent reports against the booklet yourself before acting on it.
- Owner style: short directives ("go", "continue", "yes"). Finish each turn with what is left and
  a proposed next step; ask about readings rather than guess. They answer rules questions
  precisely and sometimes paste sourcebook text.
- Web client and LAN multiplayer are on hold.

## Testing

- `pytest -q` (here: `/root/.local/share/uv/tools/pytest/bin/python -m pytest -q`): **1055
  tests pass** at handoff. `tests/conftest.py` `DiceStub` with realistic rolls
  listed one by one; assert `dice._idx == len(rolls)`.
- `flake8 --select=E9,F src/` (pytest never imports the Tk files).
- GUI checks drive the real panels: `xvfb-run -a /usr/bin/python3.12 tools/gui_checks/<name>.py`
  (that Python has tkinter; it has no pytest). Run the ones touching what you changed; full AI
  games: `gui_spectator_demo.py normal` (or `expert`), `gui_spectator_orks.py normal`,
  `gui_spectator_sm.py normal`, `gui_ai_check.py` (its
  "Traceback ... boom" is a deliberate crash test). New this session: `torpedo_types_check`,
  `fleet_list_check`, `wave_check`, `combined_fire_check`; later: `combine_capital_check`,
  `best_split_check`, `combine_split_check`, `cap_wave_check`, `teleport_ai_check`,
  `remastered_suppression_check`.

## Where things stand

`CLAUDE.md` is the single current source; this file no longer keeps copies of it (they
drifted). Read there: "Session status", "AI: how it decides (expected VP)" (everything the AI
does, with the judgement weights to tune; its first part, "Fleet strategy", lists the owner's
matchup doctrine and what of it is built or planned), "To do" (agreed order, items 1-14), "Open questions"
(none open now) and every owner ruling. `docs/AI_DESIGN.md` describes the whole AI,
built and planned, in plain language (keep it in step with CLAUDE.md). This file keeps the history: owner guidance in their words,
design notes, booklet export notes and the session log.

## Earlier in the session (history; all committed and pushed)

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

## Owner guidance on AI play (from the end of this session)

(History: the owner's guidance in their words. What was built from it is described in
CLAUDE.md "AI: how it decides"; open points are in its "To do".)

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

- **Hazard avoidance (owner, this session):** the AI should avoid asteroid fields, dust
  clouds, blast markers, and incoming torpedoes and mines, with a threat level per hazard
  (one mine is more dangerous than one torpedo salvo).
- **Optional blast markers (owner, this session): done.** Advanced settings "Blast marker
  rules": XR standard / Modern / Remastered (`GameState.blast_marker_rules`,
  `src/optional_rules.py`). Modern: a target in contact counts as behind its markers (at least
  one right shift for gunnery), ordnance attacking a ship in contact rolls as if moving
  through them (6 = destroyed, a wave rolls once), and a ship overlapping the base of a ship
  in contact counts as in contact (no cascade). Remastered adds: a firing ship in contact
  shifts right (lances and nova cannon unaffected: they don't use the gunnery table).
  Whole-base contact already holds (contact ignores arcs). Not modelled: Remastered's
  spill-over limit (markers from one round touching at most two ships), and overlapping
  bases for shields / speed / Leadership (only gunnery and ordnance use it so far).

- **Destroying incoming threats (owner, this session):** fighters should go after incoming
  mines (and other dangerous ordnance); when no fighters will reach a mine in time, or there
  are none, weigh shooting it with a ship's main armament. **Done (first version):**
  `ai_hazards.marker_threat_vp` scores each enemy marker or wave by the VP it threatens
  (worst ship it can reach); AI fighters intercept the most threatening ordnance in reach
  (`ordnance.ai_craft_target`, nearest on a tie); before each battery / lance shot the AI
  compares shooting the nearest enemy marker in arc (P(a 6) x its threat, a third of that
  if a friendly fighter can reach it this ordnance phase; `AIPlayer._ordnance_shot`) with its
  best ship shot, and fires at the marker when that is worth more (`combat.fire_at_ordnance`,
  now also used by the player's Fire at Ordnance dialog).
- **Fighters do the most good (owner, this session): done.** A fighter removes one marker
  it meets (s.19): a whole torpedo salvo however strong, one mine, or one squadron of a wave
  (lead first, s.25). `ordnance.plan_fighter_intercepts` allocates the fleet's fighters
  greedily by VP saved (`ai_hazards.intercept_gain`: one fighter per salvo or mine, one per
  squadron of a wave; half value if only reachable next phase; resilient craft half); a
  spare fighter with nothing useful in reach advances on the nearest enemy ship instead of
  doubling up on a covered target.
- **Combat air patrol vs strikes (owner, this session: tricky trade-off, think it through).**
  **First version built** (`AIPlayer._bay_allocation` / `_strike_option` / `_launch_defence`):
  per launching ship, greedy over its slots in expected VP (step 3 below, one ship at a time);
  CAP on the friendly ship a threat is closing on (within its move + 15cm; the fighters must
  reach that ship), free fighters at 0.75 within their reach, otherwise the strike's marginal
  value; threats our fighters already target count as covered. Not yet: fleet-wide allocation
  across carriers, option value of keeping bays loaded, CAP against bomber waves the enemy may
  launch next (reactive CAP). Plan:
  1. *Launch slots*: each ship with loaded bays offers squadrons of the craft types it can
     launch (bay strength, fleet craft limit s.15). Launching uses the bays up until Reload
     Ordnance, so a slot also has an option value: keeping it loaded keeps next turn's choice
     open (higher when the enemy is still out of reach or its ordnance hasn't launched yet).
  2. *Three uses, one currency (expected VP)*:
     - CAP fighters on ship S: VP saved = sum over enemy ordnance / waves that can reach S
       before our next ordnance phase of P(the CAP squadron stops it) x `marker_threat_vp`,
       with diminishing returns (one CAP squadron meets one enemy squadron or salvo; check
       s.26 for how many it can engage). A ship with many shields / turrets needs it less;
       the flagship counts its commander value (ai_hazards.ship_value).
     - Free fighters: the same saving for ordnance they can reach in their move (no
       double move risk), plus escorting our own bombers (fewer of them lost).
     - Bombers / assault boats offensively: expected VP on the best enemy ship in reach
       after its turrets and the interceptions its fighters / CAP are likely to make
       (ai_hazards.shot_vp style, with ship_attack_plan's suppression maths).
  3. *Allocation*: greedy across the fleet: list every slot x use with its marginal value,
     take the best, update what it covers (a threat already stopped is worth nothing to the
     next fighter; a target already likely dead to the next bomber), repeat; keep a slot
     loaded when its best use is worth less than its option value. Many enemy mines /
     torpedoes push value to CAP and free fighters; a weak enemy screen pushes it to strikes.
  4. *Tests*: lots of incoming mines -> CAP / fighters chosen; no enemy ordnance and a
     crippled enemy in reach -> bombers; mixed -> both, fighters first on the threatened
     ship.

- **Turret priorities (owner, this session):** checked against s.28 and the Ork rules and
  fixed: the split now works both ways and covers mines (mines were exempt, torpedoes didn't
  block anti-craft fire); it resets every phase for every ship (it used to last until the
  ship's own next turn); Ork turrets hit on 5+ with no split. When both kinds attack a ship in
  one phase it chooses (AI: expected hits saved; human: prompt). Owner ruling: bomber attack
  reduction still applies after turrets fired at torpedoes / mines. Also fixed: a bomber's
  expected attacks are E[max(0, D6 - turrets)] in the AI maths (was 3.5 - turrets).

### AI design (plan agreed in principle; build in this order)

One common currency: **expected victory points**, so hazards, targets and re-rolls compare.
A ship's "value at risk" is its VP (points value, x1.25 venerable, its commander's cost and
re-rolls included; the flagship counts double while the fleet still has re-rolls to lose).

1. **Hazards: done (first version).** `ai_hazards.move_hazard_vp` scores every movement
   candidate of the normal and expert AI (`AIPlayer._position_penalty` with the ship and its
   path, converted at 0.35 expected hits per point of in-arc firepower). Mines (20cm reach if
   it's the nearest enemy), torpedoes (next move line, turrets first), bombers / assault
   boats in reach, asteroid fields, warp rifts, dust clouds, blast markers crossed and shields
   lost to markers at the end. Hits near the cripple / kill thresholds weigh more. Since
   done: guided / seeking torpedo turn cones (`_torpedo_heading`) and the Burn Retros
   decision by expected VP (`_burn_retros_worth_it`).
   Original plan: (`ai_hazards.py`, used by every movement candidate, along the whole path,
   not just the end point). Threat = expected damage x the ship's VP per hit, plus speed or
   firing losses where they matter. From the rules, not invented weights:
   - mines: 8D6 vs Armour, ignoring shields, moving 10cm towards the nearest enemy every
     ordnance phase, so a mine's reach next phase is a 10cm (+ base) circle around it;
   - torpedoes: strength dice vs Armour, ignoring shields, along their next move line (speed);
     guided / seeking salvos get a turn cone; boarding torpedoes as raids;
   - attack craft heading for the ship: bombers' expected attacks after turrets;
   - asteroid fields: P(fail the Ld test) x D6 damage (shields stop it), escorts' re-roll;
   - warp rifts: P(fail) x the ship;
   - dust clouds: -5cm, and 1/6 damage only without shields;
   - blast markers: -5cm speed, shields down while touching, 1/6 damage to shieldless ships.
   So a mine (8 dice) weighs more than a 2-6 strength salvo, as the owner expects.
2. **Re-roll importance: done (first version).** `ai_rerolls.should_reroll` replaces the
   "2+ left" rule in `GamePanel._ld_reroll_hook`, the guided-torpedo re-roll and the AI's own
   failed special orders (it never re-rolled those before). Bars: 45 VP for the last
   re-roll, 25 with two, 15 with three, 10 with more; everything goes once the commander's
   ship is about to be lost (`commander_in_danger`). Brace scores lack the attack's expected
   hits when asked through the generic hook (default 2).
   Original plan: score each failed test by the VP it swings (finishing or crippling
   a target, a Brace that saves a ship, a navigation test that risks it, disengaging a
   crippled ship, the flagship's own tests); spend when the score clears a bar that rises as
   re-rolls run out (the last one only on the biggest swings); spend everything left when
   the commander's ship is about to be lost.
3. **Targeting by expected VP: done for single weapons.** `AIPlayer._pick_target` (normal
   and up) takes the target with the most marginal expected VP (`ai_hazards.shot_vp`:
   expected hits from `combat.expected_hits`, shields first, Poisson spread for P(kill) /
   P(cripple), a little per hull hit, a little for shields knocked down), counting the
   expected hits already committed to each target this phase (`_committed`), so it stops
   firing at a ship that is probably dead. Since done: combined squadron fire for the AI
   (`_squadron_volleys`) and hulks (`_hulk_shot`; Holding the Field VP still not counted).
   Since done too: the "Best for expected hits" default (`combat.best_aspect_choice`). Fixed: the AI now takes the target priority test (s.13) like the
   player's Fire dialog (`AIPlayer._enforce_target_priority`: nearest visible enemy unless
   the test is passed, once per ship per turn; re-rolls by importance); it used to fire at
   any target in arc.
   Original plan: per weapon / combined squadron fire, expected hits ->
   P(kill), P(cripple) -> expected VP; prefer finishing and crippling, avoid overkill
   (stop committing fire once the target is likely dead), don't spread too thin; hulks are
   targets when worth it (a re-rolled catastrophic result can hurt nearby enemies; no VP
   for a hulk already scored). The Combine Squadron Fire dialog gets a "Best for expected
   hits" default from the same scorer.
4. **Commander's ship: done (first version).** Its movement candidates add the enemy direct
   fire that could reach the end point next turn (`AIPlayer._flagship_exposure_vp`, weapons
   within range + the enemy's speed, arcs ignored, half weight), and it braces at a sixth of
   its hits instead of a quarter while it still has re-rolls (`ai_should_brace`). Not yet:
   keeping escorts near it.
   Original plan: movement scores its exposure (enemy firepower that can reach it) at
   a higher weight, it braces earlier, and the AI keeps escorts near it.

## Readings to confirm (my choices; the owner answered the open ones, see "Owner answers" above)

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
- Mark of Tzeentch AI: re-rolls a critical of 9+ on its own ship and 5 or less on an enemy.
- Troop rating: doubling / halving applies to hits remaining, the turrets added after
  ("after any other modifiers"); halving rounds up.
- Navy profile refits with no "one of" wording (Mercury's two, Tyrant's two, Mars / Overlord's
  two) may all be taken together; the grand cruisers' "may buy one of" is one only.

## Booklet export bug to report

- `ships.json` `profile_from` is still cut off for the three Grey Knights escorts
  ("Space Marine Nova (p", "... Gladius (p", "... Hunter (p"). The game doesn't use the field.

## Booklet zip 13 (updates 46-55, installed last)

Installed per the zip's HANDOFF_README. Catalog diff (stats, rules, weapons, options, notes,
Ld table, unsupported of every entry): the 195 existing entries are unchanged; 34 new ones,
Eldar 24 (MMS v2.0, update 49) and Necrons 10 (update 48), all unsupported
(`booklet_ships.UNBUILT_FACTION_RULES` plus the parser's own reasons: "Weapons Battery",
Pulsar / Phantom Lances, Eldar torpedoes, Necron weapons, three-speed movement, points "-" for
the Eldar Transport). Update 46 (Man O' War prow lances FP3) is in the Man O' War
configuration text, which isn't built (To do 5), so no entry changed. Update 47 (space hulk
rules) likewise (To do 5). Rules files renumbered (Eldar 08, Necrons 09, Orks 10, Tau 11,
scenarios 12, campaigns 13, appendices 14-20); no code opens them by name, docstrings and
CLAUDE.md updated. Built: the factions (Eldar roll the Eldar column; Necrons Default, since
Appendix 4 has no Necron column although the owner ruling says "Necron column"), the Necron
commanders with the Obelisk ruling (`booklet_options.NECRON_COMMANDERS`). AA files now in
`docs/`: the order-systems notes moved to `docs/AA_ORDER_SYSTEMS_NOTES.md`, the working notes
are `docs/AA_ACTIVATION_NOTES.md` (the path the zip's readme names), the draft PDF beside them.
CLAUDE.md: To do 9 has the Remastered escort squadron VP option, To do 14 is Eldar and Necrons.

## Booklet zip 12 (updates 44-45)

Catalog diff: only the Citadel's base (now 60mm, large). Done: the Expedition's Bastion is 255
(was 225); Demiurg Hired Reserves (`fleet_lists.DEMIURG_HIRED`, a reserve-only list of Bastion
255 / Citadel 185 offered to every list that takes reserves except Orks, Bakka, the Expedition
and the War Host; counted as cruiser reserves at the list's normal ratio, Dominion included).
Already matching: the Bastion's modular bays (one mode per turn, Reload Ordnance after either).
Not yet: the Bastion's mines as a third mode (mine launcher swaps don't exist yet), the Tau
Orbital City's hook rules (not playable), the Mercenaries rule.

## Booklet zip 11 (updates 39-43)

Table cells now use sourcebook wording. Code matches notes text in places, so the built
catalog was diffed before and after: five matches broke (Exorcist macrobattery refit, Terror
Ship launcha, Fra'al targeting matrix, battle barge and Vanguard torpedo swaps) and now
accept both wordings. Real changes: Onslaught Attack Ship speed 20cm, turrets 2; Ork Rok turns
"Special". Scenario maps redrawn (Cruiser Clash zones, Domination 5 objectives, Surprise
Attack alert area): scenarios aren't laid out by the game yet. **After every export, diff the
built catalog** (a script that dumps every entry's stats, rules, weapons and options).

## Booklet zip 10 (updates 37-38)

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
- Tau (22-23): **done:** the Demiurg War Host list (`tau_demiurg_war_host`: no commander,
  War Host re-rolls 1 for 25 / 2 for 75 usable by any Demiurg vessel and never lost
  (`Ship.war_host_rerolls`, `TurnController._war_host_rerolls`), more Demiurg commerce
  vessels than other cruisers incl. reserves, one Stronghold per two cruisers, 0-12 cruisers,
  Kroot 0-3 one per 750 or portion, one escort squadron per three Demiurg capital ships,
  Warden / Orca / Dhow mixing, no Demiurg-Tau squadrons, Kor'or'vesh reserves only
  (`reserve_sections`), Rogue Trader detachment may join). The Demiurg ships are playable:
  absorber fields (never slowed; collect every blast marker touched while moving, those in
  contact first, before a movement-phase command check: `movement.collect_blast_markers`;
  immune to solar flares, radiation bursts, dust clouds), cutting beam (FP 1 + collected
  markers, max 8; two markers for 30cm range: `combat.cutting_beam_firepower`; unused
  markers lost at the start of the owner's next turn), the Bastion's modular bays (owner
  ruling: S2 bays or S4 torpedoes chosen at each launch; launching either uses both,
  `Ship.mark_launched`), Demiurg VP (higher value if the fleet is all Demiurg or the enemy
  has Ork vessels). Mercenaries are done (see Disengaging). Not yet: mine launchers, the Courier Transport
  (scenario only), the Tau list's "allies of convenience" effects (attack rating), undoing a
  Demiurg move doesn't put collected blast markers back.
- Chaos (25): **done:** Planet Killer counts as a battleship (Battleships section, 1000+);
  reserves among Incursion / Crusade / Renegades (`reserve_excludes`: no Planet Killer or
  space hulk); Renegades space hulk (0-1, unplayable); renegade cruisers -1 rolled Ld and
  renegade ships Chaos crew (`stat_changes` lists of `add_rules`); Marks of Chaos (Khorne
  doubles troops, Nurgle +1 hit, Slaanesh -1 Ld to enemies within 15cm in command checks and
  disengage tests, Tzeentch re-rolls a critical it suffers or inflicts: `combat._tzeentch_reroll`,
  `GameState.crit_reroll_hook`; dedicated battleships' free Marks and crews from notes);
  Chaos Space Marine crews (+35: Space Marine boarding / raids / teleports, Astartes Ld or +1 to
  a commander's fixed Ld) and Terminators (+25); per-list rules in
  `fleet_lists._chaos_option_errors` (Incursion marks need a leader; Crusade one of each;
  Renegades / gods leader or CSM, Renegades crews per full 750, Terminators on battleships
  and grand cruisers; gods only their own Mark; same-mark squadrons). Boarding (s.32): crew
  bonuses Chaos +1, Orks +1, largest only; Ork Warboss doubles troops; Kor'vattra halve,
  Nicassar halve when boarded. Not yet: Mark of Chaos Undivided (not offered: the fleet uses
  the marked ship's Ld once per game), Tzeentch on hit-and-run crit results, Slaanesh on
  navigation tests, daemonships, Stormbird gunships, Abaddon, god boons, mine launchers, CSM
  battle barge / strike cruiser (not in the catalog), Mechanicus attackers' boarding re-roll,
  Nicassar never initiating boarding.
- Core (26-31): **checked.** Special orders are already declared ship by ship just before
  each ship moves (player dialog and AI); squadron fire combines capital ships too
  (`plan_squadron_volley`); squadron-against-squadron target sets come from range, arc and
  aspect; the nova cannon centre hole gives D6 hits. Fixed: torpedoes pass through every
  friendly ship in contiguous base contact with the launcher or combining group when fired
  (`ordnance.combined_exempt`; before, only the launcher / group was exempt). Not built (optional
  play modes, s.11): "Modern Blast Markers" (intervening blasts, overlapping bases) and
  "Remastered Blast Markers" (whole-base contact, firing ship in contact shifts right,
  spill-over limit). Ask the owner whether he wants them as game-setup options.

## Known limitations of this session's work

- Several Ork Bosses: each gets `flagship` from its option, but the engine keeps one re-roll
  pool (the first flagship's). Boss titles on other ships aren't usable yet.
- Ork kustom upgrades, clans and Nobz; named commanders (Lord Admiral Rath, Abaddon,
  Kor'O'Mesme); Space Marine Captains on Dominion reserves; Rogue Trader Bond-Captains;
  Inquisition Inquisitors (non-Lord), Elite Captains / Daemonhunters, retinues, honour guards
  and Ordos are not in the fleet builder.
- The AI uses fleet re-rolls on Leadership tests only while it has 2+ left; it never takes
  secondary commanders' re-rolls into account beyond that (they are spent first automatically).

## Fighter / bomber split and combined squadron launches (latest)

- `waves.wave_split_value(fighters, bombers, turrets, shots, cap, armour, p_turret, f_save,
  b_save, cap_save)`: expected hits of one wave. Enemy CAP intercepts first
  (`waves.cap_survivors`, resilient saves per s.23); then turret shots (innate + massed,
  binomial, never stopped by resilient saves) remove squadrons from the front (fighters first);
  surviving fighters suppress one bomber each (3 attacks); other bombers roll D6 - innate turrets.
  `best_wave_split(slots, ...)` tries every split. Example, 6 bays vs Armour 5: turrets 1-2 ->
  all bombers; 3 -> 3/3; 4 -> 4/2; with 2 CAP fighters, one more fighter each time. Resilient
  4+ bombers vs 3 turrets / 2 CAP -> 0/6 (no escort needed); resilient 4+ fighters vs 4 turrets
  / 2 CAP -> 4/2 instead of 5/1; vs 2 turrets / 1 CAP -> 1/5 instead of 0/6.
- Launch dialog "Best split" (`OrdnancePanel._best_split_plan`): shown only when the bays offer a
  pure fighter and a pure bomber type (multi-role craft use the s.27 suppression choice instead)
  and 2+ bays. A "Plan vs" target list (nearest first) fills editable Bays / Turrets / Massed /
  CAP / Armour fields (owner request: enter expected reactive CAP, or hold bays back); "Reset"
  refills them; the note says "custom values" once edited. Resilient saves (own fighters /
  bombers from the craft profiles, enemy CAP from its markers, all editable) go through
  `waves.cap_survivors` (exact recursion over CAP interactions, s.23 rules incl. the used save
  and both-pass removal), then the turret roll. Wave size < bays: lone and CAP fighters are
  launched outside the wave in the same launch (`extra_vars`). The combined launch dialog has a compact version (target, wave
  size, CAP) and the AI launches the planner's mix (`AIPlayer._wave_split`). The engine now
  resolves CAP against incoming groups lead first before the turret roll
  (`waves.resolve_cap_vs_group`), matching the planner.
- Combine Ordnance Launch (s.15) groups only members of one squadron in contiguous base contact
  (`contiguous_contact_groups` per `squadron_id`), capital ships included; unsquadroned ships in
  contact no longer combine. GUI checks: `combine_capital_check.py`, `best_split_check.py`.

## Session log (latest session, newest last; history)

All work committed and pushed on `claude/battlefleet-gothic-simulator-3sUkl`; 1075 tests pass,
`flake8 --select=E9,F src/` clean, all GUI checks pass.

Latest items, newest last:
- Wave planner in the launch dialogs (resilient saves, partial launches with lone / CAP
  fighters, editable inputs; compact version in the combined launch dialog); the AI launches the
  planner's mix (`AIPlayer._wave_split`).
- Combined ordnance launches only within a squadron (capital ships too).
- The engine resolves CAP against incoming craft lead first before the turret roll, with s.23
  saves (`waves.resolve_cap_vs_group`; both-pass removal also in `resolve_fighter_intercept`).
- AI respects armament crits (`combat.weapon_disabled_by_crit`).
- Wings of Fury re-rolls by expected VP. Owner rulings: Engine Room kept, escorts re-roll results
  under 4, and armament crits are valued by what the weapons threaten at the target's NEXT
  shooting phase (reach = range + movement before it; in arc now or after one turn at 0.75),
  weighted by the chance damage control hasn't repaired them (`p_crit_unrepaired`).
- Resilient saves: owner confirmed the booklet (against any other ordnance, never turrets).
- Bombers vs assault boats by expected VP (multi-role attack mode, the human prompt's Auto
  (best), AI carrier launches). Fixed on the way: the raid value of a destroying hit on a 1-hit
  escort counted the ship twice.
- AI CAP vs strikes, first version (To do 1): per carrier, fighters to CAP / free only when
  a threat is worth more than the next strike squadron.
- AI shoots enemy hulks when the re-rolled catastrophic damage would blow up among enemies
  (`ai_hazards.hulk_shot_vp`, `AIPlayer._hulk_shot`); AI hits on hulks now reach
  `apply_damage` (they were dropped before).
- AI voluntary disengagement by expected VP (`ai_hazards.incoming_hits / disengage_gain`,
  `AIPlayer._consider_disengage`); tune on the owner's feedback (one-turn horizon, Poisson risk).
  Threat per weapon mount (`ai_hazards._mount_bears`, owner: good positioning lets a ship fire
  both broadsides at different targets; never both at one), and the enemy focuses fire
  (`enemy_fire_plan`, owner: optimal play concentrates fire rather than splitting it): each
  mount goes wholly to the target it adds most VP to, biggest mounts first, so fire piles onto
  a damaged ship until it is likely dead and then moves on. Reusable for brace / positioning.
- AI ordnance focus by expected VP (owner: focusing on easier targets is optimal): torpedoes,
  strike launches and craft in flight (`_best_torp_target`, `_strike_option`,
  `ai_hazards.plan_strike_targets`), from the enemy's actual state after shooting plus the
  phase's planned ordnance. Gunnery does this already (`shot_vp` with `_committed`). Owner
  asked "does the AI focus / position for it?": guns, ordnance and positioning now all do
  (positioning: next item).
- AI fleet focus positioning (first version): `ai_hazards.fleet_focus_targets` picks one
  enemy per turn by the VP the fleet's guns in reach would add (easier / damaged first); ships
  that can reach it plan their moves against it, keep 0.3 weight on their nearest enemy, and
  pay half the hits the enemy could focus on their end position
  (`ai_hazards.position_exposure_hits`).
- Bombers always attack the lowest Armour value (a rule, s.20; the owner asked for it everywhere). Checked everywhere; the AI's hazard
  maths for incoming bombers used the facing Armour and is fixed (`ai_hazards.marker_hits`).
- AI Shooting by Squadrons: `AIPlayer._squadron_volleys` combines each squadron's batteries
  into one volley (combat.plan_squadron_volley / resolve_squadron_volley) at the best
  expected-VP target that is every contributor's nearest valid target.
- Owner asked whether Tau-style forward arcs are accounted for: yes; (L/F), (R/F) mounts are
  two weapons with overlapping front arcs, and the AI planners treat them per mount (tests in
  `tests/test_ai_forward_arcs.py`).
- Owner: not all ships turn alike (Tau Protector 90 degrees, Hero 45). Every turn allowance in
  the AI (threat model `_mount_bears`, Wings of Fury `_weapon_can_bear`, move planning) reads
  the ship's own `turn_angle`; a test pins it.
- Hazard maths: seeking / guided / Tau torpedo turn cones (`ai_hazards._torpedo_heading`,
  `_in_turn_cone`; guided salvos now at the launcher's real Ld, see below).
- Hazards in the AI's targeting (owner check): battery values include column shifts
  (`expected_hits(..., gs)`), torpedo / strike targets weighted by
  `ai_hazards.ordnance_path_survival` (mirrors the engine's terrain rules). Owner answers on
  dust clouds built: a cloud in the line of fire shifts macrobatteries but doesn't stack with
  blast markers; attack craft in a cloud die on a 6.
- Owner: craft (and turning torpedoes, within their turns) can fly round obstacles:
  `ai_hazards.best_route` (detour waypoints), used by strike targeting and by AI craft movement
  (`ordnance.craft_target_point`, AI-owned craft only).
- AI: guided salvos use the launcher's Ld (`guided_turn_chance`); Burn Retros by expected VP
  (`_burn_retros_worth_it`); escorts screen the commander's ship for massed turrets (base
  contact, s.29) while ordnance threatens it (`_screen_bonus`).
- Owner: turning torpedoes aren't all Ld-based. Hazard maths per type (s.16, s.09): boarding
  torpedoes turn freely within 45; Tau missiles turn 45, reach 40cm, 5/6 strength; guided at the
  launcher's Ld; seeking at the nearest enemy; the rest straight. Torpedo bombers (s.21) still
  count as bombers until To do 3 builds their salvos; owner: a wave of 4 torpedo bombers
  becomes one combined strength-8 salvo (s.21: waves combine like a squadron in base contact).
- Owner: kills / cripples now count the damage they prevent (`ship_threat_vp`) and the chance a
  kill explodes among nearby ships (`death_explosion_vp`); movement avoids ships about to blow
  up and a dying ship hugs enemies (`explosion_position_vp`). Torpedo-bomber salvos last one
  phase (s.21); owner ruled on Tau Tiger Shark salvos (CLAUDE.md: S2 Tau missiles, 20-40cm,
  removed that phase, no strength-loss roll). Torpedo bomber options
  ("TB 20cm +N") are on 19 carriers: Navy 6, Mechanicus 3, Chaos 10, plus Tau Tiger Sharks
  (full list in CLAUDE.md To do 3; the owner corrected an earlier, incomplete list).
- AI CAP vs strikes fleet-wide (`AIPlayer._plan_fleet_defence`): threat slots go to the
  carrier whose strike loses least; carriers no longer each send a fighter at one salvo.
  Each carrier then takes the exact best number of defence slots (`_best_defence_count`:
  strike values are convex, so one-at-a-time comparisons misjudged them), and enemy carriers
  with loaded bombers / boats in reach of our ships create CAP-only slots
  (`_anticipated_strike_slots`, weight 0.5, judgement: owner feedback welcome).
  Fighters already on CAP now cover the launched threats closing on their ship first, and
  carriers keep their bays loaded while no enemy ship is within three moves of their fastest
  craft and no enemy ordnance is in play (Reload Ordnance needed after a launch, s.15).
  Torpedo launch lanes (`AIPlayer._torp_lane`): the AI aims down the heading worth most
  that still meets the target. Owner: friendly fire is negative VP, so each lane counts the
  ships the salvo hits on the way (s.15: it attacks friend or foe and carries on weakened):
  our ships cost their damage's VP; it holds fire when the result is a net loss.
- Owner: lead torpedo targets. `AIPlayer._torp_lead_plan` samples the target's next move
  (`ai_hazards.enemy_move_samples`: minimum move, turning distance, Burn Retros / AAF dodges)
  and scores each heading over the launch move, the enemy's movement (running into the
  parked salvo) and the enemy's ordnance phase; `DODGE_WEIGHT` 0.5 is judgement (owner
  feedback welcome). Owner: closing easiest, abeam hardest, receding between. Built with a
  second-turn horizon (`LATER_TURN_WEIGHT` 0.5) and a course prior (`MOVE_TURN_WEIGHTS`: 40%
  straight, 15% each turn); at 40cm: closing 0.64, receding 0.34, abeam 0.32. Torpedo path hazards now use the
  marker's width (`torpedo_path_survival`). Turning salvos steer ahead of their target.
  Owner: target size; contacts use each ship's base (large bases easier to hit; closing
  battleships, 15cm before turning, can't sidestep), in our aim and in `marker_hits`.
- Owner: turning salvos that roll against Armour (Tau missiles, Ld-guided, boarding) plan
  approaches for the weakest facing they can reach (`ai_hazards.approach_plan`: launch
  heading, then a 45-degree turn per move, four moves deep; facing from the contact point;
  phase weights, Ld odds, Tau strength loss), used at launch (`_approach_for_launch`),
  recorded on the salvo (`torp_target_id`) and followed in flight (`salvo_approach`,
  `ordnance_movement._ai_salvo_turn`, `_steer_guided_missile`). Under 25ms a plan.
- Owner: sooner beats later. `ai_hazards.phase_weight(k)` (0.85 per ordnance phase, x 0.5 from
  the next game turn: 1, 0.85, 0.36, 0.31) weights hits in `approach_plan` and the lead plan;
  `travel_discount` shares `PHASE_DISCOUNT`.
- Two-waypoint routes for craft and turning torpedoes (`best_route`: detours of detours).
- Loaded torpedoes count in the move score (`_arc_score`): the AI steers to end with the
  target in its launcher's arc and reach.
- Several focus targets (`ai_hazards.fleet_focus_assignment`): each ship's guns where they add
  most VP given the others' (no overkill; a covered kill frees ships for the next target).
- Holding bays within reach by option value (`AIPlayer._hold_bays`): hold when
  (1 - reload odds) x next turn's launch or CAP value > launching now.
- Expert AI search uses the normal AI's expected-VP terms (`lookahead_ai`: hit maths, focus
  without overkill, torpedoes, explosions, shields per turn, real table; leaf = banked VP +
  next turn's expected swing at LATER_TURN_WEIGHT). Expert spectator games run clean.
  The spectator GUI checks take a difficulty argument (`... gui_spectator_demo.py normal`).
- Owner: carrier doctrine. With more launch capacity, kill the enemy's carriers for air
  supremacy (their bays count in `ship_threat_vp` via `bay_threat_vp`: strikes + denial of
  ours); with less, protect our carriers (`_carrier_exposure`) and fly more CAP /
  interception (`_anticipated_weight` scales with the air balance).
- Owner: enemy carriers threaten our strikes (a smaller air wing playing defence can cut a
  wave of 8 to 2); strike targets outside their umbrella. `strike_timeline` now also counts
  enemy fighters already in flight (`airborne_intercept`), the planner mixes every
  interception case and chooses its split against them.
- Owner: co-ordinate bombers and missiles (turret split, s.28; not against Orks):
  `ai_hazards.turret_split_gain`, planned arrivals in `AIPlayer._ord_arrivals`, scored by both
  the strike planner and torpedo targeting.
- Owner fleet-strategy notes this stretch (all in CLAUDE.md To do 8, not hard rules: "it
  depends on the matchup"): crossing the T / both broadsides busy (gun-heavy Imperium, e.g.
  Lunars), kiting (Chaos, or any fleet that out-ranges and out-moves its enemy on average),
  Tau prow-on only when the enemy is about to be in range; firepower by range bracket, fleet
  vs fleet and ship vs ship (brackets 0-15 for Ork Heavy Gunz, unique to Orks; 15-30; 30-45;
  45-60 for Chaos 60cm guns; 60-150 for artillery such as the Nova Cannon, 30cm minimum; e.g.
  a Tau Merchant out-guns a Lunar at 30-45cm, not 0-30cm); a speed edge to get out of the
  enemy's main arcs (e.g. a Lunar's rear); a hit-point edge (Orks) to think about boarding and
  ramming (the AI plans neither yet); teleport attacks both ways (8 j). First step for all of
  them: exposure that respects our Armour facing (8 a).
- Owner checked my understanding of the turret split (s.28): it blocks only the shoot-down roll
  (one die per turret plus massed, each success removes a squadron or a torpedo); bombers'
  attacks are still cut by the ship's own turrets (s.20: "still applies even if the defending
  ship fired its turrets at torpedoes or mines"). So against a high-turret ship bombers gain
  little from the split; missiles gain most when the turrets go to the bombers.
- Owner ruling: keep the Remastered turret-suppression toggle and follow Remastered p.82
  exactly (each fighter in the wave +1 attack to the wave's total, capped at surviving bombers,
  needs one; shot-down fighters still count, CAP-intercepted ones don't; turrets take fighters
  first; no fixed 3 attacks, that's XR only). Built and tested against p.82's two worked
  examples; the planner and AI follow the mode (CLAUDE.md owner rulings).
- Toggle audit (owner: check the other toggles too): boarding and ramming are gated for
  players and resolved only when on; Fighting Sunward / Solar Flares / Radiation Bursts (s.40)
  aren't built, their toggles do nothing (settings now says "not built yet", To do 6); the
  Remastered turret-suppression toggle isn't a booklet rule (open question then; since
  answered: keep it and follow p.82, built, see above).
- Owner: the hit-and-run toggle covers every raid: off, assault boats, boarding torpedoes and
  teleport attacks are disabled for the players too (`ordnance.craft_type_allowed`,
  `launch_torpedoes`, `check_teleport_eligibility`; multi-role craft still fly as fighters /
  bombers). Tests that play raids use `tests/conftest.make_gs_raids`.
- Owner: a disabled optional rule (e.g. teleport attacks) is neither valued in the AI's moves
  nor attempted. Recorded in CLAUDE.md "AI: how it decides" with an audit: hit-and-run is
  respected; boarding / ramming / teleport aren't valued yet (new terms must check their
  flags); gap then: Remastered turret suppression wasn't followed by the planner (since fixed:
  `waves.wave_split_value` follows the mode).
- Fixed: the AI's teleport attacks went to the human's dialog in its own end phase; it now
  raids the eligible target worth most per raid (`tools/gui_checks/teleport_ai_check.py`;
  teleports are an optional rule, `GameState.rule_teleport`).
- Spectator checks: expert games get 180s (they took ~75s of the old 90s limit and one run
  under load went over).
- Owner request: a new To do item 7, scenarios and sub-plots in the engine and the AI (after
  items 1-6). Brief tidied: CLAUDE.md now has one "AI: how it decides" section and a To do of
  open items only (renumbered 1-7: tuning, strike planning at arrival, mines / torpedo
  bombers, commanders and options, unplayable units, smaller gaps, scenarios); this file keeps
  history and points to CLAUDE.md instead of copying it.
- Design notes from the owner discussion: "Bombers vs assault boats" and "Ordnance strike
  planning" below.
- Owner notes on special orders: orders come before the move, so Lock On is worth it when an
  enemy WILL or CAN be in arc after it; a failed command check ends the turn's orders (s.2), so
  orders must be prioritised. Recorded as To do 10.
- Owner: the expert AI (5 turns ahead) must know the turn limit and play riskier when behind
  near the end, safer when ahead (To do 2); the AI must play every scenario's own win
  conditions, Domination being only one example of many (To do 7).
- New `docs/AI_DESIGN.md`: the AI in plain language (values, weapons, movement, targets,
  fighters, candidates, look-ahead, weights, win conditions, difficulty levels, gaps), sent to
  the owner.
- Owner's AI design feedback (file reviewed against the booklet), recorded as To do 11 / 12 and
  in To do 1 / 10. Checked in code: gunnery values subtract shields; the per-hit value is 0.2 x
  points / starting hits (doc wording fixed); Ork turrets 5+ and fire at everything; mines home
  on the layer's enemies, 10cm (gap: the AI's mine hazard ignores turrets). Bombers-lowest-
  Armour attributed to s.20 (a rule). Brace rules recorded: a failed command check doesn't
  block Brace; a failed brace blocks that ship until the attacker has finished; decided per
  weapon, tried once per attacker per turn (owner: fail against a ship's batteries and you
  can't brace against its lances). Brace has a cost, to be priced (To do 11 c). Weight tuning
  (CMA-ES, last) and a learned evaluation (after 11) agreed.
- Fixed: the AI's fire asked the target to brace once per firing ship, so a player who
  declined against its batteries wasn't asked before its lances; it now asks before each
  weapon (`AIPlayer._offer_brace(ship, target, weapons)`, `tests/test_brace_timing.py`).
  1076 tests pass; brace, spectator (normal, Orks, Space Marines), siege, Ork fire, squadron
  fire and AI GUI checks pass.
- Fixed: the AI's mine hazard counted 8D6 flat; it now counts the turret roll that cuts a mine
  to 4D6 (`ai_hazards.mine_attack_dice`). The player's Fire dialog asked the target once for
  all weapons fired together; it now fires batteries, then lances, then the nova cannon, asks
  before each kind and applies each kind's hits before the next question (hits rolled before
  the brace get no save; hulks still take the volley at once). 1077 tests; brace, fire dialog,
  hulk fire, siege, combined fire, Heavy Gunz, Ork fire, gui and spectator checks pass.
- Built (To do 2): armament crits are valued over the target's later shooting phases too, up
  to `CRIT_HORIZON` 3 and the turn limit (two more end phases of repairs each, a turn's more
  movement in the reach, `phase_weight`); Wings of Fury decisions in the tests are unchanged, a
  weapon out of reach next phase is now worth a little (`tests/test_raid_reroll_value.py`).
- Built (To do 2): craft already in flight are re-targeted with the same interception cases as
  planned strikes (reactive CAP, other carriers' launches, fighters flying;
  `ai_hazards.interception_cases`), so a wave in flight avoids an enemy carrier's umbrella.
- Built (To do 2): fighter / bomber strikes may launch as two waves when enemy guns can shoot
  the waiting wave (`AIPlayer._two_wave_value`, `ai_hazards.split_wave_survival`): split vs a
  1-turret target under two gunships, one wave vs 4 turrets or with no guns. 1081 tests.
- Built (To do 2, owner's turn-limit risk preference): with a turn limit the expert AI's leaf
  is the chance of winning (`lookahead_ai.win_score`: margin vs the spread of the fighting to
  come over the turns left, plus a small VP tie-break); behind on the last turn a brawl beats
  staying out of range, ahead the reverse. Expert spectator game 71s. 1083 tests.
- Built (To do 2): the normal AI's risk preference for disengaging and re-rolls
  (`ai_hazards.game_risk`, `certainty_equivalent`; `ai_rerolls.should_reroll` drops its bars
  to the lowest on the final turn). 1086 tests.
- Built (To do 11 b, minimum): the expert AI's root moves pay the normal AI's path-hazard cost
  (`move_hazard_vp`), so it takes a move clear of an asteroid field it would otherwise clip.
  Expert spectator game 76s. 1087 tests.
- Built (To do 8 a): exposure respects our Armour facing (`ai_hazards.mount_hits`, used by
  `position_exposure_hits` and `enemy_fire_plan`); prow-on (6+) is half as exposed as side-on
  (5+) to an enemy broadside. 1088 tests.
- Built (To do 8 f, the table): firepower by range bracket, ship vs ship and fleet vs fleet
  (`ai_hazards.bracket_matchup`, `fleet_bracket_table`, `best_bracket`, `nova_expected_hits`,
  `past_shields`); the owner's Merchant / Lunar example comes out right. Movement doesn't use
  it yet (11 a, 8 c). 1093 tests.
- Built (To do 11 a, first slice): turn points, a 50% distance, and the guns-to-bear and
  range-band goals in `AIPlayer._move_candidates`; every candidate validated by the engine.
  1096 tests; normal, Ork, Space Marine and expert spectator games pass.
- Owner notes on alternate activation (optional ruleset, not the booklet): three selectable
  activation-order systems, System 3 (adjusted bag) the default; recorded as CLAUDE.md To do
  13, notes kept in `docs/AA_ACTIVATION_NOTES.md`. The edge-share check values reproduce from
  the notes' formula. The AA working notes and the draft PDF aren't in the repo (asked for).
- Owner notes on movement: target-directed candidate moves (goals per target and fleet-wide,
  a small fallback grid, the hybrid with a denser grid, hill-climbing, a source diagnostic)
  replace the 15-degree heading steps; recorded as To do 11 a.

Next (To do 2 done this session apart from scenario points, which wait on To do 7): the rest of 11 a (more goals, refinement,
the coordination pass; its prerequisites 8 a and 8 f are built), then items 3-7, 9, 10
and the rest of 11 (item 3 carries the full torpedo bomber rules incl. combined wave salvos, one-phase
salvos, the AI changes they need and the Tiger Shark ruling), then 12 (learned evaluation);
item 1 (weight tuning) last and on hold. Owner: "the order isn't hugely important"; follow
the dependencies (8 a Armour facing and 8 f range brackets before 11 a's target-directed
candidates), so item 8 is no longer an open question.

### Session after booklet zip 13 ("keep going until you finish all tasks")

All committed and pushed; CLAUDE.md holds the detail of each. In order:
- Zip 13 installed (Eldar, Necrons, Necron commanders, AA docs, the Remastered escort VP option).
- To do 2 finished but scenario points: priced Brace with the risk preference, strikes and the
  guns a disengaging ship gives up by certainty equivalent, the expert simulating its own
  ordnance in flight.
- To do 11 a: more goals (prow-on, rear arc, second target, escort support, Lock On next turn,
  boarding reach), hill-climbing, the denser grid, the support move order, the expert root
  using the candidates.
- To do 3 done: mine launcher swaps, mines laid by the AI, launcher crits; torpedo bombers and
  Tiger Sharks (purchases, salvos, limited fuel, player button, AI).
- To do 4 parts: Grand Master, Elite Daemonhunters / Captains, Bond-Captains, Mark of Chaos
  Undivided, Stormbirds.
- To do 6 done: Demiurg undo, forced fleeing enforced, s.40 (Sunward, flares, bursts).
- To do 9 / 11: Auto (best) on every prompt (Brace, order re-rolls, Vault), Nova Cannon,
  repairs and blast marker removal by value, batteries before lances, scale-free re-roll bars,
  Easy softmax moves, the plasma overload's ordnance value, the first-turn roll-off.
- To do 10: Lock On and All Ahead Full by value, check-order risk, re-rolls counting blocked
  orders, Burn Retros paying the lost teleport.
- To do 8: both broadsides busy, kiting, teleport offence / defence / brace, boarding and
  ramming.
- To do 13: the activation-order core (`src/activation.py`), check values reproduced.
Readings flagged for the owner: Necrons roll Default Ld (no Necron column in Appendix 4); light
cruisers aren't "cruisers" for the mine swap; the Bastion pays +5 a bay for its mine mode;
Stormbird bays halved each (rounding up); s.40 toggles stand for the battle being in range of
the effect and one flare / burst die each; the burst's re-roll limit applies to every re-roll.
GUI checks now answer Brace and order re-roll prompts by replacing `choice_dialog.yes_no`.
Later in the same session:
- To do 4: Ork kustom upgrades, the Nob, Big Mek repair die, Goffs / Evil Sunz; god-fleet
  boons (Veil of Lust, Siren's Summon, Miasma (gunnery and ordnance), Plague Arks); named commanders
  (Rath, Abaddon, Kor'O'Mesme).
- To do 5: Zzapp Gunz, Kustom Kannon, the Planet Killer's Armageddon Gun (Slamblasta, Hammer
  and Planet Killer now playable).
- Rules fix: only the defender adds turrets to troop rating (s.32); ten boarding tests that
  encoded the old behaviour were corrected.
- AI: lance values use each weapon's hit roll (`ai_hazards.lance_p`).
Known gaps flagged in CLAUDE.md beside each item: Armageddon reload malfunction (the command
check keeps only its total, so doubles can't be seen), More Dakka / Bad Moons / Deathskulls /
Blood Axes / Snakebites, Abaddon's "You Have Failed Me", Rath's random refits, Warp Beasts / Berzerker Tide /
Strands of Fortune, daemonships (the next big rules item: they touch every targeting and
ordnance path), the AA round wiring. In ordinary games the AI rarely gets the chance to board
or ram (no contact or dead-ahead target arose in the Ork spectator runs with both rules on);
the mechanics are unit-tested.
Tests at the end: 1172 pass; every GUI check passed in the last full run (the later
Armageddon / Kustom Kannon changes were checked with the checks they touch).
Then ("go" after the brief update), all pushed:
- Miasma of Pestilence's ordnance part (ordnance attacking it dies on a 6, any blast marker
  rules); the AI's ordnance values count it and the Modern / Remastered blast-contact roll
  (`ai_hazards.attack_survival`); `tools/gui_checks/miasma_check.py`.
- Siren's Summon against plain Leadership tests: voluntary disengage tests can't be taken
  (`blocked`; a squadron tests from a member outside 15cm), forced ones fail (asteroids, warp
  rifts, guided torpedo control, Heed the Machine Spirit); the AI's disengage value knows.
  Reading to confirm: an escort squadron's off-table / forced tests are `blocked` too.
- To do 10: Reload Ordnance by value (`_reload_value`) and Come to New Heading by value
  (`_ctnh_moves` two-leg moves, `_ctnh_gain`); only 10 e's small Brace items remain.
- To do 11 a: safety goals (hazard tangents), disengaging valued at the end position
  (`_disengage_spot`), one round of the coordination pass (`_coordination_plan`, `_ships_at`).
  The expert's root moves under Come to New Heading stay one-turn (not yet two).
Tests: 1183 pass; spectator games (normal, expert, Orks, Space Marines) pass.
Owner (latest): don't start learned evaluation (To do 12) or weight tuning (To do 1) until
told to; when started, the experimental ML-driven AI stays separate and never replaces the
current AI.
AA progress (after "go"): `src/aa_round.py` (settings, scheduler for all three systems),
`src/aa_turn.py` (`AATurn` round driver; GameState `turn_system` / `aa_settings` / `aa_state`)
and the AI's per-unit entry points (`aa_command_phase`, `aa_phase_start`, `aa_move_unit`,
`aa_shoot_unit`, `aa_pick_unit`, `aa_choose_first`) are built and tested (1195 pass). Still to
do: GamePanel wiring (an AA option in the settings / new-game dialog, a phase flow that walks
`AATurn`, human activations by clicking a ship of the side to act, AI activations, the
ordnance phases A / B calling the ordnance movement with `may_move_ordnance`, launches only in
`launch_allowed`, both end phases), Brace as a command-phase order (reactive prompts off in
AA), boarding / ramming locked on declaration and resolved in the end phase, passing for the
AI, System 1 forcing, then the experiments.
AA, later in the same run (all pushed, 1200 tests): GamePanel plays AA (`src/aa_panel.py`;
Advanced settings: turn system, order system, phase order, launch phase, System 1 forcing),
AI-vs-AI in all three systems (`tools/gui_checks/gui_spectator_aa.py <mode>`) and a human
against the AI (`tools/gui_checks/aa_human_check.py`); Brace as a command-phase order (no
reactive prompts in AA), boarding and rams lock both ships with rams resolved in the end
phase, AI passing in movement, System 1 forcing (humans; the AI doesn't force), a human
activation limited to one unit. First-form AI choices flagged for the owner: unit order on a
draw (shooting: best shot now; movement: least engaged first), the System 3 choice (take it in
shooting, give it away in movement), passing (movement only, while the enemy has units left),
command-phase Brace by `brace_value` on the round's incoming fire. AA AI uses the normal AI
even when the game is set to expert.
Experiments: the PDF's Appendix B fleets are Imperial (Armageddon Sector) against Eldar
(MMS Corsair), so they wait on To do 14 (Eldar); an Imperial-only escort-splitting run is
possible now but isn't the owner's matchup. Each AA spectator game takes ~75-80s through
the GUI, so a batch needs a headless runner or a long background run.
Next: To do 14 (Eldar unblocks the AA experiments), 7 (scenarios), the rest of 4 / 5. Read docs/AA_ORDER_SYSTEMS_NOTES.md
(the source) and docs/AA_ACTIVATION_NOTES.md ("Discussion summary" and "Later decisions");
`src/activation.py` has the core. Open choices there become settings (`AAConfig`), not
decisions. Notes for GUI checks: `gui_spectator_*.py` need a difficulty argument
(`normal` / `expert`); a GUI check that drives ordnance contacts calls
`panel.ordnance._resolve_ship_contacts` (OrdnancePanel holds the mixin).

## Bombers vs assault boats (owner idea, done)

When a carrier can launch bombers and assault boats (or multi-role craft pick an attack mode),
the AI should choose by expected VP per squadron that reaches the target. Owner's example,
checked against s.20 / s.22 / s.31:

- Target: 4 turrets, Armour 6+ all round. Bomber: D6 - 4 attacks (s.20: innate turrets only,
  massed turrets don't reduce attacks) = 0 on 1-4, 1 on a 5, 2 on a 6, mean 0.5 attacks; each
  hits on a 6, so 0.5 x 1/6 = 0.083 hits per bomber (suppressed by a fighter: exactly 3 attacks,
  0.5 hits).
- Assault boat (s.22: one hit-and-run raid, no Armour roll): fails only on a 1 vs a capital
  ship; a 6 is Engine Room (+1 hit) on its own worth 1/6 = 0.167 hits, already twice the
  bomber, plus the 2-5 armament crits (worth what those weapons threaten,
  `hit_and_run.raid_result_value`) and Space Marine +1. So assault boats win against heavily
  armoured, high-turret targets.
- Against escorts it reverses: raids need 4+ for 1 damage (0.5 per boat), while a bomber vs
  1 turret / Armour 5+ makes D6 - 1 = 2.5 attacks x 1/3 = 0.83 hits.
- Both face the same turret roll and enemy CAP, and Brace repels raids / saves hits on 4+, so
  those don't change the choice. Implementation: bomber EV = E[max(0, D6 - t)] x P(hit) x
  value per hit; boat EV = mean over D6 of raid_result_value(roll + modifier, target); replace
  `ordnance.mr_attack_mode_ai` (raid at 3+ turrets, ignores Armour) and use it in the AI launch
  mix (`AIPlayer._launch_ship_ordnance` / `_wave_split`) and as the "Auto (best)" for the
  human multi-role prompt.

## Ordnance strike planning: design from the owner discussion (to do: CLAUDE.md To do 2)

Raised by the owner after the wave planner and the bombers-vs-assault-boats idea. Nothing
below is built yet except where it says so. The aim: one function, "expected VP of this
strike when it lands", used by the wave planner, the AI's launches, the bomber / assault boat
choice, multi-role attack modes, Wings of Fury re-rolls and the expert AI's leaf evaluation.

1. **Why expected VP (owner asked "does it help?").** It is one currency for unlike effects
   (bomber hits vs raid crits vs a silenced broadside), it knows what a target is worth and
   where its crippling / destruction thresholds are, and every AI decision already uses it.
   Weak points: crit effects (Bridge Smashed, Shields Collapse, silenced weapons) need
   judgement weights to turn into VP; it is risk-neutral (a sure 1 hit = a 50% chance of 2),
   so idea: a risk preference from the game state (behind on the last turn -> gamble; ahead ->
   play safe); and today it looks about one step ahead.

2. **Crits are worth what they do over the turns they last, not just now.** The owner's
   problem: at the start of a game every ship is out of range, so a "threatens nothing now"
   rule makes every armament crit worthless. Damage control (s.36, engine matches it: every
   ship, in every end phase of both players, `end_phase.resolve_damage_control`): one D6 per
   remaining hit, each 6 repairs one repairable crit, dice halved (round up) when touching a
   blast marker. An undamaged 8-hit cruiser repairs one crit with 1 - (5/6)^8 = 77% per end
   phase (52% touching a blast marker), so a repairable crit inflicted in your ordnance phase is
   still there for the target's next shooting phase only ~23-48% of the time. Unrepairable crits
   (Bridge Smashed, Shields Collapse, Hull Breach, Bulkhead Collapse) last all game; extra
   damage (Engine Room +1, D3, D6) counts in full anywhere. Value of a crit =
   sum over the target's future shooting phases (up to the scenario's turn limit) of
   P(still unrepaired then; several crits compete for the same 6s) x P(an allied ship in that
   weapon's arc AND range then) x VP that weapon would do. Early in a game repairable armament
   crits are then worth little, permanent ones and extra damage keep their value.

3. **Reach model** for "in arc and range then": distance minus both ships' movement before
   that shooting phase vs the weapon's range; broadside arcs count for less when the target
   would have to turn to bring them to bear.

4. **Travel time.** A crit lands when the wave arrives, not at launch. Attack craft move in
   both players' ordnance phases (up to 2 x speed per game turn) while the target moves:
   estimate the meeting point and the arrival phase, then evaluate the threat at the target's
   first shooting phase after arrival. Phase timing matters (turn order: movement, shooting,
   ordnance, end): a wave landing in your own ordnance phase faces one end phase of repairs
   before the target shoots again; one landing in the enemy's ordnance phase comes after the
   target has already fired that turn, so its repairable crits face more repairs before they
   matter. Holding a wave back or taking a longer route to strike in your own phase can pay.

5. **Losses on the way:** enemy fighters that can reach the wave first, blast markers on its
   path, CAP the target may launch before contact (the planner's editable CAP field covers it
   by hand today), the target turning away or disengaging. Against that, the option value of
   not launching yet and keeping the bays loaded (already in the CAP-vs-strikes plan).

6. **Enemy guns against the wave; splitting.** A wave is one marker for enemy shooting and is
   removed entirely by one hit (s.25); direct fire hits ordnance only on 6+, Ordnance column,
   range / blast shifts apply, no aspect (s.30); each weapon fires at one target; target
   priority counts only enemy ordnance when firing at ordnance. Splitting into groups means one
   6 removes one group, and guns spent on craft don't fire at ships. Costs: each group faces the
   target's turrets separately (s.25: lone squadrons / separate waves each face all turret dice),
   fighters only suppress bombers in their own wave, CAP meets each group lead first. Evaluate
   candidate groupings (one wave; two waves; a wave plus lone squadrons; each split by the
   planner): value = sum over groups of P(group survives the enemy shooting phases it is
   exposed to in flight) x planner value of that group, with survival ~ (5/6)^(dice the
   enemy would put on it), the enemy spending guns on ordnance only when that beats its best
   ship shot (the AI's own rule). Expected outcome: keep one big wave when it arrives before the
   enemy shoots again or flies outside its guns' arcs; split or re-time it when it must cross
   enemy guns in their shooting phase; escorts have little firepower, so it matters less
   against them. Splitting already exists in the engine (Attack Craft Orders; split groups
   never rejoin), so the AI must decide before committing.

7. **Bombers vs assault boats** (owner idea, maths checked): see the section above; it plugs into
   the same function (bomber EV vs mean raid value), now evaluated at arrival time.

8. **Expert AI long-range planning:** the search simulates a short horizon; its leaf
   evaluation should add these static terms (unrepaired-crit values over the remaining turns,
   ordnance in flight valued at arrival with survival, reach-based threat) so a move that pays
   off after the horizon is still seen.

10. **Done (this session): points 4-5 in part.** `ai_hazards.strike_timeline` gives the
   arrival phase, the landing turn (the raid's repair window), enemy guns on the way,
   reactive CAP and (owner: "reactive intercept should also be a strategy") reactive
   intercept by other enemy carriers' fighters; `_strike_option` and `plan_strike_targets` use it (CLAUDE.md To do 2 has the
   detail and what is left: crits beyond the next shooting phase, splitting, risk preference,
   the expert AI and craft in flight).

9. **Done (owner ruling: "the second idea is an extension of the first"):** Wings of Fury
   re-rolls value armament crits by the threat at the target's next shooting phase (reach =
   range + the movement before it; in arc now or after one turn at 0.75), times
   `hit_and_run.p_crit_unrepaired` (one or two end phases). Points 2-3 are thus built for raids;
   the rest (travel time, waves, splitting, expert leaf) is still to do.

## Remaining work (agreed order; CLAUDE.md "To do" has the detail)

1. On hold (owner): tuning the AI's judgement weights (listed in CLAUDE.md's AI section).
   Keep it in mind, but it is hard work, so leave it be until the owner asks. Owner (AI design
   feedback): do it last, after 11 and 12, with CMA-ES, paired common-random-number games, an
   opponent pool, judgement weights only (CLAUDE.md To do 1).
2. Strike planning at arrival time (design below, "Ordnance strike planning"); with it the
   owner's turn-limit risk preference: the expert AI (5 turns ahead) must know the turn
   limit and play riskier when behind near the end, safer when ahead (score by the chance of
   winning, not expected VP alone). Built: arrival
   phase and landing turn, enemy guns on the way, reactive CAP / intercept / fighters in
   flight, strikes outside the enemy's umbrella, co-ordinated bombers and missiles, wave
   splitting at launch, the expert's risk preference, risk-aware disengaging, re-rolls, brace
   and strikes, the expert valuing its own craft in flight. Left: scenario points (To do 7).
3. Mine launcher swaps; torpedo bombers (purchases, salvos, combined wave salvos, Tiger
   Sharks per the owner ruling) and the AI changes they need.
4. Named commanders, Mark of Chaos Undivided, daemonships, Stormbirds, god-fleet boons, Ork
   kustom upgrades / clans, other factions' secondary commanders, Inquisition Ordos.
5. Unplayable units (Zzapp Gunz, Kustom Kannon, special movement, fortress weapons...).
6. Smaller gaps: Fighting Sunward, Solar Flares and Radiation Bursts (s.40) aren't built
   (their toggles say "not built yet"), nor their +3 disengage Ld and commander re-roll limit;
   Demiurg undo doesn't return collected blast markers; forced-flee isn't enforced for humans.
7. New (owner request): scenarios and sub-plots, engine and AI: the booklet's scenarios
   (`bfgxr/rules/12_scenarios.md`) and sub-plots (p.80-82, plus Mechanicus, Inquisition and
   Rogue Trader faction sub-plots), then an AI that plays their objectives and win conditions,
   not just cruiser clash (owner: Domination's objective markers and 10-point race are just one
   example; there are many other scenarios, and the AI must handle each one's conditions). The engine has only the old generic modes today (`scenario.check_scenario_end`).
   Do items 1-6 first.
8. New (owner ideas, not hard rules: it depends on the matchup): matchup-aware manoeuvre.
   Crossing the T / both broadsides busy for gun-heavy Imperium fleets, kiting for Chaos (or
   any fleet that out-ranges and out-moves its enemy on average), Tau prow-on only when the
   enemy is about to be in range. Plan in CLAUDE.md To do 8: first make exposure respect our
   Armour facing, then a fleet-aware per-mount coverage score, a range / speed edge check
   with a kiting band, and prow-on emerging from the two. Owner added: firepower by range
   bracket fleet-wide and ship vs ship (a Tau Merchant out-guns a Lunar at 30-45cm, not at
   0-30cm), a speed edge to get out of the enemy's main arcs (e.g. a Lunar's rear), a hit-point
   edge (Orks) to think about boarding and ramming (the AI plans neither today), and carrier
   play as discussed (already built), and teleport attacks both ways (CLAUDE.md 8 j; done:
   the AI now decides its own teleports, it used to get the human's dialog). All in
   CLAUDE.md To do 8 f-j. Owner: the order isn't hugely important; 8 a and 8 f come before 11 a.
9. Smaller "Not yet" notes collected from CLAUDE.md's sections (Auto (best) prompts, bombers
   that re-roll attacks, fleet-list gaps, a Venerable Battle Barge, Rogue Trader / Ork torpedo
   options, end-of-move-only ordnance checks, a few AI cases): CLAUDE.md To do 9.
10. New (owner notes): AI special orders by expected VP. Orders come before the move, so Lock
   On is worth it when an enemy WILL or CAN be in arc (best straight move, re-rolled misses);
   a failed command check ends the turn's orders (s.2), so the AI must prioritise them (gain x
   pass chance, best first; skip a low-value order that risks the rest); every order valued
   the same way (Burn Retros vs a hazard, Lock On for hits, Come to New Heading, All Ahead
   Full, Reload Ordnance). Plan: CLAUDE.md To do 10. Brace rules recorded there (10 e): a
   failed command check doesn't block Brace; a failed brace blocks only that ship until the
   attacker has finished; brace is decided per weapon, once per attacker per turn (fail against a ship's batteries
   and you can't brace against its lances; the engine enforces it; the AI's fire now asks the
   target before each weapon). Brace has a cost, to be priced (To do 11 c).
11. New (owner's AI design feedback, CLAUDE.md To do 11): checks done (shields in gunnery
   values, the per-hit term, Ork turrets, mine movement; gap: mine hazard ignores turrets);
   movement candidates (turn points; owner's later notes: target-directed candidates, goals
   per target and fleet-wide, a small fallback grid, the hybrid with a denser grid, hill-climbing
   refinement, a source diagnostic; replaces 15-degree heading steps; coordination pass);
   hazards in the expert AI; Brace priced by its real costs; command check and disengage
   modifiers; plasma explosions destroying ordnance; teleports given up by orders; dust
   clouds; batteries before lances; damage control and blast-marker removal by expected VP;
   first-turn choice; scale-free re-roll bars; Eldar / Necrons; compute, don't script;
   softmax Easy.
13. New (owner draft): alternate activation as an optional ruleset, three selectable
   order systems (System 3 default), the AI choosing by expected VP, then the owner's
   experiments (CLAUDE.md To do 13; `docs/AA_ACTIVATION_NOTES.md`).
12. New (owner: do it, low priority, after 11): a learned evaluation for the expert search
   (features, self-play data, fit / play / refit; CLAUDE.md To do 12).

Watch the context window: read rules sections with targeted `sed -n` ranges, delegate long
transcriptions and verify a sample against the booklet yourself.
