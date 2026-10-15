const state = {
  alerts: [],
  selected: null,
  detail: null,
  hearingId: null,
  seats: {},
  minutes: [],
  disposition: null,
  engine: null,
  decision: null,
  busy: false,
};

const seats = ["clerk", "ledger", "archivist", "statute", "counsel", "magistrate"];
const stampWord = { clear: "Released", hold: "Held", escalate: "Escalate", split: "Split" };

const queue = document.querySelector("#queue");
const fileBody = document.querySelector("#file-body");
const empty = document.querySelector("#empty");
const minutes = document.querySelector("#minutes");
const actions = document.querySelector("#actions");
const stamp = document.querySelector("#stamp");

document.querySelector("#show-desk").onclick = () => show("desk");
document.querySelector("#show-customer").onclick = () => show("customer");
document.querySelector("#file-decision").onclick = () => fileDecision("file");
document.querySelector("#apply-override").onclick = () => fileDecision("override");
document.querySelector("#thread-pick").onchange = renderThread;

function show(which) {
  document.querySelector("#desk").hidden = which !== "desk";
  document.querySelector("#customer").hidden = which !== "customer";
  document.querySelector("#show-desk").classList.toggle("on", which === "desk");
  document.querySelector("#show-customer").classList.toggle("on", which === "customer");
  if (which === "customer") renderThread();
}

async function boot() {
  const [health, list] = await Promise.all([fetch("/api/health").then((r) => r.json()), loadQueue()]);
  const store = health.store === "firestore" ? "Firestore" : "local docket";
  const gemini = health.gemini === "unconfigured" ? "Gemini not configured" : "Gemini";
  document.querySelector("#stack").textContent = `${gemini} · ${store} · Cloud Run`;
  await loadQueue();
  if (list?.alerts?.[0]) select(list.alerts.find((row) => row.urgency === "live")?.id || list.alerts[0].id);
}

async function loadQueue() {
  const payload = await fetch("/api/alerts").then((r) => r.json());
  state.alerts = payload.alerts;
  const portfolio = await fetch("/api/portfolio").then((r) => r.json());
  document.querySelector("#portfolio").textContent = portfolio.filed
    ? `${portfolio.filed} filed · ${portfolio.cleared} released · ${portfolio.kept} still with the desk`
    : "Nothing filed yet.";
  queue.innerHTML = "";
  const pick = document.querySelector("#thread-pick");
  pick.innerHTML = "";
  for (const alert of state.alerts) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "qitem" + (alert.id === state.selected ? " on" : "");
    button.innerHTML = `<span class="amt">${alert.urgency === "live" ? '<span class="live">LIVE</span> ' : ""}${money(alert.amount, alert.currency)}</span><strong>${alert.customer}</strong><span class="rule">${alert.rule}</span>`;
    button.onclick = () => select(alert.id);
    item.append(button);
    queue.append(item);
    const option = document.createElement("option");
    option.value = alert.id;
    option.textContent = `${alert.customer} · ${alert.id}`;
    pick.append(option);
  }
  return payload;
}

async function select(id) {
  state.selected = id;
  state.seats = {};
  state.minutes = [];
  state.disposition = null;
  state.decision = null;
  state.engine = null;
  resetRing();
  const payload = await fetch(`/api/alerts/${id}`).then((r) => r.json());
  state.detail = payload.alert;
  const latest = payload.hearings[0];
  if (latest?.disposition) {
    state.hearingId = latest.id;
    state.disposition = latest.disposition;
    state.engine = latest.engine;
    state.decision = latest.decision;
    state.seats = latest.seats || {};
    for (const seat of seats) if (state.seats[seat]) mark(seat, "done");
    paintStamp(latest.disposition.disposition);
  } else {
    state.hearingId = null;
    paintStamp(null);
  }
  renderFile();
  renderMinutes();
  document.querySelectorAll(".qitem").forEach((button, index) => {
    button.classList.toggle("on", state.alerts[index].id === id);
  });
  document.querySelector("#thread-pick").value = id;
}

