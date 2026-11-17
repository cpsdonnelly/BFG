/**
 * BFG:XR Canvas2D board renderer.
 *
 * Ported from board_view.py.  All coordinates are in game-space centimetres;
 * worldToScreen() converts to CSS pixels using the current scale and pan.
 */

const SHIP_RADII_CM = {
    battleship: 2.5,
    cruiser:    1.6,
    escort:     1.6,
    defense:    1.6,
};

const PLAYER_COLORS = {
    red:    "#CC3333",
    blue:   "#3366CC",
    green:  "#33AA33",
    yellow: "#CCAA00",
    purple: "#8833AA",
    orange: "#DD6600",
    black:  "#222222",
    white:  "#DDDDDD",
    pink:   "#DD66AA",
};

const PHENOMENON_COLORS = {
    planet_small:  "#4488AA",
    planet_medium: "#448866",
    planet_large:  "#886644",
    moon:          "#AAAAAA",
    asteroid_field:"#8B7355",
    gas_dust_cloud:"#556B7B",
    warp_rift:     "#9933FF",
};

/** Board state for rendering */
export const boardState = {
    scale:  8,      // CSS pixels per cm
    panX:   40,     // CSS pixel offset
    panY:   40,
    selectedShipId: null,
    showArcsShipId: null,
    rulers: [],     // [{p1, p2}]
    gs:     null,   // current game state snapshot
};


// ── Coordinate transforms ─────────────────────────────────────────────────────

export function worldToScreen(cx, cy) {
    return [
        boardState.panX + cx * boardState.scale,
        boardState.panY + cy * boardState.scale,
    ];
}

export function screenToWorld(sx, sy) {
    return [
        (sx - boardState.panX) / boardState.scale,
        (sy - boardState.panY) / boardState.scale,
    ];
}

function cmToPx(cm) { return cm * boardState.scale; }


// ── Main redraw ───────────────────────────────────────────────────────────────

export function redraw(canvas, gs) {
    boardState.gs = gs;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#0a0a1a";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    drawGrid(ctx, gs);
    drawPhenomena(ctx, gs);
    drawBlastMarkers(ctx, gs);
    drawOrdnance(ctx, gs);
    drawShips(ctx, gs);
    drawRulers(ctx);
    if (boardState.showArcsShipId) {
        drawArcOverlay(ctx, gs, boardState.showArcsShipId);
    }
    drawArtefact(ctx, gs);
    drawCompassRose(ctx, gs);
}


// ── Grid ──────────────────────────────────────────────────────────────────────

function drawGrid(ctx, gs) {
    const [x0, y0] = worldToScreen(0, 0);
    const [x1, y1] = worldToScreen(gs.table_width, gs.table_height);

    // Table border
    ctx.strokeStyle = "#333355";
    ctx.lineWidth   = 2;
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);

    // Grid lines every 10 cm
    for (let i = 0; i <= gs.table_width; i += 10) {
        const [sx] = worldToScreen(i, 0);
        const [, sy1] = worldToScreen(i, gs.table_height);
        ctx.strokeStyle = (i % 30 === 0) ? "#333366" : "#222244";
        ctx.lineWidth   = 1;
        ctx.setLineDash([2, 4]);
        ctx.beginPath();
        ctx.moveTo(sx, y0);
        ctx.lineTo(sx, sy1);
        ctx.stroke();
    }
    for (let j = 0; j <= gs.table_height; j += 10) {
        const [, sy] = worldToScreen(0, j);
        const [sx1]  = worldToScreen(gs.table_width, j);
        ctx.strokeStyle = (j % 30 === 0) ? "#333366" : "#222244";
        ctx.lineWidth   = 1;
        ctx.setLineDash([2, 4]);
        ctx.beginPath();
        ctx.moveTo(x0, sy);
        ctx.lineTo(sx1, sy);
        ctx.stroke();
    }
    ctx.setLineDash([]);

    // 10 cm scale bar
    const [bx0, by] = worldToScreen(5, -2);
    const [bx1]     = worldToScreen(15, -2);
    ctx.strokeStyle = "#666688";
    ctx.lineWidth   = 2;
    ctx.beginPath();
    ctx.moveTo(bx0, by);
    ctx.lineTo(bx1, by);
    ctx.stroke();
    ctx.fillStyle  = "#666688";
    ctx.font       = "10px monospace";
    ctx.textAlign  = "center";
    ctx.fillText("10cm", (bx0 + bx1) / 2, by - 4);
}


