/**
 * Rendering helpers shared by every page: safe HTML templates, formatting, the
 * Loading / Empty / Error states, toasts, pagination, dialogs and form helpers.
 */

// ---------------------------------------------------------------------------
// Safe HTML templates
//
// Everything interpolated into `html` is escaped, so text that comes from the API
// (product names, descriptions, customer names...) can never inject markup.
// Nested `html` results and arrays of them are inserted as-is. `raw()` marks
// *static, trusted* markup only (icons, boolean attributes).
// ---------------------------------------------------------------------------

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ESCAPES[char]);

class SafeHtml {
  constructor(markup) {
    this.markup = markup;
  }
}

export const raw = (markup) => new SafeHtml(markup);

function toMarkup(value) {
  if (value instanceof SafeHtml) return value.markup;
  if (Array.isArray(value)) return value.map(toMarkup).join("");
  if (value === null || value === undefined || value === false) return "";
  return escapeHtml(value);
}

export function html(strings, ...values) {
  return new SafeHtml(strings.reduce((markup, text, index) => markup + toMarkup(values[index - 1]) + text));
}

export function mount(target, content) {
  target.innerHTML = toMarkup(content);
}

// ---------------------------------------------------------------------------
// Site paths and images
// ---------------------------------------------------------------------------

/** Every page declares where the site root is: <body data-root="../">. */
export const siteUrl = (path = "") => `${document.body.dataset.root ?? "./"}${path}`;

export const placeholderImage = () => siteUrl("img/placeholder.svg");

