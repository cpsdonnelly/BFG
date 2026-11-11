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

- `pytest -q`: **964 tests pass** at handoff. `tests/conftest.py` `DiceStub` with realistic rolls
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

## Current status (copied from CLAUDE.md; keep the two in step)

Booklet installed: zip 12 (CHANGES.md update 45). After every new export, diff the built
catalog (dump every entry's stats, rules, weapons and options before and after): notes text is
matched in code, and a reworded note silently drops an option.

Done this session (all pushed): exports 36 / zip 10-12; the whole export 31 "still to do"
list (Navy refits, Bakka, Armageddon, Space Marine lists and options, Mechanicus Gifts, Rogue
Trader Notable Xenos, Demiurg War Host and playable Demiurg ships, Hired Reserves, Chaos Marks /
CSM crews / reserves, core wording checks); boarding crew bonuses and troop modifiers (s.32);
torpedoes passing through friendly ships in contiguous contact; disengaging (s.37) incl. forced
disengagement and Demiurg Mercenaries; optional Modern / Remastered blast markers; defence
turret split (s.28) and Ork turrets; the AI work below.

AI (all in expected VP; `ai_hazards.py`, `ai_rerolls.py`, `AIPlayer`): hazard avoidance along
the move path (mines, torpedoes, attack craft, asteroids, warp rifts, dust, blast markers);
importance-based re-rolls; targeting by marginal expected VP (no overkill); target priority
test obeyed; the commander's ship protected (exposure, braces earlier); fighters allocated
fleet-wide by VP saved (one per salvo / mine, one per wave squadron); ships shoot incoming
ordnance when worth more than their best ship shot; turret choice by expected hits saved.

### To do (agreed order; detail in "AI design" and "Remaining work" below)

(CLAUDE.md "To do" is the current list; this copy is kept in step with it.)

1. AI, still to do: fleet-wide CAP / strike allocation across carriers (per-carrier version
   built), the option value of keeping bays loaded, CAP against enemy bomber waves not yet
   launched; escorts
   staying near the commander's ship; fleet focus positioning, next steps (several focus
   targets, torpedo lanes and craft reach in the move score, expert leaf evaluation). Done:
   hulk targeting, voluntary disengaging, ordnance focus by expected VP, fleet focus
   positioning (first versions: `fleet_focus_targets`, `_focus_for`, `_exposure_penalty`). The AI weights (re-roll bars 45 / 25 / 15 / 10 VP, 0.35 expected hits per point
   of in-arc firepower, half-weight flagship exposure, the disengage and hulk models) are
   judgment: tune on the owner's feedback.
1b. (done) Bombers vs assault boats by expected VP.
1c. Strike planning at arrival time ("Ordnance strike planning" below): travel time, phase
   timing, losses en route, enemy guns vs waves and splitting, risk preference, expert AI leaf
   evaluation. Built: crit value over time and the reach model, for raids (Wings of Fury).
2. (done) Thunderhawk / multi-role turret-suppression choice (s.27).
2b. (done) Wave planner follow-ups (combined launch dialog, AI launches, engine CAP vs wave).
3. Mine launcher swaps (Navy, Space Marine, Chaos, Tau lists; the Bastion's mines as a third
   mode), torpedo bomber purchases and torpedo bombers firing their salvo (s.21).
