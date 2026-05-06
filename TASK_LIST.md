# BFG:XR SIMULATOR - LOCKED TASK PRIORITY LIST

## Tier A: Fix Fundamentally Wrong Mechanics
1. [DONE] Fix gunnery table column mapping + edge cases
2. [DONE] Fix shooting at ordnance (6+, one hit kills wave, ordnance column, ordnance-only priority)
3. [DONE] Fix fighter vs torpedo (one marker removes entire salvo, both removed)
4. [DONE] Fix fighter vs attack craft (mutual destruction, resilient saves)
5. [DONE] Fix Tau missile movement (reuse ship movement UI, player-controlled, 20-40cm speed, one 45° turn)
6. [IN PROGRESS] Fix brace timing:
   6a. Per weapon per attacker, failed = can't retry for THAT attacker
   6b. CAN retry against a different attacker
   6c. Brace protects against hit-and-run/teleport attacks (unique crit table save case)
   6d. Brace does NOT protect against crits caused by unsaved weapon hits
   6e. Previous order effects persist (AAF speed stays, Reload stays reloaded)
   6f. Need previous_order field on Ship model
7. [DONE] Fix torpedo friendly fire (hits all ships, exception: fire through base-contact ally at launch)
8. [DONE] Fix split torpedo restriction (Str 7+ only, into exactly two)
9. [DONE] Fix turret usage restriction (craft vs torp/mine exclusive per phase)
10. [DONE] Fix Burn Retros: no minimum distance before turning (currently requires 10/15cm)
11. [PENDING] Fix Brace ordnance halving: torpedo/craft launch strength halved when braced (cumulative with cripple)

## Tier B: Missing Ordnance Features
12. Turret suppression (two modes, game setting toggle):
    12a. XR mode (default): each surviving fighter = 1 bomber gets exactly 3 attacks
    12b. Remastered mode (option): each fighter adds +1 attack, cap = surviving bombers
13. Massed turrets (+1 per base contact ally, max +3, crippled can't contribute)
14. CAP system (fighters escort ships, intercept ordnance, move with parent)
15. Additional torpedo types framework (boarding, short burn, seeking, guided Imperial, melta, vortex)
16. Multi-role attack craft rules (Mantas as fighter+bomber)

## Tier C: Easy Wins (reuse crit table)
17. Hit-and-run raids (roll on crit table, via assault boats or teleport)
18. Teleport attacks:
    18a. Shields must be down on target
    18b. Within 10cm
    18c. Tau cannot teleport
    18d. Attacker not crippled, only on Lock On/Reload/None orders
    18e. Escorts with <3 starting hits cannot teleport
    18f. Cannot target ship with more remaining HP than attacker
    18g. Resolved before damage control and blast marker removal
    18h. Target may attempt Brace against teleport

## Tier D: Major Features + QoL
19. Scroll wheel turning (ships and missiles)
20. Drag-and-drop ship movement
21. Deployment zones (alternating ship placement)
22. Fleet builder (using ship_database.json)
23. Squadron coherency (15cm chain, group orders)

## Tier D+: Dependent Tasks
24. Squadron combined volleys (base contact) [DEPENDS ON: 23]
25. Additional factions and ships [DEPENDS ON: 22, COLLABORATIVE]

## Tier E: Remaining Optional Combat Rules
26. Fighting sunward + arc helper
27. Boarding actions
28. Ramming

## Tier F: Polish
29. Match replay
30. AI commander
