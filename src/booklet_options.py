"""Ship options and fleet commanders from the booklet, as fleet-builder upgrades.

Owner ruling: booklet refits, options and fleet commanders are prose in each
ship's notes and get added one at a time. Each option is a dict that
ship_catalog turns into an UpgradeEntry:

  name, description, points_cost
  effect:        "stat_delta" {field: delta}, "set" {field: value},
                 "remove_weapons" [names], "add_weapons" [weapon dicts],
                 "add_special_rules" [rules], "rerolls" n, "flagship" True
  restrictions:  "group:<g>"      at most one option of group g per ship
                 "requires:<name>" needs that option on the same ship
                 "fleet_unique"   at most one ship in the fleet may take it
                 "sc_variant"     Strike Cruiser Variant: up to half the fleet's
                                  strike cruisers (round down) may take any
"""
from typing import Dict, List

from .chapter_tactics import TACTICS

_THUNDERHAWK_BAY = {"weapon_type": "launch_bay", "range_cm": 30, "strength": 1, "arcs": [],
                    "craft_types": ["thunderhawk"], "craft_speeds": {"thunderhawk": 20},
                    "craft_speed": 20}

# Tactical Flexibility: a Space Marine fleet with no Chapter tactic takes 10pts
# off each Strike Cruiser Variant refit (minimum 0). Variant costs below include
# it; a fleet whose Master of the Fleet takes a Chapter tactic pays the
# difference back (tactical_flexibility_refund).
TACTICAL_FLEXIBILITY = 10


def _variant_cost(pts: int) -> int:
    return max(0, pts - TACTICAL_FLEXIBILITY)


def space_marine_options(row: dict) -> List[Dict]:
    name = row["name"]
    opts: List[Dict] = []
    if name in ("Strike Cruiser", "Vanguard Cruiser"):
        opts.append({
            "name": "Secondary Shield (+1 Shield)",
            "description": "Any number may add +1 Shield for +15pts each.",
            "points_cost": 15, "effect": {"stat_delta": {"shields_max": 1}}})
    if name == "Strike Cruiser":
        opts += [
            {"name": "Variant: prow Bombardment Cannon",
             "description": "Swap prow launch bays for a Bombardment Cannon (30cm FP5 F), "
                            "+10pts (-10 Tactical Flexibility).",
             "points_cost": _variant_cost(10),
             "effect": {"remove_weapons": ["Launch Bays"],
                        "add_weapons": [{"name": "Prow Bombardment Cannon (refit)",
                                         "weapon_type": "battery", "range_cm": 30,
                                         "strength": 5, "arcs": ["front"],
                                         "hits_on": 4, "crit_on": 4}]},
             "restrictions": ["group:prow_bays", "sc_variant", "base_cost:10"]},
            {"name": "Variant: prow torpedoes",
             "description": "Swap prow launch bays for torps (30cm S6 F), free; may fire "
                            "standard or boarding torpedoes.",
             "points_cost": _variant_cost(0),
             "effect": {"remove_weapons": ["Launch Bays"],
                        "add_weapons": [{"name": "Prow Torps", "weapon_type": "torpedo",
                                         "range_cm": 30, "strength": 6, "arcs": ["front"],
                                         "torpedo_type": "standard", "torpedo_speed": 30,
                                         "boarding_torpedoes": True}]},
             "restrictions": ["group:prow_bays", "sc_variant", "base_cost:0"]},
            {"name": "Variant: macrobatteries to launch bays",
             "description": "Swap both macrobatteries for port and starboard launch bays "
                            "(1 Thunderhawk squadron each), +20pts (-10 Tactical Flexibility).",
             "points_cost": _variant_cost(20),
             "effect": {"remove_weapons": ["Port Macrobatteries", "Starboard Macrobatteries"],
                        "add_weapons": [dict(_THUNDERHAWK_BAY, name="Port Launch Bays"),
                                        dict(_THUNDERHAWK_BAY, name="Starboard Launch Bays")]},
             "restrictions": ["sc_variant", "base_cost:20"]},
        ]
    notes = row.get("notes") or ""
    if name == "Strike Cruiser":
        # "any strike cruiser with torpedoes may be armed with boarding torpedoes
        # free, short-burn torpedoes +5pts, or barrage bombs +10pts" (Variant
        # costs: Tactical Flexibility takes 10 off, minimum 0)
        opts += [_opt(f"Torpedoes: {label} (instead of boarding torpedoes)",
                      f"+{cost}pts (-10 Tactical Flexibility).", _variant_cost(cost),
                      {"add_special_rules": [f"torpedo_type:{key}", "no_boarding_torps"]},
                      ["group:torpedo_type", "requires:Variant: prow torpedoes",
                       f"base_cost:{cost}"])
                 for key, label, cost in (("short_burn", "short burn torpedoes", 5),
                                          ("barrage", "barrage bombs", 10))]
    for text, swaps in (
            (("May swap boarding torpedoes for short-burn torpedoes +5pts or barrage bombs +10pts",
              "May replace its boarding torpedoes with either short-burn torpedoes for +5 points "
              "or barrage bombs for +10 points"),
             (("short_burn", "short burn torpedoes", 5), ("barrage", "barrage bombs", 10))),
            (("Specialist Torpedoes: swap boarding torpedoes for short-burn free, or barrage "
              "bombs +5pts",
              "Specialist Torpedoes: may replace its boarding torpedoes with either short-burn "
              "torpedoes for free or barrage bombs for +5 points"),
             (("short_burn", "short burn torpedoes", 0), ("barrage", "barrage bombs", 5)))):
        if any(t in notes for t in text):                   # battle barges, Vanguard
            opts += [_opt(f"Torpedoes: {label} (instead of boarding torpedoes)",
                          f"+{cost}pts." if cost else "Free.", cost,
                          {"add_special_rules": [f"torpedo_type:{key}", "no_boarding_torps"]},
                          ["group:torpedo_type"]) for key, label, cost in swaps]
    if row.get("hull_type") != "Escort" and _sm_capital(row):
        # Crusade and Dominion lists (fleet_lists list_options)
        opts.append(_opt("Veteran honour guard", "+10pts. Double teleport range; teleport "
                         "attacks roll 2D6 and use the best.", 10,
                         {"add_special_rules": ["veteran_honour_guard"]},
                         ["group:honour_guard"]))
    if _sm_capital(row):
        mof = "Master of the Fleet (Ld 10)"
        opts += [
            {"name": mof,
             "description": "Fleet commander, 50pts (required at 750+ pts); rides a battle "
                            "barge. Ld 10.",
             "points_cost": 50,
             "effect": {"set": {"leadership": 10, "leadership_table": ""},
                        "add_special_rules": ["fleet_commander"], "flagship": True},
             "restrictions": ["fleet_unique"]},
        ] + [
            {"name": f"Master of the Fleet: {n} re-roll{'s' if n > 1 else ''}",
             "description": f"{n} fleet re-roll{'s' if n > 1 else ''} ({25 * n}pts).",
             "points_cost": 25 * n, "effect": {"rerolls": n},
             "restrictions": ["group:mof_rerolls", f"requires:{mof}"]}
            for n in (1, 2, 3)
        ] + [
            {"name": f"Chapter tactic: {label}",
             "description": ("+15pts. The Master of the Fleet's Chapter tactic, affecting all "
                             "relevant ships (replaces Tactical Flexibility)."),
             "points_cost": 15,
             "effect": {"add_special_rules": [f"chapter_tactic:{key}"]},
             "restrictions": ["group:chapter_tactic", f"requires:{mof}"]}
            for key, label in TACTICS.items()
        ] + [
            {"name": "Master of the Fleet: Terminator honour guard",
             "description": "+25pts. Double teleport range; teleport attacks roll 3D6 and "
                            "use the best two as two raids.",
             "points_cost": 25,
             "effect": {"add_special_rules": ["terminator_honour_guard"]},
             "restrictions": [f"requires:{mof}", "group:honour_guard"]},
        ]
    return opts


