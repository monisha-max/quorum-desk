// The proceedings: one turn per seat as it speaks, the exhibits its tools put
// on the board, and the Verifier reading the verdict back.

import { h, $, $$, sleep, calm, humanise, announce } from "./dom.js";
import { deskOf } from "./plan.js";

export const SEAT = {
  clerk: { name: "Clerk", duty: "Frames the question the hearing must answer." },
  ledger: { name: "Ledger", duty: "Reads the warehouse: baselines, who else pays this account, payment history." },
  archivist: { name: "Archivist", duty: "Reads KYC and documents, and flags any that try to instruct the desk." },
  statute: { name: "Statute", duty: "Finds the Harbourline policy that governs the file." },
  sentinel: { name: "Sentinel", duty: "Reads only the documents and quotes any line that tries to steer the desk. Reports to the Verifier, not the bench." },
  prosecutor: { name: "Prosecutor", duty: "Argues for the most protective outcome the evidence supports." },
  counsel: { name: "Counsel", duty: "Argues the customer's legitimate explanation, or their protection." },
  prosecutor_rebuttal: { name: "Prosecutor, in rebuttal", duty: "Answers Counsel." },
  counsel_rebuttal: { name: "Counsel, in rebuttal", duty: "Answers the Prosecutor." },
  magistrate: { name: "Magistrate", duty: "Decides the outcome, the customer note and any report." },
  verifier: { name: "Verifier", duty: "Code, not a model. Reads the verdict back before anyone signs it." },
  liaison: { name: "Liaison", duty: "Writes to the customer in their own language." },
};

const PROSE = {
  clerk: "summary", ledger: "finding", archivist: "finding", statute: "finding",
  sentinel: "finding", prosecutor: "argument", counsel: "argument", prosecutor_rebuttal: "answer",
  counsel_rebuttal: "answer", magistrate: "rationale", liaison: "message",
};

export const DISPOSITION = {
  clear: "Clear", hold: "Hold", escalate: "Escalate", split: "Split",
};

export const LANGUAGE = {
  en: "English", ne: "Nepali", tl: "Tagalog", zh: "Chinese", ms: "Malay", ta: "Tamil", hi: "Hindi",
};

const TOOL = {
  customer_baseline: "Customer baseline",
  counterparty_fan_in: "Who else pays this account",
  beneficiary_history: "History with this payee",
  peer_percentile: "Against similar customers",
  read_file: "The file",
  search_policy: "Policy",
};

// Standby answers arrive all at once; pace them so a person can follow the bench.
const PACE = { sitting: 380, seat: 560, tool_call: 120, tool_result: 220, board: 240, route: 1000, sealed: 300 };

function sourceLabel(record) {
  if (!record) return "";
  if (record.source === "gemini") return record.model || "Gemini";
  if (record.source === "standby") return "standby brief";
  if (record.source === "desk") return "desk · no model needed";
  if (record.source === "template") return "desk template";
  return record.source;
}

function format(key, value) {
  if (value == null || value === "") return "none";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") {
    if (/share|ratio/.test(key) && value <= 1) return `${Math.round(value * 100)}%`;
    return value.toLocaleString("en-SG", { maximumFractionDigits: 2 });
  }
  if (Array.isArray(value)) return value.length ? value.map((item) => (typeof item === "object" ? Object.values(item).join(" ") : item)).join(", ") : "none";
  if (typeof value === "object") {
    const entries = Object.entries(value);
    return entries.length ? entries.map(([k, v]) => `${k}: ${format(k, v)}`).join(" · ") : "none";
  }
  return String(value);
}

function stamp(word, kind = word) {
  return h("span.stamp", { dataset: { kind } }, word);
}

export class Exhibits {
  constructor(root) {
    this.root = root;
    this.passages = {};
  }

  reset() {
    this.passages = {};
    this.root.replaceChildren(
      h("div.pane-head", {}, h("h2", {}, "Exhibits"), h("span.pane-note", {}, "What the tools returned")),
      h("p.empty", {}, "Tool results land here as the seats read the warehouse, the file and the policy book."),
    );
  }

  _list() {
    let list = $(".exhibit-list", this.root);
    if (!list) {
      $(".empty", this.root)?.remove();
      list = h("ol.exhibit-list");
      this.root.append(list);
    }
    return list;
  }

  remember(result) {
    for (const passage of result.passages || []) this.passages[passage.id] = passage;
  }

