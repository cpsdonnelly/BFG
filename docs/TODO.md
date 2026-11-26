# To do (open items)

Only what is still open. Each item's full text, with everything already built, is in
`docs/TODO_DONE.md` under the same number (owner: finished work moved out so it doesn't
take up space, kept to look up for revisions). Item numbers are IDs cited in code and docs.
When an item is finished, move its remaining lines to TODO_DONE.md. The lists below were
taken from each item's own "Not yet" / "Still to do" notes (item 7 rewritten by hand); a
note may have been built later in the same item, so check TODO_DONE.md before starting one.

Item numbers are IDs (code comments and docs cite them), not the order. Agreed order
(owner: the order otherwise isn't hugely important, follow the dependencies; the last two
are fixed by the owner):
1. To do 15: the rules bugs from the code review (each with a test). Done.
2. To do 16: performance fixes and a headless multiprocess game runner (done but the
   display-free runner and a repeatable expert, which wait for 18 and 17).
3. To do 17: recording and replay (seeded dice, structured events, full snapshots, viewer).
4. To do 18: code structure (rule dispatch, scenario registry, weapon-value helper, central
   AI weights, rules out of the UI), with To do 30 (exact hit distributions for the AI's
   threat and VP values) on its weapon-value helper: owner, keep 30 now (small, half done,
   improves every game the current AI plays, the golden set included). The `ai_player.py`
   split moves to the port (owner): the AI is rebuilt there.
