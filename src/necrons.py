"""Necron rules (bfgxr/rules/09_necrons.md, Xenos pp.38-51; CLAUDE.md To do 14),
pure logic. First slice, not wired into the catalog or game yet: reactive
hulls and Brace for Impact, Deadly Awakening (alert levels, awakening,
power conservation), the inertialess drive's All Ahead Full, and the Necron
weapons' core rules (nightmare field, star pulse generator, particle whip,
lightning arc, portals). Readings to confirm with the owner are marked
"reading"."""
import re
from typing import Iterable, List, Optional

# --- Reactive hulls -------------------------------------------------------------


def parse_reactive_hull(raw: str) -> Optional[int]:
    """'RH 4+' -> 4 (escorts 6+, cruisers 5+, battleships 4+ in the profiles)."""
    m = re.fullmatch(r"\s*RH\s*(\d)\s*\+\s*", raw or "")
    return int(m.group(1)) if m else None


def hull_save(base_save: int, braced: bool) -> int:
    """The reactive hull save, used wherever a Brace for Impact save could be
    (incl. against hit-and-run attacks); on Brace for Impact it improves to 2+
    (replacing Brace's usual 4+)."""
    return 2 if braced else base_save


def armour_when_braced(armour: int, braced: bool) -> int:
    """Brace for Impact compromises their stealth: Armour falls to 4+."""
    return 4 if braced else armour


HULK_ARMOUR = 4          # Without a Trace: Necron hulks have 4+ Armour

# Necrons ignore leadership, damage and movement penalties from solar flares,
# radiation, gas clouds and blast markers; they repair critical damage on 4+
REPAIR_ON = 4

# Orders a Necron ship may not use (no torpedoes, craft only for surface
# engagements): Reload Ordnance (the tomb complex excepted)
FORBIDDEN_ORDERS = ("reload_ordnance",)


def order_allowed(order: str, tomb_complex: bool = False) -> bool:
    return tomb_complex or order not in FORBIDDEN_ORDERS


# --- Deadly Awakening -----------------------------------------------------------
AWAKEN_LD = {1: 10, 2: 9, 3: 8, 4: 7, 5: 0}      # alert level -> Ld required
MAX_ALERT = 5


def starting_alert(enemy_points_on_table: int, necron_points_on_table: int,
                   hostile_specials: int = 0) -> int:
    """Alert level 1 (the author's confirmation), +2 if the opposing fleet
    starts with more points on the table, +1 per hostile Space Hulk, Proteus
    Hive Ship, Planet Killer or Activated Blackstone Fortress (reading: +1 each,
    capped at 5)."""
    lvl = 1
    if enemy_points_on_table > necron_points_on_table:
        lvl += 2
    return min(MAX_ALERT, lvl + max(0, hostile_specials))


class AlertTracker:
    """The fleet's alert level: +1 whenever an enemy ship or ordnance marker
    inflicts an unsaved hit (or hit-and-run raid) on a Necron vessel, max 5."""

    def __init__(self, level: int = 1):
        self.level = max(1, min(MAX_ALERT, level))

    def unsaved_hit(self, n: int = 1) -> None:
        self.level = min(MAX_ALERT, self.level + max(0, n))

    def ld_required(self) -> int:
        return AWAKEN_LD[self.level]

    def may_awaken(self, effective_ld: int) -> bool:
        """At the start of each Necron turn a capital ship whose Ld, with the
        modifiers that would apply to its command checks (e.g. Enemy Contacts),
        equals or exceeds the threshold may awaken."""
        return effective_ld >= self.ld_required()


def conserving_power(ship) -> bool:
    """Capital ships start conserving power: they act as if crippled for all
    game purposes except scoring, until they awaken. Reinforcements arriving
    after the first turn are always awakened."""
    rules = getattr(ship, "special_rules", None) or []
    return ("necron" in rules and getattr(ship, "ship_type", "") != "escort"
            and "necron_awake" not in rules)


def vp_multiplier(ship) -> float:
    """Awakened Necron capital ships are worth double VP (hulks included)."""
    rules = getattr(ship, "special_rules", None) or []
    return 2.0 if "necron_awake" in rules else 1.0


# --- Inertialess drive (All Ahead Full) ----------------------------------------


def inertialess_extra(d6: int) -> int:
    """All Ahead Full: D6 x 10cm more movement instead of the usual bonus."""
    return 10 * d6


def inertialess_turns(distance_cm: float) -> int:
    """...and a turn for every 20cm travelled (reading: full 20cm stretches)."""
    return int(distance_cm // 20)


# --- Weapons --------------------------------------------------------------------
FIELD_RANGE = 20.0          # nightmare field, star pulse generator
FIELD_ORDNANCE_KILL = 4     # markers within 20cm destroyed on 4+, each one


def field_usable(crippled: bool, order: str) -> bool:
    """Nightmare fields and star pulse generators: not while crippled (power
    conservation counts as crippled) or on any special order but Lock On."""
    return not crippled and order in ("", "none", "lock_on")


def nightmare_field(dice, target_ld: int) -> bool:
    """The target (capital ship or escort squadron within 20cm) takes a
    Leadership test; True when it fails: -1 Ld for the rest of the game and no
    special orders (Brace included) until after the end of its next turn."""
    return sum(dice.roll_d6(2, f"Nightmare field Ld test (Ld {target_ld})")) > target_ld


def field_ordnance_kills(dice, markers: Iterable, label: str) -> List:
    """Each enemy marker within 20cm (each of a wave's too) is destroyed on 4+;
    the nightmare field takes only attack craft and boarding torpedoes, the
    star pulse generator any ordnance (the caller filters). Returns the
    markers destroyed."""
    markers = list(markers)
    if not markers:
        return []
    rolls = dice.roll_d6(len(markers), f"{label}: ordnance within 20cm (4+ destroyed)")
    return [m for m, r in zip(markers, rolls) if r >= FIELD_ORDNANCE_KILL]


def star_pulse_hits(dice, armours: List[int]) -> List[bool]:
    """One roll to hit against the nearest Armour of each non-Necron ship
    within 20cm."""
    if not armours:
        return []
    rolls = dice.roll_d6(len(armours), "Star pulse generator")
    return [r >= a for r, a in zip(rolls, armours)]


def particle_whip(dice, strength: int, need: int = 4):
    """A lance whose 6s bypass shields (and holofields, shadowfields, anything
    but Brace). Returns (hits, bypassing hits)."""
    rolls = dice.roll_d6(strength, f"Particle whip ({need}+, 6s bypass shields)")
    return sum(1 for r in rolls if r >= need), sum(1 for r in rolls if r == 6)


LIGHTNING_ARC_ASPECT = "closing"      # all non-defence targets count as closing


def portal_strength(strength: int, halvings: int) -> int:
    """Portals are halved like direct fire (crippled, special orders) but round
    down, not up."""
    for _ in range(halvings):
        strength //= 2
    return strength


# Portals may be used against targets with more hits than the attacker, and
# while crippled or on special orders (unlike teleport attacks)
PORTAL_IGNORES_HITS_LIMIT = True