def _sm_capital(row: dict) -> bool:
    """A Space Marine capital ship (battle barge, strike, vanguard or venerable
    strike cruiser); not the Fortress-Monastery or escorts."""
    from .booklet_ships import _ship_type
    return (_ship_type(row) in ("cruiser", "battleship")
            and "Fortress" not in row.get("name", ""))


def torpedo_strength(row: dict) -> int:
    """Total printed strength of a booklet ship's torpedo launchers."""
    return sum(int(w["value"]) for w in row.get("weapons") or []
               if w.get("kind") == "weapon" and "Torp" in (w.get("name") or "")
               and w.get("stat") == "S" and str(w.get("value", "")).isdigit())


def torpedo_type_options(row: dict, strength: int = 0, requires: str = "") -> List[Dict]:
    """Imperial Navy and Chaos fleet lists: capital ships armed with torpedoes
    may take short burn, guided torpedoes or barrage bombs at +5 per torpedo
    strength, or the +50pt D3 roll. Owner ruling: one
    type per ship, carried in addition to its other torpedoes. (Guided
    torpedoes and anointed munitions aren't playable yet.)"""
    st = strength or torpedo_strength(row)
    from .booklet_ships import _ship_type
    if not st or _ship_type(row) not in ("cruiser", "battleship"):
        return []                      # "any capital ship armed with torpedoes"
    opts = [{"name": f"Torpedoes: {label}",
             "description": f"Carried as well as its other torpedoes; chosen at each launch. "
                            f"+5pts per torpedo strength ({st}).",
             "points_cost": 5 * st,
             "effect": {"add_special_rules": [f"torpedo_type:{key}"]},
             "restrictions": ["group:torpedo_type"]}
            for key, label in (("short_burn", "short burn (40cm; out of fuel on a 6)"),
                               ("barrage", "barrage bombs (hits stopped by shields)"),
                               ("guided", "guided (turn 45° on a Leadership test)"))]
    # Chaos Anointed Munitions; Imperial Navy "+50 to roll once per game for
    # Seeking/Melta/Vortex" (owner ruling: per ship, the same D3 roll)
    name = ("Torpedoes: Anointed Munitions (D3 at game start)" if "Chaos" in row.get("faction_rules", [])
            else "Torpedoes: roll for Seeking / Melta / Vortex (D3 at game start)")
    opts.append({"name": name,
                 "description": "+50pts. At game start roll a D3: 1 Seeking, 2 Melta, 3 Vortex "
                                "torpedoes, as well as its other torpedoes; one salvo per game.",
                 "points_cost": 50,
                 "effect": {"add_special_rules": ["torpedo_roll:d3_anointed"]},
                 "restrictions": ["group:torpedo_type"]})
    if requires:                       # torpedoes only from a refit (Victory, Mercury...)
        for o in opts:
            o["restrictions"].append("requires_any:" + requires)
    return opts


_REFIT_TABLE = ("D6 at game start: 1 Short Burn, 2 Barrage Bombs, 3 Guided, 4 Seeking*, "
                "5 Melta*, 6 Vortex* (*one salvo per game), as well as its other torpedoes.")


def _ork_torps(dice: str) -> Dict:
    from .combat import dice_value_average
    return {"name": "Prow Torps", "weapon_type": "torpedo", "range_cm": 30,
            "strength": int(dice_value_average(dice)), "arcs": ["front"],
            "strength_dice": dice, "torpedo_type": "standard", "torpedo_speed": 30}


