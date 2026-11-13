# AI movement: target-directed candidate moves

**Owner instruction.** This supersedes earlier movement notes, including the "15-degree heading steps"
part of `AI_DESIGN_feedback.md` task 2b.

Candidate moves should be built from targets, not just from evenly sampled headings. Even sampling stays
as a fallback, and takes over in the conditions in section 6.

**Owner caveat:** "do not take these as hard rules, it depends on the matchup". Candidates propose
moves; the values decide.

## 0. Why target-directed: speed and quality

**Fewer moves to score.**
- Even sampling of a 90° ship (headings every 15° × 3 turn points × 4 distances) is about 150
  candidates.
- Goal-directed generation for 1-3 targets × a handful of goals is about 20.
- Scoring is the expensive part, so this is the main saving.

**Better moves.**
- Useful end positions are often narrow: a 10cm range band, a rear-arc slice, the one heading that puts
  two enemies in one broadside.
- Even sampling only hits them if a sample lands there.
- Goal-directed candidates land on them by construction.

**Cost.**
- Cost scales with targets × goals, not with the ship's turn angle.
- Each goal costs a small geometric solve or a short 1-D search.
- So keep targets to 1-3 (the focus target plus the next one or two by expected VP), and goals to those
  relevant to the ship's weapons and situation.

## 1. How a target-directed candidate is built

Pick a goal, then solve for the move that achieves it.

**The move has three parts:**
- **Turn point:** after the minimum distance before turning (battleships 15cm, cruisers 10cm). Escorts
  can turn anywhere, including at the start.
- **Turn angle:** any value up to the ship's maximum.
- **Total distance:** from the minimum move (half speed) up to full speed.

**Solving for a goal:**
- For each goal, find the turn point, angle and distance that end closest to it.
- Use geometry where possible (e.g. heading to a point, then clamp the angle to the ship's limit).
- Otherwise use a short 1-D search over turn point and distance.
- If the goal is out of reach this turn, take the move that gets closest, and keep it as a "progress
  towards" candidate.

## 2. Goals, per target

**a. Bring the best weapons to bear.** End with the target in the arc of the weapons worth most expected
VP, within their range: broadside for broadside ships, prow for Tau and prow-heavy ships.

**b. Target range band.**
- **Turn sequence:** we move then shoot; the enemy then moves then shoots. At end distance d the enemy
  can close by up to its speed before firing.
- **Safe band** (we fire, they can't reply next turn): our range ≥ d > their range + their speed.
  - Example: Chaos 60cm guns vs Imperial 30cm guns on 20cm ships gives a safe band of 50-60cm.
  - 45cm guns on 20cm ships have no safe band against 60cm guns (45 + 20 = 65).
- **With no safe band,** aim for the distance where our damage now minus theirs next turn (the existing
  exposure term) is best.

**c. Armour facing.**
- When closing without firing, end prow-on where the prow has the best Armour.
- When firing this turn, turn to unmask at the end of the move.
- Exposure by Armour facing (To do 8a) values the trade-off (e.g. a 5+ side vs a 6+ prow).

**d. Out of the target's arcs.** End in its rear or a blind arc (e.g. a Lunar's rear, To do 8g). Use the
target's predicted position after its next move (the existing course prior).

**e. Torpedo and ordnance lines.** End with the target in the launcher's arc and on a clear lane. Reuse
the torpedo planner's lead and hazard logic.

**f. Teleport, boarding and ramming reach,** where those options are on and valued (To do 8h, 8j).

**g. Lock On next turn.** Lock On forbids turning, so a ship likely to want Lock On next turn should end
this move pointed so that a straight move keeps the target in arc.

## 3. Goals not tied to one target

- **Several targets at once:** the heading that puts two enemies in the same broadside, or one in each
  broadside.
- **Fleet support:**
  - base contact with the commander's ship or a carrier for massed turrets (existing screening rule);
  - keeping squadron coherency.
- **Safety:**
  - the tangent heading past a hazard (asteroid field, cloud, blast markers, mines, incoming salvos);
  - out of the fire arcs of the most dangerous enemies.
- **Disengaging (crippled ships):** towards the nearest celestial phenomenon within 15cm (+3 Ld, s.37),
  or the nearest table edge.
- **Scenario objectives** (To do 7) as goals, once scenarios are modelled.

## 4. Fallback sampling

- Keep a small evenly spaced set so the AI can still find moves no goal predicted. For example: straight,
  plus a few headings at the ship's turn limit, at the 3 turn points, at minimum and full distance.
- Ships with 90° turns or special turning rules get more fallback headings and more variations around
  each goal. Owner: more thinking time for ships beyond the 45° baseline.

## 5. Efficiency

- Score goal candidates first.
- Prune early with the cheap terms (guns that bear, hazards).
- Run full exposure scoring only for the best 20 or so.
- In the expert search, try goal candidates first: alpha-beta prunes far more when the best move comes
  first.
- Deduplicate candidates that end within a small distance and angle of each other.

## 6. When even sampling beats target-directed, and the hybrid to use

**Even sampling is more efficient when:**
- **Crowded fights:**
  - many enemies in reach make targets × goals larger than a coarse grid;
  - each goal costs a solve;
  - capping at 1-3 targets risks missing the one that matters.
- **Dense hazards or incoming ordnance near the ship:** the best move is often a gap between hazards,
  which no goal predicts and even samples find.
- **Small reachable area** (slow or crippled ships, Burn Retros): a few even samples cover everything,
  with no solves.
- **Caching:**
  - even-sample end positions depend only on speed, turn angle and turn rule, so they can be precomputed
    per ship class and batch-scored;
  - goal candidates depend on the situation and must be built fresh.
- **Goals incomplete or wrong** (early development, unanticipated situations): sampling is the only
  source of moves outside the goal list.

**Target-directed is more efficient when:**
- there are few relevant targets;
- the ship's reachable area is large (fast ships, 90° turns, escorts);
- the useful positions are narrow.

That is most of a typical game.

**Hybrid, per ship, per turn:**

**a. Always:** generate goal candidates for the top 1-3 targets, plus the small fallback grid.

**b. Switch to a denser even grid** (goals still included) when:
- goal candidates would outnumber the dense grid;
- hazards or incoming ordnance are dense along the ship's reachable area;
- the reachable area is small.

Choose by estimated candidate count against the coverage needed.

**c. Coarse-to-fine:** refine the best few candidates from either source with small local changes to
turn point, angle and distance (hill-climbing) until the scores stop improving.

**d. Time budget (anytime ordering):**
- order: goal candidates, then the grid, then refinement;
- stop when the per-ship budget runs out;
- the expert search uses the same order for alpha-beta move ordering.

**e. Diagnostic:**
- log which source produced each chosen move (goal type, fallback grid, refinement);
- if the fallback grid often wins, a goal is missing or wrong: fix the goal rather than adding samples.

**Unknowns:** the crossover points in (b) are not known yet. Measure them in the engine (candidates scored
and time per ship, against move quality) rather than guessing.

## Dependencies

- Build To do 8a (Armour facing) and 8f (range brackets) first; goals b and c come from them.
- This replaces the 15-degree heading steps of feedback task 2b with goal-directed candidates plus a
  fallback set.
- Task 2a's turn points and task 2c's 50% minimum move still apply.
