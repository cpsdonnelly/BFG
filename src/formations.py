"""What staying together is worth, by armament (owner: Dark Eldar Impaler
escorts need to be in tight groups to overcome turrets, Firestorms and Swords
don't; it depends on the weapons, so it is priced, not a rule).

Two things base contact buys:
  - combined ordnance (s.15): squadron members in a contiguous chain of base
    contact may launch the same ordnance as one wave or salvo. A target's
    turrets fire once at each wave or salvo (s.25, s.28), each success removing
    one squadron (or torpedo) from the front, so one wave of n meets the dice
    once where n separate ones meet them n times: with K ~ Binomial(T, p) turret
    kills, E[max(0, n - K)] survive together against sum E[max(0, s_i - K)]
    apart. `combine_gain` is that difference times what one squadron (or
    torpedo) that gets through is worth, exact, not sampled. Gun-only ships
    have nothing to combine and gain nothing;
  - massed turrets (s.29): +1 turret per non-crippled friend in base contact,
    at most +3; worth something only while enemy torpedoes, bombers, assault
    boats or mines can reach the ship (`turret_value`).

The AI's move score (`AIPlayer._coherency_term`), squadron sizes at fleet
building (`squadrons._sizes`) and deployment formations (`ai_deployment`)
all read these."""
import math
from types import SimpleNamespace
from typing import List, Optional

KINDS = ("impaler", "craft", "torpedo")


def load(ship, kind: str) -> int:
    """How many squadrons (Impalers / other craft) or torpedoes the ship adds
    to a combined launch of that kind."""
    n = 0
    for w in ship.weapons or []:
        t = w.get("weapon_type")
        if kind == "torpedo" and t == "torpedo":
            n += int(w.get("strength") or 0)
        elif t == "launch_bay" and bool(w.get("impaler_bay")) == (kind == "impaler"):
            n += int(w.get("strength") or 0)
    return n


def kinds_of(ship) -> List[str]:
    return [k for k in KINDS if load(ship, k) > 0]


def survivors(n: int, dice: int, p: float) -> float:
    """E[max(0, n - K)], K ~ Binomial(dice, p): what is left of n after the
    turret roll."""
    if n <= 0:
        return 0.0
    total = 0.0
    for k in range(dice + 1):
        pk = math.comb(dice, k) * p ** k * (1 - p) ** (dice - k)
        total += pk * max(0, n - k)
    return total


def _turrets(launcher, kind: str, target, gs):
    """(turret dice, chance each removes one) the target fires at our ordnance."""
    from .ordnance import (ordnance_turrets, get_massed_turret_bonus, turret_hit_on,
                           turret_kill_p)
    marker = SimpleNamespace(special_rules=list(launcher.special_rules or []),
                             ordnance_type="torpedo_standard" if kind == "torpedo"
                             else "assault_boat")
    dice = ordnance_turrets(target, gs) + get_massed_turret_bonus(target, gs.get_ships())
    return dice, turret_kill_p(target, turret_hit_on(target, marker), gs)


def unit_value(launcher, kind: str, target, gs) -> float:
    """Expected VP of one squadron (or torpedo) that gets past the turrets."""
    from . import waves
    from .ai_hazards import hull_hits_vp, torpedo_p_hit
    if kind == "impaler":
        return waves.impaler_value(target, gs, launcher.player, launcher.special_rules, 1)
    if kind == "craft":
        return waves.bomber_squadron_value(target, gs)
    return torpedo_p_hit(target.lowest_armor_value, launcher.special_rules) * \
        hull_hits_vp(target, gs, 0.0, 1.0)


def combine_gain(launcher, kind: str, sizes: List[int], target, gs) -> float:
    """VP gained by launching these loads (squadrons / torpedoes each) as one
    wave or salvo instead of one each, against `target`'s turrets."""
    if target is None or len(sizes) < 2:
        return 0.0
    dice, p = _turrets(launcher, kind, target, gs)
    apart = sum(survivors(s, dice, p) for s in sizes)
    together = survivors(sum(sizes), dice, p)
    return max(0.0, together - apart) * unit_value(launcher, kind, target, gs)


def marginal_gain(launcher, kind: str, mates_load: int, target, gs) -> float:
    """What the launcher adds by joining a chain whose others carry
    `mates_load` of the same ordnance: their wave with it, against it apart."""
    own = load(launcher, kind)
    if not own or not mates_load or target is None:
        return 0.0
    dice, p = _turrets(launcher, kind, target, gs)
    gain = survivors(own + mates_load, dice, p) - survivors(own, dice, p) \
        - survivors(mates_load, dice, p)
    return max(0.0, gain) * unit_value(launcher, kind, target, gs)


def attacking_ordnance_near(ship_x: float, ship_y: float, player: int, gs) -> int:
    """Enemy torpedoes, mines, torpedo bombers, bombers and assault boats that
    can reach the point in their next ordnance phase (fighters don't attack
    ships; owner: no massing against them)."""
    from .ordnance import ATTACK_CRAFT_TYPES, attacks_ships
    n = 0
    for o in gs.ordnance:
        if o["owner_player"] == player or o.get("cap_ship_id"):
            continue
        kind = o["ordnance_type"]
        if not (kind.startswith("torpedo") or "mine" in kind
                or (kind in ATTACK_CRAFT_TYPES and attacks_ships(kind))):
            continue
        if math.hypot(o["x"] - ship_x, o["y"] - ship_y) <= (o.get("speed") or 20) * 2 + 10:
            n += 1
    return n


def turret_value(ship, x: float, y: float, gs, threats: Optional[int] = None) -> float:
    """VP one more turret is worth to the ship standing at (x, y): half a
    chance to stop each threat in reach (at most three), each worth a hit on
    its lowest Armour (as the commander's screen values it)."""
    from .ai_hazards import p_hit, value_per_hit
    if threats is None:
        threats = attacking_ordnance_near(x, y, ship.player, gs)
    if not threats:
        return 0.0
    return 0.5 * p_hit(ship.lowest_armor_value) * min(threats, 3) * \
        max(1.0, value_per_hit(ship, gs))


def needs_contact(ships: List, target, gs) -> bool:
    """Whether a squadron gains by keeping base contact: some kind of its
    ordnance gains by combining against the target's turrets."""
    for kind in KINDS:
        loads = [load(s, kind) for s in ships if load(s, kind)]
        if len(loads) >= 2 and combine_gain(ships[0], kind, loads, target, gs) > 0:
            return True
    return False
