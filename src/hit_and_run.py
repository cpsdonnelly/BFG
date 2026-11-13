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
  - Target shields currently at 0 (collapsed, or knocked down by blast markers)
  - Target has no more remaining hits than attacker has remaining hits
  - Each ship may perform at most one teleport attack per end phase
"""

from typing import Callable, List, Dict, Optional, Tuple
from .models import Ship, OrdnanceMarker
from .game_state import GameState
from .dice import DiceRoller
from .geometry import current_shields
from .combat import uses_crit_table


def portal_weapon(ship: Ship):
    """A Necron ship's portals (they replace its teleport attack), or None."""
    return next((w for w in ship.weapons if w.get("weapon_type") == "portal"), None)


def portal_raid_count(ship: Ship) -> int:
    """Portal attacks this end phase: the profile's strength, halved like direct
    fire for crippling (power conservation included) and for All Ahead Full,
    Burn Retros, Come to New Heading or Brace for Impact, rounding down
    (Xenos p.40)."""
    from .necrons import portal_strength
    w = portal_weapon(ship)
    if w is None:
        return 0
    halvings = int(ship.is_crippled) + int(ship.special_order in (
        "all_ahead_full", "burn_retros", "come_to_new_heading", "brace_for_impact"))
    return portal_strength(w.get("strength") or 0, halvings)


def teleport_range(ship: Ship) -> int:
    """10cm (s.31); honour guards double it (Space Marine Teleport Assault);
    an Ork Soopa Tellyporta makes it 30cm."""
    if "soopa_tellyporta" in ship.special_rules:
        return 30
    honour_guard = ("terminator_honour_guard" in ship.special_rules
                    or "veteran_honour_guard" in ship.special_rules)
    return 20 if honour_guard else 10


def teleport_raid_rolls(ship: Ship, dice: DiceRoller, target_name: str) -> Optional[List[int]]:
    """Honour guards (Space Marine Teleport Assault): a Veteran honour guard rolls
    2D6 and uses one result, a Terminator honour guard rolls 3D6 and uses two
    (each a raid). The best results are used. None without an honour guard."""
    if "terminator_honour_guard" in ship.special_rules:
        n, keep, who = 3, 2, "Terminator"
    elif "veteran_honour_guard" in ship.special_rules:
        n, keep, who = 2, 1, "Veteran"
    else:
        return None
    rolls = dice.roll_d6(n, f"{ship.name} {who} honour guard teleport on {target_name} "
                            f"({n}D6, best {keep})")
    return sorted(rolls, reverse=True)[:keep]


def check_teleport_eligibility(attacker: Ship, target: Ship,
                                gs: GameState) -> Tuple[bool, str]:
    """
    Check whether attacker can perform a teleport attack against target.
    Returns (eligible: bool, reason: str). A teleport attack is a hit-and-run
    raid (s.31), so it needs hit-and-run raids enabled as well as teleports
    (owner).
    """
    if not getattr(gs, "rule_hit_and_run", True):
        return False, "hit-and-run raids are disabled"
    portal = portal_weapon(attacker)
    if portal is not None:
        # Necron portals: resolved like teleport attacks, but against targets with
        # more hits too, and while crippled or on special orders (Xenos p.40)
        if portal_raid_count(attacker) <= 0:
            return False, f"{attacker.name}'s portals are at strength 0"
        dist = attacker.distance_to(target)
        rng = portal.get("range_cm") or 10
        if dist > rng:
            return False, f"{target.name} is {dist:.1f}cm away (portals {rng}cm)"
        shields = current_shields(target, gs.get_blast_markers())
        if shields > 0:
            return False, f"{target.name} has {shields} shield(s) still up"
        if attacker.ship_type == "escort" and target.hits_max > 6:
            # Jackal Raider: "may perform portal attacks against ships with 6 hits
            # or less" (reading: starting hits)
            return False, f"{attacker.name} may portal only ships of 6 hits or less"
        return True, ""
    if attacker.is_crippled:
        return False, f"{attacker.name} is crippled"

    allowed_orders = ("none", "lock_on", "reload_ordnance")
    from .chapter_tactics import lightning_vanguard
    if lightning_vanguard(attacker):
        allowed_orders += ("all_ahead_full",)    # Lightning Thrusters
    if attacker.special_order not in allowed_orders:
        return False, f"{attacker.name} is on {attacker.special_order}"

    if "tau" in attacker.faction.lower():
        return False, "Tau cannot perform teleport attacks"

    # Escorts and defenses with fewer than 3 starting hits cannot teleport
    if attacker.ship_type in ("escort", "defense") and attacker.hits_max < 3:
        return False, f"{attacker.name} is too small to perform teleport attacks"

    dist = attacker.distance_to(target)
    max_range = teleport_range(attacker)
    if dist > max_range:
        return False, f"{target.name} is {dist:.1f}cm away (max {max_range}cm)"

    shields = current_shields(target, gs.get_blast_markers())
    if shields > 0:
        return False, f"{target.name} has {shields} shield(s) still up"

    # Space Marines, Teleport Assault: may attack targets with more hits left
    if (target.hits_remaining > attacker.hits_remaining
            and "teleport_assault" not in attacker.special_rules):
        return False, (f"{target.name} has {target.hits_remaining} hits remaining, "
                       f"{attacker.name} only has {attacker.hits_remaining}")

    return True, ""


