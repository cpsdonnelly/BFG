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
- Victory points: core section 38 and the "Victory Points" part of `bfgxr/rules/10_scenarios.md`
  give the same rules: Destroyed, Crippled, Scattered (disengaged) and Holding the Field.
- Squadrons (s.8) include Maneuvering Squadrons and Shooting at Squadrons (target aspect, hit
  allocation nearest-first, critical damage applied before a ship counts as destroyed).
- `data/rules_cheatsheet.txt` and `data/*.csv` (plus the copies in the repo root) are an
  older hand-written summary. Where they disagree with `bfgxr/`, `bfgxr/` wins.
- The ship catalog (`src/ship_catalog.py`) is built at import from `bfgxr/data/ships.json` by
  `src/booklet_ships.py`: all 9 factions, 178 booklet ships plus 17 designed Venerable Strike
Cruisers. Ships using rules the engine can't play yet
  (Zzapp Gunz, Kustom Kannon, special movement, fortress weapons...) are
  listed with `entry.unsupported` reasons and greyed out in the fleet builder. Old catalog names
  ("Gothic Class Cruiser") still resolve. Saved fleets keep their saved stats.

### Owner rulings

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
  (Xenos, Turret Defences). Not yet: the Ork commander's Extra Turrets (4+).
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
  by the engine. The AI attempts none of boarding / ramming yet. Fighting Sunward, Solar
  Flares and Radiation Bursts (s.40) are NOT built: their toggles do nothing (the settings
  dialog now says "not built yet"; To do 6).
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
it). Not yet: the Brace prompt, special-order re-rolls (special_orders_ui), Vault of
Technology's chooser.

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
knocked out counts nothing. Escorts: 1
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
matching the booklet" (commander re-rolls). Not yet: several Ork Bosses' re-rolls (the
engine keeps one re-roll pool, on the flagship), kustom upgrades, clans, named commanders
(Lord Admiral Rath, Abaddon, Kor'O'Mesme...). Export 31 settled it: a commander is required
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
  commander's (`TurnController.get_fleet_rerolls / use_fleet_reroll(player, ship)`). Not yet:
  other factions' secondaries (Elite Captains / Daemonhunters, Ork Nobz, Bond-Captains,
  Space Marine Captains), per-Boss re-roll pools for several Ork Bosses.
