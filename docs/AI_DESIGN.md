# How the BFG:XR AI thinks: current and planned

> Where CLAUDE.md's old sections went (owner: CLAUDE.md kept small): "Owner rulings" and the
> rules-area notes -> docs/RULINGS.md; "Session status" -> docs/STATUS.md; "AI: how it
> decides" -> docs/AI_DECIDES.md; "To do" -> docs/TODO.md (open items) and docs/TODO_DONE.md (full history). References below to those
> CLAUDE.md sections mean those files.


This describes the computer opponent as it is built today and as planned from the owner's
feedback. Each feature is marked **Built** or **Planned (To do N)**; the numbers refer to the
To do list in `CLAUDE.md`, which has the implementation detail. Code lives mainly in
`src/ai_player.py` (`AIPlayer`), `src/ai_hazards.py`, `src/ai_rerolls.py`, `src/waves.py` and
`src/lookahead_ai.py` (the expert AI).

Owner's standing caveat for all strategy: **"do not take these as hard rules, it depends on
the matchup."** Every behaviour below is meant to come out of comparing values for the
situation at hand, not from fixed doctrine.

---

## 1. The core idea: one currency, expected victory points

Every decision is priced in **expected victory points (VP)**: "on average, how many VP does
this gain us or cost us?" The AI takes the option worth most. One currency lets it compare
unlike things: two bomber hits, a raid that silences a broadside, a blast marker in the way, a
fighter held on CAP, a re-roll spent now or kept.

**What damage is worth** (Built):

- Crossing the **crippled** line scores 25% of a ship's points, **destroying** it 100% (s.38;
  an escort squadron is scored once, as one unit). Damage short of a threshold is worth a
  little (0.2 x the ship's points / its starting hits, per hit), so the AI still likes wearing a ship down.
- **Threat removed** (owner): killing a ship removes its next turn of fire at us, crippling
  halves it. "Fire" includes a carrier's launch bays: what its strikes would do to us, and how
  many of our strike squadrons its fighters would stop.
- **Catastrophic damage**: a kill may explode (plasma drive 9-11, warp drive 12 on 2D6; the
  Mercury rolls 3D6; escorts never). An explosion among enemy ships adds value; one among our
  own ships subtracts it.
- **Two scales**: gunnery targets use the threshold scale above; anything comparing bomber
  hits with hit-and-run raids uses a "full value per hit" scale so the two are comparable.
  Ordnance ignores shields (s.11, s.15), and the values know that.

**Time** (Built; owner: "sooner beats later"): each ordnance phase of delay costs x0.85, and
anything from the next game turn is also halved because where ships will be is a guess by then
(1.0 now, 0.85 in the enemy's phase, 0.36 and 0.31 next turn). "2 hits on the side within 2
turns are worth much more than 3 on the rear after a 4-turn loop."

**Risk** (expert AI built, To do 2): with a turn limit the expert AI scores by its **chance of
winning**: the VP margin against the spread of the fighting still to come (more fighting, a
wider spread), so behind with few turns left it gambles (a brawl beats staying out of range)
and ahead it plays safe. A little expected VP stays in the score so more VP still wins when
the result is settled. The normal AI uses the same idea (Built) when it decides whether to
disengage (staying is a gamble, leaving a sure 10%: ahead it leaves more readily, behind less)
and spends re-rolls freely on the last turn (left-over re-rolls are worth nothing after it).
Built since: the same preference in brace and strike choices, and scenario points (Domination's
objective points, Planet Strike's bombardment) in the margin, the expert search's leaf included.

**Disabled rules** (Built principle, owner): if an optional rule is switched off (boarding,
ramming, teleport, hit-and-run...), the AI never values moves by it nor attempts it. With
hit-and-run off, assault boats, boarding torpedoes and teleports are off for everyone.

---

## 2. Weapons: ours and the enemy's

### Our weapons

- **Batteries (macrobatteries)** (Built): expected hits from the Gunnery table with the real
  column shifts (range, blast markers or dust in the line of fire, target aspect). Planners use
  the same table from where the ships stand (aspect, Armour facing, range-free shifts such as
  holofields; the range left out as the shot comes after a move), or, where the target isn't
  known, the table's own average of 0.176 hits a firepower point against 5+ (the old rule
  of thumb was 0.35, about twice the table). Ork
  random firepower is rolled when the gun fires; Heavy Gunz use their bigger close-range value
  within 15cm.
- **Lances** (Built): 0.5 hits per lance (4+ whatever the Armour); unaffected by column shifts.
- **Shields** (Built, checked): battery and lance hits are taken off the target's current
  shields first (`current_shields`); only hits past them count. Ordnance ignores shields.
- **Squadron volleys** (Built, s.8): a squadron combines its batteries into one volley when that
  rolls at least as many dice as firing separately, choosing the aspect that gives most
  expected hits. Planned (To do 9): Ork random-firepower batteries in volleys; volleys needing
  a target priority test.
- **Nova Cannon** (Built, basic): fires at the nearest enemy between 30 and 150cm. Planned
  (To do 9): aim by expected VP.
- **Torpedoes** (Built): see section 4. Lanes avoid hazards across the marker's full width and
  count friendly fire as negative VP (a salvo attacks every ship it touches, friend or foe, and
  carries on weakened, s.15). One-per-game vortex / melta / seeking salvos are saved for
  capital ships; bought guided torpedoes are guided freely; short burn beyond 30cm; barrage
  bombs wait for planetary assaults.
- **Attack craft** (Built): see sections 4 and 5.
- **Teleport attacks** (Built, basic): in its end phase, if teleports and hit-and-run are on, it
  raids the eligible target worth most per raid. Planned (To do 8 j): positioning for them.
- **Boarding and ramming** (Built, To do 8 h, only with those rules on): it moves for base
  contact and declares a boarding action or a ram when the expected VP is worth it.
- **Weapons knocked out by critical hits** never fire (Built).

### Enemy weapons

- **Guns** (Built): modelled mount by mount for the enemy's next turn. A port broadside only
  threatens our ships on its left, starboard on its right; other mounts only within their arc
  after one turn of that ship's own turn angle (owner: the Protector turns 90 degrees, the Hero
  45). Tau "(L/F), (R/F)" mounts both bear ahead, never both broadsides at one target abeam.
  The enemy is assumed to **focus fire** (owner: optimal play concentrates) on the ships it adds
  most VP against.
- **Ordnance in play** (Built): each marker by type. Mines go for the nearest ship; standard
  torpedoes run straight; guided torpedoes turn at the launcher's Leadership odds; seeking ones
  home on the nearest enemy; boarding torpedoes turn freely within 45 degrees; Tau missiles
  turn 45, reach 40cm and lose strength on later phases. Bombers always attack the lowest
  Armour (s.20). Contact uses the ship's base size plus the marker's width, so large bases are
  easier to hit.
- **Enemy carriers** (Built): what their loaded bays could launch next turn, and their fighters
  as a threat to our strikes (section 5).
- **Enemy turrets** (Built): the turret split (s.28: a ship's turrets fire at attack craft or at
  torpedoes / mines in a phase, not both) is exploited by co-ordinated strikes; Ork turrets fire
  at everything, so not against Orks.
- **Enemy teleporters** (Planned, To do 8 j): stay out of their reach when our shields may be
  down and we don't out-hit them.
- **Armour facing** (Built, To do 8 a): enemy batteries count against the Armour facing they
  would hit at our end heading, so a 6+ prow really is safer than a 5+ side (lances hit on 4+
  whatever the Armour). This is the first building block for the manoeuvre plans.

---

## 3. Moving, turning, positioning, hazards and special orders

### How a move is chosen (Built)

For each ship the normal AI tries 5 headings (straight, half its turn angle either way, its
full turn angle either way) at 3 distances (60%, 80% and 100% of its speed, never below the
minimum move): up to **15 candidate moves**, each scored as:

- **Guns that will bear** from the end position on its focus target, plus 0.3 of what bears on
  its nearest enemy; loaded torpedoes count when the target is in the launcher's arc (full
  within one torpedo move, half within two).
