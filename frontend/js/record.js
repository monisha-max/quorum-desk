// The sealed record, printed on security paper: the verdict, where the money
// went, what the customer is told, the seal, and the officer's signature.

import { h, $, calm, money, when, seconds, short, announce } from "./dom.js";
import { api } from "./api.js";
import { seal } from "./seal.js";
import { SEAT, DISPOSITION, LANGUAGE } from "./proceedings.js";

const MODE = {
  live: "Heard live by Gemini",
  standby: "Heard on standby: authored briefs over real tool results, no model calls",
  replay: "Replay of a recorded live Gemini hearing",
};

function total(rows, ids) {
  const sums = {};
  for (const row of rows.filter((item) => ids.includes(item.id))) sums[row.currency] = (sums[row.currency] || 0) + row.amount;
  return sums;
}

function flow(alert, verdict) {
  const rows = alert.transactions;
  const held = verdict.held_txn_ids || [];
  const released = verdict.released_txn_ids || [];
  const heldSum = Object.values(total(rows, held)).reduce((a, b) => a + b, 0);
  const releasedSum = Object.values(total(rows, released)).reduce((a, b) => a + b, 0);
  const all = heldSum + releasedSum || 1;
  // Show a small held amount beside a large release; the figures carry the scale.
  const share = (value) => (value ? Math.max(10, Math.round((value / all) * 100)) : 0);
  const side = (kind, ids, amount, sum) => h("div.flow-side", { dataset: { kind }, style: { "--share": share(sum) } },
    h("span.flow-bar"),
    h("p.flow-amount", {}, amount || "nothing"),
    h("p.flow-label", {}, kind === "held" ? "held" : "released"),
    h("ul.flow-rows", {}, ids.map((id) => {
      const row = rows.find((item) => item.id === id);
      return h("li", { dataset: { txn: id } }, h("code", {}, id), row ? ` ${money(row.amount, row.currency)} to ${row.counterparty}` : "");
    })));
  return h("div.flow", { "aria-label": "Where the money went" },
    side("held", held, verdict.held_amount, heldSum),
    side("released", released, verdict.released_amount, releasedSum));
}

function phone(alert, liaison, verdict) {
  const out = liaison?.out || { language: "en", message: verdict.customer_message, english: verdict.customer_message };
  const language = out.language || "en";
  // In English the message is the bubble; otherwise the English is a gloss under it.
  const english = language === "en" ? h("p.bubble", {}, out.message || out.english) : h("p.bubble.bubble-en", { hidden: true }, out.english);
  const native = language === "en" ? null : h("p.bubble", { lang: language }, out.message);
  const toggle = language === "en" ? null : h("button.link", {
    type: "button",
    "aria-expanded": "false",
    onclick: (event) => {
      english.hidden = !english.hidden;
      event.currentTarget.setAttribute("aria-expanded", String(!english.hidden));
      event.currentTarget.textContent = english.hidden ? "Show the approved English" : "Hide the English";
    },
  }, "Show the approved English");
  return h("figure.phone", {},
    h("div.phone-screen", {},
      h("p.phone-from", {}, "Harbourline"),
      h("p.phone-to", {}, `to ${alert.customer.name}`),
      native || english,
      native ? english : null),
    h("figcaption", {}, language === "en" ? "Sent in English" : `Sent in ${LANGUAGE[language] || language}`, toggle ? " · " : "", toggle));
}

function decisionView(record) {
  const decision = record.decision;
  const verb = decision.action === "file" ? `filed this as ${decision.disposition}` : `overrode ${decision.proposed} to ${decision.disposition}`;
  return h("div.signed", {},
    h("p.signed-line", {}, h("span.signature", {}, decision.officer), ` ${verb} on ${when(decision.at)}.`),
    decision.note ? h("p.signed-note", {}, decision.note) : null,
    decision.audit ? h("p.signed-audit", {}, `Audit entry Nº ${decision.audit.seq} · `, h("code", {}, short(decision.audit.hash))) : null);
}