def ork_launcha_options(row: dict) -> List[Dict]:
    """Ork kroozers: "Replace prow heavy gunz with a prow torpedo launcha (30cm
    D6+N F) +Xpts" (Kill Kroozer: with the launcha, may drop both side heavy gunz
    to add +D6, 2D6+N, free). The zzapp gunz alternatives aren't playable yet."""
    import re
    notes = row.get("notes") or ""
    m = (re.search(r"prow torpedo launcha \(30cm (D6\+\d+) F\) (free|\+(\d+)pts)", notes)
         or re.search(r"prow torpedo launcha \(Speed 30cm, Strength (D6\+\d+), Front\) "
                      r"(free|for \+(\d+) points)", notes))
    if not m:
        return []
    dice, cost = m.group(1), int(m.group(3) or 0)
    opts = [{"name": f"Prow torpedo launcha ({dice})",
             "description": f"Replace the prow heavy gunz with a prow torpedo launcha "
                            f"(30cm S {dice}, F), {'free' if not cost else f'+{cost}pts'}.",
             "points_cost": cost,
             "effect": {"remove_weapons": ["Prow Heavy Gunz"], "add_weapon": _ork_torps(dice)},
             "restrictions": ["group:ork_prow"]}]
    if "may drop both side heavy gunz to add +D6" in notes:
        big = "2" + dice
        opts.append({"name": f"Prow torpedo launcha ({big}, no side heavy gunz)",
                     "description": f"The torpedo launcha with both side heavy gunz dropped to "
                                    f"add +D6 (30cm S {big}, F), +{cost}pts.",
                     "points_cost": cost,
                     "effect": {"remove_weapons": ["Prow Heavy Gunz", "Port Heavy Gunz",
                                                   "Starboard Heavy Gunz"],
                                "add_weapon": _ork_torps(big)},
                     "restrictions": ["group:ork_prow"]})
    return opts


INQ_LORD = "Ordo Malleus Inquisitor Lord (Ld 10)"
INQ_TORPS = "Refit: launch bays to Torpedo Salvo"


def inquisition_options(row: dict) -> List[Dict]:
    """Inquisition vessels: the Inquisitorial Cruiser's special refits (no
    change in cost), the Ordo Malleus Inquisitor Lord (Banisher Fleet: Ld 10,
    75pts, one free re-roll), Inferno Torpedoes (+20pts, owner ruling) and
    vortex torpedoes on the Inquisitor Lord's ship if it has torpedoes (+50pts,
    owner ruling)."""
    name = row["name"]
    opts: List[Dict] = []
    has_torps = bool(torpedo_strength(row))
    if name == "Inquisitorial Cruiser":
        opts += [
            {"name": "Refit: dorsal lances to Bombardment Cannon",
             "description": "No change in cost: Bombardment Cannon 30cm FP6 (L/F/R), the "
                            "Space Marine bombardment cannon rules.",
             "points_cost": 0,
             "effect": {"remove_weapons": ["Dorsal Lances"],
                        "add_weapon": {"name": "Dorsal Bombardment Cannon", "weapon_type": "battery",
                                       "range_cm": 30, "strength": 6,
                                       "arcs": ["left", "front", "right"],
                                       "hits_on": 4, "crit_on": 4}}},
            {"name": INQ_TORPS,
             "description": "No change in cost: Torpedo Salvo 30cm S6 (F), standard or "
                            "boarding torpedoes.",
             "points_cost": 0,
             "effect": {"remove_weapons": ["Launch Bays"],
                        "add_weapon": {"name": "Prow Torpedo Salvo", "weapon_type": "torpedo",
                                       "range_cm": 30, "strength": 6, "arcs": ["front"],
                                       "torpedo_type": "standard", "torpedo_speed": 30,
                                       "boarding_torpedoes": True}}},
        ]
    capital = row.get("hits") and row.get("hits") > 1 and "Grey Knights" not in name
    if capital:
        opts.append({"name": INQ_LORD,
                     "description": "Fleet commander (Banisher Fleet), 75pts: Ld 10, one free "
                                    "re-roll.",
                     "points_cost": 75,
                     "effect": {"set": {"leadership": 10, "leadership_table": ""},
                                "rerolls": 1,
                                "add_special_rules": ["fleet_commander"], "flagship": True},
                     "restrictions": ["fleet_unique"]})
        opts += [{"name": f"Inquisitor Lord: {n} extra re-roll{'s' if n > 1 else ''}",
                  "description": f"{n} more fleet commander re-roll{'s' if n > 1 else ''} "
                                 f"({25 * n}pts).",
                  "points_cost": 25 * n, "effect": {"rerolls": 1 + n},
                  "restrictions": ["group:inq_rerolls", f"requires:{INQ_LORD}"]}
                 for n in (1, 2)]
    torp_needs = [] if has_torps else ([f"requires:{INQ_TORPS}"] if name == "Inquisitorial Cruiser"
                                       else None)
    if torp_needs is not None:
        opts.append({"name": "Inferno Torpedoes",
                     "description": "+20pts (Ordo Hereticus). Melta torpedoes usable any number "
                                    "of times, as well as its other torpedoes; a torpedo-launcher "
                                    "critical hit inflicts D6 Fire results.",
                     "points_cost": 20,
                     "effect": {"add_special_rules": ["torpedo_type:inferno"]},
                     "restrictions": ["group:torpedo_type"] + torp_needs})
        if capital:
            opts.append({"name": "Vortex Torpedoes (Inquisitor Lord's ship)",
                         "description": "+50pts (Ordo Malleus). Vortex torpedoes, one salvo per "
                                        "game, as well as its other torpedoes.",
                         "points_cost": 50,
                         "effect": {"add_special_rules": ["torpedo_type:vortex"]},
                         "restrictions": ["group:torpedo_type", f"requires:{INQ_LORD}"]
                         + torp_needs})
    return opts