// ── Compass rose ──────────────────────────────────────────────────────────────

function drawCompassRose(ctx, gs) {
    const cx  = 50;
    const cy  = 50;
    const arm = 20;
    const sunAngles = { north: 90, south: 270, east: 0, west: 180 };
    const sunA = sunAngles[gs.sunward_edge] ?? 0;

    for (const [label, angle] of [["N", 90], ["S", 270], ["E", 0], ["W", 180]]) {
        const rad = (angle * Math.PI) / 180;
        const isSun = angle === sunA;
        const col = isSun ? "#FFDD44" : "#556677";
        const ex  = cx + arm * Math.cos(rad);
        const ey  = cy - arm * Math.sin(rad);
        ctx.strokeStyle = col;
        ctx.lineWidth   = isSun ? 2 : 1;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(ex, ey);
        ctx.stroke();
        const tx = cx + (arm + 12) * Math.cos(rad);
        const ty = cy - (arm + 12) * Math.sin(rad);
        ctx.fillStyle  = col;
        ctx.font       = isSun ? "bold 9px monospace" : "9px monospace";
        ctx.textAlign  = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(isSun ? "☀" + label : label, tx, ty);
    }
    ctx.fillStyle = "#556677";
    ctx.beginPath();
    ctx.arc(cx, cy, 2, 0, Math.PI * 2);
    ctx.fill();
}


// ── Phenomena ─────────────────────────────────────────────────────────────────

