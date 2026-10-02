/** Admin > Users: view accounts, search, and enable or disable them. */

import { api } from "../api.js";
import {
  confirmDialog,
  dataTable,
  debounce,
  emptyState,
  formatDate,
  html,
  loadingState,
  mount,
  raw,
  renderError,
  renderPagination,
  toast,
} from "../ui.js";

const PAGE_SIZE = 15;

export function renderUsers(view, { user: me }) {
  let page = 1;
  let search = "";
  let users = new Map();

  const row = (user) => html`
    <tr data-id="${user.id}">
      <td>${user.first_name} ${user.last_name}<br /><span class="muted">@${user.username}</span></td>
      <td>${user.email}</td>
      <td><span class="badge badge--plain ${user.role === "admin" ? "badge--accent" : ""}">${user.role}</span></td>
      <td>${user.is_active
        ? html`<span class="badge badge--completed">Active</span>`
        : html`<span class="badge badge--cancelled">Disabled</span>`}</td>
      <td>${formatDate(user.created_at)}</td>
      <td>
        <div class="row-actions">
          <button type="button" class="btn ${user.is_active ? "btn--danger" : "btn--secondary"} btn--sm" data-toggle
            ${user.id === me.id ? raw('disabled title="You cannot disable your own account"') : ""}>${user.is_active ? "Disable" : "Enable"}</button>
        </div>
      </td>
    </tr>`;

  mount(
    view,
    html`<div class="admin-toolbar">
        <div class="field">
          <label for="admin-user-search">Search users</label>
          <input class="input" type="search" id="admin-user-search" placeholder="Name, email or username" />
        </div>
      </div>
      <div data-list></div>
      <nav class="pagination" aria-label="Users pagination" data-pager></nav>`,
  );
  const list = view.querySelector("[data-list]");
  const pager = view.querySelector("[data-pager]");

  async function load() {
    mount(list, loadingState("Loading users\u2026"));
    pager.innerHTML = "";
    try {
      const data = await api.get("/admin/users", { search, page, limit: PAGE_SIZE });
      if (data.total > 0 && data.items.length === 0) {
        page = data.pages;
        return load();
      }
      users = new Map(data.items.map((user) => [user.id, user]));
      if (data.items.length === 0) {
        mount(list, emptyState({ title: "No users found", message: "Try a different search term.", iconName: "users" }));
        return;
      }
      mount(
        list,
        dataTable({
          caption: "Users",
          columns: [
            { label: "Name" },
            { label: "Email" },
            { label: "Role" },
            { label: "Status" },
            { label: "Joined" },
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

  async function toggle(user) {
    if (user.is_active) {
      const confirmed = await confirmDialog({
        title: `Disable ${user.first_name} ${user.last_name}?`,
        message: "They will be signed out and will not be able to log in until you enable the account again.",
        confirmLabel: "Disable account",
        danger: true,
      });
      if (!confirmed) return;
    }
    try {
      await api.patch(`/admin/users/${user.id}`, { is_active: !user.is_active });
      toast(`Account ${user.is_active ? "disabled" : "enabled"}.`, "success");
      await load();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  view.querySelector("#admin-user-search").addEventListener(
    "input",
    debounce((event) => {
      search = event.target.value.trim();
      page = 1;
      load();
    }),
  );
  list.addEventListener("click", (event) => {
    const user = users.get(Number(event.target.closest("tr")?.dataset.id));
    if (user && event.target.closest("[data-toggle]")) toggle(user);
  });

  return load();
}
