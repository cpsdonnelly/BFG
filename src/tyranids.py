"""Tyranids, slice 1 (CLAUDE.md To do 19; bfgxr/rules/13_tyranids.md, Xenos
p.104-120): the catalog's Tyranid weapons, the bio-cruiser gene templates as
their own classes, weapon configurations (required choices per location,
copies of one weapon in one location combined), biomorphs, phage mines,
synapse nodes, Hive Mind re-rolls, and the three fleet lists' checks.

Pure logic. The faction rules in play (Instinctive Behaviour, synapse, spore
clouds, contact weapons, the crit table) are later slices; until they are
built every Tyranid ship stays unsupported (booklet_ships.UNBUILT_FACTION_RULES).
"""
import copy
import math
from typing import Dict, List, Optional, Tuple

ANTIBODY = "antibody"          # ordnance.CRAFT_STATS: multi-role fighter / assault boat, 15cm

LR = ["left", "front", "right"]


# ── Weapons (Tyranid Weapons, Xenos p.106-107) ─────────────────────────────────

def pyro_acid(location: str, rng: int, fp: int, arcs: List[str]) -> Dict:
    """Pyro-acid batteries: gunnery weapons; a crit they cause adds a Fire."""
    return {"name": f"{location} Pyro-Acid Battery".strip(), "weapon_type": "battery",
            "range_cm": rng, "strength": fp, "arcs": list(arcs), "pyro_acid": True}


def bio_plasma(location: str, rng: int, fp: int, arcs: List[str],
               name: str = "Bio-Plasma Spines") -> Dict:
    """Bio-plasma: lances that pass through shields and hit beyond 15cm only
    on a 6."""
    return {"name": f"{location} {name}".strip(), "weapon_type": "lance",
            "range_cm": rng, "strength": fp, "arcs": list(arcs), "bio_plasma": True}


def feeder_tendrils(strength: int, location: str = "Prow") -> Dict:
    """Base-contact weapon, Strength (update 58): a roll per tendril against
    the lowest Armour, each hit 1 damage + D3 raids, ignoring shields."""
    return {"name": f"{location} Feeder Tendrils", "weapon_type": "feeder_tendrils",
            "range_cm": 0, "strength": strength, "arcs": [], "contact": True}


def massive_claws(strength: int, location: str = "Prow") -> Dict:
    """Base-contact weapon, Strength: 4+ per point, 1 damage a hit ignoring
    shields, two hits grapple."""
    return {"name": f"{location} Massive Claws", "weapon_type": "massive_claws",
            "range_cm": 0, "strength": strength, "arcs": [], "contact": True}


def excretion_ducts(location: str, strength: int) -> Dict:
    """Hull-borers: boarding torpedoes, 20cm."""
    return {"name": f"{location} Excretion Ducts", "weapon_type": "torpedo", "range_cm": 20,
            "strength": strength, "arcs": ["front"], "torpedo_type": "standard",
            "torpedo_speed": 20, "boarding_torpedoes": True, "hull_borer": True}


def launch_glands(location: str, strength: int) -> Dict:
    """Launch glands: launch bays carrying antibodies (15cm multi-role
    fighter / assault boat)."""
    return {"name": f"{location} Launch Glands", "weapon_type": "launch_bay",
            "range_cm": 0, "strength": strength, "arcs": [],
            "craft_types": [ANTIBODY], "craft_speeds": {ANTIBODY: 15}, "craft_speed": 15}


def merge_weapon(weapons: List[Dict], w: Dict) -> None:
    """"Where the ship has multiple copies of the same weapon in the same
    location, combine the weapons' firepower or strength together and treat it
    as a single weapon system." """
    for have in weapons:
        if (have.get("name") == w.get("name") and have.get("weapon_type") == w.get("weapon_type")
                and have.get("arcs") == w.get("arcs") and have.get("range_cm") == w.get("range_cm")):
            have["strength"] = have.get("strength", 0) + w.get("strength", 0)
            return
    weapons.append(copy.deepcopy(w))


# ── Profiles parsed from the booklet text the export leaves raw ────────────────

def proteus_weapons() -> List[Dict]:
    """The Proteus's printed armament: the export parses its batteries and
    spines; tendrils, launch glands and excretion ducts are raw text."""
    return [feeder_tendrils(3),
            pyro_acid("Dorsal", 45, 12, LR), pyro_acid("Keel", 45, 12, LR),
            bio_plasma("Dorsal", 30, 3, LR), bio_plasma("Keel", 30, 3, LR),
            launch_glands("Port", 6), launch_glands("Starboard", 6),
            excretion_ducts("Prow", 10)]


SYNAPSE = {"Proteus Class Hive Ship": (10, 60), "Charybdis Class Hive Ship": (8, 45)}
NOMINAL_LD = 7          # "uses a nominal leadership value of 7"


def base_rules(row: dict) -> List[str]:
    """Special rules every Tyranid profile carries (catalog)."""
    name = row["name"]
    rules = ["tyranid"]
    if name in SYNAPSE:
        ld, rng = SYNAPSE[name]
        rules.append(f"synapse:{ld}:{rng}")
    if name == "Proteus Class Hive Ship":
        rules += ["extremely_ponderous", "aaf_2d6"]
    if name == "Charybdis Class Hive Ship":
        rules.append("charybdis_ponderous")      # CtNH only with solar vanes + discharge vents
    notes = (row.get("notes") or "").lower()
    if "bonded exo-plating" in notes:
        rules.append("bonded_exo_plating")
    if "pheromone sprayers" in notes:
        rules.append("pheromone_sprayers")
    if "living barrier" in notes:
        rules.append("living_barrier")
    if "slow gestation" in notes:
        rules.append("slow_gestation")
    if (row.get("shields_raw") or "") == "SC":
        rules.append("spore_cloud")              # shields = spore cysts
    return rules


# ── Bio-cruiser gene templates (Xenos pp.112-113) as catalog classes ───────────

TEMPLATES = {
    # name: (cost, cyst change, rules, prow tendrils replaced by claws S2)
    "Guardian": (0, -1, ["living_barrier"], False),
    "Scylla": (15, 0, [], False),
    "Prowler": (20, -1, ["pheromone_sprayers"], False),
    "Carnivore": (25, 0, ["bonded_exo_plating"], True),
}
BIO_CRUISER = "Tyranid Bio-Cruiser"
GESTATING_SCYLLA = "Scylla Strain Bio-Cruiser w/ Synapse Node"
GESTATING_SCYLLA_POINTS = 100      # Gestating Fleet list price, template and node included


def template_class(template: str) -> str:
    return f"{BIO_CRUISER} ({template})"


