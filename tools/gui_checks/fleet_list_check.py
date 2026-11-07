"""Fleet list selection in the real fleet builder: list choice, catalog by
section at list costs, detachment, reserves, validation, save and load."""
import os, sys, json, tempfile, tkinter as tk
from tkinter import messagebox, filedialog
sys.path.insert(0, "/home/user/BFG"); os.chdir("/home/user/BFG")
from src import fleet_builder as fb

shown = []
for n in ("showinfo", "showwarning", "showerror"):
    setattr(messagebox, n, lambda *a, **k: shown.append(a))
messagebox.askyesno = lambda *a, **k: True
fb.messagebox = messagebox
out = os.path.join(tempfile.mkdtemp(), "list_fleet.json")
filedialog.asksaveasfilename = lambda **k: out
fb.filedialog = filedialog

failures = []
def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond: failures.append(label)

root = tk.Tk(); root.withdraw()
w = fb.FleetBuilderWindow(root)
root.update()

def pick_faction(fid):
    w._faction_combo.current(w._faction_ids.index(fid)); w._on_faction_selected(); root.update()

def pick_list(key):
    w._list_combo.current(w._list_options.index(key)); w._on_list_selected(); root.update()

def add(name, key=None):
    lst = w._catalog_list
    idx = next(i for i, e in enumerate(w._catalog_entries)
               if e is not None and e.ship_class == name
               and (key is None or w._catalog_meta[i][0] == key))
    lst.selection_clear(0, tk.END); lst.selection_set(idx); w._add_selected()

print("1. Navy: a list is chosen by default; catalog is by section")
pick_faction("imperial_navy_gothic")
check(w._list_key == "navy_gothic", f"default list {w._list_key}")
items = w._catalog_list.get(0, tk.END)
check(items[0] == "— Battleships —", f"first row is a header: {items[0]}")
check(not any("Siluria" in i for i in items if "RES" not in i), "Siluria not in Gothic list")

print("2. Bakka costs")
pick_list("navy_bakka")
add("Gothic Cruiser", "navy_bakka")
check(w._fleet[-1]["points"] == 185 and w._fleet[-1]["list"] == "navy_bakka",
      f"Bakka Gothic 185pts: {w._fleet[-1]['points']}")

print("3. Back to Gothic: the fleet is repriced")
pick_list("navy_gothic")
w._fleet.clear(); w._refresh_fleet_list()
for n in ("Emperor Battleship", "Gothic Cruiser", "Lunar Cruiser"):
    add(n, "navy_gothic")
w._pts_limit_var.set("1500")
ok, errs = w._validate_fleet()
check(any(e.startswith("Battleships") for e in errs), f"battleship ratio error: {errs}")
add("Tyrant Cruiser", "navy_gothic")
ok, errs = w._validate_fleet()
check(ok, f"valid with three cruisers: {errs}")

print("4. Detachment and reserves")
dets = w._det_options
check("inq_detachment" in dets, f"Inquisition detachment offered: {dets}")
w._det_combo.current(dets.index("inq_detachment")); w._on_detachment_selected(); root.update()
add("Inquisitorial Cruiser", "inq_detachment")
add("Mechanicus Lunar Cruiser", "reserve:admech_explorator")
ok, errs = w._validate_fleet()
check(ok, f"one Inquisitorial cruiser and one reserve per three cruisers: {errs}")
check(any("(reserve)" in i for i in w._fleet_list.get(0, tk.END)), "reserve tagged in the fleet")

print("5. Save and load keep the list")
w._save_fleet()
data = json.load(open(out))
check(data["fleet_list"] == "navy_gothic" and data["detachments"] == ["inq_detachment"],
      f"saved list: {data['fleet_list']} {data['detachments']}")
check([s.get("fleet_list") for s in data["ships"]][-2:] == ["inq_detachment",
                                                            "reserve:admech_explorator"],
      f"ship lists saved: {[s.get('fleet_list') for s in data['ships']]}")
w2 = fb.FleetBuilderWindow(root, load_path=out)
root.update()
check(w2._list_key == "navy_gothic" and w2._detachment_key == "inq_detachment",
      "loaded list and detachment")
check(len(w2._fleet) == 6 and w2._validate_fleet()[0], "loaded fleet valid")

print("6. No fleet list")
pick_list("")
check(w._catalog_list.get(0).startswith("[BAT]"), "whole faction catalog again")
check(fb.FleetBuilderWindow is not None, "done")
root.destroy()
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
