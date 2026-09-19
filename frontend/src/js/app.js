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
  selectedProvider: "mistral",  // "mistral" | "groq"
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

window.showInfoModal = function(title, text) {
  const dc = document.getElementById("drawer-container");
  dc.innerHTML = `
    <div style="position:fixed; top:0; left:0; width:100vw; height:100vh; display:flex; align-items:center; justify-content:center; z-index:99999; background:rgba(0,0,0,0.5); backdrop-filter:blur(4px);" onclick="window.closeDrawer()">
      <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:24px; max-width:400px; width:90%; box-shadow:0 25px 50px rgba(0,0,0,0.2); position:relative;" onclick="event.stopPropagation()">
        <button onclick="window.closeDrawer()" style="position:absolute;top:16px;right:16px;background:none;border:none;cursor:pointer;font-size:1.4rem;color:var(--text-muted);">&times;</button>
        <div style="font-family:var(--font-heading);font-size:1.2rem;font-weight:700;color:#0f172a;margin-bottom:12px;display:flex;align-items:center;gap:8px;"><span style="color:#6366f1;font-size:1.4rem;">ℹ️</span> ${title}</div>
        <div style="font-size:0.95rem;color:var(--text-secondary);line-height:1.6;">${text}</div>
      </div>
    </div>`;
};

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
        <div style="position: absolute; top: -50%; right: -10%; width: 300px; height: 300px; background: radial-gradient(circle, rgba(255,255,255,0.2) 0%, transparent 70%); border-radius: 50%; pointer-events: none;"></div>
        
        <!-- Architecture / Flow Button -->
        <button onclick="window.showArchitectureModal()" style="position:absolute; top:24px; right:84px; background:white; border:none; cursor:pointer; color:#0ea5e9; width:44px; height:44px; border-radius:50%; display:flex; align-items:center; justify-content:center; transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); z-index: 10; box-shadow: 0 4px 15px rgba(0,0,0,0.15);" title="View Architecture & Test Cases" onmouseover="this.style.transform='scale(1.08)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.2)';" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 4px 15px rgba(0,0,0,0.15)';">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="7" height="7"></rect>
            <rect x="14" y="3" width="7" height="7"></rect>
            <rect x="14" y="14" width="7" height="7"></rect>
            <rect x="3" y="14" width="7" height="7"></rect>
            <path d="M10 6.5h4"></path>
            <path d="M17 10v4"></path>
            <path d="M10 17.5h4"></path>
            <path d="M6.5 10v4"></path>
          </svg>
        </button>

        <!-- Logout / Back to Login Button -->
        <button onclick="window.logout()" style="position:absolute; top:24px; right:24px; background:white; border:none; cursor:pointer; color:#ea580c; width:44px; height:44px; border-radius:50%; display:flex; align-items:center; justify-content:center; transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); z-index: 10; box-shadow: 0 4px 15px rgba(0,0,0,0.15);" title="Sign out / Back to Login" onmouseover="this.style.transform='scale(1.08)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.2)';" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 4px 15px rgba(0,0,0,0.15)';">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-left: 2px;">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
            <polyline points="16 17 21 12 16 7"></polyline>
            <line x1="21" y1="12" x2="9" y2="12"></line>
          </svg>
        </button>

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
          
          <button onclick="event.preventDefault(); event.stopPropagation(); window.showInfoModal('${d} Department', 'The ${d} AI Agent automatically monitors and resolves alerts belonging to this department. Click anywhere on this card to view the specific queue.')" style="position:absolute; top:16px; right:16px; background:none; border:none; cursor:pointer; font-size:1.2rem; color:#94a3b8; z-index:10; padding:4px;" onmouseover="this.style.color='${col}'" onmouseout="this.style.color='#94a3b8'">ℹ️</button>

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
      <div style="padding: 16px; border-bottom: 1px solid #f1f5f9; display: flex; align-items: center; justify-content: space-between; transition: background 0.2s; cursor: pointer;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'" onclick="window.navigate('observatory');setTimeout(()=>window.showOrchTree('${h.run_id}'),100)">
        <div>
          <div style="font-family: var(--font-heading); font-weight: 600; font-size: 0.95rem; color: #0f172a; margin-bottom: 4px;">Run ${h.run_id.slice(0,8)} <span style="font-weight: 400; color: #64748b; font-size: 0.8rem; margin-left: 8px;">Alert #${h.alert_id}</span></div>
          <div style="font-size: 0.8rem; color: var(--text-secondary); display: flex; align-items: center; gap: 12px;">
            <span><strong style="color: #475569;">Steps:</strong> ${h.total_steps}</span>
            <span><strong style="color: #475569;">Duration:</strong> ${(h.duration_ms/1000).toFixed(1)}s</span>
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <div style="font-size: 0.8rem; color: #94a3b8;">${new Date(h.created_at).toLocaleString()}</div>
          <button onclick="event.preventDefault(); event.stopPropagation(); window.showInfoModal('Orchestration Run ${h.run_id.slice(0,8)}', 'This tracks a multi-agent workflow where the Supervisor AI broke down Alert #${h.alert_id} into sub-tasks and delegated them to other department agents. Click the card to view the full delegation tree.')" style="background:none; border:none; cursor:pointer; font-size:1.2rem; color:#94a3b8; padding:4px;" onmouseover="this.style.color='#8b5cf6'" onmouseout="this.style.color='#94a3b8'">ℹ️</button>
        </div>
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

      <!-- LLM Provider Toggle & API Limits -->
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;padding:14px 16px;background:var(--bg-glass);border:1px solid var(--border);border-radius:var(--radius-lg);flex-wrap:wrap">
        <span style="font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-secondary);white-space:nowrap">🤖 LLM Provider</span>
        <div style="display:flex;gap:6px;background:var(--bg-input);border:1px solid var(--border);border-radius:100px;padding:3px">
          <button id="provider-mistral" onclick="window.setProvider('mistral')"
            style="padding:5px 16px;border-radius:100px;border:none;font-size:0.78rem;font-weight:600;cursor:pointer;transition:all 0.18s;background:${state.selectedProvider==='mistral'?'linear-gradient(135deg,#6366f1,#4f46e5)':'transparent'};color:${state.selectedProvider==='mistral'?'#fff':'var(--text-secondary)'}">
            ✦ Mistral
          </button>
          <button id="provider-groq" onclick="window.setProvider('groq')"
            style="padding:5px 16px;border-radius:100px;border:none;font-size:0.78rem;font-weight:600;cursor:pointer;transition:all 0.18s;background:${state.selectedProvider==='groq'?'linear-gradient(135deg,#f97316,#ea580c)':'transparent'};color:${state.selectedProvider==='groq'?'#fff':'var(--text-secondary)'}">
            ⚡ Groq
          </button>
        </div>
        <span style="font-size:0.73rem;color:var(--text-muted)">
          ${state.selectedProvider === "groq"
            ? "<span style='color:#f97316;font-weight:600'>Groq</span>"
            : "<span style='color:#6366f1;font-weight:600'>Mistral</span>"}
        </span>
        
        <!-- API Limit Tracker -->
        <div style="margin-left:auto;display:flex;align-items:center;gap:12px" id="api-limit-tracker">
          <div style="font-size:0.73rem;color:var(--text-muted)">Checking API limits...</div>
        </div>
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
    
    // Fetch API limits
    const limits = await api.getLimits().catch(() => null);
    if (limits) window.renderApiLimits(limits);
  } catch (e) {
    const tb = $("alerts-grid");
    if (tb) tb.innerHTML = `<div style="color:var(--critical);padding:20px;grid-column:1/-1">Error: ${e.message}</div>`;
  }
}

