"""Fleet lists for Chaos, Orks, Tau and Rogue Traders, in the format described
in fleet_lists.py. Transcribed from the booklet:
  bfgxr/rules/07_chaos.md       Fleet Composition (Incursion, Crusade, Renegades
                                & God-Dedicated Fleet Lists)
  bfgxr/rules/10_orks.md        Fleet Composition (Green Tide Fleet List)
  bfgxr/rules/11_tau-allies.md  Fleet Composition (Tau Empire Fleet List)
  bfgxr/rules/05_rogue-traders.md  Fleet Composition (Fleet Detachment,
                                Expedition & Pirate Lists)
"""
from typing import Dict, List

# ── Chaos (07_chaos.md) ──────────────────────────────────────────────────────

_CHAOS_UNENFORCED = [
    "The fleet commander rides the most expensive capital ship: not checked.",
    "Ratios (owner ruling, export 15): battleships and grand cruisers one per three "
    "cruisers and/or heavy cruisers, heavy cruisers one per two cruisers; light cruisers are "
    "their own 0-6 section and don't count.",
    "Escort squadrons of 2-6: not checked.",
    "Torpedo types (one per capital ship), anointed munitions, and mine launchers on up to "
    "two cruisers or heavy cruisers: not checked here.",
]

_CHAOS_GC = {"Retaliator Grand Cruiser": 275, "Nephilim Grand Cruiser": 250,
             "Repulsive Grand Cruiser": 230, "Executor Grand Cruiser": 210}
_CHAOS_HC = {"Styx Heavy Cruiser": 260, "Hecate Heavy Cruiser": 230,
             "Hades Heavy Cruiser": 200, "Acheron Heavy Cruiser": 190}
_CHAOS_CR = {"Devastation Cruiser": 190, "Carnage Cruiser": 180, "Inferno Cruiser": 180,
             "Murder Cruiser": 170, "Slaughter Cruiser": 165}
_CHAOS_LC = {"Fanatic Light Cruiser": 125, "Schismatic Light Cruiser": 125,
             "Heretic Light Cruiser": 120}
_CHAOS_ESC = {"Idolator Raider": 45, "Infidel Raider": 40, "Havoc Raider": 35,
              "Iconoclast Destroyer": 25}
_DEDICATED = {"Scion of Prospero (Thousand Sons)": 450,
              "Wage of Sin (Emperor's Children)": 420,
              "Terminus Est (Death Guard)": 420,
              "Slaverer (World Eaters)": 400}


def _chaos_core_sections(battleships: Dict[str, int], class_max: Dict[str, int]) -> List[Dict]:
    return [
        {"name": "Battleships", "ratio": (3, ["Cruisers", "Heavy Cruisers"]),
         "class_max": dict(class_max),
         "ships": dict(battleships)},
        {"name": "Grand Cruisers", "ratio": (3, ["Cruisers", "Heavy Cruisers"]),
         "ships": dict(_CHAOS_GC)},
        {"name": "Heavy Cruisers", "ratio": (2, ["Cruisers"]), "ships": dict(_CHAOS_HC)},
        {"name": "Cruisers", "ships": dict(_CHAOS_CR)},
        {"name": "Light Cruisers", "max": 6, "ships": dict(_CHAOS_LC)},
    ]


_CRUSADE_BS = {"Despoiler Battleship": 390, "Desecrator Battleship": 365,
               "Desolator Battleship": 300}
_CRUSADE_UNENFORCED = [
    "Abaddon the Despoiler (Ld10, 195pts, fleet 1000+pts, must ride the Planet Killer if "
    "present) is not in the fleet builder yet.",
    "Marks of Chaos (one of each, each on a different capital ship; Undivided on the "
    "commander's ship only), Chaos Space Marine crews (+35, not on daemonships) and "
    "daemonships (one capital ship per full 1000pts, not light cruisers): not checked.",
    "Dedicated battle barges must be the flagship with a Warmaster aboard (a Chaos Lord if "
    "the Planet Killer is present), except Wage of Sin; each can't join a fleet with its "
    "rival god's Mark unless Abaddon leads it.",
    "The Terminus Est is costed at 420pts in this list (its profile prints 420*).",
]


_RENEGADE_LIGHT = ["Dauntless Light Cruiser", "Endeavour Light Cruiser",
                   "Endurance Light Cruiser", "Defiant Light Cruiser"]


