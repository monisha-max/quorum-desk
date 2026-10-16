// The court plan: where each seat sits, and the path the file takes between
// them. The paths are the workflow's edges, so the fork after the openings is
// the real route the bench took.

import { s } from "./dom.js";

const DESKS = {
  magistrate: { x: 450, y: 46, w: 230, h: 34, label: "Magistrate" },
  verifier: { x: 712, y: 50, w: 112, h: 26, label: "Verifier", code: true },
  clerk: { x: 450, y: 116, w: 118, h: 26, label: "Clerk" },
  ledger: { x: 290, y: 190, w: 122, h: 26, label: "Ledger" },
  archivist: { x: 450, y: 190, w: 122, h: 26, label: "Archivist" },
  statute: { x: 610, y: 190, w: 122, h: 26, label: "Statute" },
  prosecutor: { x: 104, y: 140, w: 152, h: 30, label: "Prosecutor" },
  counsel: { x: 796, y: 140, w: 152, h: 30, label: "Counsel" },
  liaison: { x: 450, y: 268, w: 126, h: 26, label: "Liaison" },
};

const PATHS = {
  "clerk>ledger": "M450 129 C450 158 290 150 290 177",
  "clerk>archivist": "M450 129 L450 177",
  "clerk>statute": "M450 129 C450 158 610 150 610 177",
  "ledger>prosecutor": "M229 190 C180 190 112 186 104 155",
  "statute>counsel": "M671 190 C720 190 788 186 796 155",
  "prosecutor~": "M104 116 a96 30 0 1 1 -0.1 0",
  "counsel~": "M796 116 a96 30 0 1 1 -0.1 0",
  "prosecutor>magistrate": "M104 125 C104 72 250 46 335 46",
  "counsel>magistrate": "M796 125 C790 96 660 92 565 58",
  "magistrate>verifier": "M565 46 L656 50",
  "verifier>liaison": "M712 63 C712 170 700 252 513 266",
  "liaison>out": "M450 281 L450 300",
};

const INTO = {
  ledger: ["clerk>ledger"],
  archivist: ["clerk>archivist"],
  statute: ["clerk>statute"],
  prosecutor: ["ledger>prosecutor"],
  counsel: ["statute>counsel"],
  prosecutor_rebuttal: ["prosecutor~"],
  counsel_rebuttal: ["counsel~"],
  magistrate: ["prosecutor>magistrate", "counsel>magistrate"],
  verifier: ["magistrate>verifier"],
  liaison: ["verifier>liaison"],
};

export const deskOf = (seat) => seat.replace(/_rebuttal$/, "");

const SOURCE = { gemini: "Gemini", standby: "standby", desk: "desk", template: "template" };

export class Plan {
  constructor(root) {
    this.root = root;
    this.desks = {};
    this.paths = {};
    const svg = s("svg", { viewBox: "0 0 900 300", class: "plan-svg", role: "img", "aria-label": "Plan of the hearing room" });
    svg.append(
      s("path", { class: "plan-bar", d: "M24 238 L382 238 M518 238 L876 238" }),
      s("text", { class: "plan-note", x: "28", y: "254" }, "the bar"),
      s("text", { class: "plan-note plan-note-end", x: "872", y: "254" }, "to the customer"),
    );
    for (const [id, d] of Object.entries(PATHS)) {
      const path = s("path", { class: `plan-path${id.endsWith("~") ? " plan-loop" : ""}`, d, pathLength: "100" });
      this.paths[id] = path;
      svg.append(path);
    }
    this.routeLabel = s("text", { class: "plan-route", x: "450", y: "88" });
    svg.append(this.routeLabel);
    for (const [seat, desk] of Object.entries(DESKS)) {
      const group = s("g", { class: `desk${desk.code ? " desk-code" : ""}`, dataset: { seat } },
        s("title", {}, desk.label),
        s("rect", { class: "desk-glow", x: desk.x - desk.w / 2 - 6, y: desk.y - desk.h / 2 - 6, width: desk.w + 12, height: desk.h + 12, rx: "9" }),
        s("rect", { class: "desk-top", x: desk.x - desk.w / 2, y: desk.y - desk.h / 2, width: desk.w, height: desk.h, rx: seat === "magistrate" ? "15" : "5" }),
        s("text", { class: "desk-label", x: desk.x, y: desk.y + 4.5 }, desk.label),
        s("text", { class: "desk-sub", x: desk.x, y: desk.y + desk.h / 2 + 13 }));
      this.desks[seat] = group;
      svg.append(group);
    }
    root.replaceChildren(svg);
    this.svg = svg;
  }

