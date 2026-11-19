"""The owner's 1000pt fleets (CLAUDE.md To do 25) built through the real fleet
builder window (its rows, options, fleet-list check and save code), saved to
data/fleets/. Run: xvfb-run -a /usr/bin/python3.12 tools/build_owner_fleets.py
Prints each fleet's total and any fleet-list problems. Only the fleets whose
ships and options the catalog has are built; the rest are listed as gaps."""
import os
import sys
import tkinter as tk

sys.path.insert(0, ".")
from src import fleet_builder as FB   # noqa: E402

# (file, fleet name, faction picker text, list key, ships); a ship is
# (catalog class, options, flagship, squadron id). The commander goes on the
# dearest capital ship (owner's To do 29 placement waits).
FLEETS = [
    ("owner_chaos_1000.json", "13th Black Crusade 1000", "Chaos", "chaos_black_crusade", [
        ("Styx Heavy Cruiser", ["Chaos Warmaster (Ld 9)", "Commander: 1 extra re-roll"], True, ""),
        ("Devastation Cruiser", [], False, ""),
        ("Inferno Cruiser", [], False, ""),
        ("Murder Cruiser", [], False, ""),
    ] + [("Iconoclast Destroyer", [], False, "iconoclasts")] * 4),
    ("owner_gothic_1000.json", "Gothic Sector 1000", "Imperial Navy", "navy_gothic", [
        ("Mars Battlecruiser", ["Vice Admiral (Ld 8)", "Commander: 1 extra re-roll"], True, ""),
        ("Lunar Cruiser", [], False, ""),
        ("Tyrant Cruiser", ["Refit: 30cm macrobatteries to 45cm"], False, ""),
        ("Dauntless Light Cruiser", ["Refit: prow torpedoes (S6) for the lances"], False, ""),
    ] + [("Firestorm Frigate", [], False, "firestorms")] * 2
      + [("Cobra Destroyer", [], False, "cobras")] * 4),
    ("owner_bakka_1000.json", "Bakka Sector 1000", "Imperial Navy", "navy_bakka", [
        ("Victory Battleship", ["Fleet Admiral (Ld 9)", "Commander: 1 extra re-roll"], True, ""),
        ("Tyrant Cruiser", ["Refit: prow nova cannon for the torpedoes",
                            "Refit: 30cm macrobatteries to 45cm"], False, ""),
    ] + [("Dauntless Light Cruiser", [], False, "")] * 2
      + [("Sword Frigate", [], False, "swords")] * 3),
    ("owner_tau_merchant_1000.json", "Tau Merchant 1000", "Tau", "tau_empire", [
        ("Explorer Starship", ["Kor'O (Ld 9)", "Commander: 1 extra re-roll"], True, ""),
    ] + [("Orca Gunship", [], False, "orcas")] * 3
      + [("Hero Starship", [], False, "")] * 3
      + [("Messenger Starship", [], False, "")]),
    ("owner_space_marines_1000.json", "Space Marine Crusade 1000", "Space Marine", "sm_crusade", [
        ("Strike Cruiser", ["Master of the Fleet (Ld 10)", "Master of the Fleet: 2 re-rolls",
                            "Chapter tactic: Wings of Fury", "Secondary Shield (+1 Shield)"],
         True, ""),
        ("Strike Cruiser", ["Secondary Shield (+1 Shield)"], False, ""),
        ("Strike Cruiser", ["Secondary Shield (+1 Shield)"], False, ""),
        ("Strike Cruiser", ["Secondary Shield (+1 Shield)",
                            "Variant: macrobatteries to launch bays"], False, ""),
        ("Strike Cruiser", ["Secondary Shield (+1 Shield)",
                            "Variant: macrobatteries to launch bays"], False, ""),
        ("Nova Frigate", [], False, ""),
    ]),
    ("owner_mechanicus_1000.json", "Mechanicus Explorator 1000", "Mechanicus",
     "admech_explorator", [
        ("Mechanicus Dictator Cruiser", ["Archmagos Explorator (Ld 9)",
                                         "Commander: 1 extra re-roll"], True, ""),
    ] + [("Mechanicus Tyrant Cruiser", ["Refit: prow nova cannon for the torpedoes",
          "Refit: plasma-boosted gunnery (30cm macrobatteries to 45cm)"], False, "")] * 2
      + [("Mechanicus Nova Frigate", [], False, "novas")] * 4),
    ("owner_dark_eldar_1000.json", "Dark Eldar Raiders 990", "Dark Eldar", "dark_eldar_raiders", [
        ("Succubus Class Light Cruiser", [
            "Dread Archon (+2 Ld)", "Dread Archon: 2 re-rolls",
            "Kabal Variant: Burning Scale (keel launch bays, 2, with Voidravens)"], True, ""),
    ] + [("Corsair Class Frigate", ["Kabal Variant: Impaler bay, 1 module"], False,
          "corsairs")] * 6
      + [("Subjugation Class Raider", ["Kabal Variant: Torpedo salvo S2"], False,
          "torp_raiders")] * 4
      + [("Subjugation Class Raider", ["Kabal Variant: Weapons battery FP3"], False,
          "gun_raiders")] * 5),
    ("owner_tau_protector_980.json", "Tau Protector 980", "Tau", "tau_empire", [
        ("Custodian Battleship", ["Kor'O (Ld 9)", "Commander: 2 extra re-rolls"], True, ""),
    ] + [("Emissary Light Cruiser", ["Configuration: ion cannons for the gravitic hooks",
                                     "Mine launchers (replace all launch bays)", "Deflector"],
          False, "emissaries")] * 2
      + [("Warden Gunship", [], False, "wardens")] * 3
      + [("Protector Cruiser", [], False, "")]),
    ("owner_orks_980.json", "Ork Green Tide 980", "Ork", "orks_green_tide", [
        ("Dethdeala (0-1)", ["Ork Big Mek", "Boss title: Big Boss", "Kustom: Extra Power Field",
                             "Kustom force field"], True, ""),
    ] + [("Basha Lite Kroozer", ["Kustom force field"], False, "")] * 3
      + [("Onslaught Attack Ship", ["Zzapp gun (gunz to FP2)"], False, ""),
         ("reserve:Dominator Cruiser", [], False, "")]),
    ("owner_tyranid_gestating_990.json", "Tyranid Gestating 990", "Tyranid", "tyranid_gestating",
     [("Scylla Strain Bio-Cruiser w/ Synapse Node",
       ["Prow: Pyro-acid Battery", "Thorax: Pyro-acid Battery",
        "Port / Starboard: Launch Glands x2", "Phage mines (glands S4)"], i == 0, "")
      for i in range(2)]
     + [("Tyranid Bio-Cruiser (Guardian)", ["Thorax: Pyro-acid Battery",
                                            "Port / Starboard: Launch Glands"], False, "")] * 2
     + [("Tyranid Bio-Cruiser (Guardian)", ["Thorax: Excretion Ducts",
                                            "Port / Starboard: Launch Glands"], False, ""),
        ("Tyranid Bio-Cruiser (Carnivore)", ["Prow: Massive Claws", "Thorax: Bio-plasma Spines",
                                             "Thorax: Pyro-acid Battery"], False, "")]
     + [("Escort Drone", ["Weapon: Pyro-acid Battery"], False, "drones_a")] * 5
     + [("Escort Drone", ["Weapon: Pyro-acid Battery"], False, "drones_b")] * 5),
    ("owner_tyranid_vanguard_1000.json", "Tyranid Vanguard 1000", "Tyranid", "tyranid_vanguard",
     [("Tyranid Bio-Cruiser (Prowler)", ["Prow: Pyro-acid Battery", "Thorax: Pyro-acid Battery"],
       False, f"prowlers_{i // 3}") for i in range(8)]
     + [("Tyranid Bio-Cruiser (Prowler)", ["Prow: Pyro-acid Battery", "Thorax: Pyro-acid Battery",
                                           "Biomorph: Extra Discharge Vents"], False, "prowlers_2")]),
    ("owner_tyranid_hive_980.json", "Tyranid Hive Fleet 980", "Tyranid", "tyranid_hive",
     [("Charybdis Class Hive Ship", ["Prow: Excretion Ducts", "Thorax: Launch Glands",
                                     "Port / Starboard: Launch Glands x3",
                                     "Biomorph: Reinforced Carapace"], i == 0, "") for i in range(2)]
     + [("Kraken", ["Weapon: Excretion Ducts"], False, "kraken")] * 4
     + [("Escort Drone", ["Weapon: Pyro-acid Battery"], False, "drones_a")] * 6
     + [("Escort Drone", ["Weapon: Pyro-acid Battery"], False, "drones_b")] * 6),
]

