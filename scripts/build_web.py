"""Build step: copies src/*.py into web/py/ so Pyodide can fetch them."""
import os
import shutil

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
DST = os.path.join(os.path.dirname(__file__), "..", "web", "py", "src")

os.makedirs(DST, exist_ok=True)

copied = 0
for fname in os.listdir(SRC):
    if fname.endswith(".py"):
        shutil.copy2(os.path.join(SRC, fname), os.path.join(DST, fname))
        copied += 1

print(f"Copied {copied} Python files to web/py/")