function decisionForm(record, onDecided) {
  const proposed = record.verified.verdict.disposition;
  const officer = h("input", { id: "officer", name: "officer", autocomplete: "name", minlength: "2", maxlength: "60", value: localStorage.getItem("quorum.officer") || "Duty officer" });
  const note = h("textarea", { id: "override-note", name: "note", rows: "3", maxlength: "600", placeholder: "Why the desk is changing the outcome" });
  const status = h("p.form-status", { role: "status" });
  const choices = h("fieldset.override-choices", {},
    h("legend", {}, "Change the outcome to"),
    Object.keys(DISPOSITION).filter((key) => key !== proposed).map((key, i) => h("label.choice", {},
      h("input", { type: "radio", name: "disposition", value: key, checked: i === 0 ? true : null }), DISPOSITION[key])));
  const override = h("div.override", { hidden: true }, choices, h("label.field", { for: "override-note" }, "Note for the record"), note);
  const send = async (action) => {
    const body = { action, officer: officer.value.trim() || "Duty officer", note: note.value.trim() };
    if (action === "override") body.disposition = $("input[name=disposition]:checked", choices)?.value;
    status.textContent = "Signing…";
    form.querySelectorAll("button").forEach((button) => { button.disabled = true; });
    try {
      localStorage.setItem("quorum.officer", body.officer);
      const updated = await api.post(`/api/hearings/${encodeURIComponent(record.id)}/decision`, body);
      announce(action === "file" ? "Filed." : "Override recorded.");
      onDecided(updated);
    } catch (error) {
      status.textContent = error.message;
      form.querySelectorAll("button").forEach((button) => { button.disabled = false; });
    }
  };
  const fileButton = h("button.primary", { type: "button", onclick: () => send("file") }, `File as ${DISPOSITION[proposed].toLowerCase()}`);
  const overrideButton = h("button.secondary", {
    type: "button",
    "aria-expanded": "false",
    onclick: () => {
      if (override.hidden) {
        override.hidden = false;
        overrideButton.setAttribute("aria-expanded", "true");
        overrideButton.textContent = "Record the override";
        note.focus();
      } else {
        send("override");
      }
    },
  }, "Override…");
  const form = h("form.decide", { onsubmit: (event) => event.preventDefault() },
    h("label.field", { for: "officer" }, "Signing officer"), officer,
    override,
    h("div.decide-actions", {}, fileButton, overrideButton),
    status);
  return form;
}

