# How the BFG:XR AI thinks: current and planned

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
Planned: the same preference in brace and strike choices; scenario points in the margin.

**Disabled rules** (Built principle, owner): if an optional rule is switched off (boarding,
ramming, teleport, hit-and-run...), the AI never values moves by it nor attempts it. With
hit-and-run off, assault boats, boarding torpedoes and teleports are off for everyone.

---

## 2. Weapons: ours and the enemy's

### Our weapons

- **Batteries (macrobatteries)** (Built): expected hits from the Gunnery table with the real
  column shifts (range, blast markers or dust in the line of fire, target aspect). Planners use
  a quick 0.35 hits per firepower point against Armour 5+, scaled to the actual Armour. Ork
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
- **Boarding and ramming** (Planned, To do 8 h): the AI plans neither today.
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
- **Planned (To do 8 a)**: exposure should count which Armour facing the enemy sees (a 6+ prow
  really is safer than a 5+ side). This is the first building block for the manoeuvre plans.

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
any angle up to the maximum is legal. Distances run from the minimum move (ending as short as
legally possible often keeps a ship out of range; under 5cm a ship counts as Defences on the
Gunnery table, which matters for Burn Retros) to full speed.

**First slice built** (To do 11 a): every capital ship now also considers turning after its
minimum move or at the end of its move, escorts and Burn Retros at the very start, and a 50%
(minimum move) distance; on top of the old grid come two goals against its target: the end
heading that brings the most guns to bear (searched every 5 degrees) and the distance that
lands in the range bracket where it beats the target most (from the matchup table). Every
candidate is checked against the movement rules. About 30-65 candidates a ship, a few
milliseconds. The other goals, refinement and the coordination pass are still to come.

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
  tangent past a hazard, out of the most dangerous enemies' arcs); disengaging for crippled
  ships (toward a phenomenon within 15cm for +3 Ld, or the nearest edge); scenario objectives
  once scenarios exist.
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
  them. Then a **coordination pass** (suggestion): moves are greedy ship by ship, so re-optimise
  each against everyone's planned end positions (one or two passes), catching screening and
  mutual support.

**Fleet focus** (Built, owner: focus fire, easier targets first): the fleet assigns focus
targets together. Each ship's guns go where they add most VP on top of what the others will
do, so one ship finishes a 1-hit enemy while the rest move on, and two healthy targets each get
the ships needed to kill them rather than all piling on one.

### Matchup-aware manoeuvre (Planned, To do 8; owner ideas, not hard rules)

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
means no firing, launching or orders but Brace for the rest of the turn. Suggested: when a ship
is crippled or likely to disengage, value positions near phenomena before it tries. A
non-crippled ship that disengages gives 10% ("Enemies Scattered", s.38).

### Special orders

**Built today** (basic): Burn Retros when the safest half-speed move saves more hazard than half
the ship's firepower is worth; otherwise Lock On whenever an enemy is in a battery / lance arc
and range now; otherwise Reload Ordnance when ordnance is spent; it stops when a command check
fails. Never All Ahead Full or Come to New Heading. Brace for Impact is a reaction: when the
expected hull damage from the attack plus enemies still to fire reaches a quarter of its
remaining hits (the commander's ship braces earlier).

**Planned (To do 10, owner notes)**:

- Orders come before the move, so **Lock On** is worth it when an enemy **will or can** be in
  arc after the move: the best straight move with re-rolled misses, against the best move
  without the order (which may turn).
- Every order valued the same way, as expected VP over the best no-order move, with its
  firepower cost: Burn Retros to avoid a hazard, Lock On for more hits, Come to New Heading to
  turn twice (e.g. into a rear arc), All Ahead Full to close, ram or escape, Reload Ordnance for
  next turn's launch.
- **Prioritise**: a failed command check ends all movement-phase orders that turn (s.2; it never
  stops a brace later, see below), so take the most
  valuable, most reliable orders first and skip a low-value order whose failure would block
  more valuable ones. A commander re-roll on a failed check is worth the order plus everything
  the failure would block.
- **Command check modifiers** (s.6) in every pass chance: Enemy Contacts +1 Ld when any enemy
  ship is on special orders, Under Fire -1 with blast markers in contact (Ld 0-10; command checks
  only, not Leadership tests). Both directions: our ship on orders makes the enemy's checks
  easier next turn; an enemy on orders makes ours easier, so our orders are cheaper.
- A teleport-capable ship on any order but Lock On / Reload Ordnance gives up its end-phase
  raid (s.31); that counts against the order.
- **Brace for Impact** (rules, s.7): a failed movement-phase check doesn't stop a ship bracing
  later; a failed brace blocks only that ship until that attacker has finished all its
  attacks; a ship decides separately against each of an attacker's weapons (it may brace
  against the lances after not bracing against the gunnery) but tries only once per attacker
  per turn: a ship that fails against a ship's macrobatteries can't brace when that ship then
  fires its lances (the engine enforces this). When the AI fires, the target is asked before
  each weapon; the player's Fire dialog fires batteries, then lances, then the nova cannon and
  asks before each kind (Built). Planned (To do 11 c): price Brace by what it really costs until the end of the
  ship's next turn (guns, lances and ordnance halved, halved again if crippled; no special
  orders; no firing at all inside an asteroid field, s.39) against the hits it saves over this
  and every later attack until then; trying now also uses up the one try against this
  attacker's later weapons, so a failure leaves its lances unbraceable (saves count only for
  hits past shields). This replaces the fixed quarter-of-hits rule and the commander bias (the
  commander's ship should still brace earlier, because its loss is worth more, but that comes
  out of the values).

---

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

