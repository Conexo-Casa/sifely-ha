/**
 * Sifely Passcode Manager — Lovelace Custom Card
 * Manages guest passcodes for every Sifely lock in your HA instance.
 *
 * Installation (automatic via integration) or manual:
 *   resources:
 *     - url: /local/sifely/sifely-passcode-card.js
 *       type: module
 *
 * Card config:
 *   type: custom:sifely-passcode-card
 *   title: Passcode Manager   # optional
 */

const DOMAIN = "sifely";

// ── Styles ────────────────────────────────────────────────────────────────────

const STYLES = `
  :host {
    --sifely-blue:    #1a6ef5;
    --sifely-red:     #e53e3e;
    --sifely-green:   #2e7d52;
    --sifely-bg:      var(--card-background-color, #fff);
    --sifely-surface: var(--secondary-background-color, #f5f7fa);
    --sifely-border:  var(--divider-color, #e2e6ea);
    --sifely-text:    var(--primary-text-color, #1a202c);
    --sifely-muted:   var(--secondary-text-color, #718096);
    --sifely-radius:  10px;
    font-family: var(--paper-font-body1_-_font-family, sans-serif);
  }

  .card-root {
    background: var(--sifely-bg);
    border-radius: var(--sifely-radius);
    overflow: hidden;
  }

  /* ── Header ── */
  .header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 16px 20px 12px;
    border-bottom: 1px solid var(--sifely-border);
  }
  .header ha-icon { --mdc-icon-size: 22px; color: var(--sifely-blue); }
  .header-title { font-size: 1.05rem; font-weight: 600; color: var(--sifely-text); flex: 1; }

  /* ── Lock selector ── */
  .lock-bar {
    display: flex;
    gap: 8px;
    padding: 12px 20px;
    background: var(--sifely-surface);
    border-bottom: 1px solid var(--sifely-border);
    flex-wrap: wrap;
    align-items: center;
  }
  .lock-bar label { font-size: .8rem; color: var(--sifely-muted); white-space: nowrap; }
  .lock-select {
    flex: 1; min-width: 160px;
    border: 1px solid var(--sifely-border);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: .9rem;
    background: var(--sifely-bg);
    color: var(--sifely-text);
    cursor: pointer;
  }
  .refresh-btn {
    background: none;
    border: 1px solid var(--sifely-border);
    border-radius: 6px;
    padding: 6px 10px;
    cursor: pointer;
    color: var(--sifely-muted);
    font-size: .85rem;
    display: flex; align-items: center; gap: 4px;
    transition: border-color .15s, color .15s;
  }
  .refresh-btn:hover { border-color: var(--sifely-blue); color: var(--sifely-blue); }

  /* ── Passcode list ── */
  .passcode-list { padding: 12px 20px; display: flex; flex-direction: column; gap: 8px; }

  .passcode-row {
    display: grid;
    grid-template-columns: 1fr auto auto;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border: 1px solid var(--sifely-border);
    border-radius: 8px;
    background: var(--sifely-bg);
    transition: box-shadow .15s;
  }
  .passcode-row:hover { box-shadow: 0 1px 6px rgba(0,0,0,.08); }

  .pwd-info { min-width: 0; }
  .pwd-name { font-size: .9rem; font-weight: 600; color: var(--sifely-text);
               white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pwd-meta { font-size: .75rem; color: var(--sifely-muted); margin-top: 2px; }
  .pwd-code { font-family: monospace; font-size: .85rem; background: var(--sifely-surface);
               padding: 1px 6px; border-radius: 4px; color: var(--sifely-text); }

  .row-actions { display: flex; gap: 6px; }
  .btn-icon {
    background: none; border: none; cursor: pointer;
    padding: 5px; border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    --mdc-icon-size: 18px;
    transition: background .15s;
  }
  .btn-icon.edit  { color: var(--sifely-blue); }
  .btn-icon.edit:hover  { background: rgba(26,110,245,.1); }
  .btn-icon.del   { color: var(--sifely-red); }
  .btn-icon.del:hover   { background: rgba(229,62,62,.1); }

  /* ── Add button ── */
  .add-bar {
    padding: 0 20px 16px;
  }
  .btn-add {
    width: 100%;
    display: flex; align-items: center; justify-content: center; gap: 6px;
    padding: 9px;
    border: 1.5px dashed var(--sifely-blue);
    border-radius: 8px;
    background: none;
    color: var(--sifely-blue);
    font-size: .88rem; font-weight: 500;
    cursor: pointer;
    transition: background .15s;
    --mdc-icon-size: 18px;
  }
  .btn-add:hover { background: rgba(26,110,245,.07); }

  /* ── Empty / loading states ── */
  .state-msg {
    text-align: center;
    padding: 28px 20px;
    color: var(--sifely-muted);
    font-size: .9rem;
  }
  .state-msg ha-icon { --mdc-icon-size: 36px; display: block; margin: 0 auto 10px; opacity: .4; }

  /* ── Modal overlay ── */
  .modal-overlay {
    position: fixed; inset: 0;
    background: rgba(0,0,0,.45);
    display: flex; align-items: center; justify-content: center;
    z-index: 9999;
    padding: 16px;
  }
  .modal {
    background: var(--sifely-bg);
    border-radius: var(--sifely-radius);
    width: 100%; max-width: 420px;
    box-shadow: 0 8px 32px rgba(0,0,0,.2);
    overflow: hidden;
  }
  .modal-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--sifely-border);
  }
  .modal-title { font-size: 1rem; font-weight: 600; color: var(--sifely-text); }
  .btn-close {
    background: none; border: none; cursor: pointer;
    color: var(--sifely-muted); padding: 4px;
    --mdc-icon-size: 20px;
  }
  .modal-body { padding: 20px; display: flex; flex-direction: column; gap: 14px; }
  .field { display: flex; flex-direction: column; gap: 5px; }
  .field label { font-size: .8rem; font-weight: 500; color: var(--sifely-muted); }
  .field input {
    border: 1px solid var(--sifely-border);
    border-radius: 6px;
    padding: 8px 10px;
    font-size: .9rem;
    background: var(--sifely-bg);
    color: var(--sifely-text);
    width: 100%; box-sizing: border-box;
    transition: border-color .15s;
  }
  .field input:focus { outline: none; border-color: var(--sifely-blue); }
  .field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .field-hint { font-size: .74rem; color: var(--sifely-muted); }

  .modal-footer {
    display: flex; gap: 10px; justify-content: flex-end;
    padding: 14px 20px;
    border-top: 1px solid var(--sifely-border);
  }
  .btn { border: none; border-radius: 7px; padding: 8px 18px;
          font-size: .88rem; font-weight: 500; cursor: pointer; transition: opacity .15s; }
  .btn:hover { opacity: .85; }
  .btn-primary { background: var(--sifely-blue); color: #fff; }
  .btn-ghost   { background: var(--sifely-surface); color: var(--sifely-text); }
  .btn-danger  { background: var(--sifely-red);  color: #fff; }

  /* ── Toast ── */
  .toast {
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    background: #1a202c; color: #fff;
    padding: 10px 20px; border-radius: 8px;
    font-size: .88rem; z-index: 10000;
    box-shadow: 0 4px 16px rgba(0,0,0,.2);
    animation: slideUp .2s ease;
  }
  .toast.error { background: var(--sifely-red); }
  .toast.success { background: var(--sifely-green); }
  @keyframes slideUp { from { opacity: 0; transform: translateX(-50%) translateY(10px); } }

  /* ── Confirm dialog ── */
  .confirm-msg { padding: 20px; font-size: .9rem; color: var(--sifely-text); line-height: 1.5; }
`;

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(ms) {
  if (!ms || ms === 0) return "permanent";
  return new Date(ms).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function toMs(localDatetimeStr) {
  if (!localDatetimeStr) return 0;
  return new Date(localDatetimeStr).getTime();
}

function toLocalDatetime(ms) {
  if (!ms || ms === 0) return "";
  const d = new Date(ms);
  const pad = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ── Custom element ─────────────────────────────────────────────────────────────

class SifelyPasscodeCard extends HTMLElement {

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass       = null;
    this._config     = {};
    this._locks      = [];    // [{ entity_id, lock_id, name }]
    this._selectedLockId = null;
    this._passcodes  = [];
    this._loading    = false;
    this._modal      = null;  // { mode: "add"|"edit"|"delete", passcode?: {} }
    this._unsub      = null;  // event subscription cleanup
  }

  static getConfigElement() {
    return document.createElement("sifely-passcode-card-editor");
  }

  static getStubConfig() {
    return { type: "custom:sifely-passcode-card", title: "Passcode Manager" };
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    // Discover sifely lock entities
    const locks = Object.entries(hass.states)
      .filter(([eid]) => eid.startsWith("lock.") &&
                         hass.states[eid].attributes.lock_id !== undefined &&
                         (hass.states[eid].attributes.integration === DOMAIN ||
                          eid.toLowerCase().includes("sifely") ||
                          String(hass.states[eid].attributes.lock_id).length > 4))
      .map(([eid, state]) => ({
        entity_id: eid,
        lock_id:   state.attributes.lock_id,
        name:      state.attributes.friendly_name || state.attributes.lock_alias || eid,
      }));

    const changed = JSON.stringify(locks) !== JSON.stringify(this._locks);
    this._locks = locks;

    if (changed) {
      if (!this._selectedLockId && locks.length > 0) {
        this._selectedLockId = locks[0].lock_id;
      }
      this._render();
    }
  }

  connectedCallback() {
    this._subscribeEvents();
  }

  disconnectedCallback() {
    if (this._unsub) { this._unsub(); this._unsub = null; }
  }

  // ── Event subscription (listen for sifely_passcodes_listed) ───────────────

  _subscribeEvents() {
    if (!this._hass || this._unsub) return;
    this._hass.connection.subscribeEvents((event) => {
      if (event.event_type === `${DOMAIN}_passcodes_listed`) {
        const d = event.data;
        if (d.lock_id === this._selectedLockId) {
          this._passcodes = d.passcodes || [];
          this._loading   = false;
          this._render();
        }
      }
    }, `${DOMAIN}_passcodes_listed`).then(unsub => { this._unsub = unsub; });
  }

  // ── Service calls ──────────────────────────────────────────────────────────

  async _listPasscodes() {
    if (!this._selectedLockId || !this._hass) return;
    this._loading = true;
    this._render();
    try {
      await this._hass.callService(DOMAIN, "list_passcodes", { lock_id: this._selectedLockId });
      // Response comes via the event subscription above
      // Fallback timeout: if no event in 8s, stop spinner
      setTimeout(() => { if (this._loading) { this._loading = false; this._render(); } }, 8000);
    } catch (e) {
      this._loading = false;
      this._toast("Failed to load passcodes: " + e.message, "error");
      this._render();
    }
  }

  async _addPasscode(name, code, startMs, endMs) {
    await this._hass.callService(DOMAIN, "add_passcode", {
      lock_id:      this._selectedLockId,
      passcode:     code,
      passcode_name: name,
      ...(startMs ? { start_date: startMs } : {}),
      ...(endMs   ? { end_date:   endMs   } : {}),
    });
  }

  async _changePasscode(passcodeId, name, code, startMs, endMs) {
    const data = { lock_id: this._selectedLockId, passcode_id: passcodeId };
    if (name) data.passcode_name = name;
    if (code) data.passcode = code;
    if (startMs) data.start_date = startMs;
    if (endMs)   data.end_date   = endMs;
    await this._hass.callService(DOMAIN, "change_passcode", data);
  }

  async _deletePasscode(passcodeId) {
    await this._hass.callService(DOMAIN, "delete_passcode", {
      lock_id:     this._selectedLockId,
      passcode_id: passcodeId,
    });
  }

  // ── Modal form submission ──────────────────────────────────────────────────

  async _submitModal() {
    const shadow = this.shadowRoot;
    const m      = this._modal;

    if (m.mode === "delete") {
      try {
        await this._deletePasscode(m.passcode.keyboardPwdId);
        this._toast("Passcode deleted", "success");
        this._modal = null;
        await this._listPasscodes();
      } catch (e) {
        this._toast("Delete failed: " + e.message, "error");
      }
      return;
    }

    const name  = shadow.getElementById("f-name")?.value.trim();
    const code  = shadow.getElementById("f-code")?.value.trim();
    const start = shadow.getElementById("f-start")?.value;
    const end   = shadow.getElementById("f-end")?.value;

    if (!name) { this._toast("Name is required", "error"); return; }
    if (!code && m.mode === "add") { this._toast("Passcode is required", "error"); return; }
    if (code && !/^\d{4,9}$/.test(code)) { this._toast("Passcode must be 4–9 digits", "error"); return; }

    const startMs = toMs(start);
    const endMs   = toMs(end);
    if (endMs && startMs && endMs < startMs) { this._toast("End must be after start", "error"); return; }

    try {
      if (m.mode === "add") {
        await this._addPasscode(name, code, startMs, endMs);
        this._toast("Passcode added", "success");
      } else {
        await this._changePasscode(m.passcode.keyboardPwdId, name, code || null, startMs, endMs);
        this._toast("Passcode updated", "success");
      }
      this._modal = null;
      await this._listPasscodes();
    } catch (e) {
      this._toast("Error: " + e.message, "error");
    }
  }

  // ── Toast ──────────────────────────────────────────────────────────────────

  _toast(msg, type = "") {
    const t = document.createElement("div");
    t.className = "toast" + (type ? " " + type : "");
    t.textContent = msg;
    this.shadowRoot.appendChild(t);
    setTimeout(() => t.remove(), 3200);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  _render() {
    const shadow = this.shadowRoot;
    shadow.innerHTML = `<style>${STYLES}</style>${this._html()}`;
    this._attach();
  }

  _html() {
    const title = this._config.title || "Passcode Manager";

    // Lock selector options
    const lockOptions = this._locks.map(l =>
      `<option value="${l.lock_id}" ${l.lock_id == this._selectedLockId ? "selected" : ""}>${l.name}</option>`
    ).join("");

    // Passcode list
    let listHtml = "";
    if (this._loading) {
      listHtml = `<div class="state-msg"><ha-icon icon="mdi:loading"></ha-icon>Loading passcodes…</div>`;
    } else if (this._passcodes.length === 0 && this._selectedLockId) {
      listHtml = `<div class="state-msg"><ha-icon icon="mdi:key-remove"></ha-icon>No passcodes yet. Press <strong>Load</strong> to fetch, or add one below.</div>`;
    } else {
      const rows = this._passcodes.map(p => {
        const typeLabel = p.keyboardPwdType == 2 ? "Permanent" :
                          p.keyboardPwdType == 3 ? `${fmtDate(p.startDate)} → ${fmtDate(p.endDate)}` :
                          `Type ${p.keyboardPwdType}`;
        return `
          <div class="passcode-row">
            <div class="pwd-info">
              <div class="pwd-name">${p.keyboardPwdName || "(unnamed)"}</div>
              <div class="pwd-meta">
                <span class="pwd-code">${p.keyboardPwd || "••••"}</span>
                &nbsp;·&nbsp;${typeLabel}
              </div>
            </div>
            <div class="row-actions">
              <button class="btn-icon edit" data-id="${p.keyboardPwdId}" data-action="edit" title="Edit">
                <ha-icon icon="mdi:pencil-outline"></ha-icon>
              </button>
              <button class="btn-icon del" data-id="${p.keyboardPwdId}" data-action="delete" title="Delete">
                <ha-icon icon="mdi:trash-can-outline"></ha-icon>
              </button>
            </div>
          </div>`;
      }).join("");
      listHtml = `<div class="passcode-list">${rows}</div>`;
    }

    const noLock = this._locks.length === 0;

    // Modal
    let modalHtml = "";
    if (this._modal) {
      modalHtml = this._modalHtml();
    }

    return `
      <ha-card class="card-root">
        <div class="header">
          <ha-icon icon="mdi:key-variant"></ha-icon>
          <span class="header-title">${title}</span>
        </div>

        <div class="lock-bar">
          <label>Lock</label>
          <select class="lock-select" id="lock-select" ${noLock ? "disabled" : ""}>
            ${noLock
              ? '<option>No Sifely locks found</option>'
              : lockOptions}
          </select>
          <button class="refresh-btn" id="btn-refresh" ${noLock ? "disabled" : ""}>
            <ha-icon icon="mdi:refresh"></ha-icon> Load
          </button>
        </div>

        ${listHtml}

        <div class="add-bar">
          <button class="btn-add" id="btn-add" ${noLock ? "disabled" : ""}>
            <ha-icon icon="mdi:plus"></ha-icon> Add passcode
          </button>
        </div>
      </ha-card>
      ${modalHtml}
    `;
  }

  _modalHtml() {
    const m = this._modal;

    if (m.mode === "delete") {
      return `
        <div class="modal-overlay" id="modal-overlay">
          <div class="modal">
            <div class="modal-header">
              <span class="modal-title">Delete passcode</span>
              <button class="btn-close" id="btn-modal-close"><ha-icon icon="mdi:close"></ha-icon></button>
            </div>
            <div class="confirm-msg">
              Delete <strong>${m.passcode.keyboardPwdName || "this passcode"}</strong>
              (${m.passcode.keyboardPwd})?<br>
              This cannot be undone.
            </div>
            <div class="modal-footer">
              <button class="btn btn-ghost" id="btn-modal-cancel">Cancel</button>
              <button class="btn btn-danger" id="btn-modal-submit">Delete</button>
            </div>
          </div>
        </div>`;
    }

    const p       = m.passcode || {};
    const isEdit  = m.mode === "edit";
    const title   = isEdit ? "Edit passcode" : "Add passcode";

    return `
      <div class="modal-overlay" id="modal-overlay">
        <div class="modal">
          <div class="modal-header">
            <span class="modal-title">${title}</span>
            <button class="btn-close" id="btn-modal-close"><ha-icon icon="mdi:close"></ha-icon></button>
          </div>
          <div class="modal-body">
            <div class="field">
              <label>Name *</label>
              <input id="f-name" type="text" placeholder="e.g. Guest — Jane Smith"
                     value="${p.keyboardPwdName || ""}">
            </div>
            <div class="field">
              <label>${isEdit ? "New passcode (leave blank to keep)" : "Passcode * (4–9 digits)"}</label>
              <input id="f-code" type="text" inputmode="numeric" pattern="[0-9]*"
                     placeholder="${isEdit ? "Leave blank to keep current" : "e.g. 481523"}"
                     value="">
            </div>
            <div class="field-row">
              <div class="field">
                <label>Valid from (optional)</label>
                <input id="f-start" type="datetime-local" value="${toLocalDatetime(p.startDate)}">
              </div>
              <div class="field">
                <label>Expires (optional)</label>
                <input id="f-end" type="datetime-local" value="${toLocalDatetime(p.endDate)}">
              </div>
            </div>
            <div class="field-hint">Leave both dates blank for a permanent passcode.</div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-ghost" id="btn-modal-cancel">Cancel</button>
            <button class="btn btn-primary" id="btn-modal-submit">${isEdit ? "Save" : "Add"}</button>
          </div>
        </div>
      </div>`;
  }

  // ── Event wiring ───────────────────────────────────────────────────────────

  _attach() {
    const s = this.shadowRoot;

    // Lock select
    s.getElementById("lock-select")?.addEventListener("change", e => {
      this._selectedLockId = parseInt(e.target.value);
      this._passcodes = [];
      this._render();
    });

    // Load button
    s.getElementById("btn-refresh")?.addEventListener("click", () => this._listPasscodes());

    // Add button
    s.getElementById("btn-add")?.addEventListener("click", () => {
      this._modal = { mode: "add" };
      this._render();
    });

    // Edit / Delete row buttons
    s.querySelectorAll("[data-action]").forEach(btn => {
      btn.addEventListener("click", () => {
        const id  = parseInt(btn.dataset.id);
        const pwd = this._passcodes.find(p => p.keyboardPwdId == id);
        this._modal = { mode: btn.dataset.action, passcode: pwd };
        this._render();
      });
    });

    // Modal close / cancel
    s.getElementById("btn-modal-close")?.addEventListener("click",  () => { this._modal = null; this._render(); });
    s.getElementById("btn-modal-cancel")?.addEventListener("click", () => { this._modal = null; this._render(); });

    // Modal overlay click-outside
    s.getElementById("modal-overlay")?.addEventListener("click", e => {
      if (e.target === s.getElementById("modal-overlay")) { this._modal = null; this._render(); }
    });

    // Modal submit
    s.getElementById("btn-modal-submit")?.addEventListener("click", () => this._submitModal());
  }
}

customElements.define("sifely-passcode-card", SifelyPasscodeCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type:        "sifely-passcode-card",
  name:        "Sifely Passcode Manager",
  description: "Manage guest passcodes for Sifely smart locks.",
  preview:     false,
});
