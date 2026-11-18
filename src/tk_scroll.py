"""A scrolling area for dialogs taller than the screen (To do 32): the
dialog's buttons are packed outside it, so they stay visible however much
the area holds. Minimal Tk (owner: the full window is built in the browser)."""
import tkinter as tk


def fit_height(widget, wanted: int, margin: int = 80) -> int:
    """`wanted` pixels, or the screen's height less a margin if that's less."""
    try:
        return max(300, min(wanted, widget.winfo_screenheight() - margin))
    except tk.TclError:
        return wanted


def scroll_body(parent, bg=None, height: int = 200) -> tk.Frame:
    """Pack a vertically scrolling area into `parent` (filling the space left
    after the widgets packed after it get theirs) and return the frame to put
    widgets in. The mouse wheel scrolls it while the pointer is over it."""
    kw = {"bg": bg} if bg else {}
    outer = tk.Frame(parent, **kw)
    outer.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    canvas = tk.Canvas(outer, highlightthickness=0, height=height, **kw)
    bar = tk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=bar.set)
    bar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    body = tk.Frame(canvas, **kw)
    item = canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))

    def _wheel(e):
        step = -1 if (getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0) else 1
        canvas.yview_scroll(step * 3, "units")

    def _on(_e):
        canvas.bind_all("<MouseWheel>", _wheel)
        canvas.bind_all("<Button-4>", _wheel)
        canvas.bind_all("<Button-5>", _wheel)

    def _off(_e):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.unbind_all(seq)

    outer.bind("<Enter>", _on)
    outer.bind("<Leave>", _off)
    body.canvas = canvas
    return body