def refitted_torpedo_options(row: dict) -> List[Dict]:
    """Adeptus Mechanicus "refitted torpedoes +Npts" and Ork "torps to looted
    torps +20pts" in a ship's notes: a D6 roll at game start (owner ruling for
    Orks: each ship that buys them rolls)."""
    import re
    notes = row.get("notes") or ""
    launcha = ork_launcha_options(row)
    if launcha:
        opts = launcha
        m = re.search(r"torps to looted torps \+(\d+)pts", notes)
        if m:
            opts.append({"name": "Looted Torpedoes (D6 at game start)",
                         "description": f"+{m.group(1)}pts. Needs the torpedo launcha. {_REFIT_TABLE}",
                         "points_cost": int(m.group(1)),
                         "effect": {"add_special_rules": ["torpedo_roll:d6_refitted"]},
                         "restrictions": ["group:torpedo_type", "requires_any:"
                                          + "|".join(o["name"] for o in launcha)]})
        return opts
    if not torpedo_strength(row) and not any(
            "Torp" in (w.get("name") or "") for w in row.get("weapons") or []):
        return []
    m = re.search(r"refitted torpedoes \+(\d+)pts", notes)
    if m:
        return [{"name": "Refitted Torpedoes (D6 at game start)",
                 "description": f"+{m.group(1)}pts. {_REFIT_TABLE}",
                 "points_cost": int(m.group(1)),
                 "effect": {"add_special_rules": ["torpedo_roll:d6_refitted"]},
                 "restrictions": ["group:torpedo_type"]}]
    m = re.search(r"torps to looted torps \+(\d+)pts", notes)
    if m:
        return [{"name": "Looted Torpedoes (D6 at game start)",
                 "description": f"+{m.group(1)}pts. {_REFIT_TABLE}",
                 "points_cost": int(m.group(1)),
                 "effect": {"add_special_rules": ["torpedo_roll:d6_refitted"]},
                 "restrictions": ["group:torpedo_type"]}]
    return []


VSC_PROW = "Strike Cruiser Prow"


def venerable_strike_cruiser_options(row: dict) -> List[Dict]:
    """Designing a Venerable Strike Cruiser (Imperium p.137): the Strike
    Cruiser Prow (6+ prow armour and prow torpedoes 30cm S6 F, replacing any
    prow armament; free with 6+ prow armour, otherwise +25pts; already fitted
    on nova cannon ships), and short-burn torpedoes +5pts or barrage bombs
    +10pts instead of the free boarding torpedoes. Its own profile's refits
    can't be used."""
    opts: List[Dict] = []
    has_torps = bool(torpedo_strength(row))
    if not row.get("strike_cruiser_prow"):
        prow = [f"Prow {w['name']}" for w in row.get("weapons") or [] if w.get("location") == "Prow"]
        six = (row.get("armour") or {}).get("front") == 6
        opts.append({
            "name": VSC_PROW,
            "description": "6+ prow armour and prow torpedoes (30cm S6 F, standard or boarding), "
                           "replacing any prow armament; "
                           + ("free (already 6+ prow armour)." if six else "+25pts."),
            "points_cost": 0 if six else 25,
            "effect": {"remove_weapons": prow,
                       "add_weapon": {"name": "Prow Torps", "weapon_type": "torpedo",
                                      "range_cm": 30, "strength": 6, "arcs": ["front"],
                                      "torpedo_type": "standard", "torpedo_speed": 30,
                                      "boarding_torpedoes": True},
                       "set": {"armor_prow": "6+"},
                       # Ablative Prow Armour is "lost if prow torpedoes taken"
                       "remove_special_rules": ["ablative_prow_armor"]},
        })
    needs = [] if has_torps or row.get("strike_cruiser_prow") else [f"requires:{VSC_PROW}"]
    for key, label, cost in (("short_burn", "short burn torpedoes", 5),
                             ("barrage", "barrage bombs", 10)):
        opts.append({
            "name": f"Torpedoes: {label} (instead of boarding torpedoes)",
            "description": f"+{cost}pts.",
            "points_cost": cost,
            "effect": {"add_special_rules": [f"torpedo_type:{key}", "no_boarding_torps"]},
            "restrictions": ["group:torpedo_type"] + needs})
    return opts


# Fleet commanders (each faction's Fleet Composition; owner rulings for the
# Archmagos and Tau re-roll costs): (name, Ld or None, cost), free re-rolls,
# cost of each extra re-roll count (1, 2, 3 ...).
COMMANDERS = {
    "Imperial Navy": ([("Vice Admiral", 8, 50), ("Fleet Admiral", 9, 75),
                       ("Solar Admiral", 10, 100)], 1, [25, 50, 75]),
    "Chaos": ([("Chaos Lord", 8, 50), ("Chaos Warmaster", 9, 75)], 1, [25, 50]),
    "Adeptus Mechanicus": ([("Archmagos Explorator", 9, 50)], 0, [25, 50]),
    "Tau & Allies": ([("Kor'el", 8, 50), ("Kor'O", 9, 70)], 1, [25, 50]),
    "Rogue Traders": ([("Lord Captain", 8, 50), ("Venerable Lord Captain", 9, 75),
                       ("Pirate Captain", 8, 50)], 1, [25, 50]),
}
# Ork Bosses have no Ld of their own (the ship's rolled Ld; a Freebooter
# Kaptin adds +1) and get re-rolls only from a title (owner ruling)
ORK_BOSSES = [("Warboss", 40), ("Big Mek", 40), ("Freebooter Kaptin", 30)]
ORK_TITLES = [("Big Boss", 1, 20), ("Mega Boss", 2, 40)]


