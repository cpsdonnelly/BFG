"""Dark Eldar rules (bfgxr/rules/08_dark-eldar.md, Xenos p.4-6): shadowfields
and their tracking marks, flickerfields, movement. Pure logic; the engine
calls these from combat, ordnance and movement."""
from typing import Optional


def is_dark_eldar(ship) -> bool:
    return "dark_eldar" in (getattr(ship, "special_rules", None) or [])


def has_shadowfield(ship) -> bool:
    """Shadowfields work until a Shadowfield Generators Destroyed crit (which
    removes the rule, combat.apply_crit_effects)."""
    return "shadowfield" in (getattr(ship, "special_rules", None) or [])


def attacker_unit_key(attacker) -> str:
    """Tracking marks are limited to one per target per attacking ship or
    squadron."""
    if attacker is None:
        return "?"
    return getattr(attacker, "squadron_id", "") or getattr(attacker, "id", "") or "?"


def add_tracking_mark(gs, target, attacker) -> None:
    """A gunnery hit on a shadowfielded ship or squadron: one mark per
    attacking ship or squadron, on every ship of the target's unit, to the end
    of the turn (applied even if the hit was saved by bracing)."""
    if not has_shadowfield(target):
        return
    key = attacker_unit_key(attacker)
    unit = [s for s in gs.get_ships() if target.squadron_id
            and s.squadron_id == target.squadron_id] if target.squadron_id else []
    for ship in unit or [gs.get_ship_by_id(target.id) or target]:
        if key not in ship.tracking_marks:
            ship.tracking_marks = list(ship.tracking_marks) + [key]
            gs.update_ship(ship)
    if key not in target.tracking_marks:
        target.tracking_marks = list(target.tracking_marks) + [key]


def shadowfield_need(target) -> Optional[int]:
    """The shadowfield save against lance and ordnance hits (and ordnance
    raids): 2+, +1 per tracking mark, at most 6+. None without shadowfields."""
    if not has_shadowfield(target):
        return None
    return min(6, 2 + len(target.tracking_marks or []))


def shadowfield_saves(dice, target, hits: int, what: str = "hits") -> int:
    """Roll the shadowfield save for each hit; returns the number saved."""
    need = shadowfield_need(target)
    if need is None or hits <= 0:
        return 0
    rolls = dice.roll_d6(hits, f"{target.name} shadowfield vs {what} ({need}+)")
    return sum(1 for r in rolls if r >= need)


def flickerfield_penalty(marker) -> int:
    """Enemy turrets add +2 to their hit roll against Dark Eldar torpedoes and
    attack craft (not mines)."""
    rules = getattr(marker, "special_rules", None) or []
    if "dark_eldar" not in rules:
        return 0
    if "mine" in (getattr(marker, "ordnance_type", "") or ""):
        return 0
    return 2


