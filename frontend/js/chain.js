// The audit chain, checked in this browser. Nothing here trusts the server's
// own verdict on the chain: every hash is recomputed with SubtleCrypto.

import { h, $, $$, sleep, calm, when, short, announce } from "./dom.js";
import { api } from "./api.js";
import { seal, verifyChain } from "./seal.js";

const KIND = {
  hearing: "Hearing sealed",
  decision: "Officer decision",
  document: "Document uploaded",
  documents_removed: "Uploads removed",
};

function describe(entry) {
  try {
    const body = JSON.parse(entry.body);
    if (entry.kind === "hearing") return `${body.disposition}${body.mode !== "live" ? ` · ${body.mode}` : ""}`;
    if (entry.kind === "decision") return `${body.action} · ${body.disposition}`;
    if (entry.kind === "document") return `${body.doc_id}${body.reads_as_instruction ? " · reads as an instruction" : ""}`;
    if (entry.kind === "documents_removed") return (body.doc_ids || []).join(", ");
  } catch {
    // an edited copy may not parse; show nothing rather than guess
  }
  return "";
}

// Change one decisive word in a copy of an entry, the way a forger would.
function forge(entry) {
  const swaps = [['"disposition":"escalate"', '"disposition":"clear"'], ['"disposition":"hold"', '"disposition":"clear"'],
    ['"disposition":"clear"', '"disposition":"escalate"'], ['"disposition":"split"', '"disposition":"clear"']];
  for (const [from, to] of swaps) {
    if (entry.body.includes(from)) return { body: entry.body.replace(from, to), change: `${from.split(":")[1].replaceAll('"', "")} → ${to.split(":")[1].replaceAll('"', "")}` };
  }
  return { body: `${entry.body.slice(0, -1)} }`, change: "one character added" };
}

export class Chain {
  constructor(dialog, { onCheck } = {}) {
    this.dialog = dialog;
    this.onCheck = onCheck;
    this.data = null;
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  }

  async load() {
    this.data = await api.get("/api/audit?limit=300");
    return this.data;
  }

  /** Quietly verify the chain for the masthead chip. */
  async check() {
    const data = await this.load();
    const result = await verifyChain(data.entries, data.genesis);
    this.onCheck?.(result, data.entries.length);
    return result;
  }

  async open(focusSeq) {
    const list = h("ol.chain-list");
    const status = h("p.chain-status", { role: "status" }, "Loading the chain…");
    const verifyButton = h("button.primary", { type: "button", onclick: () => this.verify(list, status) }, "Verify in this browser");
    const forgeButton = h("button.secondary", { type: "button", onclick: () => this.forge(list, status) }, "Tamper with a copy");
    this.dialog.replaceChildren(
      h("header.drawer-head", {},
        h("h2#chain-title", {}, "Audit chain"),
        h("button.close", { type: "button", "aria-label": "Close", onclick: () => this.dialog.close() }, "×")),
      h("p.drawer-lead", {}, "Every hearing, upload and officer decision is appended here. Each entry's hash covers the entry before it, so changing any entry breaks every hash after it. Your browser recomputes them; it does not take the server's word."),
      h("p.drawer-rule", {}, h("code", {}, "hash = sha256(previous hash + \"\\n\" + body)")),
      h("div.drawer-actions", {}, verifyButton, forgeButton),
      status,
      h("div.forgery"),
      list);
    if (!this.dialog.open) this.dialog.showModal();
    try {
      await this.load();
    } catch (error) {
      status.textContent = error.message;
      return;
    }
    this.render(list, this.data.entries);
    status.textContent = this.data.entries.length ? `${this.data.entries.length} entries. Head ${short(this.data.entries.at(-1).hash, 10)}.` : "The chain is empty. Seal a hearing to start it.";
    if (focusSeq) {
      const row = $(`[data-seq="${focusSeq}"]`, list);
      row?.classList.add("is-focus");
      row?.scrollIntoView({ block: "center" });
    }
    if (this.data.entries.length) await this.verify(list, status);
  }

  render(list, entries) {
    list.replaceChildren(...[...entries].reverse().map((entry) => h("li.chain-entry", { dataset: { seq: entry.seq, state: "unchecked" } },
      seal(entry.hash, { small: true }),
      h("div.chain-text", {},
        h("p.chain-line", {}, h("span.chain-seq", {}, `Nº ${entry.seq}`), " ", KIND[entry.kind] || entry.kind, entry.alert_id ? h("code", {}, ` ${entry.alert_id}`) : null),
        h("p.chain-meta", {}, describe(entry), ` · ${when(entry.at)}`),
        h("p.chain-hash", {}, h("code", {}, short(entry.hash, 12)))),
      h("span.chain-mark", { "aria-hidden": "true" }))));
  }

  async verify(list, status, entries = this.data?.entries || []) {
    $$(".chain-entry", list).forEach((row) => { row.dataset.state = "unchecked"; });
    const pace = calm() ? 0 : Math.max(8, Math.min(60, 1200 / Math.max(1, entries.length)));
    const result = await verifyChain(entries, this.data.genesis, async (entry, ok) => {
      const row = $(`[data-seq="${entry.seq}"]`, list);
      if (row) row.dataset.state = ok ? "ok" : "broken";
      if (pace) await sleep(pace);
    });
    if (result.ok) {
      status.textContent = `Intact. ${result.checked} entries recomputed in this browser; head ${short(result.head, 10)}.`;
    } else {
      status.textContent = `Broken at Nº ${result.brokenAt}. Its hash does not match its contents, so every entry after it is unanchored.`;
      $$(".chain-entry", list).forEach((row) => { if (Number(row.dataset.seq) > result.brokenAt) row.dataset.state = "unanchored"; });
    }
    announce(status.textContent);
    if (entries === this.data.entries) this.onCheck?.(result, entries.length);
    return result;
  }

  async forge(list, status) {
    const entries = this.data?.entries || [];
    const target = [...entries].reverse().find((entry) => entry.kind === "hearing") || entries.at(-1);
    const panel = $(".forgery", this.dialog);
    if (!target) {
      status.textContent = "There is nothing to tamper with yet. Seal a hearing first.";
      return;
    }
    const { body, change } = forge(target);
    const copy = entries.map((entry) => (entry.seq === target.seq ? { ...entry, body } : entry));
    const result = await this.verify(list, status, copy);
    const recomputed = result.hash || target.hash;
    panel.replaceChildren(h("div.forgery-card", {},
      h("p.forgery-lead", {}, `In a copy held only by this page, entry Nº ${target.seq} was edited (${change}). The server's chain is untouched.`),
      h("div.forgery-seals", {},
        h("figure", {}, seal(target.hash, { small: true }), h("figcaption", {}, "As sealed", h("code", {}, short(target.hash, 8)))),
        h("figure", {}, seal(recomputed, { small: true }), h("figcaption", {}, "Recomputed from the edit", h("code", {}, short(recomputed, 8))))),
      h("button.link", { type: "button", onclick: async () => { panel.replaceChildren(); await this.verify(list, status); } }, "Discard the copy and verify the real chain")));
  }
}