5. To do 25: fleet building completeness (every ship upgrade, fleet option and leader
   selectable; the owner's 1000pt fleets as validation test cases).
6. To do 24 and 31: the AI list builder (personalities, validation and repair; for players
   too), with the log of the places it decides at random. Built (engine and a command-line
   tool; the window button with To do 26).
7. To do 28 and 29: AI deployment (buff ships last, escort squadrons and formations, capital
   squadrons, squadron sizes from the fleet list) and commander placement.
8. To do 26 and 27: the demo reworked (the old demo fleets removed, random terrain Cruiser
   Clash, choose both fleets and the mode) and favourite fleets (save a fleet on quitting).
   Last of 5-8 (owner): the demo needs random fleets (24) and is the most window-dependent
   task. Before the port only minimal Tk versions (also of new dialogs); the full versions
   are built once, in the browser window (see "Window and port", owner).
9. To do 22: team play (several players a side; needs 18's game flow out of the Tk panels).
10. To do 19: Dark Eldar and Tyranids (also completes the last demo fleets).
11. To do 14: the Eldar and Necron gaps.
12. To do 4 and 5: daemonships, Ordos, Inquisitors, Veteran Bond-Captains; special movement
    (Space Hulk, Rok, Nicassar, Kroot), fortress weapons, Pthuxutl, Man O' War.
13. To do 13: a small comparison of the three ordering systems on the current engine
    (owner: now, small); the large experiment runs, the expert AI per unit and the rest after
    the port.
14. (Moved into the port, owner: To do 11, 10 e and 8, the rest of the rules-based AI:
    deeper expert hazards, more coordination rounds, two-turn expert root moves, Brace's
    remaining bits, 8 d / g; built on the rebuilt AI in the new language.)
15. To do 7 and 9: the small gaps; the Decoy sub-plot with per-player visibility in the
    engine (owner: the AI knows only what its player could see, never which ship is the
    decoy; the human-vs-human hidden mode waits for online play).
16. To do 21: the replay system as the comparison standard, completed before the port: every
    kind of event covered (the rules and factions added after step 3 included), a
    versioned, language-neutral record format, a Python replay verifier and a golden set of
    recorded games covering every faction and scenario. The port's first milestone is
    reading and replaying these records.
17. Third last, To do 20: port the engine to Rust in a new branch (the engine to parity
    with the golden games, the tests and booklet checks with it, then the AI rebuilt,
    including the deeper AI work from step 14 and the AI split; Python retired at parity).
18. Second last, To do 23: online play, peer-to-peer lockstep (owner: just before the
    ML-trained AI; needs 17's events and seed, 18's game flow, 22's seats, 21's exact
    determinism; each client runs the ported engine).
19. Last, To do 12 then 1: the ML-trained AI (learned evaluation, then weight tuning); on hold
    until the owner says to start; built on the faster engine, kept separate from the current
    AI, never replacing it.
(Steps 5-8 ordered by the owner; otherwise the order isn't hugely important, follow the
dependencies.)

Window and port (owner rulings):
- The long-term window is the browser (the Rust engine compiled to WebAssembly), since online
  play needs it. Tk stays as a development and test window only; before the port build only
  minimal Tk versions of the demo, favourites and new dialogs; full versions once, in the
  browser.
- Python is retired as the reference once the port replays every golden game identically;
  the tests and booklet checks are ported with the engine.
- Rust determinism is designed in, not assumed: a pure-Rust maths crate (libm) or fixed
  point for all game maths (std sin / cos use the platform library); no HashMap iteration
  order in game logic; no multithreaded game state; a seeded RNG that is part of the record.
Done: To do 2, 3, 6; most of 7.


1. On hold until the owner says to start (owner); when built, kept separate from the current
   AI, never replacing it: tuning the AI's judgement weights (listed in "AI: how it decides"). Keep
   it in mind, but it is hard work, so leave it be for now: don't retune them unless the
   owner asks. Example worth a look later: a lone healthy cruiser facing three full enemy
   cruisers disengages under the current model. Owner (AI design feedback): do it, but as
   the LOWEST priority, after To do 11 and 12. Method agreed: CMA-ES (not a genetic
   algorithm); tune the judgement weights only, never rule-derived values (25% / 100% / 10%
   VP, Tau 5/6, the 10.5cm explosion radius, +14cm All Ahead Full, 0.5 per lance), and first
   replace the 0.35-per-battery-point rule of thumb with the exact Gunnery table (done, To
   do 30); paired
   evaluation with common random numbers (same seeds and scenarios, sides swapped), VP margin
   as fitness; an opponent pool (earlier weight sets, the untuned AI, hand-made styles);
   normal AI only (the expert takes ~75s a game); the harness doubles as a rules test (an
   optimiser finds degenerate strategies in the rules as well as in the AI); redo after any
   structural change. If weights must differ by matchup, make them functions of measured features
   (launch-capacity ratio, mean speed difference, range-bracket advantage, hits per point),
   never per-faction weight sets.
2. Strike planning by expected VP when the strike lands. Not yet: splitting assault boats or
   a wave already in flight, more than two waves, the turret-split bonus for split waves.
   (Built so far: TODO_DONE.md 2.)

3. Mines and torpedo bombers. Not yet: the salvo aimed by the lead / approach planner, Chaos
   "not if Stormbird gunships taken" (Stormbirds, To do 4), the Explorer's Bor'kan price.
   (Built so far: TODO_DONE.md 3.)

4. Named commanders. not yet: Rath's random refits and bought re-rolls, his battleship
   placement and the 1500 / 1000pt minimums, Abaddon's "You Have Failed Me", O'Mesme's crew
   skills, the Dominus Astra / Se'arle O'Mesme ships), daemonships, god-fleet boons (built:
   `booklet_options.GOD_BOONS`, only in their god's fleet list, needing that Mark: Veil of
   Lust (gunnery at it shifts right), Siren's Summon (0-2: enemy ships within 15cm fail
   every command check, Brace included; no plain Leadership tests either: a voluntary
   disengage test can't be taken (`blocked`, a squadron tests from a member outside 15cm),
   forced tests fail (asteroid / warp rift navigation, guided torpedo control, Heed the
   Machine Spirit), the AI's disengage value knows it; `tests/test_sirens_summon_ld.py`;
   sign-off answer 50: a forced disengage test (an escort leaving the table, Leadership 1 or
   less, Demiurg mercenaries) within 15cm fails with its normal result, `forced=True`),
   Miasma of Pestilence (no left shift within 15cm; ordnance attacking it destroyed on a 6
   as through blast markers, `ordnance_movement._resolve_ship_contacts`; the AI counts it
   and the Modern / Remastered blast-contact roll via `ai_hazards.attack_survival` in
   `best_route` and the torpedo planners; `tools/gui_checks/miasma_check.py`), Plague Arks
   (0-3: a Fire critical on the other side of a boarding action); not yet: the Berzerker
   Tide, Warp Beasts, Strands of Fortune; also built: Mark of Chaos Undivided,
   `src/chaos_undivided.py`: on the Warmaster's / Lord's ship, 25pts; once per game before a
   command check the fleet takes its Ld until the end of that player's turn, Ld changes
   meanwhile kept; `GameState.undivided_hook`, a human is asked with "Auto (best)", the AI
   uses it when the test gains 0.25 pass chance or the fleet a point of Ld on average
   (judgement); not yet offered before plain Leadership tests; Stormbird gunships,
   `booklet_options.STORMBIRDS`: on a Chaos Space Marine vessel, no cost given, the bays
   carry only Stormbirds (multi-role, as Thunderhawks: 4+, 20cm) at half strength each,
   rounding up, and exclude torpedo bombers), Ork kustom upgrades / clans (built:
   `booklet_options.ORK_KUSTOMS` on a Boss's or Nob's ship, one each, Big Boss +1, Mega Boss
   +2 (`kustom_count_errors`): Extra Turrets +2 max 6, Extra Power Field +1 shield, Mad Meks
   repairs on 4+, Mega Armoured Boarding Parties (crew +2, raids +1, enemy raids -1), Grot
   Riggers +1 Ld on Reload, Soopa Tellyporta 30cm (capital ships), More Dakka offered but
   not modelled; the Ork Nob (20); a Big Mek's extra repair die; clans Goffs (ram tests
   pass, turrets in boarding actions they start) and Evil Sunz (+2D6cm AAF) at +50% of the
   Boss, on his own ship only; not yet: Bad Moons, Deathskulls, Blood Axes, Snakebites, More
   Dakka, the Big Mek's hit restore, Nobz per 500pts, clan authority over further ships),
   the rest of the secondary commanders (Veteran Bond-Captains, Inquisitors; built: Elite
   Daemonhunters, Elite Captains, Bond-Captains, the Grey Knights Grand Master, see "Engine
   notes"), Inquisition Ordos. not yet: the Berzerker Tide, Warp Beasts, Strands of Fortune;
   also built: Mark of Chaos Undivided, `src/chaos_undivided.py`: on the Warmaster's /
   Lord's ship, 25pts; once per game before a command check the fleet takes its Ld until the
   end of that player's turn, Ld changes meanwhile kept; `GameState.undivided_hook`, a human
   is asked with "Auto (best)", the AI uses it when the test gains 0.25 pass chance or the
   fleet a point of Ld on average (judgement); not yet offered before plain Leadership
   tests; Stormbird gunships, `booklet_options.STORMBIRDS`: on a Chaos Space Marine vessel,
   no cost given, the bays carry only Stormbirds (multi-role, as Thunderhawks: 4+, 20cm) at
   half strength each, rounding up, and exclude torpedo bombers), Ork kustom upgrades /
   clans (built: `booklet_options.ORK_KUSTOMS` on a Boss's or Nob's ship, one each, Big Boss
   +1, Mega Boss +2 (`kustom_count_errors`): Extra Turrets +2 max 6, Extra Power Field +1
   shield, Mad Meks repairs on 4+, Mega Armoured Boarding Parties (crew +2, raids +1, enemy
   raids -1), Grot Riggers +1 Ld on Reload, Soopa Tellyporta 30cm (capital ships), More
   Dakka offered but not modelled; the Ork Nob (20); a Big Mek's extra repair die; clans
   Goffs (ram tests pass, turrets in boarding actions they start) and Evil Sunz (+2D6cm AAF)
   at +50% of the Boss, on his own ship only; not yet: Bad Moons, Deathskulls, Blood Axes,
   Snakebites, More Dakka, the Big Mek's hit restore, Nobz per 500pts, clan authority over
   further ships), the rest of the secondary commanders (Veteran Bond-Captains, Inquisitors;
   built: Elite Daemonhunters, Elite Captains, Bond-Captains, the Grey Knights Grand Master,
   see "Engine notes"), Inquisition Ordos. not yet: Bad Moons, Deathskulls, Blood Axes,
   Snakebites, More Dakka, the Big Mek's hit restore, Nobz per 500pts, clan authority over
   further ships), the rest of the secondary commanders (Veteran Bond-Captains, Inquisitors;
   built: Elite Daemonhunters, Elite Captains, Bond-Captains, the Grey Knights Grand Master,
   see "Engine notes"), Inquisition Ordos. (Built so far: TODO_DONE.md 4.)

