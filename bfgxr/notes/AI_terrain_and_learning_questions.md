# AI review questions: terrain, missing move terms, learning and tuning

These notes come from a discussion between Ciarán and Claude (November 2026). They follow on from `AI_DESIGN_feedback.md`. For each question:

- check the code against the rule quoted;
- say whether the AI already does it;
- if it doesn't, propose where it fits in the To do order.

Section numbers are booklet core-rules sections (`bfgxr/rules/00_core-rules.md`).

Tags:

- **Rules:** what the booklet says.
- **Owner:** Ciarán's ruling or instruction.
- **Suggestion:** Claude's design idea. Raise it with Ciarán if it conflicts with something already decided.

---

## 1. Terrain: does the engine and AI model each feature correctly?

### 1a. Gas and dust clouds (Rules, s.39 and s.11)

The rules:

- s.39: "To ships in base contact, gas and dust clouds have the same effect as a single blast marker in all respects (such as for shooting, movement, shields, etc)."
- s.11: "A ship reduces its shield strength by 1 for each blast marker touching its base (regardless of how it came into contact)." The shield returns when the ship leaves contact.
- Clouds do **not** block line of sight. Ships can fire through them.

Questions:

1. Does a ship in contact with a cloud lose 1 shield? Does that stack with real blast markers touching it (cloud plus two markers gives −3)? Does a large cloud still count as only one marker?
2. Do batteries fired at a ship in contact with a cloud take the right column shift? Does the ship's own battery fire take it too ("including those in contact with a ship's base", s.11)? Lances and nova cannon should be unaffected.
3. Under XR's wording, a cloud lying across the line of fire, touching neither ship, has **no** effect. Is that what the engine does? Ciarán hasn't ruled on whether this is intended, and Remastered hasn't been checked. Flag it to him rather than changing it.
4. Do the other blast-marker effects apply to a ship in contact with a cloud?
   - −5cm movement;
   - Under Fire (−1 Ld on command checks, s.6);
   - half repair dice in the end phase (s.36).
5. Damage rolls for ships moving through a cloud:
   - A ship with no shields, or with permanently disabled shields, rolls a D6 and takes 1 damage on a 6.
   - A ship whose shields are down only because of blast markers does not roll.
   - If a ship with no shields at all explodes from cloud damage, the explosion is resolved where it touched the cloud.