def _renegade_ratios(sections: List[Dict]) -> List[Dict]:
    """Renegades list: Imperial Renegade cruisers count as cruisers for the
    Chaos ratios (renegade light cruisers, like Chaos light cruisers, don't)."""
    out = []
    for sec in sections:
        sec = dict(sec)
        if sec.get("ratio"):
            n, base = sec["ratio"]
            sec["ratio"] = (n, list(base) + ["Imperial Renegade Cruisers"])
            sec["ratio_excludes"] = list(_RENEGADE_LIGHT)
        out.append(sec)
    return out


def _god_list(key: str, name: str, ship: str, rival: str, boons: str) -> Dict:
    god = {"chaos_slaanesh": "Slaanesh", "chaos_nurgle": "Nurgle", "chaos_khorne": "Khorne",
           "chaos_tzeentch": "Tzeentch"}[key]
    return {
        "key": key, "faction": "chaos", "name": name,
        # only their own god's Mark (+15); CSM crews on any capital ship;
        # Terminators on battleships and grand cruisers with CSM
        "list_options": [f"Mark of {god}", "Chaos Space Marine crew", "Chaos Terminators",
                         f"Boon of {god}:"],
        "chaos_options": {"marks_need": "leader_or_csm", "terminators": True},
        "sections": _chaos_core_sections(
            dict(_CRUSADE_BS, **{ship: _DEDICATED[ship]}), {ship: 1}) + [
            {"name": "Escorts", "ships": dict(_CHAOS_ESC)}],
        "reserves": [],
        "unenforced": list(_CHAOS_UNENFORCED[:-1]) + list(_CRUSADE_UNENFORCED) + [
            f"Uses the 13th Black Crusade list without the Planet Killer, the Chaos Space "
            f"Hulk or the other gods' dedicated battleships. {boons}",
            f"Neither gives nor takes reserves or allies; ships bearing the Mark of {rival} "
            f"are always enemy vessels."]}