# Secondary commanders (s.5): +Ld (or a fixed Ld) and re-rolls usable only
# for their own ship or squadron (`own_rerolls`). (name, Ld effect, cost,
# fleet maximum, re-roll cost or None)
SECONDARY = {
    "Imperial Navy": ("Strategic Commander (+1 Ld, max 9)", "ld_bonus:1:9", 30, 3, 15),
    "Chaos": ("Aspiring Champion (+1 Ld, max 9)", "ld_bonus:1:9", 30, None, 15),
    "Adeptus Mechanicus": ("Magos Explorator (Ld 8)", 8, 25, 3, None),
}


def secondary_commander_options(faction: str) -> List[Dict]:
    """A secondary commander can't be the required commander and shares the
    commander group: no ship carries more than one commander of any kind."""
    if faction not in SECONDARY:
        return []
    name, ld, cost, most, rr = SECONDARY[faction]
    effect = ({"add_special_rules": [ld, "secondary_commander"]} if isinstance(ld, str)
              else {"set": {"leadership": ld, "leadership_table": ""},
                    "add_special_rules": ["secondary_commander"]})
    restr = ["group:fleet_commander"] + ([f"fleet_max:{most}"] if most else [])
    opts = [{"name": name, "description": f"Secondary commander, {cost}pts.",
             "points_cost": cost, "effect": effect, "restrictions": restr}]
    if rr:
        opts.append({"name": f"{name.split(' (')[0]}: re-roll",
                     "description": f"+{rr}pts: one re-roll for this ship or its squadron only.",
                     "points_cost": rr, "effect": {"set": {"own_rerolls": 1}},
                     "restrictions": [f"requires:{name}"]})
    return opts


def commander_names(faction_rule: str) -> List[str]:
    if faction_rule == "Orks":
        return [f"Ork {n}" for n, _ in ORK_BOSSES]
    tiers = COMMANDERS.get(faction_rule, ([], 0, []))[0]
    return [f"{n} (Ld {ld})" for n, ld, _ in tiers]


def fleet_commander_options(row: dict) -> List[Dict]:
    """The faction's fleet commander as options on a capital ship: fixed Ld
    (it supersedes the ship's), free and bought re-rolls, flagship. Ork
    Bosses (one per 500pts) instead keep the ship's rolled Ld and take a title
    for re-rolls."""
    from .booklet_ships import _ship_type
    if _ship_type(row) not in ("cruiser", "battleship"):
        return []
    rules = row.get("faction_rules") or []
    name = row["name"]
    if any(k in name for k in ("Commerce Vessel", "Nicassar", "Kroot")):
        return []                        # Demiurg field no commanders; allies
    if "Orks" in rules:
        names = commander_names("Orks")
        opts = [{"name": f"Ork {n}",
                 "description": f"Fleet commander, {cost}pts (one Boss per 500pts; one must "
                                f"lead at 500+pts). Uses the ship's rolled Leadership"
                                + ("; +1 to it." if n == "Freebooter Kaptin" else "."),
                 "points_cost": cost,
                 "effect": {"add_special_rules": ["fleet_commander"]
                            + (["ld_bonus:1"] if n == "Freebooter Kaptin" else []),
                            "flagship": True},
                 "restrictions": ["group:fleet_commander"]} for n, cost in ORK_BOSSES]
        opts += [{"name": f"Boss title: {t}",
                  "description": f"+{cost}pts: {r} fleet commander re-roll{'s' if r > 1 else ''}.",
                  "points_cost": cost, "effect": {"rerolls": r},
                  "restrictions": ["group:boss_title", "requires_any:" + "|".join(names)]}
                 for t, r, cost in ORK_TITLES]
        return opts
    faction = next((f for f in COMMANDERS if f in rules), None)
    if faction is None:
        return []
    tiers, free, extra = COMMANDERS[faction]
    names = commander_names(faction)
    opts = [{"name": f"{n} (Ld {ld})",
             "description": f"Fleet commander, {cost}pts: Ld {ld}"
                            + (f", {free} free re-roll." if free else "."),
             "points_cost": cost,
             "effect": {"set": {"leadership": ld, "leadership_table": ""},
                        "rerolls": free,
                        "add_special_rules": ["fleet_commander"], "flagship": True},
             "restrictions": ["fleet_unique", "group:fleet_commander"]}
            for n, ld, cost in tiers]
    opts += secondary_commander_options(faction)
    opts += [{"name": f"Commander: {k} extra re-roll{'s' if k > 1 else ''}",
              "description": f"{cost}pts.",
              "points_cost": cost, "effect": {"rerolls": free + k},
              "restrictions": ["group:commander_rerolls", "requires_any:" + "|".join(names)]}
             for k, cost in enumerate(extra, start=1)]
    return opts


# ── Imperial Navy profile refits (bfgxr/rules/01_imperial-navy.md roster notes) ──

_NC = {"name": "Prow Nova Cannon", "weapon_type": "nova_cannon", "range_cm": 150,
       "strength": 0, "arcs": ["front"], "min_range_cm": 30}


def _torps(strength: int) -> Dict:
    return {"name": "Prow Torps", "weapon_type": "torpedo", "range_cm": 30, "strength": strength,
            "arcs": ["front"], "torpedo_type": "standard", "torpedo_speed": 30}


def _macro(side_range: int, sets: Dict) -> List[Dict]:
    return [{"match": {"name": f"{side} Macrobatteries", "range_cm": side_range}, "set": sets}
            for side in ("Port", "Starboard")]


def _opt(name, desc, cost, effect, restrictions=()):
    return {"name": name, "description": desc, "points_cost": cost, "effect": effect,
            "restrictions": list(restrictions)}