def resolve_impaler(marker, target, braced: bool, dice, gs) -> dict:
    """An Impaler assault module contacting an enemy ship (Xenos p.5): a D6; 1
    no effect; otherwise two hit-and-run raids or one critical hit (the
    attacker's choice: judgement, a crit against a capital ship, raids against
    an escort), and one point of damage first if the D6 equals or beats the
    target's Armour. A braced target saves 4+ against each effect; shadowfields
    save against it as an ordnance raid. Haemonculi make the crit a Fire."""
    from .combat import apply_damage, roll_critical_hit, add_fire_crits
    from .hit_and_run import resolve_raids
    out = {"raid_rolls": [], "failures": 0, "repelled": 0, "crits_applied": [],
           "damage": 0, "impaler_roll": 0}
    if shadowfield_saves(dice, target, 1, "the Impaler"):
        gs.add_log(f"  {target.name} shadowfield: the Impaler misses")
        out["shadowfield_saved"] = 1
        return out
    if impaler_slaves(gs, marker, target, braced, dice):
        out["slaves"] = 1
        return out
    roll = dice.roll_d6(1, f"Impaler vs {target.name} (1 no effect)")[0]
    out["impaler_roll"] = roll
    if roll == 1:
        gs.add_log("  The Impaler fails to connect")
        out["failures"] = 1
        return out

    def _saved(what):
        if not braced:
            return False
        if dice.roll_d6(1, f"{target.name} Brace vs Impaler {what} (4+)")[0] >= 4:
            out["repelled"] += 1
            return True
        return False

    armour = target.armor_vs(marker.x, marker.y)
    if roll >= armour and not _saved("damage"):
        gs.add_log(f"  The Impaler's bladed prow carves {target.name}: 1 damage")
        apply_damage(target, 1, dice, gs, ignores_shields=True, attacker_key=marker.id)
        out["damage"] += 1
    target = gs.get_ship_by_id(target.id) or target
    if target.hits_remaining <= 0:
        return out
    if target.ship_type == "escort":
        res = resolve_raids(2, target, braced, dice, gs, source_name="Impaler",
                            attacker_rules=marker.special_rules)
        for k in ("raid_rolls", "crits_applied"):
            out[k] += res.get(k, [])
        for k in ("failures", "repelled", "damage"):
            out[k] += res.get(k, 0)
        return out
    if _saved("critical hit"):
        return out
    if "haemonculi" in (marker.special_rules or []):
        gs.add_log(f"  Haemonculi: the Impaler's critical hit on {target.name} is a Fire")
        add_fire_crits(target, 1, gs)
        out["crits_applied"].append({"crit_type": "fire"})
    else:
        before = len(target.critical_damage)
        rr = ((lambda r, c: frenzy_crit_reroll(target, r, c))
              if pain_frenzy_applies(marker.special_rules, target) else None)
        roll_critical_hit(target, dice, gs, reroll_fn=rr)
        fresh = gs.get_ship_by_id(target.id) or target
        out["crits_applied"] += fresh.critical_damage[before:]
    return out


def greed_binds(gs, ship) -> bool:
    """Insatiable Greed (Xenos p.4) would make this ship's disengaging count as
    destroyed: a non-crippled Dark Eldar ship whose fleet hasn't scored 25% of
    its own value in VP. Cached on the game per turn and losses (the VP sum is
    not cheap)."""
    if not is_dark_eldar(ship) or ship.damage_crippled:
        return False
    ships = gs.get_ships()
    key = (gs.turn_number, ship.player,
           sum(1 for s in ships if s.is_destroyed or s.is_disengaged or s.damage_crippled))
    cache = gs.__dict__.setdefault("_greed_cache", {})
    if key not in cache:
        from .victory_points import calculate_victory_points
        scored = calculate_victory_points(gs)[ship.player]["total"]
        value = sum(s.points_value for s in ships if s.player == ship.player)
        cache[key] = scored * 4 < value
    return cache[key]


# ── Slave-taking (Xenos p.4) ────────────────────────────────────────────────

def _add_slave_vp(gs, player: int, vp: int, why: str) -> None:
    sv = dict(getattr(gs, "slave_vp", None) or {})
    sv[str(player)] = int(sv.get(str(player), 0)) + vp
    gs.slave_vp = sv
    gs.add_log(f"  Slave-taking: +{vp} VP to Player {player} ({why})")


def wants_slaves(gs, player: int, target, what: str, value_now: float, slaves: float) -> bool:
    """Take slaves instead of resolving the attack? A human player is asked
    (`GameState.slave_hook`); otherwise (the AI, "Auto") by expected VP:
    slaves when they are worth more than the attack (judgement)."""
    best = slaves > value_now
    hook = getattr(gs, "slave_hook", None)
    if hook is not None:
        answer = hook(player, target, what, best)
        if answer is not None:
            return bool(answer)
    return best


def take_slaves(gs, attacker_rules, target, braced: bool, dice, vp: int) -> bool:
    """A Dark Eldar hit-and-run raid may forgo its result for +5 VP. A braced
    target still saves (4+): then no VP. True if slaves were taken (the raid
    isn't rolled)."""
    if "dark_eldar" not in (attacker_rules or []):
        return False
    player = 3 - target.player
    from .waves import raid_squadron_value
    try:
        value = raid_squadron_value(target, gs, player, list(attacker_rules))
    except Exception:                     # a value we can't price: roll the raid
        value = vp + 1
    if not wants_slaves(gs, player, target, "raid", value, vp):
        return False
    if braced and dice.roll_d6(1, f"{target.name} Brace vs slave-taking (4+)")[0] >= 4:
        gs.add_log(f"  {target.name} braces: the slave-takers come away empty-handed")
        return True
    _add_slave_vp(gs, player, vp, f"raid on {target.name}")
    return True