  add(ref, tool, summary, { flash = true } = {}) {
    if (!ref) return;
    const list = this._list();
    if ($(`[data-exhibit="${CSS.escape(ref)}"]`, list)) return;
    const rows = [];
    // A sealed record carries the passage on the board; a hearing that is sitting has it from the tool result.
    const passage = this.passages[ref] || (tool === "search_policy" && summary?.title ? summary : null);
    if (passage) {
      rows.push(h("p.ex-title", {}, passage.title));
      if (passage.text) rows.push(h("p.ex-text", {}, passage.text));
    } else {
      const facts = h("dl.ex-facts");
      for (const [key, value] of Object.entries(summary || {}).slice(0, 12)) {
        facts.append(h("dt", {}, humanise(key)), h("dd", {}, format(key, value)));
      }
      rows.push(facts);
    }
    const card = h("li.exhibit", { dataset: { exhibit: ref, tool: tool || "" }, tabindex: "-1" },
      h("header.ex-head", {}, h("span.ex-tag", {}, TOOL[tool] || tool || "Exhibit"), h("code.ex-ref", {}, ref)),
      rows);
    if (flash && !calm()) card.classList.add("is-new");
    list.append(card);
  }

  reconcile(board) {
    for (const item of board) this.add(item.ref, item.tool, item.summary, { flash: false });
  }
}

export class Proceedings {
  constructor({ root, exhibits, plan, onConvened, onSealed }) {
    this.root = root;
    this.exhibits = exhibits;
    this.plan = plan;
    this.onConvened = onConvened;
    this.onSealed = onSealed;
    this.queue = [];
    this.generation = 0;
    this.runner = null; // the generation whose loop is playing the queue
    this.waiters = [];
  }

  start(alert) {
    this.stop();
    this.alert = alert;
    this.turns = {};
    this.calls = {};
    this.mode = null;
    this.paused = false;
    this.fast = false;
    this.root.replaceChildren();
    this.plan.reset();
    this.exhibits.reset();
  }

  /** Abandon whatever is playing. A loop still asleep sees the new generation and exits. */
  stop() {
    this.generation += 1;
    this.queue = [];
    this._wake?.();
    this._settle();
  }

  push(event) {
    this.queue.push(event);
    if (this.runner !== this.generation) this._run(this.generation);
  }

  /** Resolves once every event pushed so far has been played (or abandoned). */
  idle() {
    if (this.runner !== this.generation && !this.queue.length) return Promise.resolve();
    return new Promise((resolve) => this.waiters.push(resolve));
  }

  _settle() {
    for (const resolve of this.waiters.splice(0)) resolve();
  }

  pause() {
    this.paused = true;
  }

  resume() {
    this.paused = false;
    this._wake?.();
  }

  skip() {
    this.fast = true;
    this.resume();
  }

  async _run(generation) {
    this.runner = generation;
    try {
      while (this.queue.length && generation === this.generation) {
        if (this.paused) {
          await new Promise((resolve) => { this._wake = resolve; });
          continue;
        }
        const event = this.queue.shift();
        await this.handle(event);
        const pace = this.mode === "standby" && !this.fast ? PACE[event.type] || 0 : 0;
        if (pace) await sleep(calm() ? pace / 2 : pace);
      }
    } finally {
      if (this.runner === generation) {
        this.runner = null;
        this._settle();
      }
    }
  }

  async handle(event) {
    const handler = this[`on_${event.type}`];
    if (handler) await handler.call(this, event);
  }

  _scroll(el) {
    if (!el || this.paused) return;
    const pane = this.root.closest(".chamber");
    const box = el.getBoundingClientRect();
    if (pane && box.bottom > innerHeight - 24) el.scrollIntoView({ block: "end", behavior: calm() || this.fast ? "auto" : "smooth" });
  }

  // ---- turns

  turn(seat) {
    if (this.turns[seat]) return this.turns[seat];
    const meta = SEAT[seat] || { name: seat, duty: "" };
    const source = h("span.turn-source", {}, "sitting");
    const el = h("article.turn", { dataset: { seat, desk: deskOf(seat), state: "sitting" } },
      h("header.turn-head", {},
        h("h3.turn-name", {}, meta.name),
        source,
        h("p.turn-duty", {}, meta.duty)));
    const turn = { el, source, thought: null, tools: null, prose: null, body: null, streamed: false };
    this.turns[seat] = turn;
    this.root.append(el);
    this._scroll(el);
    return turn;
  }

