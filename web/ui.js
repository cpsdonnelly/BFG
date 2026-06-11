/**
 * BFG:XR — UI panels: phase indicator, action buttons, ship list, status bar.
 */

import { boardState } from "./board.js";
import { sendAction, startGame } from "./game.js";

const PHASE_LABELS = {
    movement: "Movement Phase",
    shooting: "Shooting Phase",
    ordnance: "Ordnance Phase",
    end:      "End Phase",
    setup:    "Setup",
};

const PHASE_COLORS = {
    movement: "#2255aa",
    shooting: "#aa3333",
    ordnance: "#336633",
    end:      "#664422",
    setup:    "#333344",
};

// ── Status bar ────────────────────────────────────────────────────────────────

export function setStatus(msg) {
    const el = document.getElementById("status-bar");
    if (el) el.textContent = msg;
}


// ── Top bar / phase indicator ─────────────────────────────────────────────────

export function updateUI(gs) {
    const phase   = gs.current_phase ?? "setup";
    const phaseEl = document.getElementById("phase-label");
    if (phaseEl) {
        phaseEl.textContent = PHASE_LABELS[phase] ?? phase;
        phaseEl.style.background = PHASE_COLORS[phase] ?? "#333344";
    }

    const turnEl = document.getElementById("turn-label");
    if (turnEl) {
        const pname = gs.active_player === 1 ? gs.player1_name : gs.player2_name;
        const pcolor = gs.active_player === 1
            ? _playerCSSColor(gs.player1_color) : _playerCSSColor(gs.player2_color);
        turnEl.innerHTML =
            `Turn ${gs.turn} &nbsp;|&nbsp; <span style="color:${pcolor}">${_esc(pname)}</span>`;
    }

    // Update action buttons based on phase
    _updateActionButtons(gs);
}

function _updateActionButtons(gs) {
    const phase = gs.current_phase ?? "setup";
    const sel   = boardState.selectedShipId;

    _show("panel-movement", phase === "movement");
    _show("panel-shooting", phase === "shooting");
    _show("panel-ordnance", phase === "ordnance");
    _show("panel-end",      phase === "end");

    if (phase === "movement") {
        const remaining = (gs.ships ?? []).filter(s =>
            s.player === gs.active_player
            && !s.is_destroyed && !s.is_disengaged
            && !(gs.ships_moved ?? []).includes(s.id)).length;
        const el = document.getElementById("movement-remaining");
        if (el) el.textContent = `${remaining} ship(s) to move`;
    }
}


// ── Ship list panel ───────────────────────────────────────────────────────────

export function renderShipList(gs) {
    const listEl = document.getElementById("ship-list");
    if (!listEl) return;
    listEl.innerHTML = "";

    for (const s of (gs.ships ?? [])) {
        if (s.status === "destroyed") continue;
        const isActive = s.player === gs.active_player;
        const isSelected = s.id === boardState.selectedShipId;
        const playerColor = s.player === 1
            ? _playerCSSColor(gs.player1_color)
            : _playerCSSColor(gs.player2_color);

        const card = document.createElement("div");
        card.className = "ship-card" + (isSelected ? " selected" : "");
        card.style.borderLeftColor = playerColor;
        if (!isActive) card.style.opacity = "0.5";

        const hpFrac = s.hits_max > 0 ? s.hits_remaining / s.hits_max : 0;
        const hpColor = hpFrac > 0.5 ? "#33CC33" : (hpFrac > 0.25 ? "#CCAA00" : "#CC3333");
        const orderLabel = s.special_order && s.special_order !== "none"
            ? ` [${s.special_order.replace(/_/g, " ")}]` : "";
        const statusLabel = s.is_crippled ? " CRIPPLED" : (s.status !== "ok" ? " " + s.status.toUpperCase() : "");

        card.innerHTML = `
            <div class="ship-name">${_esc(s.name)}</div>
            <div class="ship-stats">
                <span style="color:${hpColor}">${s.hits_remaining}/${s.hits_max} HP</span>
                <span class="ship-order">${_esc(orderLabel)}${_esc(statusLabel)}</span>
            </div>
            <div class="hp-bar">
                <div class="hp-fill" style="width:${Math.round(hpFrac * 100)}%; background:${hpColor}"></div>
            </div>
        `;

        card.onclick = () => {
            boardState.selectedShipId = s.id;
        };

        listEl.appendChild(card);
    }
}


// ── Setup / start game dialog ─────────────────────────────────────────────────

export function initSetupDialog() {
    document.getElementById("btn-start").onclick = _openSetupDialog;
}

function _openSetupDialog() {
    // Load a preset scenario config bundled as scenarios/demo.json
    fetch("scenarios/demo.json")
        .then(r => r.json())
        .then(cfg => {
            startGame(cfg);
            document.getElementById("setup-overlay").style.display = "none";
        })
        .catch(err => {
            console.error(err);
            alert("Could not load demo scenario: " + err.message);
        });
}


