/** Admin > Products: list (including hidden ones), search, create, edit and delete. */

import { api } from "../api.js";
import {
  clearFormErrors,
  confirmDialog,
  dataTable,
  debounce,
  emptyState,
  formatPrice,
  html,
  imageUrl,
  loadingState,
  mount,
  openDialog,
  raw,
  renderError,
  renderPagination,
  showApiError,
  toast,
  withBusy,
} from "../ui.js";

const PAGE_SIZE = 10;

const row = (product) => html`
  <tr data-id="${product.id}">
    <td>
      <div class="table__product">
        <img class="thumb" src="${imageUrl(product.image_url)}" alt="" loading="lazy" />
        <div><strong>${product.name}</strong><br /><span class="table__sub">${product.slug}</span></div>
      </div>
    </td>
    <td>${product.category.name}</td>
    <td class="num">${formatPrice(product.price)}</td>
    <td class="num">${product.stock}</td>
    <td>${product.is_active
      ? html`<span class="badge badge--completed">Visible</span>`
      : html`<span class="badge badge--cancelled">Hidden</span>`}</td>
    <td>
      <div class="row-actions">
        <button type="button" class="btn btn--secondary btn--sm" data-edit aria-label="Edit ${product.name}">Edit</button>
        <button type="button" class="btn btn--danger btn--sm" data-delete aria-label="Delete ${product.name}">Delete</button>
      </div>
    </td>
  </tr>`;

const formContent = (product, categories) => html`
  <form>
    <div class="modal__body">
      <div data-form-alert role="alert" hidden></div>
      <div class="field">
        <label for="product-name">Name</label>
        <input class="input" id="product-name" name="name" required minlength="2" maxlength="200" value="${product?.name ?? ""}" />
      </div>
      <div class="field">
        <label for="product-category">Category</label>
        <select class="select" id="product-category" name="category_id" required>
          ${product ? "" : html`<option value="" disabled selected>Choose a category</option>`}
          ${categories.map(
            (category) => html`<option value="${category.id}" ${product?.category_id === category.id ? raw("selected") : ""}>${category.name}</option>`,
          )}
        </select>
      </div>
      <div class="field-row">
        <div class="field">
          <label for="product-price">Price (USD)</label>
          <input class="input" id="product-price" name="price" type="number" inputmode="decimal" min="0" step="0.01" required value="${product?.price ?? ""}" />
        </div>
        <div class="field">
          <label for="product-stock">Stock</label>
          <input class="input" id="product-stock" name="stock" type="number" inputmode="numeric" min="0" step="1" required value="${product?.stock ?? 0}" />
        </div>
      </div>
      <div class="field">
        <label for="product-brand">Brand</label>
        <input class="input" id="product-brand" name="brand" maxlength="100" value="${product?.brand ?? ""}" />
      </div>
      <div class="field">
        <label for="product-image">Image URL</label>
        <input class="input" id="product-image" name="image_url" maxlength="500" placeholder="https://example.com/photo.jpg or /img/products/name.svg" value="${product?.image_url ?? ""}" />
        <span class="field__hint">A link to an image. Leave empty to show a placeholder.</span>
      </div>
      <div class="field">
        <label for="product-description">Description</label>
        <textarea class="textarea" id="product-description" name="description" maxlength="5000">${product?.description ?? ""}</textarea>
      </div>
      <label class="check">
        <input type="checkbox" name="is_active" ${product?.is_active === false ? "" : raw("checked")} />
        Visible in the store
      </label>
    </div>
    <div class="modal__footer">
      <button type="button" class="btn btn--secondary" data-close>Cancel</button>
      <button type="submit" class="btn btn--primary">${product ? "Save changes" : "Create product"}</button>
    </div>
  </form>`;

function readForm(form) {
  const data = new FormData(form);
  const optional = (key) => data.get(key).trim() || null;
  return {
    name: data.get("name").trim(),
    category_id: Number(data.get("category_id")),
    price: data.get("price"), // sent as text so the server parses the exact decimal
    stock: Number.parseInt(data.get("stock"), 10),
    brand: optional("brand"),
    image_url: optional("image_url"),
    description: optional("description"),
    is_active: data.get("is_active") === "on",
  };
}

export function renderProducts(view) {
  let page = 1;
  let search = "";
  let products = new Map();

  mount(
    view,
    html`<div class="admin-toolbar">
        <div class="field">
          <label for="admin-product-search">Search products</label>
          <input class="input" type="search" id="admin-product-search" placeholder="Name, brand or description" />
        </div>
        <span class="admin-toolbar__spacer"></span>
        <button type="button" class="btn btn--primary" data-add>Add product</button>
      </div>
      <div data-list></div>
      <nav class="pagination" aria-label="Products pagination" data-pager></nav>`,
  );
  const list = view.querySelector("[data-list]");
  const pager = view.querySelector("[data-pager]");

  async function load() {
    mount(list, loadingState("Loading products\u2026"));
    pager.innerHTML = "";
    try {
      const data = await api.get("/admin/products", { search, page, limit: PAGE_SIZE });
      if (data.total > 0 && data.items.length === 0) {
        page = data.pages; // the last item of the last page was just deleted
        return load();
      }
      products = new Map(data.items.map((product) => [product.id, product]));
      if (data.items.length === 0) {
        mount(
          list,
          emptyState({
            title: search ? "No products match your search" : "There are no products yet",
            message: search ? "Try a different search term." : "Use \u201cAdd product\u201d to create the first one.",
          }),
        );
        return;
      }
      mount(
        list,
        dataTable({
          caption: "Products",
          columns: [
            { label: "Product" },
            { label: "Category" },
            { label: "Price", className: "num" },
            { label: "Stock", className: "num" },
            { label: "Visibility" },
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

  async function openForm(product = null) {
    let categories;
    try {
      categories = await api.get("/categories");
    } catch (error) {
      toast(error.message, "error");
      return;
    }
    if (categories.length === 0) {
      toast("Create a category first: every product belongs to one.", "error");
      return;
    }
    const dialog = openDialog({ title: product ? "Edit product" : "Add product", content: formContent(product, categories) });
    const form = dialog.querySelector("form");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      clearFormErrors(form);
      try {
        await withBusy(form.querySelector("[type=submit]"), () =>
          product ? api.patch(`/products/${product.id}`, readForm(form)) : api.post("/products", readForm(form)),
        );
      } catch (error) {
        showApiError(form, error);
        return;
      }
      dialog.close();
      toast(product ? "Product updated." : "Product created.", "success");
      await load();
    });
  }

  async function remove(product) {
    const confirmed = await confirmDialog({
      title: `Delete \u201c${product.name}\u201d?`,
      message:
        "This permanently removes the product. Past orders keep their lines. " +
        "To just hide it from the store, edit it and untick \u201cVisible in the store\u201d instead.",
      confirmLabel: "Delete product",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await api.delete(`/products/${product.id}`);
      toast("Product deleted.", "success");
      await load();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  view.querySelector("[data-add]").addEventListener("click", () => openForm());
  view.querySelector("#admin-product-search").addEventListener(
    "input",
    debounce((event) => {
      search = event.target.value.trim();
      page = 1;
      load();
    }),
  );
  list.addEventListener("click", (event) => {
    const product = products.get(Number(event.target.closest("tr")?.dataset.id));
    if (!product) return;
    if (event.target.closest("[data-edit]")) openForm(product);
    if (event.target.closest("[data-delete]")) remove(product);
  });

  return load();
}
