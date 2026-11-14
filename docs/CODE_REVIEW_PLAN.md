# Code review and refactoring plan

Plan only: nothing here has been refactored yet. Sources: the owner's questions on
`combat.py`, a profile of an AI movement phase, and a read-only review of every module (engine,
AI, UI). Each item is marked: **[measured]**, **[checked]** (I read the code and confirmed it),
or **[reported]** (found by the review, not yet re-checked; check before acting).

## 1. Answers to the owner's questions

**Do the many function-local imports slow the code down?** Hardly. [measured] A
`from .chapter_tactics import dark_age_batteries` inside a function, once the module is loaded,
costs about 90 ns (a lookup in `sys.modules`). An `"x" in ship.special_rules` test costs about
27 ns. Profiling one AI movement phase (4 v 4 cruisers, 1.8-2.9 s), import machinery was about
3% of the time. The local imports exist to break circular imports between modules (combat ↔
ordnance ↔ scenarios ↔ subplots...). They're not a speed problem. They are a structure
smell: they show the modules depend on each other in a tangle. Fixing the structure (section 3)
removes most of them; there's no reason to move them for speed.

**Would "check whether special rules are empty first" help?** Not for speed: a membership test
on a 0-5 item list is already ~30 ns, and most ships have some rules. The real problems are
different:
- ~170 string tests (`"tag" in ship.special_rules`) are spread across ~20 files, so a typo
  fails silently.
- One rule's logic is split across many files.
- [reported] Some tags are checked but never produced (`armageddon_broken`, `tomb_complex`,
  `gate_reserve` as a ship rule).
- Others are produced but never checked (`no_teleport`, `guided_missiles` in the old
  database, `ork_nob`, `space_marine_captain`, `more_dakka`).

Better options:
- Tag constants (`rules.DARK_AGE = "chapter_tactic:dark_age"`).
- A test that every tag checked in code is produced somewhere and the reverse.
- Over time, a per-ship "capabilities" object built once at game start (frozen sets and
  precomputed values), instead of re-parsing tags such as `reactive_hull:4` on every shot.

**If ladders.** Yes, there are several, and a dispatch table / registry is the better pattern
where the keys are strings. [reported, spot-checked] The worst:
- `scenarios.py`: three parallel ladders over ~25 scenario modes. `setup_scenario` has 22
  branches and `deployment_zones` 25, plus `placement_errors`, `check_end` and
  `winner_at_end`. Adding a scenario means editing every one. Fix: a `ScenarioDef` per mode
  (setup, zones, placement, turn start, end, winner, VP bonus, AI terms), registered once.
- Crit effects in `combat.py` (~1092-1129) sit outside the crit tables. Fix: put `ld_loss`,
  `remove_rule` and an effect callback in each `tables.py` entry.
- `tables.crit_table_for`: an if-chain on tags. Fix: an ordered list of (tag, table).
- Torpedo-type effects (`ordnance.py` ~618-683). Fix: a handler per type.
- Special-order legality lives in five places: turn_controller, eldar `ALLOWED_ORDERS`,
  necrons `order_allowed` (only tests call it), hit_and_run, movement. Fix: one
  `order_allowed(ship, order, gs)`.
- `subplots.py` sub-plot setup (13 branches). Fix: a dict of key → setup function.

**The Zzapp Gunz docstring.** You're right, and the wording is misleading. [checked]
`_zzapp_firepower` runs only for weapons that have both `zzapp` and `strength_dice`, so a
fixed-firepower zzapp gun isn't rolled. But the docstring says "Zzapp Gunz' random
firepower", and `weapon_fire_pool`'s "e.g. Gunz FP D6+1" implies Gunz are random; most are
fixed (2-10). The Onslaught's "FP2 gunz + zzapp gun (30cm FP1 F)" option isn't built yet (the
zzapp gunz swaps are a To do 9 item). When it is, that zzapp gun is a fixed FP1 lance hitting
on 5+. Fix the docstrings now; build the option with the other swaps.

**Random weapons in threat assessment: average or a roll?** The AI never rolls for estimates; it
uses a stored average. That average is wrong in two ways:
- [checked] `dice_value_average` truncates (`int(...)`): D6+1 is stored as 4 instead of 4.5,
  D6 as 3 instead of 3.5, so random weapons are undervalued by about 10-15%.
- Worse, the Gunnery table isn't linear. The right estimate is the expected hits *over the
  distribution* (average the six outcomes of D6+1), not the hits at the average firepower.
