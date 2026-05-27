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
  6. Crits inflicted by hit-and-run raids cannot be saved against by bracing.
     Brace only repels the raid entirely, before the crit is determined.

Only hit-and-run raids and teleport attacks allow the defender to use brace
this way. Crits from direct fire, torpedoes, and bombers cannot be saved.

TELEPORT ATTACKS
----------------
Resolved during the end phase, before damage control or blast marker removal.
Uses the same raid resolution mechanic as hit-and-run raids.

Eligibility:
  - Attacker not crippled
  - Attacker not on special orders (Lock On and Reload Ordnance are allowed)
  - Attacker not an escort or defense with fewer than 3 starting hits
  - Attacker is not Tau faction
  - Target within 10cm
  - Target shields currently at 0
  - Target has no more remaining hits than attacker has remaining hits
  - Each ship may perform at most one teleport attack per end phase
"""

import math
from typing import List, Dict, Optional, Tuple
from .models import Ship, OrdnanceMarker
from .game_state import GameState
from .dice import DiceRoller
from .tables import CRITICAL_HITS


def check_teleport_eligibility(attacker: Ship, target: Ship,
                                gs: GameState) -> Tuple[bool, str]:
    """
    Check whether attacker can perform a teleport attack against target.
    Returns (eligible: bool, reason: str).
    """
    if attacker.is_crippled:
        return False, f"{attacker.name} is crippled"

    allowed_orders = ("none", "lock_on", "reload_ordnance")
    if attacker.special_order not in allowed_orders:
        return False, f"{attacker.name} is on {attacker.special_order}"

    if "tau" in attacker.faction.lower():
        return False, "Tau cannot perform teleport attacks"

    # Escorts and defenses with fewer than 3 starting hits cannot teleport
    if attacker.ship_type in ("escort", "defense") and attacker.hits_max < 3:
        return False, f"{attacker.name} is too small to perform teleport attacks"

    dist = attacker.distance_to(target)
    if dist > 10:
        return False, f"{target.name} is {dist:.1f}cm away (max 10cm)"

    if target.effective_shields > 0:
        return False, f"{target.name} has active shields"

    if target.hits_remaining > attacker.hits_remaining:
        return False, (f"{target.name} has {target.hits_remaining} hits remaining, "
                       f"{attacker.name} only has {attacker.hits_remaining}")

    return True, ""


# Hit-and-run roll modifiers, keyed by special rule. Attacker bonuses are added
# to the raid result; defender penalties are subtracted from the attacker's roll.
_RAID_ATTACK_BONUS = {
    "space_marine_crew": 1,  # Space Marine boarders / ordnance: +1 to raid results
}
_RAID_DEFENSE_PENALTY = {
    "space_marine_crew": 1,  # raids against a Space Marine ship: -1 to the roll
}


def _raid_roll_modifier(attacker_rules: List[str], target: Ship) -> int:
    """Net modifier applied to each hit-and-run / teleport raid roll.

    Attacker special rules add to the result; the target's special rules subtract
    from it. Defaults to 0 when no relevant rules are present.
    """
    bonus = sum(_RAID_ATTACK_BONUS.get(r, 0) for r in attacker_rules)
    penalty = sum(_RAID_DEFENSE_PENALTY.get(r, 0) for r in target.special_rules)
    return bonus - penalty


def _apply_raid_crit(roll: int, target: Ship, gs: GameState,
                     dice: DiceRoller) -> Optional[Dict]:
    """
    Apply a single hit-and-run raid result using the 1D6 roll.
    Roll of 1 = failure (should already be filtered before calling this).
    Rolls 2-6 look up directly on the critical damage table.
    Uses cascade rules (same as standard crits).
    Returns the applied crit dict, or None if cascaded off the table or failed.
    """
    from .combat import _resolve_crit_cascade
    crit_data = _resolve_crit_cascade(roll, target, gs)
    if crit_data is None:
        gs.add_log(f"  Raid result {roll} cascaded off the table — no effect")
        return None

    extra = crit_data["extra_damage"]
    if extra == "D3":
        extra = dice.roll_d3(f"Raid hull breach extra damage on {target.name}")
    elif extra == "D6":
        extra = sum(dice.roll_d6(1, f"Raid bulkhead collapse extra damage on {target.name}"))
    else:
        extra = int(extra) if extra else 0

    crit_entry = {
        "crit_type": crit_data["crit_type"],
        "description": crit_data["name"],
        "repairable": crit_data["repairable"],
        "turn_inflicted": gs.turn_number,
    }
    target.critical_damage.append(crit_entry)

    if extra > 0:
        target.hits_remaining = max(0, target.hits_remaining - extra)
        gs.add_log(f"  Raid: {crit_data['name']} (+{extra} extra damage)")
    else:
        gs.add_log(f"  Raid: {crit_data['name']}")

    gs.update_ship(target)
    return crit_entry


def resolve_raids(num_raids: int, target: Ship, brace_passed: bool,
                  dice: DiceRoller, gs: GameState,
                  source_name: str = "Assault boat",
                  attacker_rules: Optional[List[str]] = None) -> Dict:
    """
    Core raid resolution shared by hit-and-run raids and teleport attacks.

    num_raids: number of raid attempts (one per assault boat marker, or 1 for teleport)
    target: the defending ship
    brace_passed: True if the defender successfully passed a Brace For Impact Ld check
    source_name: label for log messages
    attacker_rules: special rules of the attacking ship / ordnance, used to apply
      crew-quality raid modifiers (e.g. Space Marines +1, or -1 vs a Space Marine ship)

    Returns a summary dict:
      {
        "raid_rolls": List[int],     # all natural 1D6 rolls made
        "failures": int,             # raids that failed (effective result <= 1)
        "repelled": int,             # raids repelled by brace (4+ saves)
        "crits_applied": List[dict], # crit entries that were applied
      }
    """
    summary = {
        "raid_rolls": [],
        "failures": 0,
        "repelled": 0,
        "crits_applied": [],
    }

    mod = _raid_roll_modifier(attacker_rules or [], target)
    if mod:
        gs.add_log(f"  Raid modifier: {mod:+d} to each result (crew quality)")

    for i in range(num_raids):
        roll = dice.roll_d6(1, f"{source_name} raid {i+1}/{num_raids} on {target.name}")[0]
        summary["raid_rolls"].append(roll)
        effective = roll + mod

        if effective <= 1:
            summary["failures"] += 1
            gs.add_log(f"  Raid {i+1}: rolled {roll}"
                       + (f" ({effective} after modifier)" if mod else "")
                       + " — FAILURE, no effect")
            continue

        gs.add_log(f"  Raid {i+1}: rolled {roll}"
                   + (f" ({effective} after modifier)" if mod else ""))

        # Defender brace repel attempt (4+)
        if brace_passed:
            repel_roll = dice.roll_d6(1, f"{target.name} repel raid {i+1} (4+)")[0]
            if repel_roll >= 4:
                summary["repelled"] += 1
                gs.add_log(f"  Raid {i+1}: REPELLED (rolled {repel_roll} on 4+)")
                continue
            else:
                gs.add_log(f"  Raid {i+1}: repel failed (rolled {repel_roll})")

        # Apply the crit using the modified result, clamped to the table range (2-6)
        crit = _apply_raid_crit(max(2, min(6, effective)), target, gs, dice)
        if crit:
            summary["crits_applied"].append(crit)

    return summary


def resolve_hit_and_run(marker: OrdnanceMarker, target: Ship,
                        dice: DiceRoller, gs: GameState,
                        brace_decision_fn) -> Dict:
    """
    Resolve hit-and-run raids from an assault boat marker contacting a ship.

    brace_decision_fn: callable(target_ship, context_msg) -> (wanted_brace: bool, passed: bool)
      This is a UI callback provided by game_panel.py. It must prompt the
      defender BEFORE any raid dice are shown.

    Returns the summary dict from resolve_raids plus brace info.
    """
    gs.add_log(f"  {marker.ordnance_type} hit-and-run raid on {target.name}!")

    # One raid attempt per assault boat marker (strength ignored for raid count)
    num_raids = 1

    # Defender decides on brace BEFORE any rolls are made
    brace_msg = (f"{target.name} is being boarded by {marker.ordnance_type}!\n"
                 f"Attempt Brace For Impact before raids are rolled?\n"
                 f"(A passed brace lets you roll 4+ to repel each raid)")
    wanted_brace, brace_passed = brace_decision_fn(target, brace_msg)

    if wanted_brace:
        if brace_passed:
            gs.add_log(f"  {target.name} brace passed — will roll to repel each raid")
        else:
            gs.add_log(f"  {target.name} brace FAILED — no repel rolls")

    summary = resolve_raids(num_raids, target, brace_passed, dice, gs,
                            source_name=marker.ordnance_type,
                            attacker_rules=marker.special_rules)
    summary["brace_wanted"] = wanted_brace
    summary["brace_passed"] = brace_passed
    return summary


def resolve_teleport_attack(attacker: Ship, target: Ship,
                             dice: DiceRoller, gs: GameState,
                             brace_decision_fn) -> Dict:
    """
    Resolve a teleport attack from attacker against target.
    Eligibility must be checked by the caller before calling this.

    brace_decision_fn: same callback as resolve_hit_and_run.

    Returns the summary dict from resolve_raids plus brace info.
    """
    gs.add_log(f"  {attacker.name} teleport attack on {target.name}!")

    brace_msg = (f"{target.name} is being boarded via teleporter from {attacker.name}!\n"
                 f"Attempt Brace For Impact before raids are rolled?\n"
                 f"(A passed brace lets you roll 4+ to repel each raid)")
    wanted_brace, brace_passed = brace_decision_fn(target, brace_msg)

    if wanted_brace:
        if brace_passed:
            gs.add_log(f"  {target.name} brace passed — will roll to repel each raid")
        else:
            gs.add_log(f"  {target.name} brace FAILED — no repel rolls")

    summary = resolve_raids(1, target, brace_passed, dice, gs,
                            source_name=f"{attacker.name} teleporters",
                            attacker_rules=attacker.special_rules)
    summary["brace_wanted"] = wanted_brace
    summary["brace_passed"] = brace_passed
    return summary
