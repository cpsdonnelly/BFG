# Session status and history

Moved out of CLAUDE.md (owner: keep CLAUDE.md small, it is read every session). The latest session first; CLAUDE.md keeps a short summary.

### Session status (details in docs/HANDOFF.md)

Latest (Dark Eldar values, the special orders audit, computed values, the hull-hit scale and
the strategy planner's first slice; all committed, 1902 tests pass (+ test_must_fixes), the ordnance sweep 5579
cases pass):
- Owner rulings: raid modifiers cancel (D6 + 1 - 1 = D6, "Owner ruling: raid modifiers
  cancel"); Come to New Heading never halves ordnance (s.7); Subjugation torpedoes are the
  Raider's ("frigate" = Raider); the AA round is now Command, Movement, Shooting, Ordnance
  A, Ordnance B, End by default (`phase_order` "ordnance_last", To do 13); shadowfield
  tracking marks can be turned off (`GameState.rule_tracking_marks`, setup and Advanced).
- Crew values per interaction (owner question): the Dark Eldar crews priced per raid,
  Impaler and boarding (see "Dark Eldar crews"); found and built on the way: Haemonculi
  boarding crits are Fires (`boarding._haemonculi_fire`), and `add_fire_crits` no longer
  adds a Fire twice through a shared crit list.
- Fire crits valued exactly (owner: several fires are likelier to outlast repairs):
  `ai_hazards.fire_burn_dist` / `fire_value` over the end phases left, for every Fire crit
  and for putting one out (`repair_value`); a thread-local guard (`_FIRE_GUARD`) stops the
  recursion through explosions and Impaler crits (nested calls fall back to half a hit).
- Dark Eldar movement and torpedoes in the AI (owner questions): one turning-distance rule,
  `movement.turn_distance(ship, order)`, shared by the engine, dialogs and every AI planner
  incl. the expert's sim (before, the AI gave Dark Eldar capital ships 10cm before turning);
  25% / 50% moves for ships with no minimum move; automatic passes (`ai_player.auto_pass`);
  torpedo loads by expected VP (`_torpedo_kind_by_value`: plasma, boarding, leech).
- Special orders audit (owner: "were you lazy with the other orders too?"; yes, several
  shortcuts, all fixed): one pass chance for every order and Brace from the engine's own
  rule (`movement.command_check_ld`, replacing five hand copies that each missed modifiers);
  All Ahead Full and Come to New Heading halve batteries and lances only (AAF halved
  everything, CtNH the whole arc score); Lock On's re-roll gain is 1 - p a die by the
  weapon's real to-hit (was a flat 0.5); `_pick_special_order` compares every order's
  pass-weighted expected VP on one scale (Burn Retros used to win whenever it beat its own
  cost; Reload was compared unweighted); Reload's torpedo value is the salvo's real hits
  after turrets (`torpedo_salvo_hits`); Brace's odds use the same rule. Games: Gothic v the
  third Dark Eldar fleet lost by 744, then 262 and 440 as these went in (AA: lost by 189);
  every game replayed exactly.
- The owner's third Dark Eldar list (`owner_dark_eldar_succubi_990.json`, 990, valid).
- Guesses replaced by computed values (owner: "bad and lazy judgement calls"):
  - Crit effects: `hit_and_run.crit_effect_value` applies the crit to a copy of the ship by
    the engine's own rules (its record, `combat.apply_crit_effects`) and compares the copy's
    exchange with our fleet (`_exchange`: its speed, turns, shields and guns as the engine
    reads them; the target attacks or evades, whichever is better for it) at each of its
    shooting phases to `CRIT_HORIZON`, x the chance the system is still down
    (`p_system_down`: exact repair chain, the system works again only when every crit of
    that type is repaired, so a second Thrusters hit adds more than the first with few
    repair dice), x `phase_weight`; Leadership losses by the Brace they cost; a commander
    killed adds his VPs. Used for every crit but armament (kept: `armament_threat_value`)
    and fires (`fire_value`): Thrusters, Engine Room, Shields Collapse, Bridge Smashed (it
    was 0.5 hit / a share of the ship's value), in raids, Impalers, boarding values and
    damage control (`repair_value`). Extra damage is `hull_hits_vp` (it was a flat hit plus
    "half the ship if it may finish it"). Leech torpedoes: the effect over the salvo's
    exact hit distribution (`torpedo_salvo_pmf`; `torpedo_salvo_hits` is now its exact mean).
  - Re-rolls: `ai_rerolls.firepower_outcomes` from exact volley distributions
    (`ai_hazards.weapon_hit_pmf`: the Gunnery table's dice, each faction's lance rules,
    saves; `volley_hull_pmf` past shields; `hits_vp`: the VP of exactly k hull hits), not
    0.6 a battery point and a linear kill chance; `importance` is what passing gains for
    each test (Brace's own price given it passes, a warp rift's lost ship, asteroid D6
    damage past shields, `disengage_gain`, target priority: best target less the closest,
    the order's value from the AI's plan or `_order_value`, a guided salvo turning vs
    straight); the flagship's 1.5x and "5% of the ship for other orders" are gone. Burn
    Retros costs its guns at full less at half, exactly (`firepower_outcomes(halve=True)`).
  - Mines: `ai_hazards.mine_value` follows each mine 10cm an ordnance phase at the nearest
    enemy over its sampled moves (contact as it moves into the mine too), 8D6 / 4D6 on its
    Armour facing the mine, for `MINE_PHASES` 4; the AI lays mines when that is worth
    anything (it was "an enemy within 60cm") and Reload Ordnance values next turn's mines
    the same (it was half a hit a launcher). A receding enemy 40cm off is never caught.
  - Found on the way: a recursion (a crit's extra damage -> an explosion -> the ordnance it
    sweeps -> an Impaler's crit), cut in `plasma_ordnance_vp` (not re-entered).
- The hull-hit scale (owner: "do the fix first", To do 33's largest item), built: a hull
  hit short of a cripple or kill is worth what it adds to the chance the enemy's fire
  cripples or destroys the ship by the end of the game (s.38 scores nothing until a
  threshold), the rule escorts already used. `ai_hazards.hits_vp(target, gs, k)`: the
  thresholds k hits cross now (destroyed: value, kill bonus, its fire, its explosion;
  crippled: a quarter and half its fire) plus `_future_loss` at `_future_fire` (next turn
  the fire that can reach it, `_fire_on`; later turns, to the turn limit or `FUTURE_TURNS`
  6, its share of the enemy fleet's guns, torpedoes and bays at `AIR_THREAT_WEIGHT`;
  undiscounted, VP are scored at the end). `value_per_hit` is now one hit's `hits_vp`
  (the shared value `static_value_per_hit` only inside its own computation);
  `damage_vp` is the Poisson count over `hits_vp`; `hull_hits_vp` lost its 0.8 share a
  hit (it is `added_vp`); explosions, the enemy fire plan, Brace's losses, bomber
  squadrons (exact binomial over the D6 of attacks), fires (exact burn totals; they were
  valued as Poisson means) and crits' extra damage (exact, D3 / D6 too) all on it; the
  move hazard's x1.5 / x2.5 weights and "half a hit a shield down" replaced (hull hits,
  and the enemy fire past the lowered shields); shot_vp's 0.1 share for hits on shields
  and "a crit ~ a hit" (`critical_hit_value` now) gone; the `max(1.0, vph)` floors gone
  from the value functions. The enemy fire plan values its shots with the future starting
  the turn after them (`_NEXT_TURN_GUARD`, they'd be counted twice), and a mount that
  bears fires even when nothing is gained (ties by hits). Loops cut: a ship's threat
  isn't re-entered (`_THREAT_GUARD`), nor a death explosion inside another
  (`_BOOM_GUARD`). Caches: `hits_vp` / `damage_vp` / explosions by `_state_stamp`
  (worked out once per set of stored ship records, `update_ship` replaces a record);
  an easy-AI movement phase 14.8s against 12.3s before (seeded games replay exactly; the
  search's cut is now a node budget, so slower values can't change a replay). Consequences, all by the rules: damage on a ship nothing
  can follow up is worth little (a 12-hit, 4-shield Emperor facing two gunships barely
  cares about a 1.2-hit salvo), a ship doomed anyway gains little from protection, the
  last turn's sub-threshold damage is worth less. Tests whose scenes had no guns or no
  points (they relied on the old floors) got a distant gunship (`conftest.make_gunship`)
  or points. Still on the old unit: the move score's firepower units, converted with
  `FP_HITS * max(1.0, value_per_hit(...))` in `ai_player` (about 25 places); still to
  convert to VP (To do 34). Games: Gothic v Dark Eldar 742-126 and 438-111, both replayed.
  Not proven better in play than the old flat value: telling them apart needs ~100 paired
  games (same seeds, sides swapped), not 3; owner: pinned, not worth it for now (the old
  value is still in the code, `static_value_per_hit`, if the comparison is ever run).
- The strategy planner, first slice (To do 34, owner: "a list of strategies all ships try
  out and then evaluate", for every ship, not Dark Eldar flanking alone): flank left /
  right, hold the band, kite, close, screen and the edge, each followed for two turns in
  the search's sim; the deterministic node budget. Games: Gothic v Dark Eldar 262-105
  (Gothic) and 165-342 (Dark Eldar), both replayed exactly, ~136s a game (too few games
  to credit the planner with the Dark Eldar win).
- The owner's four must-fixes (To do 33): BUILT, REVERTED, NOW ALL RE-ADDED one at a time (owner: "do that then", re-add
  one at a time). The code is back at the planner commit's state (0159146); the full change is
  kept as `docs/patches/must_fixes_todo33.patch` (`git apply` it, or take pieces; it includes
  `tests/test_must_fixes.py`). Why: with it, a normal Gothic v Dark Eldar game (seed 1,
  `--rules all`) ran past the runner's 600s limit after 3 turns (~160s a whole game before),
  and seed 1's replay diverged. Findings so far (fixes tried, NOT proven, all in the patch):
  (1) `ai_hazards.game_risk` is uncached and sums both fleets' fire (`fleet_hits_on`: 82,878
  calls, 379s in a 3-turn profile); Brace now values itself several times (with / without
  the order cost, the re-roll's gain), each doing two certainty equivalents, so it is called
  far more; cached on the state in the patch, still slow and still diverging after that.
  (2) `boarding_vp` 5x slower (each crit valued in full, 4 a call, in move scoring with
  boarding on); cached on a 2cm grid in the patch (warm 0.25ms vs 6.5ms before).
  (3) `next_order` (an AI order plan, ~0.2s a ship) cached once a turn first: order-dependent,
  so replays diverged; keyed on the state in the patch.
  (4) Found: `_state_stamp`'s memo trusts the records' ids, which Python reuses for new
  records (stale stamp, different in each process): the patch keeps the records alive in
  the memo. Possibly a real, older replay risk for every stamp-keyed cache (hits_vp,
  damage_vp...); worth its own check on the reverted code.
  NOTE for profiling: cProfile sees only the main thread; the movement search runs on a
  worker (`threading.setprofile` with a cProfile per thread, as in the profiling done here).
  RE-ADDED so far (each checked with one seed-1 game + replay, `tests/test_must_fixes.py`):
  (a) boarding crits + the stamp memo fix: 168s, replay same; (b) Dark Eldar raids (keel
  bays, salvo hits, superstructure): 160s, same; (c) the re-roll lift (orders and Brace,
  hand-added without the order cost) + the game_risk cache: 190s (~20% slower), same.
  (d) Brace's forbidden order and the Leadership crits' order cost (owner: option 5 with
  his feedback, "carry over last turn's calculation"): `GameState.planned_orders` {ship id:
  [order, gain VP]} written by `AIPlayer._plan_orders` (its movement / AA command phase)
  through a recorded action, `actions.store_order_plan` (replayed: a movement phase
  replayed from its record has no AI planning), and carried over until the ship's next
  plan, so a brace in its own movement phase (torpedoes after a failed Burn Retros), the
  enemy's movement (rams) or shooting all read a value at most about half a turn old;
  `ai_player.next_order_vp`: that gain at the pass chance from the ship's Ld NOW
  (`_pass_chance`, so a Bridge Smashed since counts), 0 on the last turn, braced or
  fleeing ships; no plan yet (turn 1 before it moved, a human's ship): the better of
  `lock_on_estimate` (each battery / lance's re-roll gain, hits x (1 - p), on the nearest
  enemy in arc and range now) and, with its ordnance spent (torpedo boats, carriers),
  Reload Ordnance (`_reload_value`; owner), and a human's "Auto" runs the full AI order choice
  (`next_order(full=True)`, rare; owner: the master AI always uses this slower, fresher
  value for its own braces and the Leadership crits it inflicts, `master_ai`); Leadership crits: `hit_and_run._order_loss` (the gain x
  the pass-chance drop). In AA the order a command-phase Brace gives up is this round's,
  counted the same. Since: (i) built, a squadron braces together (s.8), so its brace
  costs every member's halved fire and its one order (`ai_player.squadron_order_vp`: of the
  orders its members planned, the one worth most summed over them, at the pass chance of
  the member with the best Ld; `brace_value(group=)`, passed by `CombatPanel.
  _brace_before_attack`); not yet: the gain side still counts the saves on the attacked
  ship's hits only. (ii) dropped, it was a mistake: the lost order is valued against not
  bracing, where the guns are whole, so its gain at full guns is right; the brace's halved
  guns are already its own cost term (no double count either way). Check game (seed 1, normal): 143s, replay
  same, the same final state as before it (no squadron braced in that game).
  Master AI (owner: slow thinking is fine, broken replays are not): the fresh plan costs
  0.1-0.8s a call, once per Brace (twice with a re-roll) and once per Leadership crit
  valued (`_order_loss`, once per crit); checked: a 4-turn master game, seed 1, Gothic v
  Dark Eldar, 402s, its replay identical. Fixed on the way: `game_risk`'s cache missed scenario points
  changed in place (`scenario_state` in its key). Check game (seed 1, normal): 151s, replay
  same (Gothic won 517-18; the (c) game was 190s, so (d) costs nothing).
  All four must-fixes are back in (1907 tests pass).
  Still open: the other guessed values in To do 33.
  Planner follow-ups (To do 34): the easy AI tries no strategies, squadrons don't plan one
  heading, plans aren't carried between turns.

Previous session (owner fleets, Tyranids, Kill the Admiral, owner UI and rules reports; all
committed, 1802 tests pass, the ordnance sweep 5579 cases pass). Since: the Eldar either/or
ships, and To do 30's first slice (the AI's 0.35 rule of thumb replaced by the Gunnery
table, see To do 30):
- Done: Tyranids PLAYABLE (To do 19); Kill the Admiral AI (To do 7); booklet update 62
  (result 9 kills the commander on alien tables, Eldar on XR's crit table); the owner's Tau
  Protector, Ork and Necron fleets as files (To do 25; only Eldar left); owner UI reports (map
  editor, spectator auto-roll, deployment in any order with undo, hits and disengages in the
  on-screen log); rules / AI from the owner's questions: high orbit and asteroid fields
  (parking, tests along the path, fire inside a field, torpedoes launched inside detonate,
  craft roll moving out, a wave once), the Impaler (raids or crit by expected VP with a human
  prompt, slaves only after it connects, prow damage with its crit check), slave VP in the
  AI's boarding value, escort damage valued by the finishing chance and escort kills by the
  squadron's score, every point of damage taking its critical check.
- Eldar (the owner's last fleet, `owner_eldar_1000.json`, `tests/test_eldar_fleets.py`): the
  Corsair and Craftworld fleet lists (`fleet_list_data_other.ELDAR_LISTS`: Void Dragon with a
  Hero / High Admiral (`class_needs_option`), Void Stalkers one per full 1000pts (reading),
  Supernovas one per two cruisers, Wyrmships per Dragonship, Dragonships per two
  Wraithships, Ghostships 0-3, the specials 0-1 (Bahzhakhain and Wild Serpent over 1000pts),
  each the other's reserves, a commander over 750pts and a Dragon Prince / High Admiral over
  2000 (`commander_upgrade`)); `booklet_options.eldar_options`: Shadow / Dragon Prince,
  Admiral / High Admiral (Ld 9 / 10, 1 re-roll; the Ld 10s +1 in boarding,
  `eldar_bodyguard`), Hero +50, extra re-rolls / Farseers, Gryphon Knights 0-3 (MMS: a command
  check even after one has failed, `TurnController.checks_blocked`), Farseers 0-3 (a ship
  re-roll), Aspect Warriors (+1 boarding and raids), Seer Council (offered, Foresight not
  modelled); commanders never on Ghostships. AI fixes found by the games: an Eldar move was
  scored where its first leg ended, so second legs carried escorts off the table on turn 2
  (`_eldar_moves` now scores the end of both moves, MMS makes both in the movement phase);
  holofields in the AI's damage estimate (`mount_hits`: the lance save by range, one column
  shift against gunnery as `HOLOFIELD_SHIFT` 0.7, judgement). The five either/or Craftworld
  ships (Dragonship, Wraithship, Ghost Dragon, Ghost Wraith, Shadowhunter) are playable now:
  one weapon choice per location is a required option (`booklet_options.ELDAR_CONFIGS` /
  `eldar_configurations`, groups `eldar_prow` / `eldar_keel`; the Dragonship's and Wraithship's
  boarding torpedoes and Vampires +10 are their own keel choices); Ghostships (MMS p.20,
  `ghostship` rule): enemy boarding and raids +1 (`boarding._get_ship_modifier`,
  `hit_and_run._RAID_DEFENSE_PENALTY`), never initiate boarding or teleports, crits on 6
  (Fragile ignored); the Shadowhunter's shots at ordnance hit on 4+ (`ordnance_shots_4plus`,
  `combat.fire_at_ordnance` and the AI's value). Not yet: "a Ghostship which fails a special
  order may only move in the following turn". A Craftworld test fleet of all five played the
  Gothic fleet to game over and replayed (`tests/test_eldar_fleets.py`). Still open: the Seer
  Council's Foresight; XR's Corsair / Craftworld movement differences (MMS used).
- Raised this session, still open (see each section): the AI's capital squadrons by a draw, not
  expected VP, and re-formed escort squadrons' Ld after the roll (To do 28); exact hit counts in place of Poisson (To do 30); the Necron AI phasing small ships out early; Reciprocating Tesla Pylons (offered,
  not modelled); the Harvest Monument's "largest capital ship" placement (To do 29); high
  orbit's free turns; the AI never parks in a field in high orbit; escort disengage values
  still per ship (not by squadron); an Incubi raid's 2D6-best not in the slave-taking
  comparison; Kill the Admiral in the expert search's leaf. (The AI now deploys its own
  ships, To do 28's first slice.)

Previous session (Dark Eldar and owner UI reports; 1691 tests, the sweep 5250 cases):
- Done: Dark Eldar PLAYABLE (To do 19 slices 1-3: catalog, Kabal Variants, Raiders list,
  shadowfields, flickerfields, crit table, movement, Spectral Plating, plasma / leech torps,
  Impalers incl. fuel and own launch pool, Pain Frenzy, Incubi, Wych Cult, slave-taking with
  a human prompt, Insatiable Greed, Pain Frenzy in full: +1 boarding crew, +1 raids, and
  the re-roll of a raid / boarding crit / Impaler crit against a crippled ship (a Wych Cult
  counts enemy capital ships as crippled), `dark_eldar.pain_frenzy_applies`); the owner's Dark Eldar fleet `owner_dark_eldar_1000.json`
  (990, valid). Owner UI reports fixed: deployment faces the enemy by default, rotate
  buttons, right-click turns a placed ship, Undo Last Group; setup's AI mode is one choice,
  Player 1's own spectator difficulty, "All advanced rules" switch; a fleet relying on an
  optional rule that is off is flagged at Start Game (`fleet_rule_check.py`); the fleet
  builder shows a ship card (stats, every weapon with range / firepower / arcs / special
  flags, rules, options) for the selected catalog or fleet ship (`fleet_builder.ship_card`,
  `weapon_line`). Headless runner: `--rules all` by default, `--difficulty1`, sub-plots
  rolled. General AI fixes: squadrons take one command check (s.8, with a squadron re-roll),
  out-of-formation ships get no order, a squadron is under fire if any member touches a blast
  marker; coherency term and same-ordnance base contact bonus per mate in the chain;
  combined waves of the same ordnance; legal Come to New Heading for ships with no turning
  distance; the move picker no longer falls back off the table; flickerfields / Eldar
  stealth / plasma re-rolls in every AI ordnance value; Insatiable Greed in disengaging.
- Owner UI reports (latest), fixed: the map editor (empty strip above the board, Done
  button off a 768px screen, the X left the program waiting; windows now fit the screen);
  spectator mode's "auto-roll every pop-up" (`GameState.spectator_auto`, setup and
  Settings checkbox, on by default: dice by `dice.mode_for`, prompts take "Auto" and
  notices go to the log, `TkPrompter(root, gs)`, the fleets auto-deploy); deployment in
  any order (`DeploymentState.select_group`), taking back any placed group
  (`unplace_group`), Ctrl+Z, Start over, the panel taking the whole side panel; the
  on-screen log shows hits, damage, crippling, crits, destruction, hulks and disengaging
  (`GameState.report` queues a line, `GameContext.log` shows the queue first; AI shots
  through the shooting actions' default log; `combat._report_damage`).
- Problems found, still open: the AI plays Dark Eldar badly (it backs fragile ships off the
  enemy guns until they leave the table; loses ~650-950 VP to the Gothic fleet; needs
  multi-turn planning, and its hit values ignore shadowfield saves); torpedo salvos are not
  combined by the AI; the contact bonus is a flat 0.5 a mate, not priced by what combining
  gains; the AI doesn't form squadrons (To do 28; owner: same-ordnance escorts together).
- Escort damage short of a kill (owner): an escort's hits that leave it alive score nothing
  themselves (escorts aren't crippled; the squadron is scored as a unit), so the AI values
  them by what they add to the chance it is finished off later:
  `ai_hazards.escort_hits_vp(target, gs, k)` = value x (P(finished from its new hits) - P(from
  now)), the killing hit the whole escort; `finish_chance` from the fire its enemies can bring
  next shooting phase (`_mount_bears` / `mount_hits`, hull saves, past shields; Poisson;
  undiscounted, judgement; cached by both sides' state). Used by gunnery (`damage_vp`'s
  per-hit term for escorts), bombers (`hull_hits_vp`: no flat share a hit on escorts), raids
  and crits on ships off the crit table (`raid_result_value`, `crit_roll_value`) and the
  Impaler's two raids. So against a 2-hit escort at a plain 4+ two raids (25% kill now) beat
  the certain single hit unless our guns are sure to finish it.
  Owner correction: an escort kill isn't worth the escort either, as escorts are scored by
  squadron (s.38: nothing until half are gone, a quarter then, everything when the last goes;
  Remastered: only the whole squadron). `ai_hazards.escort_kill_vp`: the change in the
  squadron's expected score, i.e. the threshold the loss crosses now plus how much likelier the
  squadron becomes to be crippled / wiped out by its enemies' next turn of fire (shared between
  the escorts left, `_fire_on`; a Poisson-binomial over them; one turn, undiscounted,
  judgement; a lone escort is a squadron of one). Used for an escort's kill in `damage_vp` (so
  gunnery, bombers) and `escort_hits_vp` (raids, crits, the Impaler); escorts get no
  individual "crippled" term. Capital ships keep their own value. Not changed: disengage
  values for escorts (`disengage_gain`, its Remastered special case aside).
- Slave-taking (owner check): a raid's +5 VP, an Impaler's D6 x 5 VP (a braced target saves
  on 4+, a single attack) and boarding's +5 a hit / +100 Bridge Smashed are built
  (`dark_eldar.take_slaves`, `impaler_slaves`, `boarding_slave_vp`); a human is asked with
  "Auto" (`GameState.slave_hook`), the AI and "Auto" take slaves when they are worth more than
  the attack in expected VP (`wants_slaves`: a raid against `raid_squadron_value`, an Impaler
  against `waves.impaler_value`, both now priced as above). The AI's boarding value now adds
  the slave VP for the hits each side inflicts (`ai_hazards.boarding_vp`). Not yet: an Incubi
  crew's 2D6-best raid in the raid's value when weighing slaves.
- Impaler choice (owner question): after its D6 connects, two hit-and-run raids (a D6 each)
  or one critical hit (2D6 on the target's table, a Fire with Haemonculi, 1 damage on a ship
  off the table) by expected VP (`dark_eldar.impaler_effect_values` / `choose_impaler_effect`;
  Pain Frenzy's re-roll counted; two raids on a small escort valued together, it dies once);
  a human is asked with "Auto" (`GameState.impaler_hook`, `GameFlow._impaler_hook`); the AI's
  strike values use the same (`waves.impaler_value`; the crit was valued as one raid result
  before). Shared: `hit_and_run.crit_type_value`, `crit_roll_value`, `critical_hit_value`.
  Fixed on the way: a silenced weapon on a crippled ship now counts at half strength
  (`armament_threat_value`; it was full, so raids on crippled ships were over-valued).
- Dark Eldar crews (owner question, how strong): the AI's raid values now count Incubi's
  2D6-choose-one (both results against a crippled ship) and Pain Frenzy's re-roll for assault
  boats too (`dark_eldar.raid_value`, used by `waves.raid_squadron_value` and
  `impaler_effect_values`; only the Impaler counted the re-roll before, Incubi nowhere).
  Wych Cult (owner check): "the ship and its ordnance count all enemy capital ships as
  crippled for the purpose of Pain Frenzy and boarding modifiers" (capital ships only, not
  escorts): its Pain Frenzy re-rolls of raids, boarding crits and the Impaler's crit were
  built (`dark_eldar.pain_frenzy_applies`, in the engine and every AI value); the boarding
  modifier (+2 against a crippled ship) wasn't, now `boarding._get_ship_modifier(...,
  opponent_rules)` for both sides of a boarding action and the AI's `boarding_vp`.
  An Impaler hitting an undamaged Lunar, expected VP: none 23.3, Wych Cult 28.8, Incubi
  28.8, Haemonculi 22.4 (its forced Fire, 11.2, is worth less than a random crit, 18.7, so
  the AI takes the two raids; the coven's value is its +1 hit); crippled Lunar: Incubi 41.4.
  An assault boat raid: 7.6 / Wych 12.6 / Incubi 12.6. The owner's second Dark Eldar list,
  `owner_dark_eldar_tortures_1000.json` (1000, valid): a Torture with launch bays, Incubi and
  the Dread Archon + 2 re-rolls, a Torture with the Impaler bay, a Wych Cult and a Dracon, 3
  torpedo Raiders, 4 Impaler Corsairs (owner: one Raider dropped and the Dracon added, from
  1015). The first Dark Eldar fleet now has 4 Corsairs and 7 torpedo Raiders (4 + 3) instead of
  6 Corsairs (owner; same 990, and four 2-hit escorts a squadron as core p.58 says).
  "-1 to enemy raids" rules in the booklet (owner question): Space Marines (and Chaos Space
  Marine crews, which use their rules), Mega Armoured Boarding Parties, Incubi, every Tyranid
  ship, all in the engine, and Mucous Membrane (Tyranid biomorph, built since: assault boats,
  Impalers included, a further -1 to raids against it (`hit_and_run.ASSAULT_BOAT_RAID` tag on
  their raids; teleport values pass `assault_boat=False`), bombers one attack fewer
  (Fighta-Bommerz keep their minimum of one, reading), torpedoes count its Armour +1, max 6+;
  the AI's bomber, torpedo and raid values see it, not yet the wave planner's split;
  `tests/test_mucous_wych.py`); not yet: the Infested
  Space Station (unplayable), Deathskulls (+1 or -1 to raids they suffer; clan not built);
  XR's Aspect Warriors -1 isn't MMS's, so not applied.
- Haemonculi Coven in boarding (found missing, now built): a critical hit a Dark Eldar ship
  with Haemonculi inflicts via a boarding action is a Fire, no crit-type roll
  (`boarding._haemonculi_fire`; reading: any Haemonculi ship among the boarders); the
  Impaler half was already built. Fixed on the way: `combat.add_fire_crits` added the Fire
  twice when the caller's ship copy shared its crit list with the stored ship.
- Fire crits valued exactly (owner question, To do 30): `ai_hazards.fire_burn_dist` follows
  the burn over the end phases left (`FIRE_HORIZON` 4, judgement, cut by the turn limit):
  damage control's D6 a remaining hit (halved touching a blast marker in the first one, +4
  at the forges, a Big Mek's die, 4+ for Necrons / Mad Meks) puts fires out first, each fire
  still burning deals a hit past any reactive hull / exo-plating save and costs a die next
  time; `fire_value` = the burn with the new fire less without, as hull hits
  (`hull_hits_vp`), so a fire is worth more on a damaged or already burning ship. Used for
  every Fire crit (`hit_and_run.crit_type_value`: Impaler, raids, boarding values) and for
  putting one out (`repair_value`; it was a flat 0.5 / 1.5 hits). E.g. the Haemonculi
  Impaler Fire: 8.7 VP on an undamaged Lunar, 47.1 on a crippled one (the best option
  there). Not counted: the crit check each point of fire damage takes. The owner's third
  Dark Eldar list, `owner_dark_eldar_succubi_990.json` (990, valid): the Dread Archon on a
  launch-bay Torture, two Impaler Succubi with Wych Cults, 6 torpedo and 3 gun Raiders.
- The AI and Dark Eldar movement / torpedoes (owner questions): the turning distance is one
  rule, `movement.turn_distance(ship, order)` (Burn Retros, low orbit, Dark Eldar none; Necron
  AAF 20cm; Quest +5; Extra Discharge Vents -5), used by the engine, the move dialogs, the
  flee planner and every AI planner incl. the expert search (`SimShip.turn_dist`); before,
  the AI's candidates gave Dark Eldar capital ships 10cm before turning. Ships with no
  minimum move also get 25% / 50% moves in the candidate grid. Orders passed automatically
  (`ai_player.auto_pass`: Dark Eldar Come to New Heading, Orks' All Ahead Full) count at a
  pass chance of 1 in `_order_value` / `_ctnh_gain`, and Come to New Heading's cost halves
  only batteries and lances (s.7), never torpedoes or bays. Torpedo loads by expected VP
  (`AIPlayer._torpedo_kind_by_value`, among `ordnance.torpedo_kind_options` when no
  once-a-game / guided / short burn load is chosen): standard (plasma re-rolls) by hull hits,
  boarding a raid a hit (Chaos too; off with hit-and-run), leech a Thrusters Damaged a hit
  (half a hit, judgement, no damage); plasma wins against ordinary targets (5/9 against 5+,
  a hit worth more than a raid), boarding / leech where raids or crits are worth more.
- Shadowfield tracking marks can be turned off (owner): `GameState.rule_tracking_marks`
  (on by default, the booklet rule), a checkbox in the setup wizard's Optional Rules (not part
  of "All advanced rules") and in the in-game Advanced settings (turning it off clears marks
  already placed); off, `dark_eldar.add_tracking_mark` places none, so a shadowfield always
  saves on 2+; the AI's shadowfield values read the same marks, so they follow it
  (`tests/test_dark_eldar_rules.py`).
- Dark Eldar not yet: the Mimic Engine, the Tormentor Spire, Superstructure Damaged's turn
  roll, Only the Strong May Lead. AI value gaps (found pricing the crews for the owner):
  `ai_hazards.boarding_vp` values a boarding crit at a flat hit, so Pain Frenzy's crit
  re-roll and the Haemonculi Fire aren't in it; enemy raids on a Dark Eldar ship are worth
  0 to the AI (control circuit, graviton harness, bladevanes and ordnance-only armament
  results value nothing in `raid_result_value`), so the Incubi's -1 to enemy raids isn't
  priced either. Both are owner must-fixes in To do 33.
- Next (owner order): Tyranids (To do 19; playable now, slices 1-3 built, gaps listed there), then the other owner fleets' gaps (Tau Protector
  done: `owner_tau_protector_980.json`; Orks done: `owner_orks_980.json`; Necrons done:
  `owner_necrons_1000.json` and `owner_necrons_war_1000.json` (the owner's coin for the War
  refit, both saved); Eldar next; To do 25).
- Necron gaps built (`tests/test_necron_dynasty.py`): the Harvest and Dynasty fleet lists
  (`fleet_list_data_other.NEC_LISTS`: Monuments only in Harvest, Necron Lords, the Lord's
  vessel upgrades, Crypteks and Shroud refits only in Dynasty via `list_options`; tombship /
  grand harvest ratios, escorts 0-12 each, at least one capital ship, `min_capital`);
  `booklet_options.necron_options`: the Shroud's free Dynasty refits (War +2 hits +1 turret for
  the veil, Khopesh lightning arc L/R + whip, Cartouche arc FP8 + whip, both whips one FP2,
  each removing the nebuloscope pylons), the Lord's vessel's Bloodswarm Nanoscarabs (+1 to its
  portal raids, `hit_and_run._RAID_ATTACK_BONUS`), Reciprocating Tesla Pylons (offered, not
  modelled yet) and Nightmare Field (tombship / grand harvest ship; the Sepulchre's comes
  free), Crypteks (+1 Ld, 0-2, re-roll +15); the nightmare field in play
  (`combat.resolve_nightmare_field`, `actions.fire_nightmare_field`, the Fire dialog, the AI's
  `_nightmare_target`: P(fail) x the unit's points; enemy attack craft and boarding torpedoes
  within 20cm die on 4+; a failed Ld test: -1 Ld and no orders, Brace included, until after
  the end of its next turn, `necrons.strike_with_nightmare` / `end_of_turn_nightmare` through
  `scenarios.orders_forbidden`; readings: no line of sight or target priority, the target's
  own Ld, no Monument damaged); the negative energy veil (`negative_energy_veil` from the notes:
  no Enemy Contacts from it, `necrons.enemy_contacts` in `do_command_check`; not detected by
  mines; while conserving power, fired on only after a passed target priority test,
  `veil_hidden` in the Fire dialog and the AI's `_veil_filter`, and never the forced closest
  target) and nebuloscope pylons (+1 more Enemy Contacts for the fleet, `nebuloscope_bonus`).
  AI fixes found by the games: the AI's hit estimates now count reactive hull and bonded
  exo-plating saves (`ai_hazards.hull_save_factor` in `mount_hits`) and a veiled ship's target
  priority test, and `disengage_gain` scores by damage, not power conservation (conserving
  Necrons phased out at once). Still open: the Necron AI phases small ships out early (an
  undamaged Shroud leaves on turn 2-3 against a full enemy fleet; one-turn horizon), Tesla
  Pylons, the Harvest Monument's "largest capital ship" placement (To do 29).
- Ork gaps built (`src/orks.py`, `tests/test_ork_options.py`): the Kustom force field option
  (`booklet_options.ork_profile_options`, from "Kustom force field +Npts": -1 shield, +D3
  shields rolled at the start of each game turn, reading: rolled up front rather than "when
  first attacked", `roll_force_fields` from `TurnController.begin_phase` / `AATurn`,
  `Ship.effective_shields`); the Onslaught's free zzapp gun (gunz to FP2, a 30cm FP1 front
  zzapp gun; the squadron-must-match rule isn't checked); looted vessels: an Ork list's
  reserves (`looted_reserves`) become looted when the fleet is saved (`orks.loot` from
  `FleetBuilderWindow._save_fleet`: Ork Leadership table, orders, boarding and turrets
  (`ere_we_go`, `ork_crew`, `ork_turrets`), lances to zzapp gunz, attack craft to fighta-
  bommerz / assault boats, a nova cannon to a killkannon 30cm FP6 front), cruisers only and
  no nova cannon upgrades (`looted_errors`), and a failed command check costs a looted ship
  a hit on 1-3 (`own_goal` in `do_command_check`; not yet the other Leadership tests:
  disengage, navigation). Not yet: soopa boostas, grabbin' klaws, magno-tracktor beams,
  the other ships' zzapp gunz swaps.
- Tau Tracking Systems (found while building To do 28's buff placement; they had engine
  code but no ship carried the rule): `booklet_ships` reads them from the notes
  (`tracking_systems_<range>`: Messenger 10cm, Custodian and Orbital City 20cm; the Hero and
  Protector say "no tracking systems"); a Tau vessel within range (itself included) re-rolls
  missed turret dice (`ordnance.turret_reroll` / `turret_kill_p` in `turret_dice`, the AI's
  torpedo and craft turret estimates with the game state) and ignores the beyond-30cm gunnery
  shift (`combat._has_tracking_support`, now Tau vessels only, as the rule says); the owner's
  Tau Merchant (Messenger) and Protector (Custodian) fleet files rebuilt with it
  (`tests/test_tau_tracking.py`). Not yet: the wave planner's turret maths
  (`waves.wave_split_value`) with the re-roll.
- Tau Protector gaps built: the Emissary's Bor'kan / Sa'cea configurations (ion cannons for
  the hooks, free; a prow gravitic launcher for the launch bays, free) and Deflector +10
  (`booklet_options.tau_profile_options`); the mine swap now offered to the Emissary (a light
  cruiser in the Tau list's Kor'or'vesh Cruisers category, update 58 ruling; never with the
  launcher swap, `group:emissary_bays`); Deflectors as a rule (`deflector`, from "6+D" armour
  or "Has a Deflector"): a prow critical takes the front back to the side Armour until
  repaired (`Ship.armor_prow_value`) (`tests/test_tau_emissary.py`). Not yet: the Hero's and
  Protector's own swaps (ion cannons for railguns; the Protector's prow railguns to FP4 for
  45cm ion cannons), the Explorer's Bor'kan configuration.

Earlier work: To do 17 / 18 shooting actions and replay (the AI's attacks and every human
shooting dialog as recorded actions; `src/fire_volley.py`), the ordnance phase (AI
and every human dialog) and the end phase's decisions as recorded actions, so every phase
replays from the record. Owner report (To do 32): the setup wizard's start buttons, the
fleet builder's Save / Validate and the ship Edit dialog's lower options were cut off the
screen; fixed (scrolling dialogs, buttons always shown, options under headings, live fleet
check), builder-saved fleets crashing the game, Auto-Place breaking squadrons, the missing
Mechanicus refits; six of the owner's fleets built as files. Next: alternate activation's
per-unit phases; owner since: "try to get the other factions playable", so next is
To do 19 (Dark Eldar first; plan in To do 19), then Tyranids, then the gaps in the owner's
other fleets (see docs/HANDOFF.md "Status at a glance"). Booklet installed: zip 14 (CHANGES.md update 60; rules files: Dark Eldar 08, Eldar 09,
Necrons 10, Orks 11, Tau 12, Tyranids 13, scenarios 14, campaigns 15, appendices 16-22; the
owner's sign-off answers are `bfgxr/notes/OWNER_SIGNOFF_answers.md`). Tests: 1600 pass (BFG_SWEEP=1 adds ~4,650 ordnance cases); all
GUI checks pass (`xvfb-run -a /usr/bin/python3.12 tools/gui_checks/<x>.py`; spectator checks
take a difficulty, e.g. `gui_spectator_demo.py normal` / `expert`; scenarios
`gui_spectator_scenario.py igougo|aa <scenario> [subplots]`). After every new export, diff the
built catalog (dump every entry's stats, rules, weapons and options before and after): notes
text is matched in code, and a reworded note silently drops an option.

Finished (humans and the AI, IGOUGO and alternate activation; each section above and To do
item below says how):
- Every core rules section the engine plays; all optional rules (boarding, ramming, teleports,
  hit-and-run, s.40 celestial effects, Remastered blast markers / suppression / escort VP).
- Ten factions playable: Imperial Navy, Chaos, Mechanicus, Space Marines (+ Venerable Strike
  Cruisers), Inquisition / Grey Knights, Orks, Tau (+ Demiurg), Rogue Traders, Eldar MMS v2.0
  (all 24 ships), Necrons (the six mobile ships); fleet lists for every faction now.
- Commanders (fleet, secondary, named), refits, gifts, marks, kustoms, bought torpedo types,
  mines, torpedo bombers.
- 31 booklet scenarios (To do 7): the nine matched-play ones, the introductory, raid and battle
  scenarios, low orbit with Exterminatus! and Planetary Assault, the campaign set pieces (The
  Defence of Pelucidar, Macharia's End, Craftworld Assault) and variants (The Gauntlet,
  Parol's Bait, Daemon Blockade); sub-plots incl. the faction ones (not the Decoy).
- Alternate activation (all three order systems, To do 13); the expected-VP AI (easy, normal,
  expert search); "Auto (best)" on every player prompt; To do 2, 3 and 6.

Built since the code review (`docs/CODE_REVIEW_PLAN.md`; details in To do 15-18):
- To do 15 done; To do 16 done (headless runner `--no-display`, ~650 games / hour on 4 cores).
- To do 17: seeded, recorded dice and AI randomness, decision events, complete snapshots;
  AI-vs-AI games replay exactly; movement phases replay from recorded actions.
- To do 18 in progress: `prompts.py` (every question through `ctx.prompt`), `game_flow.py`
  (the turn flow, `GamePanel(GameFlow)`), `headless_game.py`, `tk_compat.py`, `actions.py`
  (movement actions), `replay.py`, `tools/refactor_check.sh`.
- Owner ruling s.11 / s.13 (combined macrobattery rolls, markers at once, mixing gunnery
  types) built.
Still true from the review:
- Game modes: hot seat, player vs AI (the AI is always Player 2), AI vs AI spectator (each
  player its own difficulty, `GameState.difficulty_for`). Two sides only (`3 - player` ~100 times); team play is To do 22.
- Structure (To do 18's remaining items): string-keyed ladders, ~170 special-rule tag checks,
  `ai_player.py` ~4,700 lines, some rules in UI files, judgement weights scattered. The
  "0.35 per firepower point" rule of thumb is gone (To do 30, see there).
- Language (To do 20): a full port to Rust in its own branch, Python retired once it replays
  every golden game, is the third-last task, online play (To do 23) the second last; the ML-trained AI (To do 12, then
  1) is the last, on the faster engine.

Next: the "Agreed order" at the top of the To do list.

