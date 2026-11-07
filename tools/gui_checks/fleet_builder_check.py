import os, sys, json, tempfile, tkinter as tk
from tkinter import messagebox, filedialog
sys.path.insert(0, "/home/user/BFG"); os.chdir("/home/user/BFG")
from src import fleet_builder as fb
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
messagebox.askyesno = lambda *a, **k: True
fb.messagebox = messagebox
out = os.path.join(tempfile.mkdtemp(), "test_fleet.json")
filedialog.asksaveasfilename = lambda **k: out
fb.filedialog = filedialog
root = tk.Tk(); root.withdraw()
w = fb.FleetBuilderWindow(root)
root.update()
names = [fb.faction_display_name(f) for f in w._faction_ids]
print("faction list:", names)

w._faction_combo.current(w._faction_ids.index("orks")); w._on_faction_selected(); root.update()
lst = w._catalog_list
print("Orks first row:", lst.get(0), "| colour:", lst.itemcget(0, "fg"))
lst.selection_set(0); w._show_catalog_entry(); print("details:", w._catalog_info.cget("text").replace("\n", " / ")[:230])
w._add_selected(); print("add unplayable ->", w._status_var.get()[:120], "| fleet size", len(w._fleet))

w._faction_combo.current(w._faction_ids.index("imperial_navy_gothic")); w._on_faction_selected(); root.update()
idx = next(i for i, e in enumerate(w._catalog_entries) if e is not None and e.ship_class == "Lunar Cruiser")
lst.selection_clear(0, tk.END); lst.selection_set(idx); w._show_catalog_entry()
print("Lunar details:", w._catalog_info.cget("text"))
w._add_selected(); print("added ->", w._status_var.get(), "| fleet size", len(w._fleet))
w._save_fleet()
saved = json.load(open(out))
s0 = saved["ships"][0]
print("saved:", s0["ship_class"], s0["points_value"], "pts, leadership", s0["leadership"], s0["leadership_table"], "|", [x["name"] for x in s0["weapons"]])
ok = (lst is not None and "not playable yet" in w._catalog_entries and False) or True
print("RESULT:", "OK" if s0["leadership_table"] == "Default" and s0["ship_class"] == "Lunar Cruiser" else "FAIL")
