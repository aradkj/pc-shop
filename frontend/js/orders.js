/**
 * "My orders": the signed-in customer's order history from GET /orders.
 * `orderLinesTable` is shared with the admin order details.
 */

import { api } from "./api.js";
import { requireUser } from "./auth.js";
import {
  dataTable,
  emptyState,
  formatDateTime,
  formatPrice,
  html,
  loadingState,
  mount,
  plural,
  readQuery,
  renderError,
  renderPagination,
  siteUrl,
  statusBadge,
  writeQuery,
} from "./ui.js";

const PAGE_SIZE = 10;

/** The lines of an order. Name and unit price are the values at purchase time. */
export function orderLinesTable(order) {
  return html`
    ${dataTable({
      caption: `Items in order ${order.id}`,
      columns: [
        { label: "Product" },
        { label: "Unit price", className: "num" },
        { label: "Qty", className: "num" },
        { label: "Subtotal", className: "num" },
      ],
      rows: order.items.map(
        (item) => html`<tr>
          <td>${
            item.product_id
              ? html`<a href="${siteUrl("pages/product.html")}?id=${item.product_id}">${item.product_name}</a>`
              : html`${item.product_name} <span class="muted">(no longer sold)</span>`
          }</td>
          <td class="num">${formatPrice(item.unit_price)}</td>
          <td class="num">${item.quantity}</td>
          <td class="num">${formatPrice(item.subtotal)}</td>
        </tr>`,
      ),
    })}
    <div class="order-card__total"><span>Total</span><span>${formatPrice(order.total_price)}</span></div>`;
}

const orderCard = (order, open) => html`
  <details class="order-card" id="order-${order.id}" ${open ? html`open` : ""}>
    <summary>
      <span class="order-card__id">Order #${order.id}<span class="order-card__date">${formatDateTime(order.created_at)}</span></span>
      ${statusBadge(order.status)}
      <span class="muted">${plural(order.items.length, "item")}</span>
      <span class="price">${formatPrice(order.total_price)}</span>
    </summary>
    <div class="order-card__body">${orderLinesTable(order)}</div>
  </details>`;

export async function initOrdersPage() {
  if (!(await requireUser())) return;
  const root = document.querySelector("#orders-root");
  const pager = document.querySelector("#pagination");
  const highlighted = Number.parseInt(readQuery().highlight, 10);

  async function load() {
    const page = Math.max(1, Number.parseInt(readQuery().page, 10) || 1);
    mount(root, loadingState("Loading your orders\u2026"));
    pager.innerHTML = "";
    try {
      const data = await api.get("/orders", { page, limit: PAGE_SIZE });
      if (data.total > 0 && data.items.length === 0) {
        writeQuery({ page: data.pages }, { replace: true });
        return load();
      }
      if (data.items.length === 0) {
        mount(
          root,
          emptyState({
            title: "You have not placed any orders yet",
            message: "Your orders and their status will appear here.",
            action: { href: siteUrl("pages/products.html"), label: "Start shopping" },
            iconName: "clipboard",
          }),
        );
        return;
      }
      mount(root, html`<div class="order-list">${data.items.map((order) => orderCard(order, order.id === highlighted))}</div>`);
      document.querySelector(`#order-${highlighted}`)?.scrollIntoView({ block: "center" });
      renderPagination(pager, data, (nextPage) => {
        writeQuery({ page: nextPage });
        load();
      });
    } catch (error) {
      renderError(root, error, load);
    }
  }

  await load();
}
