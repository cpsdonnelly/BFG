"""Alternate activation (AA), an optional ruleset outside the booklet (CLAUDE.md
To do 13; docs/AA_ORDER_SYSTEMS_NOTES.md is the source). This module is the
activation-order core, shared by the three systems, with no game-flow wiring
yet: units and their initiative, fleet means, the gap and the edge holder, the
System 3 band table, the bag (Systems 2 and 3), the System 1 fixed order, and
the edge-share formula from the notes (reproduced by the tests).

Everything the owner hasn't settled is configurable (`AAConfig`)."""
from dataclasses import dataclass, field
from functools import lru_cache
import math
import random
from typing import Dict, List, Optional, Tuple

ORDER_MODES = ("fixed_initiative", "bag", "bag_adjusted")
RECOMPUTE = ("start_only", "on_unit_destroyed", "abfg_turn_start")


@dataclass
class AAConfig:
    order_mode: str = "bag_adjusted"            # System 3 is the default (owner)
    capital_squadrons_as_one: bool = False      # notes' numbers assume separate units
    recompute: str = "start_only"
    allow_pass: bool = True                     # proposed, not yet confirmed
    allow_forcing: bool = False                 # System 1's optional forcing (ABFG)
    # System 3 band table: (gap at least, choice, extra dice divisor or None)
    bands: List[Tuple[float, bool, Optional[int]]] = field(default_factory=lambda: [
        (0.5, True, None), (1.5, True, 3), (3.0, True, 2)])


@dataclass
class Unit:
    player: int
    ship_ids: List[str]
    ld: int
    starting_hits: int
    crippled: int = 0

    @property
    def key(self) -> str:
        return self.ship_ids[0]


def units(gs, player: int, cfg: AAConfig = None) -> List[Unit]:
    """A capital ship is a unit; an escort squadron is one unit (its one Ld,
    the sum of its ships' starting hits). Capital squadrons are separate units
    unless `capital_squadrons_as_one` (ABFG: one unit with the highest Ld and
    the highest hits, possibly from different ships)."""
    cfg = cfg or AAConfig()
    ships = [s for s in gs.get_ships() if s.player == player
             and not s.is_destroyed and not s.is_disengaged]
    groups: Dict[str, List] = {}
    out = []
    for s in ships:
        if s.squadron_id and (s.ship_type == "escort" or cfg.capital_squadrons_as_one):
            groups.setdefault(s.squadron_id, []).append(s)
        else:
            out.append(Unit(player, [s.id], s.leadership, s.hits_max, int(s.is_crippled)))
    for members in groups.values():
        if members[0].ship_type == "escort":
            out.append(Unit(player, [m.id for m in members], max(m.leadership for m in members),
                            sum(m.hits_max for m in members),
                            sum(int(m.is_crippled) for m in members)))
        else:
            out.append(Unit(player, [m.id for m in members], max(m.leadership for m in members),
                            max(m.hits_max for m in members),
                            sum(int(m.is_crippled) for m in members)))
    return out


def initiative(u: Unit, abfg: bool = False) -> int:
    """Ld - starting hits + 10 (never current hits); ABFG's turn-start
    recompute also takes 1 per crippled ship."""
    return u.ld - u.starting_hits + 10 - (u.crippled if abfg else 0)


def fleet_mean(us: List[Unit], abfg: bool = False) -> float:
    if not us:
        return 0.0
    return round(sum(initiative(u, abfg) for u in us) / len(us), 1)


def edge(gs, cfg: AAConfig = None) -> Tuple[Optional[int], float]:
    """(edge holder or None, gap) between the fleets' mean initiatives."""
    cfg = cfg or AAConfig()
    abfg = cfg.recompute == "abfg_turn_start"
    m1 = fleet_mean(units(gs, 1, cfg), abfg)
    m2 = fleet_mean(units(gs, 2, cfg), abfg)
    gap = round(abs(m1 - m2), 1)
    if gap == 0:
        return None, 0.0
    return (1 if m1 > m2 else 2), gap


