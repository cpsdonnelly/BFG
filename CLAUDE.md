# BFG:XR Simulator

A digital play aid for Battlefleet Gothic: Extended Rules (BFG:XR). The desktop app is
Tkinter (`python run.py`); the rules engine is pure Python in `src/`.

## Rules source of truth

- **`bfgxr/` is the rules authority.** Read `bfgxr/CLAUDE.md` before changing any rule or ship
  stat. It is an export of the BFG:XR companion booklet: `bfgxr/rules/` (one Markdown file
  per section) and `bfgxr/data/ships.json` (178 ships, stats and weapons parsed). Never edit
  those generated files by hand; the `.docx` in `bfgxr/source/` is the master.
- Never invent rules, stats or values. If the booklet doesn't cover something, say so and
  ask the owner.
- Core rules sections most often needed: Basics (1), The Turn (2), Fleet Commanders (5),
  Special Orders (7), Squadrons (8), Movement (10), Shields & Blast Markers (11), Ramming (12),
  Direct Fire (13), Ordnance: Launching, Moving & Attacking (15), Torpedoes incl. torpedo types
  (16), Attack Craft (18), Hit-and-Run Raids incl. teleport attacks (31), Boarding Actions (32),
  Damage & Critical Hits (33), Catastrophic Damage (34). `bfgxr/CHANGES.md` lists what each
  export changed (read it after every new export: it flags renamed fields and spelling changes).
  Sections are numbered in `bfgxr/rules/00_core-rules.md`.
- Victory points: core section 38 and the "Victory Points" part of `bfgxr/rules/14_scenarios.md`
  give the same rules: Destroyed, Crippled, Scattered (disengaged) and Holding the Field.
- Squadrons (s.8) include Maneuvering Squadrons and Shooting at Squadrons (target aspect, hit
  allocation nearest-first, critical damage applied before a ship counts as destroyed).
- `data/rules_cheatsheet.txt` and `data/*.csv` (plus the copies in the repo root) are an
  older hand-written summary. Where they disagree with `bfgxr/`, `bfgxr/` wins.
- The ship catalog (`src/ship_catalog.py`) is built at import from `bfgxr/data/ships.json` by
  `src/booklet_ships.py`: all 11 factions, 212 booklet ships plus 17 designed Venerable Strike
Cruisers. Eldar (MMS v2.0) are playable (18 of 24 ships) and so are Necrons (the six mobile
ships; the tomb complex, pylon and Deathseed mines aren't); To do 14 lists the gaps. Ships using rules the engine can't play yet
  (special movement, fortress weapons...; immobile defences are playable) are
  listed with `entry.unsupported` reasons and greyed out in the fleet builder. Old catalog names
  ("Gothic Class Cruiser") still resolve. Saved fleets keep their saved stats.

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
- **Random Ork firepower/strength is rolled when used:** direct fire when the weapon fires
  (the target may still brace before damage is rolled), ordnance just before launching.
  `combat.weapon_fire_pool` fixes a weapon's pool on its first shot of the turn.

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
- **Attack craft orders (s.18):** each squadron keeps a target (`craft_target_id`: enemy ship,
  enemy ordnance, or a friendly ship to escort) and flies straight at it up to its speed every
  time ordnance moves; without one it carries straight on. Players set targets with "Attack
  Craft Orders"; the AI re-targets its craft each ordnance phase.

### Player choice prompts: "Auto (best)"

Owner request: the player's choice prompts have an "Auto (best: ...)" button that picks what
the AI's expected-value logic would (`src/choice_dialog.choose`; closing the window takes it
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

### Session status (details in docs/HANDOFF.md)

Booklet installed: zip 14 (CHANGES.md update 60; Dark Eldar and Tyranids added, listed but
unsupported until their faction rules are built; rules files renumbered again: Dark Eldar 08,
Eldar 09, Necrons 10, Orks 11, Tau 12, Tyranids 13, scenarios `14_scenarios.md`, campaigns 15,
the appendices 16-22; the owner's sign-off answers are `bfgxr/notes/OWNER_SIGNOFF_answers.md`).
Catalog diff against zip 13: no existing entry changed but the Eldar Transport (now Free, a
convoy ship with transport capacity 1 from its special rule, `booklet_ships.RULE_TRANSPORT`,
playable). Tests: 1300 pass; all GUI checks pass
(`xvfb-run -a /usr/bin/python3.12 tools/gui_checks/<x>.py`; the spectator checks take a
difficulty: `gui_spectator_demo.py normal` / `expert`; expert games take ~75s of their 180s
limit). After every new export, diff the built
catalog (dump every entry's stats, rules, weapons and options before and after): notes text is
matched in code, and a reworded note silently drops an option.

Latest work (HANDOFF, "Session after booklet zip 13", the AA and Eldar parts): alternate
activation plays end to end in the game window (all three systems, AI and humans; To do 13)
and Eldar MMS v2.0 are playable (To do 14). Before that, in the same session: To do 2, 3, 6 done; large parts of 4, 5, 8, 9, 10, 11 and the first slice of 13 built
(each item below says what). Fixed: attackers no longer add turrets to troop rating (s.32).
Readings to confirm with the owner are listed in HANDOFF and in To do 3 / 6.
Later in that session (HANDOFF, same section, "Then"): Miasma's ordnance part; Siren's Summon
against plain Leadership tests (reading to confirm: an escort squadron's off-table / forced
disengage tests within 15cm are treated as blocked, no failure penalty); To do 10's Reload
Ordnance and Come to New Heading by value (10 is done but e's small Brace items); To do 11 a's
safety goals, disengaging valued at the end position and one coordination round. Known limit:
the expert's root moves under Come to New Heading are one-turn only.
Then (HANDOFF, same section, "scenarios"): Necrons playable (To do 14), and To do 7's
matched-play set: all nine short scenarios built for the engine and the AI, with immobile
defences, the Space Station crit table and transport capacity; scenario points in the margin
(To do 2 done); two general AI fixes (off-table moves priced as disengaging, edge traps).
Then attack ratings, sub-plots' first slice, the introductory scenarios, four raids (The
Raiders, Blockade Run, The Bait, Rearguard Attack) on a new reinforcements framework, and
three battles (Alien Intervention, Surprise Attack, Fleet Engagement), then Escalating
Engagement's contact markers, Navigate the Storm, Destroy the Docks and the narrative
Convoy; then (booklet zip 14) the owner's sign-off answers applied, low orbit,
Exterminatus! and Planetary Assault: 25 booklet scenarios in all (To do 7 lists what is
left). Fixed on the way: a zero-length line of sight against a
planet divided by zero; AI scenario rolls asked a human in "mixed" dice mode.

Built so far: every booklet rule section the engine plays (see the sections above), the export
31 "still to do" list, boarding crew bonuses, disengaging incl. forced disengagement, optional
blast marker rules, the turret split, waves / CAP / wave planner, the hit-and-run toggle
covering every raid, Remastered turret suppression per p.82, the optional-rule toggle audit,
and the expected-VP AI below (incl. carrier doctrine, strikes valued when they land,
co-ordinated strikes, splitting a strike into two waves under enemy guns, the AI's own teleports, Brace asked before each weapon of AI fire and
before each kind of weapon in the Fire dialog, the AI's mine hazard counting turrets, crit
values over later shooting phases, playing for the win under a turn limit (expert search,
disengaging, re-rolls), the expert's root moves paying for hazards, exposure by Armour facing
(8 a), the range-bracket matchup table (8 f) and the first slice of target-directed movement
candidates (11 a)).
Not built: the campaign set pieces and the rest of the sub-plots (To do 7; 25 scenarios
are built), and the To do items below.
Next (largest first): 7 (the campaign set pieces, the rest of the sub-plots), Dark Eldar and
Tyranids (new in export 14, listed but unsupported), the Necron and Eldar gaps (To do 14), To do 13's remaining
bits (the experiments: Eldar fleet lists or hand-built fleets and a headless runner; the expert
AI per unit), the rest of 4 (daemonships:
off-table start, warp translation, spectral state touching every targeting / ordnance path;
Ordos; Inquisitors; Veteran Bond-Captains) and 5 (special movement: Space Hulk / Rok /
Nicassar / Kroot; fortress weapons; Pthuxutl; Man O' War), the rest of 11 (deeper expert
hazards, more coordination rounds, two-turn root moves for the expert under Come to New
Heading), 10 e (Brace's remaining bits), 12 (learned evaluation) and 1 (weight tuning) only when the owner says
so, kept separate from the current AI (see Owner rulings). Owner: the order isn't hugely important; follow the dependencies. For 13,
the AA notes leave several choices open (shooting vs movement order, the launch ordnance
phase, end-phase cadence): build them as settings, never settle them for the owner.

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
tuning them is on hold (owner: keep it in mind, but it is hard work, so leave it for now): re-roll bars 45 / 25 / 15 / 10 VP, 0.35 expected hits per battery
point, half-weight flagship exposure, `PHASE_DISCOUNT` 0.85, `LATER_TURN_WEIGHT` 0.5,
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
- Two VP scales: gunnery `damage_vp` (s.38 thresholds + 0.2 x points / starting hits per hit; checked) for choosing gun / torpedo
  targets; `hull_hits_vp` (full value per hit + thresholds, the raid scale) wherever bomber hits
  are compared with raids. Ordnance never loses hits to shields (s.11 / s.15).
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
  under Lock On with its batteries / lances counted `LOCK_ON_GAIN` 0.5 more, minus the best
  move that may turn, at the check's pass chance; the target is the one the move plans
  against; only guns in range after the move count); All Ahead Full by value (`_aaf_gain`,
  10 b: the best straight move at full speed + the expected bonus, guns in range halved,
  minus the best free move; Orks pass automatically), the higher of the two; Reload Ordnance
  when spent (now by value, `_reload_value`); Come to New Heading by value (`_ctnh_gain`, two-leg
  moves `_ctnh_moves`). Check
  order (10 c): `_plan_orders` values every ship's order at the start of the phase
  (`_order_value`: VP gain, pass chance with Enemy Contacts / Under Fire) and
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
  bias). Not modelled: losing special orders while braced, the engine doesn't stop a braced
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
- Holding bays (`_hold_bays`): out of reach (nothing within three moves of the fastest craft)
  hold; within reach hold when (1 - Reload Ordnance odds) x next turn's launch or CAP value >
  launching now (rarely, with fair Ld).
- Fighters fleet-wide by VP saved; turret split by expected hits saved.

Re-rolls and choices: importance-based re-rolls (`ai_rerolls.should_reroll`); Wings of Fury raid
re-rolls and the "Auto (best)" prompts (see above).

Expert AI (`lookahead_ai`): minimax over a deterministic sim using the same terms (battery 0.35
scaled by Armour, lances 0.5, focus without overkill, torpedoes once, explosions at their odds,
shields each turn, the real table, its own ordnance in flight); leaf = VP banked + next turn's expected swing at
`LATER_TURN_WEIGHT`; with a turn limit, the chance of winning from that margin
(`win_score`, To do 2); root moves are the normal AI's candidates, best first, at most
`ROOT_MOVES` 12, and pay the path-hazard cost (To do 11 b); lances valued by their hit roll.

### To do (agreed order; detail in docs/HANDOFF.md)

1. On hold until the owner says to start (owner); when built, kept separate from the current
   AI, never replacing it: tuning the AI's judgement weights (listed in "AI: how it decides"). Keep
   it in mind, but it is hard work, so leave it be for now: don't retune them unless the
   owner asks. Example worth a look later: a lone healthy cruiser facing three full enemy
   cruisers disengages under the current model. Owner (AI design feedback): do it, but as
   the LOWEST priority, after To do 11 and 12. Method agreed: CMA-ES (not a genetic
   algorithm); tune the judgement weights only, never rule-derived values (25% / 100% / 10%
   VP, Tau 5/6, the 10.5cm explosion radius, +14cm All Ahead Full, 0.5 per lance), and first
   replace the 0.35-per-battery-point rule of thumb with the exact Gunnery table; paired
   evaluation with common random numbers (same seeds and scenarios, sides swapped), VP margin
   as fitness; an opponent pool (earlier weight sets, the untuned AI, hand-made styles);
   normal AI only (the expert takes ~75s a game); the harness doubles as a rules test (an
   optimiser finds degenerate strategies in the rules as well as in the AI); redo after any
   structural change. If weights must differ by matchup, make them functions of measured features
   (launch-capacity ratio, mean speed difference, range-bracket advantage, hits per point),
   never per-faction weight sets.
2. Strike planning by expected VP when the strike lands (owner discussion; design in
   docs/HANDOFF.md "Ordnance strike planning"): crit values over the turns they last (damage
   control s.36), threat at the target's next shooting phase, travel time and which player's
   ordnance phase the wave lands in, losses on the way (fighters, blast markers, reactive CAP,
   target leaving), enemy guns vs waves (one hit removes a whole wave on 6+, s.25 / s.30) and
   when to split a wave, a risk preference from the game state, the expert AI using the same
   terms. Owner: the expert AI thinks 5 turns ahead, so it must be aware of a turn limit: if it
   is behind and the game is near its end it should play riskier moves (and, by the same
   logic, play safe when ahead). Its search already stops simulating at the limit
   (`SimState.is_terminal`), but scores outcomes by expected VP only, which is risk-neutral.
   Plan: with a turn limit, score by the chance of winning instead: VP margin now plus the
   expected swing, against its spread over the turns left (e.g. a normal approximation from
   the shots' variance); behind with few turns left, high-variance moves (closing to brawl,
   all-in strikes, rams, risky disengage tests not taken) gain; ahead, low-variance ones. The
   normal AI's re-roll, brace, disengage and strike choices should use the same game-state
   preference; scenario points (e.g. Domination) count in the margin. One function feeds the planner, AI launches, bombers vs assault boats, multi-role
   attack modes and Wings of Fury. Built: crit-over-time value and the reach model for raids
   (`hit_and_run.armament_threat_value`), the time discount (`phase_weight`), and strikes
   valued when they land (`ai_hazards.strike_timeline`, used by `_strike_option` and
   `plan_strike_targets`: arrival phase from both players' ordnance moves and the target's
   predicted track, each option at its own wave's speed (the slowest craft); the raid's
   repair window from the landing turn (1 end phase in ours, 2 in the enemy's;
   `raid_result_value(..., end_phases)`); enemy guns in reach of the waiting wave in each
   enemy shooting phase before arrival (Ordnance column, one 6 removes the wave, out of arc at
   half, x `ENEMY_FIRE_AT_WAVE` 0.5, judgement); reactive CAP from a loaded target carrier
   when an enemy ordnance phase comes first, incl. the arrival one (the enemy moves its
   ordnance first, s.15), at `REACTIVE_CAP_WEIGHT` 0.5 (judgement); reactive intercept (owner:
   "reactive intercept should also be a strategy"): any other loaded enemy carrier whose
   fighters can reach the waiting wave in an enemy ordnance phase up to arrival
   (`reactive_intercept`), fed to the planner like CAP (each meets the wave's lead, s.19 /
   s.25) at the same weight; enemy fighters already flying free that can reach the waiting wave
   by an enemy ordnance phase (they move in every ordnance phase and need no launch,
   `airborne_intercept`, `AIRBORNE_INTERCEPT_WEIGHT` 0.75, judgement); the planner mixes every
   interception case and picks the fighter / bomber split against them;
   `tests/test_strike_timeline.py`). Owner: a fleet with less launch capacity can still neuter
   one with more (6 interceptors cut a wave of 8 to 2, turrets take more), so enemy carriers
   threaten our strikes and striking outside their umbrella is a strategy: a target within an
   enemy carrier's fighter reach is worth much less (23.6 VP vs 42.6 in the open in
   `tests/test_ai_air_doctrine.py`), so the strike goes to the open one. Our own side already
   intercepts reactively: free fighters go at enemy salvos / waves in flight
   (`_threat_slots`, 0.75), and holding bays counts next turn's defence (`_hold_bays`).
   Effects: faster assault boats now beat a slower fighter / bomber wave in the owner's
   4-turret 6+ example (they land a phase sooner, less time under the target's guns; at equal
   speed the bombers still edge it); an enemy carrier holding loaded fighters 35cm away makes
   our strike land after its guns and CAP, so CAP for our weak friend wins, while from within
   one bomber move the full wave wins. Crit values beyond the next shooting phase: built
   (see "Wings of Fury re-rolls"). Reactive CAP for craft already in flight: built (in-flight
   craft are re-targeted with the same interception cases, `ai_hazards.interception_cases`,
   shared by `_strike_option` and `plan_strike_targets`; `tests/test_ai_air_doctrine.py`).
   Splitting waves against enemy guns: built for fighter / bomber strikes at launch
   (`AIPlayer._two_wave_value`: one hit removes a whole wave, s.25, but each enemy weapon
   fires at one marker, so two waves share the shots out, `ai_hazards.split_wave_survival`
   on `strike_timeline`'s "shots"; each wave then faces the turrets and suppresses alone and
   gets half the interceptors; outcomes mixed over which waves get through; the launch forms
   the two waves, `_wave_groups`). Splits when the guns on the way matter more than the
   turrets: under two gunships vs a 1-turret target it splits, vs 4 turrets or with no guns
   it stays one wave (`tests/test_strike_timeline.py`). Not yet: splitting assault boats or a
   wave already in flight, more than two waves, the turret-split bonus for split waves.
   Risk preference, expert AI: built (`lookahead_ai.win_score`, used by `_evaluate` when the
   game has a turn limit): the leaf scores the chance of winning, Phi(margin / sigma), where
   the margin is today's (VP banked + next turn's swing at `LATER_TURN_WEIGHT`) and sigma^2 =
   turns left x mean ship value x both sides' expected VP a turn (a turn's swing is lumpy: a
   ship of value V dies or it doesn't, variance about V x its expected VP), floored at 2% of
   the points; plus `RISK_TIEBREAK` 0.1 x margin / points (judgement) so more VP still wins
   when the result is settled. Behind on the last turn a brawl beats staying out of range;
   ahead the reverse; without a turn limit the leaf is expected VP as before
   (`tests/test_lookahead_sim.py`). Normal AI, built: `ai_hazards.game_risk` (margin from
   `victory_points`, spread from `outcome_sigma`, shared with `win_score`) and
   `certainty_equivalent(gs, player, outcomes)` (a gamble's sure-VP equivalent: its average
   without a turn limit; with one, the VP change with the same chance of winning, so worth
   more than its average when behind, less when ahead). Used by disengaging (staying is a
   gamble on being crippled or destroyed, leaving a sure 10%: ahead it leaves more readily,
   behind less; a crippled ship concedes nothing extra by leaving, so it still leaves) and
   re-rolls (on the final game turn the bars drop to the lowest, 10 VP: left-over re-rolls are
   worth nothing after it) (`tests/test_ai_disengage.py`). Brace (`brace_value`, both choices
   by certainty equivalent), strikes (`_strike_option`'s `risk_value`: the strike gets past the
   guns on the way or not and meets each interception case; two-wave values and in-flight
   re-targeting still use the expected value) and the guns a disengaging ship gives up
   (`ai_rerolls.firepower_outcomes`: a kill / cripple / neither gamble; staying is it and the
   damage gamble together) use it too (`tests/test_ai_disengage.py`,
   `tests/test_strike_timeline.py`). The expert AI values its own ordnance in flight:
   `lookahead_ai.SimOrdnance` (the searching player's torpedoes, bombers and assault boats;
   fighters, mines, CAP and torpedo bombers left out), moved through both ordnance phases of
   each sim turn and resolved on contact as `marker_hits` counts it (`_resolve_ordnance`), and
   counted in the leaf's swing while still flying (`_ordnance_swing`), so the enemy's moves in
   the search dodge it; the enemy's ordnance stays a root-move cost (To do 11 b) to avoid
   counting it twice (`tests/test_lookahead_sim.py`). Scenario points in the margin: built
   (Domination and Planet Strike, see To do 7). To do 2 is done.
