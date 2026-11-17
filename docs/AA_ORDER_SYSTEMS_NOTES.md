# Alternate activation: activation-order systems (notes for Claude Code)

**Status:** draft. Ciarán **slightly favours System 3** (dice in a bag with initiative adjustment), but
has not committed to it, and wants to be able to try all three in the simulator. So:
- build all three systems as selectable options, each fully playable (by humans and the AI), and none
  hard-coded;
- make System 3 the default selection;
- don't treat Systems 1 and 2 as legacy or lower-priority stubs: he wants to play and compare them.

The owner-facing write-up, with all the numbers, is `docs/BFGXR_Alternate_Activation_Draft.pdf`. That PDF
is separate from the booklet, which stays IGOUGO; AA is not a booklet rule.

The common AA framework comes from the AA working notes (`docs/AA_ACTIVATION_NOTES.md`):
- per-phase bags;
- the working round: Command, Ordnance A, Shooting, Movement, Ordnance B, End;
- Brace as a command-phase order;
- ordnance 1 move on its first turn on the board, then 2;
- Eldar use MMS;
- boarding and ramming lock on declaration and resolve in the end phase.

Items those notes mark open stay open, e.g. shooting-before-movement order, end-phase cadence and the
"turn = round" ruling. Make them configurable rather than deciding them.

---

## 1. Definitions shared by all systems

- **Unit:** each capital ship is one unit, and so is each escort squadron, with one activation per
  phase. Make capital-ship squadrons configurable (separate units, or one unit); the numbers assume
  separate.
- **Unit initiative** = Ld − starting hits + 10.
  - Escort squadrons use their one rolled Ld and the **sum** of their ships' starting hits.
  - Fixed-Ld ships use their fixed Ld.
  - A ship carrying a Necron Obelisk uses the Ld it rolls (owner ruling: the Obelisk has no Ld of its
    own; as a Monument it still gets one free re-roll and may buy more).
- **Fleet mean initiative:** the average over the fleet's units, to one decimal place.
- **Gap:** the difference between the two fleets' means. The **edge holder** is the fleet with the
  higher mean.
- **When computed:** at game start, after Ld is rolled, using starting hits. Owner decision pending;
  make the recompute trigger configurable:
  - `start_only`;
  - `on_unit_destroyed` (Claude's proposal);
  - `abfg_turn_start`: Ld changes, plus −1 per crippled ship, applied at the start of each game turn.

  Never use current hits for this, since damage would then raise initiative.

## 2. System 1: fixed initiative order (`order_mode = "fixed_initiative"`)

Source: ABFG v0.3 text, supplied by the owner and summarised in the PDF, section 2. The initiative
formula image was lost in the owner's text copy; use Ld − starting hits + 10 from the AA working notes.

- **Shooting phase:** units act in initiative order, highest first, regardless of side.
- **Movement phase:** units act in **inverse** initiative order, lowest first, so high-initiative units
  move last.
- **Capital squadrons (ABFG):** one unit, using the highest Ld and the highest hits in the squadron,
  which may come from different ships. Make this configurable against our default of separate units.
- **Escort squadrons:** use summed hits.
- **Changes:**
  - Ld changes (e.g. Bridge Smashed) change initiative;
  - a crippled ship has −1 initiative;
  - changes apply only at the start of the next game turn.
- **Ties:** broken by Ld, then the admiral's Ld, then fleet strategy rating, then a dice-off per turn.
- **Forcing an activation (optional flag):**
  - at the start of the shooting or movement phase, a player may spend a re-roll to make one ship,
    friendly or enemy, activate first;
  - a character's ship-only re-roll can force only that ship;
  - if both players force, a dice-off decides: 2D6 + the highest Ld in the fleet, which admiral re-rolls
    can influence;
  - ABFG suggests doubling re-rolls as a test.
- **Not part of System 1 here:** ABFG's other changes. These are not our framework; don't implement
  them unless the owner asks:
  - end-phase damage;
  - 1-2-2-1 ordnance with a dice-off;
  - the Carry On and Disengage orders;
  - orders tested on activation.

  They explain why ABFG tolerates a large ordering edge.

## 3. System 2: vanilla bag (`order_mode = "bag"`)

- **Filling the bag:** at the start of each phase, each side gets one die per unit that can activate in
  that phase.
- **Drawing:** draw uniformly at random. The drawn side activates one of its not-yet-activated units of
  its choice.
- **End of phase:** the phase ends when the bag is empty.

## 4. System 3: adjusted bag (`order_mode = "bag_adjusted"`)

### Band table

Thresholds and rates must be configurable (owner may retune after playtesting).

| Gap | Result |
|---|---|
| < 0.5 | no edge holder: plain bag (System 2) |
| 0.5 to < 1.5 | edge holder chooses which side takes the first activation each phase |
| 1.5 to < 3 | choice + ceil(units / 3) extra dice |
| ≥ 3 | choice + ceil(units / 2) extra dice |

"Units" is the edge holder's own unit count. Recompute it whenever the gap is recomputed.

### Rules

- **The choice:** at the start of each phase the edge holder names a side. That side activates one unit
  without a draw and **removes one of its own dice from the bag**: every activation spends one of that
  side's dice. This removal matters. Without it the surplus die acts as a bonus die (at 5 units, edge
  share 0.20 becomes 0.33).
