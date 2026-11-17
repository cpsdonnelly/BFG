# Remastered-mode rules raised this session (for the engine's Remastered toggles)

XR is the default; these apply only in the engine's Remastered modes.

## Turret suppression (Remastered p.82)

Keep the Remastered suppression toggle, but rewrite it to follow p.82 exactly:
- **Bonus:** each fighter in a wave of bombers actually attacking a ship adds +1 attack to the wave's
  **total** attack run, not +1 to each bomber's roll.
- **Shot-down fighters count:** the bonus applies whether or not turrets shoot that fighter down.
- **Cap:** the bonus cannot exceed the number of bombers **surviving** turret fire, and needs at least one
  surviving bomber.
- **Interception:** fighters intercepted by defending fighters (including CAP) add nothing.
- **Turret order:** turrets remove fighters before any other ordnance type.
- **Bomber rolls:** bombers still roll their normal attacks (D6 minus turrets, minimum 0); the bonus is
  added on top.
- **XR only:** there is no fixed-attack or re-roll bonus in this mode. "Exactly 3 attacks per surviving
  fighter, or 4 for bombers that re-roll their number of attacks" is XR only (booklet s.27, XR Rulebook
  p.32) and stays the default.

Test against Remastered's two worked examples. In both, an Emperor wave attacks a 3-turret Devastation
with no CAP, and the turrets kill three fighters:

| Wave | Each bomber rolls | Bonus attacks |
|---|---|---|
| 3 bombers + 5 fighters | D6-3 | +3 (capped at 3 surviving bombers) |
| 4 bombers + 4 fighters | D6-3 | +4 |

## Escort squadron victory points

Source: Remastered PDF p.121 and its Victory Points summary.

**Destruction:** "Each destroyed escort earns its value in victory points provided the entire escort
squadron is destroyed." There is no 25% crippled award for escort squadrons left on the table at the end;
Remastered's crippled award covers capital ships only.

**Disengaged ships and squadrons:**
- 25% of their total points value if they were crippled before disengaging;
- 10% if they disengaged before being crippled;
- an escort squadron counts as crippled once it has lost half its ships, rounding up.

| Escort squadron at end of game | XR | Remastered |
|---|---|---|
| On table, under half lost | 0 | 0 |
| On table, half or more lost | 25% | 0 |
| All destroyed | 100% | 100% |
| Disengaged, under half lost | 10% | 10% |
| Disengaged, half or more lost | not stated | 25% |

**Ambiguity:** "total points value" for a disengaging crippled squadron most likely means the full
original squadron value, not just the ships that leave. Treat it as that, and flag it as unconfirmed.

**AI consequence in Remastered mode:**
- a crippled escort squadron should not disengage unless it is likely to be wiped out;
- only the last ship's death pays out VP to the enemy.