- Disengaging (s.37): escort squadrons test together; Forced Disengagement (Ld 1 or less) and
  Demiurg Mercenaries test at the end of movement (`disengage.forced_disengage_tests`); a ship
  that fails gets `Ship.must_flee` (AI `_plan_flee`; voluntary AI disengaging: see "AI: how it
  decides"). Not yet: the +3 during a radiation burst or solar flare.

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
  lists enforce that (`list_options`). Not yet: Ordos (a ship may not mix Ordo upgrades), Grand Master, Inquisitors, Elite Daemonhunters/Captains, retinues, honour guards,
  Blessing of Chaos.
- Not yet: Rogue Trader refitted
  torpedoes (no Rogue Trader ship in the roster has torpedoes), Deathskulls' half-cost looted
  torps, the Ork zzapp gunz swaps. The Ork torpedo launcha swaps (Terror Ship, Kill Kroozer
  incl. its 2D6+2 variant, Basha) are options (`booklet_options.ork_launcha_options`); looted
  torps need one of them (`requires_any:`).

### Session status (details in docs/HANDOFF.md)

Booklet installed: zip 12 (CHANGES.md update 45). Tests: 1075 pass; all GUI checks pass
(`xvfb-run -a /usr/bin/python3.12 tools/gui_checks/<x>.py`; the spectator checks take a
difficulty: `gui_spectator_demo.py normal` / `expert`; expert games take ~75s of their 180s
limit). After every new export, diff the built
catalog (dump every entry's stats, rules, weapons and options before and after): notes text is
matched in code, and a reworded note silently drops an option.

Built so far: every booklet rule section the engine plays (see the sections above), the export
31 "still to do" list, boarding crew bonuses, disengaging incl. forced disengagement, optional
blast marker rules, the turret split, waves / CAP / wave planner, the hit-and-run toggle
covering every raid, Remastered turret suppression per p.82, the optional-rule toggle audit,
and the expected-VP AI below (incl. carrier doctrine, strikes valued when they land,
co-ordinated strikes, the AI's own teleports). Not built: Fighting Sunward, Solar Flares,
Radiation Bursts (s.40), scenarios / sub-plots, and the To do items below.
Next: the rest of To do 2, then 3-7, 9, 10 and 11; 8's place in the order is an open question;
12 (learned evaluation) after 11; 1 (weight tuning) last and on hold.

### AI: how it decides (expected VP)

The whole AI, current and planned, in plain language: `docs/AI_DESIGN.md` (keep it in step).

Fleet strategy (owner doctrine): the AI plays its matchup, judging its fleet and each ship
against the enemy's, on average and ship vs ship. Owner: "do not take these as hard rules, it
depends on the matchup": every one should come out of the expected-VP values, not a fixed rule.
- Firepower by range bracket (0-15 Ork Heavy Gunz, 15-30, 30-45, 45-60 Chaos long guns,
  60-150 artillery such as the Nova Cannon): fight in the bracket where our guns beat theirs
  (e.g. a Tau Merchant out-guns a Lunar at 30-45cm, not at 0-30cm). Planned: To do 8 f.
- Speed (and turn angle) edge: out-moving the enemy, get out of its main fire arcs (e.g. into a
  Lunar's rear arc). Planned: 8 g.
- Out-range and out-move it on average (Chaos): kite, holding the band where we can fire and it
  can't. Planned: 8 c.
- Gun-heavy broadside fleets (Imperium, e.g. Lunars, broadsides that don't overlap): keep both
  broadsides busy, cross the T. Planned: 8 b.
- Forward-firing ships with the best Armour in front (Tau Protector): show the prow only when
  the enemy is about to be in range. Planned: 8 d (needs 8 a: exposure by Armour facing).
- Hit-point edge (Orks): think about boarding and ramming (only with those rules on). Planned:
  8 h.
- Teleport attacks, both launching them and being vulnerable to them (only with teleports and
  hit-and-run on). The AI now decides its own teleports; positioning and defence planned: 8 j.
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
`DODGE_WEIGHT` 0.5, `MOVE_TURN_WEIGHTS` 40% straight / 15% per turn, `ANTICIPATED_STRIKE_WEIGHT`
0.5 (scaled by the air balance), `AIR_THREAT_WEIGHT` 0.5, `ENEMY_FIRE_AT_WAVE` 0.5,
`REACTIVE_CAP_WEIGHT` 0.5, `AIRBORNE_INTERCEPT_WEIGHT` 0.75, CAP free fighters 0.75, the
disengage and hulk models.

Optional rules (owner): when a rule is disabled (Advanced settings: `GameState.rule_*`, all
off by default: boarding, ramming, teleport, hit-and-run, fighting sunward, solar flares,
radiation bursts, Remastered turret suppression / spill-over), the AI neither values moves by
it nor attempts it. Audit: hit-and-run is respected (`_strike_option`, `waves.best_attack_mode`,
`ai_hazards`, and the craft types the AI launches); teleport attempts need `rule_teleport` and
`rule_hit_and_run` (`check_teleport_eligibility`); boarding,
ramming and teleport aren't valued anywhere yet, so every new term for them (To do 8 h, j)
must check its flag; the wave planner and AI follow the turret suppression mode (XR / Remastered
p.82, `waves.wave_split_value`); the celestial-phenomena rules aren't modelled
by the AI yet (check their flags when they are).

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
  the enemy could focus on the end position (`_exposure_penalty`, `position_exposure_hits`).
- The move score (`_arc_score`) counts in-arc batteries / lances / nova cannon and loaded
  torpedoes (they launch from the end position: full within one torpedo move, half within two).
- Explosions (`explosion_position_vp`): keep out of the 3D6cm radius of ships likely to die; a
  ship of ours likely to die ends next to enemies.
- Special orders (today, to be rebuilt by To do 10): Burn Retros by expected VP
  (`_burn_retros_worth_it`), Lock On when an enemy is in arc now, Reload Ordnance when spent;
  never All Ahead Full / Come to New Heading. Escorts screen the commander's ship for
  massed turrets (s.29, `_screen_bonus`) only while enemy torpedoes, torpedo bombers, bombers,
  assault boats or mines can reach it (owner: never against fighters alone).
- Voluntary disengaging (s.37, `_consider_disengage`, `ai_hazards.disengage_gain`): P(pass) x
  (risk avoided over the enemy's next turn - extra VP conceded) - its guns' value. Risk from
  `incoming_hits`: per enemy mount (a port broadside bears on ships on its left, starboard on its
  right, other mounts within their arc after one turn of the ship's own turn angle), the enemy
  focusing fire (`enemy_fire_plan`, owner), a Poisson count; destroyed = full value (75% more if
  already crippled), newly crippled 25%; leaving concedes 10%. One-turn horizon; escort squadrons
  and the last turn not special-cased.

Shooting:
- Targets by marginal expected VP (no overkill), target priority test obeyed; battery values with
  column shifts (`combat.expected_hits(..., gs)`); weapons knocked out by armament crits never
  fire (`combat.weapon_disabled_by_crit`); the commander's ship braces earlier.
- Squadron volleys (s.8, `_squadron_volleys`): one `plan_squadron_volley` per squadron when it
  rolls at least as many dice as firing separately, at the best target that is every
  contributor's nearest valid target; aspect by `best_aspect_choice`. Batteries only. Not yet:
  Ork random-firepower batteries in volleys, a volley needing a target priority test.
- Hulks (`_hulk_shot`, `hulk_shot_vp`): shot when the closest target in arc and P(a hit) x the
  re-rolled catastrophic damage among enemy ships beats the best ship shot. Not counted: Holding
  the Field hulk points, hulks that aren't the closest target.
- Ships shoot incoming ordnance when worth more than their best ship shot.

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
shields each turn, the real table); leaf = VP banked + next turn's expected swing at
`LATER_TURN_WEIGHT`.

### To do (agreed order; detail in docs/HANDOFF.md)

1. On hold (owner): tuning the AI's judgement weights (listed in "AI: how it decides"). Keep
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
   one bomber move the full wave wins. Still to do here: crit values beyond the next shooting
   phase, splitting waves against enemy guns, a risk preference, the expert AI valuing craft
   in flight, reactive CAP for craft already in flight.
3. Mine launcher swaps (Navy, Space Marine, Chaos, Tau lists; the Bastion's mines as a third
   mode), torpedo bomber purchases and torpedo bombers firing their salvo (s.21). Rules (s.21,
   owner): torpedo bombers are bombers against other ordnance but can't attack ships; at the
   start of any ordnance phase after their launch turn a squadron may be replaced by a
   strength-2 salvo facing any direction, removed at the end of that phase ("limited fuel": one
   move only); a wave combines its salvos like a squadron in base contact (owner: "a wave of 4
   torpedo bombers becomes a wave of 8 missiles"). Tiger Sharks: see the owner ruling below.
   Then the AI: `ai_hazards.marker_hits` (a torpedo bomber wave threatens one salvo of 2 x its
   squadrons, any facing, within its reach; today it counts them as bombers), fighter allocation
   (one fighter removes the whole combined salvo, s.19), strike planning (torpedo bombers vs
   bombers). Who has them (owner corrected an incomplete list; "Attack craft: TB 20cm +Npts"
   options): Imperial Navy (Marauders) Emperor +80, Oberon +80, Exorcist +60, Mars +40,
   Dominion +40, Dictator +40; Adeptus Mechanicus Emperor +80, Oberon +40, Dictator +40; Chaos
   ("not if Stormbird gunships taken") Despoiler +80, Desecrator +40, Retaliator +60, Nephilim
   +40, Styx +60, Hecate +40, Devastation +40, Scion of Prospero +90, Wage of Sin +60, Terminus
   Est +70; Tau Tiger Shark drone carriers (replacing Mantas on many Tau ships, and the Orbital
   City's defence module). None is offered by the fleet builder yet (`booklet_options` note,
   l.532); Orks, Space Marines, Inquisition and Rogue Traders list none.
4. Named commanders (Lord Admiral Rath, Abaddon, Kor'O'Mesme), Mark of Chaos Undivided,
   daemonships, Stormbirds, god-fleet boons, Ork kustom upgrades / clans (incl. the Ork
   commander's Extra Turrets: 4+), other factions' secondary commanders, Inquisition Ordos.
5. Unplayable units: Zzapp Gunz, Kustom Kannon, special movement (Nicassar Caravan, Kroot
   Warsphere, Space Hulk), fortress weapons (Ramilies, Fortress-Monastery), Pthuxutl
   disruptor cannon, Man O' War configuration, Planet Killer's Armageddon gun.
6. Smaller gaps: Fighting Sunward, Solar Flares and Radiation Bursts (s.40) aren't built (their
   toggles do nothing; the settings dialog says so), nor the +3 disengage Ld and the
   commander re-roll limit they bring (s.5, s.37); undoing a Demiurg
   move doesn't return collected blast markers; a human player isn't stopped from not fleeing
   after a failed forced disengage (log reminder only).
7. Scenarios and sub-plots, engine and AI (owner request: the AI must play scenario and sub-plot
   games, not just cruiser clash; after items 1-6). The engine has only the old generic modes
   (`scenario.check_scenario_end`: kill the admiral, destroy / protect a ship, capture an
   artefact); none of the booklet's scenarios (`bfgxr/rules/10_scenarios.md`: Cruiser Clash, The
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

8. Matchup-aware manoeuvre (owner ideas; "do not take these as hard rules, it depends on the
   matchup": each should come out of the expected-VP move score, not a fixed doctrine).
   Ship facts checked in the catalog: Lunar speed 20, 6+ prow / 5+ sides, port and starboard
   30cm batteries and lances that don't overlap; Chaos Murder / Carnage speed 25 with 45-60cm
   batteries and 60cm prow guns (the Slaughter is fast but 30cm: a brawler, not a kiter); Tau
   Protector speed 20, 6+ prow, railguns / ion cannons all bearing forward (L/F, R/F, F).
   Plan:
   a. First, a shared prerequisite: exposure should respect our Armour facing.
      `ai_hazards.position_exposure_hits` / `incoming_hits` count 0.35 hits a battery point
      whatever side the enemy sees; scale each enemy mount's hits by p_hit of the Armour it
      would hit (`Ship.armor_vs` from the enemy's position at our end heading). A 6+ prow then
      really is safer than a 5+ side, which the Tau and crossing-the-T ideas both need.
   b. Both broadsides busy (gun-heavy Imperium, e.g. Lunars; "crossing the T"): replace the
      move score's single-target arc score with a fleet-aware mount coverage score at the end
      position: each battery / lance mount scores the best expected VP it could add next
      shooting phase among enemies in its arc and range (the enemy's predicted positions,
      `_predicted_positions`), so a position with a target off each beam scores both
      broadsides, one with everything off one side scores one. Crossing the T then comes out
      of (a) + (b): across the enemy's line of advance our broadsides bear while only its prow
      guns bear back on us. Cost: per candidate move x mounts x enemies (cheap). Squadrons
      should plan together (one heading for the squadron, s.8).
   c. Kiting (Chaos and other long-range / fast fleets): a matchup check, `range_speed_edge`:
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
   g. Speed (and turn angle) edge, on average and ship vs ship: out-moving an enemy, get out
      of its main fire arcs, e.g. into a Lunar's rear arc where neither broadside nor prow
      bears. Plan: per enemy, the arcs its mounts can bring to bear after its next move and
      turn (`_mount_bears` with its own speed and turn angle); with a speed edge, end positions
      outside all of them score the exposure saved; this is (a)'s exposure looked one enemy move
      ahead. Without the edge it is mostly unreachable, so the term does nothing.
   h. Hit-point edge (e.g. Ork cruisers: 10 hits vs a Lunar's 8): think about boarding (s.32)
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
      `tools/gui_checks/teleport_ai_check.py`). To do: (1) offence: move teleporters to end
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
   section): Auto (best) on the Brace prompt, special-order re-rolls and the Vault of
   Technology chooser ("Auto (best)"); bombers that re-roll their attacks (+1 when suppressed)
   and resilient squadrons stopping / splitting (Waves); fleet lists: more than one
   detachment, "no more reserve copies than its own list could field", reserve-only refit rules
   (Fleet lists); designing a Venerable Battle Barge (Fleet lists); Rogue Trader refitted
   torpedoes, Deathskulls' half-cost looted torps, Ork zzapp gunz swaps (Torpedo types); attack
   craft flying straight without a target and torpedo-vs-torpedo collisions checked only at the
   end of the move (Engine notes); AI: Ork random-firepower batteries in squadron volleys and a
   volley needing a target priority test, hulks that aren't the closest target and Holding the
   Field hulk points, the target turning to show its strongest facing to a turning salvo,
   assault boats and mines in co-ordinated strikes and re-timing a launch to arrive together
   ("AI: how it decides"); AI special orders: see To do 10; the Nova Cannon aims
   at the nearest enemy 30-150cm rather than by expected VP; deployment by strategy (ships are
   only grouped for set-up), damage-control repair choices by expected VP (today a fixed
   priority: fires, engines, the rest), and which blast markers to remove in our end phase.
   Items already in 2-8 aren't repeated here (Ork Extra Turrets, Ork
   Bosses' re-roll pools, secondary commanders and Ordos are in 4; the radiation / flare
   disengage bonus is in 6; the teleport AI's positioning is in 8 j).

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
   ships take their checks in fleet order. Owner notes and plan:
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
      again after a decline; a passed brace lasts to the end of the ship's next turn. Gap: when
      the AI fires, `AIPlayer._offer_brace` asks the target once per firing ship (against the
      total of all its weapons), so a player who declines against its batteries isn't asked
      again before its lances; it should ask before each weapon until the target has tried. The
      human Fire dialog asks once for the weapons fired together in it.
   f. Command check modifiers (s.6) in every order's pass chance: Enemy Contacts +1 Ld if any
      enemy ship is on special orders, Under Fire -1 with blast markers in contact, Ld 0-10;
      command checks only, not Leadership tests. Both directions matter (our orders make the
      enemy's checks easier).
   g. Teleport-capable ships: an order other than Lock On / Reload Ordnance gives up the
      end-phase raid (s.31), so its value counts against that order.

11. AI design feedback (owner, on docs/AI_DESIGN.md; items tagged Rules / Owner / Suggestion
   in its priority order; Suggestions are the intended direction, raise them with the owner
   if they conflict with something already decided). Checks done this session: gunnery values
   subtract shields (`ai_player` `added_vp` / `ai_should_brace` use `current_shields`);
   `damage_vp`'s per-hit term is 0.2 x points / starting hits (`value_per_hit`); Ork turrets
   hit on 5+ (`ai_hazards`, `waves`) and fire at everything (`turret_split_gain` gives no
   split gain); mines in the hazard model move 10cm toward the nearest enemy vessel of the
   layer in each ordnance phase (`marker_hits`), and the engine's mines home on the layer's
   enemies only (`ordnance.move_ordnance`). Gap found: the mine hazard counts 8D6 against
   Armour flat, ignoring the turret roll that cuts it to 4D6 (`ordnance.resolve_mine_contact`).
   To build:
   a. Movement candidates (owner): turn points for capital ships right after the turning
      distance (battleships 15cm, cruisers 10cm; s.10, before modifiers), just after the
      minimum move (half speed) and at the end of the move (separate rules: a 20cm cruiser 10 /
      10cm, a 25cm cruiser 10 / 12.5cm); escorts anywhere, including at the very start; Burn Retros needs
      no movement before turning; only forward movement this phase counts toward the turning
      distance. More headings for sharper turners (owner; suggestion every 15 degrees up to the
      maximum: 45 -> 7 headings, 90 -> 13; any angle up to the maximum is legal). Suggestions:
      add a 50% distance (the exact minimum move: ending as short as legally possible often
      keeps a ship out of enemy range); a ship moving under 5cm counts as Defences
      on the Gunnery table (s.10), which matters for Burn Retros; a budget of about 150
      candidates, pruned with the cheap terms, exposure scored on the best ~20, the extra time
      spent on 90-degree ships and escorts; then a coordination pass over the fleet: moves
      are greedy in fleet order, so each ship ignores ships still to move; re-optimise each
      against everyone's planned end positions (coordinate descent, one or two passes), which
      catches screening and mutual support.
   b. Expert AI hazards (suggestion, high): it plans movement without hazards, so it can fly
      into an asteroid field (Ld test or D6 damage, s.39) or through blast markers. Minimum: the
      path-hazard cost at the root and in its evaluation; better: expected values at chance
      points, or sampled dice.
   c. Rule effects missing from valuations:
      - Price Brace instead of the 1/4-of-hits rule (owner: the feedback is right that Brace
        has a cost). Gain: 4+ saves on hull hits from this attack and every later attack until
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
        rest of that turn. Suggestion: when a ship is crippled or likely to disengage, value
        positions near phenomena before it tries. VP for a non-crippled disengaged ship: 10%
        ("Enemies Scattered", s.38). Check `disengage_gain` uses every modifier.
      - Plasma drive overload (Appendix 5, 9-11): lance shots at half starting hits at every
        ship within 3D6cm AND all ordnance within the radius destroyed, so an explosion
        protects its neighbours from incoming waves and salvos; `explosion_vp` counts the
        ship damage only.
      - Teleports (s.31): not crippled, Lock On / Reload only, target shields down, within
        10cm, no more remaining hits; no escorts or defences under 3 hits; order valuation
        counts the raid given up (To do 10 g).
      - Dust clouds (s.39, XR pp.52-54): ships in contact count as having a blast marker in
        all respects; ordnance moving through tests as for blast markers (owner ruling: XR's
        omission is an oversight, Remastered states it; the AI already matches).
   d. Shooting order (suggestion): against shielded targets fire batteries before lances
      (shield-hit blast markers shift later batteries; lances aren't affected); knocking
      shields down also opens teleports (To do 8 j).
   e. End phase and pre-game: damage control by expected VP (s.36, XR p.35: a D6 per remaining
      hit, each 6 repairs one system, dice halved in contact with blast markers; a fire costs
      1 hit per end phase; a weapon is worth its next turn of fire if it will bear; an engine crit what is lost by not
      turning; escorts don't repair; the fixed order stays as the fallback); blast marker
      removal as s.36 states it; first-turn policy (s.2: the roll-off winner chooses to move
      first or second) alongside deployment.
   f. Scale-free re-roll bars (suggestion): the 45 / 25 / 15 / 10 VP bars as a fraction of fleet
      points or points in play.
   g. Faction behaviour (suggestion): Eldar (MMS v2.0: two moves, holofields, Fragile, turning,
      own ordnance) and Necrons aren't modelled; the generic AI would misplay them.
   h. Compute, don't script (suggestion): build To do 8 a and 8 f first and see what emerges
      before adding doctrine code (kiting should come out when our best bracket is beyond the
      enemy's reach, prow-on when the prow is the best-armoured facing); matchup weights only
      as functions of measured features (To do 1), so one tuning run covers lists it never
      saw.
   i. Difficulty (suggestion): Easy chooses by softmax on expected value with a temperature
      (human-like mistakes); Hard gets the coordination pass or tuned weights.
   Claude's view (not an owner ruling): expected value of the work is rules completeness >
   candidate generation > search with dice > learned evaluation > weight tuning (fairly
   confident of the order, not of the size of each gain); tuning only improves the AI within
   its structure and must be redone after every structural change.

12. Learned evaluation for the expert search (owner: do it; low priority, after To do 11,
   and only after its a-c). Supervised fitting of position features to game outcomes.
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

- Where To do 8 (matchup-aware manoeuvre) goes in the order: it is listed last for now, after
  items 2-7; the owner may want it sooner.

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
