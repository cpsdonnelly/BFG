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

    def _required(self, entry):
        """What a ship must choose: one option of each required group (Kabal
        Variants, Eldar weapon choices) and, for Tyranids, a number of weapons
        per location (`tyranids.slot_limits`, each option's `tyranid_slot:`
        count). Returns (groups {name: [options]}, slots {loc: (lo, hi,
        [(option, count)])})."""
        opts = self._options(entry)
        groups: Dict[str, list] = {}
        slots: Dict[str, tuple] = {}
        limits = {}
        if entry.faction == "tyranids":
            from .tyranids import slot_limits
            limits = slot_limits(entry.ship_class)
        for u in opts:
            for r in u.restrictions:
                if r.startswith("required_group:"):
                    groups.setdefault(r.split(":", 1)[1], []).append(u)
                elif r.startswith("tyranid_slot:"):
                    parts = r.split(":")
                    loc = parts[1]
                    if loc in limits:
                        lo, hi = limits[loc]
                        n = int(parts[2]) if len(parts) > 2 else 1
                        slots.setdefault(loc, (lo, hi, []))[2].append((u, n))
        return groups, slots

    def _row(self, entry, key: str, cost: int, log: bool = True) -> dict:
        """A row with its required choices made at random (redrawn until the
        ship's own option checks pass, up to 30 draws); logged once, as the
        options taken."""
        from .booklet_options import ship_option_errors
        groups, slots = self._required(entry)
        ups: List[str] = []
        for _try in range(30):
            ups = [self.rng.choice(us).name for _g, us in sorted(groups.items())]
            for loc, (lo, hi, options) in sorted(slots.items()):
                want = self.rng.randint(lo, hi) if hi > lo else lo
                got, tries = 0, 0
                while got < want and tries < 20:
                    tries += 1
                    u, n = self.rng.choice(options)
                    if got + n <= want and u.name not in ups:
                        ups.append(u.name)
                        got += n
            if not ship_option_errors(entry, ups):
                break
        if (groups or slots) and log:
            self.choices.append({"what": f"{entry.ship_class}: required choices",
                                 "chose": list(ups)})
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
        """A row priced with its cheapest required choices, for fit checks
        (no choice logged)."""
        groups, slots = self._required(e)
        row = make_fleet_row(e, list_key=k, base_cost=c)
        row["points"] += sum(min(u.points_cost for u in us) for us in groups.values())
        row["points"] += sum(lo * min(u.points_cost / max(1, n) for u, n in opts)
                             for lo, _hi, opts in slots.values() if opts)
        return row

    def _satisfy(self, rows):
        """The standout ship's requirements (owner: an Emperor needs three
        cruisers): capital ships added one at a time while one leaves fewer
        fleet-list problems (then a smaller shortfall), those matching the
        personality first; a carrier heavy fleet's supports are carriers when
        they do as well."""
        def score(trial):
            e = self._errors(trial)
            return (len(e), sum(_shortfall(x) for x in e))
        cur = score(rows)
        for _ in range(8):
            if cur[0] == 0:
                return
            best = None
            for t in self.catalog:
                if ship_size(t[0]) == "escort":
                    continue
                for k in (1, 2, 3):           # "one per 3 cruisers": one alone shows nothing
                    if self._total(rows) + k * self._row_quiet(*t)["points"] > \
                            self.points - self._reserve(rows):
                        break
                    trial = rows + [self._row(*t, log=False) for _ in range(k)]
                    sc = score(trial) + (k, -self._weight(t[0]))
                    if best is None or sc < best[0]:
                        best = (sc, t, k)
            if best is None or best[0][:2] >= cur:
                return
            for _ in range(best[2]):
                rows.append(self._row(*best[1]))
            self.choices.append({"what": "requirement", "chose": best[1][0].ship_class,
                                 "count": best[2]})
            cur = best[0][:2]

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

    def _fill(self, rows, quiet: bool = False, exclude: str = ""):
        """Ships at random, weighted to the personality, while any fits.
        quiet: a repair trial (nothing logged); exclude: a class not to add."""
        # escorts come from _add_escorts (2D3 of at most two classes, owner),
        # unless the fleet is escort heavy
        heavy = "escort" in (self.personality, self.second)
        while True:
            fits = [t for t in self.catalog if t[0].ship_class != exclude
                    and (heavy or ship_size(t[0]) != "escort")
                    and self._fits(rows, self._row_quiet(*t))]
            if not fits:
                return
            weights = [self._weight(t[0]) for t in fits]
            if quiet:
                t = self.rng.choices(fits, weights=weights, k=1)[0]
            else:
                t = self._choose("ship", fits, weights, label=lambda t: t[0].ship_class)
            rows.append(self._row(*t, log=not quiet))

    def _add_commander(self, rows, log: bool = True):
        cmd = self.fl.get("commander") or {}
        if not cmd or self._has_commander(rows) or (cmd.get("required_at") or 0) > self.points:
            return
        names = set(cmd.get("options", []))
        spare = self.points - self._total(rows)
        caps = sorted([r for r in rows if r["entry"].ship_type != "escort"],
                      key=lambda r: -r["points"])
        from .fleet_lists import commander_placement_errors

        def placed_ok(r, name):
            trial = [dict(x, upgrades=list(x["upgrades"]) + ([name] if x is r else []))
                     for x in rows]
            return not commander_placement_errors(self.list_key, trial)
        for r in caps:               # the dearest capital ship the list allows (To do 29)
            opts = [u for u in self._options(r["entry"]) if u.name in names
                    and u.points_cost <= spare and placed_ok(r, u.name)]
            if opts:
                if log:
                    u = self._choose("fleet commander", opts, label=lambda u: u.name)
                    self.choices.append({"what": "commander's ship",
                                         "chose": r["entry"].ship_class,
                                         "rule": "dearest capital ship"})
                else:
                    u = self.rng.choice(opts)
                r["upgrades"].append(u.name)
                r["is_flagship"] = True
                reprice_row(r)
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
        """Escorts squadroned within the list's rules (`squadrons.
        organize_escorts`: one class and set-up to a squadron, owner, 2D3
        a squadron, Tyranid weapons matching; mixed where the list allows it
        or a repair needs it). The sizes come from one draw per build, so
        every trial in the repair is squadroned alike."""
        from .squadrons import organize_escorts
        if not hasattr(self, "_sq_seed"):
            self._sq_seed = self.rng.randrange(1 << 30)
            self.choices.append({"what": "escort squadron sizes (2D3, seed)",
                                 "result": self._sq_seed})
        organize_escorts(rows, self.list_key, random.Random(self._sq_seed),
                         mix=getattr(self, "mix_escorts", False))

    def _repair(self, rows) -> List[str]:
        """Local search on the fleet's problems. Each step tries every move of
        a few kinds: drop one ship of a class, add one of a class, add several
        escorts of a class (2-6), trade a capital ship for as many escorts of
        a class as its points buy (lists with escorts per capital ship). The
        move leaving the fewest problems, then the smallest shortfall in them
        (`_shortfall`: "9 needed, 5 taken"), then the fewest unused points, is
        kept while it improves; otherwise this attempt gives up."""
        def score(trial):
            e = self._errors(trial)
            return (len(e), sum(_shortfall(x) for x in e), self.points - self._total(trial)), e
        cur, errs = score(rows)
        escorts = [t for t in self.catalog if ship_size(t[0]) == "escort"]
        for _ in range(REPAIR_STEPS):
            if not errs:
                return errs
            best = None
            was_mixed = getattr(self, "mix_escorts", False)
            for name, trial in self._moves(rows, escorts):
                # the core rules allow mixed escort squadrons (one class each is
                # the owner's preference): mixed when a list's squadron limit needs it
                self.mix_escorts = was_mixed or name == "mix escort classes"
                self._add_commander(trial, log=False)
                self._squadrons(trial)
                sc, e = score(trial)
                if best is None or sc < best[0]:
                    best = (sc, trial, e, name)
            self.mix_escorts = was_mixed or (best is not None and best[3] == "mix escort classes"
                                             and best[0][:2] < cur[:2])
            if best is None or best[0][:2] >= cur[:2]:
                break                     # nothing helps: start again
            rows[:] = best[1]
            cur, errs = best[0], best[2]
            self.choices.append({"what": "repair", "move": best[3], "problems_left": len(errs)})
        return errs

    def _moves(self, rows, escorts):
        """(description, trial fleet) for every repair move."""
        def copy(rs):
            return [dict(r, upgrades=list(r["upgrades"])) for r in rs]

        if not getattr(self, "mix_escorts", False):
            yield "mix escort classes", copy(rows)

        def fits(trial, t, k=1):
            return self._total(trial) + k * self._row_quiet(*t)["points"] <= self.points
        seen = set()
        for i, r in enumerate(rows):                       # drop one of a class
            cls = r["entry"].ship_class
            if cls in seen:
                continue
            seen.add(cls)
            trial = copy(rows[:i] + rows[i + 1:])      # a dropped flagship's commander moves
            yield f"drop {cls}", trial
            if r["entry"].ship_type != "escort":          # trade it for escorts
                for t in escorts:
                    tr = copy(trial)
                    k = 0
                    while k < 6 and fits(tr, t):
                        tr.append(self._row(*t, log=False))
                        k += 1
                    if k:
                        yield f"trade {cls} for {k} {t[0].ship_class}", tr
        for t in self.catalog:                             # add one of a class
            if fits(rows, t):
                yield f"add {t[0].ship_class}", copy(rows) + [self._row(*t, log=False)]
        for t in self.catalog:                             # add several of a class
            for k in ((2, 3, 4, 6) if ship_size(t[0]) == "escort" else (2, 3)):
                if fits(rows, t, k):
                    yield (f"add {k} {t[0].ship_class}",
                           copy(rows) + [self._row(*t, log=False) for _ in range(k)])
        seen = set()
        for i, r in enumerate(rows):                       # drop one and refill
            cls = r["entry"].ship_class
            if cls in seen or r["entry"].ship_type == "escort":
                continue
            seen.add(cls)
            trial = copy(rows[:i] + rows[i + 1:])
            self._fill(trial, quiet=True, exclude=cls)
            yield f"drop {cls} and refill", trial

    def build(self) -> Tuple[List[dict], List[str]]:
        """(rows, problems): the best fleet over ATTEMPTS tries ([] problems
        when it keeps every rule)."""
        best = None
        for attempt in range(ATTEMPTS):
            self.mix_escorts = False
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
            self._satisfy(rows)
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


def _shortfall(err: str) -> int:
    """How far a fleet-list problem is from being met, read from its text:
    "need at least 9 escorts (5 taken)" 4, "3 taken, at most 1" 2, "8, at most ...
    (3)" 5, "5 towed ... hooks for only 0" 5; 1 otherwise.
    A tie-breaker for the repair search only."""
    import re
    text = re.sub(r"p\.\d+", "", err)
    nums = [int(n) for n in re.findall(r"\d+", text)]
    if not nums:
        return 1
    m = re.search(r"(\d+) taken", text)
    if m:
        taken = int(m.group(1))
        rest = [n for n in nums if n != taken] or [taken]
        if "at most" in text:
            return max(1, taken - min(rest))          # too many
        return max(1, max(rest) - taken)              # too few
    if len(nums) >= 2:
        return max(1, abs(nums[0] - nums[-1]))        # "8, at most (3)", "5 ... only 0"
    return 1


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
