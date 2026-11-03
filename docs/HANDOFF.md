# Handoff brief for the next Claude session

Read this, then `CLAUDE.md` (owner rulings, conventions) and `bfgxr/CLAUDE.md` (rules authority)
before touching anything. `CLAUDE.md` is the living source; this file is a snapshot of where the
work stood at the end of a long session (Nov 2026).

## Workflow rules (owner's standing instructions)

- Branch: `claude/battlefleet-gothic-simulator-3sUkl`. Commit and push there
  (`git push -u origin claude/battlefleet-gothic-simulator-3sUkl`). `main` is untouched.
  **No pull requests unless asked.**
- Commit trailers: `Co-Authored-By: ...` and `Claude-Session: ...` lines as given by the session
  reminder. No model identifiers in commits or code.
- `bfgxr/` is the rules authority. The owner sends new booklet exports as zips; each one
  **replaces `bfgxr/` wholesale**. Afterwards read `bfgxr/CHANGES.md` (renamed fields, spelling
  changes, section renumbering) and re-run the tests. Never hand-edit generated files there.
- **Never invent rules.** When the booklet is silent or ambiguous, ask the owner. Record every
  answer under "Owner rulings" in `CLAUDE.md`.
- Before fixing anything an audit agent reports, check it against the booklet text yourself.
  Audit agents sometimes report things that aren't real.
- Web client (`web/`, `src/web_*.py`) and LAN multiplayer (`network.py`) are on hold.
- Owner style: short directives ("go", "do those next"). Propose the next batch of work at the
  end of each turn and let them pick. They correct rulings quickly, so ask instead of guessing.

## Testing

- `pytest -q`: 778 tests pass at handoff. Use `tests/conftest.py` `DiceStub` with realistic
  rolls listed one by one, and assert `dice._idx == len(rolls)`.
- `flake8 --select=E9,F src/` checks that the Tk files compile. pytest never imports them.
- GUI flow checks: `tools/gui_checks/*.py` drive the real `GamePanel`:
  `xvfb-run -a /usr/bin/python3.12 tools/gui_checks/<name>.py`. That Python has tkinter; the
  default one may not. The spectator scripts (`gui_spectator_*.py`) take `normal` or `expert`.
  They write screenshots and logs to /tmp. Any change to dialog order (for example brace
  prompts) means the scripts must answer the new prompts explicitly.

## Architecture recap

- The engine is pure Python in `src/`: models, game_state, movement, combat, ordnance,
  ordnance_movement, end_phase, boarding, hit_and_run, turn_controller, scenario,
  victory_points, geometry, los, terrain_effects, ai_player, lookahead_ai.
- The Tk UI is `game_panel.py` plus the `*_panel.py`, `*_dialog.py` and `*_ui.py` mixins. Only
  the main thread may touch Tk.
- `GameState` holds dicts. `get_ship_by_id()` returns a **copy**, so re-read a ship right
  before you change it and write it back with `gs.update_ship()`. Stale copies have caused
  several bugs, the latest a lost brace in torpedo code.
- Catalog: `booklet_ships.py` builds 174 ships from `bfgxr/data/ships.json` (weapon types,
  armour tuples, faction rules, Leadership tables). `ship_catalog.py` wraps it.
  `booklet_options.py` holds ship options and fleet commanders (Space Marines so far).
  `chapter_tactics.py` holds the Space Marine Chapter tactics.

## Done this session (high level, all committed)

- Movement: minimum straight distance before every turn; staged moves; blast-marker contact
  slowing and order of speed modifiers; squadron All Ahead Full (AAF) bonus rolls;
  'Ere We Go; Improved Thrusters.
- Ordnance:
  - Boarding torpedoes, including turning and friendly-target rules. Ordnance attacks the
    first valid target it contacts, and a ship moving into ordnance is attacked by it.
  - Two-pass ordnance movement, active player first.
  - Multi-role craft (Thunderhawks, Gun-Cutters, Fighta-Bommerz).
  - Attack craft orders and steering (`craft_target_id`); the AI re-targets each phase.
  - Launch capacity, fleet craft limits, recall; separate mine reloads.
- Orks: Gunz and Heavy Gunz (close and far strength, split rule), random firepower rolled when
  used, three-value armour. Tau Explorer "5+ / 4+R" armour.
- Space Marines and Grey Knights: crew rules, teleport assaults, honour guards, Secondary
  Shield, Strike Cruiser variants, Master of the Fleet, 9 Chapter tactics (Tactical Reserves
  affects macrobatteries only), Knights of Titan, Venerable Battle Barge VP.
- Brace for Impact timing (s.7) everywhere: before any roll; `offer_brace` + `gs.brace_hook`
  for ramming, explosions and asteroids.
- Export 7 audit fixes:
  - Hulks: they block line of sight and take damage, and damage re-rolls catastrophic. They
    have no shields or turrets and drift with blast slowing and terrain damage.
  - Siege and Bombardment cannons; Machine Spirit; target priority once per turn.
- Shield impacts: blast markers placed towards the attacker, fanned, no fixed cap.

## Remaining work (booklet gaps; see CLAUDE.md "Not yet matching the booklet")

1. Waves of attack craft (s.25). Every squadron currently acts alone.
2. Squadron fire per aspect and range group, and squadron vs squadron (s.8).
3. Commander re-rolls for all Leadership tests; secondary commanders (s.5).
4. The AI never targets enemy hulks.
5. Disengaging (s.37): shared escort-squadron test for a voluntary disengage, forced disengage
   at Ld 1 or less; measure celestial phenomena to their edge, not their centre.
6. Unsupported weapons and rules: Zzapp Gunz, Kustom Kannon, special movement, fortress
   weapons, short-burn torpedoes, barrage bombs, and the fleet-list part of Lightning
   Thrusters.
7. Other factions' booklet options and commanders, added one at a time like the Space Marine
   ones.

## Open questions for the owner (ask, don't guess)

- Hulk drift: should a hulk drift in every movement phase (current behaviour) or only in its
  owner's (s.34)?
- Grey Knights Battle Barge: does "+1D6cm extra" stack with Improved Thrusters? It currently
  plays as one extra D6.
- Readings to confirm:
  - Wings of Fury: re-roll raids that would have no effect.
  - Tactical Reserves: the 25% reduction rounds up.
  - Pack Hunter: needs at least two boarders.
  - Lightning Thrusters: vanguards fire at full only if they didn't turn.
