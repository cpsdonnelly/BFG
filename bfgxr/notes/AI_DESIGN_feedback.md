# Feedback on AI_DESIGN.md

This is feedback on `AI_DESIGN.md` from a review against the booklet's core rules (section numbers are
booklet sections; XR page numbers are the XR Rulebook pages the booklet cites).

Tasks are in priority order, highest first. Each item is tagged:

- **Rules:** what the rules say. Apply as written.
- **Owner:** Ciarán's instruction.
- **Suggestion:** a design recommendation from the review that Ciarán hasn't ruled on in detail. Treat it as
  the intended direction, but raise it with him if it conflicts with something already decided.

Owner's standing caveat still applies to all strategy: "do not take these as hard rules, it depends on
the matchup."

---

## 1. Rules corrections and checks

**1a. Failed command checks don't block Brace for Impact (Rules).** AI_DESIGN To do 10 says "a failed
command check ends all orders that turn (s.2)". That restriction covers the orders declared in the
movement phase. Brace runs on its own rules (s.7, XR p.21):

- If a ship fails a brace check, *that ship* can't try again until the ship, squadron or ordnance marker
  attacking it has finished all its attacks.
- Other ships may still brace.

So the order-prioritisation plan must not treat a failed movement-phase check as blocking braces in the
enemy turn.

**1b. Brace is decided per weapon (Rules, s.7).** A ship may brace against an attacker's lances after
not bracing against its gunnery, but only once per attacker per turn. Check the brace reaction makes a
decision before each of the attacker's weapons rather than once per attacker.

**1c. Check that gunnery values subtract shields (check).** AI_DESIGN says ordnance ignores shields
"and the values know that", but the battery and lance sections don't say whether hits are taken off
shields first. If they aren't, every gunnery value against shielded targets is inflated. Confirm in code.

**1d. Check the "damage short of a threshold" value (check).** "0.2 of the ship's value per hit" can't be
meant literally. For a 180pt, 8-hit cruiser that is 36 VP per hit, so four hits (144) would be worth more
than the cripple itself (45). Presumably it means 0.2 of points per hit, i.e. 0.2 × points / starting hits
(about 4.5 VP here). Confirm in code and fix the doc wording.

**1e. Mines (Rules, s.17).** Mines move exactly 10cm towards the nearest *enemy* vessel of the player who
laid them. They don't go for the nearest ship of either side. Check the hazard model uses the owner's
enemies.

**1f. Ork turrets (Rules, Ork faction rules).** Ork turrets hit on 5+ (not 4+), as well as firing at all
ordnance types. Check both parts are modelled.

**1g. Bombers attack the lowest Armour (Rules, s.20).** This is a rule, not an owner preference. Fix the
doc's attribution only; no code change.

---

## 2. Movement and heading logic

**2a. Turn points (Owner, with rule detail).** Current candidates are 5 headings × 3 distances, with no
stated turn point. Candidate turn points should be:

- **For capital ships** (not counting modifiers):
  - immediately after the minimum distance before turning (battleships 15cm, cruisers 10cm; s.10,
    XR p.13);
  - just after the minimum move (half speed);
  - at the end of the move.
- **For escorts:** they can turn at any point in their move, including at the very start. A turn at the
  start (turn, then go straight) reaches positions no capital ship can.
- **With Burn Retros:** no movement is needed before turning.

The "minimum distance before turning" and the "minimum move" are separate rules. For a 20cm cruiser both
are 10cm and the first two turn points coincide; for a 25cm cruiser they are 10cm and 12.5cm. Only forward
movement made in the current movement phase counts towards the distance before turning.

**2b. More heading samples for sharper turns (Owner).** *Superseded by `AI_movement_target_directed_candidates.md`: build candidates from targets, with a sampled fallback; the extra thinking time for sharper-turning ships still applies.* Ships don't all have the baseline 45° turn.
Ships with 90° turns (and anything with special turning rules) should get more thinking time, i.e. more
candidate headings. *Suggestion:* sample headings at a fixed angular step (e.g. every 15°) up to the
ship's maximum turn, so a 45° ship gets 7 headings and a 90° ship 13, rather than 5 headings for both.
Turn angle is any value up to the maximum, not only half or full.

**2c. Include the exact minimum move in the distances (Suggestion).** Distances are 60/80/100% of speed,
never below the minimum move. Add 50% (the minimum move itself, s.10). Ending a move as short as legally
possible is often what keeps a ship out of enemy range.

Also note a ship that doesn't move at least 5cm counts as Defences on the Gunnery table (s.10). That
matters for Burn Retros candidates.

**2d. Budget (Suggestion).** With 2a-2c, a 90° cruiser might have about 13 headings × 3 turn points × 4
distances, roughly 150 candidates against today's 15. If scoring is too slow:

