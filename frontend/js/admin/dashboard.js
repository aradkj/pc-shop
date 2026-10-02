/** Admin dashboard: headline numbers from GET /admin/stats and the latest orders. */

import { api } from "../api.js";
import {
  dataTable,
  emptyState,
  formatDateTime,
  formatPrice,
  html,
  icon,
  loadingState,
  mount,
  plural,
  renderError,
  statusBadge,
} from "../ui.js";

const statCard = (label, value, iconName) => html`
  <div class="stat-card">
    <p class="stat-card__label">${label} ${icon(iconName)}</p>
    <p class="stat-card__value">${value}</p>
  </div>`;

export async function renderDashboard(view) {
  mount(view, loadingState("Loading the dashboard\u2026"));
  try {
    const [stats, recent] = await Promise.all([api.get("/admin/stats"), api.get("/admin/orders", { limit: 5 })]);
    mount(
      view,
      html`
        <div class="stat-grid" role="group" aria-label="Store statistics">
          ${statCard("Products", stats.total_products, "box")}
          ${statCard("Orders", stats.total_orders, "clipboard")}
          ${statCard("Users", stats.total_users, "users")}
          ${statCard("Pending orders", stats.pending_orders, "clock")}
        </div>
        <div class="section__header">
          <h2>Recent orders</h2>
          <a href="#orders">View all orders</a>
        </div>
        ${recent.items.length === 0
          ? emptyState({ title: "No orders yet", message: "Orders placed by customers will appear here.", iconName: "clipboard" })
          : dataTable({
              caption: "Most recent orders",
              columns: [
                { label: "Order" },
                { label: "Customer" },
                { label: "Placed" },
                { label: "Items", className: "num" },
                { label: "Total", className: "num" },
                { label: "Status" },
              ],
              rows: recent.items.map(
                (order) => html`<tr>
                  <td><strong>#${order.id}</strong></td>
                  <td>${order.user.first_name} ${order.user.last_name}<br /><span class="muted">${order.user.email}</span></td>
                  <td>${formatDateTime(order.created_at)}</td>
                  <td class="num">${plural(order.items.length, "item")}</td>
                  <td class="num">${formatPrice(order.total_price)}</td>
                  <td>${statusBadge(order.status)}</td>
                </tr>`,
              ),
            })}`,
    );
  } catch (error) {
    renderError(view, error, () => renderDashboard(view));
  }
}