// ── Button wiring (called from index.html DOMContentLoaded) ──────────────────

export function initButtons() {
    // Movement phase
    document.getElementById("btn-move")?.addEventListener("click", () => {
        const sid = boardState.selectedShipId;
        if (!sid) return;
        // Open a simple heading/distance prompt
        _promptMoveDialog(sid);
    });

    document.getElementById("btn-end-movement")?.addEventListener("click", () => {
        sendAction("next_phase");
    });

    // Shooting phase
    document.getElementById("btn-fire")?.addEventListener("click", () => {
        const sid = boardState.selectedShipId;
        if (!sid) return;
        _promptFireDialog(sid);
    });

    document.getElementById("btn-end-shooting")?.addEventListener("click", () => {
        sendAction("next_phase");
    });

    // Ordnance phase
    document.getElementById("btn-move-ordnance")?.addEventListener("click", () => {
        sendAction("move_ordnance");
    });

    document.getElementById("btn-end-ordnance")?.addEventListener("click", () => {
        sendAction("next_phase");
    });

    // End phase
    document.getElementById("btn-resolve-end")?.addEventListener("click", () => {
        sendAction("resolve_end");
    });

    document.getElementById("btn-end-endphase")?.addEventListener("click", () => {
        sendAction("next_phase");
    });

    // Special orders button
    document.getElementById("btn-order")?.addEventListener("click", () => {
        const sid = boardState.selectedShipId;
        if (!sid) return;
        _promptOrderDialog(sid);
    });

    // Run AI button (for spectator mode)
    document.getElementById("btn-run-ai")?.addEventListener("click", () => {
        sendAction("run_ai");
    });
}

// ── Simple prompt dialogs ────────────────────────────────────────────────────

function _promptMoveDialog(shipId) {
    const gs   = boardState.gs;
    const ship = gs ? (gs.ships ?? []).find(s => s.id === shipId) : null;
    if (!ship) return;

    const dist = prompt(
        `Move ${ship.name}\nEnter distance in cm (current heading: ${Math.round(ship.heading)}°):`,
        String(ship.speed ?? 20));
    if (!dist) return;

    const turnDir = prompt("Turn? (left / right / none):", "none");
    const turnDeg = prompt("Turn angle in degrees (0 if none):", "0");

    const commands = [];
    const d  = parseFloat(dist) || 0;
    const td = parseFloat(turnDeg) || 0;

    const minTD = { battleship: 15, cruiser: 10 }[ship.ship_type] ?? 0;
    if (td > 0 && minTD > 0) commands.push({ type: "forward", value: minTD });
    if (td > 0) commands.push({ type: turnDir === "right" ? "turn_right" : "turn_left", value: td });
    commands.push({ type: "forward", value: Math.max(0, d - (td > 0 ? minTD : 0)) });

    sendAction("move_ship", { ship_id: shipId, commands });
}

function _promptFireDialog(shipId) {
    const gs   = boardState.gs;
    const ship = gs ? (gs.ships ?? []).find(s => s.id === shipId) : null;
    if (!ship) return;

    const enemies = (gs.ships ?? []).filter(s =>
        s.player !== ship.player && !s.is_destroyed && !s.is_disengaged);
    if (!enemies.length) {
        alert("No enemy ships available");
        return;
    }

    const names = enemies.map((s, i) => `${i}: ${s.name}`).join("\n");
    const idx   = parseInt(prompt(`${ship.name} — choose target:\n${names}`, "0"));
    if (isNaN(idx) || idx < 0 || idx >= enemies.length) return;

    sendAction("fire", {
        attacker_id:    shipId,
        target_id:      enemies[idx].id,
        weapon_indices: null,   // fire all eligible weapons
    });
}

function _promptOrderDialog(shipId) {
    const orders = [
        "all_ahead_full",
        "burn_retros",
        "come_to_new_heading",
        "lock_on",
        "reload_ordnance",
        "brace_for_impact",
    ];
    const labels = orders.map((o, i) => `${i}: ${o.replace(/_/g, " ")}`).join("\n");
    const idx = parseInt(prompt(`Special order:\n${labels}`, "0"));
    if (isNaN(idx) || idx < 0 || idx >= orders.length) return;
    sendAction("issue_order", { ship_id: shipId, order: orders[idx] });
}


// ── Helpers ───────────────────────────────────────────────────────────────────

function _show(id, visible) {
    const el = document.getElementById(id);
    if (el) el.style.display = visible ? "flex" : "none";
}

function _esc(str) {
    return String(str ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

const _cssColors = {
    red:    "#CC3333", blue:  "#3366CC", green: "#33AA33",
    yellow: "#CCAA00", purple:"#8833AA", orange:"#DD6600",
    black:  "#222222", white: "#DDDDDD", pink:  "#DD66AA",
};
function _playerCSSColor(name) { return _cssColors[name] ?? "#AAAAAA"; }
