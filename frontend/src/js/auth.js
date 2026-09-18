/**
 * auth.js - AIONOS JWT Authentication helpers (Phase 5)
 *
 * Manages Supabase JWTs stored in localStorage.
 * All api.js calls attach the token automatically.
 */

const BASE = window.AIONOS_API_URL || "http://localhost:8000";

const TOKEN_KEY   = "aionos_token";
const REFRESH_KEY = "aionos_refresh_token";
const USER_KEY    = "aionos_user";

/** Get the stored access token (or null). */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

/** Get the stored refresh token (or null). */
export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

/** Get the stored user object (or null). */
export function getUser() {
  try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch (_) { return null; }
}

/** Check if the current token is present and not expired. */
export function isAuthenticated() {
  const token = getToken();
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.exp * 1000 > Date.now();
  } catch (_) {
    return false;
  }
}

/** Clear all stored auth data and redirect to login. */
export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
  const basePath = window.location.pathname.startsWith('/ui') ? '/ui' : '';
  window.location.href = `${basePath}/login.html`;
}

/**
 * Attempt to refresh the access token using the stored refresh token.
 * Returns true if successful, false if refresh failed (user must re-login).
 */
export async function tryRefresh() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const res = await fetch(`${BASE}/api/auth/refresh`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;

    const data = await res.json();
    localStorage.setItem(TOKEN_KEY,   data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);
    return true;
  } catch (_) {
    return false;
  }
}

/**
 * Guard function — call at the top of boot().
 * Redirects to /ui/login.html if not authenticated and refresh fails.
 */
export async function requireAuth() {
  if (isAuthenticated()) return;

  // Try silent refresh
  const refreshed = await tryRefresh();
  if (!refreshed) {
    const basePath = window.location.pathname.startsWith('/ui') ? '/ui' : '';
    window.location.href = `${basePath}/login.html`;
  }
}

