/**
 * BFG:XR touch + mouse input handler.
 *
 * Tap (< 200 ms, < 5 px travel)  → select/deselect ship or place move target
 * One-finger drag                 → pan board
 * Two-finger pinch                → zoom
 * Double-tap                      → centre on selected ship
 */

import { boardState, worldToScreen, screenToWorld, findShipAt } from "./board.js";
import { onShipSelected, onMoveTarget } from "./game.js";

let _pointers = {};          // pointerId → {x, y}
let _dragStart = null;       // {panX, panY, midX, midY, dist}
let _tapStart  = null;       // {x, y, t}
let _lastTap   = 0;

export function initTouch(canvas) {
    canvas.addEventListener("pointerdown",  e => { e.preventDefault(); _down(canvas, e); });
    canvas.addEventListener("pointermove",  e => { e.preventDefault(); _move(canvas, e); });
    canvas.addEventListener("pointerup",    e => { e.preventDefault(); _up(canvas, e); });
    canvas.addEventListener("pointercancel",e => { delete _pointers[e.pointerId]; _dragStart = null; });
    canvas.addEventListener("wheel", e => { e.preventDefault(); _wheel(e); }, { passive: false });
}

function _down(canvas, e) {
    canvas.setPointerCapture(e.pointerId);
    _pointers[e.pointerId] = { x: e.clientX, y: e.clientY };
    const pts = _pointerList();

    if (pts.length === 1) {
        _tapStart  = { x: e.clientX, y: e.clientY, t: Date.now() };
        _dragStart = {
            panX: boardState.panX,
            panY: boardState.panY,
            startX: e.clientX,
            startY: e.clientY,
        };
    } else if (pts.length === 2) {
        // Pinch start
        const [a, b] = pts;
        _dragStart = {
            panX:  boardState.panX,
            panY:  boardState.panY,
            scale: boardState.scale,
            midX:  (a.x + b.x) / 2,
            midY:  (a.y + b.y) / 2,
            dist:  Math.hypot(b.x - a.x, b.y - a.y),
        };
        _tapStart = null;
    }
}

function _move(canvas, e) {
    _pointers[e.pointerId] = { x: e.clientX, y: e.clientY };
    const pts = _pointerList();

    if (pts.length === 1 && _dragStart) {
        const dx = e.clientX - _dragStart.startX;
        const dy = e.clientY - _dragStart.startY;
        boardState.panX = _dragStart.panX + dx;
        boardState.panY = _dragStart.panY + dy;

        // Cancel tap if moved more than 5 px
        if (_tapStart && Math.hypot(dx, dy) > 5) {
            _tapStart = null;
        }
    } else if (pts.length === 2 && _dragStart?.dist) {
        const [a, b] = pts;
        const newDist = Math.hypot(b.x - a.x, b.y - a.y);
        const ratio   = newDist / _dragStart.dist;
        const newScale = Math.max(3, Math.min(30, _dragStart.scale * ratio));

        // Keep the pinch midpoint stable in world space
        const worldMid = screenToWorldFixed(
            _dragStart.midX, _dragStart.midY, _dragStart.panX, _dragStart.panY, _dragStart.scale);
        boardState.scale = newScale;
        boardState.panX  = _dragStart.midX - worldMid[0] * newScale;
        boardState.panY  = _dragStart.midY - worldMid[1] * newScale;
    }
}

function _up(canvas, e) {
    delete _pointers[e.pointerId];

    if (_tapStart) {
        const dt = Date.now() - _tapStart.t;
        const dx = e.clientX - _tapStart.x;
        const dy = e.clientY - _tapStart.y;

        if (dt < 200 && Math.hypot(dx, dy) < 5) {
            const now = Date.now();
            const rect = canvas.getBoundingClientRect();
            const sx   = e.clientX - rect.left;
            const sy   = e.clientY - rect.top;

            if (now - _lastTap < 300) {
                // Double-tap → centre on selected ship
                _centreOnSelected();
            } else {
                _handleTap(sx, sy);
            }
            _lastTap = now;
        }
        _tapStart  = null;
    }

    if (_pointerList().length < 2) {
        _dragStart = null;
    }
}

function _wheel(e) {
    const delta   = e.deltaY > 0 ? 0.9 : 1.1;
    const rect    = e.target.getBoundingClientRect();
    const sx      = e.clientX - rect.left;
    const sy      = e.clientY - rect.top;
    const [wx, wy]= screenToWorld(sx, sy);
    const newScale = Math.max(3, Math.min(30, boardState.scale * delta));
    boardState.panX = sx - wx * newScale;
    boardState.panY = sy - wy * newScale;
    boardState.scale = newScale;
}

function _handleTap(sx, sy) {
    const gs  = boardState.gs;
    const ship = gs ? findShipAt(gs, sx, sy) : null;

    if (ship) {
        boardState.selectedShipId = (boardState.selectedShipId === ship.id) ? null : ship.id;
        onShipSelected(ship);
    } else if (boardState.selectedShipId) {
        // Tapped on empty space while a ship is selected → treat as move target
        const [wx, wy] = screenToWorld(sx, sy);
        onMoveTarget(wx, wy);
    } else {
        boardState.selectedShipId = null;
        onShipSelected(null);
    }
}

function _centreOnSelected() {
    const gs = boardState.gs;
    if (!gs || !boardState.selectedShipId) return;
    const ship = (gs.ships ?? []).find(s => s.id === boardState.selectedShipId);
    if (!ship) return;
    const canvas = document.getElementById("board-canvas");
    boardState.panX = canvas.width  / 2 - ship.x * boardState.scale;
    boardState.panY = canvas.height / 2 - ship.y * boardState.scale;
}

function _pointerList() {
    return Object.values(_pointers);
}

function screenToWorldFixed(sx, sy, panX, panY, scale) {
    return [(sx - panX) / scale, (sy - panY) / scale];
}
