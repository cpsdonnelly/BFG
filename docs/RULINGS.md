# Owner rulings and rule-area notes

Moved out of CLAUDE.md (owner: keep CLAUDE.md small, it is read every session). Read the section for the rules area you are changing.

### Owner rulings

- **Learned evaluation and weight tuning (To do 12 and 1), owner:** don't start either until
  the owner says so. When they start, the experimental ML-driven AI stays separate: it never
  replaces the current AI (its own AI class / difficulty option, the existing normal and
  expert AIs and their weights left as they are).
- **Necron Deadly Awakening is for capital ships only** (update 59): only capital ships conserve
  power, awaken and score double; escorts act normally at normal VP, but an unsaved hit or raid
  on any Necron vessel, escorts included, raises the alert level.
- **Light cruisers in "per N cruisers" limits** (update 58): a light cruiser counts as a cruiser
  when its fleet list places it in the Cruisers category (e.g. the Corsair Aurora / Solaris, the
  Dark Eldar Succubus); one in a separate light cruiser class / list doesn't.
- **Tyranid weapons** (update 58): massive claws and feeder tendrils use Strength, not FP; the
  Proteus hive ship is a Defence (it moves as a battleship).
- **Leadership is rolled at game start** (Appendix 4, faction column; escort squadrons roll once
  and share it). Booklet ships carry `leadership_table` and Ld 0 until then.
- **Upgrades:** the old hand-written upgrades were removed. Booklet refits, options and fleet
  commanders are prose in each ship's notes and get added one at a time.
- **Towed ships** (Warden, Orca, Dhow) have no warp engines and need gravitic hooks in the fleet.
  This matters only for fleet building; gravitic hooks have no effect in battle.
- **Ship names:** the game's "Hero Class Cruiser" is the booklet's Hero Starship, and the
  "Messenger" is the booklet's Messenger Starship, an escort (the game wrongly lists it as a
  light cruiser).
- **Any damage can cause a critical hit (owner):** every point of damage goes through
  `combat.apply_damage`, which rolls the critical check (a 6, or the weapon's own lower
  number; small escorts take +1 damage instead): gunnery, lances, torpedoes, bombers, mines,
  ramming, the nova cannon, explosions, the Impaler's bladed prow, and (fixed this session)
  asteroid impacts, gas / dust cloud damage, fire damage in the end phase and an Ork looted
  ship's own goal (they used to take hits off directly). The exceptions follow their own
  rules: boarding actions, hit-and-run raids (assault boats, boarding torpedoes, teleports),
  a crit's own extra damage, Tyranid feeder tendrils (no normal crits), and Extended Duty's
  damage before the game. The unused old `terrain_effects.TabletopEffects` (a solar flare that
  logged its crit without applying it) was removed; `celestial.py` is the live one.
- **Escorts never become hulks:** they are too small. An escort reduced to 0 by anything,
  boarding included, is replaced by a blast marker (s.34). The "drifting hulk" result for
  ships boarded to 0 (s.32) applies to capital ships.
- **Victory points never double-count:** an escort squadron is scored once, as one unit.
- **Boarding and catastrophic damage (s.32):** a ship reduced to 0 by boarding damage becomes
  a drifting hulk with no catastrophic roll, but its boarding crit is still rolled. If that crit
  deals extra damage (Engine Room, Hull Breach, Bulkhead Collapse), the ship rolls on the
  Catastrophic Damage table. A crit with no extra damage leaves it a hulk.
- **Blast markers and speed (s.11):** the 5cm reduction takes effect at the point the ship
  touches a blast marker. If that leaves it with no movement (0 or less), it stops where it
  first touches the marker; otherwise it may carry on with what remains. This applies to All
  Ahead Full too.
- **Order of speed modifiers:** crippled (-5cm) first, then Burn Retros (halve), then blast
  markers (-5cm). A speed-25 crippled ship on Burn Retros touching a blast marker:
  (25 - 5) / 2 - 5 = 5cm.
- **Escort squadron off the table (s.8):** when an escort in a squadron moves off the table,
  the rest of the squadron takes a disengage test right away, and again at the end of each of
  its later movement phases. One test for the whole squadron, using the Leadership modifiers of
  its best-placed member (highest resulting Ld). A failed test has the normal effect for that
  turn; otherwise the squadron acts normally.
- **Movement is never rounded:** halving a speed gives an exact half (25cm -> 12.5cm), both
  for Burn Retros and for the half-speed minimum. Show distances as exact values too.
- **Ordnance attacks the first valid target it contacts** (now s.15). Friendly ships are
  valid targets for standard torpedoes but not for boarding torpedoes (now in s.16's torpedo
  types).
- **Cruisers are cruisers:** grand cruisers, battlecruisers, heavy and light cruisers all move
  as cruisers (10cm before turning; battleships 15cm, escorts any point).

- **Hulks drift only in their owner's movement phase** (export 8: Appendix 5 now says "in
  each of their subsequent movement phases"). A burning hulk's re-roll happens then too
  (Appendix 5 still says "each movement phase" for that). `resolve_hulk_drift(gs, dice, player=...)`.
- **"+D6cm on All Ahead Full" sources stack.** The Grey Knights Battle Barge's Sigils of
  Quickening (`sigils_of_quickening`) already give +1D6; a campaign upgrade such as Improved
  Thrusters would add another (`aaf_bonus_dice`).

- **Damaging a hulk:** a hulk that takes at least one point of damage rolls on the
  Catastrophic Damage table again. Standard torpedoes attack hulks (boarding torps pass over).
- **Splitting Heavy Gunz** between a target within 15cm and one further away shares the worse
  (15cm+) firepower, like target aspects with squadrons: a worse value may be used against an
  easier target, never a better one against a harder target.
- **"5+ / 4+R" armour** (Tau Explorer) is 5+ everywhere except the rear quadrant, 4+.
  Three-value armour (Ork cruisers 6+/5+/4+) is front / abeam / rear (`Ship.armor_vs`).
- **Random Ork firepower/strength is rolled when used:** direct fire when the weapon fires,
  after the target is chosen and has had its chance to brace; ordnance at launch, after the
  salvo is aimed (owner: "aimed first and then rolled"; the launch dialogs check the heading,
  then roll; the AI aims with the average and rolls as it launches). Once on the table a
  salvo's rolled strength is known and used (`ai_hazards.marker_hits`).
  `combat.weapon_fire_pool` fixes a weapon's pool on its first shot of the turn.