5. Unplayable units. not yet: the reload roll's double / double-6 malfunction (the command
   check keeps only the total) and exterminating planets): special movement (Nicassar
   Caravan, Kroot Warsphere, Space Hulk), fortress weapons (Ramilies, Fortress-Monastery),
   Pthuxutl disruptor cannon, Man O' War configuration. (Built so far: TODO_DONE.md 5.)

6. Smaller gaps, done. nothing listed open. (Built so far: TODO_DONE.md 6.)

7. Scenarios and sub-plots, engine and AI. All 31 booklet scenarios play (humans and AI,
   both turn systems). Open: the Decoy / Mimic Drive sub-plot (hidden identity) and the
   sub-plots' AI beyond kill bonuses (surveying features, the Treasure Haul's play); the
   Inquisition's Vendetta / Desperate Mission swap and one Secret Ploys per Ordo (Inquisitors
   not built); Kill the Admiral in the expert search's leaf and boarding crits reaching
   Bridge Smashed; racing Domination's 10 against the turn order; reinforcements entering
   along the long edges after turn 1 and choosing them / The Bait's pursued unit / Surprise
   Attack's full-alert units in the set-up dialogs; Alien Intervention's drifting hulk;
   alternating deployment (Cruiser Clash, Fleet Engagement); the scenarios' extra planetary
   defence points and forces limits in fleet building; Planet Strike's "extra assault
   points" ships; Orbit Lost; off-table entry (The Raiders / Rearguard / Surprise Attack);
   dialogs for players' set-up choices (Escalating divisions and markers, Navigate the
   Storm's rifts, Destroy the Docks' satellites and fields, the narrative Convoy's clusters
   and markers) and hiding contact markers from a human; barrage bombs' assault points, the
   biosphere choice, high orbit's free turns, the low orbit defences, the attacker placing
   patrols; the Planet Killer's forced disengage tests and Chaos ships keeping out of its
   shot; the Imperial AI leaving once 2000 VP ahead (Macharia); the AI docking damaged
   ships / aiming the Spear (Craftworld Assault); The Gauntlet's Running Battle; the AI
   weighing Parol's Bait's half value; Daemon Blockade's force limits and the AI's 10+D6cm
   mine hazard; the 13th Black Crusade variants. (Built so far: TODO_DONE.md 7.)
