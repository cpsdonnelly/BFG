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
  The current install is "export 15" (CHANGES.md: fifteenth update).
- **Never invent rules.** If the booklet is silent or ambiguous, ask the owner (AskUserQuestion
  works well), then record the answer under the matching heading in `CLAUDE.md`.
- Check what an audit or helper agent reports against the booklet yourself before acting on it.
- Owner style: short directives ("go", "continue", "yes"). Finish each turn with what is left and
  a proposed next step; ask about readings rather than guess. They answer rules questions
  precisely and sometimes paste sourcebook text.
- Web client and LAN multiplayer are on hold.

## Testing

- `pytest -q`: **869 tests pass** at handoff. `tests/conftest.py` `DiceStub` with realistic rolls
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

## Waiting on the owner

- Nothing. (Last ruling: in a squadron volley, shields knocked down by one group stay down;
  only the column shifts ignore blast markers placed during the volley.)

## Remaining work (agreed order: start with 1 and 2 together)

1. **Commander re-rolls for every Leadership test + secondary commanders (core s.5).** Today
   re-rolls (`TurnController.get_fleet_rerolls` / `use_fleet_reroll`, flagship
   `rerolls_remaining`) are offered only for command checks (`special_orders_ui`), disengage
   tests and guided torpedoes (`guided_control(reroll_fn=...)`). Extend to Brace for Impact,
   target priority, boarding, asteroid navigation and the rest. Secondary commanders
   (Strategic Commanders, Aspiring Champions, Elite Captains / Daemonhunters, Magi, Nobz...)
   don't exist: +Ld and ship/squadron-only re-rolls. Read s.5 before starting.
2. **Fleet commanders for the other factions** as fleet-builder options in
   `src/booklet_options.py` (pattern: Space Marine "Master of the Fleet (Ld 10)" and
   `INQ_LORD`): Navy Admirals (Vice/Fleet/Solar), Chaos Lord / Warmaster, Ork Warboss / Big
   Mek / Freebooter Kaptin with titles, Archmagos, Tau Kor'el / Kor'O, Rogue Trader. Costs and
   re-roll prices are in each faction file's Fleet Composition. Then add a `commander` entry
   to each list in `fleet_lists.py` / `fleet_list_data_other.py` so "750+ pts needs a
   commander" (Mechanicus 1000+, Orks one Boss per 500pts) is checked, and drop those
   sentences from the lists' `unenforced`.
3. **AI:** shoot at enemy hulks; use combined squadron fire (`combat.plan_squadron_volley`).
4. **Disengaging (s.37):** shared escort-squadron test for a voluntary disengage, forced
   disengagement at Ld 1 or less, celestial phenomena measured to their edge.
5. **The ordinary profiles' own refits** from ships.json notes, one at a time (Mars Targeting
   Matrix, Exorcist prow torps, Repulsive extra shield, ...).
6. **Smaller gaps** (see CLAUDE.md): attack craft flying straight / torpedo collisions checked
   only at the end of the move; multi-role fighter-bomber suppression choice; resilient wave
   splitting; low orbit and planetary assaults (barrage bomb assault points); unplayable ships
   (Zzapp Gunz, Kustom Kannon, special movement, fortress weapons).

Watch the context window: read rules sections with targeted `sed -n` ranges, delegate long
transcriptions (as done for the Chaos/Ork/Tau/RT fleet lists) and verify a sample against the
booklet yourself.
