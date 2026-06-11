/**
 * BFG:XR Web Worker — loads Pyodide + game modules; bridges postMessage ↔ Python.
 *
 * SharedArrayBuffer layout (Int32Array, 8 bytes):
 *   index 0 = signal: 0 = Python waiting, 1 = JS has written an answer
 *   index 1 = bool result (0/1) for yes/no questions
 *
 * String results (pick_from_list) go through self._web_str_response.
 */

importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.0/full/pyodide.js");

// SharedArrayBuffer — must be created in the worker because GitHub Pages can't
// set COOP/COEP; we rely on Netlify/Cloudflare to serve those headers.
const _sab    = new SharedArrayBuffer(8);
const _sabI32 = new Int32Array(_sab);

// String response slot (read by Python via js._web_str_response)
self._web_str_response = "";

let pyodide = null;
let pyodideReady = false;

self.onmessage = async (e) => {
    const msg = e.data;

    if (msg.type === "init") {
        await _boot(msg.modules);
        return;
    }

    if (!pyodideReady) {
        self.postMessage({ type: "error", msg: "Pyodide not ready yet" });
        return;
    }

    if (msg.type === "start_game") {
        const state = pyodide.runPython(
            `from src.web_api import start_game; start_game(cfg_json)`,
            { locals: { cfg_json: JSON.stringify(msg.config) } }
        );
        self.postMessage({ type: "state", data: JSON.parse(state) });
        return;
    }

    if (msg.type === "action") {
        const state = pyodide.runPython(
            `from src.web_api import perform_action; perform_action(act_json)`,
            { locals: { act_json: JSON.stringify(msg.action) } }
        );
        self.postMessage({ type: "state", data: JSON.parse(state) });
        return;
    }

    if (msg.type === "response") {
        // Unblock the Python worker thread waiting in web_ui_stub._block()
        if (typeof msg.value === "boolean") {
            _sabI32[1] = msg.value ? 1 : 0;
        } else {
            // String or array — store for Python to read
            self._web_str_response =
                typeof msg.value === "string" ? msg.value : JSON.stringify(msg.value);
        }
        Atomics.store(_sabI32, 0, 1);   // signal "answer ready"
        Atomics.notify(_sabI32, 0, 1);  // wake the blocked Python thread
        return;
    }
};


async function _boot(modules) {
    self.postMessage({ type: "loading", msg: "Loading Pyodide runtime…" });

    pyodide = await loadPyodide();

    self.postMessage({ type: "loading", msg: "Installing game modules…" });

    // Write every Python source file into Pyodide's virtual filesystem as a package
    pyodide.FS.mkdir("/home/pyodide/src");
    for (const [name, src] of Object.entries(modules)) {
        pyodide.FS.writeFile(`/home/pyodide/src/${name}`, src);
    }

    // Point sys.path at /home/pyodide so `import src.web_api` resolves
    pyodide.runPython(`
import sys, os
sys.path.insert(0, "/home/pyodide")
os.makedirs("/saves/bfg_web", exist_ok=True)
`);

    // Pass the SharedArrayBuffer Int32Array view to Python
    pyodide.globals.set("_sab_int32", _sabI32);

    // Initialise web_api (sets up web_ui_stub._sab and creates WebGameContext)
    pyodide.runPython(`
from src.web_api import init
init(_sab_int32)
`);

    pyodideReady = true;
    self.postMessage({ type: "ready" });
}