def navy_refit_options(row: dict) -> List[Dict]:
    """The refits printed in Imperial Navy profiles. Each is matched on its note
    text, so a reworded export drops the option instead of keeping a stale one.
    Torpedo bomber purchases ("TB 20cm +Npts") wait on torpedo bombers firing
    their salvo (s.21); they aren't offered."""
    notes = row.get("notes") or ""
    opts: List[Dict] = []
    torps_from = ""                   # option names that give the ship torpedoes
    torp_strength = 0

    if "AB 30cm +5pts" in notes:
        from .booklet_ships import _IN_CRAFT
        opts.append(_opt("Attack craft: assault boats", "+5pts. Its launch bays may also "
                         "launch assault boats (30cm).", 5,
                         {"add_craft": {_IN_CRAFT["AB"]: 30}}))
    if "swap prow nova cannon for prow torpedoes (30cm S9 F), -10pts" in notes:      # Victory
        opts.append(_opt("Refit: prow torpedoes (S9) for the nova cannon",
                         "-10pts. Prow torpedoes 30cm S9 (F) instead of the prow nova cannon.",
                         -10, {"remove_weapons": ["Prow Nova Cannon"], "add_weapon": _torps(9)},
                         ["group:navy_prow"]))
        torps_from, torp_strength = opts[-1]["name"], 9
    if "swap prow torpedoes for prow nova cannon (30-150cm Template F) +20pts" in notes or \
            "May swap prow torpedoes for a prow nova cannon (30-150cm, Template, F), +20pts" in notes:
        opts.append(_opt("Refit: prow nova cannon for the torpedoes",
                         "+20pts. A prow nova cannon (30-150cm, F) instead of the prow torpedoes.",
                         20, {"remove_weapons": ["Prow Torps"], "add_weapon": dict(_NC)},
                         ["group:navy_prow", "excludes_group:torpedo_type"]))
    if "swap nova cannon for torpedo salvo (30cm S6 F), -20pts" in notes:            # Mercury
        opts.append(_opt("Refit: prow torpedoes (S6) for the nova cannon",
                         "-20pts. A torpedo salvo 30cm S6 (F) instead of the prow nova cannon.",
                         -20, {"remove_weapons": ["Prow Nova Cannon"], "add_weapon": _torps(6)},
                         ["group:navy_prow"]))
        torps_from, torp_strength = opts[-1]["name"], 6
    if "swap prow lances for prow torpedoes (30cm S6 F), no cost change" in notes:   # Dauntless
        opts.append(_opt("Refit: prow torpedoes (S6) for the lances",
                         "Free. Prow torpedoes 30cm S6 (F) instead of the prow lances.",
                         0, {"remove_weapons": ["Prow Lances"], "add_weapon": _torps(6)},
                         ["group:navy_prow"]))
        torps_from, torp_strength = opts[-1]["name"], 6
    if "45cm Macrobatteries to 60cm +10pts" in notes:                                 # Mercury
        opts.append(_opt("Refit: 45cm macrobatteries to 60cm", "+10pts.", 10,
                         {"modify_weapons": _macro(45, {"range_cm": 60})}))
    if "30cm Macrobatteries to 45cm +10pts" in notes:                                 # Tyrant
        opts.append(_opt("Refit: 30cm macrobatteries to 45cm", "+10pts.", 10,
                         {"modify_weapons": _macro(30, {"range_cm": 45})}))
    if "Macrobatteries to FP6 for 45cm range, -5pts" in notes:                        # Dominator
        opts.append(_opt("Refit: macrobatteries 45cm FP6", "-5pts. Port and starboard "
                         "macrobatteries 45cm FP6 instead of 30cm FP12.", -5,
                         {"modify_weapons": _macro(30, {"range_cm": 45, "strength": 6})}))
    if ("reduce its macrobatteries' range to 30cm to increase their firepower to 10" in notes
            or "reduce the range of its macrobatteries to 30cm in order to increase their "
               "firepower to 10" in notes):
        opts.append(_opt("Refit: macrobatteries 30cm FP10", "Free. Port and starboard "    # Exorcist
                         "macrobatteries 30cm FP10 instead of 45cm FP8.", 0,
                         {"modify_weapons": _macro(45, {"range_cm": 30, "strength": 10})}))
    if "Targeting Matrix (Macrobatteries get +1 left column-shift) +15pts" in notes:
        opts.append(_opt("Refit: Targeting Matrix", "+15pts. Macrobatteries get a column "
                         "shift to the left.", 15, {"add_special_rules": ["targeting_matrix"]}))
    if "Extra Turrets 2→3 +10pts" in notes:
        opts.append(_opt("Refit: Extra Turrets (2 to 3)", "+10pts.", 10,
                         {"stat_delta": {"turrets": 1}}))
    if "May buy one of: Prow Torps 30cm S6 (F) +25pts; Comms Uplink +1 Ld +20pts; " \
            "Improved Thrusters (+D6cm on All Ahead Full) +5pts" in notes \
            or "May also buy one of: Prow Torps 30cm S6 (F) +25pts; Comms Uplink +1 Ld +20pts; " \
            "Improved Thrusters (+D6cm on All Ahead Full) +5pts" in notes:            # grand cruisers
        opts += [
            _opt("Refit: Prow Torps (S6)", "+25pts. Prow torpedoes 30cm S6 (F); the ship "
                 "loses Ablative Prow Armour.", 25,
                 {"add_weapon": _torps(6), "remove_special_rules": ["ablative_prow_armor"]},
                 ["group:grand_cruiser_refit"]),
            _opt("Refit: Comms Uplink (+1 Ld)", "+20pts. +1 Leadership (max 10).", 20,
                 {"add_special_rules": ["ld_always:1"]}, ["group:grand_cruiser_refit"]),
            _opt("Refit: Improved Thrusters", "+5pts. +D6cm on All Ahead Full.", 5,
                 {"add_special_rules": ["improved_thrusters"]}, ["group:grand_cruiser_refit"]),
        ]
        torps_from, torp_strength = "Refit: Prow Torps (S6)", 6
    if "swap Macrobatteries for improved sensor array (+2 Ld vs enemy on special orders " \
            "instead of +1 Ld), no cost change" in notes:                             # Cobra
        opts.append(_opt("Refit: improved sensor array", "Free. No macrobattery; enemy "
                         "ships on special orders give +2 Ld instead of +1. The whole "
                         "squadron must match.", 0,
                         {"remove_weapons": ["Macrobattery"],
                          "add_special_rules": ["improved_sensor_array"]}))
    if torps_from and not torpedo_strength(row):
        opts += torpedo_type_options(row, torp_strength, torps_from)
    from .booklet_ships import _ship_type
    if _ship_type(row) in ("cruiser", "battleship"):
        # Bakka only (fleet_lists list_options): Fleet Defence Turrets from the
        # Mechanicus Gifts, and Veteran Captains as the secondary commanders
        opts.append(_opt("Refit: Fleet Defence Turrets", "+5pts (Bakka). -2 Turrets, but "
                         "+1 massed turret to every friendly ship within 15cm, itself "
                         "included (+3 at most as normal).", 5,
                         {"stat_delta": {"turrets": -2},
                          "add_special_rules": ["fleet_defence_turrets"]}))
        # Dominion only: a Space Marine Captain on an Imperial Navy reserve
        # capital ship (Space Marine Ld table; no longer an ally of convenience)
        smc = "Space Marine Captain"
        opts += [_opt(smc, "25pts (Dominion). The ship rolls Leadership on the Space Marine "
                      "table.", 25, {"set": {"leadership_table": "Astartes"},
                                     "add_special_rules": ["space_marine_captain"]},
                      ["group:fleet_commander"]),
                 _opt("Veteran honour guard (Space Marine Captain)", "+10pts. Double teleport "
                      "range; teleport attacks roll 2D6 and use the best.", 10,
                      {"add_special_rules": ["veteran_honour_guard"]}, [f"requires:{smc}"])]
        vc = "Veteran Captain (+1 Ld, max 10)"
        opts += [_opt(vc, "Secondary commander (Bakka), 30pts.", 30,
                      {"add_special_rules": ["ld_bonus:1:10", "secondary_commander"]},
                      ["group:fleet_commander", "fleet_max:3"]),
                 _opt("Veteran Captain: re-roll", "+15pts: one re-roll for this ship or its "
                      "squadron only.", 15, {"set": {"own_rerolls": 1}}, [f"requires:{vc}"])]
    return opts