- **Blast markers and a ship's own shooting (owner ruling; s.11, s.13):** blast markers come
  into effect immediately, so they can affect later shooting in the same turn (lances and nova
  cannon never). But every macrobattery a ship fires at one target totals its firepower into
  ONE Gunnery table roll (s.13): no firing some, seeing the result and adding the rest at the
  same target; the only way to hold batteries back is to fire them at another target, which
  normally needs a target priority test (so the AI should weigh passing one to send spare
  batteries elsewhere when the total would overkill). Earlier / later shots happen only when
  a ship splits its batteries between targets, or has different gunnery weapon types (a
  strike cruiser's macrobatteries and bombardment cannon). For the second, s.13's Mixing
  Different Gunnery Weapons lets the player fire them simultaneously (all to-hit rolls first,
  so none takes column shifts from the others' markers, but all are committed even if the
  first kills the target); otherwise they fire in sequence and earlier markers shift later
  ones: a choice in the Fire dialog, and the AI uses it when committing everything is worth
  it. Siege Cannons: macrobatteries and bombardment cannons in one lookup, the macrobatteries
  making the dice beyond the cannons' firepower (so shifts and table losses fall on them; with
  fewer dice than the cannons' firepower, the cannons make them all); macrobatteries alone take
  an extra right shift (built so). Batteries before lances because lance hits absorbed by
  shields also place markers, which would shift gunnery fired after; battery markers never
  affect lances. Squadrons: one combined volley is one simultaneous attack (no shifts between
  its shares); a later separate volley is affected. Markers in the way: the line of fire,
  including markers in contact with either ship's base; Modern / Remastered add base contact
  as s.11 says (built so). Built: `combat.gunnery_kind` (macrobatteries vs bombardment
  cannons, Kustom Kannon, Eldar / lightning-arc batteries), `combined_battery` (each weapon
  reduced by its own modifiers, as capital ships halve individually in a squadron, then
  totalled; reading) and `resolve_battery_group` (one roll at a ship or as a squadron attack);
  the AI plans all its batteries' targets first (`_pick_target`'s overkill check) and fires
  one attack per target and type (`AIPlayer._fire_battery_groups`), re-picking for a group
  whose target an earlier attack destroyed, each attack seeing the markers in play, or all of
  a target's types together when the first type alone isn't expected to destroy it
  (judgement); the Fire dialog fires the same groups (`_fire_battery_groups`; a group's hits
  are applied before the next rolls) and offers "Fire different gunnery weapons together"
  for a ship with two gunnery types (`tests/test_combined_batteries.py`,
  `tools/gui_checks/battery_combine_check.py`). Not yet: the AI weighing a target priority
  test to send spare batteries elsewhere beyond what `_pick_target` already does.
- **Tactical Reserves covers macrobatteries only, not lances** (battle barges lose 25% of
  macrobattery firepower on All Ahead Full or Burn Retros; lances still halve).
- **Defence turrets (s.28; owner ruling this session):** a ship's turrets defend against
  attack craft or against torpedoes and mines in one phase, not both, and vice versa
  (`ordnance.turrets_blocked`, `mark_turrets_used`, reset every phase in
  `TurnController.begin_phase`). The split blocks shoot-down rolls only: bombers' attacks are
  still reduced by turrets after they fired at torpedoes / mines. A ship touched by both kinds
  in one phase chooses (`ordnance.choose_turret_target`: AI by expected hits saved, a human via
  `GameState.turret_choice_hook`). Orks (`ork_turrets`) hit on 5+ and fire at everything
  (Xenos, Turret Defences). The kustom Extra Turrets is +2 Turrets (max 6) on ordinary ships
  (built); "hit on 4+" is the Ork Space Hulk's version (not playable yet).
- **Bombers always attack the lowest Armour value** (a rule, s.20; the owner asked for it to be
  applied everywhere), whatever side they come from:
  the engine (`ordnance.resolve_bomber_attack`), the wave planner / "Best split"
  (`waves.wave_plan_inputs`), bomber vs assault boat values (`waves.bomber_squadron_value`),
  multi-role suppression, AI strike targeting and the AI's hazard maths for incoming bombers
  (`ai_hazards.marker_hits`, fixed: it used the Armour facing the bombers). Torpedoes use the
  facing they hit.
- **Forward-firing arcs (Tau "(L/F), (R/F)", owner):** the booklet's paired mounts load as two
  weapons with arcs left+front and right+front, so every AI planner (move score `_arc_score`,
  firing `_valid_targets`, threat model `_mount_bears` / `enemy_fire_plan`, squadron volleys)
  lets both sides' guns fire at a target ahead, never both broadsides at one target abeam.
  The threat model also allows the enemy's next turn, using each ship's own turn angle (owner:
  not all ships are the same; the Tau Protector turns 90 degrees, the Hero 45)
  (`ai_hazards._mount_bears`, `hit_and_run._weapon_can_bear`; `tests/test_ai_forward_arcs.py`).
- **Hazards in the AI's target choices (owner check):** gun values include column shifts
  (blast markers / dust in the line of fire or in contact, range; lances and nova cannon
  unaffected, s.11); asteroid fields, planets, warp rifts and hulks block direct fire
  (`los.check_los`); ordnance values use path survival mirroring the engine
  (`ai_hazards.ordnance_path_survival`): torpedoes detonate on planets / asteroid fields / warp
  rifts, die on a 6 in dust clouds and blast markers (seeking 5+); attack craft die on a 6 in
  asteroid fields, dust clouds (owner ruling) and blast markers, to warp rifts outright, and
  ignore planets. Owner: attack craft, and less so torpedoes that can turn, may move round
  obstacles (`ai_hazards.best_route`, up to two waypoints; AI craft fly them, a human's go
  straight at the target given). See "AI: how it decides".
- **Fighta-Bommerz are Fighta-Bommerz:** multi-role fighter + bomber; D3+1 attacks that
  turrets never reduce below 1, and no turret suppression.
- **Bought torpedo types** (Imperial Navy, Chaos: "+5 per torpedo strength", **capital ships
  armed with torpedoes only**, export 13): one type per ship, carried in addition to its other torpedoes and chosen at each launch
  (`booklet_options.torpedo_type_options`, ship rule `torpedo_type:<key>`,
  `ordnance.torpedo_kind_options`): short burn, barrage bombs, guided. The Navy "+50 to roll
  once per game for Seeking/Melta/Vortex" works like Chaos Anointed Munitions: per ship, a D3
  at game start (`torpedo_roll:d3_anointed`, `ordnance.roll_torpedo_types`). Mechanicus
  "refitted torpedoes +Npts" and Ork "looted torps +20pts" roll a D6 per ship at game start
  (`torpedo_roll:d6_refitted`). Seeking, melta and vortex are one salvo **per ship** per game
  (`Ship.once_torps_used`). Barrage bombs' low-orbit and assault-point rules wait on low orbit.
  Chaos torpedo tubes always carry boarding torpedoes too (`booklet_ships.convert_row`).
- **The hit-and-run toggle covers every raid (owner):** with `GameState.rule_hit_and_run` off,
  assault boats, boarding torpedoes and teleport attacks are disabled for the players too.
  Assault boats (incl. Sharks) aren't offered in the launch dialogs and can't launch
  (`ordnance.craft_type_allowed`, checked by `launch_attack_craft` and the AI); multi-role
  craft (Thunderhawks, Gun-Cutters) still launch as fighters / bombers, only their raid mode is
  off. Boarding torpedoes aren't offered (`torpedo_kind_options`) and a boarding launch fires
  standard torpedoes (`launch_torpedoes`). Teleports need both `rule_teleport` and
  `rule_hit_and_run` (`check_teleport_eligibility`, `end_phase_panel`)
  (`tests/test_raids_toggle.py`; tests that play raids use `conftest.make_gs_raids`).
- **Optional-rule toggles audit (owner: a disabled rule is off for players and the AI):**
  boarding (`rule_boarding`): declaration (`movement_dialog._offer_boarding`) and resolution
  (`end_phase_panel._resolve_boarding_actions`) both check it; ramming (`rule_ramming`): only
  declared on All Ahead Full when on, and only a declared ram resolves (`movement_panel`);
  teleport and hit-and-run: above; Remastered blast markers / spill-over: settings mode, read
  by the engine. The AI boards and rams (To do 8 h) only with `rule_boarding` / `rule_ramming` on. Fighting Sunward, Solar
  Flares and Radiation Bursts (s.40) are built (`src/celestial.py`, To do 6).