  reset() {
    for (const group of Object.values(this.desks)) {
      group.setAttribute("class", group.getAttribute("class").replace(/ is-[\w-]+/g, ""));
      group.querySelector(".desk-sub").textContent = "";
      delete group.dataset.position;
    }
    for (const path of Object.values(this.paths)) path.classList.remove("is-lit", "is-flowing", "is-unused");
    this.routeLabel.textContent = "";
    this.svg.classList.remove("is-sealed", "is-sitting");
  }

  _desk(seat) {
    return this.desks[deskOf(seat)];
  }

  sit(seats) {
    this.svg.classList.add("is-sitting");
    for (const seat of seats) {
      const desk = this._desk(seat);
      if (!desk) continue;
      desk.classList.remove("is-done");
      desk.classList.add("is-sitting");
      if (seat.endsWith("_rebuttal")) desk.classList.add("is-rising");
      desk.querySelector(".desk-sub").textContent = seat.endsWith("_rebuttal") ? "rises to rebut" : "sitting";
      for (const id of INTO[seat] || []) this.paths[id].classList.add("is-lit", "is-flowing");
    }
  }

  done(seat, record) {
    const desk = this._desk(seat);
    if (!desk) return;
    desk.classList.remove("is-sitting", "is-rising");
    desk.classList.add("is-done");
    for (const id of INTO[seat] || []) this.paths[id].classList.remove("is-flowing");
    const out = record?.out || {};
    const position = out.position || out.disposition;
    const sub = desk.querySelector(".desk-sub");
    if (record?.error) desk.classList.add("is-fallback");
    if (position) {
      desk.dataset.position = position;
      sub.textContent = out.moved ? `moves to ${position}` : position;
    } else {
      sub.textContent = record ? SOURCE[record.source] || record.source : "checked";
    }
  }

  route(route) {
    this.routeLabel.textContent = route === "contested" ? "contested · both sides rebut" : "agreed · no rebuttals";
    this.routeLabel.dataset.route = route;
    if (route === "agreed") {
      this.paths["prosecutor~"].classList.add("is-unused");
      this.paths["counsel~"].classList.add("is-unused");
    }
  }

  verifying() {
    this.sit(["verifier"]);
  }

  verified(result) {
    const desk = this.desks.verifier;
    desk.classList.remove("is-sitting");
    desk.classList.add("is-done");
    this.paths["magistrate>verifier"].classList.remove("is-flowing");
    const failing = result.checks.filter((check) => check.status === "fail").length;
    const fixed = result.checks.filter((check) => check.status === "fixed").length;
    desk.querySelector(".desk-sub").textContent = result.overturned
      ? `overturned to ${result.overturned.to}`
      : failing ? `${failing} failing` : fixed ? `${fixed} corrected` : "all checks pass";
    if (result.overturned || failing) desk.classList.add("is-fallback");
  }

  sealed() {
    this.paths["liaison>out"].classList.add("is-lit");
    this.svg.classList.remove("is-sitting");
    this.svg.classList.add("is-sealed");
  }

  /** Draw a finished hearing from its record, without the procession. */
  fromRecord(record) {
    this.reset();
    for (const [seat, seatRecord] of Object.entries(record.seats || {})) {
      for (const id of INTO[seat] || []) this.paths[id].classList.add("is-lit");
      this.done(seat, seatRecord);
    }
    if (record.route) this.route(record.route);
    for (const id of INTO.verifier) this.paths[id].classList.add("is-lit");
    this.verified(record.verified);
    this.sealed();
  }
}