# ── Adeptus Mechanicus Gifts (02_adeptus-mechanicus.md; one per capital ship) ──
# (D6, name, cost, effect). Vault of Technology's game-start roll uses the
# same table (mechanicus.roll_vault_of_technology).
MECHANICUS_GIFTS = [
    (1, "Emergency Energy Reserves", 0, {"add_special_rules": ["emergency_energy_reserves"]}),
    (2, "Fleet Defence Turrets", 5, {"stat_delta": {"turrets": -2},
                                     "add_special_rules": ["fleet_defence_turrets"]}),
    (3, "Advanced Engines", 5, {"stat_delta": {"speed": 5},          # Auxiliary Power Relays
                                "add_special_rules": ["secondary_reactors"]}),   # +2D6cm AAF
    (4, "Advanced Shields", 10, {"add_special_rules": ["overloaded_shields", "advanced_shields"]}),
    (5, "Advanced Weapons", 10, {"add_special_rules": ["targeting_matrix"],
                                 "modify_weapons": [{"match": {"name_prefix": "Dorsal Lance",
                                                               "weapon_type": "lance"},
                                                     "add": {"strength": 1}}]}),
    (6, "Vault of Technology", 0, {"add_special_rules": ["vault_of_technology"]}),
]
_GIFT_TEXT = {
    1: "While crippled, shields, turrets and weapons lose 25% instead of 50% (round down); "
       "Speed can't drop below 15cm.",
    2: "-2 Turrets, but +1 massed turret to every friendly ship within 15cm, itself included "
       "(+3 at most as normal).",
    3: "Auxiliary Power Relays (+5cm Speed) and Secondary Reactors (+2D6cm on All Ahead Full).",
    4: "Overloaded Shield Capacitors (a D6 per active shield after the enemy rolls to hit; "
       "each 6 discards a hit) and a right column shift on gunnery against it while its "
       "shields are up.",
    5: "Targeting Matrix (a left column shift on all gunnery) and +1 dorsal lance FP.",
    6: "Roll a D6 at the start of the game for a free Gift (on a 6 choose one).",
}


def mechanicus_gift_options(row: dict) -> List[Dict]:
    from .booklet_ships import _ship_type
    if _ship_type(row) not in ("cruiser", "battleship"):
        return []
    return [_opt(f"Gift: {name}", (f"+{cost}pts. " if cost else "Free. ") + _GIFT_TEXT[n],
                 cost, effect, ["group:mechanicus_gift"])
            for n, name, cost, effect in MECHANICUS_GIFTS]


def demiurg_war_host_options(row: dict) -> List[Dict]:
    """Demiurg War Host (Xenos p.101): no fleet commander, but up to two re-rolls
    for any Demiurg vessel in the fleet: one 25pts, two 75pts. Bought once, on
    any Demiurg commerce vessel (the re-rolls aren't lost with it)."""
    return [_opt(f"War Host re-roll{'s' if n > 1 else ''}: {n}",
                 f"{cost}pts (Demiurg War Host). {n} re-roll{'s' if n > 1 else ''} for any "
                 f"Demiurg vessel in the fleet.", cost, {"set": {"war_host_rerolls": n}},
                 ["group:war_host_rerolls"]) for n, cost in ((1, 25), (2, 75))]


