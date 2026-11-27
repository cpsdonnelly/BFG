# AI: how it decides (expected VP)

Moved out of CLAUDE.md (owner: keep CLAUDE.md small, it is read every session). The plain-language design is docs/AI_DESIGN.md; this is the detailed reference.

### AI: how it decides (expected VP)

The whole AI, current and planned, in plain language: `docs/AI_DESIGN.md` (keep it in step).

Fleet strategy (owner doctrine): the AI plays its matchup, judging its fleet and each ship
against the enemy's, on average and ship vs ship. Owner: "do not take these as hard rules, it
depends on the matchup": every one should come out of the expected-VP values, not a fixed rule.
- Firepower by range bracket (0-15 Ork Heavy Gunz, 15-30, 30-45, 45-60 Chaos long guns,
  60-150 artillery such as the Nova Cannon): fight in the bracket where our guns beat theirs
  (e.g. a Tau Merchant out-guns a Lunar at 30-45cm, not at 0-30cm). The matchup table is
  built (To do 8 f) and used by the range-band move goal (11 a).
- Speed (and turn angle) edge: out-moving the enemy, get out of its main fire arcs (e.g. into a
  Lunar's rear arc). Mostly covered by the rear-arc goal and exposure allowing the enemy a
  turn (8 g).
- Out-range and out-move it on average (Chaos): kite, holding the band where we can fire and it
  can't. Built, first form (`_kite_bonus`, 8 c).
- Gun-heavy broadside fleets (Imperium, e.g. Lunars, broadsides that don't overlap): keep both
  broadsides busy, cross the T. Built, first form (`_mount_coverage`, 8 b).
- Forward-firing ships with the best Armour in front (Tau Protector): show the prow only when
  the enemy is about to be in range. Planned: 8 d (its prerequisite 8 a, exposure by Armour
  facing, is built).
- Hit-point edge (Orks): boarding and ramming, only with those rules on: built (8 h).
- Teleport attacks, both launching them and being vulnerable to them (only with teleports and
  hit-and-run on). Built: its own teleports, positioning for them and defence against them
  (8 j); not yet choosing gunfire to open shields for a teleport.
- Air power, built: a carrier-heavy fleet goes after the enemy's carriers with its guns (air
  supremacy; ordnance at them is likely intercepted unless they are spread too thin or just
  launched); an out-carriered fleet protects its carriers and flies CAP / interception; a
  smaller air wing can still neuter a larger one, so enemy carriers threaten our strikes and
  we strike outside their umbrella; reactive intercept; co-ordinated bombers and missiles
  against the turret split (not against Orks). Details below ("Air power", "Strikes",
  "Co-ordinated strikes") and in To do 2.
- Ordnance, built: lead targets (closing easiest, abeam hardest, receding between; big
  bases easier), turning salvos come in on the weakest Armour facing, sooner beats later,
  friendly fire is negative VP; a disabled optional rule is never valued or attempted.

All AI choices are in expected VP (`ai_hazards.py`, `ai_rerolls.py`, `waves.py`, `AIPlayer` in
`ai_player.py`; the expert AI in `lookahead_ai.py`). Weights marked "judgement" are mine;
tuning them is on hold (owner: keep it in mind, but it is hard work, so leave it for now): re-roll bars 45 / 25 / 15 / 10 VP, half-weight flagship exposure, `PHASE_DISCOUNT` 0.85, `LATER_TURN_WEIGHT` 0.5,
`DODGE_WEIGHT` 0.5, `CRIT_HORIZON` 3 shooting phases, `RISK_TIEBREAK` 0.1, `MOVE_TURN_WEIGHTS` 40% straight / 15% per turn, `ANTICIPATED_STRIKE_WEIGHT`
0.5 (scaled by the air balance), `AIR_THREAT_WEIGHT` 0.5, `ENEMY_FIRE_AT_WAVE` 0.5,
`REACTIVE_CAP_WEIGHT` 0.5, `AIRBORNE_INTERCEPT_WEIGHT` 0.75, CAP free fighters 0.75, the
disengage and hulk models.

Optional rules (owner): when a rule is disabled (Advanced settings: `GameState.rule_*`, all
off by default: boarding, ramming, teleport, hit-and-run, fighting sunward, solar flares,
radiation bursts, Remastered turret suppression / spill-over), the AI neither values moves by
it nor attempts it. Audit: hit-and-run is respected (`_strike_option`, `waves.best_attack_mode`,
`ai_hazards`, and the craft types the AI launches); teleport attempts need `rule_teleport` and
`rule_hit_and_run` (`check_teleport_eligibility`); boarding (8 h) and teleport (8 j) terms
check their flags (`_boarding_reach`, `_consider_boarding`, `_teleport_reach`,
`_teleport_exposure`, `_teleport_given_up`) and ramming checks `rule_ramming`
(`_ram_candidate`); the wave planner and AI follow the turret suppression mode (XR / Remastered
p.82, `waves.wave_split_value`); of the s.40 effects the AI counts only Fighting Sunward's
shifts (through `get_column_shifts`), not flares / bursts (check their flags when it does).

Values:
- One hull-hit scale (owner, To do 33): `hits_vp` (the thresholds hits cross now and what
  they add to the chance the enemy's fire cripples / destroys the ship by the end of the
  game), `damage_vp` its Poisson count, `hull_hits_vp` the same for ordnance (no shields),
  `value_per_hit` one hit's worth. Ordnance never loses hits to shields (s.11 / s.15).
- `damage_vp` adds the threat removed (owner): a kill removes the target's next turn of fire
  (`ship_threat_vp`), a cripple halves it; and a kill may explode (`death_explosion_vp`,
  Catastrophic Damage 9-11 plasma / 12 warp, Mercury 3D6, escorts never), good near enemies,
  bad near our own ships.
- Air power (owner: carrier doctrine). `ship_threat_vp` (so every kill / cripple value)
  includes a carrier's bays (`bay_threat_vp`): its strike squadrons at a bomber squadron's
  value against its enemies, plus its fighters denying the enemy's strikes (one squadron
  each, up to the enemy's launch capacity), x `AIR_THREAT_WEIGHT` 0.5 (judgement). So a
  carrier-heavy fleet values the enemy's carriers more and its guns and focus go to them (air
  supremacy); ordnance at a carrier is already discounted by the CAP / intercept it can put up
  unless its bays are empty (`strike_timeline`). Out-carriered (`air_balance`), the CAP
  weight on enemy strikes not yet launched rises (`_anticipated_weight`: 0.5 x enemy / our
  launch capacity, kept to 0.25-0.9) and our carriers' moves pay for ending inside enemy
  strike reach (`_carrier_exposure`, weighted by the carrier's share of our launch capacity,
  doubled when the enemy has more) (`tests/test_ai_air_doctrine.py`).
