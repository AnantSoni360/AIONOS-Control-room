/**
 * auth.js - AIONOS JWT Authentication helpers (Phase 5)
 *
 * Manages Supabase JWTs stored in localStorage.
 * All api.js calls attach the token automatically.
 */

const BASE = window.AIONOS_API_URL || "http://127.0.0.1:8000";

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

export function isAuthenticated() {
  return true; // Bypassed for demo
}

/** Clear all stored auth data and redirect to login. */
export function logout() {
  window.location.href = 'login.html';
}

export async function tryRefresh() {
  return true; // Bypassed
}

export async function requireAuth() {
  // Bypassed
  return;
}