def impaler_slaves(gs, marker, target, braced: bool, dice) -> bool:
    """An Impaler may score D6 x 5 VP instead of its raids / crit (a single
    attack for a braced target's save). True if taken."""
    player = marker.owner_player
    value = 1.5 * (2 if target.ship_type == "escort" else 3)   # judgement: the attack's worth
    if not wants_slaves(gs, player, target, "Impaler", value, 17.5):
        return False
    if braced and dice.roll_d6(1, f"{target.name} Brace vs slave-taking (4+)")[0] >= 4:
        gs.add_log(f"  {target.name} braces: the Impaler's slavers come away empty-handed")
        return True
    roll = dice.roll_d6(1, "Impaler slave-taking (D6 x 5 VP)")[0]
    _add_slave_vp(gs, player, roll * 5, f"Impaler on {target.name}")
    return True


def boarding_slave_vp(gs, attackers, target, summary) -> None:
    """In a boarding action involving a Dark Eldar vessel, its player scores
    +5 VP a hit inflicted on the opposition, +100 for a Bridge Smashed on it."""
    win = summary.get("winner")
    if win not in ("attacker", "defender") or not attackers:
        return
    side = attackers if win == "attacker" else [target]
    if not any(is_dark_eldar(s) for s in side):
        return
    crits = summary.get("defender_crits" if win == "attacker" else "attacker_crits") or []
    vp = 5 * int(summary.get("damage") or 0)
    if any((c or {}).get("crit_type") == "bridge_smashed" for c in crits):
        vp += 100
    if vp:
        _add_slave_vp(gs, side[0].player, vp, "boarding action")


def remove_spent_impalers(gs, player: int) -> int:
    """Impalers left on the table at the start of the owning player's turn are
    removed for lack of fuel (Xenos p.5). Called at the start of the player's
    movement phase (IGOUGO, `TurnController.begin_phase`) and of each round
    (alternate activation, `AATurn._start_round`). Returns how many went."""
    gone = [o for o in gs.ordnance if o.get("owner_player") == player
            and "impaler" in (o.get("special_rules") or [])]
    if gone:
        ids = {o["id"] for o in gone}
        gs.ordnance = [o for o in gs.ordnance if o["id"] not in ids]
        gs.add_log(f"{len(gone)} Impaler(s) removed: out of fuel")
    return len(gone)


# ── Pain Frenzy re-rolls (Xenos p.4) ────────────────────────────────────────

def pain_frenzy_applies(attacker_rules, target) -> bool:
    """Against crippled enemy vessels Dark Eldar may re-roll a hit-and-run raid,
    a boarding critical hit or an Impaler critical hit (the second result
    stands). A Wych Cult counts every enemy capital ship as crippled for it."""
    rules = attacker_rules or []
    if "dark_eldar" not in rules or target is None:
        return False
    if target.damage_crippled:
        return True
    return "wych_cult" in rules and target.ship_type != "escort"


def frenzy_raid_reroll(gs, owner: int, roll: int, effective: int, target) -> bool:
    """Re-roll this raid (or boarding crit, rolled the same way on the D6
    table)? A human owner is asked (`GameState.raid_reroll_hook`, the Wings of
    Fury prompt); otherwise by expected value (`hit_and_run.best_raid_reroll`)."""
    hook = getattr(gs, "raid_reroll_hook", None)
    answer = hook(owner, roll, effective, target) if hook else None
    if answer is None:
        from .hit_and_run import best_raid_reroll
        return best_raid_reroll(roll, effective, target, gs, owner)
    return bool(answer)


def frenzy_crit_reroll(target, crit_2d6: int, crit_data) -> bool:
    """Re-roll an Impaler's 2D6 critical hit? (judgement, also "Auto"): when its
    extra damage is below the average of a fresh roll on the target's table."""
    from .tables import crit_table_for
    table = crit_table_for(target)
    dist = {t: 0 for t in range(2, 13)}
    for a in range(1, 7):
        for b in range(1, 7):
            dist[a + b] += 1

    def extra(row):
        x = (row or {}).get("extra_damage", 0)
        return {"D3": 2.0, "D6": 3.5}.get(x, x) if isinstance(x, str) else float(x or 0)
    avg = sum(n * extra(table.get(t)) for t, n in dist.items()) / 36.0
    return extra(crit_data) < avg