def template_of(ship_class: str) -> Optional[str]:
    if ship_class == GESTATING_SCYLLA:
        return "Scylla"
    for t in TEMPLATES:
        if ship_class == template_class(t):
            return t
    return None


def template_rows(rows: List[dict]) -> List[dict]:
    """The bio-cruiser "must then select one of the following gene templates":
    one catalog class per template, plus the Gestating Fleet's Scylla with its
    synapse node (Ld8, 30cm; 100pts in that list). The template's changes are
    built in (spore cysts, rules, the Carnivore's claws); its weapon choices
    are options (weapon_options)."""
    base = next((r for r in rows if r["faction"] == "Tyranids" and r["name"] == BIO_CRUISER), None)
    if base is None:
        return []
    out = []
    for t, (cost, cysts, _rules, _claws) in TEMPLATES.items():
        v = copy.deepcopy(base)
        v["name"] = template_class(t)
        v["base_class"] = BIO_CRUISER
        v["gene_template"] = t
        v["points"] = base["points"] + cost
        v["points_raw"] = str(v["points"])
        v["turrets"] = max(0, (base.get("turrets") or 0) + cysts)
        out.append(v)
    g = copy.deepcopy(base)
    g.update(name=GESTATING_SCYLLA, base_class=BIO_CRUISER, gene_template="Scylla",
             points=GESTATING_SCYLLA_POINTS, points_raw=str(GESTATING_SCYLLA_POINTS),
             synapse_node=(8, 30))
    out.append(g)
    return out


def template_profile(row: dict, kw: dict) -> None:
    """Apply a template row's built-in changes to convert_row's keywords."""
    t = row.get("gene_template")
    if not t:
        return
    _cost, _cysts, rules, claws = TEMPLATES[t]
    kw["special_rules"] = list(kw["special_rules"]) + [r for r in rules
                                                       if r not in kw["special_rules"]]
    if claws:
        kw["weapons"] = [w for w in kw["weapons"] if w.get("weapon_type") != "feeder_tendrils"]
        kw["weapons"].append(massive_claws(2))
    if "bonded_exo_plating" in kw["special_rules"]:
        _exo(kw)
    if row.get("synapse_node"):
        ld, rng = row["synapse_node"]
        kw["special_rules"].append(f"synapse:{ld}:{rng}")
        kw["special_rules"].append("synapse_node")


def _exo(kw: dict) -> None:
    """Bonded exo-plating: 6+ Armour, a 4+ save, no spore cysts (so no spore
    cloud either)."""
    kw["armor_prow"] = kw["armor_side"] = "6+"
    kw["turrets"] = 0
    kw["shields_max"] = 0
    kw["special_rules"] = [r for r in kw["special_rules"] if r != "spore_cloud"]


def finish_profile(row: dict, kw: dict) -> None:
    """Tyranid profile keywords: fixed Ld (synapse creatures their own, others
    the nominal 7 until synapse sets it), shields = spore cysts, the Proteus's
    raw armament, base prow tendrils, gene templates, exo-plating."""
    kw["leadership_table"] = ""
    ld = next((int(r.split(":")[1]) for r in kw["special_rules"] if r.startswith("synapse:")),
              None)
    if row.get("synapse_node"):
        ld = row["synapse_node"][0]
    kw["leadership"] = ld or NOMINAL_LD
    if row["name"] == "Proteus Class Hive Ship":
        kw["weapons"] = proteus_weapons()
    raw = row.get("armament_raw") or ""
    if raw.startswith("Prow Feeder Tendrils Str") and row["name"] != "Proteus Class Hive Ship":
        kw["weapons"] = [feeder_tendrils(int(raw.split("Str ")[1].split()[0]))]
    if "spore_cloud" in kw["special_rules"]:
        kw["shields_max"] = kw["turrets"]
    template_profile(row, kw)
    if "bonded_exo_plating" in kw["special_rules"]:
        _exo(kw)
    if kw["special_rules"] and "synapse_node" in kw["special_rules"]:
        kw["leadership"] = row["synapse_node"][0]


# ── Weapon configurations (Xenos pp.111-115) ───────────────────────────────────

def _w_prow_bio():
    return {
        "Excretion Ducts": (15, excretion_ducts("Prow", 4)),
        "Massive Claws": (10, massive_claws(2)),
        "Pyro-acid Battery": (10, pyro_acid("Prow", 30, 4, LR)),
        "Feeder Tendrils": (5, feeder_tendrils(1)),
    }


def _w_thorax_bio():
    return {
        "Excretion Ducts": (15, excretion_ducts("Thorax", 4)),
        "Bio-plasma Spines": (10, bio_plasma("Thorax", 30, 2, ["front"])),
        "Pyro-acid Battery": (10, pyro_acid("Thorax", 30, 4, LR)),
        "Feeder Tendrils": (5, feeder_tendrils(1, "Thorax")),
    }


def _ps(kind: str, n: int = 1) -> List[Dict]:
    """A port and starboard weapon set ("each selection provides the chosen
    weapon on both the port and starboard side, firing Left and Right")."""
    if kind == "Pyro-acid Batteries":
        return [pyro_acid("Port", 30, 4 * n, ["left"]), pyro_acid("Starboard", 30, 4 * n, ["right"])]
    if kind == "Bio-plasma Discharges":
        return [bio_plasma("Port", 15, 2 * n, ["left"], "Bio-Plasma Discharge"),
                bio_plasma("Starboard", 15, 2 * n, ["right"], "Bio-Plasma Discharge")]
    return [launch_glands("Port", n), launch_glands("Starboard", n)]


PS_KINDS = ("Pyro-acid Batteries", "Bio-plasma Discharges", "Launch Glands")

# Per class: location -> (min, max, allowed choices or None for all).
# "ps" counts port / starboard selections (copies allowed).
_BIO_SLOTS = {
    "Guardian": {"prow": (0, 0, ()), "thorax": (1, 1, ("Excretion Ducts", "Bio-plasma Spines",
                                                      "Pyro-acid Battery")), "ps": (1, 1)},
    "Scylla": {"prow": (1, 1, None), "thorax": (1, 1, ("Excretion Ducts", "Bio-plasma Spines",
                                                      "Pyro-acid Battery")), "ps": (0, 2)},
    "Prowler": {"prow": (1, 1, ("Pyro-acid Battery", "Feeder Tendrils")),
                "thorax": (1, 1, ("Pyro-acid Battery", "Feeder Tendrils")), "ps": (0, 0)},
    "Carnivore": {"prow": (1, 1, ("Excretion Ducts", "Massive Claws", "Feeder Tendrils")),
                  "thorax": (2, 2, None), "ps": (0, 0)},
}