8. Matchup-aware manoeuvre. Not yet: the enemy's next move changing the facing it sees (8
   g), our own guns' values by the facing they hit (they use the target's lowest Armour). b.
   not yet: the table edge and turning to keep a broadside on a closing enemy. Not yet: Hull
   Krusha's automatic hit, aiming a turn earlier to set up a ram. Not yet: rams (s.12, on
   All Ahead Full: built above), combined boarding by several ships, Knights of Titan /
   Mechanicus re-rolls in the value. (Built so far: TODO_DONE.md 8.)

9. Smaller "Not yet" notes from the sections above, collected so none is lost. nothing
   listed open. (Built so far: TODO_DONE.md 9.)

10. AI special orders by expected VP. Not yet: e. Not yet: re-ordering the checks. a. (Built
   so far: TODO_DONE.md 10.)

11. AI design feedback. Not yet: goal f (teleport / boarding / ramming reach, with 8 h / 8
   j), pruning by cheap terms (not needed at ~40ms a ship). Still to do: hazards deeper in
   the search (the sim has no terrain or ordnance), chance points or sampled dice. c. not
   yet: trying against the attacker's weapon where the saving is worth most rather than the
   first one asked about (today greedy: each question counts the attacker's other weapons).
   Not yet: deployment by strategy. f. Not yet: softmax in Easy's targets / orders; Hard's
   coordination pass or tuned weights. (Built so far: TODO_DONE.md 11.)

12. Learned evaluation for the expert search (owner: the LAST task, with 1 after it, built on
   To do 20's faster engine; after To do 11 and its a-c). On hold until the owner says to start; when built, an experimental
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

13. Alternate activation. Not yet: a character's ship-only re-roll forcing only that ship;
   locked ships enforced for humans. Not yet: a human command phase that only offers orders
   (the order button is shown; the IGOUGO checks on orders still apply). Still to do: the
   experiments (they need the PDF's Appendix B fleets: Imperial Armageddon Sector against
   Eldar Corsair lists, so Eldar fleet lists or hand-built fleets, and a faster runner than
   the ~80s GUI game), the AI forcing activations, the expert AI per unit, a character's
   ship-only re-roll forcing only that ship, locked ships enforced for humans, a human
   command phase offering only orders.  (Built so far: TODO_DONE.md 13.)

14. Eldar and Necrons. Not yet: holofields against other direct non-gunnery attacks besides
   lances. Not yet: Eldar bombers re-rolling attack dice, fighters' 4+ save per wave and
   first interceptions, the AI's hazard / strike maths for stealthy ordnance. Not yet:
   Superstructure Damaged's 3+ roll on turning, a second prow crit destroying port /
   starboard weaponry. Gaps still open (listed above, plus): Eldar fleet lists (Corsair,
   Craftworld; they play with "No fleet list"), Kinship and Heroes, the Void Dragon,
   Ghostships, the optional Dying Race, the AI's lance values ignoring the holofield save,
   Come to New Heading's extra turn in the AI's MMS moves, the move dialog's MMS help. Not
   yet: splitting a lightning arc's firepower between arcs, the squadron-volley path. Not
   yet: port / starboard relays (target-dependent: weapons can't fire at targets in that
   arc), monument damaged blocking re-rolls and the nightmare field. Not yet: reinforcements
   arriving awake, conserving ships phasing out when hulked, the +1 per hostile Space Hulk /
   Planet Killer / Blackstone. Not yet: firing at their own hulks after a target priority
   check. Not yet: Bloodswarm Nanoscarabs (+1, Dynasty). Gaps still open: the nightmare
   field (no profile has one), lightning arcs splitting fire between arcs, port / starboard
   relay crits, monument damaged, firing on own hulks, reinforcements awake, phasing out
   when hulked as conserving, the ground defences / Deathseed / their craft, Dynasty
   upgrades, the Reaper / Shroud / Dirge special rules, the Harvest and Dynasty fleet lists,
   the AI's Necron play (it values guns as usual and never plans around power conservation
   or alert levels). (Built so far: TODO_DONE.md 14.)

15. Rules bugs found by the code review. Left: `optional_rules.set_ship_source` binding the
   live state (harmless while the expert's sim doesn't use a GameState; revisit in To do
   18), Fleet Engagement's AI formation pick by `random` (an AI choice: seeded with the AI's
   choices in To do 17), the "0.35 per point" estimates (replaced by the Gunnery table, To
   do 30). (Built so far: TODO_DONE.md 15.)

