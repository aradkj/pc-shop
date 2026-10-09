/** Admin > Audit Logs: view administrative actions across products, orders, and users. */

import { api } from "../api.js";
import {
  dataTable,
  emptyState,
  formatDateTime,
  html,
  loadingState,
  mount,
  renderError,
  renderPagination,
} from "../ui.js";

const PAGE_SIZE = 15;

const ACTIONS = [
  "PRODUCT_CREATED",
  "PRODUCT_UPDATED",
  "PRODUCT_DELETED",
  "ORDER_STATUS_CHANGED",
  "USER_ENABLED",
  "USER_DISABLED",
];

const ENTITY_TYPES = ["product", "order", "user"];

function formatDiff(oldVal, newVal) {
  if (!oldVal && !newVal) return "-";
  if (!oldVal) return html`<span class="muted">Created:</span> <code>${JSON.stringify(newVal)}</code>`;
  if (!newVal) return html`<span class="muted">Deleted:</span> <code>${JSON.stringify(oldVal)}</code>`;
  return html`<code>${JSON.stringify(oldVal)}</code> &rarr; <code>${JSON.stringify(newVal)}</code>`;
}

const row = (log) => html`
  <tr>
    <td>${formatDateTime(log.created_at)}</td>
    <td>Admin #${log.admin_user_id ?? "system"}</td>
    <td><span class="badge badge--plain">${log.action}</span></td>
    <td><strong>${log.entity_type}</strong></td>
    <td>#${log.entity_id ?? "-"}</td>
    <td style="max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
      ${formatDiff(log.old_value, log.new_value)}
    </td>
  </tr>`;

export function renderAuditLogs(view) {
  let page = 1;
  let action = "";
  let entity_type = "";

  mount(
    view,
    html`<div class="admin-toolbar">
        <div class="field">
          <label for="admin-audit-action">Action</label>
          <select class="select" id="admin-audit-action">
            <option value="">All actions</option>
            ${ACTIONS.map((a) => html`<option value="${a}">${a}</option>`)}
          </select>
        </div>
        <div class="field">
          <label for="admin-audit-entity">Entity</label>
          <select class="select" id="admin-audit-entity">
            <option value="">All entities</option>
            ${ENTITY_TYPES.map((e) => html`<option value="${e}">${e}</option>`)}
          </select>
        </div>
      </div>
      <div data-list></div>
      <nav class="pagination" aria-label="Audit log pagination" data-pager></nav>`,
  );

  const list = view.querySelector("[data-list]");
  const pager = view.querySelector("[data-pager]");

  async function load() {
    mount(list, loadingState("Loading audit logs\u2026"));
    pager.innerHTML = "";
    try {
      const data = await api.get("/admin/audit-logs", { action, entity_type, page, limit: PAGE_SIZE });
      if (data.items.length === 0) {
        mount(
          list,
          emptyState({
            title: "No audit logs recorded",
            message: "Administrative actions will be logged here.",
            iconName: "clipboard",
          }),
        );
        return;
      }
      mount(
        list,
        dataTable({
          caption: "Audit Logs",
          columns: [
            { label: "Timestamp" },
            { label: "Admin" },
            { label: "Action" },
            { label: "Entity" },
            { label: "Entity ID" },
            { label: "Changes" },
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

  view.querySelector("#admin-audit-action").addEventListener("change", (e) => {
    action = e.target.value;
    page = 1;
    load();
  });

  view.querySelector("#admin-audit-entity").addEventListener("change", (e) => {
    entity_type = e.target.value;
    page = 1;
    load();
  });

  return load();
}