window.renderApiLimits = function(limits) {
  const tracker = $("api-limit-tracker");
  if (!tracker) return;
  const currentProvider = state.selectedProvider || "mistral";
  const limitData = limits[currentProvider];
  if (!limitData) return;

  const isReached = limitData.status === "reached";
  const isError = limitData.status === "error";
  const isMissing = limitData.status === "missing";

  let statusHtml = "";
  if (isReached) {
    statusHtml = `<span style="color:#ef4444;font-weight:700;display:flex;align-items:center;gap:4px">⚠️ API Limit Reached (429)</span>`;
  } else if (isMissing) {
    statusHtml = `<span style="color:#f97316;font-weight:600">No API Key Configured</span>`;
  } else if (isError) {
    statusHtml = `<span style="color:#ef4444;font-weight:600">API Error</span>`;
  } else {
    statusHtml = `<span style="color:#10b981;font-weight:600;display:flex;align-items:center;gap:4px">✓ Quota Available</span>`;
  }

  tracker.innerHTML = `
    <div style="font-size:0.75rem;color:var(--text-secondary);margin-right:8px"><strong>${limitData.provider}</strong> limit status:</div>
    ${statusHtml}
  `;
};

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

// ── Provider Selection ────────────────────────────────────────────────────────
window.setProvider = function(provider) {
  state.selectedProvider = provider;
  // Re-render the alerts page so the toggle reflects immediately
  if (state.page === "alerts") renderAlerts();
  toast(`LLM provider switched to ${ provider === "groq" ? "⚡ Groq (gpt-oss-120b)" : "✦ Mistral (open-mistral-7b)"}`, "info");
};

// ── Department Agent Streaming ────────────────────────────────────────────────
window.runAgentStreaming = function(alertId) {
  if (state.activeStreams[alertId]) return;
  const provider = state.selectedProvider || "mistral";
  openStreamingDrawer(alertId, `Agent Run <span style="font-size:0.72rem;opacity:.8">[${provider === "groq" ? "⚡ Groq" : "✦ Mistral"}]</span>`, "#6366f1");
  const start = Date.now();
  const es = api.streamAgent(
    alertId,
    (ev) => appendStreamStep(alertId, ev, start),
    (ev) => { delete state.activeStreams[alertId]; finalizeStreamDrawer(alertId, ev, start); loadAlerts(); loadGlobal(); renderSidebar(); },
    (msg) => { delete state.activeStreams[alertId]; renderSidebar(); toast(`Agent error: ${msg}`, "error"); },
    provider,
  );
  state.activeStreams[alertId] = es;
  renderSidebar();
  toast(`Agent streaming for Alert #${alertId} via ${provider === "groq" ? "⚡ Groq" : "✦ Mistral"}`, "info");
};