- minus **exposure**: half the hits the enemy could focus on that end position, on the Armour
  facing each enemy gun would hit.
- minus **hazards along the whole path**: mines, torpedoes and attack craft, asteroid fields,
  warp rifts, dust clouds and blast markers, each as expected VP lost.
- minus **flagship danger** for the commander's ship (half the enemy fire that could reach it).
- minus **explosions**: ending within the 3D6cm blast of a ship likely to die; a ship of ours
  that is likely to die gains by ending next to enemies instead.
- minus **carrier exposure** for carriers: ending inside enemy strike reach, doubled when the
  enemy has more launch capacity (owner: protect your carriers when out-carriered).
- plus **screening**: an escort touching the commander's ship to mass turrets (s.29), only while
  enemy torpedoes, torpedo bombers, bombers, assault boats or mines could reach it (owner: never
  against fighters alone, never when there is nothing to mass against).

**Better candidates** (Planned, To do 11 a; owner). The rules every candidate respects: a
capital ship turns right after its turning distance (battleships 15cm, cruisers 10cm; s.10,
before modifiers), just after its minimum move (half speed), or at the end. These are separate
rules: for a 20cm cruiser both are 10cm, for a 25cm cruiser 10cm and 12.5cm. Escorts turn
anywhere, even at the very start (reaching places no capital ship can); Burn Retros needs no
movement before turning; only forward movement this phase counts toward the turning distance;
any angle up to the maximum is legal. The turning distance is one rule shared with the engine (`movement.turn_distance`: none for
Burn Retros, low orbit and Dark Eldar, 20cm for Necrons on All Ahead Full, Quest +5cm, Tyranid
Extra Discharge Vents -5cm); ships with no minimum move also try quarter and half moves.
Distances run from the minimum move (ending as short as
legally possible often keeps a ship out of range; under 5cm a ship counts as Defences on the
Gunnery table, which matters for Burn Retros) to full speed.

