"""Tk where it is installed, a placeholder where it isn't (To do 18): the game
flow and its panels import their dialogs' toolkit from here, so a headless
game (headless_game.py) runs on a Python without tkinter. The placeholder
stands in for names used at import time (annotations); using it raises."""


class _NoTk:
    def __init__(self, name="tkinter"):
        self._name = name

    def __getattr__(self, attr):
        return _NoTk(f"{self._name}.{attr}")

    def __call__(self, *a, **k):
        raise RuntimeError(f"{self._name}: Tk isn't installed (a window needs it)")


try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog, ttk
    HAS_TK = True
except ImportError:                      # headless: no windows on this Python
    tk, messagebox, simpledialog, ttk = (_NoTk("tkinter"), _NoTk("messagebox"),
                                         _NoTk("simpledialog"), _NoTk("ttk"))
    HAS_TK = False