/** Product images are URLs: absolute ones are used as they are, "/img/..." paths are served by this site. */
export function imageUrl(url) {
  if (!url) return placeholderImage();
  if (/^https?:\/\//i.test(url)) return url;
  return siteUrl(url.replace(/^\/+/, ""));
}

/** Only allow redirects to paths on this site (prevents open redirects through ?next=). */
export function safeNext(candidate, fallback) {
  const isLocalPath = typeof candidate === "string" && /^\/(?![/\\])/.test(candidate);
  return isLocalPath ? candidate : fallback;
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const dateTime = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" });
const dateOnly = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" });

export const formatPrice = (amount) => currency.format(Number(amount));
export const formatDateTime = (iso) => dateTime.format(new Date(iso));
export const formatDate = (iso) => dateOnly.format(new Date(iso));
export const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);
export const plural = (count, word) => `${count} ${word}${count === 1 ? "" : "s"}`;

export function statusBadge(status) {
  return html`<span class="badge badge--${status}">${capitalize(status)}</span>`;
}

export function stockInfo(product) {
  if (!product.is_active) return { label: "Unavailable", className: "stock--out" };
  if (product.stock <= 0) return { label: "Out of stock", className: "stock--out" };
  if (product.stock <= 5) return { label: `Only ${product.stock} left`, className: "stock--low" };
  return { label: "In stock", className: "stock--in" };
}

// ---------------------------------------------------------------------------
// Icons (24x24 line icons; decorative, so hidden from assistive technology)
// ---------------------------------------------------------------------------

const ICON_PATHS = {
  cart: '<circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M2 3h3l2.7 12.4a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6"/>',
  box: '<path d="M21 8l-9-5-9 5v8l9 5 9-5V8z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
  alert: '<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  check: '<circle cx="12" cy="12" r="10"/><path d="M8 12.5l3 3 5-6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
  clipboard: '<path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  gpu: '<rect x="2" y="6" width="20" height="11" rx="2"/><circle cx="8" cy="11.5" r="2.8"/><circle cx="16" cy="11.5" r="2.8"/><path d="M5 17v2M9 17v2"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="1.5"/><rect x="9.5" y="9.5" width="5" height="5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  memory: '<rect x="2" y="6" width="20" height="9" rx="1.5"/><path d="M6 9.5v2.5M10 9.5v2.5M14 9.5v2.5M18 9.5v2.5M5 15v3M9 15v3M13 15v3M17 15v3"/>',
  storage: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 12h18M7 15.5h.01M11 15.5h6"/>',
  mouse: '<rect x="6" y="2" width="12" height="20" rx="6"/><path d="M12 2v7M6 9h12"/>',
  tag: '<path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.2"/>',
};

export function icon(name, className = "") {
  const paths = ICON_PATHS[name] ?? ICON_PATHS.box;
  return raw(
    `<svg class="${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ` +
      `stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${paths}</svg>`,
  );
}

// ---------------------------------------------------------------------------
// Loading / Empty / Error states
// ---------------------------------------------------------------------------

export const loadingState = (label = "Loading\u2026") => html`
  <div class="state" role="status" aria-live="polite">
    <div class="spinner" aria-hidden="true"></div>
    <p>${label}</p>
  </div>`;

export function emptyState({ title, message, action = null, iconName = "box" }) {
  return html`
    <div class="state">
      ${icon(iconName, "state__icon")}
      <h2>${title}</h2>
      <p>${message}</p>
      ${action ? html`<a class="btn btn--primary" href="${action.href}">${action.label}</a>` : ""}
    </div>`;
}

export const errorState = (error, canRetry = true) => html`
  <div class="state state--error" role="alert">
    ${icon("alert", "state__icon")}
    <h2>Something went wrong</h2>
    <p>${error?.message ?? "An unexpected error occurred."}</p>
    ${canRetry ? html`<button type="button" class="btn btn--secondary" data-retry>Try again</button>` : ""}
  </div>`;

/** Shows the error state in `target`; the "Try again" button runs `retry`. */
export function renderError(target, error, retry) {
  mount(target, errorState(error, Boolean(retry)));
  target.querySelector("[data-retry]")?.addEventListener("click", retry);
}

export const skeletonGrid = (count = 8) => html`
  <div class="product-grid" role="status" aria-label="Loading products">
    ${Array.from({ length: count }, () => html`
      <div class="skeleton-card" aria-hidden="true">
        <div class="skeleton skeleton-card__media"></div>
        <div class="skeleton-card__body">
          <div class="skeleton skeleton-line skeleton-line--short"></div>
          <div class="skeleton skeleton-line"></div>
          <div class="skeleton skeleton-line skeleton-line--short"></div>
        </div>
      </div>`)}
  </div>`;

// ---------------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------------

/**
 * A responsive data table. `columns` is [{ label, className? }]; `rows` are `<tr>` templates.
 * The caption is for screen readers; every header cell has scope="col". The wrapper scrolls
 * sideways on small screens, so it is a labelled, focusable region (keyboard users can scroll it).
 */
export const dataTable = ({ caption, columns, rows }) => html`
  <div class="table-wrap" role="region" aria-label="${caption}" tabindex="0">
    <table class="table">
      <caption class="visually-hidden">${caption}</caption>
      <thead><tr>${columns.map((column) => html`<th scope="col" class="${column.className ?? ""}">${column.label}</th>`)}</tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;

// ---------------------------------------------------------------------------
// Toasts
// ---------------------------------------------------------------------------

const TOAST_LIFETIME_MS = 5000;

function toastRegion() {
  let region = document.querySelector(".toast-region");
  if (!region) {
    region = document.createElement("div");
    region.className = "toast-region";
    region.setAttribute("aria-live", "polite");
    document.body.append(region);
  }
  return region;
}

/** @param {"success" | "error" | "info"} type */
export function toast(message, type = "info") {
  const element = document.createElement("div");
  element.className = `toast toast--${type}`;
  element.setAttribute("role", type === "error" ? "alert" : "status");
  mount(
    element,
    html`<span class="toast__message">${message}</span>
      <button type="button" class="toast__close" aria-label="Dismiss notification">&times;</button>`,
  );
  const dismiss = () => element.remove();
  element.querySelector(".toast__close").addEventListener("click", dismiss);
  toastRegion().append(element);
  setTimeout(dismiss, TOAST_LIFETIME_MS);
}

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

/** Page numbers to show: always the first, last and the neighbours of the current page. */
function pageWindow(page, pages) {
  const wanted = new Set([1, pages, page - 1, page, page + 1]);
  const numbers = [...wanted].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b);
  const items = [];
  numbers.forEach((n, index) => {
    if (index > 0 && n - numbers[index - 1] > 1) items.push("gap");
    items.push(n);
  });
  return items;
}

export function renderPagination(target, { page, pages }, onChange) {
  if (pages <= 1) {
    target.innerHTML = "";
    return;
  }
  const button = (label, targetPage, ariaLabel, { disabled = false, current = false } = {}) => html`
    <li>
      <button type="button" class="pagination__btn" data-page="${targetPage}" aria-label="${ariaLabel}"
        ${disabled ? raw("disabled") : ""} ${current ? raw('aria-current="page"') : ""}>${label}</button>
    </li>`;

  mount(
    target,
    html`<ul>
      ${button("\u2039 Prev", page - 1, "Previous page", { disabled: page <= 1 })}
      ${pageWindow(page, pages).map((item) =>
        item === "gap"
          ? html`<li class="pagination__gap" aria-hidden="true">\u2026</li>`
          : button(item, item, `Page ${item}`, { current: item === page }),
      )}
      ${button("Next \u203a", page + 1, "Next page", { disabled: page >= pages })}
    </ul>`,
  );
  target.onclick = (event) => {
    const clicked = event.target.closest("[data-page]");
    if (clicked && !clicked.disabled && !clicked.hasAttribute("aria-current")) {
      onChange(Number(clicked.dataset.page));
    }
  };
}

// ---------------------------------------------------------------------------
// Dialogs (native <dialog>: focus is trapped and Escape closes it)
// ---------------------------------------------------------------------------

/** Resolves to true when the user confirms, false when they cancel or press Escape. */
export function confirmDialog({ title, message, confirmLabel = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "modal";
    dialog.setAttribute("aria-labelledby", "confirm-title");
    mount(
      dialog,
      html`<form method="dialog">
        <div class="modal__header"><h2 id="confirm-title">${title}</h2></div>
        <div class="modal__body"><p>${message}</p></div>
        <div class="modal__footer">
          <button type="submit" value="cancel" class="btn btn--secondary">Cancel</button>
          <button type="submit" value="confirm" class="btn ${danger ? "btn--danger" : "btn--primary"}">${confirmLabel}</button>
        </div>
      </form>`,
    );
    dialog.addEventListener("close", () => {
      resolve(dialog.returnValue === "confirm");
      dialog.remove();
    });
    document.body.append(dialog);
    dialog.showModal();
  });
}

let dialogCount = 0;

/**
 * Opens a modal. `content` is the markup below the title bar: a `.modal__body` and usually a
 * `.modal__footer`, optionally wrapped in a <form>. Anything with `data-close` closes it.
 * Returns the <dialog> so the caller can wire up the form inside.
 */
export function openDialog({ title, content, wide = false }) {
  const dialog = document.createElement("dialog");
  dialog.className = `modal${wide ? " modal--wide" : ""}`;
  const titleId = `dialog-title-${++dialogCount}`;
  dialog.setAttribute("aria-labelledby", titleId);
  mount(
    dialog,
    html`<div class="modal__header">
        <h2 id="${titleId}">${title}</h2>
        <button type="button" class="modal__close" data-close aria-label="Close dialog">&times;</button>
      </div>
      ${content}`,
  );
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog || event.target.closest("[data-close]")) dialog.close(); // backdrop or close button
  });
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
  return dialog;
}

// ---------------------------------------------------------------------------
// Forms and buttons
// ---------------------------------------------------------------------------

/** Disables a button and shows a spinner while `task` runs, so a double click cannot submit twice. */
export async function withBusy(button, task) {
  button.disabled = true;
  button.classList.add("is-busy");
  button.setAttribute("aria-busy", "true");
  try {
    return await task();
  } finally {
    button.disabled = false;
    button.classList.remove("is-busy");
    button.removeAttribute("aria-busy");
  }
}

export function clearFormErrors(form) {
  form.querySelectorAll(".field__error").forEach((element) => element.remove());
  form.querySelectorAll("[aria-invalid]").forEach((input) => {
    input.removeAttribute("aria-invalid");
    input.removeAttribute("aria-describedby");
  });
  const alert = form.querySelector("[data-form-alert]");
  if (alert) {
    alert.hidden = true;
    alert.textContent = "";
  }
}

/** Shows `errors` ({fieldName: message}) under the matching inputs. Returns the messages nobody claimed. */
export function showFieldErrors(form, errors) {
  const unclaimed = [];
  for (const [name, message] of Object.entries(errors)) {
    const input = form.elements.namedItem(name);
    if (!input || input instanceof RadioNodeList) {
      unclaimed.push(message);
      continue;
    }
    const error = document.createElement("p");
    error.className = "field__error";
    error.id = `${form.id || "form"}-${name}-error`;
    error.textContent = message;
    input.setAttribute("aria-invalid", "true");
    input.setAttribute("aria-describedby", error.id);
    input.closest(".field")?.append(error);
  }
  form.querySelector("[aria-invalid]")?.focus();
  return unclaimed;
}

function showFormAlert(form, message, type = "error") {
  const alert = form.querySelector("[data-form-alert]");
  alert.className = `alert alert--${type}`;
  alert.textContent = message;
  alert.hidden = false;
}

/** Puts an API failure on the form: per-field messages where possible, otherwise one alert. */
export function showApiError(form, error) {
  const unclaimed = showFieldErrors(form, error.fieldErrors ?? {});
  const leftover = Object.keys(error.fieldErrors ?? {}).length === 0 ? error.message : unclaimed.join(" ");
  if (leftover) showFormAlert(form, leftover);
}

// ---------------------------------------------------------------------------
// Misc
// ---------------------------------------------------------------------------

export function debounce(callback, delay = 350) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => callback(...args), delay);
  };
}

export const readQuery = () => Object.fromEntries(new URLSearchParams(window.location.search));

/** Writes non-empty values to the address bar (without a reload) so filtered views can be shared. */
export function writeQuery(values, { replace = false } = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, value);
  }
  const query = params.toString();
  const url = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
  window.history[replace ? "replaceState" : "pushState"](null, "", url);
}