CHAOS_LISTS = [
    {"key": "chaos_incursion", "faction": "chaos", "name": "Incursion Fleet (Imperium p.54)",
     "sections": [
         {"name": "Battleships", "ratio": (3, ["Cruisers", "Heavy Cruisers"]),
          "ships": {"Despoiler Battleship": 390, "Desolator Battleship": 300}},
         {"name": "Grand Cruisers", "ratio": (3, ["Cruisers", "Heavy Cruisers"]),
          "ships": {"Repulsive Grand Cruiser": 230}},
         {"name": "Heavy Cruisers", "ratio": (2, ["Cruisers"]),
          "ships": {"Styx Heavy Cruiser": 260, "Hades Heavy Cruiser": 200,
                    "Acheron Heavy Cruiser": 190}},
         {"name": "Cruisers",
          "ships": {"Devastation Cruiser": 190, "Carnage Cruiser": 180,
                    "Murder Cruiser": 170, "Slaughter Cruiser": 165}},
         {"name": "Escorts",
          "ships": {"Idolator Raider": 45, "Infidel Raider": 40, "Iconoclast Destroyer": 25}},
     ],
     "reserves": ["chaos_black_crusade", "chaos_renegades"],
     "reserve_excludes": ["The Planet Killer", "Chaos Space Hulk"],
     "list_options": ["Mark of "], "chaos_options": {"marks_need": "leader"},
     "unenforced": list(_CHAOS_UNENFORCED)},
    {"key": "chaos_black_crusade", "faction": "chaos",
     "name": "13th Black Crusade Fleet (Imperium p.55-56)",
     # Export 25: the Relictor (300) was missing from the battleships
     # The Planet Killer (fleet 1000+pts) counts as a battleship for fleet
     # requirements and restrictions (update 25)
     "sections": [dict(sec, class_min_points={"The Planet Killer": 1000})
                  if sec["name"] == "Battleships" else sec
                  for sec in _chaos_core_sections(
                      dict(_CRUSADE_BS, **_DEDICATED, **{"Relictor Battleship": 300,
                                                          "The Planet Killer": 505}),
                      dict({s: 1 for s in _DEDICATED}, **{"The Planet Killer": 1}))] + [
         {"name": "Special", "class_max": {"Chaos Space Hulk": 1},
          "ships": {"Chaos Space Hulk": 650}},
         {"name": "Escorts", "ships": dict(_CHAOS_ESC)},
     ],
     "reserves": ["chaos_incursion", "chaos_renegades"],
     "reserve_excludes": ["Chaos Space Hulk"],
     "list_options": ["Mark of ", "Chaos Space Marine crew", "Warmaster Abaddon"],
     "chaos_options": {"marks_unique": True},
     "unenforced": list(_CHAOS_UNENFORCED) + list(_CRUSADE_UNENFORCED) + [
         "A Chaos Space Hulk, if taken, must be the fleet flagship."]},
    {"key": "chaos_renegades", "faction": "chaos", "name": "Renegades Fleet (Imperium p.57)",
     "sections": _renegade_ratios(
         _chaos_core_sections(dict(_CRUSADE_BS, **{"Relictor Battleship": 300}), {})) + [
         {"name": "Escorts", "ships": dict(_CHAOS_ESC)},
         # Imperial Renegades: per full 750pts, up to six escorts and/or one cruiser
         # (worth up to 185pts) from the Bastion or Armageddon Sector lists
         {"name": "Special", "class_max": {"Chaos Space Hulk": 1},
          "ships": {"Chaos Space Hulk": 650}},
         {"name": "Imperial Renegade Cruisers", "per_points": 750,
          "ships": {"Gothic Cruiser": 180, "Lunar Cruiser": 180, "Tyrant Cruiser": 175,
                    "Dauntless Light Cruiser": 110, "Endeavour Light Cruiser": 110,
                    "Endurance Light Cruiser": 110, "Defiant Light Cruiser": 110}},
         {"name": "Imperial Renegade Escorts",
          "ships": {"Nova Frigate": 45, "Gladius Frigate": 40, "Hunter Destroyer": 40,
                    "Firestorm Frigate": 35, "Sword Frigate": 35, "Falchion Frigate": 35,
                    "Cobra Destroyer": 30}},
     ],
     "group_caps": [{"classes": ["Nova Frigate", "Gladius Frigate", "Hunter Destroyer",
                                 "Firestorm Frigate", "Sword Frigate", "Falchion Frigate",
                                 "Cobra Destroyer"],
                     "max": 6, "per_points": 750, "label": "Imperial Renegade escorts"}],
     # "renegade cruisers subtract 1 from their rolled Leadership"
     "stat_changes": [{"sections": ["Imperial Renegade Cruisers"],
                       "add_rules": ["ld_rolled:-1", "chaos_crew"]},
                      {"sections": ["Imperial Renegade Escorts"], "add_rules": ["chaos_crew"]}],
     "reserves": ["chaos_black_crusade", "chaos_incursion"],
     "reserve_excludes": ["The Planet Killer", "Chaos Space Hulk"],
     "list_options": ["Mark of ", "Chaos Space Marine crew", "Chaos Terminators"],
     "chaos_options": {"marks_need": "leader_or_csm", "csm_per_750": True,
                       "terminators": True},
     "unenforced": list(_CHAOS_UNENFORCED) + [
         "The (0-1) Chaos Space Marine Battle Barge (440) and Chaos Space Marine Strike "
         "Cruisers (145, one per 500pts) aren't in the catalog.",
         "Marks of Chaos (one per vessel with a Chaos Space Marine crew or a Chaos Lord, "
         "Warmaster or Aspiring Champion; Undivided on the commander's ship only) and Chaos "
         "Space Marine crews (+35, one capital ship per full 750pts, not battle barges or "
         "strike cruisers): not checked.",
         "Imperial Renegades (owner rulings): \"six escorts and/or one cruiser (worth up to "
         "185pts)\" per full 750pts allows both; they are Chaos ships in all respects, so a "
         "renegade cruiser counts as a cruiser for the Chaos ratios (renegade light cruisers "
         "don't); they don't count against reserves. The Strike Cruiser is left out as an "
         "ally of convenience in the Armageddon list.",
         "A Chaos Space Hulk must be the commander's flagship (it isn't playable yet)."]},
    _god_list("chaos_slaanesh", "Pleasure Fleet of Slaanesh (Imperium p.58-61)",
              "Wage of Sin (Emperor's Children)", "Khorne",
              "Boons: Veil of Lust (+20), Siren's Summon (+25, up to two ships)."),
    _god_list("chaos_nurgle", "Plague Fleet of Nurgle (Imperium p.58-61)",
              "Terminus Est (Death Guard)", "Tzeentch",
              "Boons: Miasma of Pestilence (+10), Plague Arks (+5, up to three ships)."),
    _god_list("chaos_khorne", "Berzerker Fleet of Khorne (Imperium p.58-61)",
              "Slaverer (World Eaters)", "Slaanesh",
              "Boon: The Berzerker Tide."),
    _god_list("chaos_tzeentch", "Infinite Fleet of Tzeentch (Imperium p.58-61)",
              "Scion of Prospero (Thousand Sons)", "Nurgle",
              "Boons: Warp Beasts (+25, up to two ships), Strands of Fortune (+25)."),
]

