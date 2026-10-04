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
          ${statCard("Total Orders", stats.total_orders, "clipboard")}
          ${statCard("Pending Orders", stats.pending_orders, "clock")}
          ${statCard("Processing Orders", stats.processing_orders ?? 0, "clock")}
          ${statCard("Completed Orders", stats.completed_orders ?? 0, "check")}
          ${statCard("Cancelled Orders", stats.cancelled_orders ?? 0, "alert")}
          ${statCard("Total Revenue", formatPrice(stats.total_revenue ?? 0), "tag")}
          ${statCard("Low Stock Products", stats.low_stock_products ?? 0, "box")}
          ${statCard("Total Products", stats.total_products, "box")}
          ${statCard("Total Users", stats.total_users, "users")}
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