def options_for(row: dict) -> List[Dict]:
    """Options for one booklet ship: Space Marine and Inquisition options,
    torpedo types and refits, and each faction's fleet commander."""
    rules = row.get("faction_rules") or []
    if row.get("roster_group") == "Venerable Strike Cruisers":
        # its own design options, plus the Master of the Fleet and honour guards
        return venerable_strike_cruiser_options(row) + [
            o for o in space_marine_options(row) if not o["name"].startswith("Torpedoes")]
    if "Space Marines" in rules:
        return space_marine_options(row)
    opts: List[Dict] = []
    if "Imperial Navy" in rules or "Chaos" in rules:
        opts = torpedo_type_options(row)
    if "Imperial Navy" in rules:
        opts += navy_refit_options(row)
    elif "Adeptus Mechanicus" in rules or "Orks" in rules:
        opts = refitted_torpedo_options(row)
        if "Adeptus Mechanicus" in rules:
            opts += mechanicus_gift_options(row)       # Tech-Priest Enginseers
    elif "Inquisition & Grey Knights" in rules:
        return inquisition_options(row)
    if "demiurg" in (row.get("roster_group") or "").lower() and \
            _ship_type_of(row) in ("cruiser", "battleship"):
        opts += demiurg_war_host_options(row)
    return opts + fleet_commander_options(row)


def _ship_type_of(row: dict) -> str:
    from .booklet_ships import _ship_type
    return _ship_type(row)


def ship_option_errors(entry, chosen: List[str]) -> List[str]:
    """Problems with one ship's chosen options: two from one group, or an
    option without the one it requires."""
    by_name = {u.name: u for u in entry.upgrades_available}
    errors, groups = [], {}
    for name in chosen:
        u = by_name.get(name)
        if u is None:
            continue
        for r in u.restrictions:
            if r.startswith("group:"):
                groups.setdefault(r[6:], []).append(name)
            elif r.startswith("requires:") and r[9:] not in chosen:
                errors.append(f"{name} needs {r[9:]}.")
            elif r.startswith("excludes_group:"):
                g = "group:" + r[len("excludes_group:"):]
                clash = [n for n in chosen if n in by_name and g in by_name[n].restrictions]
                if clash:
                    errors.append(f"{name} can't be taken with {', '.join(clash)}.")
            elif r.startswith("requires_any:"):
                need = r[len("requires_any:"):].split("|")
                if not any(n in chosen for n in need):
                    errors.append(f"{name} needs one of: {', '.join(need)}.")
    for names in groups.values():
        if len(names) > 1:
            errors.append(f"Choose only one of: {', '.join(names)}.")
    return errors


def fleet_option_errors(rows: List[tuple], total_points: int = 0) -> List[str]:
    """Fleet-wide option limits. rows: (ShipClassEntry, chosen option names).
    One Master of the Fleet (required at 750+ pts in a Space Marine fleet), and
    Strike Cruiser Variants on at most half the fleet's strike cruisers (round
    down)."""
    errors = []
    restr = [(e, n, r) for e, chosen in rows for n in chosen
             for u in e.upgrades_available if u.name == n for r in u.restrictions]
    unique = {}
    for e, n, r in restr:
        if r == "fleet_unique":
            unique[n] = unique.get(n, 0) + 1
    for n, c in unique.items():
        if c > 1:
            errors.append(f"Only one ship may take {n} ({c} chosen).")
    capped: Dict[str, List[int]] = {}
    for e, n, r in restr:
        if r.startswith("fleet_max:"):
            capped.setdefault(n, [int(r.split(":")[1]), 0])[1] += 1
    for n, (most, c) in capped.items():
        if c > most:
            errors.append(f"At most {most} ships may take {n} ({c} chosen).")
    strike = [chosen for e, chosen in rows if e.ship_class == "Strike Cruiser"]
    with_variant = sum(1 for chosen in strike if any(n.startswith("Variant:") for n in chosen))
    if with_variant > len(strike) // 2:
        errors.append(f"Strike Cruiser Variants: at most {len(strike) // 2} of the fleet's "
                      f"{len(strike)} strike cruisers (half, round down); {with_variant} chosen.")
    # Master of the Fleet: on a battle barge if the fleet has one (the Chapter
    # flagship, a Venerable Battle Barge or the Ultima, if present)
    mof_on = [e for e, chosen in rows if "Master of the Fleet (Ld 10)" in chosen]
    barges = [e for e, _ in rows if "Battle Barge" in e.ship_class]
    flagships = [e for e in barges if e.ship_class == "Ultima Battle Barge"
                 or "venerable" in e.special_rules]
    for e in mof_on:
        if flagships and e not in flagships:
            errors.append(f"The Master of the Fleet must ride the Chapter flagship "
                          f"({flagships[0].ship_class}), not the {e.ship_class}.")
        elif barges and e not in barges:
            errors.append(f"The Master of the Fleet must ride a battle barge, not the "
                          f"{e.ship_class}.")
    sm = [e for e, _ in rows if "space_marine_crew" in e.special_rules]
    if sm and len(sm) == len(rows) and total_points >= 750 and not unique.get(
            "Master of the Fleet (Ld 10)"):
        errors.append("A Space Marine fleet of 750+ pts needs a Master of the Fleet "
                      "(option on a battle barge).")
    return errors


def tactical_flexibility_refund(fleet_upgrades: List[List[str]], entries) -> int:
    """Points to add back when the fleet takes a Chapter tactic: its Strike
    Cruiser Variant refits lose the Tactical Flexibility discount.
    fleet_upgrades: each ship's chosen options; entries: the matching
    ShipClassEntry objects."""
    if not any(n.startswith("Chapter tactic:") for ups in fleet_upgrades for n in ups):
        return 0
    extra = 0
    for ups, entry in zip(fleet_upgrades, entries):
        for u in entry.upgrades_available:
            if u.name in ups:
                for r in u.restrictions:
                    if r.startswith("base_cost:"):
                        extra += int(r[10:]) - u.points_cost
    return extra
