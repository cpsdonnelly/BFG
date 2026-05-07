"""BFG:XR Hit-and-Run Raids and Teleport Attacks

Both mechanics share identical resolution logic and are handled here.

HIT-AND-RUN RAIDS
-----------------
Triggered when assault boat ordnance makes contact with an enemy ship
during the ordnance phase. Each assault boat marker produces one raid attempt.

Resolution order (information hiding is critical):
  1. Defender is asked whether to attempt Brace For Impact BEFORE the
     attacker rolls anything. The defender cannot know how many raids
     will succeed — they must commit to brace blind.
  2. If defender braces: perform the Ld command check (same as normal brace).
  3. Attacker rolls 1D6 per raid attempt. A result of 1 is a failure —
     that raid has no effect. Results 2-6 are successful raids.
  4. If defender passed their brace: for each successful raid, defender
     rolls 1D6. On a 4+ that specific raid is repelled and has no effect.
  5. Each surviving successful raid is resolved on the critical damage table.
     The roll used is the same 1D6 the attacker already rolled for that raid.
  6. Crits inflicted by hit-and-run raids cannot be saved against by bracing
     (brace only repels the raid entirely, before the crit is determined).

Only hit-and-run raids and teleport attacks allow the defender to use brace
this way. Crits from direct fire, torpedoes, and bombers cannot be saved.


TELEPORT ATTACKS
----------------
Resolved during the end phase, before damage control or blast marker removal.
Uses the same raid resolution mechanic as hit-and-run raids.

Eligibility checks (attacker must pass ALL of these):
  - Attacker is not crippled
  - Attacker is not on special orders, OR is on Lock On or Reload Ordnance
  - Attacker is not an escort or defense with fewer than 3 starting hits
  - Attacker is not Tau faction
  - Target is within 10cm
  - Target's shields are currently at 0 (knocked down — active shields
    interfere with teleport beams)
  - Target has no more remaining hits than the attacker has remaining hits
  - Each ship may perform at most one teleport attack per end phase

If both players wish to attempt teleport attacks, the active player decides
the resolution order.


FUNCTIONS PLANNED
-----------------

check_teleport_eligibility(attacker, target, gs)
  - Validates all teleport eligibility conditions listed above.
  - Returns (eligible: bool, reason: str) so the caller can explain why not.

resolve_raid(attacker_roll, crit_table, dice, gs)
  - Resolves a single raid given an already-rolled attack die value.
  - A roll of 1 returns failure immediately.
  - Rolls 2-6 look up the result on the critical damage/hit-and-run table.
  - Returns a result dict: {success, roll, crit_type, description}.

resolve_hit_and_run(assault_boat_marker, target_ship, dice, gs)
  - Entry point called from the ordnance phase when an assault boat contacts
    a ship.
  - Counts how many raid attempts this marker produces.
  - Prompts defender for brace decision via a dialog callback.
  - Calls resolve_raid for each attempt.
  - Applies surviving crits to the target ship via combat.apply_damage or
    a dedicated crit application function.
  - Returns a summary dict of results for logging.

resolve_teleport_attack(attacker_ship, target_ship, dice, gs)
  - Entry point called from the end phase dialog.
  - Calls check_teleport_eligibility first.
  - Then follows the same brace prompt → roll → repel → apply crit flow
    as resolve_hit_and_run.
  - Returns a summary dict of results for logging.

prompt_brace_decision(target_ship, context_msg)
  - UI helper: asks the defender if they want to attempt Brace For Impact.
  - Called BEFORE any attack dice are revealed.
  - Returns bool indicating whether brace was chosen and whether the Ld
    check passed.
"""