- prune with the cheap terms (guns that bear, hazards) first;
- score exposure only on the best 20 or so;
- spend the extra time on 90° ships and escorts, where the reachable area is largest.

**2e. Coordination pass (Suggestion).** Movement is greedy ship by ship in fleet order, so each ship
optimises against ships already moved but not those still to move. Add a second pass that re-optimises
each ship against everyone's planned end positions (coordinate descent; one or two passes are usually
enough). This catches screening and mutual support that the first pass misses.

---

## 3. Expert AI: hazards and dice (Suggestion, high)

The expert AI replaces movement, and its simulation leaves out attack craft, hazards and blast markers.
So in expert mode, movement is the one decision made *without* the hazard pricing the normal AI has. It
can fly into an asteroid field (Ld test or D6 damage, s.39) or through blast markers.

- **Minimum fix:** add the normal AI's path-hazard cost to the expert's root candidates and to its
  evaluation.
- **Better:** replace dice-free resolution with expected values at chance points, or a few sampled dice
  outcomes.

---

## 4. Rule effects missing from valuations

**4a. Price Brace for Impact (Rules for the cost, Suggestion for the method).** The current trigger is
"expected damage reaches a quarter of remaining hits". Bracing also costs the ship, until the end of its
next turn (s.7):

- its gunnery, lances and ordnance strength are halved (halved again if crippled);
- it can't use special orders;
- if it's in an asteroid field, it can't fire at all (s.39).

Value brace like every other order: damage saved minus next turn's lost value. Saves apply only to hits
past shields. The commander's ship should brace earlier because its loss is worth more, which comes out
of the values; drop the fixed bias.

**4b. Command check modifiers (Rules, s.6).**

- **Enemy Contacts:** +1 Ld if any enemy ship is on special orders.
- **Under Fire:** -1 Ld with blast markers in contact.

Neither can take Ld above 10, and neither applies to leadership tests (only to command checks). Both
directions matter for order valuation (To do 10):

- putting our ship on orders makes the opponent's checks easier next turn;
- an enemy on orders makes our checks easier, so orders are cheaper for us.

**4c. Disengaging (Rules, s.37, XR p.38).** The test is a Ld test at the end of the movement phase:

| Situation | Ld modifier |
|---|---|
| Each blast marker within 5cm | +1 |
| A celestial phenomenon within 15cm (once only; anywhere during a radiation burst or solar flare) | +3 |
| Each enemy within 15cm, enemy ordnance markers included | -1 |

A failed test means the ship can't fire, launch or use special orders (except Brace) for the rest of its
turn. *Suggestion:* when a ship is crippled or likely to disengage, value positions near phenomena before
it tries.

VP for this (s.38): a non-crippled ship that disengages gives 10% ("Enemies Scattered").

**4d. Explosions (Rules, Appendix 5).** A plasma drive overload hits every ship within 3D6cm with lance
shots at firepower equal to half the ship's starting hits. It also destroys all ordnance within the
radius. A likely explosion beside an incoming wave or salvo therefore protects its neighbours; include
this in explosion values.

**4e. Teleports and orders (Rules, s.31).** A ship can't teleport in the end phase if it is crippled or
on any order other than Lock On or Reload Ordnance. The target must also:

- have its shields down;
- be within 10cm;
- have no more remaining hits than the attacker.

Escorts and defences with fewer than 3 starting hits can't teleport. Order valuation for
teleport-capable ships should include the raid they would give up.

**4f. Dust clouds (Rules + Owner ruling).** Ships in contact with a gas/dust cloud are treated as having
a blast marker in contact in all respects (s.39, XR pp.52-54). Ordnance moving through a cloud tests as
for blast markers; the owner has ruled XR's omission an oversight (Remastered states it). AI_DESIGN
already has attack craft dying on a 6 in dust clouds, which matches.

---

## 5. Shooting order (Suggestion)

Fleet focus decides targets but not the order ships fire in.

- **Batteries before lances:** shield hits place blast markers in contact with the target (s.11), and
  later batteries then suffer the column shift; lances don't. Against a shielded target, fire batteries
  before lances.
- **Shields down for teleports:** knocking shields down also opens teleport attacks in the end phase.

---

## 6. End phase and pre-game choices

**6a. Damage control by expected VP (Rules for the mechanism, Suggestion for the policy).** Each capital
ship rolls one D6 per remaining hit, and each 6 repairs one system (s.36, XR p.35). Dice are halved in
contact with blast markers. Escorts don't repair.

Value each repair:

- a fire costs 1 hit per end phase;
- a weapon is worth its next turn of fire if it will bear;
- an engine critical is worth what the ship loses by not turning.

The current fixed order (fires first) is a reasonable fallback.