3. Mines and torpedo bombers (built this session; s.17, s.21, owner rulings).
   Mines: the swap "up to two cruisers [or battlecruisers / heavy cruisers] may replace all
   of their launch bays with mine launchers, +5 per bay" (`booklet_options.mine_launcher_options`,
   `MINE_SWAP_GROUPS` by each list's wording: Navy Cruisers / Battlecruisers, Mechanicus,
   Space Marine and Inquisition Cruisers, Chaos Cruisers / Heavy Cruisers, Tau any cruiser
   but light cruisers; one launcher per bay in the bay's location; `fleet_max:2`); the
   Bastion gains mines as a third mode of its modular bays (strength 2, +10, `mark_launched`
   unloads all three modes); `ordnance.lay_mines` (one per launcher, halved crippled /
   braced) for the launch dialog and the AI; a crit to the launchers' location deals D3 extra
   damage (`combat.mine_launcher_crit`, raids too). The AI lays its mines when an enemy is
   within 60cm (three turns at 20cm). Readings to confirm: light cruisers aren't
   "cruisers" here; the Bastion pays +5 a bay for the third mode; Rogue Trader men o' war
   (not built) aren't offered. Torpedo bombers: "Attack craft: TB 20cm +Npts" adds the
   `torpedo_bomber` craft to the bays, Tau "Tiger Shark drone carriers +Npts" swaps the
   Mantas for `tiger_shark` (`booklet_options.torpedo_bomber_options`, `swap_craft`); they
   never attack ships (`attacks_ships` False), are intercepted like bombers, and from the
   ordnance phase after their launch turn a wave (or lone squadron) is replaced by one salvo
   of 2 a squadron facing any direction (`ordnance.torpedo_bomber_groups`,
   `fire_torpedo_bombers`; Tiger Sharks a Tau missile salvo, 20-40cm), removed at the end of
   that ordnance phase (`remove_spent_salvos`, `TurnController.end_phase`). Players: "Fire
   Torpedo Bombers" in the ordnance phase (target per wave or hold, "Auto (best)",
   `tools/gui_checks/torpedo_bomber_check.py`). AI: strike option "torpedo bombers"
   (`_strike_option`: survivors of the interceptors fire 2 each, turrets 4+ each on the
   facing), fires at the start of its ordnance phase at the ship in salvo reach worth most
   (`ai_hazards.torpedo_bomber_target`); the hazard model counts a salvo of 2 a squadron on
   the lowest Armour within craft move + salvo move (`marker_hits`). Not yet: firing in the
   enemy's ordnance phase (the AI fires in its own; a player can fire in either), the salvo
   aimed by the lead / approach planner, Chaos "not if Stormbird gunships taken"
   (Stormbirds, To do 4), the Explorer's Bor'kan price.
4. Named commanders (built, `booklet_options.NAMED_COMMANDERS`: Lord Admiral Rath, Bakka
   list only, Ld 10, 150, two free re-rolls, +1 defending in boarding; Warmaster Abaddon, 13th
   Black Crusade only, Ld 10, 195, one re-roll a turn never saved (reset in
   `TurnController.begin_phase`), free CSM crew and Terminators, troop rating doubled;
   Kor'O'Mesme, Tau, Ld 9, 110, two free re-rolls; not yet: Rath's random refits and bought
   re-rolls, his battleship placement and the 1500 / 1000pt minimums, Abaddon's "You Have
   Failed Me", O'Mesme's crew skills, the Dominus Astra / Se'arle O'Mesme ships), daemonships, god-fleet boons
   (built: `booklet_options.GOD_BOONS`, only in their god's fleet list, needing that Mark:
   Veil of Lust (gunnery at it shifts right), Siren's Summon (0-2: enemy ships within 15cm
   fail every command check, Brace included; no plain Leadership tests either: a voluntary
   disengage test can't be taken (`blocked`, a squadron tests from a member outside 15cm),
   forced tests fail (asteroid / warp rift navigation, guided torpedo control, Heed the Machine
   Spirit), the AI's disengage value knows it; `tests/test_sirens_summon_ld.py`; sign-off
   answer 50: a forced disengage test (an escort leaving the table, Leadership 1 or less,
   Demiurg mercenaries) within 15cm fails with its normal result, `forced=True`), Miasma of
   Pestilence (no left shift within 15cm; ordnance attacking it destroyed on a 6 as
   through blast markers, `ordnance_movement._resolve_ship_contacts`; the AI counts it and the
   Modern / Remastered blast-contact roll via `ai_hazards.attack_survival` in `best_route` and
   the torpedo planners; `tools/gui_checks/miasma_check.py`), Plague Arks (0-3: a
   Fire critical on the other side of a boarding action); not yet: the Berzerker Tide, Warp
   Beasts, Strands of Fortune; also built: Mark of Chaos Undivided, `src/chaos_undivided.py`: on the Warmaster's / Lord's
   ship, 25pts; once per game before a command check the fleet takes its Ld until the end of
   that player's turn, Ld changes meanwhile kept; `GameState.undivided_hook`, a human is asked
   with "Auto (best)", the AI uses it when the test gains 0.25 pass chance or the fleet a point
   of Ld on average (judgement); not yet offered before plain Leadership tests; Stormbird
   gunships, `booklet_options.STORMBIRDS`: on a Chaos Space Marine vessel, no cost given, the
   bays carry only Stormbirds (multi-role, as Thunderhawks: 4+, 20cm) at half strength each,
   rounding up, and exclude torpedo bombers), Ork kustom upgrades / clans (built:
   `booklet_options.ORK_KUSTOMS` on a Boss's or Nob's ship, one each, Big Boss +1, Mega Boss +2
   (`kustom_count_errors`): Extra Turrets +2 max 6, Extra Power Field +1 shield, Mad Meks
   repairs on 4+, Mega Armoured Boarding Parties (crew +2, raids +1, enemy raids -1), Grot
   Riggers +1 Ld on Reload, Soopa Tellyporta 30cm (capital ships), More Dakka offered but not
   modelled; the Ork Nob (20); a Big Mek's extra repair die; clans Goffs (ram tests pass,
   turrets in boarding actions they start) and Evil Sunz (+2D6cm AAF) at +50% of the Boss,
   on his own ship only; not yet: Bad Moons, Deathskulls, Blood Axes, Snakebites, More Dakka,
   the Big Mek's hit restore, Nobz per 500pts, clan authority over further ships), the rest of
   the secondary commanders (Veteran Bond-Captains, Inquisitors; built: Elite Daemonhunters, Elite Captains, Bond-Captains, the
   Grey Knights Grand Master, see "Engine notes"), Inquisition Ordos.
5. Unplayable units (Zzapp Gunz built: lances hitting on 5+, `hits_on`, their random
   firepower rolled on D6s so a rolled 1 puts a blast marker at the stern once a turn,
   `combat._zzapp_firepower`; the AI values lances by `ai_hazards.lance_p`; the Slamblasta is
   playable now; Kustom Kannon built too: the Hammer Battlekroozer's prow weapon is an FP6
   killkannon (4+ to hit and crit) or a D6+2 salvo sharing one load, so firing either needs
   Reload Ordnance, `kustom_kannon`, `combat.spend_kustom_kannon`; the Hammer is playable;
   the Planet Killer's Armageddon Gun built: `combat.resolve_armageddon_gun`, the template
   swept 90cm straight from the stem, D6 hits under the hole, 1 under the template, shields
   apply, ordnance removed, stopped by planets / asteroid fields with D6 blast markers, not
   while crippled / AAF / Burn Retros / braced, Reload Ordnance recharges it
   (`armageddon_spent`); Fire dialog and AI (`_armageddon_value`);
   `tools/gui_checks/armageddon_check.py`; not yet: the reload roll's double / double-6
   malfunction (the command check keeps only the total) and exterminating planets): special movement (Nicassar Caravan, Kroot
   Warsphere, Space Hulk), fortress weapons (Ramilies, Fortress-Monastery), Pthuxutl
   disruptor cannon, Man O' War configuration.
6. Smaller gaps, done: s.40 (`src/celestial.py`): Fighting Sunward doubles the range column
   shifts of gunnery fired at a target in the sunward abeam arc (compass parallel to the
   sunward edge; `optional_rules.set_sunward`, read by `combat.get_column_shifts`, so the AI
   counts it); Solar Flares (a 6 on any die at the start of a turn, once per game: a blast
   marker on every ship's sunward side, an unshielded ship takes one hit, crit on 4+, each
   ordnance marker removed on 4+); Radiation Bursts (5+ on any die, one a turn: every ship -D6
   Ld for the turn, given back in the end phase; fleet commanders' re-rolls only for their own
   ship or squadron, `TurnController._radiation_blocks`); the +3 disengage Ld anywhere during a
   burst or the flare's turn. Demiurg vessels are immune. Readings to confirm: a toggle on
   means the battle is where the effect applies; the phenomena table isn't rolled, so
   `GameState.solar_flare_dice` / `radiation_burst_dice` (1 each) stand for the flares and
   bursts it would generate; the re-roll limit is applied to every re-roll during a burst, not
   only command checks; the AI doesn't plan around flares / bursts yet (the sunward shift it
   does count). Also done: undoing a Demiurg move returns the
   blast markers it collected (`TurnController.undo_ship_movement`); a human's ship that
   failed a forced disengage test must move its full speed and end within 2cm of the best
   simple move towards the nearest edge (`disengage.flee_move_errors`, checked by the move
   dialogs and drag moves; disengaging stays its own button).
