/**
 * api.js - AIONOS Frontend API Client
 * Phase 5: Bearer token attached to all requests; 401 triggers logout.
 */

import { getToken, logout } from "./auth.js";

// Auto-detect backend URL:
//   - In production: set window.AIONOS_API_URL via a <script> or env injection
//   - Fallback to localhost for local dev
const BASE = window.AIONOS_API_URL || "https://aionos-agentic-factory-production.up.railway.app";

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    logout();
    throw new Error("Session expired. Please log in again.");
  }
  if (res.status === 429) {
    throw new Error("Too many requests. Please wait a moment before retrying.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API error");
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),

  // ── Alerts ─────────────────────────────────────────────────────────────────
  getAlertsSummary: () => request("/api/alerts/summary"),
  getAlerts: (params = {}) => {
    const q = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ""))
    );
    return request(`/api/alerts/?${q}`);
  },
  getAlert: (id) => request(`/api/alerts/${id}`),
  updateAlertStatus: (id, status) =>
    request(`/api/alerts/${id}/status?status=${encodeURIComponent(status)}`, { method: "PATCH" }),

  // ── Agents (blocking) ───────────────────────────────────────────────────────
  runAgent: (alertId) =>
    request("/api/agents/run", { method: "POST", body: JSON.stringify({ alert_id: alertId }) }),
  getTrace: (runId) => request(`/api/agents/trace/${runId}`),

  // ── Agents (streaming SSE) ──────────────────────────────────────────────────
  // provider: "mistral" (default) | "groq"
  streamAgent(alertId, onStep, onDone, onError, provider = "mistral") {
    return _openStream(`${BASE}/api/agents/stream/${alertId}?provider=${provider}`, onStep, onDone, onError);
  },

  // ── Supervisor ─────────────────────────────────────────────────────────────
  runSupervisor: (alertId) =>
    request("/api/supervisor/run", { method: "POST", body: JSON.stringify({ alert_id: alertId }) }),
  // provider: "mistral" (default) | "groq"
  streamSupervisor(alertId, onStep, onDone, onError, provider = "mistral") {
    return _openStream(`${BASE}/api/supervisor/stream/${alertId}?provider=${provider}`, onStep, onDone, onError);
  },
  getSupervisorTree: (runId) => request(`/api/supervisor/tree/${runId}`),
  getSupervisorHistory: (limit = 20) => request(`/api/supervisor/history?limit=${limit}`),

  // ── Approvals ───────────────────────────────────────────────────────────────
  getApprovals: (status = "pending") => request(`/api/approvals/?status=${status}`),
  getApproval: (id) => request(`/api/approvals/${id}`),
  submitDecision: (id, decision, reason = "") =>
    request(`/api/approvals/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, reason }),
    }),

  // ── Audit ───────────────────────────────────────────────────────────────────
  getAuditLogs: (params = {}) => {
    const q = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ""))
    );
    return request(`/api/audit/?${q}`);
  },

  // ── Observatory ─────────────────────────────────────────────────────────────
  getActiveRuns: () => request("/api/agents/active"),

  // ── Auth ────────────────────────────────────────────────────────────────────
  getMe: () => request("/api/auth/me"),
};

/** Shared SSE helper — attaches token as query param (EventSource can't set headers). */
function _openStream(url, onStep, onDone, onError) {
  const token = getToken();
  // url already has ?provider=..., so append token with &
  const separator = url.includes("?") ? "&" : "?";
  const fullUrl = token ? `${url}${separator}token=${encodeURIComponent(token)}` : url;
  const es = new EventSource(fullUrl);

  es.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data);
      if (event.type === "done")        { onDone?.(event); es.close(); }
      else if (event.type === "error")  { onError?.(event.message || "Agent error"); es.close(); }
      else if (event.type === "close")  { es.close(); }
      else                              { onStep?.(event); }
    } catch (_) {}
  };
  es.addEventListener("close", () => es.close());
  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) return;
    onError?.("Connection to agent stream lost");
    es.close();
  };
  return es;
}