  _prose(turn) {
    if (!turn.prose) {
      turn.prose = h("p.turn-prose", { dataset: { streaming: "" } });
      turn.el.append(turn.prose);
    }
    return turn.prose;
  }

  _tools(turn) {
    if (!turn.tools) {
      turn.tools = h("div.turn-tools");
      turn.el.insertBefore(turn.tools, turn.prose || null);
    }
    return turn.tools;
  }

  refChip(ref) {
    return h("button.ref", {
      type: "button",
      dataset: { ref },
      title: `Show ${ref}`,
      onclick: () => this.cite(ref, true),
      onmouseenter: () => this.cite(ref, false),
    }, ref);
  }

  cite(ref, focus) {
    const target = document.querySelector(`[data-exhibit="${CSS.escape(ref)}"]`);
    if (!target) return;
    target.classList.remove("is-cited");
    void target.getBoundingClientRect();
    target.classList.add("is-cited");
    target.scrollIntoView({ block: "nearest", behavior: calm() ? "auto" : "smooth" });
    if (focus) target.focus({ preventScroll: true });
  }

  facts(facts) {
    return h("ol.facts", {},
      (facts || []).map((fact) => h("li.fact", { dataset: { claim: fact.claim } },
        h("span.claim", {}, fact.claim),
        h("span.refs", {}, (fact.refs || []).map((ref) => this.refChip(ref))))));
  }

  // ---- events

  on_convened(event) {
    this.mode = event.mode;
    this.models = event.models;
    this.onConvened?.(event);
    announce(`Hearing convened, ${event.mode === "live" ? "Gemini live" : event.mode}.`);
  }

  on_open(event) {
    for (const id of event.open || []) {
      document.querySelector(`[data-exhibit="${CSS.escape(id)}"]`)?.classList.add("is-open");
    }
  }

  on_sitting(event) {
    this.plan.sit(event.seats);
    for (const seat of event.seats) this.turn(seat);
    announce(`${event.seats.map((seat) => SEAT[seat]?.name || seat).join(", ")} sitting.`);
  }

  on_thought(event) {
    const turn = this.turn(event.seat);
    if (!turn.thought) {
      turn.thoughtText = h("p.thought-text");
      turn.thought = h("details.thought", { open: true }, h("summary", {}, "Thinking"), turn.thoughtText);
      turn.el.insertBefore(turn.thought, turn.tools || turn.prose || null);
    }
    turn.thoughtText.append(event.text);
  }

  on_draft(event) {
    const turn = this.turn(event.seat);
    turn.streamed = true;
    this._prose(turn).append(event.append);
    this._scroll(turn.prose);
  }

  on_retry(event) {
    // The seat was cut off mid-answer, refused or stalled, and is being asked again: what it wrote is void, the tools it ran stand.
    const turn = this.turn(event.seat);
    turn.thought?.remove();
    turn.prose?.remove();
    turn.thought = turn.thoughtText = turn.prose = null;
    turn.streamed = false;
    this._cut(turn);
    turn.source.textContent = "asking again";
    announce(`${SEAT[event.seat]?.name || event.seat} was cut off and is being asked again.`);
  }

  _cut(turn) {
    // A tool the void run was still waiting on never reports back.
    for (const chip of turn.el.querySelectorAll(".tool[data-state=running]")) {
      chip.dataset.state = "cut";
      chip.querySelector(".tool-stat").textContent = "cut off";
    }
  }

  on_tool_call(event) {
    const turn = this.turn(event.seat);
    const args = Object.entries(event.args || {}).map(([key, value]) => `${humanise(key)} ${value}`).join(", ");
    const stat = h("span.tool-stat", {}, "running");
    const body = h("div.tool-body");
    const chip = h("details.tool", { dataset: { state: "running" } },
      h("summary", {}, h("code.tool-name", {}, event.name), args ? h("span.tool-args", {}, args) : null, stat),
      body);
    this._tools(turn).append(chip);
    this.calls[event.id || `${event.seat}:${event.name}`] = { chip, stat, body };
  }