16. Performance and a headless runner: done (TODO_DONE.md 16).

17. Recording and replay. Still to do: replaying games with human players (the recorded
   human decisions fed back in place of the dialogs: needs To do 18's game flow out of the
   Tk panels, so it waits for it), the viewer stepping through a game (snapshots + events +
   the text log), `map_maker`'s terrain randomness (part of the start state for now). (Built
   so far: TODO_DONE.md 17.)

18. Code structure. nothing listed open. (Built so far: TODO_DONE.md 18.)

19. Dark Eldar and Tyranids. Not yet: ordnance swarms, escort squadrons' same weapon and
   sizes, Pheromone Rage, the Infested Space Station (Lance Battery, orbital station), Spore
   Field and Orbital Defence Spores. Not yet: Massive Haemorrhage's 2D6cm spray, the Tyranid
   Catastrophic Damage table, enemy ships in contact treating a spore cloud base as a blast
   marker, Mucous Membrane / Vanguard Link / Tenacity / Psychic Scream / Accelerated Healing
   effects, the AI's boarding value with 2D6. Not yet: the AI valuing which units to control
   (dearest first) and planning with instinct in its move values, boarding declared after a
   "board" move (contact weapons, slice 3), Living Barrier, Psychic Scream. (Built so far:
   TODO_DONE.md 19.)

