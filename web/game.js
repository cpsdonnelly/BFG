/**
 * BFG:XR — main game orchestration module.
 *
 * Manages the Web Worker, receives state/dialog messages from Python,
 * drives the board renderer and UI panels.
 */

import { redraw, boardState, screenToWorld, findShipAt } from "./board.js";
import { showYesNo, showInfo, showWarning, showError, showPickFromList } from "./dialogs.js";
import { initTouch } from "./touch.js";
import { updateUI, renderShipList, setStatus } from "./ui.js";

// ── Worker ────────────────────────────────────────────────────────────────────

export let worker = null;
let canvas = null;
let _pendingMoveShipId = null;    // ship waiting for a move-target tap
let _pendingMoveCommands = null;  // commands being built interactively

/** Fetch all Python source files and boot the worker. */
export async function boot() {
    canvas = document.getElementById("board-canvas");
    _resizeCanvas();
    window.addEventListener("resize", _resizeCanvas);

    initTouch(canvas);
    _startRenderLoop();

    worker = new Worker("worker.js");
    worker.onmessage = _onWorkerMessage;

    setStatus("Loading game modules…");

    // Fetch all Python source files
    const pyFiles = await _fetchPyModules();

    worker.postMessage({ type: "init", modules: pyFiles });
}

async function _fetchPyModules() {
    // Paths relative to the web/ directory (same origin)
    const srcFiles = [
        // Core logic modules (no tkinter)
        "py/__init__.py",
        "py/models.py",
        "py/game_state.py",
        "py/dice.py",
        "py/geometry.py",
        "py/los.py",
        "py/tables.py",
        "py/movement.py",
        "py/movement_ui.py",
        "py/combat.py",
        "py/ordnance.py",
        "py/ordnance_movement.py",
        "py/boarding.py",
        "py/hit_and_run.py",
        "py/disengage.py",
        "py/end_phase.py",
        "py/scenario.py",
        "py/victory_points.py",
        "py/squadron.py",
        "py/terrain_effects.py",
        "py/deployment.py",
        "py/turn_controller.py",
        "py/ai_player.py",
        "py/lookahead_ai.py",
        "py/ship_catalog.py",
        "py/homebrew_catalog.py",
        "py/fleet_loader.py",
        "py/campaign.py",
        "py/network.py",
        // Web stubs
        "py/web_ui_stub.py",
        "py/web_game_context.py",
        "py/web_api.py",
    ];

    const modules = {};
    for (const path of srcFiles) {
        try {
            const resp = await fetch(path);
            if (resp.ok) {
                const name = path.split("/").pop();
                modules[name] = await resp.text();
            }
        } catch (_) { /* skip missing */ }
    }
    return modules;
}


// ── Worker message handler ────────────────────────────────────────────────────

function _onWorkerMessage(e) {
    const msg = e.data;

    switch (msg.type) {

        case "ready":
            setStatus("Ready — select a scenario to begin");
            document.getElementById("btn-start").disabled = false;
            break;

        case "loading":
            setStatus(msg.msg);
            break;

        case "state":
            boardState.gs = msg.data;
            redraw(canvas, msg.data);
            updateUI(msg.data);
            renderShipList(msg.data);
            break;

        case "log":
            _appendLog(msg.msg);
            break;

        case "ask_yesno":
            showYesNo(msg.title, msg.msg);
            break;

        case "show_info":
            showInfo(msg.title, msg.msg);
            break;

        case "show_warning":
            showWarning(msg.title, msg.msg);
            break;

        case "show_error":
            showError(msg.title, msg.msg);
            break;

        case "pick_from_list":
            showPickFromList(msg.title, msg.items, msg.max_picks ?? 1);
            break;

        case "game_over":
            showInfo("Game Over", msg.result);
            break;

        case "error":
            console.error("[Worker error]", msg.msg);
            setStatus("Error: " + msg.msg);
            break;
    }
}


// ── Actions ───────────────────────────────────────────────────────────────────

export function sendAction(name, data = {}) {
    worker.postMessage({ type: "action", action: { name, data } });
}

export function startGame(config) {
    worker.postMessage({ type: "start_game", config });
}

/** Called by touch.js when a ship is tapped. */
export function onShipSelected(ship) {
    if (ship) {
        _pendingMoveShipId = null;   // reset pending move
        document.getElementById("btn-move").disabled = false;
        document.getElementById("btn-fire").disabled = false;
    } else {
        document.getElementById("btn-move").disabled = true;
        document.getElementById("btn-fire").disabled = true;
    }
    if (boardState.gs) {
        redraw(canvas, boardState.gs);
    }
}

/** Called by touch.js when the player taps an empty square while a ship is selected. */
export function onMoveTarget(wx, wy) {
    const sid = boardState.selectedShipId;
    if (!sid) return;

    const gs   = boardState.gs;
    const ship = gs ? (gs.ships ?? []).find(s => s.id === sid) : null;
    if (!ship) return;

    // Build a simple "forward to (wx, wy)" command sequence
    const dx = wx - ship.x;
    const dy = wy - ship.y;
    const dist = Math.hypot(dx, dy);
    if (dist < 1) return;

    // Target heading
    const targetHdg = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
    const currentHdg = ship.heading;
    let turnDeg = ((targetHdg - currentHdg + 540) % 360) - 180;

    const commands = [];
    const TURN_ANGLE = ship.turn_angle ?? 45;

    if (Math.abs(turnDeg) > 5) {
        const clampedTurn = Math.max(-TURN_ANGLE, Math.min(TURN_ANGLE, turnDeg));
        const minTD = { battleship: 15, cruiser: 10, escort: 0, defense: 0 }[ship.ship_type] ?? 0;
        if (minTD > 0) {
            commands.push({ type: "forward", value: Math.min(minTD, dist) });
        }
        commands.push({
            type: clampedTurn > 0 ? "turn_right" : "turn_left",
            value: Math.abs(clampedTurn),
        });
    }

    commands.push({ type: "forward", value: Math.round(dist) });

    sendAction("move_ship", { ship_id: sid, commands });
}


// ── Log ───────────────────────────────────────────────────────────────────────

function _appendLog(msg) {
    const log = document.getElementById("game-log");
    if (!log) return;
    const line = document.createElement("div");
    line.className = "log-line";
    line.textContent = msg;
    log.appendChild(line);
    // Keep last 200 lines
    while (log.children.length > 200) log.removeChild(log.firstChild);
    log.scrollTop = log.scrollHeight;
}


// ── Render loop ───────────────────────────────────────────────────────────────

function _startRenderLoop() {
    function frame() {
        if (boardState.gs) redraw(canvas, boardState.gs);
        requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
}

function _resizeCanvas() {
    const c = document.getElementById("board-canvas");
    const wrapper = c.parentElement;
    c.width  = wrapper.clientWidth;
    c.height = wrapper.clientHeight;
}
