> **Note for Claude Code:** this is the July 2026 copy of the AA working notes. Where it conflicts with
> `AA_activation_order_notes_for_Claude_Code.md`, the newer notes win.

# Alternate Activation - Compatibility Notes

Working notes for making BFG:XR compatible with an alternate-activation (AA) mode.
These are **problems to solve, not finished rules**. Fixes are deferred; each item
records the issue and (where useful) candidate directions marked *TBD*.

## Scope

- The base game stays IGOUGO. AA lives in its own self-contained section that
  redefines the turn sequence only. The rest of the book is untouched.
- Chosen AA system (locked): keep the phased turn structure; use a **dice-in-a-bag**
  turn order (Bolt Action style); **per-phase bags** - a fresh bag for the movement
  phase, then shooting, then the shared ordnance phase, then the end phase. One die
  per activatable unit per side; draw one, that side activates one unit for that
  phase; repeat until empty, then next phase.

## Root cause of almost every problem

An **IGOUGO round is two player-turns**, so it contains **two of each phase** - two
ordnance phases, two end phases, and so on. A naive combined AA round runs **one of
each phase**. Therefore:

- Anything tied to **phase count** (it happens "every ordnance phase" / "in each
  player's end phase") runs at **half its normal cadence**.
- Anything tied to a **unit's own activation** (each ship moves once, shoots once)
  is **unchanged** - a ship activates once per round either way.
- Anything phrased **"per turn"** becomes ambiguous and must be remapped to either
  "per round" or "per activation."

Almost every problem below is one of those three. The cleanest structural fix would
address the whole first category at once (see "Fix-space" at the end), rather than
patching each rule.

---

## Category A - Cadence halving (phase-count-tied). The real balance issues.

### A1. Ordnance movement - *(your problem #1)*
Ordnance moves in **every** ordnance phase. IGOUGO gives two ordnance phases per
round, so a torpedo salvo or attack-craft wave advances **twice per round** while a
ship moves **once**. One combined ordnance phase per round drops ordnance to **once**,
i.e. **half speed relative to the fleets**. Torpedoes under-range and out-live their
usefulness; bombers and assault boats struggle to reach targets. Direction: nerfs all
ordnance.

### A2. Blast-marker removal - *(your problem #2)*
Removal happens in each player's end phase (the active player rolls a D6 and removes
that many loose markers). Two end phases per round → roughly **2D6 removed per round**.
Creation is driven by **shooting volume**, which is unchanged (every ship still fires
once per round). One combined end phase removes only **~1D6 per round** while the same
number of markers are laid down → **markers accumulate**, more column-shift penalties
and more premature detonations over time. Direction: clutters the board, indirectly
nerfs gunnery and ordnance survival.

### A3. Damage control / critical-hit repair - *(added)*
Section 26: repairs are attempted **in each player's end phase** ("both players can
attempt to repair critical damage during the end phase"). Two end phases → two repair
windows per round. Criticals are **inflicted** by shooting (unchanged per round) but
**repaired** in the end phase (halved). One combined end phase → ships repair criticals
**half as often** while taking them at the same rate → **criticals persist far longer**,
ships stay crippled/degraded. Direction: strongly amplifies the value of critical hits,
nerfs durability. This is the twin of A2 and just as significant.

### A4. Fire and other ongoing critical damage - *(added)*
Fire criticals (and similar ongoing effects) inflict their damage **in the end phase**.
Two end phases → a fire burns twice per round; one combined end phase → **once per
round**, so ongoing criticals do roughly **half their damage over the game**. Direction:
nerfs fire/ongoing criticals - the opposite direction to A3, and the two interact
(fires also get repaired half as often), so the net effect is non-obvious and needs
deliberate handling, not left to chance.

### A5. Celestial / environmental per-turn effects - *(added)*
Solar flares, radiation, warp and similar hazards resolve on a per-turn cadence
(section 29 uses "each turn" repeatedly). Whether these currently mean "each player-turn"
(twice per round) or "each round" changes their frequency under AA. Any hazard that
ticks per player-turn halves under a combined round. Needs an explicit cadence.

---

## Category B - "Per turn" phrasing that must be remapped. Mostly definitional.

