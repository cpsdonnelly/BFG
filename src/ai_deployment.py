"""AI deployment (To do 28, first slice): the AI places its own ships.

Owner design:
  - Ships that buff friends in range (Tyranid synapse, Tau tracking systems,
    Fleet Defence Turrets' massed turret; `buffs.py`) are placed last, where
    their help is worth most (friends not already covered by another).
  - With two or more of them the fleet deploys in small groups, one round
    each (`plan_clusters`), so each goes along with its group.
  - Squadrons in a line or a box, in base contact or not, chosen at random,
    always coherent (every pair within 15cm, s.8).
  - Every random choice is drawn from the game's recorded generator
    (`rng.game_random`) and logged (To do 31), so a game replays exactly.

The rest are placed in their zone the way Auto-Place does (nearest its centre,
clear of ships already placed), facing the enemy or as the scenario requires;
a scenario's own positions (`scenarios.auto_positions`) come first. Not yet:
forming squadrons (they come from the fleet file), capital squadrons,
deployment by strategy (where in the zone suits the matchup), the alternating
deployment orders, commander placement after the Ld roll (To do 29)."""
import math
from typing import Callable, List, Optional, Tuple

from .deployment import (COHERENCY_CM, DeploymentState, DeploymentZone, grid_positions,
                         placement_heading)
from .models import Ship


from .buffs import buff_range, buff_value   # noqa: F401  (buff_range used by tests too)


def _formation(group: List[Ship], shape: str, spacing: str, heading: float):
    """Offsets for a squadron: a line across the facing or a box of two rows,
    in base contact or loose (5cm), squeezed to keep every pair within 15cm."""
    n = len(group)
    base = max(s.base_radius for s in group) * 2 + 0.2
    step = base if spacing == "contact" else max(base, 5.0)
    cols = n if shape == "line" else (n + 1) // 2
    rows = 1 if shape == "line" else (2 if n > 1 else 1)

    def span(st):
        return math.hypot((cols - 1) * st, (rows - 1) * st)
    while span(step) > COHERENCY_CM - 0.5 and step > base:
        step = max(base, step - 0.5)
    h = math.radians(heading)
    across = (-math.sin(h), math.cos(h))          # perpendicular to the facing
    back = (-math.cos(h), -math.sin(h))
    out = []
    for i in range(n):
        c, r = i % cols, i // cols
        a = (c - (cols - 1) / 2.0) * step
        b = (r - (rows - 1) / 2.0) * step
        out.append((a * across[0] + b * back[0], a * across[1] + b * back[1]))
    return out


def _clear(pos, zone: DeploymentZone, placed, margin: float = 2.5) -> bool:
    return all(zone.contains(x, y) and zone.x_min + margin <= x <= zone.x_max - margin and
               zone.y_min + margin <= y <= zone.y_max - margin for x, y in pos) and \
        all(math.hypot(x - s.x, y - s.y) >= 8.0 for x, y in pos for s in placed)


def _anchors(zone: DeploymentZone, toward=None):
    """Candidate centres across the zone, nearest its centre (or `toward`,
    a group's cluster point) first."""
    cx, cy = toward or ((zone.x_min + zone.x_max) / 2.0, (zone.y_min + zone.y_max) / 2.0)
    pts = []
    x = zone.x_min + 3.0
    while x <= zone.x_max - 3.0:
        y = zone.y_min + 3.0
        while y <= zone.y_max - 3.0:
            if zone.contains(x, y):
                pts.append((x, y))
            y += 4.0
        x += 4.0
    pts.sort(key=lambda p: math.hypot(p[0] - cx, p[1] - cy))
    return pts


def cluster_points(zone: DeploymentZone, k: int) -> List[Tuple[float, float]]:
    """k cluster centres spread along the zone's long side, in its middle."""
    w, h = zone.x_max - zone.x_min, zone.y_max - zone.y_min
    out = []
    for i in range(k):
        f = (i + 0.5) / k
        if w >= h:
            out.append((zone.x_min + f * w, zone.y_min + h / 2.0))
        else:
            out.append((zone.x_min + w / 2.0, zone.y_min + f * h))
    return out


def plan_clusters(groups: List[List[Ship]], zone: DeploymentZone,
                  log: Callable[[str], None]) -> dict:
    """Owner: with ships that help friends in range, deploy in small groups so
    each of them goes along with one. One cluster per such unit, spread along
    the zone; the other units shared out, dearest first, to the cluster with
    the fewest points (judgement), preferring one whose helper they can use.
    Returns {group's first ship id: cluster point}."""
    from .buffs import buff_kinds, benefits
    helpers = [g for g in groups if any(buff_kinds(s) for s in g)]
    if len(helpers) < 2:
        return {}
    pts = cluster_points(zone, len(helpers))
    load = [sum(s.points_value for s in g) for g in helpers]
    kinds = [set(k for s in g for k in buff_kinds(s)) for g in helpers]
    plan = {g[0].id: pts[i] for i, g in enumerate(helpers)}
    rest = sorted((g for g in groups if g not in helpers),
                  key=lambda g: -sum(s.points_value for s in g))
    for g in rest:
        useful = [i for i in range(len(helpers))
                  if any(benefits(k, g[0]) for k in kinds[i])] or list(range(len(helpers)))
        i = min(useful, key=lambda j: load[j])
        load[i] += sum(s.points_value for s in g)
        plan[g[0].id] = pts[i]
    for i, g in enumerate(helpers):
        log(f"[AI] deploys a group round {g[0].name} ({load[i]} pts)")
    return plan