// ── Supervisor Orchestration Streaming ────────────────────────────────────────
window.runSupervisor = function(alertId) {
  if (state.activeSupervisor) { toast("An orchestration is already running", "warning"); return; }
  const provider = state.selectedProvider || "mistral";
  state.activeSupervisor = { alertId, startTime: Date.now() };
  openStreamingDrawer(alertId, `🔀 Supervisor Orchestration <span style="font-size:0.72rem;opacity:.8">[${provider === "groq" ? "⚡ Groq" : "✦ Mistral"}]</span>`, "#8b5cf6");
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
    },
    provider,
  );
  // Store in activeStreams too for sidebar count
  state.activeStreams[`supervisor-${alertId}`] = es;
  renderAlertsGrid();
  renderSidebar();
  toast(`Supervisor orchestrating Alert #${alertId} via ${provider === "groq" ? "⚡ Groq" : "✦ Mistral"}…`, "info");
};

// ── Streaming Drawer ──────────────────────────────────────────────────────────
function openStreamingDrawer(alertId, title, accentColor) {
  const dc = $("drawer-container");
  dc.innerHTML = `
    <div class="drawer-backdrop" onclick="window.closeDrawer()"></div>
    <div class="drawer" style="background: rgba(255, 255, 255, 0.75); backdrop-filter: blur(24px); border-left: 1px solid rgba(255,255,255,0.4); box-shadow: -10px 0 40px rgba(0,0,0,0.1);">
      <div class="drawer-header" style="background: linear-gradient(135deg, ${accentColor}15, transparent); border-bottom: 1px solid rgba(255,255,255,0.3); padding: 24px;">
        <div>
          <div style="font-weight:800; font-size:1.2rem; color: #0f172a; letter-spacing: -0.02em;">${title}</div>
          <div style="font-size:0.75rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 6px; font-weight: 600;">Alert #${alertId} · Live Stream</div>
        </div>
        <button class="close-btn" style="background: white; border-radius: 50%; box-shadow: 0 4px 12px rgba(0,0,0,0.05); width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;" onclick="window.closeDrawer()">✕</button>
      </div>
      <div style="padding:16px 24px; background:linear-gradient(90deg,${accentColor}11,transparent); border-bottom:1px solid rgba(255,255,255,0.5); display:flex; align-items:center; gap:12px; box-shadow: inset 0 -2px 10px rgba(0,0,0,0.01);">
        <div style="width:10px;height:10px;border-radius:50%;background:#22c55e;animation:pulse 1s infinite;box-shadow: 0 0 10px #22c55e;"></div>
        <div style="font-size:0.85rem;font-weight:600;color:#334155;" id="stream-status-${alertId}">Initialising connection…</div>
        <div style="margin-left:auto;font-size:0.8rem;color:var(--text-muted);font-family:'Fira Code', monospace;" id="stream-timer-${alertId}">0s</div>
      </div>
      <div class="drawer-body" style="padding:24px" id="stream-steps-${alertId}"></div>
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
  step.style.cssText = `position: relative; padding-left: 28px; margin-bottom: 20px; animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;`;

  let body = "";
  if (event.type === "thinking") {
    body = `<div style="font-size:0.9rem;color:#475569;line-height:1.6;font-style:italic;">"${event.content}"</div>`;
  } else if (event.type === "tool_call") {
    const args = JSON.stringify(event.args||{}, null, 2);
    body = `<div style="font-size:0.85rem;font-family:'Fira Code', monospace;color:#ea580c;font-weight:700;">⚡ ${event.name}()</div>
      ${args!=="{}"?`<details style="margin-top:10px"><summary style="font-size:0.75rem;color:#64748b;cursor:pointer;user-select:none;font-weight:700;letter-spacing:0.05em;">VIEW PAYLOAD</summary>
        <pre style="font-size:0.8rem;color:#e2e8f0;background:#0f172a;padding:12px;border-radius:8px;margin-top:8px;overflow-x:auto;box-shadow:inset 0 2px 10px rgba(0,0,0,0.5);">${args}</pre>
      </details>`:""}`;
  } else if (event.type === "tool_result") {
    body = `<div style="font-size:0.8rem;color:#cbd5e1;background:#1e293b;padding:12px;border-radius:8px;font-family:'Fira Code', monospace;white-space:pre-wrap;box-shadow:inset 0 2px 10px rgba(0,0,0,0.5);">${(event.content||"").slice(0,400)}</div>`;
  } else if (event.type === "rag_ready") {
    body = `<div style="font-size:0.85rem;color:#334155;margin-top:2px"><strong style="color:#22c55e">${event.chunks}</strong> policy sections successfully retrieved.</div>`;
  } else if (event.type === "supervisor_start") {
    body = `<div style="font-size:0.85rem;color:#334155;margin-top:2px">Multi-agent orchestration workflow started for Alert #${event.alert_id}</div>`;
  }

  step.innerHTML = `
    <div style="position: absolute; left: 0; top: 4px; width: 14px; height: 14px; border-radius: 50%; background: ${meta.color}; box-shadow: 0 0 0 4px ${meta.color}33;"></div>
    <div style="position: absolute; left: 6px; top: 22px; bottom: -24px; width: 2px; background: linear-gradient(to bottom, ${meta.color}44, transparent); z-index: -1;"></div>
    
    <div style="display:flex;align-items:center;gap:8px; margin-bottom: 8px;">
      <span style="font-size:0.75rem;font-weight:800;color:${meta.color};text-transform:uppercase;letter-spacing:.1em;">${meta.icon} ${meta.label}</span>
      ${event.step?`<span style="font-size:0.7rem;color:var(--text-muted);background:white;padding:2px 8px;border-radius:100px;border:1px solid var(--border);margin-left:auto;box-shadow:0 1px 3px rgba(0,0,0,0.05);">Step ${event.step}</span>`:""}
    </div>
    
    <div style="background: rgba(255,255,255,0.7); border: 1px solid rgba(255,255,255,0.9); box-shadow: 0 4px 15px rgba(0,0,0,0.03); border-radius: 12px; padding: 16px; backdrop-filter: blur(12px);">
      ${body}
    </div>
  `;
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
    <div style="padding:24px; border-top:1px solid rgba(255,255,255,0.4); background: linear-gradient(0deg, rgba(34,197,94,0.08) 0%, transparent 100%);">
      <div style="background: white; border-radius: 16px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid rgba(255,255,255,0.8);">
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px">
          <span style="font-size:0.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:#22c55e;display:flex;align-items:center;gap:6px;"><span style="font-size:1.2rem; filter: drop-shadow(0 0 4px #22c55e);">✅</span> Success</span>
          <span style="font-size:0.75rem;color:var(--text-secondary);background:#f1f5f9;padding:4px 10px;border-radius:100px;font-weight:600;">${event.steps} steps · ${dur}s</span>
          ${event.final_status?`<span style="background:${col}15;color:${col};border:1px solid ${col}33;font-size:0.75rem;padding:4px 10px;border-radius:100px;font-weight:700;">${event.final_status}</span>`:""}
        </div>
        ${event.final_message?`<div style="font-size:0.9rem;color:#334155;line-height:1.6;margin-bottom:16px;padding:12px 16px;border-left:4px solid ${col};background:#f8fafc;border-radius:0 8px 8px 0;">${event.final_message}</div>`:""}
        
        <div style="display:flex;gap:12px;">
          ${event.run_id?`<button class="btn btn-sm" style="flex:1;background:linear-gradient(135deg,#7c3aed,#4f46e5);color:white;border:none;box-shadow:0 4px 15px rgba(124,58,237,0.3);font-weight:600;" onclick="window.showOrchTree('${event.run_id}')">🔀 View Delegation Tree</button>`:""}
          <button class="btn btn-ghost btn-sm" style="background:#f1f5f9;border:1px solid #e2e8f0;font-weight:600;" onclick="window.closeDrawer()">Close Drawer</button>
        </div>
      </div>
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
    <div style="position:fixed; top:0; left:0; width:100vw; height:100vh; display:flex; align-items:center; justify-content:center; z-index:99999; background:rgba(15,23,42,0.6); backdrop-filter:blur(8px);" onclick="window.closeDrawer()">
      <div style="background:rgba(255,255,255,0.95); backdrop-filter:blur(24px); border:1px solid rgba(255,255,255,0.8); border-radius:24px; padding:0; max-width:640px; width:95%; max-height:90vh; overflow-y:auto; box-shadow:0 30px 60px rgba(0,0,0,0.3); position:relative; animation:slideUp 0.4s cubic-bezier(0.16,1,0.3,1)" onclick="event.stopPropagation()">
        
        <!-- Premium Header -->
        <div style="background: linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%); padding: 32px 40px; color: white; position: relative; overflow: hidden;">
          <div style="position: absolute; top: -50%; right: -10%; width: 250px; height: 250px; background: radial-gradient(circle, rgba(255,255,255,0.2) 0%, transparent 70%); border-radius: 50%; pointer-events: none;"></div>
          <button onclick="window.closeDrawer()" style="position:absolute;top:24px;right:24px;background:rgba(255,255,255,0.2);border:none;cursor:pointer;font-size:1.4rem;color:white;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px); transition: background 0.2s; z-index: 10;" onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.2)'">&times;</button>
          
          <div style="font-weight:800; font-size:2rem; letter-spacing:-0.03em; margin-bottom:12px; display:flex; align-items:center; gap:16px; position:relative; z-index:1;">
            <div style="background:white; color:#7c3aed; width:48px; height:48px; border-radius:14px; display:flex; align-items:center; justify-content:center; font-size:1.6rem; box-shadow:0 8px 20px rgba(0,0,0,0.2);">🔀</div>
            Delegation Tree
          </div>
          <div style="font-size:0.9rem; opacity:0.9; font-family: 'Fira Code', monospace; position:relative; z-index:1; display:flex; align-items:center; gap:8px;">
            <span style="opacity:0.7;">RUN ID:</span> <span style="background:rgba(0,0,0,0.2); padding:4px 10px; border-radius:6px; letter-spacing:0.05em;">${runId}</span>
          </div>
        </div>

        <div class="drawer-body" id="tree-body" style="padding: 40px; background: #f8fafc;">
          <div class="flex items-center justify-center gap-3" style="color:#64748b;padding:40px 0;"><div class="spinner"></div>Building orchestration map…</div>
        </div>
      </div>
    </div>`;

  try {
    const tree = await api.getSupervisorTree(runId);
    const body = $("tree-body"); if (!body) return;

    const tasks = tree.tasks || [];
    const deptColors = { Finance:"#8b5cf6", HR:"#ec4899", Sales:"#10b981", Operations:"#ea580c" };
    const deptIcon   = { Finance:"💰", HR:"👥", Sales:"📈", Operations:"⚙️" };
    
    // Convert status to glowing badge
    const getStatusBadge = (s) => {
      if (s === "done") return `<span style="background:#22c55e15; color:#22c55e; border:1px solid #22c55e44; padding:2px 8px; border-radius:100px; font-weight:700; font-size:0.7rem; text-transform:uppercase;">✓ Complete</span>`;
      if (s === "failed") return `<span style="background:#ef444415; color:#ef4444; border:1px solid #ef444444; padding:2px 8px; border-radius:100px; font-weight:700; font-size:0.7rem; text-transform:uppercase;">❌ Failed</span>`;
      return `<span style="background:#f9731615; color:#f97316; border:1px solid #f9731644; padding:2px 8px; border-radius:100px; font-weight:700; font-size:0.7rem; text-transform:uppercase;">🔄 ${s}</span>`;
    };

    body.innerHTML = `
      <div style="position:relative;">
        <!-- Glowing Vertical Connection Line -->
        <div style="position:absolute; left: 24px; top: 20px; bottom: 40px; width: 4px; background: linear-gradient(to bottom, #7c3aed, #cbd5e1); border-radius: 10px; box-shadow: 0 0 15px rgba(124,58,237,0.3);"></div>
        
        <!-- Supervisor Node -->
        <div style="position:relative; padding-left: 64px; margin-bottom: 32px;">
          <div style="position:absolute; left: 16px; top: 16px; width: 20px; height: 20px; border-radius: 50%; background: #7c3aed; box-shadow: 0 0 0 6px rgba(124,58,237,0.2); z-index: 2;"></div>
          <div style="background: white; border: 1px solid #e2e8f0; padding: 24px; border-radius: 20px; box-shadow: 0 12px 30px rgba(0,0,0,0.04);">
            <div style="font-size: 0.8rem; font-weight: 800; text-transform: uppercase; color: #7c3aed; letter-spacing: 0.1em; margin-bottom: 8px; display:flex; align-items:center; gap:6px;">
              <span style="font-size:1.2rem;">🧠</span> Supervisor Agent
            </div>
            <div style="font-size: 1rem; color: #334155; font-weight: 500; line-height: 1.5;">Orchestration initialized. Delegating required sub-tasks across specialized departments.</div>
          </div>
        </div>

        <!-- Delegated Tasks -->
        ${tasks.length === 0
          ? `<div style="padding-left: 64px; color: #94a3b8; font-style: italic; font-size: 0.95rem;">No sub-agents delegated during this run.</div>`
          : tasks.map((t, i) => {
              const col = deptColors[t.child_dept] || "#3b82f6";
              const dicon = deptIcon[t.child_dept] || "🤖";
              return `
              <div style="position:relative; padding-left: 64px; margin-bottom: 24px; animation: slideUp 0.4s ease-out; animation-fill-mode: both; animation-delay: ${i * 0.1}s;">
                <div style="position:absolute; left: 16px; top: 20px; width: 20px; height: 20px; border-radius: 50%; background: ${col}; box-shadow: 0 0 0 6px ${col}33; z-index: 2;"></div>
                <div style="background: white; border: 1px solid ${col}44; padding: 24px; border-radius: 20px; box-shadow: 0 12px 30px rgba(0,0,0,0.04); position: relative; overflow: hidden;">
                  <div style="position:absolute; top:0; left:0; width:6px; height:100%; background:${col};"></div>
                  
                  <div style="display:flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
                    <div style="display:flex; align-items: center; gap: 12px;">
                      <div style="width: 44px; height: 44px; border-radius: 12px; background: ${col}15; display: flex; align-items: center; justify-content: center; font-size: 1.5rem;">${dicon}</div>
                      <div>
                        <div style="font-size: 1.1rem; font-weight: 800; color: #0f172a; margin-bottom: 2px;">${t.child_dept} Agent</div>
                        <div style="font-size: 0.8rem; color: #64748b; display: flex; align-items: center; gap: 8px;">
                          Alert #${t.alert_id} ${getStatusBadge(t.status)}
                        </div>
                      </div>
                    </div>
                    ${t.child_run_id ? `<div style="font-size: 0.75rem; font-family: 'Fira Code', monospace; color: #64748b; background: #f1f5f9; padding: 6px 12px; border-radius: 8px; border: 1px solid #e2e8f0;">Run: ${t.child_run_id.slice(0,8)}</div>` : ""}
                  </div>

                  ${t.result_summary ? `
                    <div style="background: #f8fafc; border-radius: 12px; padding: 16px; font-size: 0.9rem; color: #334155; border-left: 3px solid #cbd5e1; line-height: 1.6;">
                      ${t.result_summary}
                    </div>
                  ` : ""}
                </div>
              </div>`;
            }).join("")}
      </div>

      <div style="margin-top: 48px; border-top: 1px solid #e2e8f0; padding-top: 32px;">
        <div style="font-size:0.85rem;color:#475569;text-transform:uppercase;letter-spacing:.1em;font-weight:800;margin-bottom:20px; display:flex; align-items:center; gap:10px;">
          <span style="font-size: 1.3rem;">📋</span> System Raw Logs
        </div>
        <div style="background: #0f172a; border-radius: 16px; padding: 24px; max-height: 350px; overflow-y: auto; box-shadow: inset 0 4px 20px rgba(0,0,0,0.5); border: 1px solid #334155;">
          ${(tree.supervisor_logs||[]).map(l => `
            <div style="margin-bottom: 16px; border-bottom: 1px solid #1e293b; padding-bottom: 16px;">
              <div style="display:flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div style="color:#a78bfa; font-weight:700; font-size:0.85rem; font-family: 'Fira Code', monospace; background: #1e293b; padding: 4px 10px; border-radius: 6px;">> ${l.action}</div>
                <div style="font-size:0.75rem; color:#64748b; font-weight:600;">${timeAgo(l.timestamp)}</div>
              </div>
              <div style="color:#cbd5e1; font-size:0.85rem; line-height:1.6;">${(l.details||"").slice(0,500)}</div>
            </div>`).join("") || `<div style="color:#64748b; font-size:0.9rem; font-style:italic;">No raw logs available.</div>`}
        </div>
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
      <div id="approvals-list" class="approvals-grid"></div>
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
    <div class="approval-card ${isSupervisor ? 'supervisor-card' : ''}" id="approval-${ap.id}">
      <div class="approval-card-header">
        <div class="flex items-center gap-2">
          <span class="badge badge-${ap.risk_level==="Critical"?"critical":"high"}">${ap.risk_level} Risk</span>
          <span style="font-weight:600;font-size:0.9rem">${isSupervisor?"🔀 ":""}${ap.agent_name}</span>
          ${isSupervisor?`<span class="badge" style="background:rgba(139,92,246,0.15);color:#a78bfa;border-color:rgba(139,92,246,0.3)">Cross-Dept</span>`:""}
        </div>
        <span class="alert-card-age">${timeAgo(ap.created_at)}</span>
      </div>
      
      <div class="approval-card-body">
        <div class="approval-section-title">Action Requested</div>
        <div class="approval-action-text">${ap.action_requested}</div>
        
        <div class="approval-section-title mt-4">Findings</div>
        <div class="approval-findings-text">${ap.context_summary||"—"}</div>
        
        ${ap.policy_reference?`
        <div class="approval-section-title mt-4">Policy Reference</div>
        <div class="approval-policy-text">${ap.policy_reference}</div>`:""}
      </div>

      <div class="alert-card-meta mt-4 flex justify-between items-center">
        <span class="badge" style="background:var(--bg-input);color:var(--text-secondary);border:1px solid var(--border)">Alert #${ap.alert_id}</span>
      </div>

      <div class="alert-card-footer">
      ${ap.status==="pending"?`
        <div class="flex gap-2 items-center" style="width:100%;flex-wrap:wrap;">
          <input class="input" id="reason-${ap.id}" placeholder="Optional reason…" style="flex:1;min-width:140px;padding:8px 12px;font-size:0.8rem">
          <div class="flex gap-2" style="flex:1">
            <button class="btn btn-sm flex-1" style="background:#10b981;color:white;border:none" onclick="window.submitDecision(${ap.id},'approved')">✓ Approve</button>
            <button class="btn btn-sm flex-1" style="background:#ef4444;color:white;border:none" onclick="window.submitDecision(${ap.id},'rejected')">✕ Reject</button>
          </div>
        </div>`:`
        <div class="badge ${ap.status==="approved"?"badge-low":"badge-critical"}" style="font-size:0.8rem;padding:6px 14px;width:100%;justify-content:center">
          ${ap.status==="approved"?"✓ Approved":"✕ Rejected"}${ap.decided_at?` · ${timeAgo(ap.decided_at)}`:""}
        </div>`}
      </div>
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
        <table><thead><tr><th>Time</th><th>Agent</th><th>Action</th><th>Details</th><th>Alert</th><th>Run ID</th><th>Type</th></tr></thead>
        <tbody id="audit-tbody"><tr><td colspan="7"><div class="flex items-center gap-3" style="padding:24px;color:var(--text-muted)"><div class="spinner"></div>Loading…</div></td></tr></tbody>
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
      tb.innerHTML = `<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">📭</div><p>No entries found</p></div></td></tr>`;
      return;
    }
    tb.innerHTML = state.auditLogs.map(l => {
      const isSup = l.agent_name === "SupervisorAgent";
      const runIdShort = l.run_id ? l.run_id.slice(0, 8) + '…' : '—';
      return `<tr>
        <td style="white-space:nowrap;color:var(--text-secondary);font-size:0.78rem">${timeAgo(l.timestamp)}</td>
        <td style="font-size:0.82rem;font-weight:500">${isSup?"🔀 ":""}${l.agent_name||"—"}</td>
        <td><span class="tag">${l.action}</span></td>
        <td style="max-width:280px;font-size:0.8rem;color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${(l.details||"—").slice(0,100)}</td>
        <td>${l.alert_id?`<button class="btn btn-ghost btn-sm" onclick="window.openAlertDrawer(${l.alert_id})">#${l.alert_id}</button>`:"—"}</td>
        <td><span style="font-family:monospace;font-size:0.72rem;color:var(--text-muted)">${runIdShort}</span></td>
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
        activeEl.innerHTML = `<div class="obs-grid">` + runs.map(r => `
          <div class="obs-card active-run">
            <div class="obs-card-header">
              <div class="flex items-center gap-2">
                <div style="width:8px;height:8px;border-radius:50%;background:#22c55e;animation:pulse 1s infinite;flex-shrink:0"></div>
                <div class="obs-title">${r.title}</div>
              </div>
              <span class="badge badge-${severityClass(r.severity)}" style="font-size:0.65rem">${r.severity}</span>
            </div>
            <div class="obs-subtitle">${r.department} · ${r.alert_type}</div>
            <div class="flex justify-between items-center mt-4 pt-3" style="border-top:1px solid var(--border-light)">
               <span style="font-size:0.75rem;color:var(--text-muted)">started ${timeAgo(r.updated_at)}</span>
               <button class="btn btn-ghost btn-sm" onclick="window.openAlertDrawer(${r.id})">View Stream</button>
            </div>
          </div>`).join("") + `</div>`;
      }
    }

    // Supervisor history
    const supEl = $("obs-supervisor");
    if (supEl) {
      const history = historyRes.history || [];
      if (!history.length) {
        supEl.innerHTML = `<div class="empty-state" style="padding:20px 0"><div class="empty-icon">🔀</div><p>No orchestration runs yet. Click <strong>🔀 Orchestrate</strong> on a Critical alert.</p></div>`;
      } else {
        supEl.innerHTML = `<div class="obs-grid">` + history.map(h => `
          <div class="obs-card supervisor-run">
            <div class="obs-card-header">
              <div class="flex items-center gap-2">
                <span style="font-size:1rem">🔀</span>
                <div class="obs-title">Alert #${h.alert_id}</div>
              </div>
              <span style="font-size:0.72rem;color:var(--text-muted)">${timeAgo(h.created_at)}</span>
            </div>
            <div class="obs-subtitle">
              ${h.total_steps} sub-agent delegation${h.total_steps !== 1 ? 's' : ''}
              · ${h.duration_ms > 0 ? (h.duration_ms / 1000).toFixed(1) + 's' : 'in progress'}
            </div>
            <div style="font-family:monospace;font-size:0.68rem;color:var(--text-muted);margin-top:6px">${(h.run_id||'').slice(0,16)}…</div>
            <div class="flex justify-between items-center mt-4 pt-3" style="border-top:1px solid var(--border-light)">
               <span class="badge" style="background:rgba(139,92,246,0.1);color:#8b5cf6;font-size:0.65rem">SupervisorAgent</span>
               <button class="btn btn-ghost btn-sm" onclick="window.showOrchTree('${h.run_id}')">View Tree</button>
            </div>
          </div>`).join("") + `</div>`;
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

// ── Architecture & Flow Modal ────────────────────────────────────────────────
window.showArchitectureModal = function() {
  const dc = $("drawer-container");
  dc.innerHTML = `
    <div style="position:fixed; top:0; left:0; width:100vw; height:100vh; display:flex; align-items:center; justify-content:center; z-index:99999; background:rgba(15,23,42,0.7); backdrop-filter:blur(12px);" onclick="window.closeDrawer()">
      <div style="background:rgba(255,255,255,0.98); border:1px solid rgba(255,255,255,0.8); border-radius:24px; max-width:800px; width:95%; max-height:90vh; overflow-y:auto; box-shadow:0 30px 60px rgba(0,0,0,0.4); position:relative; animation:slideUp 0.4s cubic-bezier(0.16,1,0.3,1)" onclick="event.stopPropagation()">
        
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%); padding: 32px 40px; color: white; position: relative; overflow: hidden;">
          <div style="position: absolute; top: -50%; right: -10%; width: 250px; height: 250px; background: radial-gradient(circle, rgba(255,255,255,0.2) 0%, transparent 70%); border-radius: 50%; pointer-events: none;"></div>
          <button onclick="window.closeDrawer()" style="position:absolute;top:24px;right:24px;background:rgba(255,255,255,0.2);border:none;cursor:pointer;font-size:1.4rem;color:white;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px); transition: background 0.2s; z-index: 10;" onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.2)'">&times;</button>
          
          <div style="font-weight:800; font-size:2rem; letter-spacing:-0.03em; margin-bottom:8px; display:flex; align-items:center; gap:16px; position:relative; z-index:1;">
            <div style="background:white; color:#2563eb; width:48px; height:48px; border-radius:14px; display:flex; align-items:center; justify-content:center; font-size:1.6rem; box-shadow:0 8px 20px rgba(0,0,0,0.2);">🗺️</div>
            User Flow Architecture
          </div>
          <p style="font-size: 1rem; opacity: 0.9; margin: 0; position:relative; z-index:1;">Multi-Agent Orchestration & Testing Flow</p>
        </div>

        <div style="padding: 40px;">
          <h3 style="font-size: 1.2rem; font-weight: 800; color: #0f172a; margin-bottom: 24px; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">1. System Flow Diagram</h3>
          
          <!-- Diagram blocks -->
          <div style="display:flex; flex-direction:column; gap:12px; margin-bottom: 40px;">
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:16px; display:flex; align-items:center; gap:16px;">
              <div style="background:#3b82f6; color:white; font-weight:800; width:32px; height:32px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0;">1</div>
              <div><strong style="color:#0f172a">User Access:</strong> Logs in and views Operations Dashboard</div>
            </div>
            <div style="width:2px; height:24px; background:#cbd5e1; margin-left:32px;"></div>
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:16px; display:flex; align-items:center; gap:16px;">
              <div style="background:#3b82f6; color:white; font-weight:800; width:32px; height:32px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0;">2</div>
              <div><strong style="color:#0f172a">Alert Queue:</strong> Monitors real-time alerts across 4 departments (Finance, HR, Sales, Operations)</div>
            </div>
            <div style="width:2px; height:24px; background:#cbd5e1; margin-left:32px;"></div>
            
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap:24px;">
              <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:12px; padding:20px; transition: transform 0.2s;" onmouseover="this.style.transform='translateY(-4px)'" onmouseout="this.style.transform='none'">
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:12px;">
                  <div style="background:#3b82f6; color:white; font-weight:800; width:32px; height:32px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0;">3A</div>
                  <strong style="color:#1d4ed8; font-size:1.1rem;">Single Agent Path</strong>
                </div>
                <p style="font-size:0.9rem; color:#475569; margin:0; line-height:1.5;">Standard alerts are processed by a department-specific agent. It fetches RAG policy, calls tools, and resolves autonomously.</p>
              </div>
              
              <div style="background:#faf5ff; border:1px solid #e9d5ff; border-radius:12px; padding:20px; transition: transform 0.2s;" onmouseover="this.style.transform='translateY(-4px)'" onmouseout="this.style.transform='none'">
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:12px;">
                  <div style="background:#a855f7; color:white; font-weight:800; width:32px; height:32px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0;">3B</div>
                  <strong style="color:#7e22ce; font-size:1.1rem;">Supervisor Orchestration</strong>
                </div>
                <p style="font-size:0.9rem; color:#475569; margin:0; line-height:1.5;">Critical alerts are intercepted by the Supervisor. It breaks the alert down and delegates sub-tasks to multiple department agents simultaneously.</p>
              </div>
            </div>
          </div>

          <h3 style="font-size: 1.2rem; font-weight: 800; color: #0f172a; margin-bottom: 24px; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">2. Demonstration Test Cases</h3>
          
          <div style="display:grid; gap:16px;">
            <div style="border:1px solid #e2e8f0; border-radius:12px; padding:20px; border-left:4px solid #3b82f6; background:white; transition: box-shadow 0.2s;" onmouseover="this.style.boxShadow='0 10px 25px rgba(0,0,0,0.05)'" onmouseout="this.style.boxShadow='none'">
              <h4 style="margin:0 0 8px 0; font-size:1.05rem; color:#0f172a; display:flex; align-items:center; gap:8px;"><span>▶</span> Test Case 1: Standard Issue Resolution</h4>
              <p style="margin:0; font-size:0.9rem; color:#64748b; line-height:1.5;"><strong>Action:</strong> Click "▶ Run Agent" on any Medium/High alert.<br><strong>Expected:</strong> The live streaming drawer opens. The agent dynamically fetches SOP guidelines (RAG), plans a solution, executes tool calls, and resolves the issue.</p>
            </div>
            
            <div style="border:1px solid #e2e8f0; border-radius:12px; padding:20px; border-left:4px solid #8b5cf6; background:white; transition: box-shadow 0.2s;" onmouseover="this.style.boxShadow='0 10px 25px rgba(0,0,0,0.05)'" onmouseout="this.style.boxShadow='none'">
              <h4 style="margin:0 0 8px 0; font-size:1.05rem; color:#0f172a; display:flex; align-items:center; gap:8px;"><span>🔀</span> Test Case 2: Multi-Department Orchestration</h4>
              <p style="margin:0; font-size:0.9rem; color:#64748b; line-height:1.5;"><strong>Action:</strong> Click "🔀 Orchestrate" on a Critical alert.<br><strong>Expected:</strong> The Supervisor takes control, delegates tasks to sub-agents (e.g., HR + Finance). After completion, clicking "View Delegation Tree" renders a visual map of the entire operation and raw system logs.</p>
            </div>

            <div style="border:1px solid #e2e8f0; border-radius:12px; padding:20px; border-left:4px solid #10b981; background:white; transition: box-shadow 0.2s;" onmouseover="this.style.boxShadow='0 10px 25px rgba(0,0,0,0.05)'" onmouseout="this.style.boxShadow='none'">
              <h4 style="margin:0 0 8px 0; font-size:1.05rem; color:#0f172a; display:flex; align-items:center; gap:8px;"><span>🤖</span> Test Case 3: LLM Provider Hot-Swapping</h4>
              <p style="margin:0; font-size:0.9rem; color:#64748b; line-height:1.5;"><strong>Action:</strong> Toggle between Mistral and Groq on the Alerts page.<br><strong>Expected:</strong> The API Limit Tracker updates instantly. Subsequent agent runs explicitly use the newly selected LLM brain for reasoning, demonstrating multi-provider reliability.</p>
            </div>
          </div>

        </div>
      </div>
    </div>
  `;
};

boot();
