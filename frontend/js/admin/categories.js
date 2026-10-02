/** Admin > Categories: list, create, edit and delete (a category with products cannot be deleted). */

import { api } from "../api.js";
import {
  clearFormErrors,
  confirmDialog,
  dataTable,
  emptyState,
  formatDate,
  html,
  loadingState,
  mount,
  openDialog,
  raw,
  renderError,
  showApiError,
  toast,
  withBusy,
} from "../ui.js";

const row = (category) => html`
  <tr data-id="${category.id}">
    <td><strong>${category.name}</strong></td>
    <td class="mono">${category.slug}</td>
    <td>${category.description ?? html`<span class="muted">\u2014</span>`}</td>
    <td>${formatDate(category.created_at)}</td>
    <td>
      <div class="row-actions">
        <button type="button" class="btn btn--secondary btn--sm" data-edit aria-label="Edit ${category.name}">Edit</button>
        <button type="button" class="btn btn--danger btn--sm" data-delete aria-label="Delete ${category.name}">Delete</button>
      </div>
    </td>
  </tr>`;

const formContent = (category) => html`
  <form>
    <div class="modal__body">
      <div data-form-alert role="alert" hidden></div>
      <div class="field">
        <label for="category-name">Name</label>
        <input class="input" id="category-name" name="name" required minlength="2" maxlength="100" value="${category?.name ?? ""}" />
      </div>
      <div class="field">
        <label for="category-description">Description</label>
        <textarea class="textarea" id="category-description" name="description" maxlength="2000">${category?.description ?? ""}</textarea>
        <span class="field__hint">The URL slug is generated from the name.</span>
      </div>
    </div>
    <div class="modal__footer">
      <button type="button" class="btn btn--secondary" data-close>Cancel</button>
      <button type="submit" class="btn btn--primary">${category ? "Save changes" : "Create category"}</button>
    </div>
  </form>`;

export function renderCategories(view) {
  let categories = new Map();

  mount(
    view,
    html`<div class="admin-toolbar">
        <span class="admin-toolbar__spacer"></span>
        <button type="button" class="btn btn--primary" data-add>Add category</button>
      </div>
      <div data-list></div>`,
  );
  const list = view.querySelector("[data-list]");

  async function load() {
    mount(list, loadingState("Loading categories\u2026"));
    try {
      const items = await api.get("/categories");
      categories = new Map(items.map((category) => [category.id, category]));
      if (items.length === 0) {
        mount(list, emptyState({ title: "There are no categories yet", message: "Use \u201cAdd category\u201d to create the first one." }));
        return;
      }
      mount(
        list,
        dataTable({
          caption: "Categories",
          columns: [
            { label: "Name" },
            { label: "Slug" },
            { label: "Description" },
            { label: "Created" },
            { label: raw('<span class="visually-hidden">Actions</span>') },
          ],
          rows: items.map(row),
        }),
      );
    } catch (error) {
      renderError(list, error, load);
    }
  }

  function openForm(category = null) {
    const dialog = openDialog({ title: category ? "Edit category" : "Add category", content: formContent(category) });
    const form = dialog.querySelector("form");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      clearFormErrors(form);
      const data = new FormData(form);
      const payload = { name: data.get("name").trim(), description: data.get("description").trim() || null };
      try {
        await withBusy(form.querySelector("[type=submit]"), () =>
          category ? api.patch(`/categories/${category.id}`, payload) : api.post("/categories", payload),
        );
      } catch (error) {
        showApiError(form, error);
        return;
      }
      dialog.close();
      toast(category ? "Category updated." : "Category created.", "success");
      await load();
    });
  }

  async function remove(category) {
    const confirmed = await confirmDialog({
      title: `Delete \u201c${category.name}\u201d?`,
      message: "This cannot be undone. A category that still contains products cannot be deleted.",
      confirmLabel: "Delete category",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await api.delete(`/categories/${category.id}`);
      toast("Category deleted.", "success");
      await load();
    } catch (error) {
      toast(error.message, "error"); // e.g. "Cannot delete a category that still has 3 product(s)"
    }
  }

  view.querySelector("[data-add]").addEventListener("click", () => openForm());
  list.addEventListener("click", (event) => {
    const category = categories.get(Number(event.target.closest("tr")?.dataset.id));
    if (!category) return;
    if (event.target.closest("[data-edit]")) openForm(category);
    if (event.target.closest("[data-delete]")) remove(category);
  });

  return load();
}