# ── Orks (10_orks.md) ─────────────────────────────────────────────────────────

_NAVY_KEYS = ["navy_gothic", "navy_armageddon", "navy_bakka", "navy_bastion"]

ORK_LISTS = [
    {"key": "orks_green_tide", "faction": "orks", "name": "Green Tide Fleet (Xenos p.73)",
     "sections": [
         {"name": "Battleships", "max": 4, "ratio": (2, ["Kroozers"]),
          "class_max": {"Gorbag's Revenge (0-1)": 1, "Slamblasta (0-1)": 1,
                        "Dethdeala (0-1)": 1, "Kroolboy (0-1)": 1},
          "ships": {"Gorbag's Revenge (0-1)": 315, "Slamblasta (0-1)": 295,
                    "Dethdeala (0-1)": 285, "Kroolboy (0-1)": 265}},
         {"name": "Battlekroozers", "ratio": (2, ["Kroozers"]),
          "ships": {"Hammer Battlekroozer": 225}},
         {"name": "Kroozers",
          "ships": {"Terror Ship": 175, "Kill Kroozer": 155, "Basha Lite Kroozer": 110}},
         {"name": "Escorts",
          "ships": {"Grunt Assault Ship": 35, "Ravager Attack Ship": 35,
                    "Onslaught Attack Ship": 30, "Savage Gunship": 25, "Brute Ramship": 20}},
         {"name": "Special: Space Hulk", "per_points": 1500, "ships": {"Ork Space Hulk": 610}},
         {"name": "Special: Roks", "ships": {"Ork Rok": 80}},
     ],
     "reserves": _NAVY_KEYS + ["chaos_incursion", "chaos_black_crusade", "chaos_renegades",
                               "tau_empire"],
     "unenforced": [
         "Fleet commanders (0-1 Ork Boss per 500pts, one required at 500+pts: Warboss, Big "
         "Mek, Freebooter Kaptin, Big Boss / Mega Boss titles), Nobz (up to 2 per 500pts) and "
         "kustom upgrades are not in the fleet builder yet.",
         "Da Ork Clanz (+50% of the commander's cost) and Snakebite affiliation: not checked.",
         "Escort squadrons of 3-10: not checked. Attack rating 3.",
         "Reserves are looted cruisers only (from any Imperial Navy, Chaos or Tau fleet "
         "list); taking a battleship or escort as a reserve isn't stopped here. The Chaos "
         "god-dedicated fleets give no reserves, so they aren't offered.",
         "Battleship and battlekroozer ratios count the Kroozers section (\"one per two "
         "kroozers\")."]},
]

# ── Tau (11_tau-allies.md) ────────────────────────────────────────────────────

