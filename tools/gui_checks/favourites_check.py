"""To do 27: the favourites prompt saves the ticked fleets and then goes on."""
import os
import shutil
import sys
import tempfile
import tkinter as tk

sys.path.insert(0, ".")
import src.favourites as F                                  # noqa: E402
from src.favourites_ui import offer_favourites              # noqa: E402

tmp = tempfile.mkdtemp()
F.FAV_DIR = os.path.join(tmp, "fav")
root = tk.Tk()
done = []
offer_favourites(root, {1: "data/fleets/owner_gothic_1000.json",
                        2: "data/fleets/owner_chaos_1000.json"},
                 {1: "Gothic", 2: "Chaos"}, on_done=lambda: done.append(True))
root.update()
dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][0]
checks = [w for w in dlg.winfo_children() if isinstance(w, tk.Checkbutton)]
checks[0].invoke()                                            # Player 1 only
save = next(w for f in dlg.winfo_children() for w in f.winfo_children()
            if isinstance(w, tk.Button) and w.cget("text") == "Save")
save.invoke()
saved = F.favourite_fleets(F.FAV_DIR)
ok = done == [True] and len(saved) == 1
print("  saved:", [os.path.basename(s) for s in saved])
root.destroy()
shutil.rmtree(tmp)
print("RESULT:", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