  on_tool_result(event) {
    const key = event.id || `${event.seat}:${event.name}`;
    const call = this.calls[key];
    const result = event.result || {};
    if (!call) return;
    if (result.error) {
      call.chip.dataset.state = "refused";
      call.stat.textContent = "refused";
      call.body.append(h("p.tool-refusal", {}, result.detail || result.error));
      return;
    }
    call.chip.dataset.state = "done";
    const queries = result.queries || [];
    const rows = queries.reduce((total, query) => total + (Number(query.rows) || 0), 0);
    call.stat.textContent = queries.length
      ? `${queries.length} ${queries.length === 1 ? "query" : "queries"} · ${rows} rows · ${result.ms ?? 0} ms`
      : result.passages ? `${result.passages.length} passages` : result.documents ? `${result.documents.length} documents` : "done";
    for (const query of queries) {
      call.body.append(
        h("p.sql-name", {}, query.name, h("span", {}, ` · ${query.engine || result.engine || ""}`)),
        h("pre.sql", {}, query.sql),
        query.params ? h("p.sql-params", {}, Object.entries(query.params).map(([k, v]) => `@${k} = ${v}`).join("   ")) : null);
    }
    for (const passage of result.passages || []) call.body.append(h("p.tool-passage", {}, h("code", {}, passage.id), ` ${passage.title}`));
    for (const doc of result.documents || []) call.body.append(h("p.tool-passage", {}, h("code", {}, doc.id), ` ${doc.kind}`));
    this.exhibits.remember(result);
    if (result.ref && result.tool !== "search_policy") this.exhibits.add(result.ref, result.tool, result.summary);
    for (const passage of result.passages || []) this.exhibits.add(passage.id, "search_policy", { title: passage.title });
  }

  on_seat(record) {
    const seat = record.seat;
    const turn = this.turn(seat);
    const out = record.out || {};
    turn.el.dataset.state = "done";
    turn.el.dataset.source = record.source;
    turn.source.textContent = sourceLabel(record);
    this._cut(turn);
    if (record.source !== "gemini") {
      // Reasoning from a run that never answered is not how a standby brief reasoned.
      turn.thought?.remove();
      turn.thought = turn.thoughtText = null;
    }
    turn.thought?.removeAttribute("open");
    if (turn.thought) turn.thought.querySelector("summary").textContent = "How it reasoned";
    const prose = this._prose(turn);
    prose.removeAttribute("data-streaming");
    const text = seat === "liaison" ? out.english : out[PROSE[seat]];
    if (text && prose.textContent !== text) {
      prose.textContent = text;
      if (!turn.streamed && !calm()) prose.classList.add("is-set");
    }
    const instead = record.source === "template" ? "the desk wrote this note itself" : "this seat read its standby brief";
    if (record.error) {
      turn.el.insertBefore(h("p.fallback", {}, `Gemini did not answer here (${record.error}), so ${instead}.`), prose);
    } else if (this.mode === "live" && (record.source === "standby" || record.source === "template")) {
      // A live hearing skips the model for every seat after enough have failed.
      turn.el.insertBefore(h("p.fallback", {}, `Earlier seats in this hearing failed, so ${instead} without asking Gemini.`), prose);
    }
    const body = h("div.turn-body");
    if (seat === "clerk") {
      if (out.question) body.append(h("p.question", {}, out.question));
      if (out.watch_for?.length) body.append(h("ul.watch", {}, out.watch_for.map((item) => h("li", {}, item))));
    }
    if (out.facts?.length) body.append(this.facts(out.facts));
    for (const item of out.instructions || []) {
      body.append(h("p.tamper-line", {}, stamp("Quoted", "objection"), " ", h("code", {}, item.document_id), ` “${item.quote}”`));
    }
    const foot = h("div.turn-foot");
    if (out.leans) foot.append(h("span.leans", { dataset: { leans: out.leans } }, `leans ${out.leans}`));
    for (const flag of out.tamper_flags || []) foot.append(stamp(`tamper · ${flag}`, "objection"));
    if (out.position) foot.append(stamp(out.position));
    if (out.moved) foot.append(stamp("Objection withdrawn", "withdrawn"));
    if (out.concession) body.append(h("p.concession", {}, h("span", {}, "Concedes "), out.concession));
    if (seat === "magistrate") {
      foot.append(stamp(DISPOSITION[out.disposition] || out.disposition, out.disposition));
      if (out.typology) foot.append(h("span.typology", {}, out.typology));
      if (out.confidence != null) foot.append(h("span.confidence", {}, `confidence ${Number(out.confidence).toFixed(2)}`));
    }
    if (seat === "liaison" && out.language && out.language !== "en") {
      body.append(h("p.native", { lang: out.language }, out.message),
        h("p.native-note", {}, `Sent in ${LANGUAGE[out.language] || out.language}. The English above is what the desk approved.`));
    }
    if (body.childNodes.length) turn.el.append(body);
    if (foot.childNodes.length) turn.el.append(foot);
    this.plan.done(seat, record);
    if (seat === "magistrate") this.plan.verifying();
    this._scroll(turn.el);
  }