TAU_LISTS = [
    {"key": "tau_empire", "faction": "tau_kororvesh",
     "class_not_more_than": [("Stronghold Commerce Vessel", "Bastion Commerce Vessel")], "name": "Tau Empire Fleet (Xenos p.99-101)",
     "sections": [
         {"name": "Kor'or'vesh Battleships", "per_points": 750,
          "per_points_of": ["Kor'or'vesh", "Kor'vattra"],
          "ships": {"Custodian Battleship": 330}},
         {"name": "Kor'or'vesh Cruisers",
          "ships": {"Protector Cruiser": 180, "Emissary Light Cruiser": 110}},
         {"name": "Kor'or'vesh Escorts", "ships": {"Castellan Escort": 45}},
         {"name": "Kor'or'vesh Towed Escorts", "ships": {"Warden Gunship": 30}},
         {"name": "Kor'vattra Battleships", "ships": {"Explorer Starship": 230}},
         {"name": "Kor'vattra Cruisers",
          "ships": {"Hero Starship": 180, "Merchant Starship": 105}},
         {"name": "Kor'vattra Messengers", "per_points": 500, "or_part": True,
          "ships": {"Messenger Starship": 50}},
         {"name": "Kor'vattra Escorts", "ships": {"Defender Starship": 50}},
         {"name": "Kor'vattra Towed Escorts", "ships": {"Orca Gunship": 25}},
         {"name": "Allies: Demiurg",
          "ships": {"Stronghold Commerce Vessel": 350, "Bastion Commerce Vessel": 255,
                    "Citadel Commerce Vessel": 185}},
         {"name": "Allies: Nicassar",
          "ships": {"Nicassar Caravan": 200, "Nicassar Dhow": 45, "Nicassar Rig": 20}},
         {"name": "Allies: Kroot", "max": 2, "ships": {"Kroot Warsphere": 145}},
     ],
     "reserves": [],
     "unenforced": [
         "Fleet commander (0-1 Kor'el Ld8 50 or Kor'O Ld9 70; required for a large fleet, "
         "and a Kor'O if a Custodian is present) is not in the fleet builder yet.",
         "Kor'O Vash'ya Y'eldi Mesme (Ld9, 110) and his flagship, the unique Custodian "
         "The Se'arle O'Mesme (400), aren't in the fleet builder or catalog.",
         "Custodians: one per full 750pts of Tau vessels (Kor'or'vesh and Kor'vattra ships, "
         "not allies).",
         "Towed escorts need gravitic hooks for their type; every Nicassar Rig needs four "
         "Dhows (checked for every fleet, fleet_lists.towed_errors). The Rig (a stationary "
         "defence) isn't playable yet, so Dhows can't be fielded.",
         "Nicassar Dhows in squadrons of 2-6: not checked.",
         "Mine launchers on up to two cruisers; escort squadrons of 2-6: not checked.",
         "Reserves: only a Rogue Trader Fleet Detachment may join; no other reserves."]},
]

TAU_LISTS.append(
    {"key": "tau_demiurg_war_host", "faction": "tau_kororvesh", "demiurg_war_host": True,
     "name": "Demiurg War Host (Xenos p.101)",
     # Never requires or fields fleet commanders; up to two re-rolls bought for
     # the whole host (booklet_options.demiurg_war_host_options)
     "no_commander": True,
     "list_excludes": ["Kor'el", "Kor'O", "Commander:"],
     "list_options": ["War Host re-roll"],
     "sections": [
         {"name": "Battleships", "ratio": (2, ["Cruisers"]),
          "ships": {"Stronghold Commerce Vessel": 350}},
         {"name": "Cruisers", "max": 12,
          "ships": {"Bastion Commerce Vessel": 255, "Citadel Commerce Vessel": 185,
                    "Protector Cruiser": 180, "Hero Starship": 180,
                    "Emissary Light Cruiser": 110, "Merchant Starship": 105}},
         {"name": "Kroot Vessels", "max": 3, "per_points": 750, "or_part": True,
          "ships": {"Kroot Warsphere": 145}},
         {"name": "Escorts",
          "ships": {"Defender Starship": 50, "Castellan Escort": 45, "Nicassar Dhow": 45,
                    "Warden Gunship": 30, "Orca Gunship": 25}},
     ],
     # Tau Kor'or'vesh vessels as reserves (normal 3:1)
     "reserves": ["tau_empire"], "reserve_sections": {"tau_empire": ["Kor'or'vesh"]},
     "unenforced": [
         "Mine launchers on up to two cruisers: not in the fleet builder yet.",
         "Demiurg ships use only generic attack craft and ordinary torpedoes."]})

# ── Rogue Traders (05_rogue-traders.md) ───────────────────────────────────────

_RT_CONVOY_ESC = {"Rogue Trader Escort Carrier": 60, "Rogue Trader Convoy Monitor": 60,
                  "Rogue Trader Sloop": 20, "Rogue Trader Caravel": 10}