def band(gap: float, n_units: int, cfg: AAConfig = None) -> Tuple[bool, int]:
    """System 3: (the edge holder chooses the first side, extra dice) for a
    gap; extra dice = ceil(its own units / divisor)."""
    cfg = cfg or AAConfig()
    choice, extra = False, 0
    for at_least, ch, div in sorted(cfg.bands):
        if gap >= at_least:
            choice = ch
            extra = math.ceil(n_units / div) if div else 0
    return choice, extra


@lru_cache(maxsize=None)
def pairs(e: int, k: int, i: int) -> float:
    """Expected (edge unit, opponent unit) pairs in which the edge unit acts
    first, with e edge units and k extra dice against i units (the notes'
    exact formula)."""
    if e == 0 or i == 0:
        return 0.0
    n = e + k + i
    return (e + k) / n * (i + pairs(e - 1, k, i)) + i / n * pairs(e, k, i - 1)


def edge_share(n_e: int, n_i: int, k: int = 0, choice: bool = False) -> float:
    """2P - 1, P the mean P(edge unit first) over all pairs; with the choice
    the edge holder goes first with its die removed."""
    if choice:
        p = (n_i + pairs(n_e - 1, k, n_i)) / (n_e * n_i)
    else:
        p = pairs(n_e, k, n_i) / (n_e * n_i)
    return 2 * p - 1


class Bag:
    """One phase's bag (Systems 2 and 3): a die per unit that can act this
    phase, plus the edge holder's extra dice in its colour. Every activation
    spends one of that side's dice; a side with all its units done ignores its
    further draws; a side may pass while it has more dice than units left
    (`allow_pass`)."""

    def __init__(self, n_units: Dict[int, int], extra: Dict[int, int] = None,
                 allow_pass: bool = True, rng: random.Random = None):
        extra = extra or {}
        self.left = dict(n_units)                         # units still to act
        self.dice = {p: n + extra.get(p, 0) for p, n in n_units.items()}
        self.allow_pass = allow_pass
        self.rng = rng or random.Random()

    def empty(self) -> bool:
        return sum(self.dice.values()) == 0

    def take_first(self, player: int) -> None:
        """The System 3 choice: `player` acts without a draw, spending a die."""
        self._spend(player)

    def draw(self) -> int:
        """Draw a die at random; returns its side (the die is removed)."""
        total = sum(self.dice.values())
        r = self.rng.randrange(total)
        for p, n in self.dice.items():
            if r < n:
                self.dice[p] -= 1
                return p
            r -= n
        raise RuntimeError("empty bag")

    def can_pass(self, player: int) -> bool:
        return self.allow_pass and self.dice[player] + 1 > self.left[player]

    def activate(self, player: int) -> bool:
        """After a draw of `player`'s colour: True if it activates a unit
        (False when it has none left)."""
        if self.left[player] <= 0:
            return False
        self.left[player] -= 1
        return True

    def _spend(self, player: int) -> None:
        if self.dice[player] > 0:
            self.dice[player] -= 1
        self.left[player] -= 1


def fixed_order(all_units: List[Unit], phase: str, admiral_ld: Dict[int, int] = None,
                rating: Dict[int, int] = None, rng: random.Random = None,
                abfg: bool = True) -> List[Unit]:
    """System 1 (ABFG v0.3): shooting in initiative order highest first,
    movement inverse; ties by Ld, then the admiral's Ld, then the fleet's
    strategy rating, then a dice-off."""
    rng = rng or random.Random()
    admiral_ld = admiral_ld or {}
    rating = rating or {}
    keyed = [(initiative(u, abfg), u.ld, admiral_ld.get(u.player, 0),
              rating.get(u.player, 0), rng.random(), u) for u in all_units]
    keyed.sort(key=lambda t: t[:5], reverse=True)
    out = [t[-1] for t in keyed]
    return list(reversed(out)) if phase == "movement" else out
