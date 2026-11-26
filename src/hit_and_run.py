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
import math

from typing import Callable, List, Dict, Optional, Tuple
from .models import Ship, OrdnanceMarker
from .game_state import GameState
from . import recorder as _rec
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
    (Surprise Attack's ships on standby can't.)
    Returns (eligible: bool, reason: str). A teleport attack is a hit-and-run
    raid (s.31), so it needs hit-and-run raids enabled as well as teleports
    (owner).
    """
    if not getattr(gs, "rule_hit_and_run", True):
        return False, "hit-and-run raids are disabled"
    from .scenarios import on_standby
    if on_standby(gs, attacker):
        return False, "on standby (Surprise Attack)"
    if "ghostship" in attacker.special_rules:
        return False, "Ghostships may not initiate teleport attacks (MMS p.20)"
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
    "dark_eldar": 1,         # Dark Eldar Pain Frenzy (Xenos p.4), their ordnance too
    "tyranid": 1,            # Tyranids and their ordnance (Xenos p.105)
    "bloodswarm": 1,         # Necron Bloodswarm Nanoscarabs: +1 to its portal attacks
    "aspect_warriors": 1,    # Eldar Aspect Warriors: +1 to all its hit-and-run attacks (MMS)
}
_RAID_DEFENSE_PENALTY = {
    "space_marine_crew": 1,  # raids against a Space Marine ship: -1 to the roll
    "mega_armoured_boarders": 1,
    "incubi": 1,             # Dark Eldar Incubi: enemy raids on the ship -1
    "tyranid": 1,            # a bio-ship's innards: enemy raids -1 (Xenos p.105)
    "ghostship": -1,         # Eldar Ghostships: enemy raids +1 (MMS p.20)
}


ASSAULT_BOAT_RAID = "assault_boat_raid"     # a raid made by an assault boat (tag)


def _raid_roll_modifier(attacker_rules: List[str], target: Ship) -> int:
    """Net modifier applied to each hit-and-run / teleport raid roll.

    Attacker special rules add to the result; the target's special rules subtract
    from it. Defaults to 0 when no relevant rules are present.
    """
    bonus = sum(_RAID_ATTACK_BONUS.get(r, 0) for r in attacker_rules)
    penalty = sum(_RAID_DEFENSE_PENALTY.get(r, 0) for r in target.special_rules)
    # Tyranid Mucous Membrane (biomorph): assault boats (Impalers too, a kind
    # of assault boat) attacking the ship suffer a further -1
    if ASSAULT_BOAT_RAID in attacker_rules and "mucous_membrane" in target.special_rules:
        penalty += 1
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
        # The crit's own effects, as for any crit (Bridge Smashed -3 Ld, Necron
        # Ld losses, Eldar Infinity Circuit / Holofield)
        from .combat import apply_crit_effects
        before = target.hits_remaining
        apply_crit_effects(target, crit_data, gs)
        extra += before - target.hits_remaining
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
    side effects: used to value Wings of Fury re-rolls. The engine's own
    cascade on the target's own table (Eldar, Necron, stations...)."""
    from .combat import _resolve_crit_cascade
    data = _resolve_crit_cascade(max(2, min(6, effective)), target, _SilentLog())
    return data["crit_type"] if data else None


class _SilentLog:
    """A stand-in game state for previews: the cascade only logs to it."""
    def add_log(self, *_a, **_k):
        pass


# Expected extra damage of each critical (D3 = 2, D6 = 3.5)
_CRIT_EXTRA = {"engine_room": 1.0, "thrusters_damaged": 1.0, "hull_breach": 2.0,
               "bulkhead_collapse": 3.5}


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


