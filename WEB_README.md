# BFG:XR — Web Client

This directory contains the browser-based version of the Battlefleet Gothic simulator. It runs the existing Python game engine directly in the browser via [Pyodide](https://pyodide.org) (Python compiled to WebAssembly) — no server, no install, no local process required.

**The desktop Tkinter app (`src/`, `main.py`, `*.py` in the root) is completely unchanged.** All web files are additive only.

---

## Branch

All web client work lives on branch `claude/battlefleet-gothic-simulator-3sUkl`. The `main` branch is untouched.

---

## How it works (brief)

1. You visit the deployed URL on any device (phone, tablet, desktop).
2. The browser downloads the Pyodide WebAssembly runtime (~8 MB, cached after first visit).
3. A Web Worker loads all Python game modules via Pyodide.
4. The board renders on an HTML5 Canvas using geometric primitives (circles, lines) — same visual style as the desktop board.
5. When Python needs a player decision mid-computation (e.g. brace-for-impact, repair selection), it blocks the Worker using `Atomics.wait()`; a dialog appears in the browser; your answer unblocks Python.

---

## Deployment

### Prerequisites

You need a free [Netlify](https://netlify.com) **or** [Cloudflare Pages](https://pages.cloudflare.com) account. Both are completely free for personal projects.

**GitHub Pages will NOT work** — it cannot serve the `Cross-Origin-Opener-Policy` and `Cross-Origin-Embedder-Policy` headers that browsers require before enabling SharedArrayBuffer (which is how Python dialogs block correctly).

---

### Option A — Netlify (recommended)

1. Push this branch to GitHub (or your own fork).

2. Log in to [netlify.com](https://netlify.com) → **Add new site → Import an existing project**.

3. Connect your GitHub account and select the repository.

4. Set the build settings:
   | Setting | Value |
   |---|---|
   | **Branch to deploy** | `claude/battlefleet-gothic-simulator-3sUkl` (or `main` once merged) |
   | **Build command** | `python scripts/build_web.py` |
   | **Publish directory** | `web` |

5. Click **Deploy site**.

The `netlify.toml` at the repo root already handles the COOP/COEP headers automatically — you don't need to configure anything in the Netlify dashboard for headers.

Your site will be live at `https://<random-name>.netlify.app` within a minute or two. You can set a custom subdomain in **Site settings → Domain management**.

---

### Option B — Cloudflare Pages

1. Log in to [dash.cloudflare.com](https://dash.cloudflare.com) → **Pages → Create a project → Connect to Git**.

2. Select your repository and set:
   | Setting | Value |
   |---|---|
   | **Production branch** | your branch name |
   | **Build command** | `python scripts/build_web.py` |
   | **Build output directory** | `web` |

3. Add the required HTTP headers. In your repo, create or edit `web/_headers`:

   ```
   /*
     Cross-Origin-Opener-Policy: same-origin
     Cross-Origin-Embedder-Policy: require-corp
   ```

   Cloudflare Pages reads this file automatically. (The `netlify.toml` is ignored by Cloudflare.)

4. Click **Save and Deploy**.

---

### Manual build (optional local preview)

If you want to test locally with a server that can serve the right headers (e.g. via a custom Python server), first run the build step:

```bash
python scripts/build_web.py
```

This copies all `src/*.py` files into `web/py/` so Pyodide can fetch them. You **must** run this after any change to the Python source. On Netlify/Cloudflare it runs automatically on each deploy.

> Note: You cannot simply open `web/index.html` as a `file://` URL — the browser will block fetching local files and SharedArrayBuffer. You need a proper HTTP server with the COOP/COEP headers, or use the deployed URL.

---

## Playing the game

1. Visit the deployed URL.
2. Wait for the loading screen — Pyodide downloads on first visit (~10 s on a decent connection; subsequent visits are near-instant thanks to browser caching).
3. Click **Start Demo Game**.
4. The demo scenario loads: two Imperial cruisers vs two Tau cruisers on a 120×120 cm board. Player 2 is AI-controlled.

### Controls

| Input | Action |
|---|---|
| Tap / click a ship | Select it (highlights in ship list too) |
| Drag (one finger / mouse) | Pan the board |
| Pinch / mouse wheel | Zoom in/out |
| Double-tap | Centre view on selected ship |

### Turn sequence

Use the buttons in the right panel (desktop) or bottom drawer (mobile):

1. **Movement Phase** — select a ship → *Special Order…* or *Move Ship…*, then *End Movement →*
2. **Shooting Phase** — select a ship → *Fire Weapons…*, then *End Shooting →*
3. **Ordnance Phase** — *Move Ordnance*, then *End Ordnance →*
4. **End Phase** — *Resolve End Phase*, then *Next Turn →*

**Run AI Turn** triggers the AI to play the active player's turn automatically.

---

## File layout

```
web/
├── index.html          SPA shell, CSS, layout
├── game.js             Boot, worker bridge, action dispatch
├── worker.js           Web Worker — Pyodide + Python game engine
├── board.js            Canvas2D renderer (geometric primitives)
├── ui.js               Phase panels, ship list, action buttons
├── dialogs.js          HTML overlay dialogs (yes/no, pick list, info)
├── touch.js            Pointer events (touch + mouse + stylus)
├── py/                 Generated by build_web.py — do not edit
│   └── *.py            Copies of src/*.py fetched by Pyodide
└── scenarios/
    └── demo.json       4-ship demo scenario

src/
├── web_api.py          Pyodide entry points (init / start_game / perform_action)
├── web_game_context.py Headless game loop (no Tkinter)
├── web_ui_stub.py      Blocking dialog stub via Atomics.wait()
└── … (all existing files unchanged)

scripts/
└── build_web.py        Copies src/*.py → web/py/

netlify.toml            Build config + COOP/COEP headers for Netlify
```

---

## Troubleshooting

**"SharedArrayBuffer is not defined"** — Your server isn't sending the COOP/COEP headers. Use Netlify or Cloudflare Pages, not GitHub Pages or a plain HTTP server.

**Blank screen / console errors on first load** — Open browser DevTools (F12) → Console. Usually a missing Python file or a typo in the scenario JSON.

**Python import error in console** — Run `python scripts/build_web.py` locally and verify `web/py/` contains all `.py` files, then redeploy.

**Pyodide taking > 30 s** — Normal on first visit on a slow connection. The runtime is ~8 MB; it caches after first download.

**Dialog doesn't appear** — Make sure you're using a browser that supports SharedArrayBuffer (Chrome 92+, Firefox 79+, Safari 15.2+, Edge 92+).

---

## Limitations vs. desktop

- No LAN multiplayer (the web client is single-device; a future WebRTC peer-to-peer mode could add this)
- No campaign persistence across sessions yet (save/load to browser localStorage is planned)
- No fleet builder UI yet — the demo scenario is fixed; custom scenarios require editing `web/scenarios/demo.json`