- **Extra dice:** they go in the edge holder's colour, and the bag is refilled each phase. They grant no
  extra activations: once a side has activated all its units in a phase, further draws of its colour do
  nothing.
- **Passing (proposed, not yet confirmed):** a side may decline a draw of its colour while it still has
  more dice in the bag than units left to activate. Implement it behind a flag (`allow_pass`), default
  on.

### AI decisions this creates

All valued by expected VP, as elsewhere in the AI:
- the choice (who goes first in each phase);
- passing;
- which unit to activate on a draw.

As a rough guide: acting early is usually right in shooting, and acting late is usually right in
movement (seeing the enemy commit). Don't hard-code either; value both.

## 5. Reference numbers (for unit tests)

**Edge share** = 2P − 1, where P is the mean over all (edge unit, opponent unit) pairs of
P(edge unit activates first). The model behind these numbers:
- shooting phase only;
- the edge holder activates on every own draw and never passes;
- squadrons are units.

The bag formula is exact. For nE edge units with k extra dice against nI units, with e and i units left
and k extra dice:

    pairs(e, k, i) = 0 if e = 0 or i = 0, else
        (e + k)/(e + k + i) · (i + pairs(e − 1, k, i)) + i/(e + k + i) · pairs(e, k, i − 1)

    edge share = 2 · pairs(nE, k, nI)/(nE · nI) − 1

**The choice:** the edge holder goes first with its die removed:

    P = (nI + pairs(nE − 1, k, nI))/(nE · nI)

Check values:

| nE v nI | Setting | Edge share |
|---|---|---|
| 5 v 6 | k = 0 (plain bag) | 0.00 |
| 5 v 6 | k = 1 (P = 0.571) | 0.14 |
| 5 v 6 | k = 2 | 0.25 |
| 5 v 6 | k = 3 | 0.33 |
| 5 v 6 | choice, k = 0 | 0.20 |
| 5 v 6 | choice, k = 1 | 0.33 |
| 5 v 6 | choice, k = 3 | 0.50 |
| 10 v 12 | k = 5 | 0.31 |
| 15 v 18 | k = 8 | 0.33 |

A Monte Carlo run of the engine's bag (with the AI never passing in shooting) should match these within
sampling error.

Owner's test fleets and full per-matchup results are in Appendix B and section 4 of the PDF.

## 6. Experiments the owner wants answered (after AA mode works)

These need the AI to play AA games. Run them only after the AI feedback tasks that affect play quality
(rules fixes, movement candidates) are done, and note that every result depends on the open framework
choices.

**1. Escort splitting.**
- Play the same lists with escorts in pairs and in full squadrons, under System 3.
- Owner intends splitting to be rewarded (dispersed escorts cover more space). The question is whether
  pairs are *dominant*.
- Use the PDF's escort builds (Appendix B: the same ships as pairs, squadrons of 3-4, or squadrons of 6).
  Owner estimates pairs, 3s and 4s are about equally common (no data), so test all three; sixes are the Ork-style extreme.
- Orks usually blob their escorts. Ork lists aren't modelled yet; add them when Ork AA testing starts.
- On paper, splitting raises mean initiative by 2.0-3.4, as much as the faction gap, and can hand the
  edge to the Imperials (PDF section 4).
- Report win rate and VP margin for each.
- If pairs win clearly, the fallback options are mean Ld only, or averaging over individual ships.

**2. Edge size.**
- Measure how win rate and VP margin change with edge share. Compare System 2, System 3, and System 3
  with rates one band higher.
- The question is whether a 0.3-0.6 edge is the right size when damage is immediate.

**3. Movement value.**
- Measure how often the AI uses the choice to go second in movement, and what that is worth.
- The calculations cover shooting only.

**4. System 1 against System 3** on the owner's 13 test matchups (PDF Appendix B), for reference.

## 7. Do not

- Don't put AA rules into the booklet export or `rules/*.md`; AA stays a separate draft.
- Don't settle on a system, band table or open framework item on the owner's behalf. System 3 is only
  the default selection, reflecting a slight preference. Expose options and report results.
