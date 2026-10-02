/**
 * The single gateway to the backend: every request in the app goes through `api`.
 *
 *   api.get("/products", { page: 2 })
 *   api.post("/cart/items", { product_id: 1, quantity: 2 })
 *   api.patch("/cart/items/5", { quantity: 3 })
 *   api.delete("/cart/items/5")
 *
 * It adds the Bearer token, turns every failure into an `ApiError` with a message that is
 * safe to show to the user, and reports 401s on authenticated requests to one handler.
 */

import { API_BASE_URL } from "./config.js";
import { getToken } from "./session.js";

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

async function request(method, path, { params, body, form = false } = {}) {
  const headers = { Accept: "application/json" };
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
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
    response = await fetch(buildUrl(path, params), { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection and try again.");
  }

  if (response.status === 204) {
    await response.text(); // empty, but reading it lets the browser finish the request (otherwise DevTools shows it as cancelled)
    return null;
  }
  const data = await response.json().catch(() => null);
  if (response.ok) {
    return data;
  }

  const { message, fieldErrors } = describeFailure(response.status, data);
  if (response.status === 401 && token && unauthorizedHandler) {
    unauthorizedHandler(); // the stored token is no longer valid
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
