/**
 * BFG:XR dialog overlays.
 *
 * Each dialog posts a "response" message to the Web Worker to unblock Python.
 * All dialogs are rendered into #dialog-layer (full-screen overlay).
 */

import { worker } from "./game.js";

const layer = () => document.getElementById("dialog-layer");

function _respond(value) {
    worker.postMessage({ type: "response", value });
    layer().innerHTML = "";
    layer().style.display = "none";
}

function _showLayer(html) {
    const el = layer();
    el.innerHTML = html;
    el.style.display = "flex";
}

// ── Yes / No ──────────────────────────────────────────────────────────────────

export function showYesNo(title, msg) {
    _showLayer(`
        <div class="dialog-box">
            <h3>${_esc(title)}</h3>
            <p>${_esc(msg).replace(/\n/g, "<br>")}</p>
            <div class="dialog-buttons">
                <button id="btn-yes" class="btn-yes">Yes</button>
                <button id="btn-no"  class="btn-no">No</button>
            </div>
        </div>
    `);
    document.getElementById("btn-yes").onclick = () => _respond(true);
    document.getElementById("btn-no").onclick  = () => _respond(false);
}


// ── Info / Warning / Error ────────────────────────────────────────────────────

export function showInfo(title, msg) {
    _showToast(title, msg, "#336633");
}

export function showWarning(title, msg) {
    _showToast(title, msg, "#886600");
}

export function showError(title, msg) {
    _showToast(title, msg, "#883333");
}

function _showToast(title, msg, color) {
    _showLayer(`
        <div class="dialog-box" style="border-color:${color}">
            <h3 style="color:${color}">${_esc(title)}</h3>
            <p>${_esc(msg).replace(/\n/g, "<br>")}</p>
            <div class="dialog-buttons">
                <button id="btn-ok" class="btn-ok">OK</button>
            </div>
        </div>
    `);
    document.getElementById("btn-ok").onclick = () => _respond(true);
}


// ── Pick from list ────────────────────────────────────────────────────────────

export function showPickFromList(title, items, maxPicks) {
    const isMulti = maxPicks > 1;

    const itemsHtml = items.map((item, i) => {
        const display = item.includes("|") ? item.split("|").slice(1).join("|") : item;
        if (isMulti) {
            return `<label class="list-item">
                        <input type="checkbox" data-idx="${i}" value="${_esc(item)}">
                        ${_esc(display)}
                    </label>`;
        }
        return `<button class="list-item list-btn" data-val="${_esc(item)}">${_esc(display)}</button>`;
    }).join("");

    const multi = isMulti ? `
        <div class="dialog-buttons">
            <button id="btn-confirm" class="btn-ok">Confirm</button>
            <button id="btn-skip"   class="btn-no">Skip</button>
        </div>` : "";

    _showLayer(`
        <div class="dialog-box">
            <h3>${_esc(title)}</h3>
            <div class="list-container">${itemsHtml}</div>
            ${multi}
        </div>
    `);

    if (isMulti) {
        document.getElementById("btn-confirm").onclick = () => {
            const checked = [...document.querySelectorAll("input[data-idx]:checked")]
                .slice(0, maxPicks)
                .map(el => el.value);
            _respond(JSON.stringify(checked));
        };
        document.getElementById("btn-skip").onclick = () => _respond("[]");
    } else {
        // Single pick — click any button
        for (const btn of document.querySelectorAll(".list-btn")) {
            btn.onclick = () => _respond(btn.dataset.val);
        }
    }
}


// ── Helper ────────────────────────────────────────────────────────────────────

function _esc(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