/** Render a sealed hearing record into `root`. */
export function renderRecord(root, record, alert, { onDecided, onChain, drawSeal = false } = {}) {
  const verified = record.verified;
  const verdict = verified.verdict;
  const disposition = verdict.disposition;
  const audit = record.audit || {};
  const struck = verified.struck || [];
  const sealArt = audit.hash
    ? seal(audit.hash, { label: `Nº ${audit.seq}`, sub: disposition.toUpperCase(), rim: `QUORUM · ${record.alert_id} · ${record.mode.toUpperCase()}`, draw: drawSeal && !calm() })
    : null;
  const sources = Object.entries(record.seats || {}).map(([seat, seatRecord]) => {
    const tokens = record.tokens?.[seat];
    return h("tr", {},
      h("th", { scope: "row" }, SEAT[seat]?.name || seat),
      h("td", {}, seatRecord.source === "gemini" ? seatRecord.model || "Gemini" : seatRecord.source),
      h("td.num", {}, seconds(seatRecord.ms)),
      h("td.num", {}, tokens ? (tokens.prompt + tokens.output + tokens.thinking).toLocaleString("en-SG") : "·"));
  });

  const sheet = h("article.record", { dataset: { disposition }, "aria-labelledby": "record-title" },
    h("header.record-head", {},
      h("div.record-title", {},
        h("p.eyebrow", {}, "Record of hearing"),
        h("h2#record-title", {}, alert.customer.name),
        h("p.record-id", {}, h("code", {}, record.id)),
        h("p.record-mode", { dataset: { mode: record.mode } },
          MODE[record.mode] || record.mode,
          record.replay_of ? h("span", {}, ` · of `, h("code", {}, record.replay_of)) : null,
          ` · ${when(record.created_at)} · ${seconds(record.ms)}`)),
      sealArt ? h("figure.record-seal", {},
        sealArt,
        h("figcaption", {},
          h("span", {}, `Audit entry Nº ${audit.seq}`),
          h("code", {}, short(audit.hash, 10)),
          h("button.link", { type: "button", onclick: () => onChain?.(audit.seq) }, "Check the chain in this browser"))) : null),

    h("section.verdict", {},
      h("p.disposition", { dataset: { disposition } }, DISPOSITION[disposition] || disposition),
      h("p.typology", {}, verdict.typology || ""),
      h("p.verdict-meta", {},
        `confidence ${Number(verdict.confidence ?? 0).toFixed(2)}`,
        verdict.false_positive ? h("span.tag", {}, "false positive cleared") : null,
        verified.overturned ? h("span.tag.tag-alert", {}, `overturned from ${verified.overturned.from}`) : null,
        verified.passed ? h("span.tag", {}, "all checks pass") : h("span.tag.tag-alert", {}, "a check failed"))),

    flow(alert, verdict),

    h("div.record-grid", {},
      h("div.record-main", {},
        verified.overturned
          ? [h("h3", {}, `Why the Magistrate said ${verified.overturned.from}`),
            h("p.overturn-note", {}, `Overturned to ${verified.overturned.to} by the Verifier: ${verified.overturned.reason}.`)]
          : h("h3", {}, "Why"),
        h("p.rationale", { dataset: { overturned: verified.overturned ? "true" : null } }, verdict.rationale),
        h("h3", {}, `Facts that stand (${(verdict.facts || []).length})`, struck.length ? h("span.h-note", {}, ` · ${struck.length} struck`) : null),
        h("ol.record-facts", {}, (verdict.facts || []).map((fact) => h("li", {}, fact.claim, " ", h("span.refs", {}, (fact.refs || []).map((ref) => h("code.ref-static", {}, ref)))))),
        struck.length ? h("ol.record-facts.record-struck", {}, struck.map((fact) => h("li", {}, h("s", {}, fact.claim), h("span.struck-why", {}, ` ${fact.reason}`)))) : null,
        verdict.next_step ? [h("h3", {}, "Next step"), h("p", {}, verdict.next_step)] : null,
        verdict.sar_draft ? h("details.sar", {}, h("summary", {}, "Suspicious activity report, draft for the reporting officer"), h("p", {}, verdict.sar_draft)) : null,
        h("h3", {}, "Checks"),
        h("ul.record-checks", {}, verified.checks.map((check) => h("li", { dataset: { status: check.status } },
          h("span.check-mark", { "aria-hidden": "true" }, check.status === "pass" ? "✓" : check.status === "fixed" ? "↻" : "✕"),
          h("span", {}, check.label), h("span.check-detail", {}, check.detail)))),
        h("details.seats", {},
          h("summary", {}, "Who sat, and on what"),
          h("table", {}, h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Seat"), h("th", { scope: "col" }, "Source"), h("th.num", { scope: "col" }, "Time"), h("th.num", { scope: "col" }, "Tokens"))),
            h("tbody", {}, sources)),
          h("p.seats-note", {}, `Warehouse: ${record.engine}.`, record.uploads?.length ? ` Uploaded documents heard: ${record.uploads.join(", ")}.` : ""))),
      h("aside.record-aside", {},
        h("h3", {}, "What the customer is told"),
        phone(alert, record.seats?.liaison, verdict))),

    h("section.officer", { "aria-label": "Officer's decision" },
      h("h3", {}, "The officer signs"),
      record.decision ? decisionView(record) : decisionForm(record, (updated) => {
        renderRecord(root, updated, alert, { onDecided, onChain });
        onDecided?.(updated);
      })));

  root.replaceChildren(sheet);
  if (drawSeal && !calm()) sheet.classList.add("is-rising");
  return sheet;
}