- Sooner beats later (owner: "2 hits on the side within 2 turns are worth much more than 3 on
  the rear after a 4-turn loop"): `phase_weight(k)` = 0.85 per ordnance phase of delay, x 0.5
  from the next game turn (1, 0.85, 0.36, 0.31); strikes' `travel_discount` shares the factor.

Movement:
- Hazards along the move path (mines, torpedoes, attack craft, asteroids, warp rifts, dust,
  blast markers), each marker's threat by type (`marker_hits`): guided / seeking / Tau turn
  cones (`_torpedo_heading`, launcher's real Ld), boarding torpedoes turn freely within 45,
  Tau missiles 45 / 40cm (`torpedo_reach`) / 5/6 strength, the rest straight; contact = base + marker half width.
- Fleet focus (owner: focus fire, easier targets first): several focus targets
  (`fleet_focus_assignment`: each ship's guns where they add most VP given the others', no
  overkill), planned against with 0.3 x the arc score on the nearest enemy, minus half the hits
  the enemy could focus on the end position (`_exposure_penalty`, `position_exposure_hits`,
  on the Armour facing each enemy would hit, `mount_hits`, To do 8 a).
- The move score (`_arc_score`) counts in-arc batteries / lances / nova cannon and loaded
  torpedoes (they launch from the end position: full within one torpedo move, half within two).
- Candidates (To do 11 a): the even grid plus turn points, goals (guns to bear, range band,
  prow-on, rear arc, second target, escort support, Lock On next, boarding reach), a denser grid
  when crowded, hill-climbing of the best three, ships moving in support order; Easy picks by
  softmax (`_move_candidates`, `_refine_move`, `_coordinated_order`). The move score also has
  both broadsides busy (8 b), kiting (8 c), teleport reach / exposure (8 j) and boarding (8 h).
- Explosions (`explosion_position_vp`): keep out of the 3D6cm radius of ships likely to die; a
  ship of ours likely to die ends next to enemies.
- Special orders (To do 10, partly rebuilt): Burn Retros by expected VP
  (`_burn_retros_worth_it`); Lock On by value (`_lock_on_gain`, 10 a: the best straight move
  under Lock On with each battery / lance counted by what re-rolling its misses adds, 1 - p a
  die (`_arc_score(reroll_gain=True)`: +50% at 4+, +67% at 5+, +83% at 6+; it was a flat
  0.5), minus the best move that may turn, at the check's pass chance; the target is the one
  the move plans against; only guns in range after the move count); All Ahead Full by value
  (`_aaf_gain`, 10 b: the best straight move at full speed + the expected bonus, batteries and
  lances in range halved, never torpedoes or bays (s.7; it halved everything before), minus
  the best free move); Reload Ordnance by value (`_reload_value`, a reloaded salvo's hits now
  after turrets and re-rolls, `torpedo_salvo_hits`); Come to New Heading by value
  (`_ctnh_gain`, two-leg moves `_ctnh_moves`, guns only halved). The choice
  (`_pick_special_order`): every order's pass-weighted expected VP on one scale, the best
  taken (Burn Retros used to win whenever it beat its own cost, and Reload's value was
  compared unweighted); a spent ship with nothing better still reloads. One pass chance for
  every order and Brace (`AIPlayer._pass_chance`, `brace_value`), from the engine's own rule
  `movement.command_check_ld` (split out of `do_command_check`: Fleet Experience / Blood Bond,
  Under Fire (not Necrons), Slaanesh, sub-plots, Grot Riggers, Enemy Contacts with the Cobra's
  sensors / nebuloscope / veiled Shrouds, Tyranid synapse Ld for Brace, automatic passes,
  Siren's Summon), 0 when orders can't be tried (a failed check this turn, a scenario, a
  Tyranid on instinct); before, five hand-written copies each missed some of these. A
  commander re-roll is counted (`ai_rerolls.with_reroll`, To do 33). Check
  order (10 c): `_plan_orders` values every ship's order at the start of the phase
  (`_order_value`: VP gain, `_pass_chance`) and
  `_choose_special_order` skips an order when p x g < (1 - p) x the later orders' expected
  gain (a failed check ends the later ones, s.2). Escorts screen the commander's ship for
  massed turrets (s.29, `_screen_bonus`) only while enemy torpedoes, torpedo bombers, bombers,
  assault boats or mines can reach it (owner: never against fighters alone).
- Voluntary disengaging (s.37, `_consider_disengage`, `ai_hazards.disengage_gain`): P(pass) x
  (risk avoided over the enemy's next turn - extra VP conceded) - its guns' value. Risk from
  `incoming_hits`: per enemy mount (a port broadside bears on ships on its left, starboard on its
  right, other mounts within their arc after one turn of the ship's own turn angle), the enemy
  focusing fire (`enemy_fire_plan`, owner), a Poisson count; destroyed = full value (75% more if
  already crippled), newly crippled 25%; leaving concedes 10%. With a turn limit staying is
  valued by its certainty equivalent (play for the win, To do 2), as are the guns given up.
  One-turn horizon; escort squadrons are special-cased only under the Remastered escort VP
  option.

Shooting:
- Targets by marginal expected VP (no overkill), target priority test obeyed; battery values with
  column shifts (`combat.expected_hits(..., gs)`); weapons knocked out by armament crits never
  fire (`combat.weapon_disabled_by_crit`). Brace is priced (`ai_player.brace_value`, To do 11 c):
  4+ saves on the expected hull hits from this attack and enemies still to fire (Poisson, the
  loss of k hits = destroyed / newly crippled value incl. its next turn of fire, plus a little a
  hit) against half its fire to the end of its next turn (`ship_threat_vp`, doubled in its own
  turn before it fires), at the command check's odds (Under Fire, Enemy Contacts); both choices
  by certainty equivalent, so ahead near the end it braces more readily, behind less. The
  commander's ship braces earlier because it is worth double while it has re-rolls (no fixed
  bias). It also pays for the order it forbids next turn (`next_order_vp`) and counts a
  commander re-roll on a failed brace (To do 33). Not modelled: the engine doesn't stop a braced
  ship firing inside an asteroid field (s.39), so neither does the AI.
- Fire order: each ship fires batteries, then other weapons, then lances (11 d); boarded ships
  don't fire or launch; the Armageddon Gun and Kustom Kannon are fired by value.
- Squadron volleys (s.8, `_squadron_volleys`): one `plan_squadron_volley` per squadron when it
  rolls at least as many dice as firing separately, at the best target that is every
  contributor's nearest valid target; aspect by `best_aspect_choice`. Batteries only. Not yet:
  Ork random-firepower batteries in volleys, a volley needing a target priority test.
- Hulks (`_hulk_shot`, `hulk_shot_vp`): shot when the closest target in arc and P(a hit) x the
  re-rolled catastrophic damage among enemy ships beats the best ship shot. Not counted: Holding
  the Field hulk points, hulks that aren't the closest target.
- Ships shoot incoming ordnance when worth more than their best ship shot.
- Nova Cannon (`_fire_nova_cannon`): the enemy in arc and 30-150cm where its expected hits
  (`nova_expected_hits`, shields still stop them) add most VP given this phase's fire; never
  at a target with one of our ships within `NOVA_FRIEND_CLEARANCE` 12cm (judgement).

Ordnance:
- Torpedo targets (`_best_torp_target`) by expected VP after turrets and path survival, counting
  the guns' work and the phase's other launches (`_ord_committed`). Lanes (`_torp_lane`): the
  heading worth most within the hit window; owner: friendly fire is negative VP (a salvo attacks
  every ship it touches and carries on weakened, s.15; friends in base contact with the launcher
  are passed through, boarding torpedoes ignore friends); path hazards across the marker's full
  width (`torpedo_path_survival`). Holds fire when the best is a net loss.
- Leading straight salvos (owner, `_torp_lead_plan`): the target's next move is sampled
  (`enemy_move_samples`: half to full speed, one turn after its turning distance, dodges by Burn
  Retros / All Ahead Full); the salvo moves now, waits while the enemy moves (a ship moving into
  it is attacked), moves again; the enemy dodges with `DODGE_WEIGHT` when a normal move or an
  order at its Ld odds escapes (a salvo parked within its minimum move ahead can only be escaped
  by an order); a catch on the second turn counts at `LATER_TURN_WEIGHT`. Owner: closing
  easiest, abeam hardest, receding between (speed-20 Ld 8 cruiser at 40cm: 0.64 / 0.34 / 0.32);
  large bases easier to hit (owner); a closing battleship can't sidestep. Beyond two moves'
  reach the intercept aim is kept.
- Turning salvos that roll against Armour (owner; Tau missiles, Ld-guided, boarding):
  `approach_plan` searches the launch heading and a 45-degree turn per later move, four moves
  deep, for the weakest facing they can reach (facing from the contact point; a ship that moves
  onto the salvo takes it on its leading side), weighted by `phase_weight`, Ld odds per guided
  turn, Tau strength loss, boarding at half; recorded on the salvo (`torp_target_id`) and
  followed in flight (`salvo_approach`, `ordnance_movement._ai_salvo_turn`,
  `_steer_guided_missile`). E.g. an Ork 6+/5+/4+ cruiser abeam: round to the 4+ rear (18.9 VP vs
  9.6 for the 5+ side). Not yet: the target turning to show its strongest facing.
- The AI fires its one vortex / melta / seeking salvo at the first capital ship target, guides
  torpedoes freely, short burn beyond 30cm, no barrage bombs until planetary assaults exist.
- Carriers: CAP vs strike fleet-wide (`_plan_fleet_defence`): every carrier starts all-strike;
  threat slots (a salvo or mine = one fighter, a wave one per squadron lead first,
  `intercept_gain`; CAP full, free fighters 0.75; enemy strikes not launched yet, CAP only,
  `_anticipated_strike_slots`; existing CAP covers its ship's threats first) go to the carriers
  with the weakest strike per squadron, each taking the exact count that maximises strike +
  gains (`_best_defence_count`). Multi-role carriers plan alone.
- Strikes (`_strike_option`): every enemy within 3 moves, the planner's fighter / bomber wave
  (`waves.plan_wave_against`) or all assault boats (owner idea: by expected VP,
  `waves.raid_squadron_value`), valued when they land (`strike_timeline`: arrival phase,
  enemy guns on the way, reactive CAP and reactive intercept by other enemy carriers, the
  raid's repair window) along the route
  (`best_route`: up to two waypoints round obstacles, AI craft fly them,
  `ordnance.craft_target_point`); craft in flight re-targeted fleet-wide the same way
  (`plan_strike_targets`); multi-role attack mode by `waves.best_attack_mode`.
- Co-ordinated strikes (owner, e.g. Tau Protector fleets with missiles and attack craft): turrets
  fire at craft or at torpedoes / mines in a phase, not both (s.28), so a salvo and a bomber
  wave reaching one ship in the same phase gain the smaller of the two turret savings
  (`ai_hazards.turret_split_gain`; bombers' attacks are still reduced by turrets; none
  against Ork turrets, which fire at everything). The AI records this phase's planned
  arrivals (`AIPlayer._ord_arrivals`: torpedo phase 0 within one torpedo move, else 1; a wave's
  `strike_timeline` phase) and both sides score the gain: the strike planner against
  torpedoes due at its target (`_turret_split_bonus`), torpedo targeting against waves due
  there, planned or already flying (`_craft_due`) (`tests/test_ai_air_doctrine.py`). Not yet:
  assault boats and mines in the split, choosing a later launch to match timings.
- CAP against torpedoes (owner): a CAP fighter intercepting a salvo removes all of it
  (s.19 both markers removed, s.26), but only one squadron of a wave. So a salvo's value
  counts the CAP left when it arrives (`_torp_cap_factor`: each craft squadron of ours due
  there in that phase, and each salvo planned there before it, uses up one CAP squadron
  unless that fighter saves, exact binomial; the enemy's later CAP isn't counted); the AI
  launches its bays fleet-wide before its torpedoes (`run_ordnance_phase`, `only=`), so a
  Dictator's bombers go ahead of its own salvo; a wave is credited with the torpedoes it
  unlocks (`_cap_strip_bonus` in `_strike_option`). The moving player chooses which of its
  ordnance meets a ship's CAP first (it moves markers one at a time): craft first by
  default, or torpedoes first, a small salvo drawing the CAP off a wave
  (`OrdnanceMovementMixin._torps_first_vs_cap`; the AI and "Auto" by
  `formations.contact_order_values`; a human is asked) (`tests/test_cap_vs_torpedoes.py`).
  Not yet: launching fighters purely to strip CAP when no bomber strike is planned, the
  enemy's reactive CAP before the salvo lands.
- Holding bays (`_hold_bays`): out of reach (nothing within three moves of the fastest craft)
  hold; within reach hold when (1 - Reload Ordnance odds) x next turn's launch or CAP value >
  launching now (rarely, with fair Ld).
- Fighters fleet-wide by VP saved; turret split by expected hits saved.

Re-rolls and choices: importance-based re-rolls (`ai_rerolls.should_reroll`); Wings of Fury raid
re-rolls and the "Auto (best)" prompts (see above).

Expert AI (`lookahead_ai`): minimax over a deterministic sim using the same terms (battery
`BATTERY_HITS_PER_FP` scaled by Armour, shields by `past_shields`, lances 0.5, focus without overkill, torpedoes once, explosions at their odds,
shields each turn, the real table, its own ordnance in flight); leaf = VP banked + next turn's expected swing at
`LATER_TURN_WEIGHT`; with a turn limit, the chance of winning from that margin
(`win_score`, To do 2); root moves are the normal AI's candidates, best first, at most
`ROOT_MOVES` 12, plus every strategy's first move (To do 34, each followed in the sim for
`PLAN_TURNS` 2), and pay the path-hazard cost (To do 11 b); lances valued by their hit roll;
cut by `NODE_BUDGET_FOR` (deterministic).

