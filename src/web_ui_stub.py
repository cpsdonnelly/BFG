"""Drop-in replacement for tkinter.messagebox and pick_ship for Pyodide web context.

Python game logic runs in a Web Worker.  When it needs player input it:
  1. Posts a message to the main thread (JS).
  2. Blocks the worker thread via Atomics.wait() on a SharedArrayBuffer.
  3. JS shows the dialog, user responds, JS writes the answer and calls Atomics.notify().
  4. Python reads the answer and continues.

Requires COOP + COEP headers so SharedArrayBuffer is available in the worker.
"""
import js
from pyodide.ffi import to_js

# Set by web_api.init(): an Int32Array view of a SharedArrayBuffer.
# Index 0 = signal sentinel (0 = waiting, 1 = JS has written an answer).
# Index 1 = bool result (0/1) for yes/no questions.
_sab = None


def _block() -> None:
    """Block the Web Worker until JS writes an answer and calls Atomics.notify()."""
    from js import Atomics
    Atomics.store(_sab, 0, 0)   # clear signal so JS knows we are waiting
    Atomics.wait(_sab, 0, 0)    # BLOCKS worker until signal != 0


def _send_and_block(payload: dict) -> None:
    js.postMessage(to_js(payload))
    _block()


# ── Messagebox replacements ───────────────────────────────────────────────────

def askyesno(title: str, msg: str, **_) -> bool:
    _send_and_block({"type": "ask_yesno", "title": title, "msg": msg})
    return bool(_sab[1])


def showinfo(title: str, msg: str, **_) -> None:
    _send_and_block({"type": "show_info", "title": title, "msg": msg})


def showwarning(title: str, msg: str, **_) -> None:
    _send_and_block({"type": "show_warning", "title": title, "msg": msg})


def showerror(title: str, msg: str, **_) -> None:
    _send_and_block({"type": "show_error", "title": title, "msg": msg})


# ── List-selection helper (pick_ship, repair choices) ─────────────────────────

def pick_from_list(title: str, items: list, max_picks: int = 1) -> str:
    """Send a list of items to JS; block until JS sends back a JSON string result.

    For max_picks=1 (ship picker): returns a single item string.
    For max_picks>1 (repair choice): returns a JSON-encoded list of chosen items.
    """
    _send_and_block({
        "type": "pick_from_list",
        "title": title,
        "items": items,
        "max_picks": max_picks,
    })
    # JS writes the response into self._web_str_response in the worker scope.
    return str(js._web_str_response)