- **Turret suppression, Remastered mode (owner ruling; Remastered p.82 is the source until the
  booklet adds a "Remastered differs" note to s.27):** the Advanced toggle
  (`rule_turret_suppression_remastered`, shared with the planner via
  `optional_rules.set_suppression_rules`) is kept and follows p.82 exactly: each fighter in a
  wave of bombers attacking a ship adds +1 attack to the wave's total attack run (not +1 to
  each bomber's roll), whether or not turrets shoot that fighter down; the bonus can't exceed
  the bombers surviving turret fire and needs at least one; fighters intercepted by defending
  fighters / CAP add nothing; turrets remove fighters before any other ordnance; bombers still
  roll D6 - turrets (minimum 0) with the bonus on top. No fixed-attack or re-roll bonus in this
  mode: "exactly 3 attacks (4 for bombers that re-roll)" is XR only (s.27, XR p.32) and stays
  the default. Code: `waves.ship_attack_plan(..., remastered)` (fighters first, "bonus" on one
  bomber), `ordnance.resolve_bomber_attack(bonus_attacks=)`, `waves.wave_split_value` (the
  wave planner and AI follow the mode). Tests: Remastered's two worked examples (Emperor wave
  vs a 3-turret Devastation, no CAP, turrets kill three fighters: 3 bombers + 5 fighters ->
  D6-3 each + 3; 4 + 4 -> D6-3 each + 4) in `tests/test_remastered_suppression.py` and
  `tools/gui_checks/remastered_suppression_check.py`.
- **Dark Eldar ordnance (owner):** every Dark Eldar torpedo and attack craft but mines has
  flickerfields (fighters, bombers, torpedo bombers, assault boats, Impalers: enemy turrets
  +2 to hit, max 6+); Raptors and Impalers are resilient 4+; plasma torpedoes are standard
  torpedoes that must re-roll misses (Voidraven salvos too; not leech or boarding
  torpedoes); Impalers are a special type of assault boat, so they follow the assault boat
  rules (off with the hit-and-run toggle, like every raid) and leave at the start of their
  owner's turn (both turn systems). The AI counts all of it (`ai_hazards.torpedo_p_hit`,
  `craft_turret_p`, `_turret_kills(ship, marker)`, `waves.impaler_value`, the Impaler fuel
  deadline in `_strike_option` / `plan_strike_targets`).
- **Attack craft orders (s.18):** each squadron keeps a target (`craft_target_id`: enemy ship,
  enemy ordnance, or a friendly ship to escort) and flies straight at it up to its speed every
  time ordnance moves; without one it carries straight on. Players set targets with "Attack
  Craft Orders"; the AI re-targets its craft each ordnance phase.

