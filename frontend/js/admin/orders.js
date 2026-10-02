/** Admin > Orders: every customer's orders, filter by status, change status, view the lines. */

import { api } from "../api.js";
import { orderLinesTable } from "../orders.js";
import {
  capitalize,
  confirmDialog,
  dataTable,
  emptyState,
  formatDateTime,
  formatPrice,
  html,
  loadingState,
  mount,
  openDialog,
  plural,
  raw,
  renderError,
  renderPagination,
  statusBadge,
  toast,
} from "../ui.js";

const STATUSES = ["pending", "processing", "shipped", "completed", "cancelled"];
const PAGE_SIZE = 15;

const statusSelect = (order) => html`
  <label class="visually-hidden" for="order-status-${order.id}">Status of order ${order.id}</label>
  <select class="select" id="order-status-${order.id}" data-status data-current="${order.status}"
    ${order.status === "cancelled" ? raw("disabled") : ""}>
    ${STATUSES.map((status) => html`<option value="${status}" ${status === order.status ? raw("selected") : ""}>${capitalize(status)}</option>`)}
  </select>`;

const row = (order) => html`
  <tr data-id="${order.id}">
    <td><strong>#${order.id}</strong></td>
    <td>${order.user.first_name} ${order.user.last_name}<br /><span class="muted">${order.user.email}</span></td>
    <td>${formatDateTime(order.created_at)}</td>
    <td class="num">${plural(order.items.length, "item")}</td>
    <td class="num">${formatPrice(order.total_price)}</td>
    <td>${statusSelect(order)}</td>
    <td><div class="row-actions"><button type="button" class="btn btn--secondary btn--sm" data-details aria-label="View order ${order.id}">Details</button></div></td>
  </tr>`;

const detailsContent = (order) => html`
  <div class="modal__body">
    <dl class="details-list details-list--spaced">
      <dt>Customer</dt><dd>${order.user.first_name} ${order.user.last_name} (${order.user.email})</dd>
      <dt>Placed</dt><dd>${formatDateTime(order.created_at)}</dd>
      <dt>Last update</dt><dd>${formatDateTime(order.updated_at)}</dd>
      <dt>Status</dt><dd>${statusBadge(order.status)}</dd>
    </dl>
    ${orderLinesTable(order)}
  </div>
  <div class="modal__footer"><button type="button" class="btn btn--secondary" data-close>Close</button></div>`;

export function renderOrders(view) {
  let page = 1;
  let status = "";
  let orders = new Map();

  mount(
    view,
    html`<div class="admin-toolbar">
        <div class="field">
          <label for="admin-order-filter">Status</label>
          <select class="select" id="admin-order-filter">
            <option value="">All orders</option>
            ${STATUSES.map((value) => html`<option value="${value}">${capitalize(value)}</option>`)}
          </select>
        </div>
      </div>
      <div data-list></div>
      <nav class="pagination" aria-label="Orders pagination" data-pager></nav>`,
  );
  const list = view.querySelector("[data-list]");
  const pager = view.querySelector("[data-pager]");

  async function load() {
    mount(list, loadingState("Loading orders\u2026"));
    pager.innerHTML = "";
    try {
      const data = await api.get("/admin/orders", { status, page, limit: PAGE_SIZE });
      if (data.total > 0 && data.items.length === 0) {
        page = data.pages;
        return load();
      }
      orders = new Map(data.items.map((order) => [order.id, order]));
      if (data.items.length === 0) {
        mount(
          list,
          emptyState({
            title: status ? `No ${status} orders` : "No orders yet",
            message: status ? "Try another status filter." : "Orders placed by customers will appear here.",
            iconName: "clipboard",
          }),
        );
        return;
      }
      mount(
        list,
        dataTable({
          caption: "Orders",
          columns: [
            { label: "Order" },
            { label: "Customer" },
            { label: "Placed" },
            { label: "Items", className: "num" },
            { label: "Total", className: "num" },
            { label: "Status" },
            { label: raw('<span class="visually-hidden">Actions</span>') },
          ],
          rows: data.items.map(row),
        }),
      );
      renderPagination(pager, data, (nextPage) => {
        page = nextPage;
        load();
      });
    } catch (error) {
      renderError(list, error, load);
    }
  }

  async function changeStatus(select) {
    const order = orders.get(Number(select.closest("tr").dataset.id));
    const next = select.value;
    const revert = () => {
      select.value = select.dataset.current;
    };

    if (next === "cancelled") {
      const confirmed = await confirmDialog({
        title: `Cancel order #${order.id}?`,
        message: "The items go back into stock. A cancelled order is final and cannot be changed again.",
        confirmLabel: "Cancel order",
        danger: true,
      });
      if (!confirmed) return revert();
    }
    select.disabled = true;
    try {
      const updated = await api.patch(`/admin/orders/${order.id}/status`, { status: next });
      orders.set(updated.id, updated);
      select.dataset.current = updated.status;
      select.disabled = updated.status === "cancelled";
      toast(`Order #${order.id} is now ${updated.status}.`, "success");
    } catch (error) {
      revert();
      select.disabled = false;
      toast(error.message, "error");
    }
  }

  view.querySelector("#admin-order-filter").addEventListener("change", (event) => {
    status = event.target.value;
    page = 1;
    load();
  });
  list.addEventListener("change", (event) => {
    if (event.target.matches("[data-status]")) changeStatus(event.target);
  });
  list.addEventListener("click", (event) => {
    const order = orders.get(Number(event.target.closest("tr")?.dataset.id));
    if (order && event.target.closest("[data-details]")) {
      openDialog({ title: `Order #${order.id}`, content: detailsContent(order), wide: true });
    }
  });

  return load();
}
