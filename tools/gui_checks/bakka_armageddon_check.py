"""Bakka and Armageddon lists in the real fleet builder: starred +1 Turret on save,
Mechanicus cruisers as battlecruisers, Armageddon variants at full price."""
import os, sys, json, tempfile, tkinter as tk
from tkinter import messagebox, filedialog
sys.path.insert(0, "/home/user/BFG"); os.chdir("/home/user/BFG")
from src import fleet_builder as fb

for n in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: True
fb.messagebox = messagebox
out = os.path.join(tempfile.mkdtemp(), "bakka.json")
filedialog.asksaveasfilename = lambda **k: out
fb.filedialog = filedialog
failures = []
def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond: failures.append(label)

root = tk.Tk(); root.withdraw()
w = fb.FleetBuilderWindow(root); root.update()
def pick_faction(fid):
    w._faction_combo.current(w._faction_ids.index(fid)); w._on_faction_selected(); root.update()
def pick_list(key):
    w._list_combo.current(w._list_options.index(key)); w._on_list_selected(); root.update()
def add(name, key):
    idx = next(i for i, e in enumerate(w._catalog_entries)
               if e is not None and e.ship_class == name and w._catalog_meta[i][0] == key)
    w._catalog_list.selection_clear(0, tk.END); w._catalog_list.selection_set(idx); w._add_selected()

pick_faction("imperial_navy_gothic"); pick_list("navy_bakka")
add("Lunar Cruiser", "navy_bakka"); add("Mechanicus Lunar Cruiser", "navy_bakka")
add("Siluria Light Cruiser", "navy_bakka")
w._save_fleet()
ships = json.load(open(out))["ships"]
check(ships[0]["turrets"] == 3, f"Bakka Lunar 2+1 turrets: {ships[0]['turrets']}")
check(ships[1]["points_value"] == 215, f"Mechanicus Lunar at 215: {ships[1]['points_value']}")

w._fleet.clear(); w._refresh_fleet_list(); pick_list("navy_armageddon")
add("Strike Cruiser", "navy_armageddon")
w._fleet[0]["upgrades"] = ["Variant: macrobatteries to launch bays"]
w._reprice_fleet()
check(w._fleet_total() == 145 + 20, f"Armageddon variant at full price: {w._fleet_total()}")
w._save_fleet()
check(json.load(open(out))["ships"][0]["points_value"] == 165, "saved ship points 165")
w._fleet.clear(); w._refresh_fleet_list()
pick_faction("rogue_traders"); pick_list("rt_wolf_pack")
add("Fra'al Raider (Notable Xenos)", "rt_wolf_pack"); add("Fra'al Raider (Notable Xenos)", "rt_wolf_pack")
for r in w._fleet:
    r["squadron_id"] = "x"
check(w._fleet_total() == 35 * 2 + 30, f"Notable Xenos squadron 2x35 + 30: {w._fleet_total()}")
w._save_fleet()
pv = [s["points_value"] for s in json.load(open(out))["ships"]]
check(pv == [65, 35], f"saved squadron cost on the first ship: {pv}")
w._fleet.clear(); w._refresh_fleet_list()
pick_faction("tau_kororvesh"); pick_list("tau_demiurg_war_host")
res = [e.ship_class for e, m in zip(w._catalog_entries, w._catalog_meta)
       if e is not None and m[0] == "reserve:tau_empire"]
check("Protector Cruiser" in res and "Hero Starship" not in res,
      f"War Host reserves are Kor'or'vesh only: {res}")
add("Bastion Commerce Vessel", "tau_demiurg_war_host"); add("Citadel Commerce Vessel", "tau_demiurg_war_host")
w._pts_limit_var.set("800")
ok, errs = w._validate_fleet()
check(ok, f"two Demiurg ships validate with no commander: {errs}")
print("FAILURES:", failures) if failures else print("all ok")