20. Port the engine to Rust in a new branch (owner: third-last task, before online play; plan
   section 7; determinism and the window: "Window and port" under the agreed order). Python
   is the reference until the port replays every golden game identically, then retired (the
   tests and booklet checks ported too); the port must reproduce Python games exactly from the same seed and events (To do 21's records and
   golden games), which is what keeps the two from drifting; every booklet export and owner
   ruling lands in Python first. Order inside the port: the replay reader first, then the
   engine until every golden game replays identically, then the AI. Measure with the
   headless runner (To do 16) before and after.
21. Replay system as the comparison standard (owner: before the port, so both versions can be
   compared). Builds on To do 17's recorder, which comes early; this finishes it once the rules
   have settled:
   - an audit that every decision and roll the engine makes is recorded, including the
     rules and factions added since To do 17 (Dark Eldar, Tyranids, To do 4 / 5 units...);
   - a versioned, language-neutral record format (JSON with a written schema: start state,
     seed, rolls, events, snapshots), not tied to Python objects;
   - a Python replay verifier that re-runs a record and reports the first divergence (turn,
     phase, event, state difference);
   - a golden set of recorded games covering every faction, scenario, optional rule and
     both turn systems, regenerated and re-verified after each rules change;
   - a determinism test in the suite (record, replay, compare).
