# Briefing: scenario extraction for the BFG:XR simulator

You are extracting Battlefleet Gothic scenarios from scanned fan zines into text. Other
Claude Code sessions build those scenarios into the owner's game simulator and then teach
its AI to play them. This file tells you how your work fits in and how to collaborate with
them through GitHub.

## The project you feed

- Repository: `cpsdonnelly/bfg` (GitHub). A digital play aid for Battlefleet Gothic:
  Extended Rules (BFG:XR): a Python rules engine with an expected-VP AI.
- The simulator already plays 31 booklet scenarios (Cruiser Clash, Domination, Convoy,
  Planetary Assault, Macharia's End...). Their rules text is in `bfgxr/rules/14_scenarios.md`
  and the campaign set pieces in `bfgxr/rules/15_*`; read one or two to see what a
  buildable scenario needs.
- Its sessions read `CLAUDE.md` (short) and `docs/CLAIMS.md` (who is doing what). Read both
  before your first delivery.
- Never edit anything under `bfgxr/`: it is generated from the owner's booklet (a .docx).
  Never invent rules: where a scan is unclear, say so (see "Unclear text").

## The pipeline (per bundle of scenarios)

Scenarios move through three stages, each its own claimable task:

1. **Extract** (you): scan to clean text, one file per scenario, in the format below.
2. **Build** (a simulator session): set-up, special rules, game end and victory in the
   engine, playable by humans, with tests.
3. **AI** (a simulator session): the AI values the scenario's objectives in expected VP and
   plays it to game over, both turn systems.

A stage starts only when the one before it is merged. Group scenarios into bundles (one
zine issue, or 3-5 related scenarios) so each bundle moves through the stages together.

## Claiming work

All claims live in `docs/CLAIMS.md` in `cpsdonnelly/bfg`, under "Scenario bundles". Before
starting a bundle:

1. `git fetch origin` and read `docs/CLAIMS.md` on every branch; check nobody holds it.
2. Add a row: bundle ID (`S1`, `S2`, ...), source (zine, issue), the scenario names, stage
   `extract`, status `active` (or `next`, at most three), your branch, the date.
3. Commit and push that change at once, before any other work.
4. When the bundle is merged, set its row to stage `build`, status `unclaimed`, so a
   simulator session can take it. The simulator sessions do the same when they hand on to
   `AI` and when they finish.

Rules shared by every session: one active claim and at most three next; take over another
session's claim only with the owner's say-so or after a week without movement (note it in
the file); edit only your own rows and your own files.

## Where your files go

- Work on your own branch of `cpsdonnelly/bfg` (whatever branch name your session was given).
- One Markdown file per scenario: `scenarios/fanzine/<bundle>/<scenario-name>.md`.
  The owner may later decide the scenarios belong in the booklet instead; until then this
  folder is the hand-off, and it is never edited by the simulator sessions except to add
  owner rulings (below).
- Keep the scans out of the repository unless the owner asks; quote the page reference.
- Open a pull request per bundle; the owner approves the merge.

## The scenario file format

Use these headings in this order, so the simulator sessions find every rule in the same
place. Write the rules as the zine states them; keep the zine's own numbers and wording.

```
# <Scenario name>

Source: <zine>, issue <n>, page <p>. Author (if given).
Extraction notes: <scan quality, anything reconstructed>.

## Verbatim text
<the full scenario text as printed, cleaned of scan errors only>

## Forces
Points, attacker / defender, fleet restrictions, special units or free assets.

## Battlezone and set-up
Table size, terrain and celestial phenomena, deployment zones with every measurement,
facing, who deploys first, maps or diagrams described in words (positions, distances,
edges).

## First turn

## Special rules
Each one as its own bullet.

## Game length and end

## Victory conditions
Including victory points, objectives and win / draw / marginal results.

## Unclear text
Every word, number or diagram you could not read for certain, with your best reading
marked "reading", and every rule the text leaves open, written as a question for the owner.
```

## Unclear text

- Never guess silently. If a number is smudged, give what you can read and flag it.
- Diagrams: describe them in measurements relative to table edges ("30cm from the left
  short edge, centred"). Where a diagram has no measurements, say so.
- Where a zine rule contradicts BFG:XR core rules, keep the zine's text and add a question;
  the owner decides.
- The owner's answers are added under the scenario's "Unclear text" as "Owner ruling: ...",
  by whichever session receives them.

## Talking to the other sessions

There is no direct chat between sessions. Use:
- `docs/CLAIMS.md` for who is doing what;
- the pull request description for what a bundle contains and its open questions;
- pull request comments for questions to a particular session.
Keep commits small and push often; the simulator sessions fetch your branch to plan ahead.

## Done means

A bundle is ready to hand on when every scenario file has all the headings, every unclear
point is listed, the pull request is open with a one-line summary per scenario, and the
claim row says `build` / `unclaimed`.
