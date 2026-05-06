# MOVEMENT SYSTEM - DESIGN NOTES

## Core Rules to Enforce

### Mandatory Movement
- Ships MUST move every turn unless on Burn Retros
- Minimum move = half speed (unless Burn Retros or speed reduced to 0 by damage/blast markers)
- Ships unable to reach half speed move maximum possible distance
- Ship that moved <5cm counts as DEFENSES on gunnery table

### Minimum Distance Before Turning
- Battleship: must move 15cm before turning
- Cruiser: must move 10cm before turning  
- Escort: can turn at any point (even before moving)
- Only forward movement IN THIS PHASE counts toward the minimum

### Turn Restrictions
- One turn per move (unless Come to New Heading = two turns)
- Turn angle limited by ship profile (45° or 90°)
- Ponderous ships (e.g. Custodian) CANNOT use Come to New Heading at all

### Blast Marker Slowdown
- Moving through ANY blast markers = -5cm speed that phase (once, not per marker)
- Includes moving away from markers you started in contact with
- Ships on AAF that contact a blast marker in last 5cm: stop at the marker

### Special Order Effects on Movement
- ALL AHEAD FULL: +4D6cm, MUST move full distance, NO turns allowed
- BURN RETROS: No minimum move, can be stationary, max half speed, can turn before moving
- COME TO NEW HEADING: Second turn allowed (must move minimum again before 2nd turn)
- LOCK ON: No turns allowed
- RELOAD ORDNANCE: Normal movement
- BRACE FOR IMPACT: Normal movement (but carried from opponent's turn, so already set)

## Two Movement Modes

### Mode 1: Exact Instructions (CLI/Dialog)
Player enters a sequence of move commands:
```
MOVE FORWARD 10
TURN LEFT 45
MOVE FORWARD 10
```
The system validates each step:
- Check minimum distance before turn
- Check turn angle doesn't exceed maximum
- Check total distance is within speed (min half, max full or AAF)
- Show preview path on canvas before confirming

### Mode 2: Drag and Drop (Visual)
1. Click ship to select
2. Drag to show projected path (straight line from current position)
3. Click to set waypoint (turning point)
4. System validates minimum distance was met before the turn
5. Click to set heading at turn point  
6. Drag again for remainder of movement
7. Right-click or Enter to confirm

### Validation Checks (Both Modes)
Before confirming movement:
- [ ] Total distance >= half speed (unless Burn Retros or at max possible)
- [ ] Total distance <= speed (or speed + 4D6 for AAF)
- [ ] No turns if on AAF or Lock On
- [ ] Turn angle <= ship's turn_angle
- [ ] Minimum distance moved before first turn
- [ ] If CtNH: minimum distance moved before second turn too
- [ ] If moving through blast markers: apply -5cm
- [ ] If Burn Retros: distance <= half speed

### Visual Feedback During Movement
- Draw projected path as dotted line from ship
- Show distance traveled along path
- Highlight valid turn zones (where minimum distance is met)
- Show remaining movement budget
- Red warning if attempting illegal move
- Ghost ship at projected final position with heading indicator

### Gravity Well Free Turns
- If starting OR ending move in a planet's gravity well (high orbit):
  - Free turn toward planet center (or up to 45° toward it)
  - No minimum distance needed for this free turn
  - Works even on AAF or Lock On
  - Stacks with CtNH (so theoretically 3 turns: free + 2 from CtNH)

## Implementation Priority
1. Exact instruction mode first (easier to validate)
2. Visual preview of the path
3. Drag-and-drop mode second
4. Both modes share the same validation engine
