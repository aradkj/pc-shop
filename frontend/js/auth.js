/**
 * Authentication: log in / register / log out, the "must be signed in" guard,
 * and the controllers of the login, register and profile pages.
 */

import { api } from "./api.js";
import { clearSession, getToken, saveSession, setFlash, setStoredUser } from "./session.js";
import {
  clearFormErrors,
  emptyState,
  formatDate,
  formatDateTime,
  formatPrice,
  html,
  loadingState,
  mount,
  plural,
  readQuery,
  renderError,
  safeNext,
  showApiError,
  showFieldErrors,
  siteUrl,
  statusBadge,
  withBusy,
} from "./ui.js";

export const isLoggedIn = () => Boolean(getToken());

export async function login(identifier, password, remember) {
  clearSession(); // never send a stale token along with fresh credentials
  const token = await api.post("/auth/login", { username: identifier, password }, { form: true });
  saveSession(token.access_token, remember);
  const user = await api.get("/auth/me");
  setStoredUser(user);
  return user;
}

export async function register(details) {
  await api.post("/auth/register", details);
  return login(details.email, details.password, false); // sign the new customer in right away
}

export function logout() {
  clearSession();
  window.location.href = siteUrl("index.html");
}

let redirecting = false;

/**
 * Sends the visitor to the login page, which returns them here afterwards, and leaves a message for them.
 * Several failing requests can ask for this at the same moment: the first one wins, so the message is
 * always the reason that actually happened first.
 */
export function redirectToLogin(message) {
  if (redirecting) return;
  redirecting = true;
  setFlash(message);
  const here = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  window.location.href = `${siteUrl("pages/login.html")}?next=${encodeURIComponent(here)}`;
}

/**
 * Guard for pages that need a signed-in user. Returns the current user, or `null` when the
 * visitor is being sent to the login page (callers must then stop).
 * Admin pages additionally require the admin role - the API enforces it too, this only
 * decides what the page shows.
 */
export async function requireUser({ admin = false } = {}) {
  if (!isLoggedIn()) {
    redirectToLogin("Please log in to continue.");
    return null;
  }
  let user;
  try {
    user = await api.get("/auth/me");
  } catch (error) {
    if (error.status === 401) return null; // the 401 handler is already redirecting
    throw error;
  }
  setStoredUser(user);
  if (admin && user.role !== "admin") {
    mount(
      document.querySelector("#main"),
      html`<div class="container page">${emptyState({
        title: "Admins only",
        message: "Your account does not have access to the admin area.",
        action: { href: siteUrl("index.html"), label: "Back to the store" },
        iconName: "alert",
      })}</div>`,
    );
    return null;
  }
  return user;
}

// ---------------------------------------------------------------------------
// Login page
// ---------------------------------------------------------------------------

export function initLoginPage() {
  const form = document.querySelector("#login-form");
  const next = safeNext(readQuery().next, siteUrl("index.html"));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearFormErrors(form);
    const data = new FormData(form);
    try {
      await withBusy(form.querySelector("[type=submit]"), () =>
        login(data.get("identifier").trim(), data.get("password"), data.get("remember") === "on"),
      );
      window.location.href = next;
    } catch (error) {
      showApiError(form, error);
    }
  });
}

// ---------------------------------------------------------------------------
// Register page
// ---------------------------------------------------------------------------

export function initRegisterPage() {
  const form = document.querySelector("#register-form");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearFormErrors(form);
    const data = Object.fromEntries(new FormData(form));

    if (data.password !== data.confirm_password) {
      showFieldErrors(form, { confirm_password: "The passwords do not match." });
      return;
    }
    const details = {
      email: data.email.trim(),
      username: data.username.trim(),
      password: data.password,
      first_name: data.first_name.trim(),
      last_name: data.last_name.trim(),
    };
    try {
      await withBusy(form.querySelector("[type=submit]"), () => register(details));
      window.location.href = siteUrl("index.html");
    } catch (error) {
      if (error.status === 409) {
        // The API names the clashing value ("Email is already registered"): show it under that field.
        const field = /email/i.test(error.message) ? "email" : "username";
        showFieldErrors(form, { [field]: error.message });
      } else {
        showApiError(form, error);
      }
    }
  });
}

// ---------------------------------------------------------------------------
// Profile page
// ---------------------------------------------------------------------------

export async function initProfilePage() {
  const user = await requireUser();
  if (!user) return;

  const account = document.querySelector("#profile-account");
  const recent = document.querySelector("#profile-orders");

  mount(
    account,
    html`<dl class="details-list">
      <dt>Name</dt><dd>${user.first_name} ${user.last_name}</dd>
      <dt>Email</dt><dd>${user.email}</dd>
      <dt>Username</dt><dd>${user.username}</dd>
      <dt>Account type</dt><dd><span class="badge badge--plain ${user.role === "admin" ? "badge--accent" : ""}">${user.role}</span></dd>
      <dt>Member since</dt><dd>${formatDate(user.created_at)}</dd>
    </dl>`,
  );

  const loadOrders = async () => {
    mount(recent, loadingState("Loading your orders\u2026"));
    try {
      const { items, total } = await api.get("/orders", { limit: 3 });
      if (items.length === 0) {
        mount(
          recent,
          emptyState({
            title: "No orders yet",
            message: "When you place an order it will show up here.",
            action: { href: siteUrl("pages/products.html"), label: "Start shopping" },
          }),
        );
        return;
      }
      mount(
        recent,
        html`<p class="muted">You have placed ${plural(total, "order")} in total.</p>
          <ul class="order-list">
            ${items.map(
              (order) => html`<li class="panel">
                <a href="${siteUrl("pages/orders.html")}?highlight=${order.id}"><strong>Order #${order.id}</strong></a>
                ${statusBadge(order.status)}
                <p class="muted order-meta">${formatDateTime(order.created_at)} \u00b7 ${plural(order.items.length, "item")} \u00b7 ${formatPrice(order.total_price)}</p>
              </li>`,
            )}
          </ul>
          <p class="section-actions"><a class="btn btn--secondary" href="${siteUrl("pages/orders.html")}">View all orders</a></p>`,
      );
    } catch (error) {
      renderError(recent, error, loadOrders);
    }
  };
  loadOrders();
}
