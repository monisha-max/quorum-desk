// The desk API, and the hearing stream read with fetch (EventSource cannot POST).

import { sleep } from "./dom.js";

export class ApiError extends Error {
  constructor(message, status = 0, retryAfter = null) {
    super(message);
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

async function problem(response) {
  let message = `The desk answered ${response.status}.`;
  try {
    const data = await response.json();
    if (typeof data.detail === "string") message = data.detail;
    else if (Array.isArray(data.detail) && data.detail[0]?.msg) message = data.detail[0].msg;
  } catch {
    // not JSON; keep the status line
  }
  return new ApiError(message, response.status, Number(response.headers.get("Retry-After")) || null);
}

async function request(method, path, body) {
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("The desk is not reachable. Check the connection and try again.");
  }
  if (!response.ok) throw await problem(response);
  return response.json();
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body ?? {}),
  del: (path) => request("DELETE", path),
};

async function* frames(response) {
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += value;
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) yield JSON.parse(data);
    }
  }
}

/**
 * Convene a hearing and follow it to its seal. The server keeps sitting if the
 * connection drops, so a dropped stream re-attaches from the last event seen.
 */
export async function hear(alertId, mode, onEvent, { signal } = {}) {
  let response;
  try {
    response = await fetch(`/api/alerts/${encodeURIComponent(alertId)}/hear`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError("The desk is not reachable. Check the connection and try again.");
  }
  if (!response.ok) throw await problem(response);
  const hearingId = response.headers.get("X-Hearing-Id");
  let seen = 0;
  let ended = false;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    try {
      for await (const event of frames(response)) {
        seen += 1;
        await onEvent(event);
        if (event.type === "sealed" || event.type === "error") ended = true;
      }
    } catch (error) {
      if (signal?.aborted) throw error;
    }
    if (ended || !hearingId) break;
    await sleep(600 * (attempt + 1));
    try {
      response = await fetch(`/api/hearings/${encodeURIComponent(hearingId)}/stream?start=${seen}`, { signal });
    } catch (error) {
      if (signal?.aborted) throw error;
      continue;
    }
    if (!response.ok) break;
  }
  if (!ended) {
    throw new ApiError("The stream dropped. The hearing still seals on the server; it will appear under earlier hearings.");
  }
  return hearingId;
}
