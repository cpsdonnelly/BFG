"""The AI list builder (To do 24) and its log of random choices (To do 31).

Builds a fleet from a fleet list for a points limit with a personality
(owner design): carrier heavy, cruiser heavy, light cruiser heavy, escort
heavy, battlecruiser / heavy cruiser heavy, grand cruiser heavy, battleship
heavy, or one picked at random. A personality the list can't do (carriers in
Bakka) is detected and another chosen.

  1. Personalities with a standout ship (carrier, battleship, grand cruiser
     heavy) take the biggest such ship the list allows first.
  2. A second personality roll for the rest, the first one likelier than
     chance (SECOND_SAME 0.4, owner's example).
  3. Escorts: 2D3 or as many as the points allow, whichever is smaller, of at
     most two classes, squadroned by class (escort heavy: as many as fit).
  4. The rest of the points on ships, weighted to the personality ("<class>
     heavy": as many of that class as possible).
  5. Required options (Kabal Variants, Eldar / Tyranid weapon choices) chosen
     as each ship is added; the fleet commander the list requires (on the
     dearest capital ship); spare points on random options.
  6. Every fleet-list rule checked (`fleet_model.validate_fleet`); a fleet
     that breaks one is repaired (ships added or dropped, a local search on
     the number of problems) or started again.

Every random decision goes into the log (`choices`), with what it chose from,
so a learned AI (To do 12, kept separate) can study them later. Reserves and
detachments aren't used yet; deployment (squadron formations) is To do 28."""
import random
from typing import Callable, Dict, List, Optional, Tuple

from .fleet_model import (make_fleet_row, fleet_total, validate_fleet, fleet_data,
                          list_catalog, reprice_row)

# The chance the second personality roll repeats the first (owner: "e.g. 40%")
SECOND_SAME = 0.4
# Weight of a ship matching the personality in the fill (others 1; judgement)
PERSONALITY_WEIGHT = 4.0
HEAVY_WEIGHT = 8.0
ATTEMPTS = 6
REPAIR_STEPS = 40


def ship_size(entry) -> str:
    """battleship, grand_cruiser, heavy_cruiser (battlecruisers and heavy
    cruisers), light_cruiser, cruiser, escort or defense."""
    name = entry.ship_class.lower()
    t = entry.ship_type
    if t == "defense":
        return "defense"
    if t == "escort":
        return "escort"
    if t == "battleship":
        return "battleship"
    if "grand cruiser" in name:
        return "grand_cruiser"
    if "battlecruiser" in name or "battle cruiser" in name or "heavy cruiser" in name:
        return "heavy_cruiser"
    if "light cruiser" in name:
        return "light_cruiser"
    return "cruiser"


def ship_roles(entry) -> set:
    """What the ship is armed with (owner: ships categorised by armament):
    carrier, torpedoes, nova_cannon, lances, batteries, long_guns (45cm+)."""
    roles = set()
    for w in entry.weapons:
        wt = w.get("weapon_type")
        if wt == "launch_bay":
            roles.add("carrier")
        elif wt == "torpedo":
            roles.add("torpedoes")
        elif wt == "nova_cannon":
            roles.add("nova_cannon")
        elif wt in ("lance", "battery"):
            roles.add("lances" if wt == "lance" else "batteries")
            if (w.get("range_cm") or 0) >= 45:
                roles.add("long_guns")
    return roles


def _is(size: str) -> Callable:
    return lambda e: ship_size(e) == size


PERSONALITIES: Dict[str, Callable] = {
    "carrier": lambda e: "carrier" in ship_roles(e) and ship_size(e) != "escort",
    "cruiser": _is("cruiser"),
    "light_cruiser": _is("light_cruiser"),
    "escort": _is("escort"),
    "heavy_cruiser": _is("heavy_cruiser"),
    "grand_cruiser": _is("grand_cruiser"),
    "battleship": _is("battleship"),
}
# Personalities built round one big ship first
STANDOUT = ("carrier", "battleship", "grand_cruiser")
# "<class> heavy": as many of that class as possible
HEAVY = ("cruiser", "light_cruiser", "escort", "heavy_cruiser")


