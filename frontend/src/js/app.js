/**
 * app.js - AIONOS Operations Control Room
 * Phase 5: Auth guard, logout, user display
 */

import { api } from "./api.js";
import { requireAuth, getUser, logout } from "./auth.js";
window.logout = logout;

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  page: "dashboard",
  summary: null,
  alerts: [], alertTotal: 0,
  alertFilters: { department: "", severity: "", status: "", limit: 50 },
  approvals: [], auditLogs: [],
  pendingApprovalCount: 0,
  activeStreams: {},   // alertId -> EventSource
  activeSupervisor: null,  // { alertId, runId, startTime }
};

// ── Router ────────────────────────────────────────────────────────────────────
const routes = {
  dashboard:   renderDashboard,
  alerts:      renderAlerts,
  approvals:   renderApprovals,
  observatory: renderObservatory,
  audit:       renderAudit,
};

function navigate(page) {
  state.page = page; location.hash = page;
  renderApp(); loadPageData(page);
}
window.addEventListener("hashchange", () => {
  const p = location.hash.slice(1) || "dashboard";
  if (routes[p]) { state.page = p; renderApp(); loadPageData(p); }
});

// ── Boot ──────────────────────────────────────────────────────────────────────
async function boot() {
  // Phase 5: Require valid JWT before rendering anything
  await requireAuth();

  const p = location.hash.slice(1) || "dashboard";
  state.page = routes[p] ? p : "dashboard";
  renderApp(); await loadGlobal(); loadPageData(state.page);
  setInterval(loadGlobal, 10000);
}

async function loadGlobal() {
  try {
    state.summary = await api.getAlertsSummary();
    const appr = await api.getApprovals("pending");
    state.pendingApprovalCount = appr.total || appr.approvals?.length || 0;
    renderSidebar();
    if (state.page === "dashboard") renderDashboardContent();
  } catch (e) { console.warn("Global:", e); }
}

async function loadPageData(page) {
  if (page === "alerts")      await loadAlerts();
  if (page === "approvals")   await loadApprovals();
  if (page === "audit")       await loadAuditLogs();
  if (page === "observatory") startObservatory();
}

// ── Utils ─────────────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const severityClass = (s) => ({ Critical:"critical", High:"high", Medium:"medium", Low:"low" }[s] || "low");
const statusClass   = (s) => (s||"").toLowerCase().replace(/_/g,"_");
function timeAgo(ts) {
  if (!ts) return "—";
  const m = Math.floor((Date.now() - new Date(ts)) / 60000);
  if (m < 1) return "just now"; if (m < 60) return `${m}m ago`;
  const h = Math.floor(m/60); if (h < 24) return `${h}h ago`;
  return `${Math.floor(h/24)}d ago`;
}
function elapsed(start) {
  const s = Math.floor((Date.now()-start)/1000);
  return s < 60 ? `${s}s` : `${Math.floor(s/60)}m ${s%60}s`;
}
function toast(msg, type="info") {
  const c = $("toast-container"); if (!c) return;
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  const icons = { success:"✓", error:"✕", info:"ℹ", warning:"⚠" };
  el.innerHTML = `<span style="color:${type==="success"?"#22c55e":type==="error"?"#f43f5e":type==="warning"?"#f97316":"#6366f1"}">${icons[type]||"·"}</span><span>${msg}</span>`;
  c.appendChild(el); setTimeout(() => el.remove(), 4000);
}

// ── App Shell ─────────────────────────────────────────────────────────────────
function renderApp() {
  document.querySelector("#app").innerHTML = `
    <div class="app-layout">
      <nav class="sidebar" id="sidebar"></nav>
      <div class="main" id="main-content"></div>
    </div>
    <div id="toast-container"></div>
    <div id="drawer-container"></div>
  `;
  renderSidebar();
  routes[state.page]?.();
}