**6b. Blast marker removal** is already listed as a gap; the rule is as AI_DESIGN states (s.36).

**6c. First turn (Rules, s.2).** The roll-off winner chooses to move first or second. Add a policy,
alongside deployment (To do 7).

---

## 7. Scale-free thresholds (Suggestion)

The re-roll bars (45 / 25 / 15 / 10 VP) mean different things at 500 and 2000 points. Express them as a
fraction of fleet points, or of points still in play.

---

## 8. Faction behaviour (Suggestion)

The faction list has no Eldar or Necron behaviour. Eldar MMS v2.0 (the booklet's Eldar section) plays
nothing like a generic fleet:

- two moves;
- holofields;
- Fragile;
- different turning;
- its own ordnance rules.

The generic AI will misplay them until these are modelled. The same goes for Necrons' rules in the
booklet's Necron section.

---

## 9. Matchup-aware manoeuvre: compute, don't script (Suggestion)

To do 8 b-g read as named doctrines (cross the T, kite, show the prow). Most should emerge from values
once two pieces are in the movement score:

- **8a:** exposure by Armour facing;
- **8f:** fleet-vs-fleet firepower by range bracket.

With those in place:

- kiting is the result when our best bracket is beyond the enemy's reach;
- showing the prow is the result when the prow is the best-armoured facing.

Build 8a and 8f first and check what behaviour appears before adding doctrine-specific code. This fits
the owner's "depends on the matchup" caveat better.

For per-faction and per-list variation, the values already adapt to actual profiles, points and refits.
What doesn't adapt is the global weights. If tuning (task 12) shows weights that should differ by
matchup, prefer weights that are simple functions of a few measured matchup features over separate
per-faction weight sets:

- launch-capacity ratio;
- mean speed difference;
- range-bracket advantage;
- hits per point.

This lets one tuning run cover lists it never saw.

---

## 10. Difficulty levels (Suggestion)

- **Easy:** choose actions with probability weighted by their expected value (softmax with a temperature)
  instead of at random among valid targets. Mistakes then look human: small ones often, large ones rarely.
- **Hard:** Hard currently equals Normal. Give it the coordination pass (2e) or tuned weights so it means
  something.

---

## 11. Learned evaluation for the expert search (Owner: do it; low priority, after tasks 1-10)

The owner wants both ML approaches: this one and weight tuning (task 12). Discussion notes follow.

### How the two approaches differ

**Weight tuning (task 12)** treats the AI as a black box:

- it sets the judgement weights, plays whole games and keeps the weight sets that score better;
- each game gives one noisy number (the result), so it needs many games and handles a couple of dozen
  parameters at most;
- it tunes the AI's decision rules (how much to fear exposure, how to discount the future).

**Learned evaluation** is supervised fitting:

- every logged position becomes a data point, labelled with how that game ended (final VP margin);
- a function is fitted that predicts the outcome from features of the position, using least squares or
  gradient descent rather than trial and error;
- one game gives dozens of data points;
- it can carry many more parameters, including interactions a weighted sum can't express (e.g. 30-45cm
  firepower worth more when the enemy is slower).

The two produce different things. Tuning sets how the AI weighs its options; the learned evaluation tells
the search how good a position is. The search then decides: it looks ahead, scores the resulting positions
with the fitted function, and picks the best line. The two combine: the learned function can replace the
hand-written leaf evaluation of the expert search while the normal AI keeps its tuned heuristics.

### Long-term ranking (Claude's view, not an owner ruling)

Weight tuning only improves the AI within its current structure. The structure itself caps quality:

- **candidates:** a move never generated can't be chosen;
- **missing rule effects:** gaps in the values can only be compensated crudely by tuning;
- **look-ahead:** a dice-free search blind to hazards misjudges positions.

Tuned weights also have to be redone after every structural change. Expected order of value:

1. rules completeness;
2. candidate generation (task 2);
3. search with dice (task 3);
4. learned evaluation;
5. weight tuning.

The ranking is fairly confident; the size of each gain for BFG specifically is not known.

### How a position is described (features)

BFG has no board squares, so positions are described by measured numbers, as chess engines did for
decades with material, mobility and king safety. Most of these quantities are already computed by the
normal AI:

- **Material:** hits remaining, points in play, crippled status, distance to each ship's next VP
  threshold, and VP scored so far.
- **Threat both ways:**
  - expected hits each side can deal next turn from current positions, arcs and ranges;
  - "guns that bear" (ours on them) and "exposure" (theirs on us) are these;
  - probably the most informative features.
- **Geometry as relative measures:**
  - distances between ships;
  - which arc each enemy is in, and which Armour facing it sees;
  - firepower by range bracket (To do 8f).

  Don't use absolute table coordinates; position and orientation on the table shouldn't matter.
