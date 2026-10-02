/**
 * Where the login session lives in the browser.
 *
 * "Remember me" ticked  -> localStorage   (survives closing the browser)
 * "Remember me" cleared -> sessionStorage (ends with the tab)
 *
 * The JWT is the only credential kept. A copy of the user's public profile is cached next to it
 * purely so the navbar can render instantly; the server stays the source of truth (every page
 * that needs the user re-reads GET /auth/me).
 */

const TOKEN_KEY = "arad.token";
const USER_KEY = "arad.user";
const FLASH_KEY = "arad.flash";

const stores = () => [window.localStorage, window.sessionStorage];

function activeStore() {
  return stores().find((store) => store.getItem(TOKEN_KEY)) ?? null;
}

export function getToken() {
  return activeStore()?.getItem(TOKEN_KEY) ?? null;
}

export function saveSession(token, remember) {
  clearSession();
  (remember ? window.localStorage : window.sessionStorage).setItem(TOKEN_KEY, token);
}

export function getStoredUser() {
  const raw = activeStore()?.getItem(USER_KEY);
  try {
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user) {
  activeStore()?.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  for (const store of stores()) {
    store.removeItem(TOKEN_KEY);
    store.removeItem(USER_KEY);
  }
}

/** A one-time message that survives a redirect (e.g. "Please log in to continue"). */
export function setFlash(message) {
  window.sessionStorage.setItem(FLASH_KEY, message);
}

export function takeFlash() {
  const message = window.sessionStorage.getItem(FLASH_KEY);
  window.sessionStorage.removeItem(FLASH_KEY);
  return message;
}