_CHARYBDIS = {
    "prow": {"Pyro-acid Battery": (30, pyro_acid("Prow", 45, 8, ["front"])),
             "Excretion Ducts": (25, excretion_ducts("Prow", 8)),
             "Bio-plasma Spines": (20, bio_plasma("Prow", 30, 4, ["front"])),
             "Massive Claws": (15, massive_claws(3))},
    "thorax": {"Pyro-acid Battery": (30, pyro_acid("Thorax", 45, 8, ["front"])),
               "Bio-plasma Spines": (20, bio_plasma("Thorax", 30, 4, ["front"])),
               "Launch Glands": (20, launch_glands("Thorax", 2))},
}

_ESCORT = {
    # class: {choice: (cost, weapon)}; "Each ... in the same squadron must have
    # the same weapon"
    "Kraken": {"Pyro-acid Battery": (15, pyro_acid("Prow", 30, 6, ["front"])),
               "Bio-plasma Discharge": (10, bio_plasma("Prow", 15, 2, ["front"],
                                                       "Bio-Plasma Discharge")),
               "Excretion Ducts": (10, excretion_ducts("Prow", 2)),
               "Massive Claws": (10, massive_claws(2)),
               "Feeder Tendrils": (5, feeder_tendrils(1))},
    "Vanguard Drone": {"Pyro-acid Battery": (0, pyro_acid("Prow", 30, 4, ["front"])),
                       "Feeder Tendrils": (0, feeder_tendrils(1))},
    "Escort Drone": {"Pyro-acid Battery": (0, pyro_acid("Prow", 30, 4, ["front"])),
                     "Bio-plasma Discharge": (0, bio_plasma("Prow", 15, 2, ["front"],
                                                            "Bio-Plasma Discharge")),
                     "Excretion Ducts": (0, excretion_ducts("Prow", 2)),
                     "Feeder Tendrils": (0, feeder_tendrils(1))},
}


def _o(name, desc, cost, effect, restrictions=()):
    return {"name": name, "description": desc, "points_cost": cost, "effect": effect,
            "restrictions": list(restrictions)}


def _merge(*ws) -> Dict:
    return {"merge_weapons": [copy.deepcopy(w) for w in ws]}


def weapon_options(row: dict) -> List[Dict]:
    """The weapon configuration of one Tyranid class as options, each tagged
    "tyranid_slot:<location>[:<copies>]" for config_errors."""
    name = row["name"]
    opts: List[Dict] = []
    t = row.get("gene_template")
    if t:
        slots = _BIO_SLOTS[t]
        for loc, table in (("prow", _w_prow_bio()), ("thorax", _w_thorax_bio())):
            lo, hi, allowed = slots[loc]
            for choice, (cost, w) in table.items():
                if hi and (allowed is None or choice in allowed):
                    opts.append(_o(f"{loc.title()}: {choice}", f"+{cost}pts.", cost, _merge(w),
                                   [f"tyranid_slot:{loc}"]))
        lo, hi = slots["ps"]
        for kind in PS_KINDS if hi else ():
            for n in range(1, hi + 1):
                opts.append(_o(f"Port / Starboard: {kind}" + (f" x{n}" if hi > 1 else ""),
                               f"+{20 * n}pts.", 20 * n, _merge(*_ps(kind, n)),
                               [f"tyranid_slot:ps:{n}", "group:tyranid_ps"]))
    elif name == "Charybdis Class Hive Ship":
        for loc, table in _CHARYBDIS.items():
            for choice, (cost, w) in table.items():
                opts.append(_o(f"{loc.title()}: {choice}", f"+{cost}pts.", cost, _merge(w),
                               [f"tyranid_slot:{loc}"]))
        for kind in PS_KINDS:
            for n in (1, 2, 3):
                opts.append(_o(f"Port / Starboard: {kind} x{n}", f"+{20 * n}pts.", 20 * n,
                               _merge(*_ps(kind, n)), [f"tyranid_slot:ps:{n}",
                                                       f"group:tyranid_ps_{kind[:4]}"]))
    elif name in _ESCORT:
        for choice, (cost, w) in _ESCORT[name].items():
            opts.append(_o(f"Weapon: {choice}", f"+{cost}pts." if cost else "Free.", cost,
                           _merge(w), ["tyranid_slot:weapon", "group:tyranid_weapon"]))
    return opts


def slot_limits(ship_class: str) -> Dict[str, Tuple[int, int]]:
    t = template_of(ship_class)
    if t:
        s = _BIO_SLOTS[t]
        return {"prow": s["prow"][:2], "thorax": s["thorax"][:2], "ps": s["ps"]}
    if ship_class == "Charybdis Class Hive Ship":
        return {"prow": (1, 1), "thorax": (1, 1), "ps": (0, 3)}
    if ship_class in _ESCORT:
        return {"weapon": (1, 1)}
    return {}


def gland_strength(entry, chosen: List[str]) -> int:
    """Total launch gland strength the chosen configuration gives."""
    d = {"weapons": copy.deepcopy(entry.weapons), "special_rules": []}
    by = {u.name: u for u in entry.upgrades_available}
    for n in chosen:
        for w in by[n].effect.get("merge_weapons", []) if n in by else []:
            merge_weapon(d["weapons"], w)
    return sum(w.get("strength", 0) for w in d["weapons"] if w.get("weapon_type") == "launch_bay")


def config_errors(entry, chosen: List[str]) -> List[str]:
    """Weapon configuration problems for one Tyranid ship: each location's
    required number of choices, the Carnivore's two different thorax weapons,
    biomorph limits and the phage mines' price matching its glands."""
    by = {u.name: u for u in entry.upgrades_available}
    used: Dict[str, int] = {}
    for n in chosen:
        for r in (by[n].restrictions if n in by else []):
            if r.startswith("tyranid_slot:"):
                parts = r.split(":")
                used[parts[1]] = used.get(parts[1], 0) + (int(parts[2]) if len(parts) > 2 else 1)
    errors = []
    for loc, (lo, hi) in slot_limits(entry.ship_class).items():
        n = used.get(loc, 0)
        label = {"ps": "port / starboard weapon sets", "weapon": "weapon"}.get(loc, f"{loc} weapon")
        if n < lo or n > hi:
            want = f"{lo}" if lo == hi else f"{lo}-{hi}"
            errors.append(f"{entry.ship_class}: choose {want} {label}{'s' if hi > 1 and loc != 'ps' else ''} "
                          f"({n} chosen).")
    bio = [n for n in chosen if n in by and "tyranid_biomorph" in by[n].restrictions]
    most = biomorph_limit(entry, chosen)
    if len(bio) > most:
        errors.append(f"{entry.ship_class}: at most {most} biomorph{'s' if most > 1 else ''} "
                      f"({len(bio)} chosen).")
    phage = [n for n in chosen if n.startswith("Phage mines")]
    if phage:
        s = gland_strength(entry, chosen)
        want = phage_cost(entry.ship_class, s)
        got = by[phage[0]].points_cost if phage[0] in by else 0
        if not s:
            errors.append(f"{entry.ship_class}: phage mines need launch glands.")
        elif got != want:
            errors.append(f"{entry.ship_class}: phage mines for launch glands of strength {s} "
                          f"cost {want}pts; take that option.")
    return errors