_RT_CONVOY = [
    {"name": "Convoy Ships",
     "class_max": {"Universe Class Mass Conveyor": 1},
     "ships": {"Universe Class Mass Conveyor": 200, "Rogue Trader Carrack": 40}},
    {"name": "Convoy Escorts", "ships": dict(_RT_CONVOY_ESC)},
]
_RT_MOW = ("Men O' War (\"Rogue Trader Man O' War: Varies\") are designed from a chassis and "
           "aren't offered by this list yet.")
_RT_FORTUNE = "Fortune costs and the fleet's Fortune rating are not tracked."
_RT_CONVOY_LIMITS = (
    "Transport capacity limits (Mass Conveyor no more than 75%, Carracks no more than one "
    "third; Escort Carriers and Convoy Monitors one per point of transport capacity) and "
    "squadrons of 2-6 (max four two-hit escorts): not checked.")

# A xenos cutter squadron may instead become a Notable Xenos (one profile for
# the whole squadron): 35pts per ship plus 30pts per squadron (the squadron
# cost is added by fleet_lists.notable_xenos_cost)
_XENOS_CUTTERS = {"Xenos Cutter": 35, "Pthuxutl War Cruiser (Notable Xenos)": 35,
                  "Fra'al Raider (Notable Xenos)": 35, "Nekulli Whip (Notable Xenos)": 35}

