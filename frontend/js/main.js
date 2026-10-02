/**
 * Entry point loaded by every page.
 *
 * - renders the shared navbar and footer (so the 9 pages do not repeat them),
 * - wires the mobile menu, the account menu and the global 401 handling,
 * - starts the controller of the current page, chosen by <body data-page="...">.
 */

import { api, onUnauthorized } from "./api.js";
import { isLoggedIn, logout, redirectToLogin } from "./auth.js";
import { getCartCount, refreshCartBadge, setCartBadge } from "./cart.js";
import { clearSession, getStoredUser, setStoredUser, takeFlash } from "./session.js";
import { errorState, html, icon, mount, placeholderImage, raw, siteUrl, toast } from "./ui.js";

const PAGE = document.body.dataset.page;

const LOGO = raw(`<svg class="brand__logo" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2.2"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
  <path d="M16 2.5l11.5 6.5v14L16 29.5 4.5 23V9L16 2.5z"/><path d="M10.5 21.5L16 9.5l5.5 12M12.7 17h6.6"/></svg>`);

// Each page module is loaded only when its page is opened.
const PAGES = {
  home: async () => (await import("./products.js")).initHomePage(),
  products: async () => (await import("./products.js")).initProductsPage(),
  product: async () => (await import("./products.js")).initProductPage(),
  login: async () => (await import("./auth.js")).initLoginPage(),
  register: async () => (await import("./auth.js")).initRegisterPage(),
  profile: async () => (await import("./auth.js")).initProfilePage(),
  cart: async () => (await import("./cart.js")).initCartPage(),
  orders: async () => (await import("./orders.js")).initOrdersPage(),
  admin: async () => (await import("./admin.js")).initAdminPage(),
};

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

function navLinks(user) {
  const links = [
    { key: "home", label: "Home", href: "index.html" },
    { key: "products", label: "Shop", href: "pages/products.html" },
  ];
  if (isLoggedIn()) links.push({ key: "orders", label: "My orders", href: "pages/orders.html" });
  if (user?.role === "admin") links.push({ key: "admin", label: "Admin", href: "pages/admin.html" });
  return links;
}

function accountArea(user) {
  if (!isLoggedIn()) {
    return html`
      <a class="btn btn--ghost btn--sm" href="${siteUrl("pages/login.html")}">Log in</a>
      <a class="btn btn--primary btn--sm" href="${siteUrl("pages/register.html")}">Sign up</a>`;
  }
  const name = user?.first_name ?? "Account";
  return html`
    <details class="user-menu">
      <summary aria-label="Account menu for ${name}">
        <span class="user-menu__avatar" aria-hidden="true">${name.charAt(0).toUpperCase()}</span>
        <span class="user-menu__name">${name}</span>
      </summary>
      <div class="user-menu__list">
        ${user ? html`<p class="user-menu__email">${user.email}</p>` : ""}
        <a href="${siteUrl("pages/profile.html")}">My profile</a>
        <a href="${siteUrl("pages/orders.html")}">My orders</a>
        <button type="button" data-logout>Log out</button>
      </div>
    </details>`;
}

function renderHeader() {
  const user = isLoggedIn() ? getStoredUser() : null;
  const header = document.querySelector("#site-header");
  mount(
    header,
    html`
      <a class="skip-link" href="#main">Skip to main content</a>
      <div class="container site-header__inner">
        <a class="brand" href="${siteUrl("index.html")}" aria-label="Arad Store, home">
          ${LOGO}<span class="brand__name">ARAD<span>STORE</span></span>
        </a>
        <button type="button" class="nav-toggle" aria-expanded="false" aria-controls="site-nav" aria-label="Open menu">
          <span class="nav-toggle__bars"></span>
        </button>
        <nav class="site-nav" id="site-nav" aria-label="Main">
          <ul class="site-nav__links">
            ${navLinks(user).map(
              (link) => html`<li><a href="${siteUrl(link.href)}" ${link.key === PAGE ? raw('aria-current="page"') : ""}>${link.label}</a></li>`,
            )}
          </ul>
          <div class="site-nav__actions">
            <a class="cart-link" href="${siteUrl("pages/cart.html")}" aria-label="Cart">
              ${icon("cart")}<span class="cart-link__count" data-cart-count hidden>0</span>
            </a>
            ${accountArea(user)}
          </div>
        </nav>
      </div>`,
  );
  header.querySelector("[data-logout]")?.addEventListener("click", logout);
  header.querySelector(".nav-toggle").addEventListener("click", () => setMenuOpen(!menuIsOpen()));
  setCartBadge(getCartCount());
}