22. Team play (owner design): two teams, each team one side, so the engine stays two-sided
   (`player` 1 / 2 is the team) and the number of phases is unchanged. Players on a team are
   "like the same player but cut up": each ship belongs to one team member (a controller,
   human or AI), and all of a team's ships act in that team's phases together, whoever
   controls them. IGOUGO: the team's movement / shooting / ordnance / end phase as now, each
   member acting with their own ships, the phase ending when the team is done. Alternate
   activation's bags: unchanged, the dice just carry the controller's name (a drawn die of
   the team's lets the member it names activate one of their units; System 1's order and
   System 3's choice per team). Victory points, holding the field, scenario roles and turn
   order per team. Plan: a controller per ship (`Ship.controller`), team rosters on
   `GameState`, the UI's action filter by the seat at the screen, AI seats per controller,
   setup screens for teams. Owner rulings (no rules source, the owner's calls): each player
   has their own fleet list, commander and re-roll pool; points are split equally by default,
   adjustable at setup; fleets of different factions on one team follow their factions'
   normal allies rules; team-wide choices (System 3 first activation, end-phase blast marker
   removal, anything else the rules give "the player") are made by a nominated team leader,
   by default the player whose commander has the highest Ld.

23. Online play (owner: another task, the second last, just before the ML-trained AI;
   worked on before, not finished). Today: `web/` +
   `src/web_*.py` run the whole game in one browser on Pyodide (Python compiled for the
   browser, in a Web Worker, Netlify for the COOP / COEP headers) with their own older
   copy of the game flow (`WebGameContext`, simplified rules); `network.py` is desktop LAN
   only (the full state over a raw TCP socket each phase end). Neither is online play.
   Owner decision: peer-to-peer lockstep. Each player's client runs the engine itself
   (after the port, To do 20, the compiled engine, e.g. Rust built for WebAssembly in the
   browser, or the desktop app), both start from the same start state and seed, and they
   exchange only decisions (To do 17's events: moves, orders, targets, launches, prompts'
   answers); each applies the other's decisions, so both games stay identical. Needs:
   exact determinism (every roll from the seeded dice, no unseeded `random`, no
   order-dependent iteration over sets / dicts, float results identical on both machines),
   a state hash exchanged each phase to catch a divergence at once (then resync from the
   other side's snapshot), hidden information kept fair (secret formations, Escalating /
   convoy contact markers, Treasure Haul: commit a hash first, reveal later), a small
   signalling / relay service only for finding the other player and NAT traversal (WebRTC
   data channels; a relay when a direct link fails), reconnect by replaying the record, and
   the AI run by the client of the player who owns it. Dice (owner): online games can turn
   typed dice off (a game setting, off by default online; both players must agree to allow
   them; typed rolls go to the other side as a decision, tagged "manual"). Digital dice, two
   settings: "shared seed" (both clients know the seed from the start: simple, but a modified
   client could read every future roll and a player choosing the seed could pick a good
   one; fine between friends) and "cheat-proof" (commit-reveal: each side commits a SHA-256 hash of a
   random secret of 128+ bits, then both reveal and the roll comes from the two together, so
   no one picks the dice; new randomness is revealed for each roll, after the decision it
   follows is locked in, never once per game or per phase, which would let a modified client
   read ahead; each side commits at the start to a hash chain of secrets and reveals the next
   link with each roll, one message each way; it guarantees fair, unpredictable dice
   only, not against outside help). Disconnects (owner): never an automatic loss. The game
   is its record (start state, seed / commitments, rolls, events) and both sides hold it, so
   a disconnect pauses the game and either player resumes it later (the two records and a
   state hash compared, the side behind catches up from the other's); a stalling player
   gains nothing, since its committed chain fixes the secret it must reveal on return; a
   forfeit only after a time limit both players agreed in setup (off by default). Play by
   mail (owner: must be possible): each player's turn is sent as a file / message carrying
   its decisions and the record. Dice by mail (owner): two options, shared seed (trust) and a small
   signing dice service both trust (as play-by-mail dice servers do; fair with neither
   player online, but a server); not the opponent's client answering online, which isn't
   play by mail. Default for play by mail: shared seed (owner). Not commit-reveal ahead of time:
   secrets handed over in advance let a player read its own turn's rolls. Owner decision: cheat-proof is the online default; shared seed is an
   option the players can choose instead. Team play (To do 22) adds one peer
   per seat. Retire `WebGameContext` and the LAN `network.py` rather than extend them.
24. AI list builder. Not yet: reserves and detachments, the builder in the window (a minimal
   Tk button, To do 26's demo), squadron formations and capital squadrons (To do 28),
   commander placement after the Ld roll (To do 29), upgrades bought by role rather than at
   random. (Built so far: TODO_DONE.md 24.)

25. Fleet building completeness: done (TODO_DONE.md 25).

26. Demo rework. Not yet: the full version in the browser window. (Built so far:
   TODO_DONE.md 26.)

27. Favourite fleets: done (TODO_DONE.md 27).

28. AI deployment. not yet: deployment by strategy, the alternating deployment orders, the
   players' formation setter. (Built so far: TODO_DONE.md 28.)

29. Commander placement. Not yet: secondary commanders (Strategic Commanders, Dracons,
   Veteran Captains...), the Rogue Trader detachment's man o' war (men o' war aren't built).
   (Built so far: TODO_DONE.md 29.)

30. Exact hit distributions for the AI's threat and VP values. not yet, the sim ships carry
   no special rules; a cached lookup, about 0.4 microseconds a weapon). Not yet: exact
   distributions in place of the Poisson counts (`poisson_at_least`; needs `damage_vp` to
   take a hit distribution rather than a mean, and the phase's committed fire kept as one
   per target), the wave / CAP / turret chain by DP. Not yet: Lock On's re-rolls and low
   orbit's 4+ to fire in the estimate; the shield bypass in our own target choice (`shot_vp`
   takes all hits through the shields). (Built so far: TODO_DONE.md 30.)

31. Log of random decisions: done (TODO_DONE.md 31).

32. Playability. Still to do: the other seven fleets (catalog gaps: Tau Protector's Emissary
   options, Ork kustom force field / zzapp gun swap / looted vessels, Necron Dynasty
   upgrades, Eldar commanders, Dark Eldar and Tyranids, To do 19 / 25); the AI doesn't
   deploy its own ships (the human places them or presses Auto-Place; To do 28); with "No
   fleet list" the Edit dialog still offers every list's options (s.4: no restrictions,
   kept).  (Built so far: TODO_DONE.md 32.)

33. Guessed values to compute. Not yet: the squadron brace's gain from the hits on the other
   members. - Boarding crits on the target's own table: `hit_and_run.boarding_crit_value`
   (as `boarding._boarding_crit_check` rolls it: an escort 1 damage, else a D6 at least 2 on
   the raid table after the cascade; a Haemonculi ship's crit a Fire; Pain Frenzy's re-roll
   of a weaker result), used for all four crits in `ai_hazards.boarding_vp`. (Built so far:
   TODO_DONE.md 33.)

34. Strategy candidates for every ship. Not yet: the easy AI (no search: it never tries
   them), squadrons planning one heading, strategies longer than 2 turns, the move score's
   firepower units in VP (its `max(1.0, value_per_hit)` floors), a strategy carried over
   between turns (each turn re-plans from scratch). (Built so far: TODO_DONE.md 34.)