class ListBuilder:
    def __init__(self, list_key: str, points: int, personality: Optional[str] = None,
                 seed: Optional[int] = None, rng: Optional[random.Random] = None):
        from .fleet_lists import LISTS, option_allowed
        self.fl = LISTS[list_key]
        self.list_key = list_key
        self.points = points
        self.wanted = personality
        self.rng = rng or random.Random(seed)
        self.choices: List[dict] = []
        self._allowed = lambda name: option_allowed(name, [list_key])
        self.catalog = [(e, key, cost) for e, key, cost, _sec in list_catalog(list_key)
                        if e is not None and not key.startswith("reserve:")
                        and e.playable and e.ship_type != "defense"
                        and "immobile" not in e.special_rules]
        self.personality = ""
        self.second = ""

    # ── the log (To do 31) ──────────────────────────────────────────────
    def _choose(self, what: str, options: list, weights: Optional[list] = None,
                label=lambda o: o):
        """A random choice, logged with what it was chosen from."""
        if not options:
            return None
        pick = (self.rng.choices(options, weights=weights, k=1)[0] if weights
                else self.rng.choice(options))
        self.choices.append({"what": what, "options": [label(o) for o in options],
                             **({"weights": [round(w, 3) for w in weights]} if weights else {}),
                             "chose": label(pick)})
        return pick

    def _roll(self, what: str, dice: int) -> int:
        v = sum(self.rng.randint(1, 3) for _ in range(dice))
        self.choices.append({"what": what, "roll": f"{dice}D3", "result": v})
        return v

    # ── ships ───────────────────────────────────────────────────────────
    def _options(self, entry) -> list:
        from .ship_catalog import get_upgrades_for_ship
        return [u for u in get_upgrades_for_ship(entry) if self._allowed(u.name)]

    def _row(self, entry, key: str, cost: int) -> dict:
        """A row with one option of each required group chosen at random."""
        opts = self._options(entry)
        groups: Dict[str, list] = {}
        for u in opts:
            for r in u.restrictions:
                if r.startswith("required_group:"):
                    groups.setdefault(r.split(":", 1)[1], []).append(u)
        ups = []
        for g, us in sorted(groups.items()):
            u = self._choose(f"{entry.ship_class}: {g}", us, label=lambda u: u.name)
            ups.append(u.name)
        # Tyranid configurations: a required weapon per slot (tyranids.config_errors)
        return make_fleet_row(entry, upgrades=ups, list_key=key, base_cost=cost)

    def _total(self, rows) -> int:
        return fleet_total(rows)

    def _errors(self, rows) -> List[str]:
        return validate_fleet(rows, self.list_key, "", self.points)

    def _fits(self, rows, row) -> bool:
        return self._total(rows + [row]) <= self.points - self._reserve(rows + [row])

    def _reserve(self, rows) -> int:
        """Points kept for the fleet commander the list will require."""
        cmd = self.fl.get("commander") or {}
        if not cmd or self._has_commander(rows):
            return 0
        if (cmd.get("required_at") or 0) > self.points:
            return 0
        costs = [u.points_cost for e, _k, _c in self.catalog for u in self._options(e)
                 if u.name in cmd.get("options", [])]
        return min(costs) if costs else 0

    def _has_commander(self, rows) -> bool:
        names = set((self.fl.get("commander") or {}).get("options", []))
        return any(names & set(r["upgrades"]) for r in rows)

    # ── personality ─────────────────────────────────────────────────────
    def _possible(self, p: str) -> bool:
        return any(PERSONALITIES[p](e) and c <= self.points for e, _k, c in self.catalog)

    def _pick_personality(self) -> str:
        names = list(PERSONALITIES)
        if self.wanted and self.wanted != "random":
            if self._possible(self.wanted):
                return self.wanted
            self.choices.append({"what": "personality", "unavailable": self.wanted})
        names = [n for n in names if self._possible(n)]
        return self._choose("personality", names) or "cruiser"

    # ── building ────────────────────────────────────────────────────────
    def _add_standout(self, rows):
        p = self.personality
        if p not in STANDOUT:
            return
        fits = [(e, k, c) for e, k, c in self.catalog if PERSONALITIES[p](e)]
        fits = [t for t in fits if self._fits(rows, self._row_quiet(*t))]
        if fits:
            top = max(c for _e, _k, c in fits)
            biggest = [t for t in fits if t[2] == top]
            e, k, c = self._choose(f"standout {p}", biggest, label=lambda t: t[0].ship_class)
            rows.append(self._row(e, k, c))

    def _row_quiet(self, e, k, c) -> dict:
        """A row priced with its cheapest required options, for fit checks
        (no choice logged)."""
        opts = self._options(e)
        groups: Dict[str, int] = {}
        for u in opts:
            for r in u.restrictions:
                if r.startswith("required_group:"):
                    g = r.split(":", 1)[1]
                    groups[g] = min(groups.get(g, 10 ** 6), u.points_cost)
        row = make_fleet_row(e, list_key=k, base_cost=c)
        row["points"] += sum(groups.values())
        return row

    def _add_escorts(self, rows):
        escorts = [t for t in self.catalog if ship_size(t[0]) == "escort"]
        if not escorts:
            return
        classes = self._choose("escort classes (count)", [1, 2] if len(escorts) > 1 else [1])
        picked = []
        pool = list(escorts)
        for i in range(classes):
            t = self._choose("escort class", pool, label=lambda t: t[0].ship_class)
            picked.append(t)
            pool.remove(t)
        heavy = self.personality == "escort" or self.second == "escort"
        n = 99 if heavy else self._roll("escorts", 2)
        added = 0
        while added < n:
            t = picked[added % len(picked)]
            row = self._row(*t)
            if not self._fits(rows, row):
                alt = [p for p in picked if self._fits(rows, self._row_quiet(*p))]
                if not alt:
                    break
                row = self._row(*alt[0])
            rows.append(row)
            added += 1

    def _weight(self, e) -> float:
        w = 1.0
        for p, mult in ((self.personality, PERSONALITY_WEIGHT), (self.second, PERSONALITY_WEIGHT)):
            if p and PERSONALITIES[p](e):
                w *= HEAVY_WEIGHT if p in HEAVY else mult
        return w

    def _fill(self, rows):
        while True:
            fits = [t for t in self.catalog if self._fits(rows, self._row_quiet(*t))]
            if not fits:
                return
            t = self._choose("ship", fits, [self._weight(t[0]) for t in fits],
                             label=lambda t: t[0].ship_class)
            rows.append(self._row(*t))

    def _add_commander(self, rows):
        cmd = self.fl.get("commander") or {}
        if not cmd or self._has_commander(rows) or (cmd.get("required_at") or 0) > self.points:
            return
        names = set(cmd.get("options", []))
        spare = self.points - self._total(rows)
        caps = sorted([r for r in rows if r["entry"].ship_type != "escort"],
                      key=lambda r: -r["points"])
        for r in caps:               # the dearest capital ship that can take one
            opts = [u for u in self._options(r["entry"]) if u.name in names
                    and u.points_cost <= spare]
            if opts:
                u = self._choose("fleet commander", opts, label=lambda u: u.name)
                r["upgrades"].append(u.name)
                r["is_flagship"] = True
                reprice_row(r)
                self.choices.append({"what": "commander's ship", "chose": r["entry"].ship_class,
                                     "rule": "dearest capital ship"})
                return

    def _spend_spare(self, rows):
        """Random options with the points left, kept only if the fleet is no
        worse for them."""
        base = len(self._errors(rows))
        for _ in range(12):
            spare = self.points - self._total(rows)
            cands = [(r, u) for r in rows for u in self._options(r["entry"])
                     if u.name not in r["upgrades"] and 0 < u.points_cost <= spare
                     and not any(x.startswith("required_group:") for x in u.restrictions)
                     and not any(x == "group:fleet_commander" for x in u.restrictions)]
            if not cands:
                return
            r, u = self._choose("option", cands, label=lambda t: f"{t[0]['entry'].ship_class}: {t[1].name}")
            r["upgrades"].append(u.name)
            reprice_row(r)
            if len(self._errors(rows)) > base or self._total(rows) > self.points:
                r["upgrades"].remove(u.name)
                reprice_row(r)
                self.choices[-1]["kept"] = False

    def _squadrons(self, rows):
        """Escorts of one class squadroned together, 2-6 a squadron, split as
        evenly as possible (owner: one class per squadron)."""
        by: Dict[str, list] = {}
        for r in rows:
            r["squadron_id"] = ""
            if r["entry"].ship_type == "escort":
                by.setdefault(r["entry"].ship_class, []).append(r)
        n = 0
        for cls, members in by.items():
            if len(members) < 2:
                continue
            k = -(-len(members) // 6)
            for i, r in enumerate(members):
                r["squadron_id"] = f"sq{n + i % k + 1}"
            n += k

    def _repair(self, rows) -> List[str]:
        """Local search on the fleet's problems: try random additions and
        removals, keep the best that leaves fewer problems (then less unused
        points)."""
        errs = self._errors(rows)
        for _ in range(REPAIR_STEPS):
            if not errs:
                return errs
            best = None
            for _try in range(10):
                trial = [dict(r, upgrades=list(r["upgrades"])) for r in rows]
                if self.rng.random() < 0.5 and trial:
                    victims = [r for r in trial if not r["is_flagship"]] or trial
                    trial.remove(self.rng.choice(victims))
                else:
                    fits = [t for t in self.catalog
                            if self._total(trial + [self._row_quiet(*t)]) <= self.points]
                    if not fits:
                        continue
                    t = self.rng.choice(fits)
                    trial.append(self._row_quiet_logged(t))
                self._add_commander(trial)
                self._squadrons(trial)
                e = self._errors(trial)
                score = (len(e), self.points - self._total(trial))
                if best is None or score < best[0]:
                    best = (score, trial, e)
            if best is None or best[0][0] > len(errs):
                break                     # nothing tried helps: start again
            rows[:] = best[1]
            errs = best[2]
            self.choices.append({"what": "repair", "problems_left": len(errs)})
        return errs

    def _row_quiet_logged(self, t) -> dict:
        e, k, c = t
        self.choices.append({"what": "repair: add", "chose": e.ship_class})
        return self._row(e, k, c)

    def build(self) -> Tuple[List[dict], List[str]]:
        """(rows, problems): the best fleet over ATTEMPTS tries ([] problems
        when it keeps every rule)."""
        best = None
        for attempt in range(ATTEMPTS):
            self.choices.append({"what": "attempt", "n": attempt + 1})
            rows: List[dict] = []
            self.personality = self._pick_personality()
            same = self.rng.random() < SECOND_SAME
            self.second = (self.personality if same else
                           self._choose("second personality",
                                        [p for p in PERSONALITIES if self._possible(p)]))
            self.choices.append({"what": "second personality", "same_roll": same,
                                 "chose": self.second})
            self._add_standout(rows)
            self._add_escorts(rows)
            self._fill(rows)
            self._add_commander(rows)
            self._squadrons(rows)
            errs = self._repair(rows)
            if not errs:
                self._spend_spare(rows)
                self._squadrons(rows)
                errs = self._errors(rows)
            if best is None or len(errs) < len(best[1]):
                best = (rows, errs)
            if not errs:
                break
        return best


def build_random_fleet(list_key: str, points: int, personality: Optional[str] = None,
                       seed: Optional[int] = None, name: str = "") -> dict:
    """A random fleet's file contents (`fleet_loader` reads it like any saved
    fleet), with "personality", "problems" (empty when valid) and
    "random_choices" (the log, To do 31)."""
    from .fleet_lists import LISTS
    b = ListBuilder(list_key, points, personality, seed)
    rows, problems = b.build()
    fl = LISTS[list_key]
    data = fleet_data(rows, fl["faction"], list_key, "",
                      name or f"Random {b.personality.replace('_', ' ')} {points}", points,
                      f"Built by the AI list builder: {b.personality} heavy "
                      f"(then {b.second}), seed {seed}.")
    data["personality"] = b.personality
    data["problems"] = problems
    data["random_choices"] = b.choices
    return data