function renderSidebar() {
  const s = $("sidebar"); if (!s) return;
  const pending = state.pendingApprovalCount;
  const activeAgents = Object.keys(state.activeStreams).length + (state.activeSupervisor ? 1 : 0);
  const links = [
    { id:"dashboard",   icon:"⬛", label:"Dashboard" },
    { id:"alerts",      icon:"🔔", label:"Alerts" },
    { id:"approvals",   icon:"✅", label:"Approvals", badge: pending > 0 ? pending : null },
    { id:"observatory", icon:"🔭", label:"Observatory", badge: activeAgents > 0 ? activeAgents : null, live: activeAgents > 0 },
    { id:"audit",       icon:"📋", label:"Audit Log" },
  ];
  s.innerHTML = `
    <div class="sidebar-logo">
      <div class="logo-mark">A</div>
      <div class="logo-text">AIONOS<span>Control Room</span></div>
    </div>
    <div class="nav-section">
      <div class="nav-section-label">Navigation</div>
      ${links.map(l => `
        <div class="nav-link ${state.page===l.id?"active":""}" onclick="window.navigate('${l.id}')">
          <span class="nav-icon">${l.icon}</span><span>${l.label}</span>
          ${l.live ? `<span class="nav-badge" style="background:#22c55e;animation:pulse 1s infinite">${l.badge}</span>` :
            l.badge ? `<span class="nav-badge">${l.badge}</span>` : ""}
        </div>`).join("")}
    </div>
    <div style="flex:1"></div>
    <div style="padding:14px 16px;border-top:1px solid var(--border)">
      ${(() => { const u = getUser(); return u ? `
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
          <div style="width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#f97316,#ea580c);display:flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:700;color:white;flex-shrink:0">${u.email?.[0]?.toUpperCase()||'U'}</div>
          <div style="overflow:hidden;flex:1">
            <div style="font-size:0.72rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${u.email}</div>
            <div style="font-size:0.65rem;color:var(--text-muted)">Authenticated</div>
          </div>
        </div>` : ''; })()
      }
      <button onclick="window.logout()" class="btn btn-ghost btn-sm" style="width:100%;justify-content:center;color:var(--text-secondary);font-size:0.75rem">
        ⎋ Sign Out
      </button>
    </div>`;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
function renderDashboard() {
  $("main-content").innerHTML = `
    <div class="page">
      <div style="background: linear-gradient(135deg, #f97316 0%, #ea580c 100%); border-radius: var(--radius-xl); padding: 40px; color: white; margin-bottom: 32px; position: relative; overflow: hidden; box-shadow: 0 12px 32px rgba(234, 88, 12, 0.2);">
        <div style="position: absolute; top: -50%; right: -10%; width: 300px; height: 300px; background: radial-gradient(circle, rgba(255,255,255,0.2) 0%, transparent 70%); border-radius: 50%;"></div>
        <div style="position: relative; z-index: 1;">
          <h1 style="font-family: var(--font-display); font-size: 2.5rem; letter-spacing: -0.04em; margin-bottom: 8px;">Operations Control Room</h1>
          <p style="font-size: 1.05rem; opacity: 0.9; max-width: 600px;">Real-time multi-department monitoring powered by AIONOS Agentic AI.</p>
        </div>
      </div>
      <div id="dashboard-content">
        <div class="flex items-center gap-3" style="color:var(--text-muted);padding:40px 0; justify-content: center;">
          <div class="spinner"></div>Loading insights…
        </div>
      </div>
    </div>`;
}

function renderDashboardContent() {
  const c = $("dashboard-content"); if (!c) return;
  const s = state.summary; if (!s) return;
  const overall = s.overall || {};
  const depts = ["Finance","HR","Sales","Operations"];
  const deptColors = { Finance:"#8b5cf6", HR:"#ec4899", Sales:"#10b981", Operations:"#ea580c" };
  const deptIcons  = { Finance:"💰", HR:"👥", Sales:"📈", Operations:"⚙️" };

  c.innerHTML = `
    <!-- Summary bar -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px;">
      <div class="card" style="display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; border-bottom: 4px solid #94a3b8; padding: 24px;">
        <div style="font-family: var(--font-heading); font-size: 0.8rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">Total Alerts</div>
        <div style="font-family: var(--font-display); font-size: 3rem; font-weight: 800; color: #0f172a; line-height: 1;">${overall.total??0}</div>
      </div>
      ${[["Open",overall.open,"#ea580c"],["In Progress",overall.in_progress,"#3b82f6"],["Pending Approval",overall.pending_approval,"#eab308"],["Resolved",overall.resolved,"#10b981"],["Critical",overall.critical,"#ef4444"]]
        .map(([l,v,col]) => `
        <div class="card" style="display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; border-bottom: 4px solid ${col}; padding: 24px;">
          <div style="font-family: var(--font-heading); font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">${l}</div>
          <div style="font-family: var(--font-display); font-size: 2.5rem; font-weight: 700; color: ${col}; line-height: 1;">${v??0}</div>
        </div>`).join("")}
    </div>

    <!-- KPI Grid -->
    <h2 style="font-family: var(--font-heading); font-size: 1.4rem; color: #0f172a; margin-bottom: 16px;">Department Overview</h2>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 32px;">
      ${depts.map(d => {
        const ds = s[d]||{}, col = deptColors[d];
        return `
        <div class="card" style="cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; position: relative; overflow: hidden;" onclick="window.navigate('alerts');window.setDeptFilter('${d}')" onmouseover="this.style.transform='translateY(-4px)'; this.style.boxShadow='0 12px 32px rgba(0,0,0,0.08)'" onmouseout="this.style.transform='none'; this.style.boxShadow='var(--shadow-card)'">
          <div style="position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: ${col};"></div>
          <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
            <div style="width: 48px; height: 48px; border-radius: 12px; background: ${col}15; display: flex; align-items: center; justify-content: center; font-size: 1.5rem;">${deptIcons[d]}</div>
            <div>
              <div style="font-family: var(--font-heading); font-size: 1.1rem; font-weight: 700; color: #0f172a;">${d}</div>
              <div style="font-size: 0.8rem; color: var(--text-secondary);">Department AI Agent</div>
            </div>
          </div>
          
          <div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 16px;">
            <div style="font-family: var(--font-display); font-size: 2.2rem; font-weight: 700; color: ${col}; line-height: 1;">${ds.total??0}</div>
            <div style="font-size: 0.8rem; color: var(--text-secondary); font-weight: 500; text-transform: uppercase;">Total</div>
          </div>

          <div style="display: flex; gap: 16px; font-size: 0.85rem; font-weight: 500;">
            <div style="display: flex; align-items: center; gap: 6px;"><div style="width:8px;height:8px;border-radius:50%;background:#ea580c"></div>${ds.open??0} Open</div>
            <div style="display: flex; align-items: center; gap: 6px;"><div style="width:8px;height:8px;border-radius:50%;background:#ef4444"></div>${ds.critical??0} Critical</div>
            <div style="display: flex; align-items: center; gap: 6px;"><div style="width:8px;height:8px;border-radius:50%;background:#10b981"></div>${ds.resolved??0} Resolved</div>
          </div>
        </div>`;
      }).join("")}
    </div>

    <!-- Supervisor History -->
    <div class="card" style="padding:0; overflow:hidden; margin-bottom:24px; border: 1px solid var(--border);">
      <div style="padding: 20px 24px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; background: #f8fafc;">
        <div style="font-family: var(--font-heading); font-weight: 700; font-size: 1.1rem; display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 1.3rem;">🔀</span> Orchestration History
        </div>
        <button class="btn btn-ghost btn-sm" onclick="window.navigate('observatory')" style="background: white; border: 1px solid var(--border); box-shadow: 0 1px 2px rgba(0,0,0,0.05);">View Observatory</button>
      </div>
      <div id="supervisor-history" style="padding: 8px;">
        <div style="padding: 32px; text-align: center; color: var(--text-muted); font-size: 0.9rem;">
          <div class="spinner" style="margin: 0 auto 12px;"></div>Loading orchestration logs…
        </div>
      </div>
    </div>
  `;
  api.getSupervisorHistory(5).then(res => {
    const sh = $("supervisor-history"); if (!sh) return;
    if (!res.history?.length) {
      sh.innerHTML = '<div style="padding:32px;text-align:center;color:var(--text-muted);font-size:0.9rem">No recent orchestration runs.</div>';
      return;
    }
    sh.innerHTML = res.history.map(h => `
      <div style="padding: 16px; border-bottom: 1px solid #f1f5f9; display: flex; align-items: center; justify-content: space-between; transition: background 0.2s; cursor: pointer;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'" onclick="window.navigate('observatory');setTimeout(()=>window.viewSupervisorTree('${h.run_id}'),100)">
        <div>
          <div style="font-family: var(--font-heading); font-weight: 600; font-size: 0.95rem; color: #0f172a; margin-bottom: 4px;">Run ${h.run_id.slice(0,8)} <span style="font-weight: 400; color: #64748b; font-size: 0.8rem; margin-left: 8px;">Alert #${h.alert_id}</span></div>
          <div style="font-size: 0.8rem; color: var(--text-secondary); display: flex; align-items: center; gap: 12px;">
            <span><strong style="color: #475569;">Steps:</strong> ${h.total_steps}</span>
            <span><strong style="color: #475569;">Duration:</strong> ${(h.duration_ms/1000).toFixed(1)}s</span>
          </div>
        </div>
        <div style="font-size: 0.8rem; color: #94a3b8;">${new Date(h.created_at).toLocaleString()}</div>
      </div>`).join("");
  }).catch(() => {
    const sh = $("supervisor-history"); if(sh) sh.innerHTML = '<div style="padding:20px;text-align:center;color:#ef4444;font-size:0.85rem">Failed to load history</div>';
  });
}

// ── Alerts ────────────────────────────────────────────────────────────────────
function renderAlerts() {
  $("main-content").innerHTML = `
    <div class="page">
      <div class="page-header">
        <h1>Alerts</h1>
        <p>▶ Run Agent — autonomous resolution · 🔀 Orchestrate — multi-agent for Critical alerts</p>
      </div>
      <div class="flex gap-3 items-center" style="margin-bottom:16px;flex-wrap:wrap">
        <select id="filter-dept" class="select" onchange="window.applyAlertFilters()">
          <option value="">All Departments</option>
          <option value="Finance">Finance</option><option value="HR">HR</option>
          <option value="Sales">Sales</option><option value="Operations">Operations</option>
        </select>
        <select id="filter-severity" class="select" onchange="window.applyAlertFilters()">
          <option value="">All Severities</option>
          <option value="Critical">Critical</option><option value="High">High</option>
          <option value="Medium">Medium</option><option value="Low">Low</option>
        </select>
        <select id="filter-status" class="select" onchange="window.applyAlertFilters()">
          <option value="">All Statuses</option>
          <option value="Open">Open</option><option value="In_Progress">In Progress</option>
          <option value="Pending_Approval">Pending Approval</option><option value="Resolved">Resolved</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="window.applyAlertFilters()">↻ Refresh</button>
        <span id="alert-count" style="margin-left:auto;font-size:0.8rem;color:var(--text-secondary)"></span>
      </div>
      <div id="alerts-grid" class="alerts-grid">
        <div class="flex items-center gap-3" style="padding:24px;color:var(--text-muted)"><div class="spinner"></div>Loading…</div>
      </div>
    </div>`;
  const df = state.alertFilters;
  if ($("filter-dept"))     $("filter-dept").value     = df.department;
  if ($("filter-severity")) $("filter-severity").value = df.severity;
  if ($("filter-status"))   $("filter-status").value   = df.status;
  loadAlerts();
}

async function loadAlerts() {
  try {
    const res = await api.getAlerts({ ...state.alertFilters });
    state.alerts = res.alerts || [];
    state.alertTotal = res.total || 0;
    renderAlertsGrid();
  } catch (e) {
    const tb = $("alerts-grid");
    if (tb) tb.innerHTML = `<div style="color:var(--critical);padding:20px;grid-column:1/-1">Error: ${e.message}</div>`;
  }
}

function renderAlertsGrid() {
  const tb = $("alerts-grid"), cnt = $("alert-count");
  if (cnt) cnt.textContent = `${state.alertTotal} alerts`;
  if (!tb) return;
  if (!state.alerts.length) {
    tb.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">🎉</div><p>No alerts match the filters</p></div>`;
    return;
  }
  tb.innerHTML = state.alerts.map(a => {
    const streaming = !!state.activeStreams[a.id];
    const supervising = state.activeSupervisor?.alertId === a.id;
    const canRun = ["Open","In_Progress"].includes(a.status);
    const isCritical = a.severity === "Critical";
    return `
    <div class="alert-card" id="alert-card-${a.id}">
      <div class="alert-card-header">
        <div class="flex items-center gap-2">
          <span class="badge badge-${severityClass(a.severity)}">${a.severity}</span>
          <span class="badge status-${statusClass(a.status)}">${a.status.replace(/_/g," ")}</span>
        </div>
        <span class="alert-card-age">${timeAgo(a.created_at)}</span>
      </div>
      
      <div class="alert-card-body">
        <h3 class="alert-title">${a.title}</h3>
        ${a.description ? `<p class="alert-desc">${a.description}</p>` : ""}
      </div>
      
      <div class="alert-card-meta flex gap-2">
        <div class="flex items-center gap-1"><div class="dept-dot dept-${a.department}"></div><span style="font-weight:500">${a.department}</span></div>
        <span style="color:var(--border);">|</span>
        <span class="tag">${a.alert_type}</span>
      </div>

      <div class="alert-card-footer">
        <div class="flex gap-2" style="width:100%">
          ${canRun && !supervising ? `
            <button id="run-btn-${a.id}" class="btn ${streaming?"btn-warning":"btn-primary"} btn-sm flex-1"
              onclick="window.runAgentStreaming(${a.id})" ${streaming?"disabled":""}>
              ${streaming?`<div class="spinner" style="width:12px;height:12px;border-width:2px"></div> Live…`:"▶ Run Agent"}
            </button>
            ${isCritical && !streaming ? `
              <button id="orch-btn-${a.id}" class="btn btn-sm flex-1" style="background:linear-gradient(135deg,#7c3aed,#4f46e5);color:#fff;border:none"
                onclick="window.runSupervisor(${a.id})">
                🔀 Orchestrate
              </button>` : ""}
          ` : supervising ? `
            <button disabled class="btn btn-sm flex-1" style="background:rgba(139,92,246,0.2);color:#a78bfa;border:1px solid rgba(139,92,246,0.3)">
              <div class="spinner" style="width:12px;height:12px;border-width:2px"></div> Orchestrating…
            </button>` : ""}
          <button class="btn btn-ghost btn-sm ${(!canRun && !supervising) ? 'flex-1' : ''}" onclick="window.openAlertDrawer(${a.id})">View Detail</button>
        </div>
      </div>
    </div>`;
  }).join("");
}

window.applyAlertFilters = function() {
  state.alertFilters.department = $("filter-dept")?.value   || "";
  state.alertFilters.severity   = $("filter-severity")?.value || "";
  state.alertFilters.status     = $("filter-status")?.value   || "";
  loadAlerts();
};
window.setDeptFilter = function(dept) { state.alertFilters.department = dept; };

// ── Department Agent Streaming ────────────────────────────────────────────────
window.runAgentStreaming = function(alertId) {
  if (state.activeStreams[alertId]) return;
  openStreamingDrawer(alertId, "Agent Run", "#6366f1");
  const start = Date.now();
  const es = api.streamAgent(
    alertId,
    (ev) => appendStreamStep(alertId, ev, start),
    (ev) => { delete state.activeStreams[alertId]; finalizeStreamDrawer(alertId, ev, start); loadAlerts(); loadGlobal(); renderSidebar(); },
    (msg) => { delete state.activeStreams[alertId]; renderSidebar(); toast(`Agent error: ${msg}`, "error"); }
  );
  state.activeStreams[alertId] = es;
  renderSidebar();
  toast(`Agent streaming for Alert #${alertId}`, "info");
};

// ── Supervisor Orchestration Streaming ────────────────────────────────────────
window.runSupervisor = function(alertId) {
  if (state.activeSupervisor) { toast("An orchestration is already running", "warning"); return; }
  state.activeSupervisor = { alertId, startTime: Date.now() };
  openStreamingDrawer(alertId, "🔀 Supervisor Orchestration", "#8b5cf6");
  const start = Date.now();

  // Add supervisor badge to drawer header
  const header = document.querySelector(".drawer-header div");
  if (header) {
    const badge = document.createElement("div");
    badge.style.cssText = "font-size:0.7rem;background:rgba(139,92,246,0.2);color:#a78bfa;border:1px solid rgba(139,92,246,0.3);padding:2px 8px;border-radius:100px;margin-top:4px;display:inline-block";
    badge.textContent = "Multi-Agent Orchestrator";
    header.appendChild(badge);
  }

  const es = api.streamSupervisor(
    alertId,
    (ev) => appendStreamStep(alertId, ev, start),
    (ev) => {
      state.activeSupervisor = null;
      finalizeStreamDrawer(alertId, ev, start);
      loadAlerts(); loadGlobal(); renderSidebar();
      toast(`Orchestration complete · ${ev.steps} steps`, "success");
    },
    (msg) => {
      state.activeSupervisor = null;
      renderSidebar(); renderAlertsGrid();
      toast(`Orchestration error: ${msg}`, "error");
    }
  );
  // Store in activeStreams too for sidebar count
  state.activeStreams[`supervisor-${alertId}`] = es;
  renderAlertsGrid();
  renderSidebar();
  toast(`Supervisor orchestrating Alert #${alertId}…`, "info");
};

// ── Streaming Drawer ──────────────────────────────────────────────────────────
function openStreamingDrawer(alertId, title, accentColor) {
  const dc = $("drawer-container");
  dc.innerHTML = `
    <div class="drawer-backdrop" onclick="window.closeDrawer()"></div>
    <div class="drawer">
      <div class="drawer-header">
        <div>
          <div style="font-weight:700;font-size:1rem">${title}</div>
          <div style="font-size:0.78rem;color:var(--text-secondary)">Alert #${alertId} · streaming live</div>
        </div>
        <button class="close-btn" onclick="window.closeDrawer()">✕</button>
      </div>
      <div style="padding:12px 20px;background:linear-gradient(90deg,${accentColor}1a,transparent);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px">
        <div style="width:8px;height:8px;border-radius:50%;background:#22c55e;animation:pulse 1s infinite"></div>
        <div style="font-size:0.8rem;color:var(--text-secondary)" id="stream-status-${alertId}">Initialising…</div>
        <div style="margin-left:auto;font-size:0.75rem;color:var(--text-muted)" id="stream-timer-${alertId}">0s</div>
      </div>
      <div class="drawer-body" style="padding:12px 16px" id="stream-steps-${alertId}"></div>
      <div id="stream-footer-${alertId}"></div>
    </div>`;

  const timerEl = $(`stream-timer-${alertId}`), start = Date.now();
  const timerId = setInterval(() => {
    if (!timerEl || !document.body.contains(timerEl)) { clearInterval(timerId); return; }
    timerEl.textContent = elapsed(start);
  }, 1000);
}

const STEP_META = {
  start:            { icon:"🚀", color:"#6366f1", label:"Started" },
  supervisor_start: { icon:"🔀", color:"#8b5cf6", label:"Supervisor initialised" },
  rag_fetch:        { icon:"📚", color:"#8b5cf6", label:"Fetching policy…" },
  rag_ready:        { icon:"✅", color:"#22c55e", label:"Policy loaded" },
  thinking:         { icon:"🤖", color:"#6366f1", label:"Thinking" },
  tool_call:        { icon:"🔧", color:"#f97316", label:"Tool call" },
  tool_result:      { icon:"📥", color:"#3b82f6", label:"Tool result" },
  done:             { icon:"✅", color:"#22c55e", label:"Complete" },
  error:            { icon:"❌", color:"#f43f5e", label:"Error" },
};

function appendStreamStep(alertId, event, startTime) {
  const container = $(`stream-steps-${alertId}`);
  const statusEl  = $(`stream-status-${alertId}`);
  if (!container) return;
  const meta = STEP_META[event.type] || { icon:"·", color:"#94a3b8", label:event.type };

  if (statusEl) {
    if (event.type === "thinking")    statusEl.textContent = "Reasoning…";
    else if (event.type === "tool_call") statusEl.textContent = `Calling ${event.name}…`;
    else if (event.type === "rag_fetch") statusEl.textContent = "Retrieving SOP policy…";
    else if (event.type === "supervisor_start") statusEl.textContent = "Supervisor planning orchestration…";
  }

  const step = document.createElement("div");
  step.style.cssText = `border-left:2px solid ${meta.color};padding:8px 12px;margin-bottom:6px;border-radius:0 var(--radius-sm) var(--radius-sm) 0;background:rgba(255,255,255,0.02);animation:slideIn 0.2s ease`;

  let body = "";
  if (event.type === "thinking") {
    body = `<div style="font-size:0.82rem;color:var(--text-secondary);margin-top:4px;line-height:1.6">${event.content}</div>`;
  } else if (event.type === "tool_call") {
    const args = JSON.stringify(event.args||{}, null, 2);
    body = `<div style="font-size:0.78rem;font-family:monospace;color:#f97316;margin-top:4px">${event.name}()</div>
      ${args!=="{}"?`<details style="margin-top:4px"><summary style="font-size:0.72rem;color:var(--text-muted);cursor:pointer">args</summary>
        <pre style="font-size:0.72rem;color:var(--text-secondary);white-space:pre-wrap;margin-top:4px;background:var(--bg-glass);padding:6px 8px;border-radius:4px">${args}</pre>
      </details>`:""}`;
  } else if (event.type === "tool_result") {
    body = `<div style="font-size:0.78rem;color:var(--text-secondary);margin-top:4px;font-family:monospace;background:var(--bg-glass);padding:6px 8px;border-radius:4px;white-space:pre-wrap">${(event.content||"").slice(0,400)}</div>`;
  } else if (event.type === "rag_ready") {
    body = `<div style="font-size:0.78rem;color:var(--text-secondary);margin-top:2px">${event.chunks} policy sections retrieved</div>`;
  } else if (event.type === "supervisor_start") {
    body = `<div style="font-size:0.78rem;color:var(--text-secondary);margin-top:2px">Multi-agent orchestration started for Alert #${event.alert_id}</div>`;
  }

  step.innerHTML = `<div style="display:flex;align-items:center;gap:6px">
    <span style="font-size:0.85rem">${meta.icon}</span>
    <span style="font-size:0.75rem;font-weight:600;color:${meta.color};text-transform:uppercase;letter-spacing:.06em">${meta.label}</span>
    ${event.step?`<span style="font-size:0.68rem;color:var(--text-muted);margin-left:auto">step ${event.step}</span>`:""}
  </div>${body}`;
  container.appendChild(step);
  container.scrollTop = container.scrollHeight;
}

function finalizeStreamDrawer(alertId, event, startTime) {
  const footer = $(`stream-footer-${alertId}`);
  const statusEl = $(`stream-status-${alertId}`);
  if (statusEl) statusEl.textContent = `Completed · ${event.final_status||"Done"}`;
  const dur = Math.floor((Date.now()-startTime)/1000);
  const col = event.final_status==="Resolved"?"#22c55e":event.final_status==="Pending_Approval"?"#f97316":"#6366f1";
  if (footer) footer.innerHTML = `
    <div style="padding:16px 20px;border-top:1px solid var(--border);background:rgba(34,197,94,0.04)">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px">
        <span style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#22c55e">✓ Completed</span>
        <span style="font-size:0.75rem;color:var(--text-muted)">${event.steps} steps · ${dur}s</span>
        ${event.final_status?`<span class="badge" style="background:${col}22;color:${col};border:1px solid ${col}44;font-size:0.72rem">${event.final_status}</span>`:""}
        ${event.run_id?`<span style="font-size:0.68rem;color:var(--text-muted);font-family:monospace">Run: ${event.run_id.slice(0,8)}…</span>`:""}
      </div>
      ${event.final_message?`<div style="font-size:0.8rem;color:var(--text-secondary);line-height:1.6;background:var(--bg-glass);padding:10px 12px;border-radius:var(--radius-sm)">${event.final_message}</div>`:""}
      ${event.run_id?`<button class="btn btn-ghost btn-sm" style="margin-top:10px" onclick="window.showOrchTree('${event.run_id}')">🔀 View Delegation Tree</button>`:""}
      <button class="btn btn-ghost btn-sm" style="margin-top:10px;margin-left:8px" onclick="window.closeDrawer()">Close</button>
    </div>`;
  // Cleanup stream tracking
  delete state.activeStreams[alertId];
  delete state.activeStreams[`supervisor-${alertId}`];
  renderAlertsGrid();
}

window.closeDrawer = function() {
  const dc = $("drawer-container"); if (dc) dc.innerHTML = "";
};

// ── Orchestration Tree Viewer ─────────────────────────────────────────────────
window.showOrchTree = async function(runId) {
  const dc = $("drawer-container");
  dc.innerHTML = `
    <div class="drawer-backdrop" onclick="window.closeDrawer()"></div>
    <div class="drawer">
      <div class="drawer-header">
        <div><div style="font-weight:700;font-size:1rem">🔀 Delegation Tree</div>
        <div style="font-size:0.72rem;font-family:monospace;color:var(--text-muted)">${runId}</div></div>
        <button class="close-btn" onclick="window.closeDrawer()">✕</button>
      </div>
      <div class="drawer-body" id="tree-body"><div class="flex items-center gap-3" style="color:var(--text-muted);padding:20px 0"><div class="spinner"></div>Loading tree…</div></div>
    </div>`;

  try {
    const tree = await api.getSupervisorTree(runId);
    const body = $("tree-body"); if (!body) return;

    const tasks = tree.tasks || [];
    const statusIcon = { done:"✅", running:"🔄", failed:"❌", pending:"⏳" };
    const deptIcon   = { Finance:"💰", HR:"👥", Sales:"📈", Operations:"⚙️" };

    body.innerHTML = `
      <div style="margin-bottom:20px">
        <div style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.08em;font-weight:600;margin-bottom:8px">Orchestration Tree</div>
        <div style="background:var(--bg-glass);border:1px solid var(--border);border-radius:var(--radius-sm);padding:16px;font-family:monospace;font-size:0.82rem">
          <div style="color:#8b5cf6;margin-bottom:8px">🔀 SupervisorAgent (${runId.slice(0,8)}…)</div>
          ${tasks.length === 0
            ? `<div style="color:var(--text-muted);padding-left:20px">No sub-agents delegated</div>`
            : tasks.map((t, i) => {
                const isLast = i === tasks.length - 1;
                const icon = statusIcon[t.status] || "·";
                const dicon = deptIcon[t.child_dept] || "·";
                return `<div style="padding-left:20px;color:var(--text-secondary);margin-bottom:6px">
                  ${isLast ? "└──" : "├──"} ${icon} ${dicon} ${t.child_dept}Agent
                  <span style="color:var(--text-muted);font-size:0.72rem;margin-left:8px">
                    Alert #${t.alert_id} · ${t.status}
                    ${t.child_run_id ? `· ${t.child_run_id.slice(0,8)}…` : ""}
                  </span>
                  ${t.result_summary ? `<div style="padding-left:40px;color:var(--text-muted);font-size:0.72rem;white-space:pre-wrap;margin-top:2px">${t.result_summary.slice(0,120)}…</div>` : ""}
                </div>`;
              }).join("")}
        </div>
      </div>

      <div style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.08em;font-weight:600;margin-bottom:8px">Supervisor Logs</div>
      <div class="trace-list">
        ${(tree.supervisor_logs||[]).map(l => `
          <div class="trace-step">
            <div class="trace-role" style="color:#8b5cf6">🔀 SupervisorAgent · ${l.action}</div>
            <div class="trace-content">${(l.details||"").slice(0,400)}</div>
            <div style="font-size:0.7rem;color:var(--text-muted);margin-top:6px">${timeAgo(l.timestamp)}</div>
          </div>`).join("") || `<div class="empty-state" style="padding:20px 0"><p>No supervisor logs yet</p></div>`}
      </div>`;
  } catch (e) { toast(`Failed to load tree: ${e.message}`, "error"); }
};

// ── Alert Detail Drawer ───────────────────────────────────────────────────────
window.openAlertDrawer = async function(alertId) {
  const dc = $("drawer-container");
  dc.innerHTML = `
    <div class="drawer-backdrop" onclick="window.closeDrawer()"></div>
    <div class="drawer">
      <div class="drawer-header">
        <div><div style="font-weight:700;font-size:1rem">Alert Detail</div>
        <div style="font-size:0.78rem;color:var(--text-secondary)">#${alertId}</div></div>
        <button class="close-btn" onclick="window.closeDrawer()">✕</button>
      </div>
      <div class="drawer-body"><div class="flex items-center gap-3" style="color:var(--text-muted);padding:20px 0"><div class="spinner"></div>Loading…</div></div>
    </div>`;
  try {
    const a = await api.getAlert(alertId);
    const body = dc.querySelector(".drawer-body"); if (!body) return;
    const trace = a.audit_trail || [];
    body.innerHTML = `
      <div style="margin-bottom:20px">
        <div class="flex gap-2 items-center" style="margin-bottom:10px;flex-wrap:wrap">
          <span class="badge badge-${severityClass(a.severity)}">${a.severity}</span>
          <span class="badge status-${statusClass(a.status)}">${a.status.replace(/_/g," ")}</span>
          <span style="font-size:0.75rem;color:var(--text-secondary);margin-left:auto">${timeAgo(a.created_at)}</span>
        </div>
        <h2 style="font-size:1rem;font-weight:700;margin-bottom:6px">${a.title}</h2>
        <div style="font-size:0.78rem;color:var(--text-secondary);margin-bottom:10px;display:flex;gap:12px;flex-wrap:wrap">
          <span><div class="dept-dot dept-${a.department}" style="display:inline-block;margin-right:5px"></div>${a.department}</span>
          <span class="tag">${a.alert_type}</span>
        </div>
        ${a.description?`<p style="font-size:0.82rem;color:var(--text-secondary);line-height:1.6">${a.description}</p>`:""}
      </div>
      <hr class="divider">
      <div style="font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text-secondary);margin-bottom:10px">
        Agent Trace ${a.agent_run_id?`· <span style="font-family:monospace;font-size:0.7rem">${a.agent_run_id.slice(0,8)}…</span>`:"(not run yet)"}
      </div>
      ${!trace.length ? `<div class="empty-state" style="padding:30px 0"><div class="empty-icon">🤖</div><p>No agent runs yet.</p></div>` : `
        <div class="trace-list">
          ${trace.map(t => `
            <div class="trace-step">
              <div class="trace-role" style="color:${t.agent_name==="SupervisorAgent"?"#8b5cf6":t.is_human_action?"#f97316":"#6366f1"}">
                ${t.agent_name==="SupervisorAgent"?"🔀 Supervisor":t.is_human_action?"👤 Human":"🤖 "+t.agent_name} · ${t.action}
              </div>
              <div class="trace-content">${(t.details||"").slice(0,400)}</div>
              <div style="font-size:0.7rem;color:var(--text-muted);margin-top:6px">${timeAgo(t.timestamp)}</div>
            </div>`).join("")}
        </div>`}
      ${(a.status==="Open"||a.status==="In_Progress")?`
        <hr class="divider">
        <div class="flex gap-2">
          <button class="btn btn-primary" style="flex:1" onclick="window.closeDrawer();window.runAgentStreaming(${a.id})">▶ Run Agent</button>
          ${a.severity==="Critical"?`<button class="btn btn-sm" style="flex:1;background:linear-gradient(135deg,#7c3aed,#4f46e5);color:#fff;border:none" onclick="window.closeDrawer();window.runSupervisor(${a.id})">🔀 Orchestrate</button>`:""}
        </div>`:""}`;
  } catch (e) { toast(`Failed to load alert: ${e.message}`, "error"); }
};

// ── Approvals ─────────────────────────────────────────────────────────────────
function renderApprovals() {
  $("main-content").innerHTML = `
    <div class="page">
      <div class="page-header"><h1>Approvals Queue</h1><p>Review agent escalations — including cross-department supervisor escalations</p></div>
      <div class="flex gap-3" style="margin-bottom:16px">
        <select id="approval-status-filter" class="select" onchange="window.loadApprovals()">
          <option value="pending">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="window.loadApprovals()">↻ Refresh</button>
      </div>
      <div id="approvals-list"></div>
    </div>`;
  loadApprovals();
}

async function loadApprovals() {
  const filter = $("approval-status-filter")?.value || "pending";
  try {
    const res = await api.getApprovals(filter);
    state.approvals = res.approvals || [];
    renderApprovalsList();
  } catch (e) { toast(e.message, "error"); }
}

function renderApprovalsList() {
  const c = $("approvals-list"); if (!c) return;
  if (!state.approvals.length) {
    c.innerHTML = `<div class="empty-state"><div class="empty-icon">✅</div><p>No approvals in this queue</p></div>`; return;
  }
  c.innerHTML = state.approvals.map(ap => {
    const isSupervisor = ap.agent_name === "SupervisorAgent";
    return `
    <div class="card" style="padding:22px;margin-bottom:14px${isSupervisor?";border-left:3px solid #8b5cf6":""}" id="approval-${ap.id}">
      <div class="flex justify-between items-center" style="margin-bottom:14px;flex-wrap:wrap;gap:8px">
        <div class="flex items-center gap-3">
          <span class="badge badge-${ap.risk_level==="Critical"?"critical":"high"}">${ap.risk_level} Risk</span>
          <span style="font-weight:600;font-size:0.9rem">${isSupervisor?"🔀 ":""}${ap.agent_name}</span>
          <span class="tag">Alert #${ap.alert_id}</span>
          ${isSupervisor?`<span class="tag" style="background:rgba(139,92,246,0.15);color:#a78bfa;border-color:rgba(139,92,246,0.3)">Cross-Dept</span>`:""}
        </div>
        <span style="font-size:0.75rem;color:var(--text-secondary)">${timeAgo(ap.created_at)}</span>
      </div>
      <div style="margin-bottom:12px">
        <div style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;font-weight:600;margin-bottom:4px">Action Requested</div>
        <div style="font-size:0.875rem;font-weight:500">${ap.action_requested}</div>
      </div>
      <div style="margin-bottom:12px">
        <div style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;font-weight:600;margin-bottom:4px">Findings</div>
        <div style="font-size:0.82rem;color:var(--text-secondary);line-height:1.6;background:var(--bg-glass);padding:10px 14px;border-radius:var(--radius-sm);border:1px solid var(--border)">${ap.context_summary||"—"}</div>
      </div>
      ${ap.policy_reference?`<div style="margin-bottom:16px"><div style="font-size:0.7rem;color:var(--text-muted);font-weight:600;margin-bottom:4px">Policy Reference</div>
        <div style="font-size:0.78rem;color:var(--indigo);background:var(--indigo-dim);padding:8px 12px;border-radius:var(--radius-sm)">${ap.policy_reference}</div></div>`:""}
      ${ap.status==="pending"?`
        <div class="flex gap-3 items-center" style="flex-wrap:wrap">
          <input class="input" id="reason-${ap.id}" placeholder="Optional reason…" style="flex:1;min-width:160px">
          <button class="btn btn-success" onclick="window.submitDecision(${ap.id},'approved')">✓ Approve</button>
          <button class="btn btn-danger"  onclick="window.submitDecision(${ap.id},'rejected')">✕ Reject</button>
        </div>`:`
        <div class="badge ${ap.status==="approved"?"badge-low":"badge-critical"}" style="font-size:0.8rem;padding:5px 14px">
          ${ap.status==="approved"?"✓ Approved":"✕ Rejected"}${ap.decided_at?` · ${timeAgo(ap.decided_at)}`:""}
        </div>`}
    </div>`;
  }).join("");
}

window.submitDecision = async function(apId, decision) {
  const reason = $(`reason-${apId}`)?.value || "";
  const card = $(`approval-${apId}`);
  if (card) card.style.opacity = "0.5";
  try {
    await api.submitDecision(apId, decision, reason);
    toast(`Decision '${decision}' recorded`, "success");
    await loadApprovals(); await loadGlobal();
  } catch (e) { if (card) card.style.opacity="1"; toast(`Error: ${e.message}`, "error"); }
};
window.loadApprovals = loadApprovals;

// ── Audit ─────────────────────────────────────────────────────────────────────
function renderAudit() {
  $("main-content").innerHTML = `
    <div class="page">
      <div class="page-header"><h1>Audit Log</h1><p>Every agent action, supervisor delegation, and human decision</p></div>
      <div class="flex gap-3 items-center" style="margin-bottom:16px;flex-wrap:wrap">
        <select id="audit-dept" class="select" onchange="window.loadAuditLogs()">
          <option value="">All Departments</option>
          <option value="Finance">Finance</option><option value="HR">HR</option>
          <option value="Sales">Sales</option><option value="Operations">Operations</option>
        </select>
        <select id="audit-type" class="select" onchange="window.loadAuditLogs()">
          <option value="">All Types</option><option value="false">Agent Actions</option><option value="true">Human Actions</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="window.loadAuditLogs()">↻ Refresh</button>
      </div>
      <div class="table-wrapper">
        <table><thead><tr><th>Time</th><th>Agent</th><th>Action</th><th>Details</th><th>Alert</th><th>Type</th></tr></thead>
        <tbody id="audit-tbody"><tr><td colspan="6"><div class="flex items-center gap-3" style="padding:24px;color:var(--text-muted)"><div class="spinner"></div>Loading…</div></td></tr></tbody>
        </table></div>
    </div>`;
  loadAuditLogs();
}

async function loadAuditLogs() {
  try {
    const res = await api.getAuditLogs({
      department:      $("audit-dept")?.value   || undefined,
      is_human_action: $("audit-type")?.value !== "" ? $("audit-type")?.value : undefined,
      limit: 100,
    });
    state.auditLogs = res.logs || [];
    const tb = $("audit-tbody"); if (!tb) return;
    if (!state.auditLogs.length) {
      tb.innerHTML = `<tr><td colspan="6"><div class="empty-state"><div class="empty-icon">📭</div><p>No entries found</p></div></td></tr>`;
      return;
    }
    tb.innerHTML = state.auditLogs.map(l => {
      const isSup = l.agent_name === "SupervisorAgent";
      return `<tr>
        <td style="white-space:nowrap;color:var(--text-secondary);font-size:0.78rem">${timeAgo(l.timestamp)}</td>
        <td style="font-size:0.82rem;font-weight:500">${isSup?"🔀 ":""}${l.agent_name||"—"}</td>
        <td><span class="tag">${l.action}</span></td>
        <td style="max-width:320px;font-size:0.8rem;color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${(l.details||"—").slice(0,100)}</td>
        <td>${l.alert_id?`<button class="btn btn-ghost btn-sm" onclick="window.openAlertDrawer(${l.alert_id})">#${l.alert_id}</button>`:"—"}</td>
        <td><span class="badge ${isSup?"":"badge-"+(l.is_human_action?"medium":"low")}" style="${isSup?"background:rgba(139,92,246,0.15);color:#a78bfa;border:1px solid rgba(139,92,246,0.3);":""}font-size:0.7rem">
          ${isSup?"🔀 Supervisor":l.is_human_action?"👤 Human":"🤖 Agent"}
        </span></td>
      </tr>`;
    }).join("");
  } catch (e) { toast(e.message, "error"); }
}
window.loadAuditLogs = loadAuditLogs;

// ── Observatory ───────────────────────────────────────────────────────────────
let _obsInterval = null;

function renderObservatory() {
  $("main-content").innerHTML = `
    <div class="page">
      <div class="page-header"><h1>Agent Observatory</h1><p>Live view of all running agents and orchestration trees · updates every 3s</p></div>
      <div style="margin-bottom:24px">
        <div style="font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text-secondary);margin-bottom:12px;display:flex;align-items:center;gap:8px">
          <div style="width:8px;height:8px;border-radius:50%;background:#22c55e;animation:pulse 1s infinite"></div>Active Runs
        </div>
        <div id="obs-active"><div class="flex items-center gap-3" style="color:var(--text-muted);padding:20px 0"><div class="spinner"></div>Loading…</div></div>
      </div>
      <div style="margin-bottom:24px">
        <div style="font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text-secondary);margin-bottom:12px">🔀 Orchestration History</div>
        <div id="obs-supervisor"><div class="flex items-center gap-3" style="color:var(--text-muted);padding:20px 0"><div class="spinner"></div>Loading…</div></div>
      </div>
      <div>
        <div style="font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text-secondary);margin-bottom:12px">Recent Agent Activity</div>
        <div id="obs-recent"></div>
      </div>
    </div>`;
}

function startObservatory() {
  if (_obsInterval) clearInterval(_obsInterval);
  refreshObservatory();
  _obsInterval = setInterval(refreshObservatory, 3000);
}

async function refreshObservatory() {
  if (state.page !== "observatory") { clearInterval(_obsInterval); return; }
  try {
    const [activeRes, auditRes, historyRes] = await Promise.all([
      api.getActiveRuns(),
      api.getAuditLogs({ limit: 20 }),
      api.getSupervisorHistory(8),
    ]);

    // Active
    const activeEl = $("obs-active");
    if (activeEl) {
      const runs = activeRes.active_runs || [];
      const localStreams = Object.keys(state.activeStreams).length;
      if (!runs.length && !localStreams) {
        activeEl.innerHTML = `<div class="empty-state" style="padding:24px 0"><div class="empty-icon">💤</div><p>No agents running right now</p></div>`;
      } else {
        activeEl.innerHTML = runs.map(r => `
          <div class="card" style="padding:16px 20px;margin-bottom:10px;border-left:3px solid #22c55e">
            <div class="flex items-center gap-3" style="flex-wrap:wrap">
              <div style="width:8px;height:8px;border-radius:50%;background:#22c55e;animation:pulse 1s infinite;flex-shrink:0"></div>
              <div><div style="font-weight:600;font-size:0.88rem">${r.title}</div>
                <div style="font-size:0.75rem;color:var(--text-secondary);margin-top:2px">${r.department} · ${r.alert_type} · started ${timeAgo(r.updated_at)}</div>
              </div>
              <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
                <span class="badge badge-${severityClass(r.severity)}" style="font-size:0.7rem">${r.severity}</span>
                <button class="btn btn-ghost btn-sm" onclick="window.openAlertDrawer(${r.id})">View</button>
              </div>
            </div>
          </div>`).join("");
      }
    }

    // Supervisor history
    const supEl = $("obs-supervisor");
    if (supEl) {
      const history = historyRes.history || [];
      if (!history.length) {
        supEl.innerHTML = `<div class="empty-state" style="padding:20px 0"><div class="empty-icon">🔀</div><p>No orchestration runs yet. Click <strong>🔀 Orchestrate</strong> on a Critical alert.</p></div>`;
      } else {
        supEl.innerHTML = history.map(h => `
          <div class="card" style="padding:14px 18px;margin-bottom:8px;border-left:3px solid #8b5cf6">
            <div class="flex items-center gap-3">
              <span style="font-size:0.85rem">🔀</span>
              <div style="flex:1">
                <div style="font-size:0.85rem;font-weight:600">Alert #${h.alert_id} · SupervisorAgent</div>
                <div style="font-size:0.75rem;color:var(--text-secondary);margin-top:2px">${(h.details||"").slice(0,100)}…</div>
              </div>
              <div style="text-align:right">
                <div style="font-size:0.72rem;color:var(--text-muted)">${timeAgo(h.timestamp)}</div>
                <button class="btn btn-ghost btn-sm" style="margin-top:4px" onclick="window.showOrchTree('${h.run_id}')">View Tree</button>
              </div>
            </div>
          </div>`).join("");
      }
    }

    // Recent agent activity
    const recentEl = $("obs-recent");
    if (recentEl) {
      const logs = (auditRes.logs || []).filter(l => !l.is_human_action);
      if (!logs.length) {
        recentEl.innerHTML = `<div class="empty-state" style="padding:24px 0"><div class="empty-icon">📭</div><p>No agent activity yet</p></div>`;
      } else {
        recentEl.innerHTML = `<div class="table-wrapper"><table>
          <thead><tr><th>Time</th><th>Agent</th><th>Action</th><th>Details</th><th>Alert</th></tr></thead>
          <tbody>${logs.map(l => `
            <tr>
              <td style="white-space:nowrap;color:var(--text-secondary);font-size:0.78rem">${timeAgo(l.timestamp)}</td>
              <td style="font-size:0.82rem;font-weight:500">${l.agent_name==="SupervisorAgent"?"🔀 ":""}${l.agent_name||"—"}</td>
              <td><span class="tag">${l.action}</span></td>
              <td style="max-width:300px;font-size:0.8rem;color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${(l.details||"—").slice(0,100)}</td>
              <td>${l.alert_id?`<button class="btn btn-ghost btn-sm" onclick="window.openAlertDrawer(${l.alert_id})">#${l.alert_id}</button>`:"—"}</td>
            </tr>`).join("")}
          </tbody></table></div>`;
      }
    }
  } catch (e) { console.warn("Observatory:", e); }
}

// ── Globals ───────────────────────────────────────────────────────────────────
window.navigate = navigate;

const style = document.createElement("style");
style.textContent = `@keyframes slideIn { from { opacity:0;transform:translateY(4px); } to { opacity:1;transform:translateY(0); } }`;
document.head.appendChild(style);

boot();
