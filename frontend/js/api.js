/**
 * The single gateway to the backend: every request in the app goes through `api`.
 *
 *   api.get("/products", { page: 2 })
 *   api.post("/cart/items", { product_id: 1, quantity: 2 })
 *   api.patch("/cart/items/5", { quantity: 3 })
 *   api.delete("/cart/items/5")
 *
 * Uses HttpOnly cookies for authentication (credentials: "include"),
 * includes double-submit CSRF protection on state-changing requests,
 * and turns every failure into an `ApiError` with a user-friendly message.
 */

import { API_BASE_URL } from "./config.js";

class ApiError extends Error {
  /**
   * @param {number} status HTTP status, or 0 when the server could not be reached
   * @param {string} message text that is safe to show to the user
   * @param {Record<string, string>} fieldErrors validation messages keyed by field name (422)
   */
  constructor(status, message, fieldErrors = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

const FALLBACK_MESSAGES = {
  400: "The request could not be processed.",
  401: "Please log in to continue.",
  403: "You do not have permission to do that.",
  404: "We could not find what you were looking for.",
  409: "That conflicts with the current state of the data.",
  429: "Too many requests. Please slow down and try again.",
};

const SERVER_ERROR_MESSAGE = "The server ran into a problem. Please try again in a moment.";

let unauthorizedHandler = null;

/** Registers the function called when an authenticated request is answered with 401. */
export function onUnauthorized(handler) {
  unauthorizedHandler = handler;
}

const humanize = (field) => field.charAt(0).toUpperCase() + field.slice(1).replaceAll("_", " ");

function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[2]) : null;
}

async function ensureCsrfToken() {
  let token = getCookie("csrf_token");
  if (!token) {
    try {
      const res = await fetch(new URL(API_BASE_URL + "/auth/csrf", window.location.href), {
        credentials: "include",
      });
      const data = await res.json().catch(() => null);
      token = data?.csrf_token || getCookie("csrf_token");
    } catch {
      // ignore
    }
  }
  return token;
}

function buildUrl(path, params) {
  const url = new URL(API_BASE_URL + path, window.location.href);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  }
  return url;
}

/** Turns FastAPI's `{detail: "..."}` / `{detail: [{loc, msg}]}` into a message and per-field errors. */
function describeFailure(status, data) {
  const detail = data?.detail;
  if (typeof detail === "string" && status < 500) {
    return { message: detail, fieldErrors: {} };
  }
  if (Array.isArray(detail)) {
    const fieldErrors = {};
    for (const problem of detail) {
      const field = problem.loc?.at(-1);
      if (typeof field === "string" && !(field in fieldErrors)) {
        fieldErrors[field] = problem.msg;
      }
    }
    const message =
      Object.entries(fieldErrors)
        .map(([field, text]) => `${humanize(field)}: ${text}`)
        .join(" \u00b7 ") || "Some of the data you entered is not valid.";
    return { message, fieldErrors };
  }
  if (status >= 500) {
    return { message: SERVER_ERROR_MESSAGE, fieldErrors: {} };
  }
  return { message: FALLBACK_MESSAGES[status] ?? `Request failed (HTTP ${status}).`, fieldErrors: {} };
}

let isRefreshing = false;
let refreshSubscribers = [];

function subscribeTokenRefresh(cb) {
  refreshSubscribers.push(cb);
}

function onRefreshed(success) {
  refreshSubscribers.forEach((cb) => cb(success));
  refreshSubscribers = [];
}

async function request(method, path, { params, body, form = false, isRetry = false } = {}) {
  const isStateChanging = ["POST", "PUT", "PATCH", "DELETE"].includes(method.toUpperCase());
  const headers = { Accept: "application/json" };

  if (isStateChanging) {
    const csrfToken = await ensureCsrfToken();
    if (csrfToken) {
      headers["X-CSRF-Token"] = csrfToken;
    }
  }

  let payload;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(body);
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      headers,
      body: payload,
      credentials: "include",
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection and try again.");
  }

  if (response.status === 401 && !isRetry && !path.startsWith("/auth/login") && !path.startsWith("/auth/refresh") && !path.startsWith("/auth/logout")) {
    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshCsrf = getCookie("csrf_token");
        const refreshHeaders = { Accept: "application/json" };
        if (refreshCsrf) refreshHeaders["X-CSRF-Token"] = refreshCsrf;
        const res = await fetch(buildUrl("/auth/refresh"), {
          method: "POST",
          headers: refreshHeaders,
          credentials: "include",
        });
        if (res.ok) {
          isRefreshing = false;
          onRefreshed(true);
          return request(method, path, { params, body, form, isRetry: true });
        }
      } catch {
        // refresh failed
      }
      isRefreshing = false;
      onRefreshed(false);
      if (unauthorizedHandler) unauthorizedHandler();
    } else {
      return new Promise((resolve, reject) => {
        subscribeTokenRefresh((success) => {
          if (success) {
            resolve(request(method, path, { params, body, form, isRetry: true }));
          } else {
            reject(new ApiError(401, FALLBACK_MESSAGES[401]));
          }
        });
      });
    }
  }

  if (response.status === 204) {
    await response.text();
    return null;
  }
  const data = await response.json().catch(() => null);
  if (response.ok) {
    return data;
  }

  const { message, fieldErrors } = describeFailure(response.status, data);
  if (response.status === 401 && unauthorizedHandler && !isRefreshing) {
    unauthorizedHandler();
  }
  throw new ApiError(response.status, message, fieldErrors);
}

export const api = {
  get: (path, params) => request("GET", path, { params }),
  /** `options.form = true` sends application/x-www-form-urlencoded (used by the OAuth2 login). */
  post: (path, body, options = {}) => request("POST", path, { body, ...options }),
  patch: (path, body) => request("PATCH", path, { body }),
  delete: (path) => request("DELETE", path),
};