Planned (To do 2): the risk preference, the expert AI valuing craft in flight; splitting
assault boats or waves already in flight. (To do 3): torpedo bombers, whose waves become one combined salvo.

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
- **Planned** (To do 11 a): target-directed candidates, about 20 per ship (goals for the top
  1-3 targets plus a small fallback grid; a denser grid in crowded or hazard-dense fights or
  small reachable areas), the best few refined by hill-climbing, exposure on the best ~20,
  then a fleet coordination pass.
- **Expert AI movement**: for each ship, 9 candidate moves at the root, each followed by a
  minimax search 5 turns deep that tries 6 variations of each side's moves per step and keeps
  the best 4 (alpha-beta pruning), within 2 seconds per ship.

---

## 7. Thinking over several turns

- **Normal AI** (Built): about one turn ahead, through: the enemy's next turn of fire
  (exposure, disengaging), the threat a kill removes, explosions before our next move, next
  turn's launch when holding bays, and ordnance planners looking two game turns (four ordnance
  phases) ahead with the time discount. Disengaging uses a one-turn horizon.
- **Expert AI** (Built): simulates 5 turns of both sides moving and shooting, and stops at the
  game's turn limit.
- **Planned**: the turn-limit risk preference (To do 2: play riskier when behind near the end,
  safer when ahead); crit values over the turns they last (built: up to 3 of the target's shooting phases and the turn limit); scenario objectives over
  the game (To do 7).

---

## 8. Every weight (judgement; tuning is on hold)

Tuning these is on hold (owner: "keep it in mind, but it is hard work, so leave it for now").

| Area | Weight | Value | Meaning |
|---|---|---|---|
| Values | damage short of a threshold | 0.2 | x points / starting hits, per hit (180pt 8-hit cruiser: 4.5 VP) |
| Values | crippled / destroyed | 25% / 100% | of points (s.38) |
| Time | phase discount | 0.85 | per ordnance phase of delay |
| Time | later-turn weight | 0.5 | anything from the next game turn |
| Guns | battery rule of thumb | 0.35 | hits per firepower point vs 5+ |
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
  values are built from; Holding the Field isn't counted yet.
- **Turn limit** (Built in the expert search as a horizon and as its risk preference; Planned for
  the normal AI's choices, To do 2).
- **Scenarios** (Planned, To do 7; owner: "Domination was just one example; there are many
  other scenarios"): the engine today has only old generic modes (kill the admiral, destroy or
  protect a ship, capture an artefact). Every booklet scenario has its own objectives, length
  and end triggers, and the AI must play each: e.g. Domination (objective markers held by a
  ship within 15cm with no enemy near, 1 point per marker at the end of each player's own
  turn, first to 10 or the fleet destroyed / disengaged), convoys and blockade runners getting
  off the table, planets and assault points, Exterminatus, rescue and escape objectives, and the
  rest of the booklet's scenarios. These feed the same values as ship VP, in both the normal AI
  and the expert search.
- **Sub-plots** (Planned, To do 7): Legacies of War, Chance Circumstances, Secret Ploys and the
  faction sub-plots (Mechanicus Quest for Knowledge, Inquisition Secret Ploys, Rogue Trader
  Business as Usual), e.g. the Vendetta target, keeping the flagship above 75% for Fleet
  Experience, boarding for battle plans; the battle result (Heroic Victory to Miserable Defeat).

---

## 10. Easy, normal and expert

| | Easy | Normal (and Hard) | Expert |
|---|---|---|---|
| Targets | random among valid targets | marginal expected VP, focus, no overkill | as normal |
| Special orders | none | Burn Retros / Lock On / Reload (To do 10 to improve) | as normal |
| Ordnance | simple launches (its strike craft, at the nearest target) | full planner: CAP vs strikes, strikes on arrival, lanes, leading, co-ordination | as normal |
| Squadron volleys, hulks, shooting ordnance, disengaging, explosions, screening | off | on | as normal |
| Movement | the same 15 candidates, scored on guns and hazards only (no exposure, focus, explosions or screening) | 15 candidates scored greedily, one turn ahead | 5-turn minimax per ship (9 x search), ~75s a game |

Planned (To do 11 i, suggestion): Easy chooses by a softmax on expected value with a temperature,
so its mistakes look human rather than random; Hard gets the coordination pass or tuned weights.
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

Hard currently plays like Normal. The expert AI replaces only movement; its simulation is
dice-free and leaves out attack craft, hazards and blast markers (only its first move pays for
hazards), so its strength is long-range manoeuvre. Its other phases are the normal AI's.

---

## 11. Things the questions didn't cover

- **Deployment** (gap): ships are grouped for set-up (escorts first, squadrons together) but not
  placed by strategy. Planned with scenarios (To do 7): deploy for the matchup and objectives.
- **Damage control** (gap; To do 11 e): each capital ship rolls a D6 per remaining hit, each 6
  repairs one system, dice halved in contact with blast markers (s.36, XR p.35). Repairs follow a
  fixed priority (fires first, then engines, then the rest), not expected VP: a fire costs 1 hit
  per end phase, a weapon is worth its next turn of fire if it will bear, an engine crit what is lost by not turning; escorts don't repair. The
  fixed order stays as the fallback.
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
- **Not built engine rules** the AI therefore can't use yet: Fighting Sunward, Solar Flares and
  Radiation Bursts (s.40; To do 6), torpedo bombers and mine launcher swaps (To do 3), several
  units (To do 5).
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
~75s a game), VP margin as fitness; the 0.35 battery rule of thumb gives way to the exact Gunnery
table first; redo after any structural change. The same harness is a rules test: an optimiser
finds degenerate strategies in the rules as well as in the AI.

Possible gaps in this plan worth the owner's view: deployment strategy, damage-control choices,
blast-marker removal, whether Hard should differ from Normal, and how much the expert AI should
think (its 2 seconds per ship and its simplified simulation).