def p_system_down(target: Ship, gs: GameState, phases: int, k: int,
                  others: int = None) -> float:
    """Chance a system hit by `k` repairable crits of one type is still down
    after `phases` end phases of damage control (s.36: a D6 per remaining hit,
    halved rounding up touching a blast marker, each 6 repairs one crit; the
    system works again only when every one of its crits is repaired, rules
    "not cumulative; all must be repaired"). Exact: a chain over the crits
    left, the repairs falling evenly at random among all the repairable crits
    (`others`: the ship's other repairable crits, by default those it has)."""
    from math import comb
    from .geometry import count_blast_markers_touching
    if k <= 0:
        return 0.0
    if target.ship_type in ("escort", "defense") and not uses_crit_table(target):
        return 1.0
    n = max(0, target.hits_remaining)
    if count_blast_markers_touching(target, gs.get_blast_markers()) > 0:
        n = (n + 1) // 2
    if others is None:
        others = sum(1 for c in target.critical_damage if c.get("repairable")) - k
        others = max(0, others)
    six = [comb(n, x) * (1 / 6) ** x * (5 / 6) ** (n - x) for x in range(n + 1)]
    state = {(k, others): 1.0}
    for _ in range(max(1, phases)):
        nxt = {}
        for (a, b), q in state.items():
            if a == 0:
                nxt[(a, b)] = nxt.get((a, b), 0.0) + q
                continue
            tot = a + b
            for x, px in enumerate(six):
                r = min(x, tot)
                # thruster crits among the r repaired: hypergeometric
                for ra in range(max(0, r - b), min(a, r) + 1):
                    ph = comb(a, ra) * comb(b, r - ra) / comb(tot, r)
                    key = (a - ra, b - (r - ra))
                    nxt[key] = nxt.get(key, 0.0) + q * px * ph
        state = nxt
    return sum(q for (a, _b), q in state.items() if a > 0)


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
    a turn's more movement in the reach and the phase_weight discount). Each weapon there scores its expected hits (batteries on the Gunnery table, lances by
    their own rules, `ai_hazards._gun_hits`; torpedoes 0.3) on the most valuable allied ship it
    can bear on then (`_weapon_can_bear`: in reach = range + the movement
    before that phase, i.e. the target's move, plus ours when the crit lands in
    the target's own turn; in arc now, or after one turn at 0.75). A location
    threatening no allied ship then is worth nothing, so Wings of Fury re-rolls
    it. Weapons already knocked out count nothing."""
    from .ai_hazards import phase_weight, added_vp
    from .combat import weapon_in_crit_slot, weapon_disabled_by_crit
    friends = [f for f in gs.get_ships() if f.player == owner and not f.is_destroyed
               and not f.is_disengaged]
    # end_phases: given by a strike planned to land later (ai_hazards.strike_timeline)
    phases = end_phases or _end_phases_before_target_shoots(target, gs)
    weapons = [w for w in target.weapons
               if weapon_in_crit_slot(w, crit_type) and not weapon_disabled_by_crit(target, w)
               and w.get("weapon_type") in _THREAT_PER_DIE]
    # launch bays in that location (a Dark Eldar Torture's keel bays): their
    # share of the ship's bays' worth a turn (ai_hazards.bay_threat_vp)
    bay_vp = 0.0
    all_bays = [w for w in target.weapons if w.get("weapon_type") == "launch_bay"]
    hit_bays = [w for w in all_bays if weapon_in_crit_slot(w, crit_type)
                and not weapon_disabled_by_crit(target, w)]
    if hit_bays:
        from .ai_hazards import bay_threat_vp
        tot = sum(w.get("strength") or 0 for w in all_bays) or 1
        bay_vp = bay_threat_vp(target, gs) * sum(w.get("strength") or 0 for w in hit_bays) / tot
    if not weapons and bay_vp <= 0:
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
            st = w.get("strength") or 0
            if target.is_crippled:
                st = target.crippled_value(st)        # a crippled ship's guns fire at half
            for f in friends:
                reach = ((target.speed or 0) * (j + 1)
                         + (f.speed or 0) * (j + (1 if phases > 1 else 0)))
                wt = _weapon_can_bear(target, w, f, reach)
                if wt:
                    # the hits it would score on that ship: batteries on the
                    # Gunnery table, lances by their own rules (To do 30;
                    # ai_hazards._gun_hits, crippling included); torpedoes 0.3
                    if w["weapon_type"] in ("battery", "lance"):
                        from .ai_hazards import _gun_hits
                        h = _gun_hits(target, w, f)
                        best = max(best, wt * added_vp(f, gs, 0.0, h))
                    elif w["weapon_type"] == "torpedo":
                        # the salvo's exact hits after the friend's turrets
                        # (torpedoes ignore shields, s.15)
                        from .ai_hazards import torpedo_salvo_hits
                        h = torpedo_salvo_hits(st, f, gs, (target.x, target.y),
                                               target.special_rules)
                        best = max(best, wt * added_vp(f, gs, 0.0, h, shields=False))
                    else:
                        h = st * _THREAT_PER_DIE[w["weapon_type"]]
                        best = max(best, wt * added_vp(f, gs, 0.0, h))
            threat += best
        threat += bay_vp
        total += phase_weight(2 * j) * p_left * threat
    return total


def _bears_mobility(shooter: Ship, weapon: Dict, victim: Ship, reach: float,
                    can_turn: bool) -> float:
    """`_weapon_can_bear`, with the turn allowed only when the shooter can turn
    (Engine Room Damaged and its kind take it away)."""
    from .combat import check_weapon_in_arc
    from .chapter_tactics import weapon_range
    rng = weapon_range(shooter, weapon) or (weapon.get("range_cm") or 0)
    if shooter.distance_to(victim) > rng + reach:
        return 0.0
    if check_weapon_in_arc(shooter, weapon, victim.x, victim.y):
        return 1.0
    if not can_turn:
        return 0.0
    from .models import ship_copy
    turn = shooter.turn_angle or 0
    for dh in (-turn, turn):
        if dh and check_weapon_in_arc(ship_copy(shooter, heading=(shooter.heading + dh) % 360),
                                      weapon, victim.x, victim.y):
            return 0.75
    return 0.0


def _exchange(target: Ship, gs: GameState, owner: int, j: int, phases: int,
              ref_speed: float) -> Tuple[float, float, float]:
    """The target's exchange with the owner's fleet at its j-th shooting phase
    from now, from the target's side: (net VP, its threat VP, our fire's VP on
    it) in the posture it would pick (owner: compute, don't guess). Its speed,
    turns, shields and guns are read from the ship itself (`effective_speed`,
    `movement.get_max_turns`, `effective_shields`, `weapon_disabled_by_crit`), so a
    copy carrying a crit shows that crit's effect.
    - attack: it closes (its move towards each of our ships, all of it if it can
      turn, else the part along its heading) and so do we; its guns' reach is
      both moves before its shot; ours on it, in our shooting phase after our
      move, its undamaged move plus ours (we close the gap it no longer can);
    - evade: it runs (away from each ship, as above), our ships chase; its
      reach our moves before its shot less its, ours our moves less its.
    Its fire: each weapon at the most valuable of our ships it bears on (the
    armament model, `armament_threat_value`); ours: every battery / lance that
    bears, past its shields (`past_shields`), at its value a hit."""
    from .ai_hazards import _gun_hits, past_shields, added_vp, damage_vp
    from .combat import weapon_disabled_by_crit
    from .movement import get_max_turns
    friends = [f for f in gs.get_ships() if f.player == owner and not f.is_destroyed
               and not f.is_disengaged]
    if not friends:
        return 0.0, 0.0, 0.0
    can_turn = get_max_turns("", target) > 0
    t_move = (target.effective_speed or 0) * (j + 1)
    t_ref = ref_speed * (j + 1)
    shields = target.effective_shields
    weapons = [w for w in target.weapons if w.get("weapon_type") in _THREAT_PER_DIE
               and not weapon_disabled_by_crit(target, w)]

    def f_move(f):
        return (f.speed or 0) * (j + (1 if phases > 1 else 0))

    def along(f, sign):
        # its move towards (+1) or away from (-1) ship f
        if can_turn:
            return t_move
        b = math.atan2(f.y - target.y, f.x - target.x)
        c = math.cos(b - math.radians(target.heading or 0))
        return t_move * max(0.0, sign * c)

    def threat(reach_of):
        tot = 0.0
        for w in weapons:
            best = 0.0
            for f in friends:
                wt = _bears_mobility(target, w, f, reach_of(f), can_turn)
                if not wt:
                    continue
                if w["weapon_type"] in ("battery", "lance"):
                    h = _gun_hits(target, w, f)
                else:
                    st = w.get("strength") or 0
                    if target.is_crippled:
                        st = target.crippled_value(st)
                    h = st * _THREAT_PER_DIE[w["weapon_type"]]
                best = max(best, wt * added_vp(f, gs, 0.0, h))
            tot += best
        return tot

    def our_fire(reach_of):
        lam = 0.0
        for f in friends:
            r = reach_of(f)
            for w in f.weapons:
                if w.get("weapon_type") not in ("battery", "lance"):
                    continue
                wt = _bears_mobility(f, w, target, r, get_max_turns("", f) > 0)
                if wt:
                    lam += wt * _gun_hits(f, w, target)
        return damage_vp(target, gs, past_shields(lam, shields))

    # our fire on it comes in our shooting phase, after our own move: one more
    # of our moves than its shot (j + 1 of each side's moves by then)
    def our_move(f):
        return (f.speed or 0) * (j + 1)
    a_threat = threat(lambda f: along(f, 1) + f_move(f))
    a_fire = our_fire(lambda f: t_ref + our_move(f))
    e_threat = threat(lambda f: f_move(f) - along(f, -1))
    e_fire = our_fire(lambda f: our_move(f) - along(f, -1))
    if a_threat - a_fire >= e_threat - e_fire:
        return a_threat - a_fire, a_threat, a_fire
    return e_threat - e_fire, e_threat, e_fire


def _crit_entry(target: Ship, ct: str) -> Dict:
    from .tables import crit_table_for
    for e in crit_table_for(target).values():
        if e.get("crit_type") == ct:
            return e
    return {"crit_type": ct, "repairable": True}


def _brace_pass(ld: int) -> float:
    from .ai_hazards import p_sum_at_most
    return p_sum_at_most(2, max(0, ld))


def superstructure_value(target: Ship, ct: str, gs: GameState, owner: int,
                         end_phases: int = None) -> float:
    """Expected VP of a Superstructure Damaged crit (Dark Eldar, Eldar;
    Appendix 3): until repaired, a D6 each time the ship turns in its
    movement phase, 1-2 one point of damage (`dark_eldar.superstructure_strain`).
    The ship chooses: turn (one turn a move, `movement.get_max_turns`) and take
    the 1 in 3 chance of a hit (`ai_hazards.hits_vp`), or keep straight, which
    costs what a no-turns crit costs it (the Graviton Harness / Mast Lines
    effect measured on a copy, `crit_effect_value`); the cheaper of the two,
    over the movement phases the crit is likely to last (`p_crit_unrepaired`,
    `phase_weight`)."""
    from .ai_hazards import hits_vp, phase_weight
    from .movement import get_max_turns
    turns = max(0, get_max_turns("", target)) if target.speed else 0
    if turns <= 0:
        return 0.0
    phases = end_phases or _end_phases_before_target_shoots(target, gs)
    strain = 0.0
    for j in range(_crit_shooting_phases(target, gs, phases)):
        p_left = p_crit_unrepaired(target, gs, phases + 2 * j)
        if p_left < 0.01:
            break
        strain += phase_weight(2 * j) * p_left * min(turns, 2) / 3.0 * hits_vp(target, gs, 1)
    no_turn = crit_effect_value(target, "graviton_harness" if ct == "de_superstructure"
                                else "mast_lines", gs, owner, end_phases)
    return min(strain, no_turn)


def crit_effect_value(target: Ship, ct: str, gs: GameState, owner: int,
                      end_phases: int = None, count: int = 1) -> float:
    """Expected VP, to the owner, of the EFFECT of `count` critical hits of type
    `ct` on `target` (no extra damage; owner: computed, not a share of the
    ship's value). The crit is applied to a copy of the ship by the engine's own
    rules (its record, then `combat.apply_crit_effects`), and the copy's exchange
    with our fleet (`_exchange`: its speed, turns, shields and guns as the
    engine reads them) is compared with the ship's without that crit type, at
    each of its shooting phases up to CRIT_HORIZON and the turn limit, x the
    chance the crit is still unrepaired then (`p_crit_unrepaired`; several hits
    of one type: the system is down until every one is repaired, so one more
    on a ship that already has it counts only where the others get repaired),
    x `phase_weight`. Leadership losses (Bridge Smashed -3, Necron losses,
    Infinity Circuit, Control Circuit) are valued by the Brace they cost: the
    drop in its pass chance x half our fire on it that phase past what bracing
    costs it (half its fire). A crit that kills the commander adds the
    commander's VPs (`victory_points.commander_points`), scored outright.
    The special orders a lower Ld fails are counted (`_order_loss`); not counted: the commander's re-rolls'
    later use."""
    cache = gs.__dict__.setdefault("_crit_effect_cache", {})
    key = (gs.turn_number, gs.current_phase, gs.active_player, ct, owner, end_phases, count,
           tuple(sorted((s.id, round(s.x, 1), round(s.y, 1), round(s.heading or 0), s.hits_remaining,
                         len(s.critical_damage), s.status, s.leadership)
                        for s in gs.get_ships())), target.id, target.hits_remaining,
           len(target.critical_damage), target.leadership)
    if key in cache:
        return cache[key]
    if len(cache) > 4000:
        cache.clear()
    val = _crit_effect_value(target, ct, gs, owner, end_phases, count)
    cache[key] = val
    return val


def _crit_effect_value(target: Ship, ct: str, gs: GameState, owner: int,
                       end_phases: int, count: int) -> float:
    from .ai_hazards import phase_weight
    from .combat import apply_crit_effects
    from .models import ship_copy, COMMAND_CRITS
    entry = _crit_entry(target, ct)
    clean = ship_copy(target, critical_damage=[c for c in target.critical_damage
                                               if c.get("crit_type") != ct])
    hit = ship_copy(clean, critical_damage=list(clean.critical_damage)
                    + [dict(entry, crit_type=ct)],
                    special_rules=list(clean.special_rules))
    try:
        apply_crit_effects(hit, dict(entry, crit_type=ct), _QuietState(gs))
    except Exception:
        pass
    old = sum(1 for c in target.critical_damage if c.get("crit_type") == ct)
    phases = end_phases or _end_phases_before_target_shoots(target, gs)
    ref = target.effective_speed or 0
    ref = max(ref, clean.effective_speed or 0)
    total = 0.0
    repairable = bool(entry.get("repairable", True))
    for j in range(_crit_shooting_phases(target, gs, phases)):
        if repairable:
            # the system stays down until all its crits are repaired: what the
            # new ones add to that chance (exact, p_system_down)
            oth = max(0, sum(1 for c in target.critical_damage if c.get("repairable")) - old)
            t_ph = phases + 2 * j
            weight = (p_system_down(target, gs, t_ph, old + max(1, count), oth)
                      - p_system_down(target, gs, t_ph, old, oth))
        else:
            weight = 0.0 if old else 1.0
        if weight < 0.005:
            continue
        n0, _t0, fire0 = _exchange(clean, gs, owner, j, phases, ref)
        n1, t1, _f1 = _exchange(hit, gs, owner, j, phases, ref)
        delta = max(0.0, n0 - n1)
        if hit.leadership < clean.leadership:
            dp = _brace_pass(clean.leadership) - _brace_pass(hit.leadership)
            delta += dp * max(0.0, 0.5 * fire0 - 0.5 * t1)
            # ... and the special order it would take that turn passes less
            # often (owner, To do 33): the order's worth x the drop in its
            # pass chance, by the AI's own order choice (ai_player.next_order)
            delta += _order_loss(clean, hit, gs)
        total += phase_weight(2 * j) * weight * delta
    if ct in COMMAND_CRITS and "commander_slain" not in target.special_rules:
        from .victory_points import commander_points
        total += commander_points(target)
    return total


def _order_loss(clean: Ship, hit: Ship, gs: GameState) -> float:
    """VP the lower Leadership of `hit` costs the ship's next special order:
    the order's gain x (pass chance at the old Ld - at the new one)."""
    try:
        from .ai_player import next_order, order_reader
        order, g, _p = next_order(gs, clean)
        if not order or g <= 0:
            return 0.0
        ai = order_reader(gs, clean.player)
        return max(0.0, g * (ai._pass_chance(clean, order) - ai._pass_chance(hit, order)))
    except Exception:
        return 0.0


class _QuietState:
    """A game state stand-in for applying a crit to a copy: no log."""
    def __init__(self, gs):
        self._gs = gs

    def add_log(self, *a, **k):
        pass

    def __getattr__(self, name):
        return getattr(self._gs, name)


# Expected hits per die / strength point when valuing a silenced weapon
# (batteries: ai_hazards.BATTERY_HITS_PER_FP, the Gunnery table's average, To do 30)
_THREAT_PER_DIE = {"lance": 0.5, "battery": 0.176, "torpedo": 0.3}
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
    if raid_has_no_effect(effective, target):
        return 0.0
    if not uses_crit_table(target):
        # 1 damage: the ship if it destroys it, else what it adds to finishing
        # it off later (ai_hazards.escort_hits_vp, owner)
        from .ai_hazards import escort_hits_vp
        return max(1.0, escort_hits_vp(target, gs, 1))
    ct = raid_crit_preview(effective, target)
    if ct is None:
        return 0.0
    return crit_type_value(ct, target, gs, owner, end_phases)


def crit_type_value(ct: str, target: Ship, gs: GameState, owner: int,
                    end_phases: int = None) -> float:
    """Expected VP of one critical hit of type `ct` on a crit-table target:
    its extra damage plus its effect (raid_result_value's crit part)."""
    from .combat import ARMAMENT_CRIT_TYPES
    extra = _CRIT_EXTRA.get(ct, 0.0)
    # its extra damage as hull hits, the destroy / cripple thresholds included
    # (it used to be a flat hit each plus half the ship "if it may finish it")
    from .ai_hazards import hits_vp
    if ct == "bulkhead_collapse":
        # D6 extra damage: each roll's exact total (_CRIT_EXTRA's 3.5 is its mean)
        value = sum(hits_vp(target, gs, r) for r in range(1, 7)) / 6.0
    elif ct == "hull_breach":
        value = sum(hits_vp(target, gs, r) for r in range(1, 4)) / 3.0     # D3
    else:
        value = hits_vp(target, gs, int(round(extra))) if extra else 0.0
    if ct == "fire":
        # its burn over the end phases left, against the fires already
        # burning (ai_hazards.fire_value, exact)
        from .ai_hazards import fire_value
        value += fire_value(target, gs, 1)
    elif ct in ARMAMENT_CRIT_TYPES or ct in ("keel_armament", "thorax_armament"):
        # the weapons (and launch bays) it silences in that location
        value += armament_threat_value(target, ct, gs, owner, end_phases)
    elif ct in ("de_superstructure", "eldar_superstructure"):
        # a D6 each time it turns, 1-2 one damage (Appendix 3): the ship
        # either turns and risks it or holds straight as if it couldn't turn
        value += superstructure_value(target, ct, gs, owner, end_phases)
    else:
        # every other effect (speed, turns, shields, Leadership, the
        # commander) applied to a copy and measured (crit_effect_value)
        value += crit_effect_value(target, ct, gs, owner, end_phases)
    if ct in ("bridge_smashed", "commanders_slain", "infinity_circuit_smashed", "monument",
              "synapse_severed"):
        from .scenarios import admiral_bonus_vp
        value += admiral_bonus_vp(gs, target)       # Kill the Admiral: the admiral dies (update 62)
    return value


def boarding_crit_value(target: Ship, gs: GameState, owner: int,
                        inflicted_by_rules=None) -> float:
    """Expected VP, to `owner`, of one boarding critical hit on `target`, as
    `boarding._boarding_crit_check` rolls it (s.32): an escort takes 1 point of
    damage (`ai_hazards.escort_hits_vp`); any other ship a D6 on the raid
    critical table (at least 2) on its own table, after the cascade
    (`raid_crit_preview`, `crit_type_value`). When the crit is inflicted by a
    Dark Eldar ship: Haemonculi make it a Fire (`fire` by `crit_type_value`),
    and Pain Frenzy against a crippled ship (a Wych Cult: any capital ship)
    re-rolls a result worth less than a fresh roll (`dark_eldar.frenzy_raid_reroll`'s
    rule, the second roll standing). A winner's own crit has no
    `inflicted_by_rules`."""
    rules = list(inflicted_by_rules or [])
    if target.ship_type == "escort":
        from .ai_hazards import escort_hits_vp
        return escort_hits_vp(target, gs, 1)
    if "dark_eldar" in rules and "haemonculi" in rules:
        return crit_type_value("fire", target, gs, owner)
    vals = []
    for r in range(1, 7):
        ct = raid_crit_preview(max(2, r), target)
        vals.append(crit_type_value(ct, target, gs, owner) if ct else 0.0)
    mean = sum(vals) / 6.0
    from .dark_eldar import pain_frenzy_applies
    if pain_frenzy_applies(rules, target):
        return sum(max(v, mean) for v in vals) / 6.0
    return mean


def crit_roll_value(roll_2d6: int, target: Ship, gs: GameState, owner: int,
                    end_phases: int = None) -> float:
    """Expected VP of a critical hit rolled as `roll_2d6` (2-12) on the
    target's own table, after the cascade. A ship off the crit table (small
    escorts and defences) takes 1 damage instead."""
    if not uses_crit_table(target):
        from .ai_hazards import escort_hits_vp
        return max(1.0, escort_hits_vp(target, gs, 1))
    from .combat import _resolve_crit_cascade
    data = _resolve_crit_cascade(max(2, min(12, roll_2d6)), target, _SilentLog())
    if data is None:
        return 0.0
    return crit_type_value(data["crit_type"], target, gs, owner, end_phases)


_TWO_D6 = {n: sum(1 for a in range(1, 7) for b in range(1, 7) if a + b == n) / 36.0
           for n in range(2, 13)}


def critical_hit_value(target: Ship, gs: GameState, owner: int, end_phases: int = None,
                       reroll: bool = False) -> float:
    """Expected VP of one critical hit rolled on 2D6. `reroll`: a re-roll may
    be taken (Pain Frenzy against a crippled ship), kept when the first is
    worth more than a fresh roll on average."""
    vals = {n: crit_roll_value(n, target, gs, owner, end_phases) for n in _TWO_D6}
    mean = sum(_TWO_D6[n] * v for n, v in vals.items())
    if reroll:
        return sum(_TWO_D6[n] * max(v, mean) for n, v in vals.items())
    return mean


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
    from .tables import crit_table_for
    entry = crit_table_for(target).get(max(2, min(6, effective))) or {}
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

    from .dark_eldar import take_slaves, pain_frenzy_applies, frenzy_raid_reroll
    incubi = "incubi" in (attacker_rules or []) and preset_rolls is None
    if incubi:
        # Dark Eldar Incubi (Xenos p.5): each raid rolls 2D6 and applies the
        # better result; against a crippled ship both results (two raids),
        # which replaces Pain Frenzy's re-roll (reading: "crippled" as Pain
        # Frenzy counts it, so a Wych Cult's capital-ship rule applies too)
        owner = 3 - target.player
        if pain_frenzy_applies(attacker_rules, target):
            num_raids *= 2
            gs.add_log(f"  Incubi: both results apply against the crippled {target.name}")
        else:
            best_of = []
            for i in range(num_raids):
                pair = dice.roll_d6(2, f"Incubi raid {i + 1} on {target.name} (choose one)")
                best_of.append(max(pair, key=lambda r: (raid_result_value(r + mod, target, gs, owner), r)))
            preset_rolls = best_of
            gs.add_log(f"  Incubi choose {best_of}")
    elif reroll_fn is None and pain_frenzy_applies(attacker_rules, target):
        # Dark Eldar Pain Frenzy (Xenos p.4): may re-roll a raid on a crippled ship
        def reroll_fn(roll, effective, tgt, _owner=3 - target.player):
            return frenzy_raid_reroll(gs, _owner, roll, effective, tgt)
    for i in range(num_raids):
        # Dark Eldar slave-taking (Xenos p.4): forgo the raid for +5 VP
        if take_slaves(gs, attacker_rules or [], target, brace_passed, dice, 5):
            continue
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

    # Necron Escalating Threat: a hit-and-run raid on any Necron vessel,
    # escorts included, raises the alert level (update 59; reading: each raid
    # that takes effect, max 5)
    landed = summary["damage"] + len(summary["crits_applied"])
    if landed and "necron" in target.special_rules:
        from .necrons import MAX_ALERT
        al = dict(getattr(gs, "necron_alert", None) or {})
        key = str(target.player)
        al[key] = min(MAX_ALERT, al.get(key, 1) + landed)
        gs.necron_alert = al
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
    # Dark Eldar shadowfields (Xenos p.5): a save against raids by ordnance
    from .dark_eldar import shadowfield_saves, resolve_impaler
    if "impaler" in (marker.special_rules or []):
        summary = resolve_impaler(marker, target, brace_passed, dice, gs)
        summary["brace_wanted"] = wanted_brace
        summary["brace_passed"] = brace_passed
        from .ordnance import end_ordnance_attack
        end_ordnance_attack(target, gs)
        return summary
    if shadowfield_saves(dice, target, num_raids, "the raid"):
        gs.add_log(f"  {target.name} shadowfield: the raid fails to find its target")
        from .ordnance import end_ordnance_attack
        end_ordnance_attack(target, gs)
        return {"raid_rolls": [], "failures": 0, "repelled": 0, "crits_applied": [],
                "damage": 0, "shadowfield_saved": 1, "brace_wanted": wanted_brace,
                "brace_passed": brace_passed}
    summary = resolve_raids(num_raids, target, brace_passed, dice, gs,
                            source_name=marker.ordnance_type,
                            attacker_rules=list(marker.special_rules or []) + [ASSAULT_BOAT_RAID],
                            reroll_fn=wings_reroll if wings else None)
    summary["brace_wanted"] = wanted_brace
    summary["brace_passed"] = brace_passed
    from .ordnance import end_ordnance_attack
    end_ordnance_attack(target, gs)          # Promethean turret halving used up
    return summary


@_rec.logged("teleport", lambda r, A: (A["gs"], dict(
    ship=A["attacker"].id, target=A["target"].id, result=r)))
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