4. Named commanders (Lord Admiral Rath, Abaddon, Kor'O'Mesme), Mark of Chaos Undivided,
   daemonships, Stormbirds, god-fleet boons, Ork kustom upgrades / clans (incl. the Ork
   commander's Extra Turrets: 4+), other factions' secondary commanders, Inquisition Ordos.
5. Unplayable units: Zzapp Gunz, Kustom Kannon, special movement (Nicassar Caravan, Kroot
   Warsphere, Space Hulk), fortress weapons (Ramilies, Fortress-Monastery), Pthuxutl
   disruptor cannon, Man O' War configuration, Planet Killer's Armageddon gun.
6. Smaller gaps: the +3 disengage Ld during a radiation burst / solar flare; undoing a Demiurg move
   doesn't return collected blast markers; a human player isn't stopped from not fleeing
   after a failed forced disengage (log reminder only); scenario rules (Business as Usual,
   High-Risk Convoys, planetary assaults, low orbit).

### Owner rulings: answers to the open questions (implemented, tested)

All implemented: Fleet Defence Turrets (a crippled ship gives no +1, `ordnance.get_massed_turret_bonus`);
Bakka (Mechanicus Endeavour / Endurance / Defiant added to its Battlecruisers section); Emergency
Energy Reserves, troop rating, Sensors / Comms Uplink and Navy refits already matched (tests
added); Master of the Fleet (new free option "Chapter Flagship (0-1)" on the Space Marine Battle
Barge, `booklet_options.is_chapter_flagship`, used by `fleet_lists._sm_barge_errors` and the
placement check); overlapping bases for every blast marker effect
(`geometry.count_blast_markers_touching` + `optional_rules.overlap_ships`, the turn controller
registers the ships); Remastered spill-over limit as its own Advanced checkbox
(`GameState.rule_remastered_spillover`, `combat._place_shield_impacts`: one round of a ship's
shooting in a phase touches at most the target and one other ship; markers overlap each other
rather than touch a third ship).

- **Fleet Defence Turrets:** the gift reduces the ship's own Turrets by 2 and gives +1
  MASSED turret to all allied ships within 15cm, including itself (massed limit +3). It does
  not raise innate turrets. Crippling halves only the innate value (rounding up); the massed
  +1 is added after. Massed turrets never count towards troop rating. A crippled ship cannot
  contribute massed turrets, so a crippled Fleet Defence Turrets ship gives no +1 (including
  to itself).
- **Bakka:** any Mechanicus cruiser in the Mechanicus list's Cruisers section may take
  battlecruiser places, including the Endeavour, Endurance and Defiant light cruisers.
- **Emergency Energy Reserves:** round the LOSS down (25% of 2 = 0.5, so 2 stays 2; 4
  becomes 3; FP6 becomes 5). The 15cm speed floor still applies after Thrusters Damaged.
- **Troop rating:** apply doubling / halving to remaining hits first, then the defender adds
  turrets ("after any other modifiers"), not including massed turrets.
- **Master of the Fleet:** a standard Battle Barge is the Chapter flagship only if bought in
  the 0-1 Chapter Flagship slot (fleet must be 1000+ pts). If all battle barges are Command
  Ships, there is no flagship and the Master of the Fleet goes on any battle barge.
- **Sensors / Comms Uplink:** yes, +1 on top of the commander's Ld, max 10.
- **Navy refits:** yes, Mercury, Tyrant, Mars and Overlord refits may all be combined.
- **Optional blast markers:** overlapping bases covers every blast marker effect (shields,
  speed, Ld, shooting, ordnance). Build Remastered's spill-over limit as a separate
  Remastered option, not the XR default.

- **Troop rating, crippled defender (implemented):** it adds its CURRENT turrets, halved
  rounding up when crippled (s.33; the drawn-combat rule says "remaining turrets"). Order:
  remaining hits, any doubling / halving, then current innate turrets (crippled-halved, after
  Fleet Defence Turrets' -2, never massed) (`boarding.troop_rating`, `Ship.effective_turrets`).

### Open questions for the owner

- None open.

### Player "Auto (best)" button (owner request, done)

The player's choice prompts (re-rolls, Wings of Fury, Mark of Tzeentch, turret split,
multi-role suppression) have an "Auto (best: ...)" button picking the AI's expected-best
option (`src/choice_dialog.py`). Still to add it to: Brace for Impact, special-order
re-rolls, the Combine Squadron Fire aspect choice, the Vault of Technology chooser.
Known stale GUI check: `tools/gui_checks/heavy_gunz_check.py` expects no split-fire entry in
the Fire dialog; it already failed at the start of this session (not caused by this work).

### Owner rulings given this session (also in CLAUDE.md)

- Bastion's modular bays: S2 attack craft or S4 torpedoes, chosen at each launch.
- Turrets (s.28): after turrets fired at torpedoes / mines, bombers' attacks are still reduced
  by turrets (only the shoot-down roll is blocked).
- Optional blast markers: add Modern and Remastered as an advanced setting (done).
- AI guidance: hazards with threat levels (a mine outweighs a torpedo salvo), destroy incoming
  threats (fighters first, guns when worth it), do the most good with each fighter (one per
  salvo / mine / wave squadron), think through CAP vs strikes (plan below), protect the
  commander's ship, spend re-rolls by importance.

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

## Booklet zip 12 (updates 44-45, installed last)

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

## Session end state (latest)

All work committed and pushed on `claude/battlefleet-gothic-simulator-3sUkl`; 1018 tests pass,
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
- Owner: bombers always attack the lowest Armour value. Checked everywhere; the AI's hazard
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
  `_in_turn_cone`; guided at an assumed Ld 8 test).
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
- Design notes from the owner discussion: "Bombers vs assault boats" and "Ordnance strike
  planning" below.

Next: CLAUDE.md "To do" item 1 (what is left: fleet-wide CAP / strikes, keeping bays loaded,
reactive CAP; fleet focus positioning follow-ups: several focus targets, torpedo lanes /
craft reach in the move score, expert leaf evaluation; torpedo launch lanes and
multi-waypoint routes) and 1c (strike planning at arrival time), then items 3-6 (item 3 now
carries the full torpedo bomber rules incl. combined wave salvos and the AI changes they need). Owner feedback wanted on the AI's judgement weights, e.g. a
healthy lone cruiser facing three full enemy cruisers disengages under the current model. No open
questions (the dust-cloud answers are built: one shift at most with blast markers; attack craft
destroyed on a 6 in a cloud).

## Bombers vs assault boats (owner idea, done: CLAUDE.md To do 1b)

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

## Ordnance strike planning: design from the owner discussion (to do: CLAUDE.md To do 1c)

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

9. **Done (owner ruling: "the second idea is an extension of the first"):** Wings of Fury
   re-rolls value armament crits by the threat at the target's next shooting phase (reach =
   range + the movement before it; in arc now or after one turn at 0.75), times
   `hit_and_run.p_crit_unrepaired` (one or two end phases). Points 2-3 are thus built for raids;
   the rest (travel time, waves, splitting, expert leaf) is still to do.

## Remaining work (agreed order)

**The current to-do list and open questions are in CLAUDE.md ("To do", "Open questions for
the owner"); it supersedes the list below where they differ** (disengaging, the export 31
items and the first AI steps below are done).

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
3. **Disengaging (s.37): done.** A voluntary disengage by an escort in a squadron is one
   squadron test; a capital ship that fails leaves its squadron; Forced Disengagement at Ld 1
   or less and Demiurg Mercenaries (`disengage.mercenary_must_disengage`) test at the end of
   the movement phase (`forced_disengage_tests`), and a ship that fails gets `must_flee` (the
   AI heads for the nearest edge, `AIPlayer._plan_flee`; a human is reminded in the log);
   celestial phenomena are measured to their edge. Not yet: the +3 for a radiation burst or
   solar flare in progress (anywhere on the table); the AI never disengages voluntarily.
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