6. Teleports: a 1-shield ship in contact with a cloud has its shields down, so it can be teleported into (s.31). Does the teleport check see this, in both directions?
7. Ordnance moving through a cloud tests as for blast markers (owner ruling: XR's omission is an oversight).

### 1b. Asteroid fields versus planets (Rules, s.39)

Ciarán's starting view was that the only difference is that entering an asteroid field is a hazard. The rules give more differences than that.

**The same for both:**

- they block direct-fire line of sight (lances, gunnery, nova cannon);
- torpedoes that strike them detonate;
- drifting hulks that enter them are destroyed;
- either counts as a celestial phenomenon for the +3 disengage bonus within 15cm (s.37).

**Different:**

| | Planet | Asteroid field |
|---|---|---|
| Moving through | Free: ships pass over or under the template | Ld test (3D6 on All Ahead Full; escorts re-roll once). On a failure: D6 damage, shields block it but place no markers. Slowed 5cm either way |
| Ships on or in it | Line of sight to them isn't blocked; normal fire | Opposing ships inside may fire at each other only within 10cm, at half firepower, with no close-range shift. Crippled or braced ships inside can't fire at all |
| Attack craft | No rule | Destroyed on a 6 moving through |
| Torpedoes fired from inside | Removed when they reach the template edge | Detonate |
| Gravity well | Yes (see 1c) | No |
| Explosions | Not stated | Explicitly not blocked |
| Can be shot | No | Yes, after a Ld test; each hit places a blast marker at its edge |

Questions:

1. Does the engine implement every row of this table?
2. Does the AI's hazard pricing use the right test for each feature? Does it charge an asteroid field the 5cm slowdown even when the test is passed?
3. Squadrons test once. A failed capital squadron gives D6 damage to each member that touched the field. A failed escort squadron spreads D6 damage evenly among the escorts that touched it, in movement order. Is this modelled?
4. Does the engine stop braced or crippled ships inside an asteroid field from firing? Does the AI's brace valuation count that cost (feedback 4a)?

### 1c. Planets: gravity wells (Rules, s.39)

A ship that begins or ends its move in high orbit (inside the gravity well) may make a free turn towards the planet's centre, up to 45°. It needs no minimum distance, and is allowed even on All Ahead Full or Lock On. A ship in high orbit doesn't need to move, but a stationary ship counts as Defences on the Gunnery table.

Questions:

1. Are free turns in the engine?
2. Does candidate generation include them? They reach headings a normal move can't, so they belong with the turn points in feedback 2a.
3. Does the AI see the cost of sitting still, which makes the ship easier to hit?

---

## 2. Terms the hand-crafted move score may be missing (Suggestion)

The move score today is:

- guns that bear;
- minus exposure;
- minus path hazards;
- minus flagship danger;
- minus explosions;
- minus carrier exposure;
- plus screening.

For each item below: is it already covered, and is it worth adding?

**2a. Contact effects at the end position.** Clouds and blast markers are priced only as path hazards. Ending a move in contact with a cloud has two sides:

- incoming batteries take a column shift, but the ship has one fewer shield;
- its own batteries also take the shift;
- it is Under Fire on command checks and rolls half its repair dice.

Against a battery-heavy enemy, sitting in a cloud can pay. Against a lance-heavy enemy, the lost shield is pure cost, because lances ignore the shift. Compute this from the actual enemy weapons; don't treat the cloud as fixed cover. Ending inside an asteroid field has its own two-sided effect: the 10cm, half-firepower limit applies to both sides.

**2b. Gravity-well free turns** in candidates and values (see 1c).

**2c. Next-turn forcing.** Every ship must move at least half its speed next turn, with limited turns. An end position facing an asteroid field, warp rift, planet edge or table edge at short range can force a hazard next turn. Path hazards only price this turn's move.

Suggestion: price the hazard cost of the best reachable move next turn. It's cheap to approximate with the existing hazard model.

**2d. Gunnery table aspect and range shifts.** The 0.35 hits-per-firepower rule of thumb ignores the Gunnery table's columns (closing, abeam, moving away, Defences) and its range shifts. Once the exact table replaces it (feedback 12), heading becomes a defensive term too: presenting prow or stern to enemy batteries reduces the hits taken. This is separate from Armour facing (To do 8a).

Check: do guns-that-bear and exposure use the target's aspect relative to the firer?

**2e. Table edge.** It's mentioned only for kiting. Two terms are missing:

- a cost for losing room to manoeuvre or being forced off the table;
- a value of nearness to an edge for a crippled ship that may want to disengage.

**2f. Holding the Field VP.** AI_DESIGN says these aren't counted yet.

**2g. Ordnance in exposure.** Exposure is "half the hits the enemy could focus on that end position". Does that include torpedoes and attack craft the enemy can launch next turn, against non-carriers too? Or only gunfire?

**2h. Line of sight in move scoring.** Shooting respects line-of-sight blockers. Do guns-that-bear and exposure also check line of sight from the end position, so that hiding behind a planet or asteroid field is valued? Clouds must not be treated as blockers here.

---

## 3. Learned evaluation (To do 12): which features?

The hand-crafted AI's weights are the *parameters*; the things it measures are *features*.

**Owner and Suggestion:** the learned evaluation should get **every feature the hand-crafted score uses, plus more**. If it only had the same features combined linearly, it could learn nothing weight tuning can't. Its value comes from two places:

- **Interactions** a weighted sum can't express. For example, how much a given range is worth depends on whether the ship carries lances or batteries, the target's Armour and aspect, crippled status and turns left.
- **Features too awkward to hand-weight:**
  - line-of-sight cover from blockers;
  - contact with clouds and blast markers (with the shield effect in 1a);
  - next-turn forcing;
  - gravity wells;
  - edge distance;
  - ordnance in flight;
  - objectives, VP margin, turn number;
  - special orders in force, Leadership.

A model that learns its own features from raw positions would need far more games than are realistic here.

Questions:

1. Which of these features does the engine already compute, so they can be logged cheaply?
2. Is position logging (after each phase) in place?

---

## 4. Variance reduction for tuning and learning

**Suggestion: luck-adjusted scoring.** This removes dice noise from the score without touching the dice; statisticians call it a control variate.

- For every roll, the engine knows the expected outcome given the state: hit chance × damage × VP value of that damage.
- Luck for that roll = actual − expected. Sum each player's luck.
- Fitness = VP margin − (luck A − luck B).

Each luck term averages zero given the state when it was rolled. So subtracting it doesn't shift the average score, but it removes much of the dice noise. Compounding effects (a lucky critical changes later rolls) are only partly captured.

Combine it with the methods already in feedback 12: paired games with common random numbers and swapped sides, and VP margin as fitness.

- Dice streams desynchronise once decisions differ. Seed per ship per turn, not as one global stream.
- The same luck-adjusted margin is a better training label for learned evaluation than raw final VP.

Questions:

1. Can the engine record expected and actual outcomes per roll? Which roll types would be hard to do: criticals, Leadership tests, ordnance?
2. Is per-ship-per-turn seeding feasible with the current RNG?

---

## 5. How many games? (Claude's estimates; nothing measured)

Ciarán asked how many games learned evaluation would need to beat the hand-crafted weights. There's no reliable figure for BFG. Rough orders of magnitude:

- **Gradient-boosted trees** on about 30-80 features (the hand-crafted features plus interaction terms): a few thousand games to match the hand-crafted weights, roughly 5,000-20,000 to beat them clearly. Positions within a game are correlated, so the game count matters more than the position count.
- **Neural network learning spatial features:** TD-Gammon (backgammon, dice-heavy, far simpler than BFG) took about 300,000 self-play games, and over a million for its best versions. Expect hundreds of thousands of games for BFG.
- **Temporal-difference labels** (each position scored by the evaluation of later positions) or **luck-adjusted margin labels** get more from the same games than final-result labels.
- **Confirming an improvement:** a 55% win rate needs about 1,000 games to distinguish from 50%, fewer with paired seeds and margin scoring. That cost recurs at every checkpoint.

Ciarán's conclusion: the GA/CMA-ES tuning runs generate the data anyway, so do both. Gradient-boosted trees are the realistic target; a neural network is a long-term option at most.

Questions:

1. **The deciding number:** how many headless normal-AI-vs-normal-AI games per hour can the simulator run? Measure it before planning either To do 12 or weight tuning.
2. Can it run games in parallel?