- [reported] The AI also picks its target before the dice are rolled (correct: the value
  isn't known yet) but doesn't re-pick once the roll is in.
- `Weapon["strength"]` means the average for dice guns but the maximum for random launch
  bays. Split it into `strength_mean` and `strength_cap`.

**Killkannons and bombardment cannons (Gunnery table, hit on 4+, crit on 4+).** Handled correctly
in the engine: [checked]
- `resolve_batteries` uses the Gunnery table for the dice and `hits_on` 4 for the roll.
- `apply_damage(crit_on=4)` applies crits on 4+.
- Siege Cannons split the dice between macrobatteries and bombardment cannons.
- `combat.expected_hits` uses `hits_on`.

The AI's values are the gap: [reported, spot-checked]
- Target values (`damage_vp` / `shot_vp`) count every hit the same, so a 4+ crit weapon
  isn't valued for its three-times crit chance when choosing targets.
- About eight places use the "0.35 per firepower point" shortcut, which ignores `hits_on` and
  `crit_on`.
- [checked] `ai_player._brace_hull_hits` uses `strength × (7 - armour) / 6` for batteries
  and lances alike. That ignores the Gunnery table, lances' 4+ and `hits_on`.

**Should we branch to another language?** I'd advise against a rewrite.
- **What it would cost:** the code is ~45,000 lines with 1,334 tests and dozens of owner
  rulings encoded in it. A rewrite would cost months and re-introduce rules bugs the tests
  have already caught.
- **The profile shows the slowness is design, not Python:** most AI time goes on copying
  ship objects (section 2). Fixing that gives a 2-3x speed-up in Python.
- **If raw speed is ever needed** (the learned evaluation or weight tuning, To do 12 / 1, which
  want thousands of games), the better path is to move only the hot simulation core (the
  expert AI's sim, geometry) into a compiled module, Rust via PyO3 or Cython, behind the same
  Python API. Keep the rules engine and UI in Python.
- **A browser version** (on hold) could use TypeScript for the UI over the existing engine
  (Pyodide or a small server) rather than porting the rules.

**AI vs AI / player vs player / player vs AI?** All three exist:
- Hot seat (PvP).
- "Enable AI opponent" (PvAI; the AI is always Player 2).
- "Spectator mode" (AI vs AI, one difficulty for both sides).

Small gaps: the AI can't be Player 1 in PvAI, and spectator games can't give each side its own
difficulty. LAN multiplayer exists but is on hold.

**2v2 or more players?** Not supported. The engine is two-sided throughout (`3 - player`
appears ~100 times, and VP, turn order, AA bags and every scenario assume two sides). Allied
fleets on one side are fine: a side can field ships of several factions.
- **Team play (2 v 2 humans):** the cheap form is several humans controlling one side's ships
  (ownership per ship within a side). That's a UI and turn-flow change, not an engine one.
- **Three or more sides:** a much bigger change, because the rules assume one enemy side.
  The booklet doesn't cover multi-player games.

## 2. Performance (measured first, the biggest wins)

[measured] AI movement phase, 4 v 4: ~40% of the time is `ai_hazards.ship_bracket_raw`, whose
`Ship.to_dict()` → `dataclasses.asdict` deep copies dominate. Overall, `asdict` + `from_dict`
are over half the phase.
1. **Cache `ship_bracket_raw` / `bracket_matchup` per phase.** They depend on the two ships'
   states, not on the candidate move. Expect about 1.6x on movement planning alone.
2. **Stop copying ships to test arcs.** `_mount_bears`, `position_exposure_hits` and
   `_screen_bonus` build Ship copies per candidate, per mount, per target. Fix: arc and range
   functions that take `(x, y, heading)` directly.
3. **Build one per-phase snapshot** in `_movement_setup` (enemies, markers, phenomena, value
   per hit, enemy mounts, a hits matrix), passed to every `_move_score` term. About 20 terms
   now re-read `gs.get_ships()` per candidate. The three near-identical focus loops
   (`fleet_focus_targets`, `fleet_hits_on`, `_ship_hits_on`) come from the one matrix.
4. **Make `GameState` copies cheaper.** Replace `asdict` (recursive deep copy) in
   `Ship.to_dict` with a shallow field copy plus copies of the mutable lists, or move to
   live Ship objects with explicit snapshots. This touches every module, so do it last, with
   the convention change documented.

Re-profile after each step; keep the GUI spectator timings as the benchmark.

## 3. Rules bugs the review found (fix soon; correctness, not refactoring)

- [checked] **Raid crits skip effects.** `hit_and_run._apply_raid_crit` re-implements the
  crit application and skips Bridge Smashed's -3 Ld (and Demiurg's extra damage instead),
  Necron `ld_loss`, Infinity Circuit -1 Ld and Holofield destroyed. A raid's cascade can
  reach Bridge Smashed. Fix: one shared `apply_crit_effects` used by `roll_critical_hit`
  and raids.
- [checked] **Raid preview uses the wrong table.** `hit_and_run.raid_crit_preview` always
  reads the default `CRITICAL_HITS`, so the Wings of Fury / raid values are wrong for Eldar,
  Necrons and stations. Fix: `crit_table_for(target)`.
- [reported] **Crit slot tests disagree.** `Ship.has_armament_slot` treats any weapon with
  "front" in its arcs as a prow slot (a dorsal L/F/R weapon counts), while
  `weapon_in_crit_slot` disables by name, then exact arcs. A prow crit can then land, not
  cascade, and disable nothing. Fix: one slot table, used by both. There are also three
  separate armament-crit lists in combat.py.
- [reported] **Meteor Storm:** the sub-plot's crit ignores `roll_critical_hit`'s
  "destroyed" result, so a ship can sit at 0 hits with no catastrophic roll.
- [reported] **Stale crit list:** `combat.add_fire_crits` copies the caller's possibly stale
  `critical_damage` list onto the fresh ship.
- [reported] **Kustom Kannon:** in the AI shooting loop the ship copy keeps
  `ordnance_loaded_torps=True` after `spend_kustom_kannon`.
- [checked] **Eldar sunward edge goes stale.** Two sunward-edge globals: `eldar._SUNWARD`
  is set only when a TurnController is created, while the settings dialog re-syncs only
  `optional_rules`. Eldar speeds go stale after changing the sunward edge in-game. Fix: read
  it from `gs`.
- [checked] **Raw `random` instead of the dice.** Game rolls use raw `random` (the Daemon
  mine's D6, which I added this session, and Fleet Engagement's AI formation pick), so manual
  dice mode and seeded replays are bypassed. Several marker ids use `randint(0, 9999)` and
  can collide. Fix: route rolls through `DiceRoller`, use a counter for ids.
- [reported] **Leaky state on `gs.__dict__`:** `_zzapp_blast`, `_spillover_touched` (never
  pruned), `_bm_collected`. Not saved, not reset by `restore_from`, so they leak across
  load and undo. Fix: declared transient fields.
- [reported] **`GameState.save` hand-lists its fields** and will drift from the dataclass.
  Fix: iterate `fields()`.
- [reported] **`optional_rules.set_ship_source(gs.get_ships)`** binds the live game state,
  so a lookahead or cloned state would read the real board.

## 4. Structure (after the bugs and the performance steps)

1. **Rule dispatch:**
   - Tag constants and the tag-coverage test (section 1).
   - Crit entries carry their effects.
   - One `order_allowed`.
   - One `effective_launch_strength` / `effective_fire_pool`: the halving for crippled,
     braced or in an asteroid field is re-done inline in ordnance_panel, combat_dialog and
     combat_panel today.
2. **`ScenarioDef` registry** replacing the scenarios.py ladders, one module per scenario
   family (most already exist: escalating, navigate_storm, convoy_narrative, planet_scenarios,
   campaign_scenarios, craftworld).
3. **Split `ai_player.py`** (4,600 lines) into `ai/movement.py`, `ai/scenario_terms.py`,
   `ai/orders.py`, `ai/shooting.py`, `ai/ordnance.py` and `ai/aa.py`, behind the `AIPlayer`
   facade.
   - `_move_score` becomes a list of terms (name, weight, function); scenario terms register
     only when their scenario is active, so the others cost nothing.
4. **One weapon-value helper,** `mount_expected_hits(weapon, target / armour)`. It knows the
   Gunnery table, `hits_on`, `crit_on` and `strength_dice` (expected over the distribution).
   It replaces the ~8 copies of the 0.35 rule of thumb in ai_hazards, ai_player, ai_rerolls
   and lookahead_ai. This also does To do 1's prerequisite ("replace 0.35 with the exact
   Gunnery table").
5. **`ai/weights.py`:** every judgement weight in one place with its note (0.35 appears ~43
   times, plus dozens of others), so difficulty profiles and the future tuning (To do 1,
   on hold) can override them.
6. **Rules out of the UI:**
   - Squadron size and composition limits and the one-flagship rule (fleet_builder.py
     ~970-1027) go to `fleet_lists`.
   - The hull-repair threshold and cost (game_panel.py ~1035) go to a campaign rules
     function.
   - Guided-torpedo 45° and the asteroid 10cm range cap become engine constants.
7. **Duplicated AI / UI logic:** Siege Cannons orchestration (AI and Fire dialog), the ram
   declaration (AI and movement panel), `_pick_target` vs `_valid_targets`, and lookahead_ai's
   copies of `_arc_score` / `mount_hits`. Each becomes one engine function.
8. **Long functions:**
   - `ordnance_movement._resolve_ship_contacts` (395 lines): one function per step (turret
     choice, CAP, brace, suppression, attacks).
   - `combat._apply_damage` (161): a pipeline of save stages.
   - `movement.validate_movement` (234) and `scenarios.setup_scenario` (210).
9. **Docstrings to fix:** `_zzapp_firepower` / `weapon_fire_pool` (above),
   `optional_rules.py`'s "spill-over isn't modelled" (it is), and `GameState.scenario_mode`'s
   list of 4 modes (there are ~30). Also the repair priority list naming unrepairable crits.

## 5. Order of work (proposal)

1. The section 3 bugs, each with a test (small, rules-correctness).
2. Performance steps 2.1-2.3 (big speed-up, low risk, profile-checked).
3. The weapon-value helper and the AI value gaps: random weapons by distribution, 4+ crits in
   target values, `_brace_hull_hits`.
4. Tag constants + coverage test; crit-effect tables; `order_allowed`.
5. `ScenarioDef` registry; split `ai_player.py`; `ai/weights.py`.
6. `GameState` copy model (2.4), with the convention rewritten in CLAUDE.md.

Each step leaves all 1,334 tests and the GUI spectator checks passing, and lands as its own
commit. No behaviour changes in the pure refactors (2, 4, 5, 6): if a test changes, it's a
bug fix and is listed as one.