function drawPhenomena(ctx, gs) {
    for (const p of (gs.phenomena ?? [])) {
        const color = PHENOMENON_COLORS[p.phenomenon_type] ?? "#555555";
        const [sx, sy] = worldToScreen(p.x, p.y);

        if (p.phenomenon_type.startsWith("planet") || p.phenomenon_type === "moon") {
            const r = cmToPx(p.radius ?? 5);
            ctx.fillStyle   = color;
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth   = 1;
            ctx.globalAlpha = 0.7;
            ctx.beginPath();
            ctx.arc(sx, sy, r, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
            ctx.globalAlpha = 1;

            // Gravity well
            const gw = cmToPx(p.gravity_well_radius ?? 0);
            if (gw > 0) {
                ctx.strokeStyle = "#336699";
                ctx.lineWidth   = 1;
                ctx.setLineDash([4, 4]);
                ctx.beginPath();
                ctx.arc(sx, sy, gw, 0, Math.PI * 2);
                ctx.stroke();
                ctx.setLineDash([]);
            }

        } else if (p.phenomenon_type === "asteroid_field") {
            const [ax1, ay1] = worldToScreen(p.x - (p.width ?? 10) / 2,
                                             p.y - (p.height ?? 10) / 2);
            const [ax2, ay2] = worldToScreen(p.x + (p.width ?? 10) / 2,
                                             p.y + (p.height ?? 10) / 2);
            ctx.strokeStyle = "#665544";
            ctx.lineWidth   = 1;
            ctx.setLineDash([3, 5]);
            ctx.strokeRect(ax1, ay1, ax2 - ax1, ay2 - ay1);
            ctx.setLineDash([]);

            // Scatter pebbles (deterministic via simple seed)
            const w = Math.abs(ax2 - ax1);
            const h = Math.abs(ay2 - ay1);
            let seed = _strHash(p.id);
            for (let i = 0; i < Math.max(8, (w * h) / 400); i++) {
                seed = _lcg(seed);
                const rx = Math.min(ax1, ax2) + (seed % 1000) / 1000 * w;
                seed = _lcg(seed);
                const ry = Math.min(ay1, ay2) + (seed % 1000) / 1000 * h;
                seed = _lcg(seed);
                const rr = 2 + (seed % 300) / 100;
                ctx.fillStyle = "#8B7355";
                ctx.beginPath();
                ctx.arc(rx, ry, rr, 0, Math.PI * 2);
                ctx.fill();
            }

        } else if (p.phenomenon_type === "gas_dust_cloud") {
            const rw = cmToPx((p.width ?? 10) / 2);
            const rh = cmToPx((p.height ?? 10) / 2);
            ctx.fillStyle   = "#2a3a4a";
            ctx.strokeStyle = "#556B7B";
            ctx.globalAlpha = 0.6;
            ctx.beginPath();
            ctx.ellipse(sx, sy, rw, rh, 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
            ctx.globalAlpha = 1;

        } else if (p.phenomenon_type === "warp_rift") {
            const [wx1, wy1] = worldToScreen(p.x - (p.width ?? 10) / 2,
                                             p.y - (p.height ?? 10) / 2);
            const [wx2, wy2] = worldToScreen(p.x + (p.width ?? 10) / 2,
                                             p.y + (p.height ?? 10) / 2);
            ctx.fillStyle   = "#1a0033";
            ctx.strokeStyle = "#9933FF";
            ctx.lineWidth   = 2;
            ctx.fillRect(wx1, wy1, wx2 - wx1, wy2 - wy1);
            ctx.strokeRect(wx1, wy1, wx2 - wx1, wy2 - wy1);
        }
    }
}


// ── Blast markers ─────────────────────────────────────────────────────────────

function drawBlastMarkers(ctx, gs) {
    for (const bm of (gs.blast_markers ?? [])) {
        const [sx, sy] = worldToScreen(bm.x, bm.y);
        const r  = cmToPx(0.75);
        const off = cmToPx(0.65);
        for (const angle of [90, 210, 330]) {
            const rad = (angle * Math.PI) / 180;
            const cx  = sx + off * Math.cos(rad);
            const cy  = sy - off * Math.sin(rad);
            ctx.fillStyle   = "#CC5500";
            ctx.strokeStyle = "#FF8800";
            ctx.lineWidth   = 1;
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        }
        ctx.fillStyle = "#FFAA33";
        ctx.beginPath();
        ctx.arc(sx, sy, cmToPx(0.3), 0, Math.PI * 2);
        ctx.fill();
    }
}


// ── Ordnance markers ──────────────────────────────────────────────────────────

function drawOrdnance(ctx, gs) {
    for (const o of (gs.ordnance ?? [])) {
        const [sx, sy] = worldToScreen(o.x, o.y);
        const playerCol = o.owner_player === 1
            ? gs.player1_color : gs.player2_color;
        const color = PLAYER_COLORS[playerCol] ?? "#FFFFFF";
        const dark  = _darken(color, 0.6);
        const hdg   = (o.heading * Math.PI) / 180;
        const otype = o.ordnance_type ?? "";

        if (otype.includes("torpedo")) {
            const hw = cmToPx(1.0);
            const hh = cmToPx(0.75);
            const tip = cmToPx(0.5);
            const body = [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]];
            const arrow = [[hw, -hh], [hw + tip, 0], [hw, hh]];
            _fillPoly(ctx, _rotatePoly(body, hdg, sx, sy), dark, color, 1);
            _fillPoly(ctx, _rotatePoly(arrow, hdg, sx, sy), dark, color, 1);
            _centreText(ctx, sx, sy, `T${o.strength}`, "#ffffff", "bold 8px monospace");

        } else if (["fighter", "barracuda"].includes(otype)) {
            const hs = cmToPx(1.0);
            const sq = [[-hs, -hs], [hs, -hs], [hs, hs], [-hs, hs]];
            _fillPoly(ctx, _rotatePoly(sq, hdg, sx, sy), dark, color, 2);
            _centreText(ctx, sx, sy,
                otype === "fighter" ? "F" : "Br", "#ffffff", "bold 9px monospace");

        } else if (otype === "bomber") {
            const hs = cmToPx(1.0);
            const sq = [[-hs, -hs], [hs, -hs], [hs, hs], [-hs, hs]];
            _fillPoly(ctx, _rotatePoly(sq, hdg, sx, sy), dark, color, 1);
            _centreText(ctx, sx, sy, "B", "#ffffff", "bold 9px monospace");

        } else if (otype === "manta") {
            const hs = cmToPx(1.0);
            const sq = [[-hs, -hs], [hs, -hs], [hs, hs], [-hs, hs]];
            _fillPoly(ctx, _rotatePoly(sq, hdg, sx, sy), dark, "#FFDD00", 2);
            _centreText(ctx, sx, sy, "M", "#ffffff", "bold 9px monospace");

        } else if (otype === "mine_field") {
            const hs = cmToPx(1.0);
            const sq = [[-hs, -hs], [hs, -hs], [hs, hs], [-hs, hs]];
            ctx.setLineDash([3, 2]);
            _fillPoly(ctx, _rotatePoly(sq, 0, sx, sy), "#331100", "#FF8800", 2);
            ctx.setLineDash([]);
            _centreText(ctx, sx, sy, "M", "#FF8800", "bold 9px monospace");

        } else {
            const hs = cmToPx(0.8);
            ctx.fillStyle   = dark;
            ctx.strokeStyle = color;
            ctx.lineWidth   = 1;
            ctx.fillRect(sx - hs, sy - hs, hs * 2, hs * 2);
            ctx.strokeRect(sx - hs, sy - hs, hs * 2, hs * 2);
        }
    }
}


// ── Ships ─────────────────────────────────────────────────────────────────────

function drawShips(ctx, gs) {
    for (const s of (gs.ships ?? [])) {
        if (s.status === "destroyed" || s.status === "disengaged") continue;
        if (s.is_disengaged) continue;
        _drawSingleShip(ctx, gs, s);
    }
}

function _drawSingleShip(ctx, gs, s) {
    const [sx, sy]   = worldToScreen(s.x, s.y);
    const displayR   = cmToPx(SHIP_RADII_CM[s.ship_type] ?? 1.6);
    const playerCol  = s.player === 1 ? gs.player1_color : gs.player2_color;
    const baseColor  = PLAYER_COLORS[playerCol] ?? "#FFFFFF";
    const isSelected = s.id === boardState.selectedShipId;

    // Fill colour based on status
    let fill;
    if (s.status === "drifting_hulk") fill = "#444444";
    else if (s.status === "burning_hulk") fill = "#553300";
    else if (s.is_destroyed)  fill = "#333333";
    else if (s.is_crippled)   fill = _darken(baseColor, 0.5);
    else                      fill = baseColor;

    const outlineCol = isSelected ? "#FFFFFF" : "#888888";
    const outlineW   = isSelected ? 3 : 1;

    // Ship circle
    ctx.fillStyle   = fill;
    ctx.strokeStyle = outlineCol;
    ctx.lineWidth   = outlineW;
    ctx.beginPath();
    ctx.arc(sx, sy, displayR, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Heading arrow
    const hdgRad  = (s.heading * Math.PI) / 180;
    const arrowLen = displayR * 1.8;
    const ax = sx + arrowLen * Math.cos(hdgRad);
    const ay = sy - arrowLen * Math.sin(hdgRad);
    ctx.strokeStyle = "#FFFF00";
    ctx.lineWidth   = 2;
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(ax, ay);
    ctx.stroke();
    // Arrowhead
    const headLen = 5;
    const headAng = Math.PI / 6;
    const angle   = Math.atan2(ay - sy, ax - sx);
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(ax - headLen * Math.cos(angle - headAng),
               ay - headLen * Math.sin(angle - headAng));
    ctx.lineTo(ax - headLen * Math.cos(angle + headAng),
               ay - headLen * Math.sin(angle + headAng));
    ctx.closePath();
    ctx.fillStyle = "#FFFF00";
    ctx.fill();

    // Arc crosshair notches
    const crossR = displayR * 1.3;
    for (const off of [45, 135, 225, 315]) {
        const a = hdgRad + (off * Math.PI) / 180;
        ctx.strokeStyle = outlineCol;
        ctx.lineWidth   = 1;
        ctx.beginPath();
        ctx.moveTo(sx + crossR * 0.3 * Math.cos(a), sy - crossR * 0.3 * Math.sin(a));
        ctx.lineTo(sx + crossR * Math.cos(a),        sy - crossR * Math.sin(a));
        ctx.stroke();
    }

    // HP bar
    if (s.hits_max > 0 && !s.is_destroyed) {
        const barW   = displayR * 1.5;
        const barH   = 3;
        const bx     = sx - barW / 2;
        const by     = sy - displayR - 6;
        const hpFrac = s.hits_remaining / s.hits_max;
        const hpCol  = hpFrac > 0.5 ? "#33CC33" : (hpFrac > 0.25 ? "#CCAA00" : "#CC3333");
        ctx.fillStyle = "#333333";
        ctx.fillRect(bx, by, barW, barH);
        ctx.fillStyle = hpCol;
        ctx.fillRect(bx, by, barW * hpFrac, barH);
    }

    // Special order icon
    if (s.special_order && s.special_order !== "none") {
        _drawOrderIcon(ctx, sx, sy - displayR - 14, s.special_order);
    }

    // Ship name
    ctx.fillStyle    = "#cccccc";
    ctx.font         = "8px monospace";
    ctx.textAlign    = "center";
    ctx.textBaseline = "top";
    ctx.fillText(s.name, sx, sy + displayR + 3);
}


// ── Special order icons ───────────────────────────────────────────────────────

function _drawOrderIcon(ctx, cx, cy, order) {
    const s   = 6;
    const col = "#FFAA00";
    ctx.fillStyle   = "#1a1a2e";
    ctx.strokeStyle = col;
    ctx.lineWidth   = 1;
    ctx.beginPath();
    ctx.arc(cx, cy, s + 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.strokeStyle = col;
    ctx.fillStyle   = col;
    ctx.lineWidth   = 2;

    if (order === "all_ahead_full") {
        for (const dy of [-2, 3]) {
            ctx.beginPath();
            ctx.moveTo(cx - s + 2, cy + dy + 2);
            ctx.lineTo(cx, cy + dy - 3);
            ctx.lineTo(cx + s - 2, cy + dy + 2);
            ctx.stroke();
        }
    } else if (order === "come_to_new_heading") {
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, s - 1, (30 * Math.PI) / 180, (150 * Math.PI) / 180);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(cx, cy, s - 1, (210 * Math.PI) / 180, (330 * Math.PI) / 180);
        ctx.stroke();
    } else if (order === "burn_retros") {
        for (let a = 0; a < 360; a += 60) {
            const rad = (a * Math.PI) / 180;
            ctx.beginPath();
            ctx.moveTo(cx + 2 * Math.cos(rad), cy - 2 * Math.sin(rad));
            ctx.lineTo(cx + s * Math.cos(rad), cy - s * Math.sin(rad));
            ctx.stroke();
        }
    } else if (order === "lock_on") {
        ctx.beginPath();
        ctx.arc(cx, cy, s - 1, 0, Math.PI * 2);
        ctx.stroke();
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(cx - s, cy);
        ctx.lineTo(cx + s, cy);
        ctx.moveTo(cx, cy - s);
        ctx.lineTo(cx, cy + s);
        ctx.stroke();
    } else if (order === "reload_ordnance") {
        // Lightning bolt
        ctx.beginPath();
        ctx.moveTo(cx - 2, cy - s + 1);
        ctx.lineTo(cx + 2, cy - 2);
        ctx.lineTo(cx, cy - 1);
        ctx.lineTo(cx + 3, cy + 1);
        ctx.lineTo(cx - 1, cy + s - 1);
        ctx.lineTo(cx, cy + 1);
        ctx.lineTo(cx - 3, cy - 1);
        ctx.closePath();
        ctx.fill();
    } else if (order === "brace_for_impact") {
        // Diamond
        ctx.beginPath();
        ctx.moveTo(cx, cy - s);
        ctx.lineTo(cx + s, cy);
        ctx.lineTo(cx, cy + s);
        ctx.lineTo(cx - s, cy);
        ctx.closePath();
        ctx.stroke();
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(cx, cy - 3);
        ctx.lineTo(cx, cy + 1);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(cx, cy + 3, 1, 0, Math.PI * 2);
        ctx.fill();
    }
}


// ── Arc overlay ───────────────────────────────────────────────────────────────

export function drawArcOverlay(ctx, gs, shipId) {
    const s = (gs.ships ?? []).find(sh => sh.id === shipId);
    if (!s) return;

    const [sx, sy] = worldToScreen(s.x, s.y);
    const hdgRad   = (s.heading * Math.PI) / 180;

    let maxRange = 0;
    for (const w of (s.weapons ?? [])) {
        if ((w.range_cm ?? 0) > maxRange) maxRange = w.range_cm;
    }
    if (!maxRange) maxRange = 45;

    const rangePx = cmToPx(maxRange);

    // Arc separator lines
    ctx.strokeStyle = "#666666";
    ctx.lineWidth   = 1;
    ctx.setLineDash([4, 4]);
    for (const off of [45, 135, 225, 315]) {
        const a = hdgRad + (off * Math.PI) / 180;
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(sx + rangePx * Math.cos(a), sy - rangePx * Math.sin(a));
        ctx.stroke();
    }
    ctx.setLineDash([]);

    // Range circles
    const brackets = [...new Set([15, 30, maxRange])].sort((a, b) => a - b);
    for (const r of brackets) {
        const rpx = cmToPx(r);
        ctx.strokeStyle = "#444466";
        ctx.lineWidth   = 1;
        ctx.setLineDash([2, 6]);
        ctx.beginPath();
        ctx.arc(sx, sy, rpx, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        const la = hdgRad + (60 * Math.PI) / 180;
        ctx.fillStyle    = "#666688";
        ctx.font         = "8px monospace";
        ctx.textAlign    = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(`${r}cm`,
            sx + rpx * Math.cos(la),
            sy - rpx * Math.sin(la));
    }

    // Arc labels
    for (const [label, off] of [["FRONT", 0], ["LEFT", 90], ["REAR", 180], ["RIGHT", 270]]) {
        const a    = hdgRad + (off * Math.PI) / 180;
        const lr   = rangePx * 0.4;
        ctx.fillStyle    = "#555577";
        ctx.font         = "9px monospace";
        ctx.textAlign    = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(label, sx + lr * Math.cos(a), sy - lr * Math.sin(a));
    }
}


// ── Rulers ────────────────────────────────────────────────────────────────────

function drawRulers(ctx) {
    for (const { p1, p2 } of boardState.rulers) {
        const [sx0, sy0] = worldToScreen(p1[0], p1[1]);
        const [sx1, sy1] = worldToScreen(p2[0], p2[1]);
        const dist = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]);

        ctx.strokeStyle = "#FFFFFF";
        ctx.lineWidth   = 2;
        ctx.setLineDash([5, 3]);
        ctx.beginPath();
        ctx.moveTo(sx0, sy0);
        ctx.lineTo(sx1, sy1);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle    = "#FFFFFF";
        ctx.font         = "bold 10px monospace";
        ctx.textAlign    = "center";
        ctx.textBaseline = "bottom";
        ctx.fillText(`${dist.toFixed(1)}cm`,
            (sx0 + sx1) / 2, (sy0 + sy1) / 2 - 4);
    }
}


// ── Artefact ──────────────────────────────────────────────────────────────────

function drawArtefact(ctx, gs) {
    if (gs.scenario_mode !== "capture_artefact") return;

    let ax, ay;
    if (gs.artefact_token_pos) {
        [ax, ay] = worldToScreen(...gs.artefact_token_pos);
    } else if (gs.artefact_carrier_id) {
        const carrier = (gs.ships ?? []).find(s => s.id === gs.artefact_carrier_id);
        if (!carrier || carrier.is_destroyed) return;
        [ax, ay] = worldToScreen(carrier.x, carrier.y);
    } else {
        return;
    }

    const r = 8;
    ctx.fillStyle   = "#FFD700";
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth   = 1;
    ctx.beginPath();
    for (let i = 0; i < 5; i++) {
        const a1 = (i * 72 - 90) * Math.PI / 180;
        const a2 = (i * 72 + 36 - 90) * Math.PI / 180;
        if (i === 0) ctx.moveTo(ax + r * Math.cos(a1), ay + r * Math.sin(a1));
        else         ctx.lineTo(ax + r * Math.cos(a1), ay + r * Math.sin(a1));
        ctx.lineTo(ax + r * 0.4 * Math.cos(a2), ay + r * 0.4 * Math.sin(a2));
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
}


// ── Find ship at screen point ─────────────────────────────────────────────────

export function findShipAt(gs, sx, sy) {
    if (!gs) return null;
    const [cx, cy] = screenToWorld(sx, sy);
    for (const s of (gs.ships ?? [])) {
        if (s.status === "destroyed" || s.is_disengaged) continue;
        const r  = SHIP_RADII_CM[s.ship_type] ?? 1.6;
        const dx = cx - s.x;
        const dy = cy - s.y;
        if (Math.hypot(dx, dy) <= r + 0.5) return s;
    }
    return null;
}


// ── Internal helpers ──────────────────────────────────────────────────────────

function _darken(hex, factor) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgb(${Math.floor(r * factor)},${Math.floor(g * factor)},${Math.floor(b * factor)})`;
}

function _rotatePoly(pts, angleRad, cx, cy) {
    const cos = Math.cos(angleRad);
    const sin = Math.sin(angleRad);
    return pts.map(([lx, ly]) => [
        cx + lx * cos - ly * sin,
        cy - (lx * sin + ly * cos),   // Y inverted for canvas
    ]);
}

function _fillPoly(ctx, pts, fill, stroke, lineW) {
    ctx.fillStyle   = fill;
    ctx.strokeStyle = stroke;
    ctx.lineWidth   = lineW;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
}

function _centreText(ctx, x, y, text, color, font) {
    ctx.fillStyle    = color;
    ctx.font         = font;
    ctx.textAlign    = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, x, y);
}

function _strHash(str) {
    let h = 0;
    for (const c of str) h = (Math.imul(31, h) + c.charCodeAt(0)) | 0;
    return Math.abs(h);
}

function _lcg(seed) {
    return (seed * 1664525 + 1013904223) >>> 0;
}