- **In flight:** ordnance on the table and loaded bays, priced by the existing ordnance models.
- **Tempo:** turns left and the current VP margin; the same lead is worth more with fewer turns left.
- **State:** blast markers in contact, crits, special orders in force, commander re-rolls left.
- **Terrain and obstacles (Owner: the evaluation must know about these).** This covers:
  - asteroid fields, gas/dust clouds, planets and gravity wells, warp rifts and minefields;
  - drifting and burning hulks;
  - blast markers;
  - table edges and the sunward edge;
  - active effects (solar flares, radiation bursts).

  Terrain enters in two ways:
  - **Through other features:** the threat features must be computed with line of sight, so blockers
    reduce expected hits; the in-flight features must use the path hazard model.
  - **As features of its own,** always relative to ships, such as:
    - expected hazard cost of each ship's reachable moves next turn (from the existing hazard pricing);
    - whether each ship is in contact with a cloud or blast markers (shields, Under Fire, repair dice);
    - distance to the nearest phenomenon (the +3 disengage bonus within 15cm, s.37) and to the nearest
      table edge (disengaging, being pushed off);
    - share of enemy firepower blocked by line-of-sight obstructions (cover);
    - inside a gravity well or not;
    - whether ordnance paths to or from each ship cross hazards.

  Encode terrain like ships, by what it does to ships, not by where it lies on the table, so one fitted
  evaluation works on any table layout. Logged games must therefore cover a varied spread of terrain set-ups
  (random generation, s.39) or the evaluation will only know the layouts it saw.

**Variable fleet size:**

- **Start:** aggregate per-ship quantities (sum, average, maximum), or score each ship's expected VP change
  separately and sum the results.
- **Later (optional):** set-based neural networks (deep sets, graph networks).

**Baseline with no learning:** current VP margin + expected VP change over the next turn from the existing
threat model. This is roughly what normal-AI move scoring does now. Learning then refines it by fitting
feature weights and interactions to actual game outcomes.

**Alternative (rollout evaluation):** play the position out many times with the normal AI and random dice,
and average the result.

- It needs no features and includes every rule the simulator has.
- It is slow, and only as good as the normal AI.
- Use rollouts to generate labels, then fit the fast feature-based evaluation to them.

The continuous table matters more for search than for evaluation: there are infinitely many moves, so
search can only choose among sampled candidates. This is why task 2's turn-point and heading sampling
matters for the expert AI as well.

### Data generation

**Source:** this does not need weight tuning. Any self-play produces the data: the normal AI against
itself across a spread of factions, fleet lists and scenarios, logging every position (e.g. after each
phase).

**Volume:** a game gives dozens of positions (e.g. 8 turns × 2 player turns, logged after each phase), so
a few thousand games give on the order of 100,000 labelled positions. That is enough to fit an
evaluation with a few dozen features. Weight tuning needs more games than this, not fewer.

**Variety:**

- add a little randomness to AI choices during data generation (softmax with a temperature, as for Easy in
  task 10), so self-play doesn't repeat the same predictable lines;
- if task 12 runs, log its games too, since its population of weight sets adds variety.

**Iteration:** the evaluation learns position values *as the logging AI plays them*, so values from weak
play are weak. Iterate: fit, play new games with the improved search, refit.

**When to start:** only after tasks 1-3 (rules fixes, movement candidates, expert hazards). Games played
under wrong rules or with a cramped move set teach the wrong values.

---

## 12. Weight tuning (Owner: do it, at the lowest priority; tuning is on hold)

The owner wants this as well as task 11. Leave it until everything above is done, and redo it after any
later structural change, since tuned weights fit the code they were tuned on. When it is picked up:

- **Optimiser:** use CMA-ES rather than a classic genetic algorithm. It suits a couple of dozen continuous
  parameters under noise and needs far fewer evaluations.
- **What to tune:** only the judgement weights. Exclude rule-derived values:
  - the 25% / 100% / 10% VP values;
  - Tau missile 5/6;
  - the 10.5cm explosion radius;
  - the +14cm All Ahead Full;
  - 0.5 per lance.

  The 0.35 battery rule of thumb should be replaced by the exact Gunnery table rather than tuned.
- **Noise:** dice noise is the main cost.
  - Use paired evaluation with common random numbers: same seeds and scenarios for both candidates, sides
    swapped.
  - Use VP margin as fitness rather than win/loss.
- **Opponents:** evaluate against a pool (earlier weight sets, the untuned AI, a few hand-made styles) to
  avoid tuning to one opponent's habits or to engine bugs.
- **Speed:** use the normal AI only; the expert AI (~75s a game) is too slow.
- **Rules testing:** the same harness is useful as a rules test. An optimiser trying to beat the AI finds
  degenerate strategies in house rules (e.g. activation schemes) as well as in the AI.