# Owner's lists (all 1000pt or under). Mechanicus Gifts: the owner rolls them on the table
# and keeps a good, affordable result (never Fleet Defence Turrets): random, left to the
# player / the AI list builder (To do 24).
GAPS = ["Necrons (Dynasty upgrades: Cartouche, Khopesh, War, nightmare field, Bloodswarm)",
        "Eldar (commanders and fleet lists)"]


def build(root, spec, out_dir):
    fname, name, faction, list_key, ships = spec
    w = FB.FleetBuilderWindow(root)
    names = list(w._faction_combo.cget("values"))
    w._faction_combo.current(next(i for i, n in enumerate(names) if faction.lower() in n.lower()))
    w._on_faction_selected()
    w._list_combo.current(w._list_options.index(list_key))
    w._on_list_selected()
    w._fleet_name_var.set(name)
    w._pts_limit_var.set("1000")
    meta = w._catalog_meta
    for cls, opts, flag, sq in ships:
        reserve = cls.startswith("reserve:")       # e.g. an Ork fleet's looted vessel
        cls = cls.split(":", 1)[1] if reserve else cls
        j = next((j for j, e in enumerate(w._catalog_entries)
                  if e and e.ship_class == cls and meta[j][0].startswith("reserve") == reserve),
                 None)
        if j is None:
            raise SystemExit(f"{name}: {cls} not in the {list_key} catalog")
        entry = w._catalog_entries[j]
        known = {u.name for u in FB.get_upgrades_for_ship(entry)}
        missing = [o for o in opts if o not in known]
        if missing:
            raise SystemExit(f"{name}: {cls} has no option {missing}")
        row = FB._make_fleet_row(entry, upgrades=opts, is_flagship=flag, squadron_id=sq,
                                 list_key=meta[j][0], base_cost=meta[j][1])
        w._fleet.append(row)
    w._refresh_fleet_list()
    ok, errors = w._validate_fleet()
    path = os.path.join(out_dir, fname)
    FB.filedialog.asksaveasfilename = lambda **_k: path
    FB.messagebox.askyesno = lambda *a, **k: True
    FB.messagebox.showinfo = lambda *a, **k: None
    w._save_fleet()
    print(f"{name}: {w._fleet_total()} pts, {'valid' if ok else 'PROBLEMS'} -> {path}")
    for e in errors:
        print("    -", e)
    w.win.destroy()
    return ok


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "fleets")
    root = tk.Tk()
    root.withdraw()
    results = [build(root, f, out) for f in FLEETS]
    print("Not buildable yet (catalog gaps):", "; ".join(GAPS))
    sys.exit(0 if all(results) else 1)
