// The audit seal: a hash drawn as a guilloche rosette, the way banknotes print
// patterns that are hard to forge. Every curve comes from the hash bytes, so a
// changed entry gives a visibly different seal. The rim carries the full hash
// as microtext.

import { s } from "./dom.js";

export async function sha256(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

/** The same rule as store.entry_hash: sha256(prev + "\n" + body), over the stored body string. */
export const entryHash = (prev, body) => sha256(`${prev}\n${body}`);

/** Recompute the chain in this browser. Calls onEntry(entry, ok, hash) as it goes. */
export async function verifyChain(entries, genesis, onEntry) {
  let prev = entries.length && entries[0].seq !== 1 ? entries[0].prev : genesis;
  let checked = 0;
  for (const entry of entries) {
    const hash = await entryHash(entry.prev, entry.body);
    const ok = entry.prev === prev && hash === entry.hash;
    checked += 1;
    if (onEntry) await onEntry(entry, ok, hash);
    if (!ok) return { ok: false, brokenAt: entry.seq, checked, hash };
    prev = entry.hash;
  }
  return { ok: true, head: prev, checked };
}

const bytes = (hex) => (hex.match(/../g) || []).map((pair) => parseInt(pair, 16));

function band(base, waves, rotation, steps) {
  let d = "";
  for (let i = 0; i <= steps; i += 1) {
    const t = (i / steps) * Math.PI * 2;
    let r = base;
    for (const wave of waves) r += wave.a * Math.sin(wave.n * (t + rotation) + wave.phase);
    const x = r * Math.cos(t);
    const y = r * Math.sin(t);
    d += `${i ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
  }
  return `${d}Z`;
}

function bands(hex) {
  const b = bytes(hex);
  const pick = (i, lo, span) => lo + (b[i % b.length] % span);
  return [
    { base: 100 + pick(0, 0, 4), copies: pick(1, 14, 6), ink: "ovi",
      waves: [{ n: pick(2, 18, 12), a: 4 + (b[3] % 4), phase: b[4] / 40 }, { n: pick(5, 3, 4), a: 1 + (b[6] % 3), phase: b[7] / 40 }] },
    { base: 72 + pick(8, 0, 6), copies: pick(9, 10, 6), ink: "green",
      waves: [{ n: pick(10, 9, 8), a: 6 + (b[11] % 5), phase: b[12] / 40 }, { n: pick(13, 2, 4), a: 2 + (b[14] % 3), phase: b[15] / 40 }] },
    { base: 34 + pick(16, 0, 6), copies: pick(17, 8, 6), ink: "violet",
      waves: [{ n: pick(18, 5, 5), a: 12 + (b[19] % 8), phase: b[20] / 40 }, { n: pick(21, 9, 9), a: 2 + (b[22] % 3), phase: b[23] / 40 }] },
  ];
}

let uid = 0;

/**
 * An SVG seal for `hash`. `label` is the centre text, `rim` is printed around
 * the edge before the hash. `small` draws a lighter version for lists.
 */
export function seal(hash, { label = "", sub = "", rim = "", small = false, draw = false } = {}) {
  uid += 1;
  const id = `ovi-${uid}`;
  const rimText = `${rim ? `${rim} · ` : ""}${hash.toUpperCase()} · `;
  const paths = [];
  let index = 0;
  for (const spec of bands(hash)) {
    const copies = small ? Math.max(3, Math.round(spec.copies / 3)) : spec.copies;
    const steps = small ? 180 : Math.max(360, spec.waves[0].n * 22);
    for (let copy = 0; copy < copies; copy += 1) {
      const rotation = (copy * 2 * Math.PI) / (copies * spec.waves[0].n);
      paths.push(s("path", {
        d: band(spec.base, spec.waves, rotation, steps),
        class: `ink-${spec.ink}`,
        stroke: spec.ink === "ovi" ? `url(#${id})` : null,
        pathLength: "1",
        style: { "--i": index },
      }));
      index += 1;
    }
  }
  const svg = s("svg", {
    class: `seal${small ? " seal-small" : ""}${draw ? " seal-draw" : ""}`,
    viewBox: "-130 -130 260 260",
    role: "img",
    "aria-label": `Seal of hash ${hash}`,
  },
  s("defs", {},
    s("linearGradient", { id, gradientUnits: "userSpaceOnUse", x1: "-120", y1: "-120", x2: "120", y2: "120" },
      s("stop", { offset: "0", "stop-color": "#2F7D62" }),
      s("stop", { offset: "0.5", "stop-color": "#A98C4C" }),
      s("stop", { offset: "1", "stop-color": "#6A4A9A" })),
    s("path", { id: `${id}-rim`, d: "M0 -121a121 121 0 1 1 0 242a121 121 0 1 1 0 -242" })),
  s("circle", { class: "seal-ring", r: "126" }),
  s("circle", { class: "seal-ring", r: "116" }),
  small ? null : s("text", { class: "seal-micro" }, s("textPath", { href: `#${id}-rim`, textLength: "758", lengthAdjust: "spacing" }, rimText.repeat(2))),
  s("g", { class: "seal-bands" }, paths),
  s("circle", { class: "seal-core", r: small ? "26" : "24" }),
  label ? s("text", { class: "seal-label", y: sub ? "2" : "6" }, label) : null,
  sub ? s("text", { class: "seal-sub", y: "14" }, sub) : null);

  if (!small) {
    // Optically variable ink: the outer band shifts colour as the pointer moves over it.
    const gradient = svg.querySelector("linearGradient");
    svg.addEventListener("pointermove", (event) => {
      const box = svg.getBoundingClientRect();
      const angle = Math.atan2(event.clientY - box.top - box.height / 2, event.clientX - box.left - box.width / 2);
      gradient.setAttribute("gradientTransform", `rotate(${((angle * 180) / Math.PI).toFixed(1)})`);
    });
  }
  return svg;
}
