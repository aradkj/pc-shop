/**
 * Where non-sensitive session data (like cached user profile for UI) lives in the browser.
 * Authentication tokens (access_token, refresh_token) are HttpOnly cookies handled by the browser,
 * NEVER stored in localStorage or sessionStorage.
 */

const USER_KEY = "arad.user";
const FLASH_KEY = "arad.flash";

const stores = () => [window.localStorage, window.sessionStorage];

export function isLoggedIn() {
  return Boolean(getStoredUser());
}

export function getStoredUser() {
  for (const store of stores()) {
    const raw = store.getItem(USER_KEY);
    if (raw) {
      try {
        return JSON.parse(raw);
      } catch {
        // invalid JSON
      }
    }
  }
  return null;
}

export function setStoredUser(user, remember = false) {
  clearSession();
  if (user) {
    const store = remember ? window.localStorage : window.sessionStorage;
    store.setItem(USER_KEY, JSON.stringify(user));
  }
}

export function clearSession() {
  for (const store of stores()) {
    store.removeItem(USER_KEY);
    store.removeItem("arad.token"); // ensure legacy key is wiped
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
