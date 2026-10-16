// DOM helpers. Model text only ever enters the page through text nodes.

const SVG_NS = "http://www.w3.org/2000/svg";

function build(el, attrs, children) {
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === "class") el.setAttribute("class", [el.getAttribute("class"), value].filter(Boolean).join(" "));
    else if (key === "dataset") {
      for (const [name, v] of Object.entries(value)) if (v != null && v !== false) el.dataset[name] = String(v);
    }
    else if (key === "style" && typeof value === "object") {
      for (const [prop, v] of Object.entries(value)) el.style.setProperty(prop, String(v));
    }
    else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

// "h2#title.big.quiet" -> name "h2", id "title", classes ["big", "quiet"]
function parse(tag) {
  const [head, ...classes] = tag.split(".");
  const [name, id] = head.split("#");
  return { name, id, classes };
}

function create(el, id, classes, attrs, children) {
  if (id) el.id = id;
  if (classes.length) el.setAttribute("class", classes.join(" "));
  return build(el, attrs, children);
}

/** h("p#intro.lead.quiet", {title: "x"}, "text", child) */
export function h(tag, attrs, ...children) {
  const { name, id, classes } = parse(tag);
  return create(document.createElement(name || "div"), id, classes, attrs, children);
}

export function s(tag, attrs, ...children) {
  const { name, id, classes } = parse(tag);
  return create(document.createElementNS(SVG_NS, name), id, classes, attrs, children);
}

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

export function money(amount, currency) {
  if (amount == null || amount === "") return "";
  return `${currency} ${Number(amount).toLocaleString("en-SG", { maximumFractionDigits: 0 })}`;
}

export function when(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  return date.toLocaleString("en-SG", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });
}

export function seconds(ms) {
  if (ms == null) return "";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)} s`;
}

export const short = (hash, n = 6) => (hash ? `${hash.slice(0, n)}…${hash.slice(-4)}` : "");

export function humanise(key) {
  return key.replace(/_/g, " ");
}

export function announce(text) {
  const region = $("#announce");
  if (region) region.textContent = text;
}
