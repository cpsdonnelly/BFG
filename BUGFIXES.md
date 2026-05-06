# BUGFIX TRACKER - Session Feedback

## CRITICAL BUGS (game-breaking)
- [x] B1: Shield damage not tracked as depleting pool across all attacks in a turn
      Shields should deplete: 1 shield escort hit by 2 attacks (1 hit each) = 1 absorbed, 1 hull
- [x] B2: Brace saves applied to shield hits (should only save hull damage)
- [x] B3: Game allows ending movement without all ships moving (should block)
- [x] B4: Ordnance doesn't move in ordnance phase
- [x] B5: Kais' Emissary speed set to 15 instead of 20 (data entry bug)
- [x] B6: No feedback shown when auto-rolling command checks
- [x] B7: Manual dice input not working for command checks
- [x] B8: Movement limited to 2 commands max (should allow unlimited incremental moves)

## GAMEPLAY FIXES
- [x] G1: Rename turn_left/turn_right to anticlockwise/clockwise
- [x] G2: Lock On must NOT affect Nova Cannon (verify in code)
- [x] G3: Shooting and ordnance launch in same phase (should be: shoot first, launch at END)
- [x] G4: No torpedo heading control (should pick angle within forward arc)
- [x] G5: No attack craft wave composition choice
- [x] G6: No heading/distance control for launched craft
- [x] G7: Add remaining movement meter to move dialog
- [x] G8: Auto move minimum distance button
- [x] G9: Auto move minimum-before-turn button (not for escorts)
- [x] G10: Brace persists until next end phase, blocks new orders next turn

## SQUADRON RULES (needed)
- [ ] S1: Squadron coherency check (15cm between members)
- [ ] S2: Largest group keeps squadron benefits when coherency breaks
- [ ] S3: Group move order for escort squadrons

## QOL
- [x] Q1: Help menu with keybindings
- [ ] Q2: Tau tracking systems aura check for nearby ships

## SESSION 3 TASKS (ordered by implementation efficiency)

### Batch 1: Visuals & Scale (affects everything downstream)
- [ ] V1: Blast marker shape: 3 overlapping circles at triangle points, ~2.5x3cm, orange
- [ ] V2: Torpedo marker: rectangle with arrow tip, ~2x2.5cm, team-colored
- [ ] V3: Attack craft: 20x20mm squares, team-colored, letter for type (F/B/M)
- [ ] V4: Nova cannon template visual: 5cm outer circle, 1.2cm center hole
- [ ] V5: Team color distinction on all ordnance
- [ ] V6: Fighter vs bomber visual distinction
- [ ] V7: Special order icon displayed on each ship

### Batch 2: Shooting Improvements
- [ ] F1: Auto full volley button (fire all weapons at closest valid target)
- [ ] F2: Split weapon fire (assign different weapons to different targets)
- [ ] F3: Target priority Ld test for non-closest targets
- [ ] F4: Shooting at ordnance markers (torps/craft as valid targets)
- [ ] F5: Ordnance doesn't block target priority (ship OR ordnance = closest)
- [ ] F6: Line of sight checking (planets, asteroids block LoS)
- [ ] F7: Blast marker / dust cloud gunnery effects

### Batch 3: Ordnance
- [ ] O1: Split torpedo volleys
- [ ] O2: Split attack craft waves
- [ ] O3: Full volley option for torps and craft
- [ ] O4: Ordnance movement in ordnance phase

### Batch 4: UI/QOL
- [ ] U1: Override button for movement phase completion
- [ ] U2: Squadron coherency chain display
- [ ] U3: Warning for unfired weapons
