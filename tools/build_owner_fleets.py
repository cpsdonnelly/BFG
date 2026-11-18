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
]

# Owner's lists (all 1000pt or under). Mechanicus Gifts: the owner rolls them on the table
# and keeps a good, affordable result (never Fleet Defence Turrets): random, left to the
# player / the AI list builder (To do 24).
GAPS = ["Tau Protector (Emissary options: ion cannons for hooks, mine launchers, deflector)",
        "Orks (kustom force field, the Onslaught's zzapp gun swap, looted vessels)",
        "Necrons (Dynasty upgrades: Cartouche, Khopesh, War, nightmare field, Bloodswarm)",
        "Eldar (commanders and fleet lists)", "Dark Eldar and Tyranids (To do 19)"]


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
        j = next((j for j, e in enumerate(w._catalog_entries)
                  if e and e.ship_class == cls and not meta[j][0].startswith("reserve")), None)
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