**First slice built** (To do 11 a): every capital ship now also considers turning after its
minimum move or at the end of its move, escorts and Burn Retros at the very start, and a 50%
(minimum move) distance; on top of the old grid come two goals against its target: the end
heading that brings the most guns to bear (searched every 5 degrees) and the distance that
lands in the range bracket where it beats the target most (from the matchup table). Every
candidate is checked against the movement rules. **Second slice built**: more goals (closing
prow-on to where the target will be, into its rear arc, guns on a second enemy, an escort to the
commander's ship), the best three refined by small changes to angle, distance and turn point,
ships moving in support order (the commander's ship first, escorts last), and the expert's
root using the same candidates, best first. About 35 candidates and 40ms a ship. Still to
come: raid-reach goals. Built since: Lock-On-next, a denser grid in crowded fights, safety
(tangents past hazards), disengaging from the end position, Come to New Heading's two-turn
moves, and one round of the coordination pass (every ship planned once, then each real move
planned with the ships still to move at their planned ends).

**Target-directed candidates** (Planned in full, owner; replaces the earlier idea of headings every 15
degrees, about 150 candidates, which survives only as a fallback). Candidates propose, values
decide. Instead of sampling headings evenly, the AI picks **goals** and solves for the move
that reaches each one (heading for a point and clamping to the turn limit, or a short search
over turn point and distance); a goal out of reach gives the closest move as "progress
towards" it. About 20 candidates instead of ~150, and they land exactly on the narrow
positions that matter (a 10cm range band, a rear-arc slice, the one heading with two enemies in
one broadside). Cost grows with targets and goals, not with the turn angle.

- **Per target** (the focus target plus the next one or two by expected VP):
  bring the best weapons to bear (broadside ships the broadside, Tau and prow-heavy ships the
  prow); the **range band**: we move and shoot, then the enemy moves up to its speed and shoots,
  so the safe band is our range >= distance > their range + their speed (Chaos 60cm guns vs
  Imperial 30cm on 20cm ships: 50-60cm; 45cm guns on 20cm ships have none against 60cm), and
  without one, the distance where our damage now minus theirs next turn is best; **Armour
  facing** (closing without firing, prow-on where the prow is best; firing, turn to unmask at
  the end); **out of its arcs** (its rear or a blind arc, from its predicted position);
  **torpedo lines** (target in the launcher's arc on a clear lane); teleport, boarding and
  ramming reach (only when those rules are on); and **Lock On next turn** (no turning allowed,
  so end pointed so a straight move keeps the target in arc).
- **Not tied to one target**: two enemies in one broadside or one in each; fleet support
  (massed turrets with the commander's ship or a carrier, squadron coherency); safety (the
  tangent past a hazard, built: `_safety_goals`; out of the most dangerous enemies' arcs); disengaging for crippled
  ships (toward a phenomenon within 15cm for +3 Ld, or the nearest edge); scenario objectives
  (built: Domination's three nearest markers as point goals).
- **Fallback grid**: a small even set (straight plus a few headings at the turn limit, at the
  three turn points, minimum and full distance) for moves no goal predicted; 90-degree ships
  and special turners get more fallback headings and more variations round each goal (owner:
  more thinking time beyond the 45-degree baseline).
- **Efficiency**: goal candidates scored first, cheap terms prune, full exposure on the best
  ~20, near-duplicates dropped; the expert search tries goal candidates first so alpha-beta
  prunes more.
- **When even sampling wins, and the hybrid**: crowded fights, dense hazards or incoming
  ordnance (the best move is a gap no goal predicts), a small reachable area (slow or crippled
  ships, Burn Retros), caching (grid end positions can be precomputed per ship class), and
  goals that are incomplete or wrong. Target-directed wins with few targets, a large reachable
  area (fast ships, 90-degree turns, escorts) and narrow useful positions, which is most of a
  game. Per ship per turn: always goals for the top 1-3 targets plus the small grid; a denser
  grid (goals still in) when goals would outnumber it, hazards are dense or the area is small;
  then hill-climb the best few with small changes to turn point, angle and distance; anytime
  order goals -> grid -> refinement within the time budget (also the expert's move ordering);
  and log which source produced each chosen move: if the grid often wins, a goal is missing or
  wrong, so fix the goal rather than add samples. The crossover points are to be measured in
  the engine, not guessed.
- Needs exposure by Armour facing (8 a) and range brackets (8 f) first: goals b and c come from
  them. Then a **coordination pass** (suggestion; one round built): moves are greedy ship by
  ship, so re-optimise each against everyone's planned end positions (one or two passes),
  catching screening and mutual support.

**Fleet focus** (Built, owner: focus fire, easier targets first): the fleet assigns focus
targets together. Each ship's guns go where they add most VP on top of what the others will
do, so one ship finishes a 1-hit enemy while the rest move on, and two healthy targets each get
the ships needed to kill them rather than all piling on one.

### Strategies (Built, first slice; owner: "a list of strategies all ships try out")

Each ship lists the strategies its weapons, speed and state allow:

- flank left or right into the target's rear arc;
- hold the range band where its guns beat the target's;
- kite (with a range and speed edge);
- close in (with boarding or ramming on, or when it fights best under 15cm);
- screen the flagship or a carrier (escorts);
- run for the nearest edge (crippled).

Each strategy's first move is searched alongside the usual candidates, and the simulated
ship keeps following the plan the next turn while the enemy replies. So a move that looks
poor on its own, such as swinging wide now to be behind the enemy next turn, is valued by
what it leads to. Every line is judged over the same two turns (normal now looks two turns
ahead along one line). The search stops after a fixed number of simulated turns rather
than a time limit, so seeded games replay exactly.

### Matchup-aware manoeuvre (To do 8; owner ideas, not hard rules; a and f built, the rest planned)

- **a.** Exposure by Armour facing (prerequisite; **Built**): the enemy's batteries are scored
  against the Armour they would actually hit at our end heading, so ending prow-on to an enemy
  broadside with a 6+ prow is half as exposed as showing it a 5+ side (lances hit on 4+ anyway).
- **b.** Gun-heavy broadside fleets (e.g. Lunars, broadsides that don't overlap): keep both
  broadsides busy, cross the T.
- **c.** Out-range and out-move the enemy on average (e.g. Chaos): kite in the band where we can
  fire and it can't; watch the table edge.
- **d.** Forward-firing ships with the best Armour in front (Tau Protector): show the prow only
  when the enemy is about to be in range.
- **f.** Firepower by range bracket, fleet vs fleet and ship vs ship: 0-15cm (Ork Heavy Gunz),
  15-30, 30-45, 45-60 (Chaos long guns), 60-150 (artillery such as the Nova Cannon). Fight in
  the bracket where our guns win (a Tau Merchant out-guns a Lunar at 30-45cm, not at 0-30cm).
  **The table is built**: for each pair of ships and for the fleets, the VP each side does per
  shooting phase in each bracket, from the real Gunnery table (range shifts, Heavy Gunz), lances
  and the Nova Cannon's own scatter rules, past shields (a ship whose average is below the
  target's shields still gets some hits through on good rolls). It confirms the owner's
  examples: the Merchant beats a Lunar only at 30-45cm, a Murder at 30-60cm. Movement doesn't
  use it yet: that comes with the range-band goal (To do 11 a) and kiting (8 c).
- **g.** Speed and turn edge: get out of the enemy's main arcs (e.g. into a Lunar's rear).
- **h.** Hit-point edge (Orks): boarding and ramming.
- **j.** Teleport attacks both ways.

### Hazards (Built)

Asteroid fields, warp rifts, dust clouds, planets, blast markers, mines, torpedoes and attack
craft are all priced along the move path, mirroring the engine (e.g. attack craft die on a 6 in
asteroid fields, dust clouds and blast markers; torpedoes detonate on planets, asteroid fields
and warp rifts). Line of sight blockers (asteroid fields, planets, warp rifts, hulks) are
respected when shooting.

### Disengaging (Built)

It disengages voluntarily when the chance of passing x (the risk avoided over the enemy's next
turn - the VP conceded) beats the value of its guns. Forced disengagement and Demiurg
Mercenaries make it flee for the nearest edge.
Planned (To do 11 c): every modifier of the test (s.37, XR p.38): +1 Ld per blast marker within
5cm, +3 once for a celestial phenomenon within 15cm (anywhere during a radiation burst or solar
flare), -1 per enemy within 15cm, enemy ordnance markers included; Ld max 10. A failed test
means no firing, launching or orders but Brace for the rest of the turn. Built: the test comes
at the end of the move, so a ship likely to try it values each end position by what trying from
there would gain (its Ld modifiers and the fire it faces there), e.g. ending next to a dust
cloud for +3, weighed against its guns. A
non-crippled ship that disengages gives 10% ("Enemies Scattered", s.38).

### Special orders

**Built** (rebuilt after the owner's audit question, "were you lazy with the other orders
too?"; several shortcuts were found and fixed):

- **One pass chance** for every order and for Brace, taken from the engine's own rule
  (`movement.command_check_ld`, the same function the real command check uses): Leadership,
  Under Fire (not Necrons), Enemy Contacts (incl. the Cobra's sensors, nebuloscope pylons,
  veiled Shrouds), Fleet Experience / Blood Bond, Slaanesh, sub-plots, Grot Riggers, Siren's
  Summon, Tyranid synapse Ld for Brace, and automatic passes (Dark Eldar Come to New Heading,
  Orks' All Ahead Full). It is 0 when no order can be tried (a failed check this turn, a
  scenario forbidding orders, a Tyranid on instinct). Before, five hand-written copies each
  missed some of these.
- **Each order's value** is the best move it allows against the best free move, in expected
  VP, with only the firepower cost the rules give it (s.7): All Ahead Full, Come to New
  Heading and Burn Retros halve batteries and lances, never torpedoes or launch bays (AAF
  used to halve everything, Come to New Heading the whole arc score); Lock On costs nothing
  and is worth what re-rolling the misses adds, 1 - p a die by the weapon's real to-hit
  (+50% at 4+, +67% at 5+, +83% at 6+; it was a flat half); Reload Ordnance is worth next
  turn's launch (a strike or CAP for spent bays, the reloaded salvo's real hits after turrets
  and re-rolls for torpedoes); Burn Retros the hazard it avoids. Come to New Heading's moves
  are two-leg (a first leg and turn, then a normal move), so a forward-firing ship with an
  enemy close behind turns twice, and a Dark Eldar ship (no turning distance, an automatic
  pass) can get behind an enemy.
- **The choice**: every order's value times its pass chance on one scale, the best taken (Burn
  Retros used to win whenever it beat its own cost); with nothing better a spent ship still
  reloads. An order is skipped when its failure would block more valuable later orders (a
  failed check ends the turn's orders, s.2); a commander re-roll on a failed check is worth
  the orders the failure would block.
- A teleport-capable ship on any order but Lock On / Reload Ordnance gives up its end-phase
  raid (s.31); that counts against the order.
- Brace is priced: the VP its 4+ saves are expected to keep (this attack and enemies still to
  fire) against half the ship's fire until the end of its next turn, at the same pass chance;
  with a turn limit both by certainty equivalent. The commander's ship braces earlier only
  because it is worth more.

Planned (owner; built once and reverted, see CLAUDE.md To do 33): a commander re-roll counted in every order's and Brace's pass chance: a
failed check is re-rolled when the AI would spend one on it, passing at the same chance
again, less what the AI holds a kept re-roll to be worth. Brace also pays for the order it
forbids next turn (the AI's own choice from where the ship stands, at its pass chance).
**Not yet**: re-ordering the checks (it would break the support move order).

**Brace for Impact** (rules, s.7): a failed movement-phase check doesn't stop a ship bracing
later; a failed brace blocks only that ship until that attacker has finished all its
  attacks; a ship decides separately against each of an attacker's weapons (it may brace
  against the lances after not bracing against the gunnery) but tries only once per attacker
  per turn: a ship that fails against a ship's macrobatteries can't brace when that ship then
  fires its lances (the engine enforces this). When the AI fires, the target is asked before
  each weapon; the player's Fire dialog fires batteries, then lances, then the nova cannon and
  asks before each kind (Built). Its price (above) replaced the fixed quarter-of-hits rule and
the commander bias. Not yet: trying against the weapon where the saving is worth most (a
failed try against the batteries leaves the lances unbraceable).

---

### What a hit is worth (Built, owner: "s.38 scores nothing until a threshold")

A hull hit that doesn't cripple or destroy a ship scores nothing by itself. It is worth what
it adds to the chance the ship is crippled or destroyed by the end of the game. That chance
comes from the enemy's fire on it: next turn the guns that can reach it, later turns its
share of the enemy fleet's guns, torpedoes and bays, to the turn limit (or six turns),
undiscounted, since VP are scored at the end. Hits that cross a threshold now also count
the ship's value, its fire removed and its explosion. Every value in hits uses this: gunnery
targets, bombers and raids, crits' extra damage, fires, explosions, Brace and the enemy's
fire plan. So damage nothing can follow up is worth little, and a doomed ship gains little
from protection. Before, every hit counted a flat share of the ship's value.

This is a value, not a lookahead (owner question): no ship is moved and no turn played to
work it out, so it is the same at every difficulty. The difficulty sets how many turns of
moves the search plays out (section 10); the search's own leaf scores where those turns end
with its simpler count (VP banked + one more turn's swing), not with this. Whether the
weaker levels should use a shorter span is an open question for the owner. Is it better in
play than the flat value? By the rules' reasoning yes (focus where a threshold can be
reached, finish what can be finished, waste nothing on the last turn), but unproven: it
would take about 100 paired games to tell, and the owner has pinned that as not worth it.

### Critical hits and re-rolls, measured (Built)

Owner: no guessed shares where the rules give an answer.

- **A crit's effect** is measured, not guessed. The crit is applied to a copy of the ship by
  the engine's own rules, and the copy's exchange with our fleet is compared with the
  original's at each of its next few shooting phases. The exchange counts its fire on our
  ships and ours on it, with the target attacking or evading, whichever suits it; its speed,
  turns, shields and guns are read as the engine reads them. Each phase is weighted by the
  chance the crit is still unrepaired. That chance is exact: the repair dice over each end
  phase, and a system with several crits works again only when all of them are repaired.
- So Thrusters Damaged costs the reach the ship needed, Engine Room the turn it needed (to
  close, or to bring a broadside round), and Shields Collapse the fire that would then get
  through. Bridge Smashed costs the Brace its lower Leadership loses, plus the commander's
  VPs. Extra damage is valued as hull hits.
- **Planned (built, then reverted; To do 33):** lower Leadership also costs the special order the ship would take next turn: the
  order's worth times the drop in its pass chance.
- **Planned (built, then reverted):** boarding crits valued as the engine rolls them on the ship's own table (a D6 on
  the raid table; an escort's 1 damage), with the Haemonculi's Fire and Pain Frenzy's
  re-roll when a Dark Eldar ship inflicts them. They used to count a flat hit.
- **Planned (built, then reverted):** raids on Dark Eldar ships worth something for every result: keel armament by
  the launch bays it silences, Superstructure Damaged by the cheaper of turning with a 1 in
  3 chance of a hit or holding straight. Silenced torpedoes count their salvo's real hits.
- **Re-rolls** are worth what passing gains over failing, test by test:
  - Brace: its own price, given that it passes.
  - A warp rift: the ship.
  - An asteroid field: the D6 damage past its shields.
  - Disengaging: its disengage value.
  - Target priority: the guns at the target it wants, less at the closest.
  - An order: that order's value.
  - A guided salvo: its plan turning now, less held straight.
- The guns' value comes from exact hit distributions: the Gunnery table's dice for
  batteries, and each faction's lance rules and saves, die by die.

## 4. Target priority

### Direct fire (Built)

The target where the weapon's expected hits add the most VP given what earlier shots this phase
already did (no overkill; easier and damaged ships first), obeying target priority (it takes
the Leadership test when it wants a farther ship). It shoots an enemy **hulk** when the hulk's
re-rolled explosion would hurt enemies more than its best ship shot, and incoming **ordnance**
when that is worth more than its best ship shot. Carrier-heavy fleets put guns on enemy
carriers (air supremacy; ordnance at a carrier tends to be intercepted).

### Torpedoes (Built)

The target the salvo adds most VP to after turrets, path hazards and friendly fire.

- **Straight salvos lead the target** (owner): the target's next move is sampled (half to full
  speed, one turn after its turning distance, dodges by Burn Retros or All Ahead Full). The
  salvo moves now, waits while the enemy moves (a ship moving into it is attacked) and moves
  again. Closing targets are easiest, abeam hardest, receding between (0.64 / 0.32 / 0.34 at
  40cm for a speed-20 Ld 8 cruiser); a salvo parked inside a ship's minimum move can only be
  escaped by Burn Retros; big bases are easier to hit; a catch on the second turn counts at
  half.
- **Turning salvos** (Tau missiles, Leadership-guided, boarding) plan a path, four moves deep,
  onto the weakest Armour facing they can reach (e.g. round to an Ork cruiser's 4+ rear), and
  follow it in flight.
- **The load** (when no once-a-game, guided or short burn load is chosen) by expected VP:
  standard (Dark Eldar plasma re-rolling misses) by hull hits, boarding torpedoes a raid a
  hit (off with hit-and-run), leech a Thrusters Damaged a hit (its measured effect, below, over
  the salvo's exact hit distribution); plasma wins against ordinary targets.
- **Co-ordinated with bombers** (owner): salvos and bomber waves reaching one ship in the same
  phase gain the turret split (not against Orks).

### Bombers and assault boats (Built)

Every enemy within three craft moves is considered; each strike is valued **when it lands**:
its arrival phase (time discount), which turn it lands in (a raid's crits face one end phase of
repairs before the target shoots if it lands in our turn, two in the enemy's), enemy guns that
can shoot the waiting wave (one 6 removes the whole wave), and every interceptor on the way:
the target's own CAP, other enemy carriers' fighters, and enemy fighters already flying (owner:
a smaller air wing can still cut a wave of 8 down to 2, so **strike outside the enemy's
umbrella**). It chooses the fighter / bomber split against all that, or all assault boats when
raids are worth more (owner idea: boats ignore Armour), and multi-role craft pick bomber or
raid mode the same way. Faster craft that land a phase sooner can win on that alone.
A raid's crit is valued over up to three of the target's shooting phases (fewer near the turn
limit), each with more repairs and a bigger discount (Built). Craft already flying are
re-targeted every ordnance phase with the same interceptors counted, so a wave in flight also
turns away from an enemy carrier's umbrella (Built).

**Two waves or one** (Built): one hit removes a whole wave, but each enemy gun fires at one
marker, so a strike that must wait under enemy guns may launch as two waves to spread the
shots. Each wave then faces the turrets alone, suppresses alone and gets half the CAP, so the
AI splits only when the guns matter more than the turrets (e.g. under two gunships vs a
1-turret target, not vs 4 turrets).

Built since: the risk preference in strike choices, the expert AI valuing its own craft in
flight (its search moves our torpedoes and bombers and the enemy's moves dodge them). Planned:
splitting assault boats or waves already in flight. Built (To do 3): torpedo bombers as a strike option (the squadrons that get past interceptors fire 2 each), fired at the ship in salvo reach worth most, and counted in the hazard model as a salvo; mines laid when they are worth anything: each mine is followed 10cm an ordnance phase at the nearest enemy over its sampled moves for four ordnance phases, attacking with 8D6 (4D6 if a turret hits) on contact (`mine_value`), so a receding enemy that a mine can't catch gets none.

---

## 5. Fighters (Built)

Each ordnance phase the AI plans fighters across all its carriers:

- A fighter can stop one incoming threat: a torpedo salvo or a mine needs one fighter, a wave
  one per squadron (front first). On **CAP** over the threatened ship it always intercepts
  (full value); flying **free** at the threat it counts 0.75. Fighters already on CAP cover their
  ship first.
- **Enemy strikes not yet launched** count too, CAP only, weighted by the air balance (0.25 when
  we have more launch capacity, up to 0.9 when out-carriered): an out-carriered fleet plays
  defensively and flies interception (owner).
- Carriers with the weakest strikes take the defence; each takes the exact number of fighters
  that maximises strike value plus defence value (strikes are worth more than the sum of their
  squadrons: fighters suppress turrets and big waves cripple).
- Bays are **held** when nothing is within three craft moves, or when poor reload odds make next
  turn's launch or CAP worth clearly more.
- In a wave, fighters lead and suppress turrets (XR: a surviving fighter gives one bomber
  exactly 3 attacks; Remastered mode, p.82: each fighter adds +1 to the wave's attacks, capped
  at the surviving bombers). The planner follows whichever mode is set.

---

## 6. How many moves it evaluates

- **Normal AI movement**: about 30-65 candidates per ship (the grid of 5 headings x 4
  distances, extra turn points, and goal candidates for guns to bear and the winning range
  bracket), scored greedily, ship by ship in fleet order. The Burn Retros check compares the safest of up to 9
  normal moves with the safest of up to 9 half-speed moves.
- **Torpedo aiming**: every heading through the target's sampled positions within the launch
  arc (dumb-fire); for turning salvos, up to several thousand short paths (launch heading, then
  -45 / 0 / +45 per move, 20/30/40cm for Tau missiles), pruned to well under a second.
- **Strikes**: every enemy within three craft moves x every fighter / bomber split x every
  interception case.
- **Planned** (To do 11 a, the rest): torpedo-line, raid-reach and Lock-On goals, a denser
  grid in crowded or hazard-dense fights or small reachable areas, exposure only on the best
  ~20, then the full fleet coordination pass (built: Armour-facing and rear-arc goals,
  hill-climbing, the support move order).
- **Searched movement (normal and up)**: for each ship, up to 12 of the normal AI's
  candidates at the root (best first) plus every strategy's first move (section 3,
  Strategies), each followed by a minimax search (normal 2 turns, hard 3, expert 5, master
  10) that tries a few variations of each side's moves per step and keeps the best few lines
  (alpha-beta pruning), cut by a fixed number of simulated turns per decision (normal 450 up
  to master 2800), so the same seed always gives the same game.

---

## 7. Thinking over several turns

- **Normal AI** (Built): its movement search plays out 2 turns (since the strategy
  planner: every line is followed for the strategies' two turns, the second along one line);
  its other choices look about one turn ahead, through: the enemy's next turn of fire
  (exposure, disengaging), the threat a kill removes, explosions before our next move, next
  turn's launch when holding bays, and ordnance planners looking two game turns (four ordnance
  phases) ahead with the time discount. Disengaging uses a one-turn horizon.
- **Hard, expert, master** (Built): simulate 3, 5 and 10 turns of both sides moving and
  shooting, and stop at the game's turn limit.
- **Values that reach further than the search**: a hull hit's worth assumes the enemy keeps
  firing to the turn limit or 6 turns (section 3, "What a hit is worth"); a formula, not
  simulated turns.
- **Built since**: the turn-limit risk preference (the expert's chance-of-winning score, and the
  normal AI's disengaging and re-rolls); crit values over up to 3 of the target's shooting
  phases and the turn limit; the risk preference in brace, strike choices and the guns a
  disengaging ship gives up, and scenario points in the margin (Domination, Planet Strike).

---

## 8. Every weight (judgement; tuning is on hold)

Tuning these is on hold (owner: "keep it in mind, but it is hard work, so leave it for now").

**Owner ruling (learned evaluation and weight tuning):** don't start either until the owner
says so. When they start, the experimental ML-driven AI is kept separate: it never replaces
the current AI, whose normal and expert players and weights stay as they are.

| Area | Weight | Value | Meaning |
|---|---|---|---|
| Values | damage short of a threshold | 0.2 | x points / starting hits, per hit (180pt 8-hit cruiser: 4.5 VP) |
| Values | crippled / destroyed | 25% / 100% | of points (s.38) |
| Time | phase discount | 0.85 | per ordnance phase of delay |
| Time | later-turn weight | 0.5 | anything from the next game turn |
| Guns | battery average (rule-derived, To do 30) | 0.176 | the Gunnery table's hits per firepower point vs 5+ |
| Guns | lance | 0.5 | hits per lance |
| Raids | torpedo in a silenced location | 0.3 | hits per point |
| Raids | weapon brought to bear after a turn | 0.75 | when valuing an armament crit |
| Raids | crit horizon | 3 | target shooting phases a silenced weapon is valued over (turn limit cuts it) |
| Movement | nearest-enemy arc score | 0.3 | beside the focus target |
| Movement | exposure | 0.5 | of the hits the enemy could focus |
| Movement | flagship exposure | 0.5 | of the fire that can reach it |
| Movement | screening | 0.5 | of a turret shot per threat, up to 3 |
| Movement | carrier exposure when out-carriered | x2 | |
| Orders | Burn Retros | 0.5 | hazard saved must beat half the firepower value |
| Orders | brace | 1/4 | of remaining hits in expected damage (to be replaced by pricing its cost, To do 11 c) |
| Re-rolls | bars | 45 / 25 / 15 / 10 VP | to spend the last / 2nd / 3rd / further re-roll |
| Disengage | concession | 10% | of the ship's value |
| Disengage | already crippled | +75% | extra loss if destroyed |
| Enemy moves | dodge | 0.5 | a target dodges a salvo it can escape |
| Enemy moves | course prior | 40% / 15% | holding course / each of four turns |
| Enemy moves | All Ahead Full sample | +14cm | 4D6 average |
| Ordnance | Tau missiles on later phases | 5/6 | strength |
| Ordnance | boarding torpedoes | 1/2 | relative to hull hits |
| Ordnance | hulk's next re-roll when burning | 0.5 | of its value |
| Air | anticipated enemy strike | 0.5 | scaled 0.25-0.9 by the air balance |
| Air | carrier bays per turn | 0.5 | share acting in a turn |
| Air | enemy fires at our wave | 0.5 | per gun in reach |
| Air | reactive CAP / intercept | 0.5 | enemy uses loaded fighters against us |
| Air | enemy fighters already flying | 0.75 | they go for our wave |
| Air | our free fighter | 0.75 | vs 1.0 on CAP |
| Reach | strike / torpedo targeting / lead plan | 3 / 3 / 2 moves | |
| Expert | explosion radius | 10.5cm | 3D6 average |
| Expert | risk tie-break | 0.1 | expected VP kept in the chance-of-winning score |
| Expert | depth / beam / variations / time | 5 / 4 / 6 / 2s per ship | |

---

## 9. Win conditions

- **Victory points** (Built): destroyed, crippled and disengaged ships (s.38) are what the AI's
  values are built from; Holding the Field isn't counted yet (but in Planet Strike, where it
  wins the game, the defender's ships count keeping the field).
- **Turn limit** (Built: the expert search's horizon and risk preference, and the normal AI's
  disengaging, re-rolls, brace and strikes, To do 2).
- **Scenarios** (Built for 25 booklet scenarios, To do 7; owner: "Domination was just one
  example; there are many other scenarios"): each plays its own objectives in expected VP next
  to ship VP. Domination: markers held at the end of our turn, contesting enemy-held ones, a
  pull towards markers within two moves, point goals for the move candidates, the points race
  in the margin. Escalating Engagement (first form): its divisions always roll to arrive and
  edge markers go (and slide) nearest its ships; no move term yet. Navigate the Storm: convoy
  ships (their capacity value + points) and warships while the 25% points goal is short run
  for the exit point (progress, move goals); the attacker's kill bonus is the capacity; a warp
  rift costs a lost defending ship's value + capacity (`lost_ship_vp`), an attacking ship only
  0.1 of its value (it comes back). Destroy the Docks: the stations, dock and inner platforms
  carry a kill bonus (half the points on the table shared out). The narrative Convoy: convoy
  ships run for the far short edge (capacity value + points), the attacker's kill bonus is the
  same; the attacker reveals the contact marker nearest the convoy each turn. Exterminatus! /
  Planetary Assault: ships with a planet objective (Exterminators, assaulting ships) close on
  the gravity well and enter low orbit, then end within 45 / 30cm of the planet edge but
  never where the falls before their next move, or the round after even climbing, would take
  them off it; they always assault; defenders value Exterminators and assault ships as kills
  and pay a stake for leaving. Line Breaker: platforms carry a kill bonus, then capital ships run for the
  defender's edge. Chance Encounter: the defender values crippling the attacking flagship
  (half the points on the table), the attacker runs for the far edge. Convoy / Blockade Run:
  convoy ships and blockade runners head for their exit edge and don't take disengage tests.
  Rescue: the flagship's double value, and its run for its own edge when leaving pays. Space
  Assault: the station's 250 VP swing. Planet Strike: Burn Retros to hold over the planet,
  closing on it, the defender keeping the field. Warp Storm: the chance a disengaged ship is
  lost in the warp. Every scenario: a move off the table is priced as the disengage it is
  (only the scenario's own exit edge counts as its exit), and ending pointed at an edge that
  every next move would cross is penalised. Not yet: racing Domination's 10 against the turn
  order; the AI choosing when reinforcements enter (it brings them at once); the scenarios
  still to build (CLAUDE.md To do 7). Macharia's End: the Imperials value crippling the
  Planet Killer at half the points on the table; the Planet Killer heads for a firing spot
  aimed at Macharia and starts charging when three minimum straight moves leave the planet
  dead ahead within 60cm. The Defence of Pelucidar: plain VP play (not yet: disengaging to
  end the game once 2000 VP ahead).
- **Sub-plots** (first slice built, To do 7): generation, most effects, objectives and the
  battle result (Heroic Victory to Miserable Defeat). The AI values a Vendetta target and its own
  Desperate Mission / Experimental Ship / Fleet Experience flagship more (a tenth of the points
  on the table, judgement); other objectives (No Quarter, Enemy Plans boarding, Secret
  Intelligence raids, Hit and Run's deadline) aren't steered for yet.

---

## 10. Very easy, easy, normal, hard, expert and master

Easy plays exactly as normal, without the movement search (owner). The table compares very
easy with the rest.

| | Very easy | Easy / Normal | Hard / Expert / Master |
|---|---|---|---|
| Targets | the closest valid target (owner) | marginal expected VP, focus, no overkill | as normal |
| Re-rolls, Brace | expected VP, as normal | expected VP | as normal |
| Special orders | Lock On whenever an enemy is in arc and range now (no expected-VP check) | every order by pass-weighted expected VP, one pass chance from the engine's rule | as normal |
| Ordnance | simple launches (its strike craft, at the nearest target) | full planner: CAP vs strikes, strikes on arrival, lanes, leading, co-ordination | as normal |
| Squadron volleys, hulks, shooting ordnance, disengaging, explosions, screening | off | on | as normal |
| Movement | the same candidates, scored on guns and hazards only (no exposure, focus, explosions or screening), picked by softmax (`EASY_TEMPERATURE` 2.0), not always the best | the move candidates scored greedily; normal adds a 2-turn search with the strategies | hard 3 turns, expert 5, master 10 or to the game's end (owner) |

Built for movement (To do 11 i): Very easy picks its move by a softmax on its move score, so its
mistakes look human rather than random; not yet for its targets and orders, which are random /
fixed rules; Hard gets the coordination pass or tuned weights.
The expert AI now pays the normal AI's path-hazard cost for each move it chooses between
(Built, To do 11 b): mines, torpedoes and attack craft in flight, asteroid fields, warp rifts,
clouds and blast markers, so it no longer drives into an asteroid field it can avoid. Deeper in
its search it still sees no terrain or ordnance; planned: hazards there too, and expected
values at chance points or a few sampled dice. The wider candidate sampling
(To do 11 a) matters for the expert too: on a continuous table it can only choose among the
moves it samples. Later (To do 12, owner:
low priority) a learned evaluation for its search: position features (material, threat both
ways, relative geometry, ordnance in flight, tempo, terrain by what it does to ships) fitted to
self-play outcomes, to beat today's "VP banked + next turn's swing" leaf. Owner: it must know
about terrain (asteroids, clouds, planets and gravity wells, warp rifts, minefields, hulks,
blast markers, table edges and the sunward edge, solar flares / radiation bursts), encoded by
what it does to ships, never by where it lies, and trained on varied random set-ups (s.39).
It replaces only the expert's leaf; the normal AI keeps its heuristics.

The searching levels replace only movement; its simulation is
dice-free and leaves out attack craft, hazards and blast markers (only its first move pays for
hazards), so its strength is long-range manoeuvre. Its other phases are the normal AI's.

---

## CAP against torpedoes (owner note)

A ship's CAP fighter removes a whole torpedo salvo when it intercepts it, but only one
squadron of an attack craft wave. So the AI launches its attack craft before its torpedoes,
values a salvo by the chance the target's CAP is already used up when it arrives (by our craft
or earlier salvos reaching it in the same phase), and credits a wave with the torpedoes it
lets through. Which ordnance meets the CAP first is the moving player's choice: craft first
in front of a big salvo, or a small salvo first to draw the CAP away from a wave of Impalers;
the AI picks by expected VP.

## 11. Things the questions didn't cover

- **Deployment** (partly built, To do 28): the AI places its own ships. Ships that help
  friends in range (Tyranid synapse, Tau tracking systems, Fleet Defence Turrets) go last,
  where their help is worth most; with two or more of them the fleet deploys in small
  groups, one round each. Squadrons go in a random line or box, always coherent. Before
  deploying, the AI forms capital ship squadrons from ships of one size, faction, speed and
  role (a random draw at present, not yet by expected VP), keeping the squadron rules. In
  play, helpers move to keep friends in reach when that is worth more than what the spot
  costs, and move after the friends they help. Where to stand inside a zone still isn't
  chosen for the matchup or the objectives.
- **Damage control** (built; To do 11 e): each ship rolls a D6 per remaining hit, each 6
  repairs one system, dice halved in contact with blast markers (s.36, XR p.35). Repairs go by
  expected VP (`repair_value`): a fire by its exact burn (`fire_burn_dist` / `fire_value`: the
  fires still burning each cost a hit an end phase and a damage-control die, so a fire on a
  damaged or burning ship is worth more; the same value prices a Fire crit we inflict), a
  weapon by what it threatens at the next shooting phases, the rest by judgement shares. The
  fixed order breaks ties.
- **First turn** (gap; To do 11 e): the roll-off winner chooses to move first or second (s.2);
  the AI should choose, alongside deployment.
- **Shooting order** (suggestion, To do 11 d): against shielded targets fire batteries before
  lances, since shield-hit blast markers shift later batteries but not lances; knocking shields
  down also opens teleports.
- **Explosions and ordnance** (gap, To do 11 c): a plasma drive overload also destroys all
  ordnance within its radius, so it shields its neighbours from incoming waves and salvos; the
  explosion values count only the ship damage.
- **Mines** (fixed): the hazard model counts the turret roll that cuts a mine from 8D6 to 4D6.
- **Eldar and Necrons** (suggestion, To do 11 g): Eldar (MMS v2.0: two moves, holofields,
  Fragile, turning, own ordnance) and Necrons aren't modelled; the generic AI would misplay them.
- **Blast marker removal** (gap): the player whose turn it is chooses which D6 blast markers to
  remove; the AI doesn't choose strategically (clear its own lines of fire, keep enemies'
  shields down).
- **Re-rolls** (Built): spent by importance in expected VP against the bars above; the
  commander's ship is protected (it braces earlier, its moves pay for exposure). Planned (To do
  11 f, suggestion): bars as a fraction of fleet points or points in play, so they scale. Commander
  re-rolls are lost on Bridge Smashed or the commander's death.
- **Leadership** is rolled at game start; the AI reads its real Ld for every test.
- **Faction rules** it plays: Ork random firepower and Ere We Go, Heavy Gunz, Ork turrets; Tau
  forward arcs and missiles; Space Marine raid bonuses, honour guards and Chapter tactics
  (Wings of Fury re-rolls by expected VP); Chaos Marks; Demiurg absorber fields and fixed Ld;
  Mechanicus gifts.
- **Information**: the AI sees the whole table, as players do; secret sub-plots (To do 7) will
  need it to respect hidden information.
- **Dice**: the AI decides on expected values and never sees future rolls.
- **Help for human players** (Built): "Auto (best)" buttons on choice prompts pick what the AI
  would; the wave planner's "Best split" shows the AI's split.
- **Transparency**: the AI writes its reasons to the log ("[AI] ... strike vs X: 2 fighters + 2
  bombers (about 21 VP)", "keeps its bays loaded (...)").
- **Not built engine rules** the AI therefore can't use yet: several units (To do 5). The
  s.40 effects are built; the AI counts Fighting Sunward's shifts but doesn't plan around
  flares or bursts yet.
- **Order of work** (owner): "the order isn't hugely important"; follow the dependencies
  (exposure by Armour facing and range brackets, To do 8 a / 8 f, before the target-directed
  candidates).

**Approach** (owner feedback): compute, don't script. Build exposure by Armour facing (8 a) and
range brackets (8 f) first and see what behaviour emerges before adding doctrine code (kiting
should come out when our best bracket is beyond the enemy's reach, prow-on when the prow is the
best-armoured facing); where
weights must vary by matchup, make them functions of measured features (launch-capacity ratio,
mean speed difference, range-bracket advantage, hits per point), never per-faction weight sets,
so one tuning run covers lists it never saw.
Order of value (Claude's view, not a ruling): rules completeness > candidate generation >
search with dice > learned evaluation > weight tuning. Weight tuning (owner: last, on hold):
CMA-ES over the judgement weights only, paired games with common random numbers, an opponent
pool (avoids tuning to one opponent's habits or to engine bugs), the normal AI (the expert takes
~75s a game), VP margin as fitness; the 0.35 battery rule of thumb has given way to the exact Gunnery
table (done); redo after any structural change. The same harness is a rules test: an optimiser
finds degenerate strategies in the rules as well as in the AI.

Possible gaps in this plan worth the owner's view: deployment strategy, damage-control choices,
blast-marker removal, whether Hard should differ from Normal, and how much the expert AI should
think (its node budget per decision, ~1-8s a ship, and its simplified simulation).

---

## Update after booklet zip 13 (summary; CLAUDE.md has the detail)

Built since the sections above were written: priced Brace with the game-state risk preference;
strikes and the guns a disengaging ship gives up valued by certainty equivalent; the expert
simulating its own ordnance in flight and using the normal AI's move candidates; more movement
goals, hill-climbing, the support move order, Easy's softmax moves; Lock On and All Ahead Full
by value with the check-order risk; both broadsides busy, kiting, teleport offence / defence,
boarding and ramming (only with those rules on); torpedo bombers, mines, the Nova Cannon,
Armageddon Gun and Kustom Kannon by value; repairs and blast marker removal by value; the
first-turn choice; scale-free re-roll bars; lances valued by their hit roll.