def _place_positions(gs, state: DeploymentState, player: int, group: List[Ship], rng,
                     log: Callable[[str], None], toward=None) -> List[Tuple[float, float]]:
    zone = state.zones[player]
    friends = [s for s in state.placed_ships if s.player == player]
    reach = max(buff_range(s) for s in group)
    shape = spacing = None
    if len(group) > 1:
        # Owner: formation by armament. A squadron whose ordnance gains by
        # combining (formations.needs_contact, against the enemy's dearest
        # ship's turrets) starts in base contact, in a line abreast across its
        # facing (a combined wave is measured from the member furthest from
        # the target, so abreast loses least); gun squadrons gain nothing from
        # contact, so their formation is a random draw (logged, To do 31)
        from .formations import needs_contact
        enemies = [s for s in gs.get_ships() if s.player != player and s.status == "active"]
        foe = max(enemies, key=lambda s: s.points_value) if enemies else None
        if foe is not None and needs_contact(group, foe, gs):
            shape, spacing = "line", "contact"
            log(f"[AI] deploys {group[0].name}'s squadron of {len(group)} in base contact, "
                f"line abreast (its ordnance combines)")
        else:
            shape = rng.choice(["line", "box"])
            spacing = rng.choice(["contact", "loose"])
            log(f"[AI] deploys {group[0].name}'s squadron of {len(group)} in a {shape}"
                f"{', in base contact' if spacing == 'contact' else ', loose'}")
    best, best_key = None, None
    for ax, ay in _anchors(zone, toward):
        heading = placement_heading(gs, state, player, ax, ay)
        offs = _formation(group, shape, spacing, heading) if shape else [(0.0, 0.0)]
        pos = [(ax + ox, ay + oy) for ox, oy in offs]
        if not _clear(pos, zone, state.placed_ships):
            continue
        if not reach:
            return pos                         # nearest the zone's centre
        # the help it gives friends not yet covered by another helper
        # (buffs.buff_value), then the friends in reach as a tie-break
        val = 0.0
        for s, (x, y) in zip(group, pos):
            val += buff_value(s, x, y, friends)
        covered = sum(1 for f in friends
                      if min(math.hypot(f.x - x, f.y - y) for x, y in pos) <= reach)
        key = (-val, -covered)
        if best_key is None or key < best_key:
            best, best_key = pos, key
    if best is not None and reach:
        log(f"[AI] places {group[0].name} last, with {-best_key[1]} friend(s) in its "
            f"{reach:.0f}cm reach")
    return best or grid_positions(group, zone, state.placed_ships)


def ai_deploy(gs, state: DeploymentState, player: int,
              log: Optional[Callable[[str], None]] = None) -> List[str]:
    """Place `player`'s groups while it is its turn to deploy (all of them in a
    sequential deployment). Ships are written to `gs`. Returns the errors of a
    group that couldn't be placed (it stops there)."""
    from .rng import game_random
    from .scenarios import auto_positions
    log = log or (lambda _m: None)
    rng = game_random(gs, "deploy")
    i = state.next_idx[player]
    rest = state.groups[player][i:]
    # buff ships last (stable: the rest keep their order)
    rest.sort(key=lambda g: max(buff_range(s) for s in g) > 0)
    state.groups[player][i:] = rest
    clusters = plan_clusters(rest, state.zones[player], log)
    while not state.is_complete() and state.active_player == player:
        group = state.current_group()
        if group is None:
            break
        positions = (auto_positions(gs, group, state.zones[player], state.placed_ships,
                                    state.next_idx[player])
                     or _place_positions(gs, state, player, group, rng, log,
                                         clusters.get(group[0].id)))
        headings = [placement_heading(gs, state, player, x, y) for x, y in positions]
        ok, errors = state.place_group(positions, headings)
        if not ok:
            positions = grid_positions(group, state.zones[player], state.placed_ships)
            headings = [placement_heading(gs, state, player, x, y) for x, y in positions]
            ok, errors = state.place_group(positions, headings)
            if not ok:
                return [f"{group[0].name}: {e}" for e in errors]
        for ship in state.placed_ships[-len(group):]:
            gs.update_ship(ship)
    return []


def ai_deploy_all(gs, state: DeploymentState, log=None) -> List[str]:
    """Both fleets placed by the AI (spectator games, the headless runner)."""
    while not state.is_complete():
        before = sum(state.next_idx.values())
        errors = ai_deploy(gs, state, state.active_player, log)
        if errors:
            return errors
        if sum(state.next_idx.values()) == before:
            break
    return []
