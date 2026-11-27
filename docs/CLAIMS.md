# Task claims

Owner: several Claude Code sessions (the owner's and collaborators') may work on this
repository at once through GitHub. Each session claims the task it is working on plus a few
to do next, so no two sessions start the same work. Task numbers are the To do IDs in
`docs/TODO.md`.

## Rules

1. Before starting a task, fetch the latest `docs/CLAIMS.md` from every working branch
   (`git fetch origin` and read it there) and check nobody else holds it.
2. Claim it here with your session's branch name and the date, commit and push at once.
   Hold one task "active" and at most three "next".
3. A claim may be taken over only with the owner's say-so, or when it hasn't moved for a
   week (note it here).
4. Work on your own branch; open a pull request to merge; the owner approves merges to
   `main`.
5. Shared status files (`docs/STATUS.md`, `docs/TODO.md`): add only your own dated section
   or edit only your own task's lines, to keep merges simple.
6. When a task is finished: move it to "Done" below, move its lines from `docs/TODO.md` to
   `docs/TODO_DONE.md`, and promote your next claim to active.
7. Every pull request runs the full test suite, and for AI changes one seeded game with
   `--replay-check` (replays must stay exact).

## Claimed

| Task | What | Status | Branch | Since |
| --- | --- | --- | --- | --- |
| 22 | Team play (several players a side) | active | claude/battlefleet-gothic-simulator-3sUkl | 2026-11-26 |
| 19 | Dark Eldar and Tyranid gaps | next | claude/battlefleet-gothic-simulator-3sUkl | 2026-11-26 |
| 14 | Eldar and Necron gaps | next | claude/battlefleet-gothic-simulator-3sUkl | 2026-11-26 |
| 33 | The remaining guessed AI values | next | claude/battlefleet-gothic-simulator-3sUkl | 2026-11-26 |

## Scenario bundles (fan-zine scenarios: extract -> build -> AI)

Each bundle moves through three stages, each claimed separately: `extract` (the
extraction session: scans to `scenarios/fanzine/<bundle>/<name>.md`, see
`docs/BRIEFING_SCENARIO_EXTRACTION.md`), `build` (a simulator session: engine, tests,
playable by humans) and `AI` (a simulator session: objectives in expected VP, played to game
over in both turn systems). A stage starts when the previous one is merged; on finishing a
stage set the row to the next stage, `unclaimed`.

| Bundle | Source | Scenarios | Stage | Status | Branch | Since |
| --- | --- | --- | --- | --- | --- | --- |

Unclaimed, in the agreed order: 4 and 5 (daemonships, Ordos, Inquisitors, special
movement units), 13 (a small comparison of the AA order systems), 7 and 9 (small gaps incl.
the Decoy), 34 (strategy planner follow-ups), 18's leftovers, 21 (the replay standard).
Fixed by the owner, not to be claimed early: 20 (Rust port), 23 (online play), 12 and 1
(ML-trained AI; on hold).

## Done

- 2026-11-26, claude/battlefleet-gothic-simulator-3sUkl: To do 33's four must-fixes (all
  re-added, Brace incl. squadrons).