- **AI difficulty (owner):** very easy and easy look 0 turns ahead (no search), normal 1
  (now 2 along one line: every root line is judged over the strategies' `PLAN_TURNS` 2, To
  do 34), hard 3, expert 5, master 10 or to the end of the game, whichever is shorter. Easy plays for
  the most expected VP like normal (every value and planner), only without the lookahead;
  very easy makes the simplifications (the closest valid target, owner, Lock On whenever an enemy is in
  arc now, moves scored on guns and hazards only and picked by softmax, simple ordnance, no
  squadron volleys / hulk or ordnance shots / disengaging / boarding / ramming / teleports;
  re-rolls and Brace by expected VP as the others): every `difficulty == "very_easy"` in
  `ai_player.py` (it was "easy" before the split). Game times: very easy ~8s, easy ~80s
  (the planning is most of normal's cost). Built:
  `lookahead_ai.DEPTH_FOR`, all four through `LookaheadAI` (minimax over the deterministic
  sim for movement, one level a full turn of both sides' moves and fire; the rest of their
  play is the normal AI's), `_depth_now` (capped by the turns left), run off the Tk thread
  (`GameFlow`). Each level keeps the best few lines (`BEAM_FOR`: normal 4; hard 4, 3; expert
  4, 3, 2; master 4, 3, 2, 1 then one line on to the tenth turn; judgement) within a time
  budget per ship (`TIME_BUDGET_FOR` 2 / 2 / 4 / 10s; judgement), now only a guard: the
  search is cut by a deterministic node budget (`NODE_BUDGET_FOR` sim turns a decision,
  normal 450, hard 550, expert 1100, master 2800), so seeded games replay at every level.
  Measured before the planner
  (`BFG_SEARCH_STATS=1` prints each decision's depth, lines, cuts and time): normal and hard
  reach their depth on every line; expert its 5 turns with a few lines cut by time; master
  its 10 turns on every line in 5-7s a ship (a wider master beam didn't fit the budget).
  Games: normal ~136s since the planner (~70s before it, ~25s before it searched), hard
  ~60-90s before the planner, master several minutes; seeded games repeat exactly.
  Search depth is not the value horizon (owner question, explained): the depth counts turns
  of moves played out in the sim; the value of a hull hit (`ai_hazards.hits_vp`) is a
  formula, the same at every level, that assumes the enemy keeps firing to the turn limit or
  `FUTURE_TURNS` 6 (next turn from the fire that can reach the ship, later turns a share of
  the enemy fleet's guns; no ship moved). It feeds the one-off decisions (targets, Brace,
  re-rolls, ordnance, orders) and, through `value_per_hit`, the move score that ranks the
  search's root moves; the sim's own leaf doesn't use it (VP banked + one more turn's
  swing). Whether that span should shrink with the difficulty: Open questions 2.
  Alternate activation uses the normal AI without the search for all of them (no
  per-unit search yet).

### Player choice prompts: "Auto (best)"

Owner request: the player's choice prompts have an "Auto" button that picks what the AI's
expected-value logic would (owner: on screen it is only ever labelled "Auto", never "best",
so players don't read it as the AI telling them how to play; "Auto split" in the launch
dialog, "(Auto: <aspect>)" in Combine Squadron Fire) (`src/choice_dialog.choose`; closing the window takes it
too): Leadership-test re-rolls and guided torpedo re-rolls (`ai_rerolls.should_reroll`),
Wings of Fury raid re-rolls (`hit_and_run.best_raid_reroll`, below), Mark of Tzeentch re-rolls (9+ own / 5-
enemy), the turret split (`ordnance.choose_turret_target`) and multi-role turret suppression
(`waves.best_mr_suppress`), multi-role attack mode (`waves.best_attack_mode`). GUI checks that answer these prompts must stub `choose`.
The Combine Squadron Fire aspect choice defaults to "Best for expected hits" (shown beside
it). The Brace prompt has it too (`choice_dialog.yes_no` with `ai_should_brace`; GUI checks
that answer Brace replace `choice_dialog.yes_no`), and so do the special-order re-roll prompts
(`special_orders_ui`, `should_reroll`) and the Vault of Technology chooser (the AI's Advanced
Shields).

Wings of Fury re-rolls (owner guidance): re-roll when a fresh D6 is worth more on average than
the result in hand (`raid_result_value`, in expected VP, using the crit after the cascade,
`raid_crit_preview`). Engine Room is +1 hit; an armament crit is worth the expected hits its
weapons would score on the raiding player's ships (`armament_threat_value`). Owner ruling
(extends the earlier "in arc and range now"): what the weapons threaten at the target's NEXT
shooting phase, weighted by the chance damage control hasn't repaired the crit by then
(`p_crit_unrepaired`: D6 per remaining hit, 6s repair, halved touching a blast marker; one end
phase when the raid lands in the raider's turn, two when in the target's own turn). An allied
ship counts if it is within range + the movement before that phase (the target's move, plus
ours in the two-end-phase case) and in the weapon's arc now (full) or after one turn of the
target's turn angle (0.75) (`_weapon_can_bear`). A disable that threatens no allied ship then is
worth nothing and is re-rolled; long-ranged, heavy weapons count most; a location already
knocked out counts nothing. Beyond the next phase (To do 2, done): the crit also counts at the
target's later shooting phases, up to `CRIT_HORIZON` 3 (judgement) and the turn limit, each
with two more end phases of repairs, a game turn's more movement in the reach (both ships) and
the `phase_weight` discount (1, 0.36, 0.26), so a weapon out of reach next phase is worth a
little rather than nothing (`hit_and_run._crit_shooting_phases`). Escorts: 1
damage on 4+, so Space Marines (+1) re-roll a 1 or 2. Armament crits now also silence the
AI's weapons (`combat.weapon_disabled_by_crit`, shared with the fire dialogs; it used to be
UI-only, so the AI kept firing knocked-out weapons).

- **Parking in an asteroid field in high orbit (owner check):** high orbit (s.41, "ships do
  not need to move") is built as no minimum move in a planet's gravity well
  (`optional_rules.high_orbit_planet`, `movement.get_effective_speed`; the end of the movement
  phase no longer demands a move from a ship with none; the table's terrain registered by
  `TurnController` through `set_phenomena_source`); not yet its free turns towards the planet.
  Asteroid fields (s.39): the navigation test is taken by a ship whose move passes through or
  touches a field anywhere along its path (`movement._asteroid_fields_on_path`), never by one
  that doesn't move; ordnance meets terrain anywhere along its move
  (`check_ordnance_vs_phenomena(start=)`: bombers launched from inside a field roll the 6);
  ships both inside one field may fire at each other within 10cm, half firepower
  (`combat._in_field_together`), no close range shift, never when crippled or braced
  (`los.check_los_ships`); every other line through a field is blocked. So a carrier can park
  inside a field in a gravity well, untouchable by direct fire from outside, launching bombers
  that each roll a 6 to leave; the AI doesn't seek this out (`tests/test_asteroid_high_orbit.py`).
  Launching inside a field (owner confirmed): a torpedo salvo placed in contact with a field
  detonates at launch (`ordnance.launch_in_asteroids`, from every launch path in `actions`);
  attack craft test as they move out on their first move, like blast markers: a wave rolls
  once for the whole wave (its lead; the wave goes with it), a lone squadron for itself (s.25,
  s.39). Tau missiles' per-point strength roll is their own rule, not this.

### Brace for Impact (s.7)

Declared before any combat rolls for an attack (to hit, scatter, turrets, weapon strength,
crits), after checks that decide whether the attack happens (target priority).
`CombatPanel._brace_before_attack` asks the target's player (the AI decides for its own ships
with `ai_should_brace`) before the Fire dialog, the squadron dialogs, AI fire (`AIPlayer.brace_fn`)
and torpedo / mine / bomber-wave attacks roll anything. A squadron tests once and braces
together. Hit-and-run raids keep s.31's order (brace after turret fire). Nova cannon: the
targeted ship is asked before the scatter roll. Engine-side attacks call
`combat.offer_brace`, which uses `GameState.brace_hook` (set by GamePanel, main thread only):
ramming (both ships, after the Leadership test), exploding ships (each ship in the blast,
after the radius roll) and asteroid fields (after a failed navigation test).

### Faction rules in the catalog

`booklet_ships.faction_special_rules` turns ships.json `faction_rules` into engine special rules:
Space Marines and Grey Knights get `space_marine_crew` (boarding +2, raids +1, enemy raids -1)
and `teleport_assault`; Grey Knights also `knights_of_titan` (re-roll a lost boarding action)
and roll Ld on the Astartes table; Rapid Strike Vessels ("no Space Marine rules apply") roll on
Default. Orks get `ere_we_go` (auto-pass All Ahead Full, +3D6cm). Built-in "+D6cm on All Ahead
Full" is `improved_thrusters`; Venerable Battle Barges are `venerable` (VP 50% / 125%).

### Ship options and fleet commanders

`src/booklet_options.py` holds booklet options as fleet-builder upgrades (effects: stat deltas,
set fields, weapon swaps, re-rolls; restrictions: one per group, requires, fleet-unique, Strike
Cruiser Variant limit). Space Marines so far: Secondary Shield, the three Strike Cruiser
Variants (Tactical Flexibility -10pts unless the fleet takes a Chapter tactic), Master of the
Fleet (Ld 10, 0-3 re-rolls, Terminator honour guard, one Chapter tactic +15pts). Honour guards
double teleport range; Veteran 2D6 keep best, Terminator 3D6 keep best two (two raids).

Other factions' fleet commanders (`booklet_options.COMMANDERS`, `fleet_commander_options`,
on capital ships): Navy Vice / Fleet / Solar Admiral (Ld 8/9/10, 50/75/100, 1 free re-roll,
+1/2/3 for 25/50/75), Chaos Lord / Warmaster (Ld 8/9, 50/75, 1 free, +25/50), Archmagos
Explorator (Ld 9, 50, no free re-roll, +25/50), Tau Kor'el / Kor'O (Ld 8/9, 50/70, 1 free,
+25/50), Rogue Trader Lord Captain / Venerable Lord Captain / Pirate Captain. Owner rulings:
the Archmagos and Tau re-roll costs (25 / 50, Imperium p.17, Xenos p.99); Ork Bosses
(Warboss 40, Big Mek 40, Freebooter Kaptin 30) have no Ld of their own (the ship's rolled
Ld; a Kaptin adds +1, `ld_bonus:1` in `fleet_loader.roll_starting_leadership`) and get
re-rolls only from a title (Big Boss 1 +20, Mega Boss 2 +40). Each list's `commander`
(`fleet_lists._attach_commanders`): required for more than 750 pts (see below),
Explorator 1000+, Green Tide one Boss at 500+ and at most one per 500pts, a Rogue Trader
detachment always; a Tau Custodian needs a Kor'O. Secondary commanders: see "Not yet
matching the booklet" (commander re-rolls). Kustom upgrades, two clans and the named
commanders are built (To do 4). Not yet: several Ork Bosses' re-rolls (the engine keeps one
re-roll pool, on the flagship). Export 31 settled it: a commander is required
for a fleet of **more than 750 points** (core s.5; `required_at` 751), except where a list says
otherwise (Banisher "at least 750", Explorator "1000+", Green Tide "500+"). Owner ruling,
booklet updates 33-34: commander re-rolls (fleet and secondary) are lost on Bridge Smashed
**or** when the commander's ship is destroyed (`TurnController`), and the opponent then
scores the commander's cost, which is part of that ship's points value (options add to
`points_value`, which `victory_points` scores).