  on_board(event) {
    this.exhibits.reconcile(event.board || []);
  }

  on_route(event) {
    const positions = event.positions || {};
    const contested = event.route === "contested";
    const el = h("div.route", { dataset: { route: event.route } },
      h("p.route-word", {}, contested ? "Contested" : "Agreed"),
      h("p.route-text", {}, contested
        ? `The Prosecutor opens on ${positions.prosecutor} and Counsel on ${positions.counsel}. Each side answers the other before the Magistrate decides.`
        : `Both sides open on ${positions.prosecutor}. There are no rebuttals; the Magistrate decides.`));
    this.root.append(el);
    this.plan.route(event.route);
    this._scroll(el);
    announce(contested ? "The bench is contested." : "The bench is agreed.");
  }

  async on_verified(result) {
    const turn = this.turn("verifier");
    turn.el.classList.add("turn-verifier");
    turn.source.textContent = "code";
    const list = h("ol.checks");
    turn.el.append(list);
    const pace = this.fast || calm() ? 0 : 260;
    for (const check of result.checks) {
      list.append(h("li.check", { dataset: { status: check.status } },
        h("span.check-mark", { "aria-hidden": "true" }, check.status === "pass" ? "✓" : check.status === "fixed" ? "↻" : "✕"),
        h("span.check-label", {}, check.label),
        h("span.check-detail", {}, check.detail),
        h("span.sr-only", {}, check.status)));
      this._scroll(list);
      if (pace) await sleep(pace);
    }
    const magistrate = this.turns.magistrate?.el;
    for (const fact of result.struck || []) {
      const item = magistrate && $$(".fact", magistrate).find((li) => li.dataset.claim === fact.claim);
      if (item) {
        item.classList.add("is-struck");
        item.append(stamp("Struck", "objection"), h("span.struck-why", {}, fact.reason));
      }
      turn.el.append(h("p.struck-line", {}, h("span.stamp", { dataset: { kind: "objection" } }, "Struck"), ` “${fact.claim}” ${fact.reason}.`));
      if (pace) await sleep(pace);
    }
    for (const doc of result.tamper || []) {
      const by = doc.by?.length ? ` Caught by ${doc.by.join(" and ")}.` : "";
      turn.el.append(h("p.tamper-line", {}, h("span.stamp", { dataset: { kind: "objection" } }, "Objection"),
        ` ${doc.id} reads as an instruction to the desk: “${doc.phrase}”.${by} It is evidence about the customer, not an order.`));
    }
    for (const id of result.unscreened || []) {
      turn.el.append(h("p.tamper-line", {}, h("span.stamp", { dataset: { kind: "objection" } }, "Unscreened"),
        ` ${id} was added to the file and no model screened it, so it cannot clear the file.`));
    }
    for (const item of result.unproven || []) {
      turn.el.append(h("p.struck-line", {}, h("span.stamp", { dataset: { kind: "objection" } }, "Struck"),
        ` The Sentinel quoted “${item.quote}” from ${item.id}: ${item.reason}, so it is ignored.`));
    }
    if (result.overturned) {
      const banner = h("div.overturned", { role: "alert" },
        h("p.overturned-word", {}, "Overturned"),
        h("p.overturned-text", {}, `The Magistrate said ${result.overturned.from}. The Verifier holds the money instead: ${result.overturned.reason}, so it cannot be cleared on this record.`));
      turn.el.append(banner);
      announce(`Verdict overturned from ${result.overturned.from} to ${result.overturned.to}.`);
    }
    turn.el.dataset.state = "done";
    this.plan.verified(result);
    this._scroll(turn.el);
  }

  on_sealed(event) {
    this.plan.sealed();
    announce(`Sealed as ${event.disposition}. Audit entry ${event.audit?.seq}.`);
    this.onSealed?.(event);
  }

  on_error(event) {
    const el = h("div.hearing-error", { role: "alert" },
      h("p.error-word", {}, "The hearing stopped"),
      h("p", {}, event.message),
      h("p.error-help", {}, "Nothing was sealed. Convene again; on standby the bench needs no model."));
    this.root.append(el);
    this._scroll(el);
  }
}
