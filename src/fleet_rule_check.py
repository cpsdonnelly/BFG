"""Fleets that rely on optional rules (owner request): before a game starts,
list what each fleet carries that does nothing with an optional rule
switched off, so the player can turn the rule on or start anyway. Pure logic;
the setup wizard asks (main._show_setup_dialog)."""
from typing import Dict, List, Tuple

RULE_NAMES = {"hit_and_run": "Hit and Run Raids", "teleport": "Teleport Attacks",
              "boarding": "Boarding Actions", "ramming": "Ramming"}


def _assault_only(craft_type: str, bays) -> bool:
    from .ordnance import craft_stats, craft_roles
    return set(craft_roles(craft_stats(craft_type, bays)[0])) == {"assault_boat"}


def ship_needs(ship) -> List[Tuple[str, str]]:
    """[(rule key, what needs it)] for one ship: things it carries or bought that
    only work with that optional rule. Innate faction abilities that are just a
    bonus (Space Marine teleport assault, crew raid bonuses) aren't listed."""
    out = []
    rules = set(ship.special_rules or [])
    bays = [w for w in ship.weapons if w.get("weapon_type") == "launch_bay"]
    for w in bays:
        types = list(w.get("craft_types") or [])
        boats = [ct for ct in types if _assault_only(ct, [w])]
        if not boats:
            continue
        if len(boats) == len(types):
            what = "Impalers" if w.get("impaler_bay") else "assault boats"
            out.append(("hit_and_run", f"{w.get('name', 'launch bays')} carry only {what}"))
        elif any("assault boat" in (u or "").lower() for u in (ship.upgrades or [])):
            out.append(("hit_and_run", "the assault boats bought for its bays"))
    if any(w.get("weapon_type") == "portal" for w in ship.weapons):
        out += [("teleport", "portals"), ("hit_and_run", "portals")]
    if "soopa_tellyporta" in rules:
        out += [("teleport", "Soopa Tellyporta"), ("hit_and_run", "Soopa Tellyporta")]
    for r in ("veteran_honour_guard", "terminator_honour_guard"):
        if r in rules:
            out += [("teleport", "an honour guard (teleport attacks)"),
                    ("hit_and_run", "an honour guard (teleport attacks)")]
    if "incubi" in rules:
        out.append(("hit_and_run", "Incubi (their raids)"))
    if "mega_armoured_boarders" in rules:
        out += [("boarding", "Mega Armoured Boarding Parties"),
                ("hit_and_run", "Mega Armoured Boarding Parties")]
    if "wych_cult" in rules:
        out.append(("boarding", "a Wych Cult"))
    if "plague_ark" in rules:
        out.append(("boarding", "a Plague Ark"))
    return out


def fleet_rule_warnings(ships, enabled: Dict[str, bool]) -> Dict[str, List[str]]:
    """{rule key: ["<ship>: <what>", ...]} for optional rules switched off
    (`enabled`: {"hit_and_run": False, ...}) that something in `ships` needs."""
    counts: Dict[str, Dict[str, int]] = {}
    for s in ships:
        for key, what in ship_needs(s):
            if enabled.get(key, True):
                continue
            line = f"{s.name}: {what}"
            per = counts.setdefault(key, {})
            per[line] = per.get(line, 0) + 1
    return {key: [ln if n == 1 else f"{ln} (x{n})" for ln, n in per.items()]
            for key, per in counts.items()}


def warning_text(by_player: Dict[int, Dict[str, List[str]]]) -> str:
    """The message the setup wizard shows."""
    parts = []
    for p, warns in sorted(by_player.items()):
        for key, lines in warns.items():
            parts.append(f"Player {p}'s fleet relies on {RULE_NAMES.get(key, key)} (off):")
            parts += [f"  - {ln}" for ln in lines[:8]]
            if len(lines) > 8:
                parts.append(f"  ... and {len(lines) - 8} more")
    return "\n".join(parts)