# Hit-and-run roll modifiers, keyed by special rule. Attacker bonuses are added
# to the raid result; defender penalties are subtracted from the attacker's roll.
_RAID_ATTACK_BONUS = {
    "space_marine_crew": 1,  # Space Marine boarders / ordnance: +1 to raid results
    "mega_armoured_boarders": 1,   # Ork Mega Armoured Boarding Parties
}
_RAID_DEFENSE_PENALTY = {
    "space_marine_crew": 1,  # raids against a Space Marine ship: -1 to the roll
    "mega_armoured_boarders": 1,
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
    Returns the applied crit dict plus the extra damage it dealt, or None if
    cascaded off the table or failed.
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
    if target.hits_remaining > 0:
        # Unused melta / vortex torpedoes in a hit launcher explode (s.16)
        from .combat import torpedo_launcher_crit, mine_launcher_crit
        before = target.hits_remaining
        if not mine_launcher_crit(target, crit_data["crit_type"], dice, gs):
            torpedo_launcher_crit(target, crit_data["crit_type"], dice, gs)
        extra += before - target.hits_remaining

    from .combat import demiurg_leadership
    demiurg_leadership(target)
    gs.update_ship(target)
    return {**crit_entry, "extra_damage": extra}


def raid_has_no_effect(effective: int, target: Ship) -> bool:
    """A raid result that does nothing: 1 or less, or under 4 against a target
    that doesn't use the critical hits table (escorts)."""
    return effective <= 1 or (not uses_crit_table(target) and effective < 4)


def raid_crit_preview(effective: int, target: Ship) -> Optional[str]:
    """The critical a raid result would inflict on a crit-table target, after
    the cascade (no weapons in that slot, unrepairable crit already there), or
    None (off the table, or a prow crit absorbed by Ablative Prow Armour). No
    side effects: used to value Wings of Fury re-rolls."""
    from .tables import CRITICAL_HITS
    from .combat import ARMAMENT_CRIT_TYPES
    roll = max(2, min(6, effective))
    while roll <= 12:
        data = CRITICAL_HITS.get(roll)
        ct = data["crit_type"]
        if ct == "prow_armament" and "ablative_prow_armor" in target.special_rules:
            return None
        if ct in ARMAMENT_CRIT_TYPES and not target.has_armament_slot(ct):
            roll += 1
            continue
        if not data["repairable"] and any(c.get("crit_type") == ct
                                          for c in target.critical_damage):
            roll += 1
            continue
        return ct
    return None


# Expected extra damage of each critical (D3 = 2, D6 = 3.5)
_CRIT_EXTRA = {"engine_room": 1.0, "thrusters_damaged": 1.0, "hull_breach": 2.0,
               "bulkhead_collapse": 3.5, "fire": 0.5}


def _end_phases_before_target_shoots(target: Ship, gs: GameState) -> int:
    """Damage control rolls a crit faces before the target's next shooting
    phase: one (this end phase) when it lands in the raider's turn; two (the
    target's and the raider's end phases) when it lands in the target's own
    turn, after the target has already fired."""
    return 2 if gs.active_player == target.player else 1


def p_crit_unrepaired(target: Ship, gs: GameState, phases: int = 1, new_crits: int = 1) -> float:
    """Chance a newly inflicted repairable crit is still there after `phases`
    end phases of damage control (s.36): one D6 per remaining hit (halved,
    rounding up, touching a blast marker), each 6 repairs one repairable crit;
    the repair crews' choice among several crits is taken as even."""
    from math import comb
    from .geometry import count_blast_markers_touching
    if target.ship_type in ("escort", "defense") and not uses_crit_table(target):
        return 1.0
    n = max(0, target.hits_remaining)
    if count_blast_markers_touching(target, gs.get_blast_markers()) > 0:
        n = (n + 1) // 2
    k = new_crits + sum(1 for c in target.critical_damage if c.get("repairable"))
    survive = 0.0
    for sixes in range(n + 1):
        p = comb(n, sixes) * (1 / 6) ** sixes * (5 / 6) ** (n - sixes)
        survive += p * max(0.0, 1.0 - sixes / k)
    return survive ** max(1, phases)


def _weapon_can_bear(target: Ship, weapon: Dict, friend: Ship, reach: float) -> float:
    """Threat weight at the target's next shooting phase: 1 if the friend is in
    the weapon's arc now and within range + `reach` (the movement before that
    phase); 0.75 if a turn of up to the target's turn angle would bring it into
    the arc; else 0."""
    from .combat import check_weapon_in_arc
    from .chapter_tactics import weapon_range
    rng = weapon_range(target, weapon) or (weapon.get("range_cm") or 0)
    if target.distance_to(friend) > rng + reach:
        return 0.0
    if check_weapon_in_arc(target, weapon, friend.x, friend.y):
        return 1.0
    turn = target.turn_angle or 0
    for dh in (-turn, turn):
        turned = Ship.from_dict({**target.to_dict(), "heading": (target.heading + dh) % 360})
        if dh and check_weapon_in_arc(turned, weapon, friend.x, friend.y):
            return 0.75
    return 0.0


def armament_threat_value(target: Ship, crit_type: str, gs: GameState, owner: int,
                          end_phases: int = None) -> float:
    """Expected VP the raiding player saves by knocking out the target's weapons
    in one location (owner ruling: what the weapons threaten at the target's
    next shooting phase, weighted by the chance damage control hasn't repaired
    the crit by then; extended to the target's later shooting phases, up to
    CRIT_HORIZON and the turn limit, each with two more end phases of repairs,
    a turn's more movement in the reach and the phase_weight discount). Each weapon there scores its expected hits (lances 0.5 a
    die, batteries 0.35, torpedoes 0.3) on the most valuable allied ship it
    can bear on then (`_weapon_can_bear`: in reach = range + the movement
    before that phase, i.e. the target's move, plus ours when the crit lands in
    the target's own turn; in arc now, or after one turn at 0.75). A location
    threatening no allied ship then is worth nothing, so Wings of Fury re-rolls
    it. Weapons already knocked out count nothing."""
    from .ai_hazards import value_per_hit, phase_weight
    from .combat import weapon_in_crit_slot, weapon_disabled_by_crit
    friends = [f for f in gs.get_ships() if f.player == owner and not f.is_destroyed
               and not f.is_disengaged]
    # end_phases: given by a strike planned to land later (ai_hazards.strike_timeline)
    phases = end_phases or _end_phases_before_target_shoots(target, gs)
    weapons = [w for w in target.weapons
               if weapon_in_crit_slot(w, crit_type) and not weapon_disabled_by_crit(target, w)
               and w.get("weapon_type") in _THREAT_PER_DIE]
    if not weapons:
        return 0.0
    total = 0.0
    for j in range(_crit_shooting_phases(target, gs, phases)):
        # the target's j-th shooting phase from now: 2 more end phases of
        # repairs and a game turn more movement for both sides each time
        p_left = p_crit_unrepaired(target, gs, phases + 2 * j)
        if p_left < 0.01:
            break
        threat = 0.0
        for w in weapons:
            best = 0.0
            for f in friends:
                reach = ((target.speed or 0) * (j + 1)
                         + (f.speed or 0) * (j + (1 if phases > 1 else 0)))
                wt = _weapon_can_bear(target, w, f, reach)
                if wt:
                    best = max(best, wt * max(1.0, value_per_hit(f, gs)))
            threat += (w.get("strength") or 0) * _THREAT_PER_DIE[w["weapon_type"]] * best
        total += phase_weight(2 * j) * p_left * threat
    return total


# Expected hits per die / strength point when valuing a silenced weapon
_THREAT_PER_DIE = {"lance": 0.5, "battery": 0.35, "torpedo": 0.3}
# Shooting phases a crit is valued over (judgement): later ones count less
# (phase_weight) and are cut short by repairs and the turn limit
CRIT_HORIZON = 3


def _crit_shooting_phases(target: Ship, gs: GameState, first_end_phases: int) -> int:
    """How many of the target's shooting phases a crit landing now can still
    affect: CRIT_HORIZON, cut by the game's turn limit (the target shoots once
    a game turn; when the crit lands in its own turn it has already fired)."""
    n = CRIT_HORIZON
    limit = getattr(gs, "turn_limit", None)
    if limit:
        left = limit - gs.turn_number + (1 if first_end_phases <= 1 else 0)
        n = min(n, max(1, left))
    return n


def raid_result_value(effective: int, target: Ship, gs: GameState, owner: int,
                      end_phases: int = None) -> float:
    """Expected VP a raid result is worth to the raiding player (before any
    brace save, which scales every result alike). Escorts: 1 damage on 4+.
    Capital ships: the critical it inflicts after the cascade, valued as its
    extra damage (Engine Room +1 hit) plus its effect: an armament critical by
    the weapons it silences (armament_threat_value), Bridge Smashed and
    Shields Collapse a share of the ship's value."""
    from .ai_hazards import ship_value, value_per_hit
    if raid_has_no_effect(effective, target):
        return 0.0
    vph = max(1.0, value_per_hit(target, gs))       # points unknown: still worth something
    if not uses_crit_table(target):
        # the hit that destroys it is worth the ship (not its value per hit on top)
        return max(vph, ship_value(target, gs)) if target.hits_remaining <= 1 else vph
    ct = raid_crit_preview(effective, target)
    if ct is None:
        return 0.0
    from .combat import ARMAMENT_CRIT_TYPES
    extra = _CRIT_EXTRA.get(ct, 0.0)
    value = extra * vph
    if extra and target.hits_remaining <= extra:
        value += ship_value(target, gs) * 0.5          # may finish it off
    if ct in ARMAMENT_CRIT_TYPES:
        value += armament_threat_value(target, ct, gs, owner, end_phases)
    elif ct == "bridge_smashed":
        value += ship_value(target, gs) * 0.1
    elif ct == "shields_collapse":
        value += ship_value(target, gs) * 0.15
    elif ct == "thrusters_damaged":
        value += vph * 0.5
    return value


def best_raid_reroll(roll: int, effective: int, target: Ship, gs: GameState,
                     owner: int) -> bool:
    """Wings of Fury: re-roll when a fresh D6 (same modifiers) is worth more on
    average than the result in hand. Against escorts (1 damage on 4+) that is
    exactly "re-roll a result with no effect": Space Marines (+1) re-roll a 1
    or 2."""
    mod = effective - roll
    keep = raid_result_value(effective, target, gs, owner)
    again = sum(raid_result_value(r + mod, target, gs, owner) for r in range(1, 7)) / 6.0
    return keep <= 0 or again > keep + 1e-9      # nothing in hand: nothing to lose


def describe_raid_result(effective: int, target: Ship) -> str:
    """Plain-words outcome of a raid result, before any brace save."""
    if raid_has_no_effect(effective, target):
        return "no effect"
    if not uses_crit_table(target):
        return "1 damage"
    from .tables import CRITICAL_HITS
    entry = CRITICAL_HITS.get(max(2, min(6, effective))) or {}
    name = entry.get("name") or entry.get("crit_type", "critical hit").replace("_", " ")
    return f"critical hit: {name}"


def resolve_raids(num_raids: int, target: Ship, brace_passed: bool,
                  dice: DiceRoller, gs: GameState,
                  source_name: str = "Assault boat",
                  attacker_rules: Optional[List[str]] = None,
                  preset_rolls: Optional[List[int]] = None,
                  reroll_failed: bool = False,
                  reroll_fn: Optional[Callable[[int, int, Ship], bool]] = None) -> Dict:
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
        "damage": int,               # damage to escorts/small targets (no crits)
      }
    """
    # Sub-plots: Secret Intelligence (a hit-and-run attack on the nominated ship)
    from .subplots import record_raid
    record_raid(gs, 3 - target.player, target)
    summary = {
        "raid_rolls": [],
        "failures": 0,
        "repelled": 0,
        "crits_applied": [],
        "damage": 0,
    }

    mod = _raid_roll_modifier(attacker_rules or [], target)
    if mod:
        gs.add_log(f"  Raid modifier: {mod:+d} to each result (crew quality)")

    for i in range(num_raids):
        if preset_rolls is not None:
            roll = preset_rolls[i]          # chosen from an honour guard's dice
        else:
            roll = dice.roll_d6(1, f"{source_name} raid {i+1}/{num_raids} on {target.name}")[0]
        effective = roll + mod
        # Wings of Fury: Thunderhawks may re-roll their raid results; the
        # second result stands. reroll_fn(roll, effective, target) is the
        # owner's choice; without one, re-roll a raid that would have no effect.
        no_effect = effective <= 1 or (not uses_crit_table(target) and effective < 4)
        if reroll_fn is not None:
            wants = bool(reroll_fn(roll, effective, target))
        else:
            wants = reroll_failed and no_effect
        if wants:
            gs.add_log(f"  Raid {i+1}: rolled {roll} — Wings of Fury re-roll")
            roll = dice.roll_d6(1, f"{source_name} raid {i+1} re-roll on {target.name}")[0]
            effective = roll + mod
        summary["raid_rolls"].append(roll)

        if effective <= 1:
            summary["failures"] += 1
            gs.add_log(f"  Raid {i+1}: rolled {roll}"
                       + (f" ({effective} after modifier)" if mod else "")
                       + " — FAILURE, no effect")
            continue

        gs.add_log(f"  Raid {i+1}: rolled {roll}"
                   + (f" ({effective} after modifier)" if mod else ""))

        if not uses_crit_table(target) and effective < 4:
            summary["failures"] += 1
            gs.add_log(f"  Raid {i+1}: no effect on {target.name} (needs 4+ vs small target)")
            continue

        # Defender brace repel attempt (4+)
        if brace_passed:
            repel_roll = dice.roll_d6(1, f"{target.name} repel raid {i+1} (4+)")[0]
            if repel_roll >= 4:
                summary["repelled"] += 1
                gs.add_log(f"  Raid {i+1}: REPELLED (rolled {repel_roll} on 4+)")
                continue
            else:
                gs.add_log(f"  Raid {i+1}: repel failed (rolled {repel_roll})")

        if not uses_crit_table(target):
            # Escorts and small targets: 1 damage, never a critical hit
            target.hits_remaining = max(0, target.hits_remaining - 1)
            from .combat import demiurg_leadership
            demiurg_leadership(target)
            gs.update_ship(target)
            summary["damage"] += 1
            gs.add_log(f"  Raid {i+1}: 1 damage to {target.name}")
            continue

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

    wings = (marker.ordnance_type == "thunderhawk"
             and "chapter_tactic:wings_of_fury" in (marker.special_rules or []))
    hook = getattr(gs, "raid_reroll_hook", None)

    def wings_reroll(roll, effective, tgt, _owner=marker.owner_player):
        answer = hook(_owner, roll, effective, tgt) if hook else None
        if answer is None:              # no player to ask (AI, tests): expected-value choice
            return best_raid_reroll(roll, effective, tgt, gs, _owner)
        return answer
    summary = resolve_raids(num_raids, target, brace_passed, dice, gs,
                            source_name=marker.ordnance_type,
                            attacker_rules=marker.special_rules,
                            reroll_fn=wings_reroll if wings else None)
    summary["brace_wanted"] = wanted_brace
    summary["brace_passed"] = brace_passed
    from .ordnance import end_ordnance_attack
    end_ordnance_attack(target, gs)          # Promethean turret halving used up
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

    chosen = teleport_raid_rolls(attacker, dice, target.name)
    count = len(chosen) if chosen else 1
    if portal_weapon(attacker) is not None:
        count, chosen = portal_raid_count(attacker), None
    summary = resolve_raids(count, target, brace_passed, dice, gs,
                            source_name=f"{attacker.name} teleporters",
                            attacker_rules=attacker.special_rules,
                            preset_rolls=chosen)
    summary["brace_wanted"] = wanted_brace
    summary["brace_passed"] = brace_passed
    return summary