Imperial Navy profile refits (`booklet_options.navy_refit_options`, matched on each note's
text): weapon swaps (`remove_weapons` + `add_weapon`), range / firepower changes
(`modify_weapons`, matched by name and range: Mercury and Tyrant have two weapons of one
name), extra craft types (`add_craft`, assault boats +5), Targeting Matrix, Extra Turrets,
the grand cruisers' "one of" group, the Cobra's improved sensor array (Enemy Contacts +2).
Torpedo types bought for a refit's torpedoes need that refit; a refit that removes the
torpedoes excludes them (`excludes_group:`). Built in from notes: Mercury `catastrophic_3d6`,
Sensors `ld_always:1` (+1 Ld after the roll or a commander's Ld, max 10; Comms Uplink too).
Battlefleet Bakka: starred classes +1 Turret when taken from that list (`stat_changes`,
`fleet_lists.list_stat_changes`, applied at fleet save), Veteran Captains (+1 Ld max 10, 30,
0-3, re-roll +15) replace Strategic Commanders and Fleet Defence Turrets (+5) are offered
only there (`list_options`, `list_excludes`), Mechanicus cruisers in the battlecruiser places.
Armageddon Sector: Master of the Fleet may be its commander (`extra_commanders`); its Space
Marine ships are allies of convenience (no Chapter tactics, `no_tactical_flexibility`).
Space Marine lists (update 18): Master of the Fleet on any SM capital ship, on a battle barge if
the fleet has one (the Ultima / Venerable Battle Barge if present); veteran honour guard +10;
Dominion Space Marine Captains (Navy reserves, Astartes Ld table); specialist torpedoes;
Chapter tactics only in SM fleets; Dominion reserve rules and nova cannon limits
(`nova_per_points`) in `fleet_list_errors`.
Mechanicus Gifts (`booklet_options.MECHANICUS_GIFTS`, one per capital ship): crippled
values go through `Ship.crippled_value` (Emergency Energy Reserves), Advanced Shields'
capacitors in `combat.apply_damage` (`rolled_to_hit=False` for explosions), Vault of
Technology rolled at game start (`mechanicus.roll_vault_of_technology`, main.py).
Option effects are applied by `ship_catalog.apply_upgrade_effect`.
Demiurg (Xenos p.91-94, p.101): War Host list `tau_demiurg_war_host` (no commander; War Host
re-rolls on `Ship.war_host_rerolls`, any Demiurg vessel, never lost); absorber fields
(`movement.collect_blast_markers`, `blast_markers_to_slow`), cutting beam
(`combat.cutting_beam_firepower`, `chapter_tactics.weapon_range`), phenomena immunity
(`terrain_effects`), Demiurg VP (`victory_points`). Owner ruling: the Bastion's modular bays
are S2 launch bays or S4 torpedoes, chosen at each launch (`Ship.mark_launched` unloads both).
Chaos (update 25): Marks (`mark:<god>` rules; Khorne troops, Nurgle +1 hit, Slaanesh
`movement.slaanesh_penalty`, Tzeentch `combat._tzeentch_reroll` with `GameState.crit_reroll_hook`),
Chaos Space Marine crews / Terminators, per-list limits in `fleet_lists._chaos_option_errors`
(each list's `chaos_options`). Boarding crew bonuses: largest only (`boarding._CREW_DAMAGE_BONUSES`).

Chapter tactics (`src/chapter_tactics.py`): chosen on the Master of the Fleet as
`chapter_tactic:<key>`; `apply_fleet_tactics` (game start, in main.py) copies it to the
player's Space Marine ships. Checked against the booklet text (s.03): Wings of Fury "may
re-roll" raids, so the owner chooses per raid (`GameState.raid_reroll_hook`, asked by GamePanel;
the AI and "Auto (best)" use `hit_and_run.best_raid_reroll`, see above); Tactical Reserves' 25% reduction rounds the result up,
like "half firepower (rounding up)", macrobatteries only; Pack Hunter needs a combined boarding
action (two or more of one squadron) against a larger ship; Lightning Thrusters vanguards
"either fire macrobatteries at full effectiveness or turn up to 45°". Its fleet-list part (up to 4
vanguards count against the strike cruiser maximum) is in `fleet_lists` (the vanguards'
`lightning_thrusters` section key). The other six also match s.03 (Dark Age, Siege Cannons, Shadow
Engines, Promethean Unguents, Heed the Machine Spirit, Tactical Flexibility), except:
Promethean Unguents barrage bombs hit on 4+, place a blast marker per hit (no damage) and
halve turrets for the next ordnance attack that turn (`Ship.turrets_halved_turn`,
`ordnance.ordnance_turrets`); Shadow Engines' "no effect against Tyranids or Necrons" has no
faction to apply to; Heed the Machine Spirit is always taken when a save fails (no prompt).

### Optional blast marker rules (s.11)

Advanced settings "Blast marker rules" (`GameState.blast_marker_rules`: standard / modern /
remastered). The engine reads the mode from `src/optional_rules.py` (`set_blast_rules`, set by
TurnController and the settings dialog): gunnery shifts in `combat.get_column_shifts`
(`blast_gunnery_shift`), ordnance vs ships in contact in `ordnance_movement._resolve_ship_contacts`.
Overlapping bases count for every effect (`geometry.count_blast_markers_touching`); the
Remastered spill-over limit is a separate checkbox (`rule_remastered_spillover`).

### Shooting by Squadrons (s.8)

`combat.plan_squadron_volley` / `resolve_squadron_volley`, used by the "Combine Squadron
Fire" dialog: firing ships are grouped by aspect fired at, range column shift, the target
ships they can hit and the Armour each needs; each group makes its own gunnery lookup
(escorts total then halve), and dice are combined into one attack per target set and
Armour values. Against one ship all hits are applied together; against a squadron each
group of firers seeing a different mix of aspects chooses the aspect (dialog comboboxes,
default "Best for expected hits": `combat.best_aspect_choice` / `volley_expected_hits`,
the aspect per group of firers giving the volley the most expected hits; the AI's volleys use
it too), each attack resolves separately with hits nearest first.
Owner ruling: blast markers placed by one group don't make the target harder to hit for
the others (every group's column shifts come from the markers before the volley), but
shields knocked down by one group stay down for the rest.

### Waves of attack craft (s.25)

`src/waves.py`: a wave is the markers sharing `wave_id`, ordered by `wave_order` (fighters,
then multi-role fighters, then the rest), formation "close"/"loose", stacked on the lead.
Launch dialogs (single ship and combined squadron) have "Launch as one wave" (on by default;
never for CAP); the AI launches each ship's craft as a close wave. A wave moves as one marker
at its slowest speed with one blast / terrain roll (`ordnance_movement`), interacts with
ordnance lead-first in repeated passes (`ordnance._interaction_pass`, `waves.is_lead`), is
removed whole by one hit from shooting (`waves.whole_wave_ids`), and against a ship it must
attack takes one turret roll (kills from the front), then attacks; surviving fighters in
the wave suppress one bomber each (exactly 3 attacks; Fighta-Bommerz never suppress), and the
whole wave is removed afterwards (`waves.ship_attack_plan`). Lone squadrons are their own
group: each faces turrets separately, and a fighter that isn't in the wave no longer
suppresses. Attack Craft Orders give a wave one target and can split squadrons off (alone
or as a new wave in the same formation; they never rejoin). The board labels waves "xN C/L".
Multi-role fighter-bombers (s.27) may suppress turrets instead of attacking, chosen before
the turrets fire (`waves.apply_mr_suppress`: suppressors to the front, at least one squadron
attacks; AI `waves.best_mr_suppress` by expected hits, a human via
`GameState.mr_suppress_hook`; Fighta-Bommerz never). Fleets without multi-role craft get a "Best split"
button in the single-ship launch dialog (`waves.best_wave_split`: fighters vs bombers for one
wave from the wave size, the chosen enemy ship's turrets incl. massed, its enemy CAP
fighters, Armour and resilient saves; `OrdnancePanel._best_split_plan`). Its inputs (target, bays, turrets,
massed, CAP, Armour) are filled from the chosen target, nearest first, and can be edited, e.g.
for CAP the enemy is expected to launch before the wave arrives; "Reset" refills them.
Resilient saves (s.23) for own fighters, bombers and enemy CAP (`waves.cap_survivors`: CAP
intercepts first, a passed save keeps the squadron in play as the lead with its save used;
turrets ignore saves). The wave size may be less than the bays: "+ lone fighters" launch
outside the wave (e.g. to intercept torpedoes), "+ CAP fighters" go on CAP for the Protect
ship, all in the same launch. Combining ordnance launches (s.15):
only members of one squadron (escorts or capital ships) in contiguous base contact. Not yet: bombers that re-roll attacks
(+1 when suppressed) don't exist yet; resilient
squadrons don't stop or split (interactions happen after movement, so it rarely matters).
CAP vs incoming craft (s.26, `waves.resolve_cap_vs_group`, `OrdnancePanel._cap_vs_group`): on
contact, before Brace and the turret roll, each of the ship's CAP squadrons intercepts the
group's current lead (fighters lead), any enemy craft group including fighters alone; s.23
saves (once per phase; a squadron that saved stays lead / keeps intercepting without a save;
both passing removes both, also in `ordnance.resolve_fighter_intercept`).

### Fleet lists (s.4)

`src/fleet_lists.py` (Navy, Mechanicus, Space Marines, Inquisition) and
`src/fleet_list_data_other.py` (Chaos, Orks, Tau, Rogue Traders) transcribe each faction's
Fleet Composition: sections with their ships at the list's costs (Bakka's premium), section
maxima, "one per N cruisers" ratios, "one per N pts", 0-1 uniques, minimum fleet sizes,
reserves (one per 3 of each type; Bakka 4; Dominion's own ratios), detachments (`kind:
"detachment"`, `joins`), options only some lists allow (`list_options`: Inferno torpedoes in
the Inquisitorial Fleet Detachment) and Lightning Thrusters' vanguards. `fleet_list_errors` is
called by the fleet builder's validation. The fleet builder picks a list per fleet (the
faction's first by default; "No fleet list" plays without restrictions, s.4), shows the
catalog by section, then the chosen detachment's ships and the reserve lists' ships, and saves
`fleet_list`, `detachments` and each ship's `fleet_list`. Older fleet files load with no list.
Rules a list can't check yet are in its `unenforced` text. Not yet: more than one detachment, "can't take more
copies as reserves than its own list could field", reserve-only refit rules. Support assets
have no list (they're scenario units).
Owner rulings (fleet lists, export 15):
- Points-based limits use what the fleet is worth (its actual total), not the game's points
  limit: "for every full 750" rounds down, "(or portion thereof)" rounds up (`or_part`).
- Chaos ratios count only what each list names: battleships and grand cruisers one per three
  cruisers and/or heavy cruisers, heavy cruisers one per two cruisers; light cruisers (0-6)
  don't count. Imperial Renegades are Chaos ships in all respects: a renegade cruiser counts
  as a cruiser for the ratios (renegade light cruisers don't); they aren't reserves; "six
  escorts and/or one cruiser" per full 750pts allows both.
- A Rogue Trader Fleet Detachment joins any fleet but Necrons / Tyranids, Orks included (not a
  reserve). The Crusade (Inquisitorial detachment only) and Banisher lists still refuse it.
  An Expedition's supporting fleet is one faction, never Orks, Dark Eldar, Necrons or
  Tyranids; any Space Marine list may be it, and then no Demiurg, Kroot or other xenos ships.
- Nicassar: every Rig needs four Dhows bought with it; towed escorts need gravitic hooks of
  their type (`towed_errors`, every fleet; capacities from the profiles as `hooks:<type>:<n>`).
- Space Marine battle barges (both lists): one per 1000pts or portion thereof; (0-1) Chapter
  Flagship (a Venerable Battle Barge, the Ultima or a Space Marine Battle Barge) needs a
  1000+pt fleet; (0-2) Command Ships (Space Marine Battle Barges). Venerable strike cruisers:
  with 1000+pts, one per three standard strike cruisers (variants count), at most two.
- Venerable Strike Cruisers (Imperium p.137): `booklet_ships.venerable_strike_cruiser_rows`
  makes "Venerable Strike Cruiser (<class>)" from every non-unique Navy / Chaos grand cruiser,
  battlecruiser and heavy cruiser (17): +25pts, Space Marine rules only, VP 50% / 125%,
  Thunderhawks only with each hangar's bay strength halved (rounding up), boarding
  torpedoes free; nova cannon ships get the Strike Cruiser Prow built in for 10pts less.
  Options (`venerable_strike_cruiser_options`): Strike Cruiser Prow (free with 6+ prow,
  else +25; removes Ablative Prow Armour, "lost if prow torpedoes taken"), short burn +5 or
  barrage bombs +10 instead of boarding torpedoes. The base profile's own special rules
  apply (Ablative Prow Armour, `ablative_prow_armor`, now set from notes for all six booklet
  ships that have it); its refits don't. Owner ruling: each hangar is halved separately
  (port S3 + stbd S3 -> 2 + 2). Designing a Venerable Battle Barge (guidelines agreed with the opponent) isn't built.
- Demiurg commerce vessels: fixed Ld (Stronghold 10, Bastion and Citadel 9), -1 per point of
  damage to a minimum of 5; Bridge Smashed deals one extra damage instead of -3 Ld
  (`combat.demiurg_leadership`).

### Engine notes and gaps (export 7 audit)

- Torpedoes attack ships touched anywhere along their move (`geometry.torpedo_first_contact`,
  facing taken from the contact point); attack craft flying straight without a target and
  torpedo-vs-torpedo collisions are still checked at the end of the move only.
- Commander re-rolls (s.5) are offered for command checks (special orders), disengage tests,
  guided torpedoes and, via `GameState.ld_reroll_hook` / `movement.fleet_reroll_offered`
  (GamePanel asks; the AI spends by importance in expected VP, `ai_rerolls.should_reroll`,
  see docs/HANDOFF.md "AI design"), Brace for Impact, target priority,
  asteroid (non-escorts; escorts have their own re-roll) and warp rift navigation.
  Secondary commanders (`booklet_options.SECONDARY`): Navy Strategic Commander (+1 Ld max 9,
  30pts, 0-3, re-roll +15), Chaos Aspiring Champion (+1 Ld max 9, 30, re-roll +15), Mechanicus
  Magos Explorator (Ld 8, 25, 0-3). They share the commander option group (one commander of
  any kind per ship); `ld_bonus:1:9` is added after the starting Ld roll; their re-roll is
  `Ship.own_rerolls`, usable only for that ship or its squadron and spent before the fleet
  commander's (`TurnController.get_fleet_rerolls / use_fleet_reroll(player, ship)`). Also built (To do 4):
  Inquisition Elite Daemonhunters (Banisher Fleet, Grey Knights Brother-Captain or Ordo Malleus
  Inquisitor, Ld 9, 30, one free own re-roll, 0-3 together: `fleet_max_group:`) and Elite
  Captains (Inquisitorial Fleet Detachment, +1 Ld max 9, 30, 0-3, re-roll +15), Rogue Trader
  Bond-Captains (Fleet Detachment, +1 Ld max 8, 10, 0-3, re-roll +15; Fortune not modelled),
  the Grey Knights Grand Master (Banisher fleet commander, Ld 10, 75, one free re-roll, +1 / +2
  for 25 / 50; a Grey Knights battle barge needs him, more than three Grey Knights strike
  cruisers need him or a Brother-Captain). Grey Knights ships now get the Inquisition options.
  Not yet: Elite Daemonhunters on escort squadrons, Ork Nobz (they grant kustom upgrades),
  Veteran Bond-Captains (need men o' war), the Fleet Detachment's 1-3 Inquisitors, the Grand
  Master's Paladins, per-Boss re-roll pools for several Ork Bosses.
- Disengaging (s.37): escort squadrons test together; Forced Disengagement (Ld 1 or less) and
  Demiurg Mercenaries test at the end of movement (`disengage.forced_disengage_tests`); a ship
  that fails gets `Ship.must_flee` (AI `_plan_flee`; voluntary AI disengaging: see "AI: how it
  decides"). The +3 applies anywhere during a radiation burst or the turn of a solar flare.

### Torpedo types (s.16): owner rulings

- Guided: turn up to 45° only if the launching ship passes its Leadership test (a fleet
  commander re-roll may be used: `guided_control(reroll_fn=...)`); a launcher no longer in
  play can't guide, so the salvo doesn't turn. After a failed test the enemy player chooses
  which ship tries to take control (`choose_enemy_fn`; the AI uses its best Ld); in control,
  it turns the salvo at the owner's ships.
- Unused melta / vortex torpedoes that explode on a launcher crit are not used up; once the
  salvo is fired the ship is no longer vulnerable. Launcher location = the torpedo weapon's
  arc (front = prow, L/F/R = dorsal).
- Melta Fire crits hit escorts too, and they may put the fire out in damage control like
  other ships; a drifting hulk hit by melta becomes a burning hulk.
- Inquisition (owner rulings): Inferno Torpedoes +20pts on any Inquisition vessel with
  torpedoes (melta usable any number of times; a launcher crit gives D6 Fires); vortex
  torpedoes +50pts only on an Ordo Malleus Inquisitor Lord's ship armed with torpedoes.
  `booklet_options.inquisition_options` also has the Inquisitorial Cruiser's free refits
  (Bombardment Cannon, Torpedo Salvo) and the Inquisitor Lord (Banisher list: Ld 10, 75pts,
  one free re-roll, +1 / +2 re-rolls for 25 / 50pts). The booklet now has two Inquisition
  lists (Ordo Malleus Banisher Fleet, Inquisitorial Fleet Detachment) whose options differ
  (Inferno needs an Ordo Hereticus Inquisitor, so not in the Banisher list); the fleet
  lists enforce that (`list_options`). Grand Master, Elite Daemonhunters / Captains built (To
  do 4). Not yet: Ordos (a ship may not mix Ordo upgrades), the detachment's Inquisitors,
  retinues, honour guards, Blessing of Chaos.
- Not yet: Rogue Trader refitted
  torpedoes (no Rogue Trader ship in the roster has torpedoes), Deathskulls' half-cost looted
  torps, the Ork zzapp gunz swaps. The Ork torpedo launcha swaps (Terror Ship, Kill Kroozer
  incl. its 2D6+2 variant, Basha) are options (`booklet_options.ork_launcha_options`); looted
  torps need one of them (`requires_any:`).

### Booklet update 62: the commander's death on alien tables (implemented, tested)

Result 9 on the Dark Eldar (Commanders Slain), Eldar (Infinity Circuit Smashed), Necron
(Monument Damaged) and Tyranid (Synapse Link Severed) tables counts as Bridge Smashed (s.5;
Necron Command Core Damaged, 10, doesn't): `models.COMMAND_CRITS` / `commander_dead`; the
crit marks the ship `commander_slain` (`combat.apply_crit_effects`), kept after a repair (the
Necron and Tyranid results are repairable, the loss isn't). The commander's re-rolls on that
ship are lost (`TurnController._commander_rerolls`, `use_fleet_reroll`, `_own_reroll_holder`:
fleet, secondary and Tyranid Hive Mind re-rolls), the opponent scores the commander's VPs
(`victory_points.commander_points`: the options in the commander groups or giving re-rolls;
the ship then scores on the rest of its points, a destroyed ship already counts them all), and
Kill the Admiral ends (`scenarios.ADMIRAL_KILLING_CRITS` is the same set, so the AI's
`bridge_smashed_chance` counts result 9 on every table). Bridge Smashed now scores the
commander's points too (it only lost the re-rolls before). Eldar use XR's critical hits table
(`tables.ELDAR_CRITICAL_HITS`, update 62): 2 infinity circuit -1 Ld given back on repair, 4 a
second prow hit also disables port / starboard weapons (`weapon_disabled_by_crit`), 7
superstructure +1 and a D6 per turn, 1-2 one damage (`dark_eldar.superstructure_strain`; the
engine has no solar jibes), 9 Infinity Circuit Smashed +1, -3 Ld, unrepairable, 10 Field
Generators Destroyed: no holofields nor shields (`Ship.effective_shields`)
(`tests/test_commander_crits.py`). Booklet installed: zip 15 (CHANGES.md update 62; the
catalog is unchanged by it, diffed).

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

- **Necron Obelisk (update 55):** it has no Ld of its own. The ship it is assigned to rolls Ld
  as normal (Appendix 4 has no Necron column, so the Default one: "factions not listed use
  Default"), and as a Monument it still gets one free re-roll and may buy more (Necron fleet
  list, Xenos p.50). Built in the fleet builder: `booklet_options.NECRON_COMMANDERS` (Obelisk,
  Monolith Ld 9, Sepulchre Ld 10, Overlord Ld 9, Nemesor Ld 10; one free re-roll, +1 for 25, +2
  for 75); the Obelisk keeps the ship's `leadership_table`, so `roll_starting_leadership` rolls
  it (`tests/test_necron_eldar_catalog.py`). To do 13 uses this for AA initiative. Not yet: the
  Harvest / Dynasty fleet lists (which commanders each allows), Monument damaged crits.
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

- **Troop rating: only the defender adds turrets** (s.32, "with the defending vessel adding
  its turrets"; fixed this session: attackers used to add theirs too). Goffs add theirs in
  boarding actions they start (`boarding.troop_rating(..., defending=)`).
- **Troop rating, crippled defender (implemented):** it adds its CURRENT turrets, halved
  rounding up when crippled (s.33; the drawn-combat rule says "remaining turrets"). Order:
  remaining hits, any doubling / halving, then current innate turrets (crippled-halved, after
  Fleet Defence Turrets' -2, never massed) (`boarding.troop_rating`, `Ship.effective_turrets`).

### Owner rulings: Impaler slave-taking (implemented, tested)

- **The Impaler's D6 comes first:** a 1 fails to connect and nothing happens, slave-taking
  included; on a 2+, a roll at or above the target's Armour does the bladed prow's 1 damage, and
  then slave-taking (D6 x 5 VP) may replace the raids / critical hit (`dark_eldar.resolve_impaler`
  -> `impaler_slaves` after the roll; the AI weighs the slaves against the better of the raids
  and the crit, and its strike value counts slaves as a third option, `waves.impaler_value`).
- **Each hit-and-run attack may be swapped for +5 VP,** an Impaler's two raids included (as
  built: `resolve_raids` -> `take_slaves`).

### Owner ruling: raid modifiers cancel (implemented, tested)

Every raid modifier is added together (`hit_and_run._raid_roll_modifier`): an attacker's
bonus and the target's penalty cancel, so Space Marines raiding Chaos Space Marines roll a
plain D6 (D6 + 1 - 1), as does a Dark Eldar raid (+1 Pain Frenzy) on a Space Marine ship.
A -1 to enemy raids applies only where a unit's rule prints it (Space Marines and those using
their rules, Mega Armoured Boarding Parties, Incubi, Tyranids, Mucous Membrane); a +1 rule
(Pain Frenzy, Aspect Warriors) never also gives a -1.

### Owner ruling: torpedo bomber salvos placed on a ship (s.21; implemented, tested)

A salvo placed overlapping a ship's base is in contact and attacks it at once (s.15 "comes
into contact ... it will immediately attack it"; s.17 "contacts a ship's base (friend or
foe)", its example a marker overlapping a base): a normal torpedo attack at placement, the
target's turrets first, then the attack, then the salvo carries on its move at its reduced
strength; it can't attack that ship again that turn (s.17's once per full turn). It also
attacks a friendly ship it is placed on (the fire-through-allies exception is for ships
firing torpedoes). No launch-turn arc for placed salvos (the bombers left on an earlier
turn and the facing is the player's choice): `ordnance.torpedo_in_launch_arc` passes every
`limited_fuel` salvo. AI: its waves fly at their target ship's centre (`craft_target_id`),
so they park on it and contact is certain next ordnance phase; `ai_hazards.
torpedo_bomber_target` values each salvo along its heading (`_bomber_salvo_value`: the
ships it is placed on first, friends against us, then the lane, nearest first, carrying on
with the misses) and `torpedo_bomber_heading` points a parked salvo's carry-on where it does
most (another enemy, never a friend; 24 headings); the human dialog's "Auto" and heading
use the same. Defence: the hazard model counts a wave within its move + the salvo move of
the end position (a parked wave included), and fighters, CAP and gunfire at ordnance value
it through `marker_hits` (`tests/test_torpedo_bombers.py`). In flight
(`ordnance.assign_ai_craft_targets` -> `ai_hazards.torpedo_bomber_flight_target`, the whole
wave together): the AI's torpedo bombers keep the strike planner's target while it is in
play; when it is destroyed, hulked or gone they fly at the enemy ship their salvo is worth
most against, x `phase_weight` of the phases before it is in salvo reach (they used to be
sent at the nearest enemy every phase, overriding the strike target). Not counted there:
interceptors and guns on the way (judgement). Firing: the AI fires a wave at the start of
every ordnance phase it can (s.21: any ordnance phase after the launch turn), the enemy's
too (`OrdnanceMovementMixin._ai_off_turn_ordnance`, IGOUGO; alternate activation already
runs both players' AI ordnance phases), when the salvo is worth anything; its own phase
fires before its missiles move (`run_ordnance_phase`), so a Tiger Shark salvo makes its
20-40cm Tau missile move that phase (it used to be left to the 20cm minimum).
Reach: standard torpedo bomber salvos 30cm (torpedo speed), Tiger Sharks 40cm.
Tau missiles (Tau Missiles: "20-40cm each ordnance phase") now move in both players'
ordnance phases, as other ordnance does: the AI's by plan in either phase, a human's from
"Move Tau Missiles" in either (unmoved ones still auto-move 20cm at resolution); before,
they stood still in the opponent's phase. The AI's moves take the approach planner's first
move length (`approach_plan` returns "length"), no longer always the full 40cm.
Turning salvos in flight (Tau missiles, Ld-guided, boarding torpedoes; owner: they don't
manoeuvre like craft) keep their planned target while the planner can still reach it,
else re-target to the enemy worth most through `approach_plan` itself, i.e. with only the
45-degree turns, move lengths and Ld odds they really have (`ai_hazards.salvo_approach`,
recorded as `torp_target_id`); a torpedo bomber salvo plans one move only (`max_moves=1`,
it is removed at the end of the phase).

Round 2, team play (To do 22), steps 5-8, the window, the port language and the Decoy
are answered (see below, the agreed order, "Window and port", To do 22).

### Owner rulings: answers to the open questions, round 2 (implemented, tested)

- **Halving (standing ruling, s.13 / s.8):** capital ships halve each weapon separately
  (rounding up), then total: two FP3 on Burn Retros make 2 + 2 = 4. Escort squadrons are the
  exception: total first, then halve (s.8, Shooting by Squadrons; `plan_squadron_volley`),
  and an escort's own combined batteries likewise (`combat.combined_battery`).
- **Low orbit placement:** Remastered p.116's "touching the edge furthest from the planet".
  The owning player chooses the facing (`GameFlow._low_orbit_facing_hook`, prompt with
  "Auto"; `low_orbit.FACINGS`, `enter(gs, ship, heading)`); the AI and "Auto" face along the
  planet edge on its heading's side (`low_orbit.default_facing`); position along the edge by
  its side of the planet, as built.
- **Craftworld forges (XR Xenos p.32, for the craftworld's forges only; the booklet's MMS
  Haven Spire keeps neither field):** a docked ship (`craftworld.forge_fields`) has the
  Netherfield, "All gunnery weapons suffer an additional right column-shift against" it
  (`combat.get_column_shifts`, so the AI's values see it), and the Polarization Field, it
  "never risks suffering a hit for being in contact with blast markers and ignores all
  effects of solar flares" (`movement._blast_marker_damage`, `celestial._solar_flare`).
- **Sign-off 2:** closed. **10:** as built: Navigate the Storm ends only when no transport
  capacity remains or a fleet is gone (the "both or neither" draw needs both checked at the
  end). **16:** in alternate activation, materialising ships come into play at the start of
  the round's movement phase and return to normal at its end, after both sides' movement
  activations, base contact as in IGOUGO (`navigate_storm.aa_movement_start / _end`, from
  `AATurn._begin_phase` / `advance`). **54:** the Remastered escort VP option's "total
  points value" is the full original squadron (as built). **55:** the 45-degree sun split is
  fine. **63-66:** the AA AI choices are fine as built.

Answered before: the AA notes and draft PDF are now in `docs/` (To do 13); where AA sits
in the order follows the dependencies (its experiments come after 11 a-c). Answered: where To do 8 goes. Owner: "the order isn't hugely important". So follow
the dependencies: build 8 a (Armour facing) and 8 f (range brackets) before 11 a
(target-directed candidates) and 11 h, and the rest of 8 with or after them; otherwise the
listed order is a guide, not a rule (1, weight tuning, stays last and on hold).

Owner ruling (Tiger Sharks, Tau; for To do 3): Tiger Sharks follow the torpedo bomber rules in
full, except that the salvo they produce is a Tau missile salvo (Xenos, Tiger Shark entry:
"follow the rules for torpedo bombers, except that they produce missile salvos ... rather than
normal torpedoes"). So:
- at the start of any ordnance phase after the turn they are launched, a Tiger Shark squadron
  may be replaced by a strength-2 missile salvo placed facing any direction; a wave may combine
  its salvos as normal torpedo bombers do (XR Rulebook p.31);
- the salvo uses a torpedo marker and moves 20-40cm that phase (player's choice), per the Tau
  Missiles rule; the missile rule's single 45-degree turn is redundant, since the salvo is
  already placed facing any direction;
- the salvo is removed at the end of the ordnance phase in which it is fired (torpedo bomber
  limited fuel, p.31);
- the Tau missile strength-loss roll (1D6 per point, each 1 loses 1) never applies: it only
  affects salvos launched on a previous turn, and a Tiger Shark salvo never survives to a later
  phase;
- Tiger Sharks have a 4+ resilient save and speed 20cm, and are bombers when interacting with
  other ordnance.

Owner rulings (dust clouds, answers to the last questions; implemented, tested):
- A gas / dust cloud in the line of fire shifts macrobatteries one column right even if
  neither ship touches it, but it doesn't stack with blast markers: blast markers and dust in
  the way give one right shift between them (`los.check_los` "column_shifts" is 0 or 1;
  `combat.get_column_shifts`; also shooting at ordnance). Lances and nova cannon unaffected.
- Attack craft in a gas / dust cloud are destroyed on a 6, like torpedoes
  (`ordnance.check_ordnance_vs_phenomena`; the AI's `ordnance_path_survival` / `best_route`
  count it).

Owner ruling (resilient saves, s.23): the booklet's wording stands. A resilient squadron saves
against any other ordnance it intercepts or is intercepted by (fighters, bombers, torpedoes,
mines), as `ordnance.py` already does; never against turrets, blast markers, shooting or after
attacking a ship.