const menuIsOpen = () => document.querySelector("#site-nav").classList.contains("is-open");

function setMenuOpen(open) {
  const toggle = document.querySelector(".nav-toggle");
  document.querySelector("#site-nav").classList.toggle("is-open", open);
  toggle.setAttribute("aria-expanded", String(open));
  toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
}

/** Listeners on `document` are added once; they look the elements up when an event happens. */
function wireGlobalListeners() {
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (menuIsOpen()) {
      setMenuOpen(false);
      document.querySelector(".nav-toggle").focus();
    }
    document.querySelector(".user-menu[open]")?.removeAttribute("open");
  });

  document.addEventListener("click", (event) => {
    const menu = document.querySelector(".user-menu[open]");
    if (menu && !menu.contains(event.target)) menu.removeAttribute("open");
    if (event.target.closest("#site-nav a")) setMenuOpen(false);
  });

  window.matchMedia("(min-width: 861px)").addEventListener("change", (event) => {
    if (event.matches) setMenuOpen(false);
  });

  // A product image that fails to load is replaced by the placeholder (error events do not bubble: capture them).
  document.addEventListener(
    "error",
    (event) => {
      const image = event.target;
      if (image instanceof HTMLImageElement && !image.dataset.fallback) {
        image.dataset.fallback = "true";
        image.src = placeholderImage();
      }
    },
    true,
  );
}

// ---------------------------------------------------------------------------
// Footer
// ---------------------------------------------------------------------------

function renderFooter() {
  mount(
    document.querySelector("#site-footer"),
    html`
      <div class="container site-footer__inner">
        <div>
          <a class="brand" href="${siteUrl("index.html")}" aria-label="Arad Store, home">${LOGO}<span class="brand__name">ARAD<span>STORE</span></span></a>
          <p class="site-footer__blurb">PC components and gaming gear: graphics cards, processors, memory, storage and accessories.</p>
        </div>
        <nav aria-label="Shop links">
          <h2>Shop</h2>
          <ul>
            <li><a href="${siteUrl("pages/products.html")}">All products</a></li>
            <li><a href="${siteUrl("pages/cart.html")}">Cart</a></li>
            <li><a href="${siteUrl("pages/orders.html")}">My orders</a></li>
          </ul>
        </nav>
        <nav aria-label="Account links">
          <h2>Account</h2>
          <ul>
            ${isLoggedIn()
              ? html`<li><a href="${siteUrl("pages/profile.html")}">My profile</a></li>`
              : html`<li><a href="${siteUrl("pages/login.html")}">Log in</a></li>
                  <li><a href="${siteUrl("pages/register.html")}">Create an account</a></li>`}
          </ul>
        </nav>
      </div>
      <div class="container site-footer__legal">
        \u00a9 ${new Date().getFullYear()} Arad Store \u00b7 A demo project: no payments are processed and nothing is shipped.
      </div>`,
  );
}

// ---------------------------------------------------------------------------
// Session handling
// ---------------------------------------------------------------------------

// An authenticated request was answered with 401: the token expired or was revoked.
onUnauthorized(() => {
  clearSession();
  if (document.body.dataset.auth) {
    redirectToLogin("Your session has expired. Please log in again.");
  } else {
    renderHeader();
    setCartBadge(0);
  }
});

/** Pages that did not already load the user (via requireUser) need it for the navbar. */
async function ensureUserForHeader() {
  if (!isLoggedIn() || getStoredUser()) return;
  try {
    setStoredUser(await api.get("/auth/me"));
    renderHeader();
  } catch {
    // A 401 is handled globally; anything else only means the navbar keeps its generic account menu.
  }
}

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

async function start() {
  wireGlobalListeners();
  renderHeader();
  renderFooter();

  const flash = takeFlash();
  if (flash) toast(flash, "info");

  ensureUserForHeader();
  refreshCartBadge();

  try {
    await PAGES[PAGE]?.();
  } catch (error) {
    console.error(error);
    mount(document.querySelector("#main"), html`<div class="container page">${errorState(error, false)}</div>`);
  }
}

start();