# ── Biomorphs (Xenos p.109) ────────────────────────────────────────────────────

HIVE_SHIPS = ("Proteus Class Hive Ship", "Charybdis Class Hive Ship")


def is_hive_ship(entry_or_class, rules=()) -> bool:
    """Hive ships for biomorph limits; a Scylla with a synapse node counts."""
    cls = getattr(entry_or_class, "ship_class", entry_or_class)
    rules = list(rules) or list(getattr(entry_or_class, "special_rules", []))
    return cls in HIVE_SHIPS or "synapse_node" in rules


def biomorph_limit(entry, chosen: List[str] = ()) -> int:
    """Hive ships three, other capital ships two, escort squadrons one."""
    if entry.ship_type == "escort":
        return 1
    hive = is_hive_ship(entry) or "Minor Synapse Node (Ld7, 30cm)" in (chosen or [])
    return 3 if hive else 2


def _pct(points: int) -> int:
    """10% of the base cost, rounded up to the nearest 5 points."""
    return int(math.ceil(points * 0.10 / 5.0) * 5)


def biomorph_options(row: dict, ship_type: str) -> List[Dict]:
    """Biomorphs for one class. Escort costs are per escort; a percentage
    cost for an escort is 10% of its own cost, not rounded (reading: the
    booklet rounds the squadron's total, which the builder can't price)."""
    name = row["name"]
    escort = ship_type == "escort"
    capital = not escort
    pts = row.get("points") or 0
    hive = name in HIVE_SHIPS or bool(row.get("synapse_node")) or row.get("gene_template") == "Scylla"
    pct = (pts // 10 if escort else _pct(pts))
    table = [
        ("Solar Vanes", 5 if escort else 10, {"stat_delta": {"speed": 5}}, True),
        ("Adrenaline Sacs", 5 if escort else 10, {"add_special_rules": ["adrenaline_sacs"]}, True),
        ("Psychic Scream", 15, {"add_special_rules": ["psychic_scream"]}, hive and capital),
        ("Extra Discharge Vents", 10, {"add_special_rules": ["turn_distance_minus5"]}, capital),
        ("Extra Spore Cysts", 15, {"stat_delta": {"turrets": 1, "shields_max": 1}},
         capital and name != "Proteus Class Hive Ship"),
        ("Reinforced Carapace", 20, {"stat_delta": {"hits_max": 2}}, capital),
        ("Mucous Membrane", pct, {"add_special_rules": ["mucous_membrane"]}, True),
        ("Accelerated Healing", 10, {"add_special_rules": ["repair_dice:2"]}, capital),
        ("Vanguard Link", 10 if escort else 20, {"add_special_rules": ["vanguard_link"]}, True),
        ("Tenacity", pct, {"add_special_rules": ["tenacity"]}, True),
        ("Spore Overdrive", 10, {"add_special_rules": ["spore_overdrive"]}, capital),
    ]
    out = []
    for bname, cost, eff, ok in table:
        if not ok:
            continue
        if bname == "Extra Spore Cysts" and ("bonded" in (row.get("notes") or "").lower()
                                             or row.get("gene_template") == "Carnivore"):
            continue
        if bname == "Psychic Scream" and row.get("gene_template") == "Scylla" \
                and not row.get("synapse_node"):
            out.append(_o(f"Biomorph: {bname}", f"+{cost}pts (hive ships only).", cost, eff,
                          ["tyranid_biomorph", "requires:Minor Synapse Node (Ld7, 30cm)"]))
            continue
        out.append(_o(f"Biomorph: {bname}", f"+{cost}pts" + (" per escort." if escort else "."),
                      cost, eff, ["tyranid_biomorph"]))
    return out


# ── Phage mines, synapse nodes, Hive Mind re-rolls ─────────────────────────────

def phage_cost(ship_class: str, gland_s: int) -> int:
    """Proteus +60; others +5 per point of launch gland strength."""
    return 60 if ship_class == "Proteus Class Hive Ship" else 5 * gland_s


def _possible_gland_strengths(row: dict) -> List[int]:
    name = row["name"]
    if name == "Proteus Class Hive Ship":
        return [12]
    if name == "Charybdis Class Hive Ship":
        return [s for s in range(2, 9, 2)]            # thorax 2 and/or 1-3 sets of 2
    t = row.get("gene_template")
    if t in ("Guardian",):
        return [2]
    if t == "Scylla":
        return [2, 4]
    return []


def other_options(row: dict) -> List[Dict]:
    name = row["name"]
    opts = []
    for s in _possible_gland_strengths(row):
        cost = phage_cost(name, s)
        label = "Phage mines" if name == "Proteus Class Hive Ship" else f"Phage mines (glands S{s})"
        opts.append(_o(label, f"+{cost}pts: the launch glands also count as mine launchers "
                       "(each hull hit a Fire critical).", cost,
                       {"add_special_rules": ["phage_mines"]}, ["group:phage_mines"]))
    if row.get("gene_template") == "Scylla" and not row.get("synapse_node"):
        opts.append(_o("Minor Synapse Node (Ld7, 30cm)", "+5pts: a synapse creature with Ld7 "
                       "and 30cm synapse range (a hive ship for biomorph limits).", 5,
                       {"add_special_rules": ["synapse:7:30", "synapse_node"],
                        "set": {"leadership": 7}}))
    if name in HIVE_SHIPS:
        opts.append(_o("Hive Mind re-roll", "+25pts: works exactly like a fleet commander "
                       "re-roll (reading: one per primary hive ship).", 25,
                       {"rerolls": 1, "add_special_rules": ["fleet_commander"], "flagship": True},
                       ["fleet_unique"]))   # the engine keeps one fleet re-roll pool
    if name == "Charybdis Class Hive Ship":
        opts.append(_o("Alpha Synapse Node (Ld9)", "+40pts: Ld9.", 40,
                       {"add_special_rules": ["synapse:9:45"],
                        "remove_special_rules": ["synapse:8:45"], "set": {"leadership": 9}}))
    if row.get("gene_template") == "Scylla":
        req = [] if row.get("synapse_node") else ["requires:Minor Synapse Node (Ld7, 30cm)"]
        for k, cost in ((1, 15), (2, 30)):
            opts.append(_o(f"Hive Mind re-rolls: {k}", f"+{cost}pts: usable only for its own "
                           "command checks.", cost, {"set": {"own_rerolls": k}},
                           ["group:scylla_rerolls"] + req))
    return opts


def options(row: dict, ship_type: str) -> List[Dict]:
    """Every fleet-builder option for a Tyranid class (the Infested Space
    Station "may not be given any biomorphs or other refits")."""
    if row["name"] in ("Infested Space Station", "Spore Field", "Orbital Defence Spores"):
        return []
    return weapon_options(row) + biomorph_options(row, ship_type) + other_options(row)


# ── Fleet lists (Xenos pp.118-120) ─────────────────────────────────────────────

def _is_synapse_scylla(r: Dict) -> bool:
    return (r["entry"].ship_class == GESTATING_SCYLLA
            or "Minor Synapse Node (Ld7, 30cm)" in r.get("upgrades", []))


def _escort_count(rows: List[Dict], classes=None) -> int:
    """Escorts, Kraken counting as two."""
    return sum(2 if r["entry"].ship_class == "Kraken" else 1 for r in rows
               if r["entry"].ship_type == "escort"
               and (classes is None or r["entry"].ship_class in classes))


def fleet_errors(kind: str, rows: List[Dict], fleet_points: int) -> List[str]:
    """The Tyranid lists' own limits (the sections' ships and costs are in
    fleet_list_data_other)."""
    errors: List[str] = []
    cls = [r["entry"].ship_class for r in rows]
    if kind == "hive":
        prot = cls.count("Proteus Class Hive Ship")
        chary = cls.count("Charybdis Class Hive Ship")
        scylla = sum(1 for r in rows if _is_synapse_scylla(r))
        if not prot + chary:
            errors.append("Tyranid Hive Fleet: at least one primary hive ship (a Proteus or "
                          "Charybdis) is required.")
        if prot and fleet_points < 2000:
            errors.append("A Proteus hive ship needs a fleet worth at least 2000 points.")
        bio = sum(1 for c in cls if template_of(c))
        if bio > 3 * chary + 6 * prot:
            errors.append(f"Bio-cruisers: {bio}, at most three per Charybdis and six per "
                          f"Proteus ({3 * chary + 6 * prot}).")
        need = 4 * scylla + 6 * chary + 12 * prot
        extra = 8 * scylla + 12 * chary + 24 * prot
        drones = _escort_count(rows, ["Escort Drone"])
        if drones < need:
            errors.append(f"Escorts: {need} escort drones required (4 per synapse Scylla, 6 per "
                          f"Charybdis, 12 per Proteus); {drones} taken.")
        esc = _escort_count(rows)
        if esc > need + extra:
            errors.append(f"Escorts: {esc} (Kraken count two), at most {need + extra}.")
    elif kind == "gestating":
        scylla = cls.count(GESTATING_SCYLLA)
        if not scylla:
            errors.append("Tyranid Gestating Fleet: at least one Scylla strain bio-cruiser with "
                          "a synapse node is required.")
        bio = sum(1 for c in cls if template_of(c) and c != GESTATING_SCYLLA)
        if bio > 2 * scylla:
            errors.append(f"Bio-cruisers: {bio}, at most two per Scylla ({2 * scylla}).")
        need, extra = 4 * scylla, 8 * scylla
        drones = _escort_count(rows, ["Escort Drone"])
        if drones < need:
            errors.append(f"Escorts: {need} escort drones required (4 per Scylla); "
                          f"{drones} taken.")
        esc = _escort_count(rows)
        if esc > need + extra:
            errors.append(f"Escorts: {esc} (Kraken count two), at most {need + extra}.")
    return errors


# ── Synapse and Instinctive Behaviour (Xenos p.104-105), slice 2b ──────────────
#
# Turn state lives in GameState.tyranid_state[str(player)]:
#   {"turn": turn key, "controlled": [ship ids], "failed": [creature ids],
#    "instinct": {ship id: {"action", "order", "target"}}}

def synapse(ship) -> Optional[Tuple[int, float]]:
    """(Ld, range) of a synapse creature that can use synaptic control now:
    not destroyed or a hulk, not with its synapse link severed."""
    for r in getattr(ship, "special_rules", None) or []:
        if r.startswith("synapse:"):
            if ship.status != "active" or any(
                    c.get("crit_type") == "synapse_severed" for c in ship.critical_damage):
                return None
            _t, ld, rng = r.split(":")
            return int(ld), float(rng)
    return None


def is_synapse_creature(ship) -> bool:
    return any(r.startswith("synapse:") for r in (getattr(ship, "special_rules", None) or []))


def is_tyranid(ship) -> bool:
    return "tyranid" in (getattr(ship, "special_rules", None) or [])


def _live(gs, player):
    return [s for s in gs.player_ships(player) if s.status == "active" and not s.is_disengaged]


def unit_of(gs, ship) -> List:
    """A ship's unit: its squadron's members in play, or the ship alone."""
    if not ship.squadron_id:
        return [ship]
    mates = [s for s in _live(gs, ship.player) if s.squadron_id == ship.squadron_id]
    return mates or [ship]


def creatures(gs, player) -> List:
    return [s for s in _live(gs, player) if synapse(s)]


def vanguard_fleet(gs, player) -> bool:
    """A Tyranid fleet with no synapse creatures (the Vanguard Fleet list;
    reading: ships don't carry their list, so a fleet without synapse
    creatures is played as one): every ship or squadron may try a command
    check of its own to ignore Instinctive Behaviour."""
    own = [s for s in gs.player_ships(player) if is_tyranid(s)]
    return bool(own) and not any(is_synapse_creature(s) for s in own)


def unit_ld(gs, ship) -> int:
    """A Vanguard fleet's Leadership: Prowlers Ld7 +1 per other Prowler in
    their squadron (max 10), escort squadrons Ld = surviving ships (Kraken two,
    min 6, max 10). Otherwise the ship's own Ld."""
    unit = unit_of(gs, ship)
    if vanguard_fleet(gs, ship.player):
        if ship.ship_type == "escort":
            n = sum(2 if s.ship_class == "Kraken" else 1 for s in unit)
            return max(6, min(10, n))
        if "pheromone_sprayers" in ship.special_rules and ship.ship_type != "escort":
            others = sum(1 for s in unit if s.id != ship.id and "pheromone_sprayers" in s.special_rules)
            return min(10, 7 + others)
    return ship.leadership


def _state(gs, player) -> Dict:
    st = dict(getattr(gs, "tyranid_state", None) or {})
    mine = st.get(str(player)) or {}
    key = f"{gs.turn_number}:{player}"
    if mine.get("turn") != key:
        mine = {"turn": key, "controlled": [], "failed": [], "instinct": {}}
        st[str(player)] = mine
        gs.tyranid_state = st
    return mine


def _save(gs, player, mine) -> None:
    st = dict(getattr(gs, "tyranid_state", None) or {})
    st[str(player)] = mine
    gs.tyranid_state = st


def controlled(gs, ship) -> bool:
    return ship.id in _state(gs, ship.player)["controlled"]


def in_range(creature, ship) -> bool:
    syn = synapse(creature)
    return bool(syn) and creature.distance_to(ship) <= syn[1] + 1e-9


def control_candidates(gs, creature) -> List:
    """Units (their lead ship) the creature may still try to control: any of
    their ships within its synapse range (itself included), not yet controlled
    this turn, not with a severed synapse link, Tyranid."""
    mine = _state(gs, creature.player)
    if creature.id in mine["failed"] or not synapse(creature):
        return []
    out, seen = [], set()
    for s in _live(gs, creature.player):
        if not is_tyranid(s) or s.id in mine["controlled"]:
            continue
        unit = unit_of(gs, s)
        key = s.squadron_id or s.id
        if key in seen:
            continue
        if any(c.get("crit_type") == "synapse_severed" for u in unit for c in u.critical_damage):
            continue                       # "cannot use or benefit from synaptic control"
        if any(in_range(creature, u) for u in unit):
            seen.add(key)
            out.append(unit[0])
    return out


def try_control(gs, dice, creature, target) -> bool:
    """One synaptic control attempt: a command check on the creature's Ld
    (its own modifiers). Passed: the target's unit ignores Instinctive
    Behaviour this turn and may take any order without a second check.
    Failed: this creature's attempts end for the turn."""
    from .movement import do_command_check
    from .geometry import count_blast_markers_touching
    mine = _state(gs, creature.player)
    enemy_orders = any(s.special_order not in ("none", "") for s in gs.get_ships()
                       if s.player != creature.player and s.status == "active")
    in_blast = count_blast_markers_touching(creature, gs.get_blast_markers()) > 0
    chk = do_command_check(creature, "synaptic control", dice, enemy_orders, in_blast, gs=gs)
    unit = unit_of(gs, target)
    if chk["passed"]:
        mine["controlled"] = list(mine["controlled"]) + [u.id for u in unit]
        for u in unit:
            mine["instinct"].pop(u.id, None)
        gs.add_log(f"{creature.name}: synaptic control of {target.name}"
                   f"{' and its squadron' if len(unit) > 1 else ''} passed "
                   f"({chk['roll']} vs Ld {chk['needed']})")
    else:
        mine["failed"] = list(mine["failed"]) + [creature.id]
        gs.add_log(f"{creature.name}: synaptic control of {target.name} failed "
                   f"({chk['roll']} vs Ld {chk['needed']}); its synaptic control ends")
    _save(gs, creature.player, mine)
    return chk["passed"]


def try_self_control(gs, dice, ship) -> bool:
    """Vanguard fleet: before moving a ship or squadron may test its own
    Leadership (unit_ld); passed, it ignores Instinctive Behaviour."""
    from .movement import do_command_check
    mine = _state(gs, ship.player)
    unit = unit_of(gs, ship)
    saved = ship.leadership
    ship.leadership = unit_ld(gs, ship)
    chk = do_command_check(ship, "ignore instinct", dice, False, False, gs=gs)
    ship.leadership = saved
    if chk["passed"]:
        mine["controlled"] = list(mine["controlled"]) + [u.id for u in unit]
        _save(gs, ship.player, mine)
    gs.add_log(f"{ship.name}: command check to ignore Instinctive Behaviour "
               f"{'passed' if chk['passed'] else 'failed'} ({chk['roll']} vs {chk['needed']})")
    return chk["passed"]


def default_control_order(gs, creature, candidates) -> Optional[object]:
    """Judgement (the AI, "Auto"): the dearest unit first (each success frees
    one; a failure ends the creature's chain)."""
    if not candidates:
        return None
    return max(candidates, key=lambda s: (sum(u.points_value for u in unit_of(gs, s)), s.id))


def run_synapse(gs, dice, player, choose=None) -> None:
    """Before moving: every synapse creature in turn tries to control units in
    its range until it fails or none are left. choose(creature, candidates) ->
    a candidate or None (stop); None uses default_control_order. A Vanguard
    fleet tests each unit's own Leadership instead."""
    if vanguard_fleet(gs, player):
        seen = set()
        for s in _live(gs, player):
            key = s.squadron_id or s.id
            if is_tyranid(s) and key not in seen and not controlled(gs, s):
                seen.add(key)
                pick = s if choose is None else choose(s, [s])
                if pick is not None:
                    try_self_control(gs, dice, s)
        return
    for creature in sorted(creatures(gs, player), key=lambda c: -synapse(c)[0]):
        while True:
            fresh = gs.get_ship_by_id(creature.id)
            cands = control_candidates(gs, fresh)
            if not cands:
                break
            pick = (choose or (lambda c, cs: default_control_order(gs, c, cs)))(fresh, cands)
            if pick is None:
                break
            if not try_control(gs, dice, fresh, pick):
                break


HAZARDS = ("asteroid_field", "gas_dust_cloud", "warp_rift")


def _point_in(p, x, y, margin: float = 0.0) -> bool:
    if p.radius:
        return math.hypot(x - p.x, y - p.y) <= p.radius + margin
    a = math.radians(-(p.rotation or 0.0))
    dx, dy = x - p.x, y - p.y
    rx, ry = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
    return abs(rx) <= p.width / 2 + margin and abs(ry) <= p.height / 2 + margin


def hazard_ahead(gs, ship) -> Optional[object]:
    """The hazardous phenomenon (gas cloud, asteroid field, warp rift) a normal
    straight move at full speed would take the ship into, if any."""
    speed = max(1.0, float(getattr(ship, "effective_speed", ship.speed) or ship.speed))
    h = math.radians(ship.heading)
    hz = [p for p in gs.get_phenomena() if p.phenomenon_type in HAZARDS]
    for p in hz:
        if _point_in(p, ship.x, ship.y):
            continue                        # already in it: not "into"
        for i in range(1, 21):
            d = speed * i / 20.0
            if _point_in(p, ship.x + d * math.cos(h), ship.y + d * math.sin(h), 1.0):
                return p
    return None


def _nearest_enemy(gs, ship):
    foes = [s for s in gs.get_ships() if s.player != ship.player and s.status == "active"
            and not s.is_disengaged]
    return min(foes, key=lambda s: (ship.distance_to(s), s.id)) if foes else None


def _has_bio_weapons_on(ship, target) -> bool:
    """Operational bio-weapons (pyro-acid, bio-plasma) in range and arc."""
    from .combat import check_weapon_in_arc, weapon_disabled_by_crit
    d = ship.distance_to(target)
    for w in ship.weapons:
        if not (w.get("pyro_acid") or w.get("bio_plasma")) or weapon_disabled_by_crit(ship, w):
            continue
        if d <= w.get("range_cm", 0) and check_weapon_in_arc(ship, w, target.x, target.y):
            return True
    return False


def _needs_reload(ship) -> bool:
    torps = any(w.get("weapon_type") == "torpedo" for w in ship.weapons)
    bays = any(w.get("weapon_type") == "launch_bay" for w in ship.weapons)
    return (torps and not ship.ordnance_loaded_torps) or (bays and not ship.ordnance_loaded_craft)


def instinct(gs, ship) -> Dict:
    """The first Instinctive Behaviour action that applies to the unit led by
    `ship` (the chart, Xenos p.104). {"action", "order", "target"}."""
    from .models import Arc, SpecialOrder as SO
    hz = hazard_ahead(gs, ship)
    if hz is not None:
        return {"action": "evade", "order": SO.BURN_RETROS.value, "target": hz.id}
    foe = _nearest_enemy(gs, ship)
    arc = ship.get_target_arc(foe.x, foe.y) if foe is not None else None
    d = ship.distance_to(foe) if foe is not None else 999.0
    bio_plasma = any(w.get("bio_plasma") for w in ship.weapons)
    if foe is not None and arc == Arc.FRONT and d < 15 and not bio_plasma:
        return {"action": "board", "order": "", "target": foe.id}
    if foe is not None and arc == Arc.FRONT and d > 60:
        return {"action": "aaf", "order": SO.ALL_AHEAD_FULL.value, "target": foe.id}
    if foe is not None and arc == Arc.REAR and ship.ship_type == "escort":
        return {"action": "ctnh", "order": SO.COME_TO_NEW_HEADING.value, "target": foe.id}
    foes = [s for s in gs.get_ships() if s.player != ship.player and s.status == "active"
            and not s.is_disengaged]
    if any(ship.get_target_arc(f.x, f.y) == Arc.FRONT and _has_bio_weapons_on(ship, f)
           for f in foes):
        return {"action": "lock_on", "order": SO.LOCK_ON.value, "target": None}
    if _needs_reload(ship):
        return {"action": "reload", "order": SO.RELOAD_ORDNANCE.value, "target": None}
    goal = _drift_goal(gs, ship)
    return {"action": "close" if goal else "drift", "order": "", "target": goal}


def _drift_goal(gs, ship) -> Optional[List[float]]:
    """Where an idle bio-ship goes: the nearest planet or (other) synapse
    creature it isn't already touching, else None (half speed straight)."""
    pts = []
    for p in gs.get_phenomena():
        if p.phenomenon_type.startswith("planet") or p.phenomenon_type == "moon":
            if math.hypot(p.x - ship.x, p.y - ship.y) > (p.radius or 0) + 3:
                pts.append((p.x, p.y))
    for c in creatures(gs, ship.player):
        if c.id != ship.id and ship.distance_to(c) > 6:
            pts.append((c.x, c.y))
    if not pts:
        return None
    x, y = min(pts, key=lambda q: math.hypot(q[0] - ship.x, q[1] - ship.y))
    return [x, y]


def assign_instinct(gs, tc, player) -> None:
    """After synaptic control: every uncontrolled Tyranid unit that isn't a
    synapse creature acts on Instinctive Behaviour. Its order is applied with
    no command check; a braced unit keeps Brace and only follows the
    movement restrictions."""
    mine = _state(gs, player)
    from .models import SpecialOrder as SO
    seen = set()
    for s in _live(gs, player):
        if not is_tyranid(s) or is_synapse_creature(s) or s.id in mine["controlled"]:
            continue
        key = s.squadron_id or s.id
        if key in seen:
            continue
        seen.add(key)
        unit = unit_of(gs, s)
        act = instinct(gs, unit[0])
        braced = any(u.special_order == SO.BRACE_FOR_IMPACT.value for u in unit)
        for u in unit:
            mine["instinct"][u.id] = dict(act)
            if act["order"] and not braced:
                tc.apply_passed_order(u, act["order"])
        gs.add_log(f"{unit[0].name}{' (squadron)' if len(unit) > 1 else ''}: Instinctive "
                   f"Behaviour - {act['action']}"
                   + (f", {act['order']}" if act["order"] and not braced else ""))
    _save(gs, player, mine)


def start_turn(gs, tc, dice, player, choose=None) -> None:
    """Synaptic control, then Instinctive Behaviour, before the Tyranid
    player's ships move (IGOUGO movement phase; the AA command phase)."""
    if not any(is_tyranid(s) for s in _live(gs, player)):
        return
    _state(gs, player)
    run_synapse(gs, dice, player, choose)
    assign_instinct(gs, tc, player)


def order_rule(gs, ship, order: str) -> Tuple[str, str]:
    """How a Tyranid ship's special order is resolved: ("auto", "") passes with
    no check (a controlled unit; its instinct order), ("brace", "") tests on
    brace_ld, ("deny", reason) refused, ("normal", "") not a Tyranid ship."""
    from .models import SpecialOrder as SO
    if not is_tyranid(ship):
        return "normal", ""
    if order == SO.BRACE_FOR_IMPACT.value:
        return "brace", ""
    mine = _state(gs, ship.player)
    if ship.id in mine["controlled"]:
        return "auto", ""
    act = mine["instinct"].get(ship.id)
    if act and act.get("order") == order:
        return "auto", ""
    if is_synapse_creature(ship):
        return "deny", (f"{ship.name}: a synapse creature needs synaptic control (from itself "
                        f"or another creature) before it can take special orders")
    return "deny", (f"{ship.name} acts on Instinctive Behaviour "
                    f"({(act or {}).get('action', 'not yet assigned')}): no other orders "
                    f"without synaptic control")


def brace_ld(gs, ship) -> int:
    """Brace for Impact: the Ld of the nearest synapse creature in range, else
    7 (a Vanguard fleet: its own, at least 7)."""
    if vanguard_fleet(gs, ship.player):
        return max(NOMINAL_LD, unit_ld(gs, ship))
    near = [c for c in creatures(gs, ship.player) if in_range(c, ship)]
    if not near:
        return NOMINAL_LD
    return synapse(min(near, key=lambda c: (c.distance_to(ship), c.id)))[0]


def instinct_of(gs, ship) -> Optional[Dict]:
    if not is_tyranid(ship):
        return None
    return _state(gs, ship.player)["instinct"].get(ship.id)


def instinct_commands(gs, ship, order: str, aaf_bonus: int = 0):
    """The move an instinct action prescribes, or None when the player moves
    freely (All Ahead Full, Come to New Heading, Lock On, Reload). Board: the
    best simple move ending nearest the enemy (base contact if it can);
    close: nearest the planet or synapse creature; drift: half speed straight
    ahead; evade: Burn Retros, turning as far away from the hazard as it can."""
    from .movement import (MoveCommand, validate_movement, get_effective_speed,
                           MIN_TURN_DISTANCE)
    act = instinct_of(gs, ship)
    if not act or act["action"] not in ("board", "close", "drift", "evade"):
        return None
    mn, mx = get_effective_speed(ship, order, aaf_bonus)
    left = max(0.0, mx - (ship.distance_moved_this_turn or 0.0))
    if act["action"] == "drift":
        return [MoveCommand("forward", max(mn, ship.speed / 2.0))]
    if act["action"] == "evade":
        hz = next((p for p in gs.get_phenomena() if p.id == act["target"]), None)
        best, best_d = None, None
        for turn in ("turn_left", "turn_right"):
            cmds = [MoveCommand(turn, ship.turn_angle), MoveCommand("forward", max(1.0, left / 2))]
            r = validate_movement(ship, cmds, special_order=order, aaf_bonus=aaf_bonus,
                                  table_width=gs.table_width, table_height=gs.table_height)
            if r.valid and hz is not None:
                d = math.hypot(r.final_x - hz.x, r.final_y - hz.y)
                if best_d is None or d > best_d:
                    best, best_d = cmds, d
        return best
    if act["action"] == "board":
        foe = gs.get_ship_by_id(act["target"])
        if foe is None or foe.status != "active":
            return None
        goal = (foe.x, foe.y)
    else:
        goal = tuple(act["target"])
    td = min(MIN_TURN_DISTANCE.get(ship.ship_type, 0), left)
    best, best_d = None, None
    cands = []
    for frac in (1.0, 0.75, 0.5):
        dist = max(mn, left * frac)
        cands.append([MoveCommand("forward", dist)])
        for turn in ("turn_left", "turn_right"):
            for ang in (ship.turn_angle, ship.turn_angle / 2, ship.turn_angle / 4):
                c = ([MoveCommand("forward", td)] if td else []) + [MoveCommand(turn, ang)]
                if dist - td > 0:
                    c.append(MoveCommand("forward", dist - td))
                cands.append(c)
    for cmds in cands:
        r = validate_movement(ship, cmds, special_order=order, aaf_bonus=aaf_bonus,
                              table_width=gs.table_width, table_height=gs.table_height,
                              distance_already_moved=ship.distance_moved_this_turn or 0.0)
        if not r.valid:
            continue
        d = math.hypot(r.final_x - goal[0], r.final_y - goal[1])
        if best_d is None or d < best_d - 1e-9:
            best, best_d = cmds, d
    return best


def instinct_move_errors(gs, ship, result, order: str = "", aaf_bonus: int = 0,
                         tolerance: float = 2.0) -> List[str]:
    """Errors for a human's move that ignores its instinct action (a move
    ending more than `tolerance` cm further from the goal than the prescribed
    one; drift: not straight ahead at half speed)."""
    act = instinct_of(gs, ship)
    if not act or act["action"] not in ("board", "close", "drift", "evade"):
        return []
    ref = instinct_commands(gs, ship, order, aaf_bonus)
    if not ref:
        return []
    from .movement import validate_movement
    r = validate_movement(ship, ref, special_order=order, aaf_bonus=aaf_bonus,
                          table_width=gs.table_width, table_height=gs.table_height,
                          distance_already_moved=ship.distance_moved_this_turn or 0.0)
    if not r.valid:
        return []
    off = math.hypot(result.final_x - r.final_x, result.final_y - r.final_y)
    what = {"board": "move into base contact with the nearest enemy and board it",
            "close": "move closer to the nearest planet or synapse creature",
            "drift": "move half speed straight ahead",
            "evade": "Burn Retros and turn away from the hazard as much as possible"}[act["action"]]
    if act["action"] in ("board", "close") and act.get("target"):
        foe = gs.get_ship_by_id(act["target"]) if act["action"] == "board" else None
        gx, gy = (foe.x, foe.y) if foe is not None else tuple(act["target"])
        if math.hypot(result.final_x - gx, result.final_y - gy) <= \
                math.hypot(r.final_x - gx, r.final_y - gy) + tolerance:
            return []
    elif off <= tolerance:
        return []
    return [f"{ship.name} acts on Instinctive Behaviour: it must {what} "
            f"(without synaptic control)."]


# ── Shooting (Xenos p.105) ─────────────────────────────────────────────────────

def highlighted(gs, attacker, target) -> bool:
    """A target within 15cm of a friendly ship with Pheromone Sprayers."""
    for s in _live(gs, attacker.player):
        if "pheromone_sprayers" in s.special_rules and \
                math.hypot(s.x - target.x, s.y - target.y) <= 15.0 + 1e-9:
            return True
    return False


def shooting_target_error(gs, attacker, target, candidates) -> str:
    """Tyranid direct fire: the closest enemy ship within range and arc
    (`candidates`, the ships the weapon can fire at), or a highlighted target,
    with no target priority test needed or allowed. "" if allowed."""
    if not is_tyranid(attacker) or target is None:
        return ""
    if highlighted(gs, attacker, target):
        return ""
    ships = [c for c in candidates if hasattr(c, "hits_max")]
    if not ships:
        return ""
    nearest = min(ships, key=lambda c: (attacker.distance_to(c), c.id))
    if attacker.distance_to(target) <= attacker.distance_to(nearest) + 1e-6:
        return ""
    return (f"{attacker.name} (Tyranid) must fire at the closest enemy ship in range and arc "
            f"({nearest.name}) or a target highlighted by Pheromone Sprayers")


def may_fire_at_ordnance(gs, attacker, marker) -> bool:
    """Tyranids may only shoot ordnance highlighted by Pheromone Sprayers."""
    if not is_tyranid(attacker):
        return True
    for s in _live(gs, attacker.player):
        if "pheromone_sprayers" in s.special_rules and \
                math.hypot(s.x - marker.x, s.y - marker.y) <= 15.0 + 1e-9:
            return True
    return False