These aren't balance breaks so much as ambiguities the AA section must pin down: does
"turn" mean the whole round, or a single activation?

### B1. Fleet-commander and character re-rolls - *(added)*
Re-rolls are "once per turn" (fleet commander; also Abaddon, Pirate Captains, etc.).
Under IGOUGO a fleet has one turn per round, so this is already ~one per round - but
under AA "per turn" must be explicitly fixed to **per round** (else, read as
per-activation, it multiplies and breaks command economy).

### B2. Special-order duration - *(added; verify)*
Special orders are declared and last relative to the turn ("until the ship's next
turn"). Under AA the natural mapping is **until the ship's next activation**, which also
neatly replaces the IGOUGO per-fleet command phase (declare on the draw). Needs stating
explicitly; confirm the exact source phrasing when we write it.

### B3. Nova cannon reload - *(added)*
"May not fire two turns running" must become "two **rounds** running" (or key off
activations), or the reload restriction evaporates/doubles under AA.

### B4. Faction "once per turn" abilities - *(added)*
Several faction rules use "once per turn" / "each ordnance phase" (Eldar, Orks, Tau,
Marks of Chaos triggers, etc.). Each must be remapped consistently with whatever B1-B3
decide. A single global ruling ("'turn' means 'round' unless stated as 'activation'")
would cover most of these at once.

### B5. Disengagement - *(added)*
Disengaging (section 27) is defined against "your turn" - declaring, testing, and
leaving the table. With no single block that is "your turn," AA must specify **when** a
disengage is declared and resolved (natural fit: on the ship's activation) and when
disengaged ships are removed.

---

## Category C - New interactions from interleaving within a shared phase

Per-phase bags preserve the important "all movement resolves before all shooting"
ordering, which is why the choice is sound. The residual issues are *within* a shared
phase:

### C1. Blast markers mid shooting-phase - *(added)*
In IGOUGO a player resolves **all** their own shooting before the enemy shoots, so
blast markers a player creates don't shift the enemy's fire until the enemy's turn.
Under a shared shooting phase with interleaved draws, markers laid by an early
activation now sit on the table and **apply column shifts to later activations in the
same phase** - including the same side's own later shots. This changes gunnery math and
hands an advantage to being drawn later (shoot through fewer of your own markers) or
earlier (shoot before the enemy clutters the lanes). Needs a ruling on whether
mid-phase markers apply within their own phase.

### C2. Shared ordnance phase interactions - *(added)*
In the single ordnance phase, ordnance moved/placed by one side can contact or threaten
enemy ships that have not yet activated that phase, and attack runs resolve against a
board that is still changing. Mostly a sequencing/clarity issue; specify resolution
order within the ordnance phase.

---

## Category D - Attack craft, CAP and ordnance persistence - *(added)*

Overlaps A1. Attack craft move and attack **per ordnance phase** and are removed after a
set number of phases / after attacking; CAP and interception key off the same clock.
Halving ordnance phases means waves under-move (A1) **and** their lifespan-in-phases
maps to a different number of rounds, shifting how long fighters screen, how far bombers
reach, and how CAP refreshes. Attack-craft endurance and CAP timing need restating in
round/activation terms rather than phase-count terms.

---

## Fix-space (deferred - your call)

Most of Category A is one problem wearing five hats: **the second ordnance phase and
second end phase per round have gone missing.** Broad directions, none chosen:

1. **Preserve the count.** Run the ordnance phase and the end phase **twice** per AA
   round (e.g. once after the movement/shooting bags for each "side-pass"), keeping A1-A5
   at their native cadence while movement and shooting stay single shared bags. Least
   rebalancing; slightly more phase handling.
2. **Rescale the effects.** Keep one of each phase but double ordnance movement, double
   blast removal, give two repair rolls, tick fires twice, etc. Fewer phases; lots of
   individual "×2 under AA" caveats, which is exactly the threading-through-every-section
   we wanted to avoid.
3. **Half-round unit.** Define the AA "turn" as a half-round so two turns still make a
   round with two of each phase. Cleanest conceptually, but changes how "per turn" reads
   everywhere and interacts with B1-B5.

Category B is best solved with **one global "turn = round" ruling** plus a short list of
explicit "per activation" exceptions. Category C needs a couple of one-line sequencing
rulings. Category D falls out of whatever A1 decides.

---

## Summary of problems

| # | Problem | Source |
|---|---------|--------|
| A1 | Ordnance moves half-speed relative to ships | you |
| A2 | Blast markers accumulate (removal halved, creation not) | you |
| A3 | Critical damage repaired half as often | added |
| A4 | Fire / ongoing criticals do half damage | added |
| A5 | Celestial/environmental per-turn effects change cadence | added |
| B1 | "Per turn" re-rolls need remapping | added |
| B2 | Special-order duration needs an AA definition | added |
| B3 | Nova cannon "two turns running" needs remapping | added |
| B4 | Faction "once per turn" abilities need remapping | added |
| B5 | Disengagement timing undefined without "your turn" | added |
| C1 | Blast markers shift fire within the shared shooting phase | added |
| C2 | Ordnance-phase sequencing against un-activated ships | added |
| D  | Attack-craft/CAP movement, lifespan and refresh cadence | added |

---

## Discussion summary & working decisions (turn structure + Brace)

**Working turn structure** (one round, both sides interleaved via per-phase bags):
0. Command phase - non-Brace special orders declared here.
1. Ordnance Phase A - on-board ordnance moves ("anticipated" movement).
2. Shooting phase.
3. Movement phase.
4. Ordnance Phase B - on-board ordnance moves ("reacted" movement; both reaction phases precede it).
5. End phase.

(Shooting-vs-movement order, and which ordnance phase new launches occur in, are still open - below.)

**Ordnance (fixes A1).** Two ordnance phases restore two-moves-per-round (IGOUGO parity), fixing the half-speed problem; on-board ordnance moves in both A and B. Separating them with the reaction phases preserves counterplay: OrdA is the move the target only anticipates (its reaction happened last round), OrdB is the move both movement and shooting sit in front of. This mirrors how IGOUGO ordnance already plays - one anticipated move (owner's turn), one reacted move (target's turn) - so the round-boundary gap is the same gap IGOUGO carries, not the naive-double pathology.

**Open - which ordnance phase launches new ordnance** (irreducible tradeoff, deferred):
- Launch in OrdA: new salvos get IGOUGO reaction cadence, but the carrier launches *before* it moves, losing the advanced-position launch (arc/closing) on every launch.
- Launch in OrdB: carrier launches *after* moving (vanilla position preserved), but a fresh salvo gets one un-reacted move in the next OrdA before the target can react.

**Brace for Impact - resolved by a duration rule, not a phase reorder.** The malus (no special orders, halved gunnery, halved lances, halved ordnance) applies from the moment of bracing through the ship's next activation *in each phase*: brace before firing this round → shooting halved this round; brace after firing → pay next round (matches IGOUGO). Phase-reordering (move-last, or fire-then-move) was considered and rejected: it breaks the ordnance dodge, inverts BFG's move-then-shoot loop, and only touches one of Brace's three malus phases anyway.

**Special orders (the five non-Brace).** Declared in the command phase / on activation; last until the ship's next activation (a full round). Command check folds into activation.

**Still open beyond the launch phase:**
- The end-phase halving problems - A2 (blast-marker removal), A3 (critical repair), A4 (fire damage) - are NOT fixed by the two-ordnance-phase change; the structure still has a single end phase, so these remain halved and need their own decision (parallel two-end-phase split, or doubled per-round effects).
- Shooting-vs-movement order within the round.

---

## Later decisions (from reviewing two fan AA systems)

Reference sources: the *Eldar MMS v2.0* fan pack (Amkreutz/Sigoroth) and *A Big Fleet Game (ABFG)*, a fan conversion of BFG to alternating activation. These informed the decisions below.

### Brace for Impact - now a command-phase order (supersedes the earlier duration rule)

Brace becomes a **pre-committed order declared in the command phase**, alongside the other orders, rather than a reactive declaration. This **replaces the Option 1 "duration" rule** recorded above.

Rationale: reactive Brace exists to keep both players engaged during the opponent's turn under IGOUGO. Alternating activation already keeps both engaged, so the reason for it being reactive is gone. Pre-committing kills the shared-shooting-phase exploit by construction - you commit before any activation, so you can't brace after seeing the fire. The full malus (no other order; halved gunnery, lances, and ordnance) applies for the whole turn from the start, so there's no "brace then shoot at full" window and no duration rule to write. Also folds all six orders into one command phase (tidy), and a face-down order token adds bluff.

Tradeoff (accepted): Brace stops being a reaction and becomes a prediction - you gamble a turn of halved weapons on anticipating incoming fire. Guess wrong and you waste the brace or eat an unanswerable alpha strike. Rewards reading the opponent over reacting.

### Eldar - use MMS under alternate activation (not the base book's MSM)

The base IGOUGO rules keep the Eldar's **Move-Shoot-Move (MSM)** identity. The AA module gives Eldar the fan **Move-Move-Shoot (MMS v2.0)** profile instead.

Rationale: MSM works only because your shooting and the enemy's shooting happen at different times - the Eldar fire prow-forward, then reposition into the gap before the enemy's separate return fire. A **shared shooting phase collapses that gap** (return fire lands concurrently), so the shoot-then-hide move has nothing to hide from. Both AA placements of the second move fail: before the shared shooting phase → Eldar slide out of arc then shoot freely (untouchable); after it (an ordnance-phase move) → they've already been shot in their exposed position and the reposition is a redundant free move (next round they move in the movement phase anyway). MSM's character is an IGOUGO artifact.

MMS is activation-native: both moves sit inside the movement phase (a double-move on the Eldar's activation), not a bonus move wedged between phases - so it doesn't create the untouchable window. Corroborated by the MMS designer notes, which call moving in the ordnance phase "just plain wrong" and state MMS was built to make Eldar "play more like a normal faction" by removing that move. So the property that makes MSM feel special under IGOUGO is the one that makes it AA-incompatible, and the fan fix is already the AA-compatible form. When Eldar gets a roster, MMS v2.0 is a plausible rules/roster source; the AA module references its move-move-shoot paradigm. (Eldar is held back until it has a roster; this is a future task.)

### Initiative system - one extra die in the bag ("Idea A")

> **SUPERSEDED (13 Nov 2026):** Idea A is replaced by the three activation-order systems in
> `AA_activation_order_notes_for_Claude_Code.md` (System 3, the adjusted bag, is the default). Keep this
> section for background only.

Add a lightweight initiative system on top of the per-phase dice-in-a-bag, because it rewards bringing nimble escorts rather than only line ships.

- **Mechanism:** the side with the initiative edge gets **one extra die of its colour in the bag**, reused across phases (same bag, no switching). Surplus draws beyond a side's unit count are no-ops (or a voluntary "pass"), so the extra die grants **no extra activation** - it just pulls that colour earlier in the draw order.
- **Why it works directionally without extra rules:** being pulled earlier is pure upside in the **shooting** phase (fire sooner) and a liability in the **movement** phase (you'd rather commit after the enemy). So Idea A is, emergently, *shoot earlier automatically* + *one reactive "hold" you may spend in movement* (decline the early draw once) - a clean expression of initiative from a single die in a single bag. It also preserves the choice to deliberately activate early (e.g. move first to dodge a ram or boarding), which the alternative (giving the worse-initiative side the movement-phase die, "Idea B") can't do - B just shoves you late. Idea A chosen over B: weaker blanket movement edge, but it keeps one bag all game and gives the player control.
- **Calculation:** use **average**, not total. Per-ship value ≈ `Leadership − Starting Hits + 10` (from ABFG); averaging is size-neutral and captures fleet *quality*, whereas total just rewards owning more hulls (backwards for a responsiveness stat). Escort squadrons count **summed hitpoints** for their value, so blobbing escorts tanks that squadron's initiative - rewarding small nimble screens over escort spam. Zero-arithmetic alternative: compare a value the fleet already has (admiral's Ld, or fleet strategy rating), trading the hits flavour for simplicity.
- **Effect on list-building (the point of adding it):** escorts read as high-initiative (≈ Ld − 1 + 10), two-shield cruisers (e.g. Lunar) as low (≈ Ld − 8 + 10), so a screen pulls a cruiser-heavy list's average up and tilts the die. Gives the cruiser-spammer a reason to bring escorts; Orks stay coherent (fragile ramships = responsive, big Terror Ships = sluggish).
- Token-equivalent (if dead draws annoy): higher-initiative side gets one "seize" per phase - spend in shooting to activate a unit now, spend in movement to force an enemy unit to activate now (delaying yourself). Same directional effect, no bag change.

### Boarding & ramming timing under AA

Not broken by AA so much as **decided** by it - the whole question is who commits first in the movement phase (rammer/boarder wants to move after the target; target wants to move after them). That tension is exactly what the bag and the initiative "hold" adjudicate (a point in favour of the initiative system).

- **Timing (from ABFG):** the lock applies the instant a board or ram is **declared during the movement phase** (both ships stuck, can't move or fire/launch); the actual boarding combat **resolves in the end phase in initiative order** (attacker's initiative), alongside hit-and-run and teleport.
- **Consequence to state plainly:** a ship boarded or rammed **before it has activated loses its move** - the cost of being out-positioned. Fair, because initiative gave the faster fleet the tools to do the positioning.

### Note on the end-phase model (cross-reference)

ABFG resolves the end-phase-cadence problems (A2/A3/A4, still marked open above) by **applying all damage, criticals, Brace saves, holofield saves, and damage control in the end phase**, with blast markers removed 1D6 per player. That's a more invasive restructure than the two-ordnance-phase approach we adopted for A1, but it's a coherent option for the still-open A2/A3/A4 decision. Not adopted yet - logged as a candidate.

### Launch-turn ordnance rule (Ciarán's idea) - candidate resolution for the OrdA/OrdB launch problem

**The rule:** ordnance gets **1 move on its first turn on the board; 2 moves every turn thereafter.**

**What it resolves.** This dissolves the open OrdA-vs-OrdB launch question by construction. The old framing forced a choice of *which phase* new launches occur in, each with an irreducible downside (OrdA = vanilla-style reaction but a pre-move nerf; OrdB = vanilla position but a fresh salvo gets an un-reacted move). This idea makes the **launch-turn move count** the lever instead of the phase, so the phase choice stops mattering: ordnance launched during the movement phase simply catches only the remaining ordnance phase (OrdB) that turn, giving it 1 move, and then picks up the full OrdA + OrdB = 2 moves from the next turn onward. Simple to track (a token on newly-launched markers, cleared at end of turn) and activation-agnostic.

**Vanilla baseline - checked, and it makes this a deliberate nerf.** The XR rulebook (p.27, "The Ordnance Phase - Types of Ordnance") says torpedoes launch *"moving a distance equal to their speed and continuing in this direction in each subsequent ordnance phase"*. So under IGOUGO a freshly-launched salvo moves **twice** in its launch round: once on the launch move itself, then again in the opponent's ordnance phase. Established ordnance also moves twice per round. Therefore:

| | Launch round | Later rounds |
|---|---|---|
| Vanilla IGOUGO | 2 moves | 2 moves |
| This idea, under AA | **1 move** | 2 moves |
| ABFG's version | 2 moves (1 at launch + 1 in the 2nd part of its ordnance phase) | 2 moves |

So this is **−1 move in the launch round versus vanilla**, and it also differs from ABFG, which deliberately preserves the launch move to hit parity. Worth being explicit that this is a real tempo change, not a neutral restatement: torpedoes threaten one move-distance later than they do in the base game.

**The argument that the nerf is correct anyway (worth testing).** AA already hands the launching player something IGOUGO never does: because ships activate inside a *shared* movement phase, a ship that activates late can launch *after* seeing the enemy commit its move. That's a free information advantage on the launch turn. Charging 1 move for it is a plausible price, and it's the same instinct behind the initiative system (act later = pay for it). If playtesting shows torpedoes feel toothless, the fallback is ABFG's version (restore the launch move for parity, keeping 2/2).

**Scope (decided):** applies to **all ordnance** - torpedoes, attack craft, assault boats alike, not torpedoes only. The rule is phrased as "first turn *on the board*", which is arrival-agnostic, so it also covers ordnance entering play by means other than a launch (reserves, Craftworld Gates, and similar): whatever the arrival route, first turn on the board = 1 move, 2 moves thereafter.