7. Scenarios and sub-plots, engine and AI (owner request: the AI must play scenario and sub-plot
   games, not just cruiser clash; after items 1-6). The engine has only the old generic modes
   (`scenario.check_scenario_end`: kill the admiral, destroy / protect a ship, capture an
   artefact); none of the booklet's scenarios (`bfgxr/rules/14_scenarios.md`: Cruiser Clash, The
   Bait, Chance Encounter, The Raiders, Blockade Run, Convoy, Rearguard Attack, Navigate the
   Storm, Destroy the Docks, Exterminatus!, Alien Intervention, Surprise Attack, Planetary
   Assault, Escalating Engagement, Fleet Engagement, the campaign set pieces and the newer
   short set: Confrontation, Line Breaker, Ambush, Convoy, Space Assault, Rescue, Warp Storm,
   Planet Strike, Domination) or sub-plots (p.80-82: Legacies of War, Chance Circumstances,
   Secret Ploys; Heroic / Victory / Heroic Defeat / Miserable Defeat results; renown in
   campaigns; plus faction sub-plots: Mechanicus Quest for Knowledge, Inquisition Secret Ploys,
   Rogue Trader Business as Usual). Build: (a) the scenarios' set-up, special rules, game length
   and victory conditions (attack ratings, attacker / defender, low orbit, planets, convoys,
   transport capacity, assault points, High-Risk Convoys); (b) sub-plot generation, their
   effects and objectives, and the battle result; (c) the AI: value each scenario's and
   sub-plot's objectives in expected VP alongside ship VP (e.g. escaping or stopping convoys and
   blockade runners, objective ships, planets and assault points, the Vendetta target, keeping
   the flagship above 75% for Fleet Experience, reinforcements surviving, boarding for battle
   plans, Holding the Field, the turn limit). Ask the owner where the booklet is unclear.
   Owner: the AI must know every scenario's own win conditions, not only VP. Domination is just
   one example (owner); there are many other scenarios, each with its own objectives, game
   length and end triggers, and the AI must handle all of them. E.g. Domination
   (p.125-126): objective markers that can't be moved or attacked; a player controls one with
   at least one ship within 15cm of it (marker centre to the ship's stem) and no enemy ship;
   at the end of each player's own turn they score 1 point per marker controlled; the game ends
   when a fleet is destroyed or disengages or a player reaches 10 points, and the most points
   wins. So the AI values control in its move score (holding, contesting, denying markers),
   races the points against the turn order, and weighs that against ship VP. Likewise each
   scenario's conditions and end triggers (convoys or blockade runners exiting, planets and
   assault points, Exterminatus, rescue / escape objectives) and sub-plot objectives feed the
   same values, normal and expert AI alike (the expert search's leaf score included).
   First slice built (`src/scenarios.py`, pure logic; the old generic modes stay in
   `scenario.py`, both chosen by `GameState.scenario_mode`): the registry (`SCENARIOS`: first
   turn, game end, victory), Confrontation (attacker / defender zones 30cm from the long
   edges, attacker first, VP) and Domination (the six D6 deployment diagrams transcribed edge-
   relative, `_domination_layout`, incl. Domination 3's L-shaped zones (`DeploymentZone.extra`);
   `setup_scenario` rolls the D6 before deployment (`GamePanel._start_game`) into
   `GameState.scenario_state`; `controller` (a ship's stem within 15cm, no enemy; reading:
   hulks, destroyed and disengaged ships hold nothing); `score_end_of_turn` from
   `TurnController.end_phase` (AA scores both players in the round's end phase, reading);
   `check_end` at 10 points; a fleet gone or the turn limit decided by points
   (`winner_at_end`, `scenario.check_game_over`). Deployment zones and the attacker's first
   turn are used by the game (`deployment_panel`, `_begin_turn1`); the board draws the markers,
   their 15cm ring in the controller's colour and the score; setup and in-game settings offer
   both (`tests/test_scenarios_booklet.py`). AI (first form, judgement): `_objective_term` in
   the move score (markers this ship's end position wins us at the end of our turn, plus
   `OBJECTIVE_DENIAL` 0.5 for contesting an enemy-held one, a small pull towards markers within
   two moves; ships still to move at their planned ends), "objective" point goals for the
   three nearest markers, and `_objective_stake` against voluntary disengaging (its share of
   the markers for the turns left); a point = `OBJECTIVE_POINT_WEIGHT` 0.5 x the points on the
   table / 20 VP. `tools/gui_checks/gui_spectator_domination.py igougo|aa [layout]` plays an
   AI-vs-AI Domination game to game over. Second slice built: Ambush (XR p.119: defender
   more than 30cm from every edge, every defending ship / squadron facing one way and 20cm
   from the others, `placement_errors` via `DeploymentState(extra_check=)`; attacker within
   30cm of any edge; the defender starts unloaded (`setup_scenario`); no special orders, Brace
   or disengaging for the defender until the end of its first turn, `orders_forbidden` /
   `disengage_forbidden` in `TurnController.issue_special_order` / `can_issue_special_order`,
   `movement.attempt_brace`, `combat.offer_brace`, `CombatPanel._brace_before_attack`,
   `ai_should_brace` and `disengage._ftl_blocked`; reading: the attacker's first turn counts
   too, the defender is caught unawares), Rescue (p.122: defender's short edge = the left one;
   the flagship, or the dearest capital ship when none is marked (reading), placed by the
   scenario at the centre facing that edge, `fixed_placements`; no orders in the defender's
   first turn; it may only disengage off that edge (reading: no Leadership-test disengage),
   off any other edge it is destroyed, `off_table_destroyed` in `movement.execute_movement`;
   the attacker +100% of its cost if destroyed, `vp_bonus` in `calculate_victory_points`),
   Warp Storm (p.123: 30cm corner squares, attacker bottom-left / top-right; `division_errors`
   warns at the end of deployment when the divisions differ by more than one capital ship or
   escort squadron (reading); at game end each disengaged ship or squadron tests Ld once, a
   failure is destroyed, `end_of_game` from `GamePanel._declare_game_over`). AI: the Rescue
   flagship's kill bonus in `damage_vp` and `disengage_gain` (`kill_bonus_vp`), the flagship
   heading for its edge when leaving is worth it (`_rescue_escape`), Warp Storm's warp loss in
   `disengage_gain` (`warp_loss_chance`). `tools/gui_checks/gui_spectator_scenario.py
   igougo|aa ambush|rescue|warp_storm|confrontation|line_breaker|space_assault`. Third
   slice built: immobile defences (Support Assets p.61-62: the five "Immobile" high orbit
   defences, the dormant Blackstone Fortress and the Tau Security Orbital / Orbital City are
   playable, `immobile` rule from `booklet_ships.convert_row`, speed 0; they never move
   (`TurnController.get_unmoved_ships`, the AI marks them moved), take no All Ahead Full / Burn
   Retros / Come to New Heading, never disengage (reading), all-round torpedo launchers aim
   any way (`ordnance.launch_torpedoes`); Ld 7 as fleet support; the Space Station Critical
   Hits table for high orbit defences with 3+ starting hits, `tables.SPACE_STATION_CRITICAL_HITS`
   with `space_station_crits`: lances / main armament / ordnance bays out
   (`weapon_disabled_by_crit`, cascading when there is nothing to hit), reactors halving
   shields and turrets (`Ship.effective_shields / effective_turrets`), fire, shields collapse,
   hull breach, bulkhead collapse; Orbit Lost has no effect yet, no planet to fall to).
   Line Breaker (p.118: defender's long edge the bottom one, its fleet within 60cm, its
   platforms more than 30cm from every edge, 15cm apart and outside phenomena; attacker within
   15cm of the top; `force_errors` warns unless the defender has one platform per 200pts or
   portion; ends when every platform is destroyed and an attacking capital ship has moved off
   the bottom edge (`record_exit` / `line_breaker_won`), otherwise the defender wins) and Space
   Assault (p.121: the station placed 30cm from the defender's edge, centred; +250 VP to the
   attacker if destroyed, else to the defender). AI: platforms' kill bonus (the defender's
   points / platforms, judgement) and the station's 500 (the 250 swing both ways);
   `_breakthrough` pulls attacking capital ships to the bottom edge once the platforms are
   gone (`BREAKTHROUGH_WEIGHT` 0.5, judgement) and `_objective_stake` keeps them from
   disengaging. Fourth slice built: convoy ships' transport capacity (`booklet_ships.
   transport_capacity` from the notes of convoy ships only: `transport:<n>`, and
   `transport_build_only` for escort carriers / Q-ships; the Fast Clipper (unarmed) and the
   free Conventional Transport are playable; `scenarios.transport` halves it for crippled
   ships larger than escorts) and the matched-play Convoy (`convoy_matched`, p.120: defender
   and convoy within 30cm of the bottom edge, attacker 15-45cm from the top, defender first;
   `force_errors` wants exactly one capacity per 100pts or portion of the defender's other
   ships (reading: convoy ships' own points excluded) and one ship whose capacity counts in
   play; the game ends when no capacity is left on the table; convoy ships are scored by
   `vp_bonus`, not the normal VP (`scores_normally`): off the top edge +100 to the defender,
   leaving any other way their cost + 50 to the attacker, destroyed their cost, crippled 25%
   (reading: one by one, not as squadrons)). AI: `_convoy_run` (convoy ships head for the top
   edge, 100 + `CONVOY_RUN_WEIGHT` 0.5 x their points, judgement), they never take disengage
   tests (`_objective_stake`), and the attacker's kill bonus of 100 a convoy ship. Fifth
   slice built: Planet Strike (p.124: `setup_scenario` places a large planet (radius 8)
   centred between the long edges with its far side 45cm from the defender's short edge (the
   right one) and removes other planets (reading); attacker within 30cm of the left edge,
   defender within 45cm of the right one, its defences in the gravity well; `force_errors`
   wants the attacker to carry at least one transport capacity per 100pts or portion of its
   warships (reading: "at least"); at the end of the attacker's turn each attacking ship that
   moved no distance (reading: turning on the spot allowed) and touches the planet scores its
   remaining hits + transport capacity (`score_end_of_turn`, `in_planet_contact`); at game
   end the attacker holding the field wins, else the D6 table (`strike_need`, rolled in
   `end_of_game`, `winner_at_end`)). AI: Burn Retros to hold over the planet when the
   bombardment (`_bombard_hold_value`, a point = `BOMBARD_WEIGHT` 0.5 x the points on the
   table / 25, judgement) beats half its guns, then no move; `_bombard_approach` closes on the
   planet; the defender's ships count keeping the field in `_objective_stake`. General AI fixes
   found by these games: a move ending off the table is now priced as the sure disengage it is
   (`_off_table_score`: `disengage_gain` at a certain pass less the scenario stake, or the
   scenario's own exit value; Rescue's flagship off the wrong edge is destroyed), and an end
   position from which every minimum move next turn leaves the table pays that at
   `PHASE_DISCOUNT` (`_edge_trap_penalty`); before, ships could wander off the edge.
   `TurnController._clear_previous_orders` now resets the per-turn movement tracking
   (alternate activation had nothing resetting it). Scenario points in the margin (To do 2's
   last item): `scenarios.scenario_margin_vp` (Domination points and Planet Strike
   bombardment as VP: `domination_point_vp`, `bombard_point_vp`, the weights now shared in
   `scenarios`) is added to `ai_hazards.game_risk`'s margin (so the certainty equivalents,
   re-roll bars and disengaging play for the scenario's win), and the expert search's leaf
   (`lookahead_ai._scenario_margin`, `SimState.scenario` from `scenarios.sim_scenario`): points
   banked plus, at `LATER_TURN_WEIGHT`, the markers each side holds where its ships stand / the
   attacker's hits touching the planet. Attack ratings (p.78): `scenarios.attack_rating`
   (the main faction's by points; Grey Knights banisher 3, 2 when more than half isn't Grey
   Knights; Rogue Trader / Inquisition detachments change nothing; sign-off answer 44: Rogue
   Traders alone 3, Dark Eldar 4, Tyranids 2 (3 with Pheromone Rage, not built), Corsair /
   Craftworld Eldar 4 / 3 and Necron Harvest / Dynasty 4 / 3 by `LIST_ATTACK_RATINGS`
   (ships don't carry their list yet, so Eldar 3 and Necrons 4)) and `roll_attack_ratings`
   (best die, then the next; out of dice loses; full tie re-rolled), chosen in setup as
   "Attack ratings (roll)" (`GameState.attacker_by_rating`, rolled in
   `GamePanel._start_game`). Sub-plots, first slice (7 b, `src/subplots.py`): with the
   setup option "Sub-plots" (`GameState.rule_subplots`) each player, the attacker first,
   rolls one before deployment (`GamePanel._roll_subplots`; D6 table, D6 entry; nominations
   asked of a human with "Auto (best)", the AI nominates the dearest ship), kept in
   `GameState.subplots`. Effects built: Gunnery Practice / Extended Duty command check
   modifiers (`command_check_modifier` in `movement.do_command_check`), Extended Duty's D3
   damage, Meteor Storm's crits, Fresh Captain's -1 Ld, Surprise Attack (the enemy's
   `orders_forbidden` for D3 game turns, reading: both players' turns), Secret Intelligence's
   extra re-roll, Experimental Ship's improvement / side effect (contradictions re-rolled),
   Navigational Hazards' clouds / asteroid field (reading: placed at random away from the long
   edges), Hit and Run's 2D6 turns, Enemy Plans' search roll on boarding a capital ship
   (`record_boarding` in `boarding.resolve_boarding`) and Secret Intelligence's raid
   (`record_raid` in `hit_and_run.resolve_raids`). Objectives judged at the end
   (`objective_met`; readings: Extended Duty / No Quarter count a crippled ship's whole
   points, a draw isn't a won main mission) and the battle result with renown in the game-over
   dialog (`battle_result`: Heroic Victory / Victory / Heroic Defeat / Miserable Defeat). Not
   built (flagged `unbuilt` when rolled): Blood Bond's +1 Ld, Fleet Experience's borrowed Ld,
   Signaling Problems' re-roll limit (their objectives are judged), Unexpected Help's
   reinforcements and the Decoy (can't be met), Fresh Captain's objective (kills aren't
   credited to ships); faction sub-plots. AI, first form: `subplots.kill_bonus_vp` (a
   Vendetta target, our Desperate Mission / Experimental Ship, a Fleet Experience flagship:
   `SUBPLOT_WEIGHT` 0.1 x the points on the table, judgement) through
   `scenarios.kill_bonus_vp` into `damage_vp` and `disengage_gain`
   (`tests/test_subplots.py`; `gui_spectator_scenario.py igougo confrontation subplots`).
   Introductory scenarios built: Cruiser Clash (p.84: Fleet A / B zones 90cm wide centred on
   the long edges, a D6 for which (reading: player 1 rolls), every ship facing the opposite
   edge (`placement_errors`), first turn by the usual roll-off, eight turns each
   (`game_turn_limit` sets `GameState.turn_limit` for any scenario with `game_turns`: player
   turns in IGOUGO, rounds in AA), won on damage points (`damage_points`: a point per damage,
   +1 crippled or +3 destroyed), not VP) and Chance Encounter (p.88: the attacker's flagship
   placed 10cm in from the centre of its long edge facing the defender (`chance_flagship`,
   reading: its dearest ship without a commander marked), the attacker's zone 60cm wide, six
   turns, the defender chooses to go first or second (`first_turn_chooser`, AI by
   `ai_moves_first`); the defender wins when the flagship is crippled (destroyed: heroic, shown
   in the game-over dialog), the attacker when the uncrippled flagship and another capital ship
   left off the defender's edge (`chance_result`; reading: otherwise a draw); AI:
   `cripple_bonus_vp` (half the points on the table, judgement) in `damage_vp` and
   `_breakthrough` for the attacker's capital ships). Raids built: The Raiders (p.91:
   defender more than 30cm from every edge, every ship facing the same table edge and 20cm
   from the other ships / squadrons; the attacker "moves on from any edge" (reading: it
   deploys within 3cm of any edge, facing onto the table); attacker first; the defender at -1
   Ld for the first D6 game turns, given back by `scenarios.turn_start` from
   `TurnController.begin_phase` / `AATurn._start_round`; eight turns; VP) and Blockade Run
   (p.92: a D6 per blockading ship or squadron for its third of the table, more than 60cm from
   the attacker's edge; attacker within 15cm of the bottom edge; roll-off for the first turn;
   six turns; the attacker's ships off the blockader's (top) edge score their points, a
   quarter if crippled, on top of the normal VP; AI `_exit_value` / `_convoy_run` pull its
   ships to that edge and `_objective_stake` keeps them from disengaging by a test). The AI's
   off-table moves now count a scenario exit only off that scenario's own edge.
   Reinforcements built (`scenarios`: reserve ships have status `reserve` and
   `is_disengaged`, so everything ignores them until they arrive; `ships_alive` counts them,
   VP never scores them (reading: reinforcements that never arrive score nothing), deployment
   skips them; `turn_start` offers each reserve unit at the start of its player's turn (both
   players each AA round) through `GameState.reserve_hook` (GamePanel: the AI brings them on
   at once, judgement; a human gets "Enter now / Wait"); `place_arrival` puts them at the
   scenario's `entry_edge`, facing in, and they move normally that turn). Built on it: The
   Bait (p.86: the pursued ship or squadron, reading: the defender's dearest unit within 250pts
   unless chosen, at the centre facing the right short edge; the rest of the defender's fleet
   in reserve entering from that edge; pursuers more than 60cm behind it; defender first; VP)
   and Rearguard Attack (p.97: reading: the defender's cheapest units until 25% of its points
   are reinforcements, entering from the sunward edge, the left one as drawn; the defender
   more than 30cm from the long edges and 60cm from the sunward edge, facing it, 10cm apart;
   the attacker on from any edge as The Raiders; -1 Ld for D6 turns; eight turns; VP). Not
   yet: entering along the long edges after turn 1 (up to 30cm a turn), choosing the
   reinforcements / the pursued unit in the set-up dialogs, Navigate the Storm (ships lost in
   rifts), the narrative Convoy (contact markers, deadfall torpedoes), Destroy the Docks
   (orbital mines, random arrival rolls). Battles built: Alien Intervention (p.103: the
   defender's ships of a faction other than its main one are the alien allies, in reserve,
   arriving as one fleet from a long edge (reading: the top) on a D6 from the defender's 2nd
   game turn, 4+ / 3+ / 2+ / 2+ / automatic on turns 2-6; a planet near the centre (reading:
   medium); defender within 30cm of the centre line, facing one way and 10cm apart; attacker
   within 20cm of either short edge; first turn by the attacker's 2D6 against the defender's
   D6, `roll_for_choice`; eight turns; VP; not yet: the drifting hulk near the centre) and
   Surprise Attack (p.104: a planet at the centre sized by the defender's points; D3 units on
   full alert (reading: its dearest unless chosen) more than 30cm from the edges, the rest on
   standby within 15cm of the planet and abeam of it; standby ships don't move, shoot, launch
   or teleport (`on_standby`: `TurnController.get_unmoved_ships / get_unfired_ships`, the AI's
   movement / shooting / ordnance loops, `launch_attack_craft`, the human launch dialogs,
   `check_teleport_eligibility`) but may brace; at the start of each defender turn each
   standby unit tests Ld (a squadron once on its best Ld, reading) to go on full alert, then
   no special orders that turn; the attacker comes on from one edge; VP). Scenario rolls for
   an AI player at turn start are automatic (`_dice_for`; in "mixed" dice mode the human was
   asked to roll for the AI). Fixed on the way: a zero-length line of sight against a planet
   divided by zero (`los._line_intersects_circle`), which crashed an AI ordnance phase. Not
   yet: Exterminatus! and Planetary Assault (the low orbit table), Escalating Engagement
   (contact markers), the defenders' extra planetary defence points. Fleet Engagement built
   (p.108-109: each player's secret formation (a human from a dialog, the AI at random,
   judgement: they beat each other in a circle) through the table to a set-up and roles
   (`resolve_formations`; two results: a D6 + `formation_bonus` (fastest ship, best commander,
   most escorts, +1 each; reading: ties give no bonus, tied rolls are re-rolled), the winner
   choosing from its own formation's results; set-up B has no attacker: the chooser's fleet
   deploys below, reading); set-ups A-D transcribed edge-relative (`_fe_rects`, divisions with
   their approach arrows); every ship faces its division's arrow (`placement_errors`,
   `fe_division_at`, `auto_heading` also used by the deployment panel's auto-place) and every
   division needs a unit (`fe_division_errors`, warned at the end of deployment); roll-off for
   the first turn; VP; not yet: the alternating deployment by a roll).
   Escalating Engagement built (p.107, `src/escalating.py`): up to five divisions per player
   (`auto_divisions`, judgement: dearest units first, each to the division with fewest
   points; `scenario_state["divisions"]` keeps a chosen split), a random starting division
   each (D6, re-rolled above the count), a roll-off for who places its starting marker first
   (the winner second, judgement), markers 30cm from the edges and 60cm apart (placed
   automatically on the player's half, a D6 along it, reading), the starting division within
   10cm of its marker (`placement_errors`, zone = the rect round it); the rest in reserve. In
   each player's end phase (`end_of_turn`, from `TurnController.end_phase`) a random waiting
   division's marker goes on a D6 edge (1 left, 2-3 top, 4-5 bottom, 6 right): not within
   60cm of enemy ships, within 30cm of our ships near that edge, nearest our ships
   (judgement); none legal: it waits (reading). At the start of the player's turn
   (`turn_start`) each edge marker rolls 5+ / 4+ / 3+ by the slowest speed, +2 with friends
   within 30cm (always tried, judgement): arrived divisions are placed touching the edge within
   10cm of the marker, facing in, and move normally; otherwise the marker slides along the
   edge up to the slowest speed towards our ships (judgement). The board draws the markers.
   Not yet: a human choosing the divisions, the markers' positions and slides (dialogs); the
   AI valuing where its markers go.
   Navigate the Storm built (p.98, `src/navigate_storm.py`): no other phenomena, 8 warp rifts
   each placed alternately from the attacker (D3x5cm wide by D3x10cm long, s.39, sign-off
   answer 17, long side along the table, 10cm apart edge to edge; placed
   automatically, judgement: the attacker on the convoy's way from the defender's zone to the
   exit point, the defender away from it, never in a zone or the exit point); zones from the
   diagram (defender the bottom-left quarter 20cm in from the left edge, attacker the
   top-right quarter 10cm down and short of the exit point, the exit point the right edge's
   20cm strip beside it, `zones`); the attacker chooses who goes first (`first_turn
   "attacker_choice"`); `force_errors` wants 10 transport capacity. A failed rift test
   (`terrain_effects.resolve_warp_rift_navigation` -> `lose_ship`): a defending ship counts
   as destroyed (reading: its capacity and VP to the attacker); an attacking ship is
   `lost_in_warp` and in the attacker's end phase (`end_phase`) picks a capital ship on the
   table (judgement, also for a human: the one nearest the convoy) and on a 2+ is placed 15cm
   from it towards the convoy (reading: within 20cm), `materialising` and out of play until
   the attacker's next movement phase (`turn_start`), where it moves ignoring terrain and
   blast markers; at the end of that phase (`end_of_movement`, from `TurnController.end_phase`)
   it returns to normal unless in base contact with an enemy (then out of play again,
   the end of the next one) and tests Ld: a failure halves its armament (`half_armament`:
   batteries, lances and ordnance, sign-off answer 14) until the end phase. AA (reading): materialising ships return at
   the round start. Exit point: off the right edge with the centre between its ends
   (`via_exit_point`, recorded by `record_exit`); evacuated ships score nothing for the
   attacker (`scores_normally`). Game end: no transport capacity in play (reading for "until
   victory conditions are met") or a fleet gone. Victory (`winner`): attacker 8 capacity
   destroyed and 50% of the defender's points in VP; defender 5 capacity and 25% of its
   points (uncrippled) via the exit point; one met wins, else the most capacity destroyed /
   evacuated, the attacker on a tie. AI: convoy ships (capacity x `CAPACITY_WEIGHT` 0.05 x the
   points on the table + their points) and uncrippled warships while the 25% is short
   (`WARSHIP_EXIT_WEIGHT` 0.25 x points) run for the exit point (`_exit_value`, `_convoy_run`,
   exit-point move goals); the attacker's kill bonus is the capacity value; a warp rift's loss
   costs a ship's value plus its kill bonus (`ai_hazards.lost_ship_vp`; an attacking ship
   0.1 x its value, it comes back). Not yet: players placing the rifts and choosing the
   return anchor / spot in dialogs, secret deployment, the 13th Black Crusade daemonship
   variant.
   Fixed on the way (general): AI moves never took asteroid field / warp rift navigation
   tests or dust cloud contact (the flags were set and left);
   `terrain_effects.resolve_post_move_terrain` now resolves them for the AI and the human
   move dialogs alike.
   Destroy the Docks built (p.99, `src/destroy_docks.py`): no other phenomena, a large planet
   at the centre, one asteroid field each outside the 30cm gravity well (judgement: the
   attacker's across the reinforcement approach above the planet, the defender's between the
   left force and the planet); the defender's free assets added at set-up (2 Space Stations,
   an Orbital Dock, a Defence Monitor, 2 System Escorts, 4 inner and 4 outer satellites,
   judgement mix: 2 weapons platforms, a laser, a torpedo launcher each; reading: they score
   their normal VP) and its fleet held in reserve; the free fleet commander re-roll on its
   flagship (reading); the attacker split into two forces as equal as possible (dearest first
   to the smaller), each within 10cm of its short edge; dock / stations / inner platforms /
   escorts / monitor in the gravity well, outer platforms anywhere (`placement_errors`,
   `auto_positions` on rings round the planet); 8 orbital mines laid as mine markers on a
   20cm ring at the start of turn 1 (`lay_orbital_mines`, active at once), 5 VP to the
   attacker each when removed (`mines_removed`, Support Assets); first turn by 2D6 v D6; the
   reinforcements roll a D6 each at the start of the defender's turn (5+ / 4+ / 3+ by the
   slowest speed, +1 per two failed turns, `arrivals`), entering from the top edge; 8 turns;
   the attacker wins by destroying both stations, the dock, every inner platform and 25% of
   the reinforcements' points (`attacker_won`; reading: destroyed ships only), else the
   defender; `force_errors` warns about defending battleships. AI: those targets carry a kill
   bonus (`target_bonus_vp`, `TARGET_WEIGHT` 0.5 x the points on the table shared out,
   judgement). Not yet: players choosing the satellites and the inner / outer split and
   placing the asteroid fields, the alternating set-up order, orbital mines as a general
   support asset (only this scenario lays them), the 13th Black Crusade framing.
   The narrative Convoy built (p.94-95, `src/convoy_narrative.py`, mode `convoy_narrative`):
   the attacker's built fleet is replaced by the random force (reading; its main faction kept):
   2 + one per 2 transport capacity D6s, 1-3 that many clusters (judgement: alternately
   deadfall torpedoes and attack craft), 4 / 5 an escort squadron up to 100 / 150pts, 6 a
   capital ship up to 200pts (judgement picks: the escort class giving the most points within
   the limit, the dearest capital ship; unique, immobile and convoy ships excluded), held off
   the table; one contact marker each, 30cm apart and from every edge (judgement: a 30cm grid
   from the centre out, doubled up when full); the defender's entry edge by a D6 (reading:
   1-3 left, 4-6 right), the entry point midway between the long edges; the defender goes
   first and moves on from it (all its ships wait off the table and arrive at the start of
   its turn; up to half its ships by count may wait for its second turn, `wants_arrival`;
   the AI never holds back). A marker activates when a defending ship comes within 30cm
   (sign-off answer 6: along its actual path, turns included, `record_path` from
   `movement.execute_movement`, `check_activation`), deployed after the defender's movement phase (`end_of_defender_
   movement`): deadfall torpedoes a strength D6+2 speed-30 salvo, attack craft D3+1
   squadrons (judgement: half fighters, the rest bombers, one close wave at the nearest
   defender), ships on the marker facing the nearest defender. The attacker activates one
   marker at the start of its turn, two if a defending ship is on special orders
   (`attacker_turn_start`, judgement: always, nearest the convoy). Game end: no convoy ships
   left (on the table or to come), or the attacker spent (no ships, markers or ordnance): the
   defender wins if any capacity escaped or is left. Result by capacity off the far short
   edge (rounded down): 0 attackers win, 1 attackers marginal, 2 convoy marginal, 3+ convoy
   win (`result_text`). AI: convoy ships run for the far edge (capacity x `CAPACITY_WEIGHT`
   0.1 x the points on the table, at least 300, judgement), the attacker's kill bonus is the
   same. Not yet: players choosing the clusters' mix, marker spots and deployments
   (dialogs), the escort squadron's formation choice, hiding markers' contents from a human
   defender (they're drawn as "?" but the log names them), the Gauntlet variant.
   Low orbit built (s.39, `src/low_orbit.py`; sign-off answer 1): the low orbit table is a
   separate area of the engine's coordinates (x 0-120, y 10000-10060, judgement: 120 x 60cm;
   far from the main table so nothing reaches across), its top edge the planet edge; the
   board draws it as a strip above the main table (`BoardView.cm_to_screen` maps it, clicks
   map back). A ship in the planet's gravity well at the start of its turn may enter
   (`can_enter` / `enter`: a human is asked, `GameState.low_orbit_hook`; the AI by
   `planet_scenarios.wants_low_orbit`), placed touching the edge furthest from the planet
   (Remastered p.116, proposed; owner to confirm) facing along the planet edge (reading:
   left or right by its heading; facing the planet a 45-degree ship couldn't climb away
   before falling), at an x for its
   side of the planet (judgement). In low orbit (`in_low_orbit` rule): no minimum move, no
   turning distance (`movement.get_effective_speed` / `validate_movement`), gunnery one
   column right (`combat.get_column_shifts`), lances and nova cannon fire only on a 4+
   (`resolve_lances`, `resolve_nova_cannon`), no torpedoes or mines (barrage bombs allowed;
   `ordnance.launch_torpedoes` / `lay_mines`, the launch dialogs); ordnance can't leave
   (`marker_off_bounds`). At the start of each player's turn ships within 45cm of the
   planet edge fall 5 / 8 / 10cm by planet size (`falling`), off it destroyed; off the planet
   edge voluntarily escorts and transports land (disengaging), capital ships stop at the
   edge (reading); off any other edge a ship returns to high orbit touching the planet
   template (on the side its x stands for, facing out, reading), never in the turn it
   entered (it stops at the edge, reading) (`handle_move_end` from
   `movement.execute_movement`; off-table checks by `bounds_for` / `off_bounds`).
   Exterminatus! and Planetary Assault built (p.101-102, p.105-106,
   `src/planet_scenarios.py`): the planet by D6 (1 small, 2-5 medium, 6 large; radii 3 / 5 / 8
   as elsewhere) with its near edge 150cm from the attacker's (right) short edge, centred
   (reading of the drawing); other planets removed; attacker within 15cm of the right edge;
   roll-off for the first turn. Exterminatus!: one Exterminator per 1000pts or portion
   (judgement: the ships with most hits; the Planet Killer or an Activated Blackstone counts
   alone), prow weapons removed (`_is_prow`) except Space Marine battle barges (virus bombs)
   and Inquisitorial Cruisers with torpedoes, which need 3+; one patrol per 500pts or portion
   (judgement: the cheapest units) in reserve, arriving on 5+ / 4+ / 3+ by speed from a D6
   edge (1 left, 2-3 top, 4-5 bottom, 6 right, `patrol_arrivals`); the defender more than
   30cm from the edges; each Exterminator in low orbit within 45cm of the planet edge rolls
   at the start of each attacker's turn (reading: "each turn" as the attacker's) to destroy
   the planet (`exterminatus_rolls`); defenders may treat Exterminators as the closest enemy
   (`priority_free`, AI and Fire dialog); ends on the planet destroyed (attacker wins), every
   Exterminator destroyed (defender wins) or a fleet gone (holding the field). Planetary
   Assault: the defender's dearest half on alert in the gravity well, the rest on patrol 30cm
   from the edges (judgement; the attacker placing patrols on 1-3 isn't built); 2 transport
   capacity per 500pts or portion (`force_errors`); at the start of the attacker's shooting
   phase each capital ship / convoy ship within 30cm of the planet edge may assault
   (`shooting_start`, a human via `GameState.assault_hook`, the AI always): 2 x its capacity
   (capital ships at least 1/2) in assault points, no shooting / launching / teleporting that
   turn (`has_fired`); escort convoy ships landing score that turn (`record_landing`); ends at
   10 points or a fleet gone; result: points + 1 per full 500 VP of the attacker - 1 per 500
   (or portion) of the defender, + a final score for each uncrippled attacking capital /
   convoy ship on the table when it holds the field (reading: wherever it is), 0-1 / 2-5 /
   6-9 / 10+ (`assault_total`, `assault_result`). AI: `_planet_term` (high orbit: close on the
   gravity well with a planet objective; low orbit: end within 45 / 30cm of the planet edge,
   never where the two falls before its next move, or the round after even climbing its best,
   take it off the edge), `_low_orbit_exit_score`, Exterminators' and assault ships' kill
   bonuses (`planet_scenarios.kill_bonus_vp`), defenders' stake against disengaging. Not yet:
   barrage bombs' assault points, the defenders' extra planetary defence points, the
   biosphere choice, high orbit's free turns towards the planet, the low orbit defences,
   the attacker placing patrols.
   Status: 25 booklet scenarios play end to end for humans and the AI, in IGOUGO and AA: the
   nine matched-play ones, Cruiser Clash, Chance Encounter, The Bait, The Raiders, Blockade
   Run, Rearguard Attack, Alien Intervention, Surprise Attack, Fleet Engagement, Escalating
   Engagement, Navigate the Storm, Destroy the Docks, the narrative Convoy, Exterminatus!,
   Planetary Assault
   (`tools/gui_checks/gui_spectator_scenario.py igougo|aa <scenario> [subplots]`; Domination
   also `gui_spectator_domination.py`). Still to build (largest first): the campaign set pieces (Defence of Pelucidar, Macharia's End,
   Craftworld Assault) and variants (Parol's Bait, Daemon Blockade, The Gauntlet); the rest of
   the sub-plots (Blood Bond, Fleet Experience, Signaling Problems effects; Unexpected Help,
   Decoy, Fresh Captain's objective; faction sub-plots) and their AI beyond kill bonuses.
   Smaller gaps: racing Domination's 10 against the turn order; reinforcements entering along
   the long edges after turn 1 and choosing them / The Bait's pursued unit / Surprise Attack's
   full-alert units in the set-up dialogs; Alien Intervention's drifting hulk; alternating
   deployment (Cruiser Clash, Fleet Engagement); the scenarios' extra planetary defence
   points and forces limits (fleet building: the Ambush / raid attackers' half points, Line
   Breaker's "platforms can't squadron", Cruiser Clash's 185pt cruisers); Planet Strike's
   "extra assault points" ships; Orbit Lost; off-table entry (The Raiders / Rearguard /
   Surprise Attack attackers deploy touching the edge instead).

8. Matchup-aware manoeuvre (owner ideas; "do not take these as hard rules, it depends on the
   matchup": each should come out of the expected-VP move score, not a fixed doctrine).
   Ship facts checked in the catalog: Lunar speed 20, 6+ prow / 5+ sides, port and starboard
   30cm batteries and lances that don't overlap; Chaos Murder / Carnage speed 25 with 45-60cm
   batteries and 60cm prow guns (the Slaughter is fast but 30cm: a brawler, not a kiter); Tau
   Protector speed 20, 6+ prow, railguns / ion cannons all bearing forward (L/F, R/F, F).
   Plan:
   a. First, a shared prerequisite: exposure should respect our Armour facing. Built:
      `ai_hazards.mount_hits(e, w, t)` (batteries 0.35 a point vs 5+ scaled to the Armour
      facing the enemy would hit, `Ship.armor_vs` from its position at our end heading; lances
      0.5 whatever the Armour), used by `position_exposure_hits` and `enemy_fire_plan` (so
      `incoming_hits`, disengaging and the move score's exposure). Prow-on to an enemy
      broadside (6+) is half as exposed as side-on (5+) (`tests/test_ai_focus.py`). Not yet:
      the enemy's next move changing the facing it sees (8 g), our own guns' values by the
      facing they hit (they use the target's lowest Armour).
   b. Built, first form: `_mount_coverage` adds `COVERAGE_WEIGHT` 0.5 (judgement) x the
      battery / lance strength at the end position that can't bear on the target but can on
      another enemy in arc and range (now, not yet their predicted positions); squadrons
      don't plan one heading together yet.
      Both broadsides busy (gun-heavy Imperium, e.g. Lunars; "crossing the T"): replace the
      move score's single-target arc score with a fleet-aware mount coverage score at the end
      position: each battery / lance mount scores the best expected VP it could add next
      shooting phase among enemies in its arc and range (the enemy's predicted positions,
      `_predicted_positions`), so a position with a target off each beam scores both
      broadsides, one with everything off one side scores one. Crossing the T then comes out
      of (a) + (b): across the enemy's line of advance our broadsides bear while only its prow
      guns bear back on us. Cost: per candidate move x mounts x enemies (cheap). Squadrons
      should plan together (one heading for the squadron, s.8).
   c. Built, first form: `range_speed_edge` (longer gun reach and at least the enemy's
      speed) and `_kite_bonus` (`KITE_WEIGHT` 0.5 x the guns that bear, judgement, at end
      positions in (its range + its speed, our range]); not yet: the table edge and turning
      to keep a broadside on a closing enemy. Kiting (Chaos and other long-range / fast
      fleets): a matchup check, `range_speed_edge`:
      our guns' firepower-weighted range and speed vs the enemy's (on average, per owner). With
      an edge, the move score prefers end positions where we can fire next shooting phase but
      the enemy, after its own move, mostly can't (distance in (enemy range + enemy move, our
      range]); this is (a)'s exposure at full weight instead of half, plus a band bonus. No
      edge (or a brawler like the Slaughter): close as now. Watch: the table edge (kiting
      backwards runs out of table; disengaging off it concedes VP), and turning to keep a
      broadside on a closing enemy.
   d. Tau prow-on (forward-firing ships with the best Armour in front, e.g. the Protector):
      falls out of (a) + the move score: when the enemy will be in range after its move, ending
      prow-on keeps the 6+ front facing it and every gun bearing; while it is out of reach any
      heading is fine (no exposure), so the ship can manoeuvre freely and turn in only as it
      closes. Turn angle matters (Protector 90, Hero 45: owner).
   e. Tests: a Lunar pair placed so one position has targets off both beams scores higher
      than one with both off one side; a Murder squadron facing Lunars holds the 30-45cm band;
      a Slaughter facing Lunars closes; a Protector ends prow-on when the enemy will reach it
      and is free otherwise. Then AI-vs-AI games for each faction pair.
   More owner notes (fleet strategy; same caveat: matchup-dependent, not hard rules):
   f. Firepower by range bracket, on average (fleet vs fleet) and ship vs ship: e.g. a Tau
      Merchant Starship (6 battery points of railguns, all 45cm and bearing forward; speed 15,
      6 hits, 5+) out-guns a Lunar (all 30cm: 6 battery points + 2 lances a side, 6 torpedoes
      forward) at 30-45cm but not at 0-30cm. Plan: a matchup table per pair of ships, the
      expected VP each does to the other per shooting phase in brackets 0-15 / 15-30 / 30-45 /
      45-60 / 60-150 (in-arc mounts, the Gunnery table's range shifts, armour, shields), summed
      for the fleets. Owner: 0-15 is its own bracket mostly because of Ork Heavy Gunz (unique to
      Orks: batteries with a bigger `strength_close` value within 15cm, e.g. Kroolboy, Savage
      Gunship, Gorbag's Revenge; the Gunnery table also shifts every battery one column left
      within 15cm); 45-60 is its own bracket (Chaos 60cm batteries and lances); 60-150 is for
      artillery such as the Nova Cannon (150cm, 30cm minimum: it can't fire at ships closer
      than that). The move score then prefers the bracket where our guns beat theirs, for each
      ship against what it faces. Kiting (c) is the case where we also out-move them; the
      Merchant is slower than a Lunar (15 vs 20), so it can't hold the bracket against a
      Lunar that wants to close: it takes the bracket when it can and positions to delay.
      Built (the table; its use in movement waits for 11 a's range-band goal and 8 c, per
      "compute, don't script"): `ai_hazards.RANGE_BRACKETS`, `bracket_matchup(a, b)` (ship vs
      ship) and `fleet_bracket_table(gs, player)` (fleet vs fleet, each side's fire spread
      evenly, each target's shields taken once), `best_bracket`. Per bracket at its middle
      distance: batteries on the real Gunnery table with the range shifts and Heavy Gunz'
      close value (`combat.expected_hits` on an empty table), lances 0.5, the Nova Cannon by
      its own rules (`nova_expected_hits`: 1/3 direct hit for D6, else 1-3D6cm scatter, D6
      on the centre hole or 1 on the template, 30-150cm), averaged over the target's facing
      with the shooter turned to bear its best guns; shields by `past_shields` (E[max(0, H -
      shields)], H Poisson: a ship averaging below the target's shields still gets some
      through). Ordnance isn't counted. Checks: the Merchant beats a Lunar only at 30-45cm,
      a Murder at 30-60cm, a Dominator's Nova Cannon alone reaches 60-150cm
      (`tests/test_ai_range_brackets.py`).
   g. Speed (and turn angle) edge, on average and ship vs ship: out-moving an enemy, get out
      of its main fire arcs, e.g. into a Lunar's rear arc where neither broadside nor prow
      bears. Plan: per enemy, the arcs its mounts can bring to bear after its next move and
      turn (`_mount_bears` with its own speed and turn angle); with a speed edge, end positions
      outside all of them score the exposure saved; this is (a)'s exposure looked one enemy move
      ahead. Without the edge it is mostly unreachable, so the term does nothing.
   h. Ramming built too: `ai_hazards.ram_vp` (resolve_ram's dice both ways: the rammer's
      starting hits vs the struck facing, the target's back, half unless head-on, vs our prow;
      shields stop neither), `_ram_candidate` (an enemy dead ahead on the All Ahead Full line,
      reachable with the lowest bonus roll, at the ram Leadership test's 1D6 / 2D6 / 3D6 odds,
      Goffs auto-pass), counted in `_aaf_gain`; `_declare_ram` after the AAF check and before
      the speed roll, `_resolve_ram` after the move (only with `rule_ramming` on). Not yet:
      Hull Krusha's automatic hit, aiming a turn earlier to set up a ram.
      Boarding built: `ai_hazards.boarding_vp` (both D6s enumerated with
      resolve_boarding's modifiers: troop ratings, crew bonuses, crippled / orders / blast
      markers; the loser's damage by `hull_hits_vp`, crits by the s.32 table at a hit's value,
      judgement; grapples count nothing), `_boarding_gain` (that less the guns' value given
      up), a "board" move goal (base contact on our side of the target), `_boarding_reach` in
      the move score, `_consider_boarding` declaring after the move, and boarded ships
      neither fire nor launch (s.32); all only with `rule_boarding` on. Not yet: rams (s.12,
      on All Ahead Full: built above), combined boarding by several ships, Knights of Titan / Mechanicus
      re-rolls in the value.
      Hit-point edge (e.g. Ork cruisers: 10 hits vs a Lunar's 8): think about boarding (s.32)
      and ramming (s.12). Today the AI never plans either: boarding only happens when ships
      end in base contact by chance, and no AI move aims for contact. Plan: expected VP of a
      boarding action (`boarding.troop_rating` both ways, crew bonuses, the s.32 result table)
      and of a ram (s.12 hits both ways, the Leadership test) as move candidates ending in base
      contact / ramming the target, compared with the gun value of the alternatives; Orks also
      get the boarding bonus and Ere We Go speed. Same caveat: it depends on the enemy's hits,
      turrets, crew and whether contact is reachable. Only when `rule_boarding` /
      `rule_ramming` are on (owner: a disabled rule is neither valued nor attempted).
   j. Teleport attacks (owner: be aware of them, both ways). Rules (s.31, `hit_and_run`): in
      its own end phase a ship may teleport-raid one enemy within 10cm (20 with a Space Marine
      honour guard, which also rolls 2D6 / 3D6 keep best), if not crippled, on no special order
      but Lock On / Reload Ordnance, the target's shields down, and the target no more
      remaining hits than it; escorts / defences under 3 hits can't; Tau and Nicassar never.
      Faction rules: Space Marine Teleport Assault, Ordo honour guards, Chaos Champions /
      Terminators, Ork Soopa Tellyporta. An optional rule (`GameState.rule_teleport`, off by
      default). Done: the AI decides its own teleports (it used to get the human's dialog in
      its end phase): it raids the eligible target worth most per raid
      (`waves.raid_squadron_value`; `end_phase_panel._resolve_teleport_attacks`;
      `tools/gui_checks/teleport_ai_check.py`). Also done: (2) defence, `_teleport_exposure`
      (a move ending within an enemy teleporter's range + its move, when we have no more
      hits left than it, pays the raid's expected VP x the chance our shields are down:
      certain with blast markers at the end point covering them, else
      `TELEPORT_SHIELDS_DOWN` 0.3, judgement); (3) the brace against a teleport,
      `ai_should_brace_vs_raid` (half the raid's value saved vs half the ship's fire); (1)
      offence, first part, `_teleport_reach` (a teleporter's move gains the best raid within
      its teleport range of the end point, on targets with no more hits left than it, x the
      chance their shields are down: 1 if down, 0.6 if our fleet's guns this turn should put
      at least that many hits on it, else 0.1, judgement; only off orders other than Lock On
      / Reload). Still to do in (1): choosing gunfire targets to open shields for a teleport.
      Original plan: (1) offence: move teleporters to end
      within range of a target whose shields our guns will knock down this turn (the shooting
      planner's shield hits / blast markers), with remaining hits at or below ours, staying
      uncrippled and off orders other than Lock On / Reload Ordnance; value it at the raid's
      expected VP in the move score, and choose targets for gunfire that open shields for a
      teleport; (2) defence: our ships' moves pay the expected raid VP of ending within an
      enemy teleporter's range after its move when our shields may be down by its end phase
      (blast markers touching us, the enemy's guns) and we have no more hits than it; keep
      shields up (stay off blast markers), keep distance, or out-hit it; (3) the AI's brace
      against a teleport uses the raid's value, not "fewer than 6 hits"; (4) Ork Soopa
      Tellyporta and Chaos Terminators' own rules when those options are built. All of it
      only when `rule_teleport` is on, for us and for the enemy (owner: a disabled rule is
      neither valued nor attempted).
   i. Carriers: the carrier doctrine already built (see "AI: how it decides": air supremacy,
      protecting carriers when out-carriered, strikes outside the enemy's umbrella, reactive
      intercept, co-ordinating bombers with missiles) is part of the same matchup picture.

9. Smaller "Not yet" notes from the sections above, collected so none is lost (details in each
   section): Auto (best) prompts are all done; bombers that re-roll their attacks (+1 when suppressed)
   and resilient squadrons stopping / splitting (Waves); fleet lists: more than one
   detachment, "no more reserve copies than its own list could field", reserve-only refit rules
   (Fleet lists); designing a Venerable Battle Barge (Fleet lists); Rogue Trader refitted
   torpedoes, Deathskulls' half-cost looted torps, Ork zzapp gunz swaps (Torpedo types); attack
   craft flying straight without a target and torpedo-vs-torpedo collisions checked only at the
   end of the move (Engine notes); AI: Ork random-firepower batteries in squadron volleys and a
   volley needing a target priority test, hulks that aren't the closest target and Holding the
   Field hulk points, the target turning to show its strongest facing to a turning salvo,
   assault boats and mines in co-ordinated strikes and re-timing a launch to arrive together
   ("AI: how it decides"); AI special orders: see To do 10; deployment by strategy (ships are
   only grouped for set-up). Built: which blast markers the player whose turn it is removes
   (`end_phase.remove_blast_markers`: those nearest its own ships' next moves and furthest
   from the enemy's, within a ship's speed + 10cm, judgement);
   damage-control repairs by expected VP when no choice is given (`ai_hazards.repair_value`
   in `end_phase.resolve_damage_control`: a fire 1.5 hits, armament the threat of its weapons
   as if repaired (`armament_threat_value`), collapsed shields the enemy's expected hits they
   would stop, engines / thrusters / bridge judgement shares; the fixed order breaks ties;
   `tests/test_repair_value.py`).
   Items already in 2-8 aren't repeated here (Ork Extra Turrets, Ork
   Bosses' re-roll pools, secondary commanders and Ordos are in 4; the radiation / flare
   disengage bonus is in 6; the teleport AI's positioning is in 8 j).
   Remastered escort squadron VP: built as an Advanced checkbox
   (`GameState.rule_remastered_escort_vp`, `victory_points._score_squadron(..., remastered)`;
   Remastered PDF p.121): only a squadron destroyed entirely scores; nothing for a crippled
   squadron left on the table; disengaged, 25% of the whole squadron's value if crippled (half
   its ships lost, rounding up) before leaving, else 10% ("total points value" read as the
   full original squadron: unconfirmed). AI (`ai_hazards._remastered_escort_terms` in
   `disengage_gain`): staying risks the squadron's value only if every survivor dies, leaving
   concedes 25% / 10%, so a crippled squadron stays unless it is likely to be wiped out. XR,
   the default, is unchanged (`tests/test_remastered_escort_vp.py`).

10. AI special orders by expected VP (owner notes). Rules: orders are declared in the movement
   phase before each ship or squadron moves, one at a time (declare, command check, move;
   s.7), and the first failed command check ends all further checks that turn (s.2; movement-phase
   orders only, it never blocks a later Brace, see e); Lock On
   re-rolls missed battery / lance dice but the ship may not turn; Burn Retros: no minimum
   move, turn at once, at most half speed, half firepower; Come to New Heading: an extra
   turn, half firepower (not Ponderous ships); All Ahead Full: +4D6cm, must move it all, no
   turn, half firepower (ramming, s.12); Reload Ordnance: reloads all ordnance. Today: Burn
   Retros when the hazard saved beats half the firepower value; otherwise Lock On whenever an
   enemy is in a battery / lance arc and range NOW (wrong moment: the move comes after the
   order); otherwise Reload Ordnance when spent; never All Ahead Full or Come to New Heading;
   ships take their checks in fleet order (that was the state before this item; see "Built so far"
   for what each order does now). Owner notes and plan:
   Built so far: a (`_lock_on_gain`), c (`_plan_orders`, the skip rule; not yet re-ordering
   the checks, which would break the support move order), d (a failed check's re-roll counts
   the later orders it unblocks, `importance(..., {"blocked_orders_vp"})`), f's modifiers in
   the pass chance, g (Burn Retros pays half the best teleport raid in reach,
   `_teleport_given_up`), b's All Ahead Full (`_aaf_gain`). Not yet: e. Built: Come to New
   Heading (`_ctnh_moves`: a first leg of the turning distance and a turn of half or all the
   turn angle either way, then a normal one-turn candidate from there; `_ctnh_gain` as AAF's,
   in-range guns halved, at the pass chance; e.g. a Tau Protector with an enemy close behind
   turns twice; the expert's root moves stay one-turn under it, not yet two). Built: Reload Ordnance by value (`_reload_value`: next turn's strike or CAP
   for spent bays, the salvo's expected hits on the nearest enemy in reach for torpedoes at
   `phase_weight(2)`, mines half a hit a launcher, the Armageddon Gun; weighed against Lock On /
   All Ahead Full in VP; with nothing better a spent ship still reloads, it costs no firepower).
   a. Lock On is worth it when an enemy WILL or CAN be in arc after the move: value = the
      best straight move under Lock On (no turn), its guns' expected hits at the next
      shooting phase against the enemy's predicted positions with missed dice re-rolled,
      minus the best move without the order (which may turn to bring more guns to bear).
   b. Every order the same way: its expected-VP gain over the best no-order move, using the
      moves the order allows: Burn Retros (hazard avoided, holding position or a tight turn),
      Come to New Heading (two turns: e.g. into a rear arc, 8 g), All Ahead Full (closing for
      a ram or torpedo reach, escaping, disengaging; 8 h), Reload Ordnance (next turn's
      launch, as `_hold_bays` values it), each with its firepower cost.
   c. Prioritise: a failure ends the turn's orders, so the order of the checks matters. Each
      candidate has a gain g and a pass chance p (Ld, crew modifiers, blast markers / Bridge
      Smashed, a commander re-roll); take them in the order that maximises the expected total
      (best first by g x p / (1 - p)), and skip a low-value order whose failure would cost
      more of the later ones than it gains. Squadrons test once for all their ships.
   d. Commander re-rolls on a failed check are worth the order plus the later orders the
      failure would block (`ai_rerolls.should_reroll` should count them).
   e. Brace for Impact stays a reaction during the enemy's attacks (any time before damage is
      rolled), with its own value; note that bracing ends Lock On's re-rolls and halves fire.
      Rules (s.7, XR p.21; feedback 1a-b): a failed movement-phase command check does NOT
      block Brace, so (c) must not treat it as blocking braces. A failed brace blocks only
      that ship, and only until the attacker (ship, squadron or ordnance marker) has finished
      all its attacks; other ships may still brace. A ship decides separately against each of
      an attacker's weapons (it may brace against the lances after not bracing against the
      gunnery) but attempts only once per attacker per turn: once per hazard, so a ship that
      fails to brace against a ship's macrobatteries can't brace when that ship then fires its
      lances (owner). Engine (checked): `CombatPanel._brace_before_attack` records a failure in
      `Ship.brace_failed_vs` by attacker key (the attacking ship's id; "asteroid_field", the
      rammer, the exploding ship for `combat.offer_brace`), cleared in the end phase, and asks
      again after a decline; a passed brace lasts to the end of the ship's next turn. AI fire
      asks before each weapon (`AIPlayer._offer_brace(ship, target, weapons)`; a squadron
      volley once with its expected hits), so a player who declines against the batteries is
      asked again before the lances (`tests/test_brace_timing.py`). The human Fire dialog fires
      batteries, then lances, then the nova cannon (`combat_dialog._FIRE_ORDER`) and asks the
      targets before each kind; each kind's hits are applied before the next question, so hits
      rolled before the target braced get no save (a hulk still takes the whole volley at once;
      `_apply_volley_damage`, `tools/gui_checks/brace_check.py` case 3).
   f. Command check modifiers (s.6) in every order's pass chance: Enemy Contacts +1 Ld if any
      enemy ship is on special orders, Under Fire -1 with blast markers in contact, Ld 0-10;
      command checks only, not Leadership tests. Both directions matter (our orders make the
      enemy's checks easier).
   g. Teleport-capable ships: an order other than Lock On / Reload Ordnance gives up the
      end-phase raid (s.31), so its value counts against that order.

11. AI design feedback (owner, on docs/AI_DESIGN.md; items tagged Rules / Owner / Suggestion
   in its priority order; Suggestions are the intended direction, raise them with the owner
   if they conflict with something already decided; the owner's later notes on
   target-directed movement candidates replace its 15-degree heading steps, see a). Checks done this session: gunnery values
   subtract shields (`ai_player` `added_vp` / `ai_should_brace` use `current_shields`);
   `damage_vp`'s per-hit term is 0.2 x points / starting hits (`value_per_hit`); Ork turrets
   hit on 5+ (`ai_hazards`, `waves`) and fire at everything (`turret_split_gain` gives no
   split gain); mines in the hazard model move 10cm toward the nearest enemy vessel of the
   layer in each ordnance phase (`marker_hits`), and the engine's mines home on the layer's
   enemies only (`ordnance.move_ordnance`). Gap found and fixed: the mine hazard counted 8D6 flat,
   ignoring the turret roll that cuts it to 4D6 (now `ai_hazards.mine_attack_dice`).
   To build:
   a. Movement candidates (owner). Rules for every candidate: capital ships turn right after
      the turning distance (battleships 15cm, cruisers 10cm; s.10, before modifiers), just
      after the minimum move (half speed) or at the end of the move (separate rules: a 20cm
      cruiser 10 / 10cm, a 25cm cruiser 10 / 12.5cm); escorts anywhere, including at the very
      start; Burn Retros needs no movement before turning; only forward movement this phase
      counts toward the turning distance; any angle up to the maximum is legal. Distances from
      the minimum move (50%, kept: ending as short as legally possible often keeps a ship out
      of enemy range) to full speed; a ship moving under 5cm counts as Defences on the Gunnery
      table (s.10), which matters for Burn Retros.
      Target-directed candidates (owner; supersede the earlier "every 15 degrees, ~150
      candidates" plan, which stays only as the fallback grid). Candidates propose, values
      decide (owner caveat: not hard rules, it depends on the matchup). Why: scoring is the
      expensive part, and 1-3 targets x a handful of goals is about 20 candidates against ~150
      evenly sampled for a 90-degree ship; useful end positions are often narrow (a 10cm range
      band, a rear-arc slice, the one heading with two enemies in one broadside), which goals
      hit by construction; cost scales with targets and goals, not with the turn angle.
      1. Building one: pick a goal, then solve for the turn point, angle and distance that end
         closest to it (geometry where possible, e.g. head for a point and clamp the angle to
         the ship's limit; else a short 1-D search over turn point and distance). Out of reach
         this turn: the closest move, kept as a "progress towards" candidate.
      2. Goals per target (1-3 targets: the focus target plus the next one or two by expected
         VP; only goals relevant to the ship's weapons and situation):
         a. bring the best weapons to bear: target in the arc and range of the weapons worth
            most expected VP (broadside ships the broadside, Tau and prow-heavy ships the prow);
         b. range band: we move and shoot, then the enemy moves (up to its speed) and shoots,
            so the safe band is our range >= d > their range + their speed (Chaos 60cm guns vs
            Imperial 30cm on 20cm ships: 50-60cm; 45cm guns on 20cm ships have none against
            60cm, 45 + 20 = 65); with no safe band, the distance where our damage now minus
            theirs next turn (the exposure term) is best;
         c. Armour facing: closing without firing, end prow-on where the prow has the best
            Armour; firing this turn, turn to unmask at the end of the move (8 a values the
            trade-off, e.g. 5+ side vs 6+ prow);
         d. out of the target's arcs: its rear or a blind arc (a Lunar's rear, 8 g), from its
            predicted position after its next move (the course prior);
         e. torpedo and ordnance lines: target in the launcher's arc on a clear lane (the
            torpedo planner's lead and hazard logic);
         f. teleport, boarding and ramming reach, only where those rules are on and valued
            (8 h, 8 j);
         g. Lock On next turn: Lock On forbids turning, so a ship likely to want it next turn
            ends pointed so a straight move keeps the target in arc.
      3. Goals not tied to one target: two enemies in one broadside or one in each; fleet
         support (base contact with the commander's ship or a carrier for massed turrets, the
         screening rule; squadron coherency); safety (the tangent past a hazard: asteroid
         field, cloud, blast markers, mines, incoming salvos; out of the most dangerous
         enemies' arcs); disengaging for crippled ships (toward a celestial phenomenon within
         15cm, +3 Ld s.37, or the nearest table edge); scenario objectives (To do 7) once
         built.
      4. Fallback grid: a small even set (straight plus a few headings at the turn limit, at
         the 3 turn points, minimum and full distance) for moves no goal predicted; ships with
         90-degree turns or special turning rules get more fallback headings and more
         variations round each goal (owner: more thinking time beyond the 45-degree baseline).
      5. Efficiency: score goal candidates first, prune with the cheap terms (guns that bear,
         hazards), full exposure only on the best ~20; deduplicate candidates ending within a
         small distance and angle of each other; in the expert search try goal candidates
         first (alpha-beta prunes far more when the best move comes first).
      6. When even sampling wins: crowded fights (targets x goals larger than a coarse grid,
         and capping at 1-3 targets may miss the one that matters); dense hazards or incoming
         ordnance near the ship (the best move is a gap no goal predicts); a small reachable
         area (slow or crippled ships, Burn Retros); caching (grid end positions depend only
         on speed, turn angle and turn rule, so they can be precomputed per class and
         batch-scored; goal candidates are built fresh); goals incomplete or wrong. Target-
         directed wins with few relevant targets, a large reachable area (fast ships,
         90-degree turns, escorts) and narrow useful positions: most of a typical game.
         Hybrid, per ship per turn: (a) always goal candidates for the top 1-3 targets plus the
         small fallback grid; (b) a denser even grid (goals still in) when goal candidates
         would outnumber it, when hazards or incoming ordnance are dense in the reachable area,
         or when the area is small, chosen by estimated candidate count against coverage
         needed; (c) coarse-to-fine: hill-climb the best few from either source with small
         changes to turn point, angle and distance until scores stop improving; (d) anytime
         order: goals, then the grid, then refinement, stopping at the per-ship time budget
         (the expert's alpha-beta move ordering too); (e) diagnostic: log which source (goal
         type, grid, refinement) produced each chosen move; if the grid often wins, a goal is
         missing or wrong, so fix the goal rather than add samples. The crossover points in (b)
         aren't known: measure them in the engine (candidates scored and time per ship against
         move quality), don't guess.
      Dependencies: build 8 a (Armour facing) and 8 f (range brackets) first; goals b and c come
      from them (both built).
      First slice built (`AIPlayer._move_candidates`, scored by `_move_score`, commands by
      `_move_cmds`; the simulators take a turn point, `_simulate_final_pos(..., turn_at)`):
      the even grid (straight, half and full turn each way, at 50 / 60 / 80 / 100% of speed)
      as the fallback; turn points after the turning distance, after the minimum move and at
      the end, and at the very start for escorts and Burn Retros; goal a (guns to bear: the
      end heading searched every 5 degrees up to the turn angle, by the arc score) and goal b
      (range band: the distance along those headings ending nearest the middle of the bracket
      where the ship beats the target most, `_range_band` from `bracket_matchup`, none when it
      wins nowhere). Every candidate passes `movement.validate_movement` and the simulator
      ends where the engine does (`tests/test_ai_move_candidates.py`); `_last_move_source`
      records which source won (diagnostic e). Second slice built: point goals
      (`_head_for`: per turn point, turn towards a point clamped to the turn angle, on for the
      distance left, "progress towards" when out of reach): c prow-on to the target's
      predicted position, d into its rear arc (behind its predicted end, the range band
      clamped to 10-30cm), a second target (guns to bear on the next nearest enemy), 3 fleet
      support (an escort to the commander's ship); hill-climbing refinement of the best three
      (`_refine_move`: +-5 / 2 degrees, +-2 / 1cm, turn point +-2cm, legal by
      `_candidate_validator`, at most 12 steps; it stops right at a hazard's modelled edge);
      a coordination order (`_coordinated_order`: the commander's ship, carriers, other
      capital ships, escorts last, squadrons together, so supporters plan against where the
      supported end); the expert search's root uses the candidates, best first by the move
      score, at most `ROOT_MOVES` 12 (judgement). About 32-37 candidates, ~40ms a ship with
      refinement. Also built: goal g ("lock on next": the end heading that keeps guns on the
      target's position after two of its moves from a straight move at speed) and the denser
      grid (hybrid b: a quarter of the turn angle steps at three distances and every turn
      point when two or more enemy markers / phenomena are within the move + 30cm or blast
      markers within the move). Goal e (torpedo lanes) is covered for prow launchers by
      prow-on (the torpedo planner picks the lane at launch). Also built: goal 3's safety
      (`_safety_goals`: for the three nearest hazards ahead in reach, a point either side
      clear by the base and 3cm, flown by `_head_for`) and disengaging (`_disengage_spot`, a
      move-score term, see 11 c). Not yet: goal f (teleport /
      boarding / ramming reach, with 8 h / 8 j), pruning by cheap terms (not needed at ~40ms a ship). Coordination pass built
      (one round): `_coordination_plan` plans every ship greedily in move order (no orders,
      the normal planner), then each real move is planned with the ships still to move standing
      at those planned ends (`_ships_at`, restored after); more rounds not yet.
      Then a coordination pass over the fleet (suggestion): moves are greedy in fleet order, so
      each ship ignores ships still to move; re-optimise each against everyone's planned end
      positions (coordinate descent, one or two passes), which catches screening and mutual
      support.
   b. Expert AI hazards (suggestion, high): it plans movement without hazards, so it can fly
      into an asteroid field (Ld test or D6 damage, s.39) or through blast markers. Minimum: the
      path-hazard cost at the root and in its evaluation; better: expected values at chance
      points, or sampled dice. Root part built: each root move pays `move_hazard_vp` along its
      path (mines, torpedoes, attack craft in flight, asteroid fields, warp rifts, clouds, blast
      markers) in the search's units (per point on the table; with a turn limit the slope of
      the chance of winning at the current margin, `lookahead_ai._vp_scale_for`); a test
      shows the expert taking a move clear of an asteroid field it would otherwise clip
      (`tests/test_lookahead_sim.py`). Still to do: hazards deeper in the search (the sim has
      no terrain or ordnance), chance points or sampled dice.
   c. Rule effects missing from valuations:
      - Price Brace instead of the 1/4-of-hits rule (owner: the feedback is right that Brace
        has a cost). Built (`ai_player.brace_value`, see "Shooting"); not yet: trying
        against the attacker's weapon where the saving is worth most rather than the first
        one asked about (today greedy: each question counts the attacker's other weapons),
        the special orders a braced ship can't take. Gain: 4+ saves on hull hits from this attack and every later attack until
        the end of the ship's next turn. Because a ship tries only once per attacker, trying
        now also spends the chance against that attacker's later weapons: a failed test leaves
        its lances unbraceable too, while declining now keeps that option, so try against the
        weapon (or the point in the attack) where the expected saving is worth most. Costs
        until the end of the ship's next turn (gunnery, lances and ordnance halved, halved again if crippled; no special
        orders; no firing at all inside an asteroid field, s.39); saves only for hits past
        shields; drop the fixed commander bias (the commander's ship should still brace
        earlier because its loss is worth more, but that comes out of the values).
      - Command check modifiers (To do 10 f).
      - Disengage test (s.37, XR p.38), end of the movement phase: +1 Ld per blast marker
        within 5cm, +3 once for a celestial phenomenon within 15cm (anywhere during a
        radiation burst or solar flare), -1 per enemy within 15cm, enemy ordnance markers
        included; Ld max 10. A failed test: no firing, launching or orders but Brace for the
        rest of that turn. Built: a ship that could gain by trying from somewhere values each
        end position by max(0, `disengage_gain`) there, with the Ld modifiers and incoming fire at
        that position (`_disengage_spot` in the move score; the test is taken at the end of the
        move, s.37), so a crippled ship weighs moving next to a phenomenon against its guns. VP for a non-crippled disengaged ship: 10%
        ("Enemies Scattered", s.38). Check `disengage_gain` uses every modifier.
      - Disengage modifiers (checked): blast markers +1, phenomena / bursts / flares +3, -1
        per enemy ship and enemy ordnance marker within 15cm, Slaanesh -1, max 10.
      - Plasma drive overload: built, `ai_hazards.plasma_ordnance_vp` in
        `death_explosion_vp` (enemy markers removed count for us, ours against us, each at
        P(3D6 reaches it)).
        Plasma drive overload (Appendix 5, 9-11): lance shots at half starting hits at every
        ship within 3D6cm AND all ordnance within the radius destroyed, so an explosion
        protects its neighbours from incoming waves and salvos; `explosion_vp` counts the
        ship damage only.
      - Teleports (s.31): not crippled, Lock On / Reload only, target shields down, within
        10cm, no more remaining hits; no escorts or defences under 3 hits; order valuation
        counts the raid given up (To do 10 g).
      - Mines (done): the hazard model now counts the turret roll that cuts a mine to 4D6
        (`ai_hazards.mine_attack_dice`, innate turrets; massed turrets and the s.28 split
        aren't predicted).
      - Human Fire dialog (done): asks before each kind of weapon (batteries, lances, nova
        cannon), see To do 10 e.
      - Dust clouds (s.39, XR pp.52-54): ships in contact count as having a blast marker in
        all respects; ordnance moving through tests as for blast markers (owner ruling: XR's
        omission is an oversight, Remastered states it; the AI already matches).
   d. Built for each ship's own weapons (`run_shooting_phase` fires batteries, then other
      weapons, then lances); not yet across the fleet's ships or for teleports (8 j).
      Shooting order (suggestion): against shielded targets fire batteries before lances
      (shield-hit blast markers shift later batteries; lances aren't affected); knocking
      shields down also opens teleports (To do 8 j).
   e. End phase and pre-game: damage control by expected VP (s.36, XR p.35: a D6 per remaining
      hit, each 6 repairs one system, dice halved in contact with blast markers; a fire costs
      1 hit per end phase; a weapon is worth its next turn of fire if it will bear; an engine crit what is lost by not
      turning; escorts don't repair; the fixed order stays as the fallback); blast marker
      removal as s.36 states it; first-turn policy (s.2: the roll-off winner chooses to move
      first or second) alongside deployment. Built: damage control and blast marker removal
      by value (see To do 9), the first-turn roll-off (`src/first_turn.py`,
      `GamePanel._first_turn_roll_off` after deployment, `GameState.first_player`; ties
      re-rolled, AI players roll automatically; the AI moves first when its gun reach + speed
      covers the gap between the fleets, judgement; a human winner gets "Auto (best)").
      Not yet: deployment by strategy.
   f. Built: scale-free re-roll bars (`ai_rerolls._bar(left, gs)`: the 45 / 25 / 15 / 10 VP
      bars set for a 1500pt game, `BAR_REFERENCE_POINTS`, scaled by one fleet's worth of the
      points on the table, at least a quarter).
   g. Faction behaviour (suggestion): Eldar (MMS v2.0: two moves, holofields, Fragile, turning,
      own ordnance) and Necrons aren't modelled; the generic AI would misplay them.
   h. Compute, don't script (suggestion): build To do 8 a and 8 f first and see what emerges
      before adding doctrine code (kiting should come out when our best bracket is beyond the
      enemy's reach, prow-on when the prow is the best-armoured facing); matchup weights only
      as functions of measured features (To do 1), so one tuning run covers lists it never
      saw.
   i. Built for movement: Easy picks its move by softmax on the move score
      (`EASY_TEMPERATURE` 2.0, judgement). Not yet: softmax in Easy's targets / orders; Hard's
      coordination pass or tuned weights. Difficulty (suggestion): Easy chooses by softmax on
      expected value with a temperature (human-like mistakes); Hard gets the coordination pass
      or tuned weights.
   Claude's view (not an owner ruling): expected value of the work is rules completeness >
   candidate generation > search with dice > learned evaluation > weight tuning (fairly
   confident of the order, not of the size of each gain); tuning only improves the AI within
   its structure and must be redone after every structural change.

12. Learned evaluation for the expert search (owner: do it; low priority, after To do 11,
   and only after its a-c). On hold until the owner says to start; when built, an experimental
   ML-driven AI kept separate from the current AI, never replacing it. Supervised fitting of position features to game outcomes.
   Features: material, threat both ways, relative geometry (no absolute coordinates),
   ordnance in flight, tempo, state, and terrain by what it does to ships (hazard cost of
   reachable moves, cloud / blast contact, distance to the nearest phenomenon and the table
   edge, cover share, gravity wells, ordnance paths crossing hazards). Owner: the evaluation
   must know about terrain: asteroid fields, gas / dust clouds, planets and gravity wells, warp
   rifts, minefields, drifting and burning hulks, blast markers, table edges and the sunward
   edge, active effects (solar flares, radiation bursts); threat features computed with line
   of sight, in-flight features with the path hazard model; terrain encoded by what it does to
   ships, never by where it lies, so one fit works on any layout. It replaces only the expert
   search's leaf; the normal AI keeps its heuristics. Each logged position is labelled with its
   game's final VP margin; fit by least squares or gradient descent; interactions allowed
   (e.g. 30-45cm firepower worth more against a slower enemy). Fleet size: sum / mean /
   max aggregation first, set-based networks optional later. Baseline to beat: VP margin +
   next turn's expected swing (today's leaf); alternative: rollouts to make labels, then fit
   the fast evaluation. Data: normal-AI self-play across factions, lists, scenarios and varied
   terrain (s.39 random generation), logged after each phase; a few thousand games give about
   100k positions; softmax randomness (11 i) for variety; log the tuning games (To do 1) if
   they run; varied terrain set-ups or it only knows the layouts it saw. Values learned from
   weak play are weak, so iterate fit / play with the improved search / refit. Start only
   after To do 11 a-c (rules fixes, candidates, expert hazards): games under wrong rules or a
   cramped move set teach wrong values.

13. Alternate activation (AA), an optional ruleset outside the booklet (owner draft; the
   order-systems notes are `docs/AA_ORDER_SYSTEMS_NOTES.md`, keep them as the source; the AA
   working notes are `docs/AA_ACTIVATION_NOTES.md`, whose "Idea A" is superseded by the three
   systems; the draft is `docs/BFGXR_Alternate_Activation_Draft.pdf`, 91 matchups in Appendix
   B incl. escort builds, results in section 4 and Appendix C). The booklet stays IGOUGO: never
   put AA into the booklet export or `bfgxr/rules/*.md`. Build three activation-order systems
   as selectable options, all fully playable by humans and the AI, none hard-coded:
   `order_mode` = `fixed_initiative` (System 1, ABFG v0.3: shooting in initiative order highest
   first, movement inverse; ties by Ld, admiral's Ld, fleet strategy rating, a dice-off;
   optional forcing an activation with a re-roll), `bag` (System 2: one die per unit per
   phase, drawn at random, the drawn side picks which unit) and `bag_adjusted` (System 3, the
   DEFAULT selection: owner slightly favours it but hasn't committed; Systems 1 and 2 are not
   stubs, he wants to play and compare all three). Shared definitions: a unit is a capital
   ship or an escort squadron (capital squadrons as one unit configurable; ABFG uses the
   highest Ld and highest hits); unit initiative = Ld - starting hits + 10 (escort squadrons:
   their one Ld and the sum of starting hits; fixed-Ld ships their fixed Ld; a Necron Obelisk
   ship its rolled Ld); fleet mean to one decimal; the gap and the edge holder; recompute
   trigger configurable (`start_only`, `on_unit_destroyed`, `abfg_turn_start` with Ld changes
   and -1 per crippled ship), never from current hits. System 3 band table (thresholds and
   rates configurable): gap < 0.5 plain bag; 0.5 to < 1.5 the edge holder chooses which side
   takes each phase's first activation; 1.5 to < 3 choice + ceil(units / 3) extra dice; >= 3
   choice + ceil(units / 2); "units" is the edge holder's own count. The chosen side activates
   without a draw and removes one of its own dice (every activation spends a die); extra dice
   give no extra activations; passing (`allow_pass`, default on) while a side has more dice
   than units left. The common AA framework (from the AA working notes, `docs/AA_ACTIVATION_NOTES.md`):
   per-phase bags; the
   round Command, Ordnance A, Shooting, Movement, Ordnance B, End; Brace as a command-phase
   order; ordnance 1 move on its first turn, then 2; Eldar use MMS; boarding and ramming lock
   on declaration and resolve in the end phase. Items the notes leave open stay open and
   configurable (shooting-before-movement order, end-phase cadence, "turn = round"). The AI
   values its new choices by expected VP (who goes first each phase, passing, which unit to
   activate on a draw; acting early usually pays in shooting, late in movement: value both,
   don't hard-code). Unit tests: the edge-share formula (pairs(e, k, i)) and its check values
   (5 v 6: k=0 0.00, k=1 0.14, k=2 0.25, k=3 0.33, choice 0.20 / 0.33 / 0.50 for k=0/1/3;
   10 v 12 k=5 0.31; 15 v 18 k=8 0.33; all reproduced from the formula), and a Monte Carlo of
   the engine's bag (AI never passing in shooting) matching them. Experiments after AA works
   and after the play-quality AI tasks (rules fixes, movement candidates, To do 11 a-c): escort
   splitting (pairs vs 3-4s vs 6s under System 3; are pairs dominant?), edge size (System 2 vs
   3 vs 3 one band higher), the value of going second in movement, System 1 vs 3 on the
   owner's matchups (PDF Appendix B, now 91 incl. escort builds); report win rate and VP margin; never settle a system,
   band table or open item for the owner. Not part of System 1 here unless asked: ABFG's
   end-phase damage, 1-2-2-1 ordnance, Carry On / Disengage orders, orders tested on
   activation.
   First slice built (`src/activation.py`, no game-flow wiring yet): `AAConfig` (order mode,
   System 3 default; capital squadrons as one unit or not; recompute trigger; `allow_pass`;
   the band table), `units` / `initiative` / `fleet_mean` / `edge` / `band`, the edge-share
   formula (`pairs`, `edge_share`), `Bag` (draws, the System 3 choice spending a die, extra
   dice, passing) and System 1's `fixed_order` with its tie-breaks. Tests reproduce all nine
   check values, a Monte Carlo of `Bag` matches them within 0.02, and initiative / bands /
   fixed order are checked (`tests/test_activation.py`). Second slice built (`src/aa_round.py`,
   pure logic): `AARoundConfig` (the open items as settings: `phase_order` shoot_first /
   move_first, `launch_phase`, ordnance `first_turn_moves` 1 / `later_moves` 2,
   `brace_in_command_phase`), `ordnance_moves`, `EdgeTracker` (the recompute triggers),
   `phase_units` (shooting dice only for units with guns) and `PhaseScheduler` (one shooting /
   movement phase in any of the three systems: `next()` gives (player, unit) in System 1 or
   (player, None) in the bags, `activated`, `can_decline` / `decline` for passing, the System 3
   choice asked of the edge holder each phase via `choose_first`); a Monte Carlo of the
   scheduler matches `edge_share` (`tests/test_aa_round.py`). Third slice built
   (`src/aa_turn.py`, pure logic): `AATurn` drives a round on top of the TurnController
   (`GameState.turn_system` "igougo" / "aa", `aa_settings` flat AARoundConfig + AAConfig fields
   via `config_from`, `aa_state` round / phase): both fleets' orders cleared at the round start
   (Brace too when it is a command-phase order), turrets reset each phase, a PhaseScheduler per
   shooting / movement phase setting `gs.active_player` to the side activating, `advance` to
   the next phase and round, ordnance cadence (`may_move_ordnance` / `record_ordnance_move`,
   markers carry `aa_round_placed` / `aa_moves`) and `launch_allowed` (`tests/test_aa_turn.py`).
   AI side built (`ai_player`): `aa_command_phase` (every ship's order declared and tested
   before anything moves; `_issue_order` split out of `_move_ship`, `_movement_setup` out of
   `run_movement_phase`), `aa_phase_start`, `aa_move_unit` / `aa_shoot_unit` (one unit, a
   squadron's volley first: `_squadron_volleys(only=)`), `aa_pick_unit` by `aa_unit_value`
   (shooting: the best shot in reach now first; movement: the unit with least in reach first,
   so engaged ships move after seeing the enemy) and `aa_choose_first` (shooting: take it when
   our best shot beats the enemy's; movement: give it away); first forms, judgement, to
   confirm with the owner (`tests/test_aa_ai.py`). Passing built: `aa_decline` (movement:
   decline while the enemy has units left to move; shooting never; judgement, to confirm).
   Boarding locks built: `aa_turn.lock_boarding` (on declaration, AA only) marks the target
   `Ship.aa_locked`; `is_locked` stops the AI moving, firing or launching a boarder / boarded
   ship that round (cleared each round); resolution stays in the end phase. System 1 forcing built
   (`AAConfig.allow_forcing`, off by default, Advanced settings checkbox): `AATurn.force_first`
   (each forcing player spends a re-roll; both: 2D6 + the fleet's best Ld, ties re-rolled),
   `PhaseScheduler.force`; humans are asked at the start of each shooting / movement phase
   (`AAPanelMixin._aa_offer_forcing`); the AI never forces yet. Not yet: a character's
   ship-only re-roll forcing only that ship; locked ships enforced for humans. Rams built:
   in AA a ram that connects is deferred (`aa_turn.defer_ram`: both ships locked, kept in
   `gs.aa_state["pending_rams"]`) and resolved at the start of the end phase
   (`resolve_pending_rams`), for the AI and humans alike; IGOUGO resolves at once (s.12).
   Game window built (`src/aa_panel.py`, `AAPanelMixin` on GamePanel): Advanced settings pick
   the turn system (IGOUGO / AA, before the game starts) and the order system, phase order and
   launch phase; after deployment `_aa_begin` runs `AATurn` (`_aa_step`): command orders, the
   ordnance phases (each side's AI `run_ordnance_phase` with `aa_no_launch` outside the launch
   phase, then `_resolve_ordnance_movement` with the cadence hook `OrdnancePanel.aa_turn`),
   activations one unit at a time (AI by `aa_pick_unit`; a human acts with the usual buttons
   and presses End Phase, the unit being the ship / squadron that moved or fired), the end
   phase for both players. AI activations use the normal AI even at expert (no per-unit
   search yet). `tools/gui_checks/gui_spectator_aa.py <mode> [shoot_first|move_first]` plays
   an AI-vs-AI AA game to game over (all three systems pass, ~75-80s). Brace in AA built: with
   `brace_in_command_phase` (default) there are no reactive Brace prompts
   (`aa_turn.brace_is_reactive`, checked by `CombatPanel._brace_before_attack` and
   `combat.offer_brace`); humans get "Brace for Impact" in the command phase's order dialog and
   the AI declares it there when `brace_value` against the round's `incoming_hits` is positive
   (`_aa_brace_worth_it`). A human activation is limited to one
   unit (`TurnController.aa_allowed`, read by `get_unmoved_ships` / `get_unfired_ships` and
   the Fire dialog; `AAPanelMixin._aa_unit_filter`: any unit not yet activated until one of its
   ships moves or fires, then only that unit); `tools/gui_checks/aa_human_check.py` plays a
   human against the AI through command, launch and activation steps. Not yet: a human
   command phase that only offers orders (the order button is shown; the IGOUGO checks on
   orders still apply).
   Still to do: the experiments (they need the PDF's Appendix B fleets: Imperial Armageddon
   Sector against Eldar Corsair lists, so Eldar fleet lists or hand-built fleets, and a faster
   runner than the ~80s GUI game), the AI forcing activations, the expert AI per unit, a
   character's ship-only re-roll forcing only that ship, locked ships enforced for humans, a
   human command phase offering only orders.

14. Eldar and Necrons (export 13, CHANGES updates 48-49, 51-52): Eldar are built and playable
   (below); Necrons are built and playable too (below, after the Eldar).
   Eldar use the fan MMS v2.0 rules (`bfgxr/rules/09_eldar.md`, replacing XR's Eldar): three
   speeds by the sun (sun / away / abeam) and two moves, holofields ("2+H" shields), Fragile
   (crits on 5+), Natural Spacefarers (+1 Ld, the Eldar column), turrets +1 to hit, their own
   special orders, ordnance and critical hits table (Appendix 3), Kinship and Heroes, the
   Corsair and Craftworld fleet lists. The speeds need a sun direction (Fighting Sunward, To do 6, also has one). Necrons
   (`bfgxr/rules/10_necrons.md`): reactive hulls ("RH 4+"), Deadly Awakening, Without a Trace
   (auto-disengage, firing on own hulks, hulks 4+ Armour), Necron weapons (nightmare field,
   star pulse generator, particle whip, lightning arc, portals), Dynasty upgrades, the Necron
   critical hits table, Monuments and Necron Lords (the commanders are built, see the Obelisk
   ruling), the Harvest and Dynasty fleet lists (attack ratings 4 / 3), planetary defences
   (Tomb Complex, Pylon, Deathseed mines). The AI then needs each faction's play (To do 11 g).
   First Eldar slice built (`src/eldar.py`, pure logic, not wired in yet): `parse_speeds`
   ("10/15/20" = into the sun / away / abeam, the rules' order), `parse_holofield` ("2+H"),
   `sun_aspect` / `speed_for` (reading to confirm: within 45 degrees of straight towards the
   sunward edge is into the sun, within 45 of the opposite away, else abeam, exactly 45
   abeam), `validate_mms_move` (two legs, each a turn on the spot up to the turn angle then a
   move up to that heading's speed, no minimum; Lock On / AAF no turns, AAF +5D6 to one move,
   Come to New Heading one extra turn after the second move, no Burn Retros; reading:
   crippled -5cm on every speed), `mms_end`, holofields (`holofield_gunnery_shift`: one right
   shift, none under 15cm; `holofield_save`: 5+ beyond 30cm, 6+ at 15-30cm, none under 15cm,
   stops the blast marker) and Fragile (`crit_threshold` 5, Ghostships 6)
   (`tests/test_eldar_rules.py`). Catalog slice built (`booklet_ships`): Eldar speed = the
   highest of the three, `eldar_speeds:<sun>/<away>/<abeam>` and `eldar_mms` / `fragile` /
   `holofield` special rules, shields from "N+H", weapons batteries / pulsar / phantom lances /
   torpedoes typed with flags (`eldar_battery`, `pulsar`, `phantom`, `eldar_torpedo`), keel
   launch bays read from the export's unparsed text (`_eldar_bays`; an export gap to report:
   the parser doesn't know the Keel location), Eldar craft types `eldar_fighter` /
   `eldar_bomber` / `vampire_assault_boat` (plain fighter / bomber / assault boat stats so far);
   the non-Eldar catalog is unchanged (diffed). Still unsupported: the five Craftworld ships
   with either/or armament, one with no points cost, and all of them until the rules are wired.
   Combat built (`combat`): holofields' right shift (`get_column_shifts`, not under 15cm) and
   save against lances (`_holofield`, in `resolve_lances`: a saved hit is thwarted), Eldar
   weapons batteries' left shift, pulsars (`_eldar_lance_hits`; reading to confirm: each
   die that hits gives up to two follow-up attacks, at most three hits a die; Lock On re-rolls
   only the first miss), phantom lances (1 hit on 4-5, 2 on 6), Fragile crits on 5+ in
   `apply_damage` (a weapon's own lower crit roll still wins). Not yet: holofields against
   other direct non-gunnery attacks besides lances. Turrets / ordnance built (`ordnance`):
   `turret_hit_on(ship, marker)` gives Eldar turrets +1 to hit and Eldar ordnance (markers
   carry the launcher's rules, `is_eldar_ordnance`) stealth -2 (reading: never worse than
   6+), used against torpedoes, mines and attack craft; Eldar torpedoes re-roll misses. Not yet:
   Eldar bombers re-rolling attack dice, fighters' 4+ save per wave and first interceptions,
   the AI's hazard / strike maths for stealthy ordnance. Movement built: `movement.validate_movement`
   sends Eldar ships to `_validate_eldar` (MMS legs from the commands, `eldar.commands_to_legs`;
   an IGOUGO "move, turn, move" is two legs; speeds by `eldar.sunward_edge()`, registered from
   `GameState.sunward_edge` by the TurnController; no staged moves; blast markers slow them like
   any ship, sign-off answer 58: -5cm from the first touch on that move and the later one,
   `eldar.validate_mms_move(slowed_at=)`). Critical hits built: `tables.ELDAR_CRITICAL_HITS` /
   `crit_table_for` in the crit cascade (keel armament as a weapon slot, infinity circuit -1 Ld,
   holofield destroyed, mast lines no turns, mainsail scarred -5cm each speed per hit, mainsail
   shredded one move). Not yet: Superstructure Damaged's 3+ roll on turning, a second prow crit
   destroying port / starboard weaponry.
   Also built: Eldar AAF +5D6 (`aaf_bonus_dice`), Burn Retros refused
   (`TurnController.issue_special_order`; the AI never values it), clouds don't slow them,
   escorts pass asteroid tests and capital ships re-roll failures, warp rifts at -2 Ld with the
   3+ way home; the AI's MMS moves (`AIPlayer._eldar_moves`: a grid of first turn / length and
   second turn / length, legal by `validate_movement`, scored from the first leg's end; ~135
   moves, ~30ms a ship). Eldar are PLAYABLE now (removed from `UNBUILT_FACTION_RULES`; 18 of 24
   ships; the rest have either/or armament or no points cost); AI-vs-AI Eldar against Imperial
   Navy plays to game over in IGOUGO and AA (`tools/gui_checks/gui_spectator_eldar.py
   igougo|aa`). Gaps still open (listed above, plus): Eldar fleet lists (Corsair, Craftworld;
   they play with "No fleet list"), Kinship and Heroes, the Void Dragon, Ghostships, the
   optional Dying Race, the AI's lance values ignoring the holofield save, Come to New Heading's
   extra turn in the AI's MMS moves, the move dialog's MMS help.
   Also still open from the slices above: Eldar bombers re-rolling attack dice, fighters' 4+
   save per wave, holofields against non-lance direct attacks, Superstructure Damaged, a
   second prow crit, the five either/or ships and the one without a points cost.
   Necrons, first slice built (`src/necrons.py`, pure logic, not wired in yet): reactive
   hulls (`parse_reactive_hull` "RH 4+", `hull_save` 2+ when braced, `armour_when_braced` 4+,
   hulks 4+), no Reload Ordnance but the tomb complex, Deadly Awakening (`starting_alert`:
   1, +2 when the enemy has more points on the table, +1 per hostile special (reading: each,
   max 5); `AlertTracker` +1 per unsaved hit or raid; `AWAKEN_LD` 10 / 9 / 8 / 7 / none;
   `conserving_power` capital ships act crippled but for scoring; awakened ships double VP),
   the inertialess drive (AAF + D6x10cm, a turn per full 20cm, reading), the weapons' core
   (fields only uncrippled and off orders but Lock On, ordnance within 20cm destroyed on 4+
   each, the nightmare field's Ld test, one star pulse roll per ship within 20cm, particle
   whip 6s bypass shields, lightning arcs always "closing", portals halved rounding down and
   free of the hits limit) (`tests/test_necron_rules.py`). Catalog slice built
   (`booklet_ships`): `necron` and `reactive_hull:<n>` rules (no shields), lightning arcs as
   batteries and particle whips as lances with flags (`lightning_arc`, `particle_whip`), star
   pulse generators (`star_pulse`) and portals (`portal`, range and strength) as their own
   weapon types; other factions unchanged (diffed); every Necron ship still unsupported.
   Reactive hulls built: `combat.apply_damage` rolls the save on every hull hit (2+ braced,
   replacing Brace's 4+), and `Ship.armor_for_arc` gives a braced or hulked Necron ship 4+
   Armour. Lightning arcs built: `combat._battery_orientation` (every non-defence target
   closing, in `resolve_batteries` and `expected_hits`), no holofield right shift. Not yet:
   splitting a lightning arc's firepower between arcs, the squadron-volley path. Particle
   whips built: `resolve_lances` records `ShotResult.bypass_hits` (6s, re-rolls included; no
   holofield save on them) and `apply_damage(bypass_hits=)` keeps them off the shields; the AI
   (`_apply_hits_to`), the Fire dialog (a 6th element in its damage entries) and
   `CombatPanel._apply_hits_to_target` pass them on. Critical hits built:
   `tables.NECRON_CRITICAL_HITS` (with `ld_loss`, applied each time and never removed, in
   `roll_critical_hit`'s effects), main capacitors / power flow silencing lightning arcs /
   whips (`weapon_disabled_by_crit`), main drive no turns (`get_max_turns`; Eldar Mast Lines
   now there too), impulse power -5cm (`Ship.effective_speed`), inertialess drive refusing All
   Ahead Full and Necrons refusing Reload Ordnance (`TurnController.issue_special_order`,
   the tomb complex excepted). Not yet: port / starboard relays (target-dependent: weapons
   can't fire at targets in that arc), monument damaged blocking re-rolls and the nightmare
   field. Immunities built: no blast marker slowing (`blast_markers_to_slow`), damage
   (`_blast_marker_damage`) or Under Fire penalty (`do_command_check`), no gas cloud effects,
   solar flare / radiation immunity (`celestial._immune`), repairs on 4+ (`end_phase`).
   Deadly Awakening built: `Ship.is_crippled` includes a Necron capital ship conserving power
   (escorts never; `Ship.damage_crippled` is the damage-only check, which `victory_points`
   now uses, so scoring ignores power conservation); `GameState.necron_alert` {player: level}
   starts at `necrons.starting_alert` (points on the table) and rises in `apply_damage` by each
   unsaved hit from a roll (reading: per hit, max 5); `TurnController._necron_awakening` at
   the start of each Necron movement phase awakens ships meeting the threshold (Ld, +1 for
   Enemy Contacts), marking `necron_awake`; awakened ships and their hulks score double
   (`victory_points`). Not yet: reinforcements arriving awake, conserving ships phasing out
   when hulked, the +1 per hostile Space Hulk / Planet Killer / Blackstone. Without a Trace
   built: `disengage.attempt_disengage` / `squadron_disengage_test` let Necron ships vanish
   with no test; the AI's `disengage_gain` uses a pass chance of 1. Not yet: firing at their
   own hulks after a target priority check. Inertialess drive built: `resolve_aaf_speed` /
   `squadron_aaf_bonuses` roll D6 x 10cm for Necrons, `get_max_turns` allows turns on AAF and
   `validate_movement` needs 20cm before each (reading); the AI expects +35cm. Star pulse
   generator built: `combat.resolve_star_pulse` (one roll per non-Necron ship within 20cm vs
   its nearest Armour, a normal hit each (reading: shields apply), enemy ordnance within 20cm
   destroyed on 4+ each; not crippled / conserving or on orders but Lock On); fired by the AI
   whenever a target is in reach and from the Fire dialog ("any target"). Portals built:
   `hit_and_run.portal_weapon` / `portal_raid_count` (the profile's strength halved for
   crippling incl. power conservation and for AAF / Burn Retros / Come to New Heading / Brace,
   rounding down) and `check_teleport_eligibility` (portal range, shields down, no hits limit,
   crippled / orders allowed; escorts (the Jackal) only against ships of 6 starting hits or
   less, reading); `resolve_teleport_attack` makes that many raids; same toggles as
   teleports (reading: Remastered says portals aren't teleports in the normal manner). Not
   yet: Bloodswarm Nanoscarabs (+1, Dynasty). Necrons are PLAYABLE now (off
   `UNBUILT_FACTION_RULES`; the six mobile ships; ground defences and Deathseed mines stay
   unsupported for their own reasons); AI-vs-AI Necrons against Imperial Navy plays to game
   over in IGOUGO and AA (`tools/gui_checks/gui_spectator_necron.py igougo|aa`). Gaps still
   open: the nightmare field (no profile has one), lightning arcs splitting fire between
   arcs, port / starboard relay crits, monument damaged, firing on own hulks, reinforcements
   awake, phasing out when hulked as conserving, the ground defences / Deathseed / their
   craft, Dynasty upgrades, the Reaper / Shroud / Dirge special rules, the Harvest and Dynasty
   fleet lists, the AI's Necron play (it values guns as usual and never plans around power
   conservation or alert levels). Next (old list, now partly done): the rest of
   the combat / movement / end-phase wiring (the nightmare field (no profile carries one; a
   Dynasty / Monument item), star pulse generator and portals as actions, power conservation and awakening in the turn, the inertialess AAF), the tomb
   complex / pylon / Deathseed rules and their craft, the Necron crit table, Without a
   Trace (auto-disengage, firing at own hulks), the AI, then the Eldar gaps above.

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

### Open questions for the owner

- **Low orbit placement:** XR (s.39) says a ship in the gravity well at the start of its turn
  may enter low orbit, but not where it appears; the booklet-side answer proposes
  Remastered's "touching the edge furthest from the planet" (built that way). Ciarán to
  confirm. Also my readings in To do 7's low orbit / planet battle paragraph.
- **Sign-off answers still marked Owner** (`bfgxr/notes/OWNER_SIGNOFF_answers.md`): 2 (what
  next), 10 (Navigate the Storm ending as soon as an objective is met?), 16 (AA), 54, 55, 63-66.

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

## Running and testing

- `python run.py` starts the desktop game (needs Tk; on Debian/Ubuntu `apt install python3-tk`).
- `pytest -q` runs the test suite; it does not need Tk. It also never imports the Tkinter
  files, so check they compile: `flake8 --select=E9,F src/` (plain `--select=F` misses
  syntax errors).
- The Tkinter panels can't be unit-tested here; drive the real `GamePanel` under `xvfb-run`
  with a Python that has tkinter when a change touches UI flow.

## Code layout

- Pure-logic engine (no Tk, unit-tested): `models.py`, `game_state.py`, `movement.py`,
  `combat.py`, `ordnance.py`, `end_phase.py`, `boarding.py`, `hit_and_run.py`,
  `turn_controller.py`, `scenario.py`, `victory_points.py`, `geometry.py`, `ai_player.py`,
  `lookahead_ai.py`, and friends.
- Tkinter UI: `game_panel.py` (game flow, AI driver), `board_view.py`, and the
  `*_panel.py` / `*_dialog.py` / `*_ui.py` mixins.
- On hold: the browser client (`web/`, `src/web_*.py`, `netlify.toml`) and LAN multiplayer
  (`network.py`). Don't extend them unless asked.

## Conventions that have caused bugs

- `GameState` stores ships and ordnance as dicts. `get_ships()` / `get_ship_by_id()` return
  copies. Re-read a ship right before changing it and write it back with `gs.update_ship()`.
  Saving an old copy silently undoes newer changes (this caused the fleet re-roll and
  chain-explosion bugs).
- Shields: always use `geometry.current_shields(ship, blast_markers)`. It covers the Shields
  Collapse crit, crippling and blast markers in one place.
- Threads: only the Tk main thread may touch widgets, `ctx.log()` or `board.redraw()`. The
  expert AI search runs on a worker thread that must not call Tk; the main thread polls it.
- Human input during the AI's turn is blocked through `GameContext.actions_locked()`.
- Tests: use `tests/conftest.py`'s `DiceStub` with realistic die values listed roll by roll,
  and assert every roll was consumed (`dice._idx == len(rolls)`). Impossible rolls (a 12 on
  a D6) once hid a real bug.

## Git

Work happens on `claude/battlefleet-gothic-simulator-3sUkl`; `main` is the owner's original
upload plus one early merge.
