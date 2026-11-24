"""Ork rules built for the owner's Ork fleet (11_orks.md, Xenos p.53-57):
kustom force fields, looted vessels and their own-goal on a failed
Leadership test. Pure logic."""
from typing import Dict, List

KILLKANNON = {"name": "Prow Killkannon", "weapon_type": "battery", "range_cm": 30,
              "strength": 6, "arcs": ["front"], "hits_on": 4, "crit_on": 4}
ORK_RULES = ["ere_we_go", "ork_crew", "ork_turrets"]


# ── Kustom force fields ────────────────────────────────────────────────────────
# "replaces one of the ship's shields (losing a point of shield strength) with
# +D3 shields, rolled randomly each game turn when the ship first comes under
# attack or would otherwise need its shields". Reading: rolled at the start of
# each game turn for every ship that has one (the same chance, rolled up front).

def force_field_bonus(ship) -> int:
    for r in getattr(ship, "special_rules", None) or []:
        if r.startswith("kff:"):
            return int(r.split(":")[1])
    return 0


def roll_force_fields(gs, dice) -> List[str]:
    """A fresh D3 for every ship with a kustom force field."""
    out = []
    for s in gs.get_ships():
        if "kustom_force_field" not in s.special_rules or s.status != "active":
            continue
        n = dice.roll_d3(f"{s.name} kustom force field (+D3 shields)")
        s.special_rules = [r for r in s.special_rules if not r.startswith("kff:")] + [f"kff:{n}"]
        gs.update_ship(s)
        out.append(f"{s.name}: kustom force field +{n} shields this game turn")
    for line in out:
        gs.add_log(line)
    return out


# ── Looted vessels ─────────────────────────────────────────────────────────────

def loot(ship: Dict) -> Dict:
    """Turn a stored ship dict taken as an Ork fleet's reserve into a looted
    vessel: an Ork vessel for Leadership (Orks table), orders, boarding and
    turrets; lances become zzapp gunz (same profile), attack craft fighta-
    bommerz / assault boats, a nova cannon a killkannon (30cm FP6 front)."""
    ship = dict(ship)
    weapons = []
    for w in ship.get("weapons", []):
        w = dict(w)
        if w.get("weapon_type") == "lance":
            w.update(hits_on=5, zzapp=True)
            w["name"] = w["name"].replace("Lances", "Zzapp Gunz").replace("Lance", "Zzapp Gunz")
        elif w.get("weapon_type") == "nova_cannon":
            w = dict(KILLKANNON)
        elif w.get("weapon_type") == "launch_bay":
            w["craft_types"] = ["fighta_bommer", "assault_boat"]
            w["craft_speeds"] = {"fighta_bommer": 25, "assault_boat": 30}
            w["craft_speed"] = 30
        weapons.append(w)
    ship["weapons"] = weapons
    rules = [r for r in ship.get("special_rules", []) if r not in ORK_RULES]
    ship["special_rules"] = rules + ORK_RULES + ["looted"]
    ship["leadership_table"] = "Orks"
    ship["faction"] = "orks"
    return ship


def looted_errors(rows: List[Dict]) -> List[str]:
    """Looted vessels: cruisers only (from the Navy, Chaos or Tau lists), and
    "any normal upgrades shown in their profile (except nova cannons)"."""
    errs = []
    for r in rows:
        if not (r.get("list") or "").startswith("reserve:"):
            continue
        e = r["entry"]
        if e.ship_type != "cruiser":
            errs.append(f"{e.ship_class}: Ork fleets take only cruisers as looted vessels.")
        d = e.to_ship_dict(name="", player=0, upgrades=r.get("upgrades", []))
        base = {w.get("weapon_type") for w in e.weapons}
        if any(w.get("weapon_type") == "nova_cannon" for w in d["weapons"]) \
                and "nova_cannon" not in base:
            errs.append(f"{e.ship_class}: a looted vessel can't take a nova cannon upgrade.")
    return errs


def own_goal(ship, dice, gs) -> bool:
    """A looted vessel that fails a Leadership test: a D6, on 1-3 the Orks
    damage their own ship (1 hit, no saves). True if it took the hit."""
    if "looted" not in (getattr(ship, "special_rules", None) or []) or gs is None:
        return False
    r = dice.roll_d6(1, f"{ship.name} (looted) failed a Leadership test: 1-3 the Orks damage it")[0]
    if r > 3:
        return False
    fresh = gs.get_ship_by_id(ship.id) or ship
    gs.add_log(f"{ship.name}: the Orks damage their own looted ship (1 hit)")
    # "no saves of any kind", but a hit like any other: its critical check (owner)
    from .combat import apply_damage
    apply_damage(fresh, 1, dice, gs, ignores_shields=True, rolled_to_hit=False)
    fresh = gs.get_ship_by_id(ship.id) or fresh
    ship.hits_remaining = fresh.hits_remaining
    if fresh.hits_remaining <= 0:
        from .actions import resolve_kill
        resolve_kill(gs, dice, fresh.id)
    return True