RT_LISTS = [
    {"key": "rt_detachment", "faction": "rogue_traders", "kind": "detachment",
     "name": "Rogue Trader Fleet Detachment (Imperium p.126)",
     # Owner ruling: joins any fleet except Necrons or Tyranids, Orks included (a
     # detachment isn't a reserve). The Crusade list (only an Inquisitorial
     # detachment) and the Banisher fleet (no detachments) refuse it.
     "joins": _NAVY_KEYS + ["admech_explorator", "sm_dominion", "chaos_incursion",
                            "chaos_black_crusade", "chaos_renegades", "chaos_slaanesh",
                            "chaos_nurgle", "chaos_khorne", "chaos_tzeentch",
                            "orks_green_tide", "tau_empire", "tau_demiurg_war_host"],
     "list_options": ["Bond-Captain"],
     "sections": [dict(s, ships=dict(s["ships"])) for s in _RT_CONVOY] + [
         {"name": "Xenos Cutters", "ships": dict(_XENOS_CUTTERS)},
     ],
     "unenforced": [
         "1 Rogue Trader (Lord Captain Ld8 50, Venerable Lord Captain Ld9 75) must lead it "
         "and may serve as the joined fleet's required commander; 0-3 Bond-Captains. Not in "
         "the fleet builder yet.",
         _RT_MOW + " Up to one per Rogue Trader and/or Bond-Captain, counting against the "
         "joined fleet's limits by chassis.",
         _RT_CONVOY_LIMITS, _RT_FORTUNE,
         "Xenos cutter squadrons don't count as reserves (1 Fortune for 1-3 ships, 2 for "
         "4-6). For every 750pts, one Demiurg or Kroot capital ship as a reserve (not in a "
         "Tau or Ork joined fleet): not offered (the list prints no cost).",
         "If the joined fleet has any Space Marine ships, honour guards or commanders, no "
         "xenos allies at all (not even cutters).",
         "Joins any fleet except Necron or Tyranid; not offered for lists that refuse "
         "detachments (Space Marine Crusade, Banisher, Chaos god-dedicated fleets, the "
         "Rogue Trader standalone lists). Whether it may join the Green Tide (\"no other "
         "reserves\") is a reading: a detachment isn't reserves."]},
    {"key": "rt_expedition", "faction": "rogue_traders", "expedition": True,
     "name": "Rogue Trader Expedition Fleet (Imperium p.127)",
     "sections": [
         {"name": "Expedition Cruisers", "max": 6,
          "ships": {"Dauntless Light Cruiser": 110, "Endeavour Light Cruiser": 110,
                    "Siluria Light Cruiser": 100}},
         {"name": "Recommissioned Cruisers", "ratio": (1, ["Expedition Cruisers"]),
          "ships": {"Lunar Cruiser": 180, "Carnage Cruiser": 180, "Tyrant Cruiser": 175,
                    "Murder Cruiser": 170}},
         {"name": "Demiurg & Kroot Mercenaries", "ratio": (3, ["Expedition Cruisers"]),
          "xenos": True,
          "class_max": {"Kroot Warsphere": 1},
          "ships": {"Stronghold Commerce Vessel": 350, "Bastion Commerce Vessel": 255,
                    "Citadel Commerce Vessel": 185, "Kroot Warsphere": 145}},
         {"name": "Escorts", "ships": dict(_XENOS_CUTTERS), "xenos": True},
     ] + [dict(s, ships=dict(s["ships"])) for s in _RT_CONVOY],
     "reserves": _NAVY_KEYS + ["admech_explorator", "sm_crusade", "sm_dominion",
                               "chaos_incursion", "chaos_black_crusade", "chaos_renegades",
                               "tau_empire"],
     "unenforced": [
         "Fleet commander (0-1 Rogue Trader, required at 750+pts) and Veteran Bond-Captains "
         "(one per two Men O' War) are not in the fleet builder yet.",
         _RT_MOW + " They count as the Expedition Flagship (grand galleon, ship of the line) "
         "or Expedition Cruisers (brig, galleon).",
         "The (0-1) Expedition Flagship (fleet 1000+pts) has no catalog ships of its own; "
         "supporting-fleet battleships and grand cruisers taken as reserves count against it, "
         "other cruisers against the recommissioned-cruiser limit: not checked.",
         "One escort squadron of 2-6 per capital ship (max four two-hit escorts); "
         "supporting-fleet escorts may be taken in the Escorts section (not Tau escorts "
         "needing hooks) but are offered here as reserves.",
         "At least one squadron of convoy escorts is required. " + _RT_CONVOY_LIMITS,
         "Choose one supporting fleet from another faction (not Dark Eldar, Ork, Necron or "
         "Tyranid); its capital ships come as reserves at 3:1, but Demiurg and Kroot can't "
         "be taken that way. A Space Marine supporting fleet bars all xenos.",
         _RT_FORTUNE + " Refitted torpedoes +20; mine launchers on up to two capital ships. "
         "Attack rating 3."]},
    {"key": "rt_wolf_pack", "faction": "rogue_traders",
     "name": "Wolf-Pack Pirate Fleet (Imperium p.128-129)",
     "sections": [
         {"name": "Infamous Pirate Ships", "per_points": 1000, "or_part": True,
          "class_max": {"Fra'al Battlecruiser": 2},
          "ships": {"Fra'al Battlecruiser": 250}},
         {"name": "Pirate Cruisers", "per_points": 500, "or_part": True,
          "class_max": {"Strike Cruiser": 1},
          "ships": {"Murder Cruiser": 170, "Slaughter Cruiser": 165, "Strike Cruiser": 145,
                    "Fanatic Light Cruiser": 125, "Schismatic Light Cruiser": 125,
                    "Heretic Light Cruiser": 120}},
         {"name": "Pirate Escorts",
          "ships": {"Rogue Trader Escort Carrier": 60, "Rogue Trader Convoy Monitor": 60,
                    "Infidel Raider": 40, "Havoc Raider": 35, "Iconoclast Destroyer": 25,
                    "Rogue Trader Sloop": 20, "Rogue Trader Caravel": 10}},
         {"name": "Xenos Escorts", "ships": dict(_XENOS_CUTTERS)},
         {"name": "Other Xenos Allies", "max": 4, "ships": {"Stryxis Caravan Vessel": 80}},
     ],
     "reserves": [],
     "unenforced": [
         "Fleet commanders (0-3 Pirate Captains, one per 500pts, one required at 750+pts) "
         "are not in the fleet builder yet. A Problem with Authority: -1Ld while re-rolling.",
         _RT_MOW + " They count as Infamous Pirate Ships (grand galleon, ship of the line) "
         "or Pirate Cruisers (brig, galleon).",
         "The Space Marine Strike Cruiser rolls Leadership on the standard table and takes "
         "no Space Marine refits.",
         "At least one escort squadron of 2-6 per capital ship (max four two-hit escorts); "
         "xenos escort squadrons one per capital ship. The Corsair Eldar Raider, Dark Eldar "
         "Raider, Ork Freebooter and Tau Scout (\"Varies\") aren't in the catalog.",
         _RT_FORTUNE + " Refitted torpedoes +20. Attack rating 3.",
         "Neither gives nor takes reserves or allies beyond the above; no fleet "
         "detachments."]},
]

OTHER_LISTS: List[Dict] = CHAOS_LISTS + ORK_LISTS + TAU_LISTS + RT_LISTS