function renderFile() {
  const alert = state.detail;
  if (!alert) return;
  empty.hidden = true;
  fileBody.hidden = false;
  const rows = alert.transactions.map((row) => `<tr><td>${row.at}</td><td>${row.counterparty}</td><td>${row.narrative}</td><td class="num">${money(row.amount, row.currency)}</td></tr>`).join("");
  const docs = alert.documents.map((doc) => `<li><strong>${doc.kind}.</strong> ${doc.detail}</li>`).join("");
  const who = alert.customer;
  let verdict = "";
  if (state.disposition) {
    const d = state.disposition;
    verdict = `<section class="disposition"><p class="kicker">${state.engine === "gemini" ? "Heard by Gemini" : "Standby brief — Gemini did not finish this seat"}</p><h3>${stampWord[d.disposition] || d.disposition}</h3><p>${d.rationale}</p><div class="customer-note"><p class="kicker">Customer thread</p><p>${d.customer_message}</p></div>${d.sar_draft ? `<p><strong>Draft for the suspicious-matter file.</strong> ${d.sar_draft}</p>` : ""}<ul class="docs">${(d.citations || []).map((c) => `<li>${c.source} ${c.ref}: ${c.point}</li>`).join("")}</ul></section>`;
  }
  fileBody.innerHTML = `<p class="kicker">${alert.id} · ${alert.product}</p><h2 class="file-title">${who.name}</h2><p class="lede">${alert.summary}</p><div class="facts"><span>${money(alert.amount, alert.currency)}</span><span>${who.city}</span><span>${who.tenure_years} years</span><span>${alert.rule}</span></div><table><thead><tr><th>When</th><th>Who</th><th>Narrative</th><th class="num">Amount</th></tr></thead><tbody>${rows}</tbody></table><ul class="docs">${docs}</ul><button class="convene" id="convene" type="button" ${state.busy ? "disabled" : ""}>Convene the quorum</button>${verdict}`;
  document.querySelector("#convene").onclick = convene;
  actions.hidden = !state.disposition;
}

function resetRing() {
  document.querySelectorAll(".seat").forEach((seat) => seat.classList.remove("speaking", "done"));
  minutes.innerHTML = "";
}

function mark(seat, mode) {
  const node = document.querySelector(`.seat[data-seat="${seat}"]`);
  if (!node) return;
  node.classList.remove("speaking", "done");
  if (mode) node.classList.add(mode);
}

function paintStamp(kind) {
  stamp.className = "hub" + (kind ? ` ${kind}` : "");
  stamp.textContent = kind ? stampWord[kind] || kind : "Waiting";
}

function renderMinutes() {
  minutes.innerHTML = "";
  for (const line of state.minutes) {
    const item = document.createElement("li");
    item.innerHTML = `<strong>${line.seat}.</strong> ${line.text}`;
    minutes.append(item);
  }
  actions.hidden = !state.disposition;
}

async function convene() {
  if (!state.selected || state.busy) return;
  state.busy = true;
  state.minutes = [];
  state.disposition = null;
  state.seats = {};
  resetRing();
  renderFile();
  const response = await fetch("/api/hearings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ alert_id: state.selected }),
  });
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    for (const part of parts) apply(part);
  }
  if (buffer) apply(buffer);
  state.busy = false;
  renderFile();
  loadQueue();
}

function apply(part) {
  const line = part.split("\n").find((row) => row.startsWith("data: "));
  if (!line) return;
  const event = JSON.parse(line.slice(6));
  if (event.type === "started") state.hearingId = event.hearing_id;
  if (event.type === "seat" && event.state === "speaking") mark(event.seat, "speaking");
  if (event.type === "tool") {
    state.minutes.push({ seat: event.seat, text: `Opened ${event.tool.replaceAll("_", " ")}.` });
    renderMinutes();
  }
  if (event.type === "seat" && event.state === "done") {
    mark(event.seat, "done");
    state.minutes.push({ seat: event.seat, text: event.summary });
    renderMinutes();
  }
  if (event.type === "disposition") {
    state.disposition = event.disposition;
    state.engine = event.engine;
    state.hearingId = event.hearing_id;
    paintStamp(event.disposition.disposition);
    renderFile();
  }
  if (event.type === "error") {
    state.minutes.push({ seat: "desk", text: event.message });
    renderMinutes();
  }
}

async function fileDecision(action) {
  if (!state.hearingId || !state.disposition) return;
  const disposition = action === "override" ? document.querySelector("#override").value : state.disposition.disposition;
  const note = document.querySelector("#note").value;
  await fetch(`/api/hearings/${state.hearingId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, disposition, note }),
  });
  state.decision = { disposition };
  await loadQueue();
  renderThread();
}

function renderThread() {
  const id = document.querySelector("#thread-pick").value || state.selected;
  const alert = state.alerts.find((row) => row.id === id);
  const title = document.querySelector("#thread-title");
  const body = document.querySelector("#thread-body");
  if (!alert?.decision || !alert.customer_message) {
    const first = alert ? alert.customer.split(" ")[0] : "This customer";
    title.textContent = `${first}'s payment is still with the desk.`;
    body.textContent = "When the night desk files a disposition, this screen shows the plain-language note and nothing from the case file.";
    return;
  }
  title.textContent = stampWord[alert.decision.disposition] || "Filed";
  body.textContent = alert.customer_message;
}

function money(amount, currency) {
  return `${currency} ${Number(amount).toLocaleString("en-SG")}`;
}

boot();
