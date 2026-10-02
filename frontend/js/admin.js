/**
 * Admin area: one page, five sections (Dashboard, Products, Categories, Orders, Users)
 * switched through the URL hash (#products, #orders, ...) so each section can be bookmarked.
 * The API enforces the admin role on every call; this page only decides what to show.
 */

import { requireUser } from "./auth.js";
import { renderCategories } from "./admin/categories.js";
import { renderDashboard } from "./admin/dashboard.js";
import { renderOrders } from "./admin/orders.js";
import { renderProducts } from "./admin/products.js";
import { renderUsers } from "./admin/users.js";
import { html, mount } from "./ui.js";

const SECTIONS = [
  { id: "dashboard", label: "Dashboard", render: renderDashboard },
  { id: "products", label: "Products", render: renderProducts },
  { id: "categories", label: "Categories", render: renderCategories },
  { id: "orders", label: "Orders", render: renderOrders },
  { id: "users", label: "Users", render: renderUsers },
];

export async function initAdminPage() {
  const user = await requireUser({ admin: true });
  if (!user) return;

  const tabs = document.querySelector("#admin-tabs");
  const view = document.querySelector("#admin-view");

  mount(tabs, html`${SECTIONS.map((section) => html`<a href="#${section.id}" data-section="${section.id}">${section.label}</a>`)}`);

  function show() {
    const section = SECTIONS.find((candidate) => candidate.id === window.location.hash.slice(1)) ?? SECTIONS[0];
    tabs.querySelectorAll("a").forEach((link) => {
      if (link.dataset.section === section.id) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    document.title = `${section.label} \u00b7 Admin \u00b7 Arad Store`;
    // A fresh container per visit: a slow response from the previous section can only
    // write into its own (now detached) container, never into the one on screen.
    const container = document.createElement("div");
    view.replaceChildren(container);
    section.render(container, { user });
  }

  window.addEventListener("hashchange", show);
  show();
}
