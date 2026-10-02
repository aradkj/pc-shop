/**
 * Catalogue pages: home, product listing (search / category / price filters / pagination)
 * and product detail. All data comes from GET /products and GET /categories.
 */

import { api } from "./api.js";
import { addToCart } from "./cart.js";
import {
  emptyState,
  formatPrice,
  html,
  icon,
  imageUrl,
  loadingState,
  mount,
  raw,
  readQuery,
  renderError,
  renderPagination,
  siteUrl,
  skeletonGrid,
  stockInfo,
  toast,
  withBusy,
  writeQuery,
} from "./ui.js";

const PAGE_SIZE = 12;
const MAX_QUANTITY = 100; // mirrors the API limit per cart line

// Decorative icons for the well-known categories; any other category gets a generic tag.
const CATEGORY_ICONS = {
  "graphics-cards": "gpu",
  processors: "cpu",
  memory: "memory",
  storage: "storage",
  "gaming-accessories": "mouse",
};

const categoryIcon = (slug) => CATEGORY_ICONS[slug] ?? "tag";

// ---------------------------------------------------------------------------
// Shared pieces
// ---------------------------------------------------------------------------

function productCard(product) {
  const detailUrl = `${siteUrl("pages/product.html")}?id=${product.id}`;
  const stock = stockInfo(product);
  const unavailable = !product.is_active || product.stock <= 0;
  return html`
    <article class="product-card">
      <a class="product-card__media" href="${detailUrl}" tabindex="-1" aria-hidden="true">
        <img src="${imageUrl(product.image_url)}" alt="${product.name}" loading="lazy" />
      </a>
      <div class="product-card__body">
        <p class="product-card__meta">
          ${product.brand ? html`<span class="product-card__brand">${product.brand}</span>` : ""}
          <span>${product.category.name}</span>
        </p>
        <h3 class="product-card__title"><a href="${detailUrl}">${product.name}</a></h3>
        <p class="product-card__stock stock ${stock.className}">${stock.label}</p>
        <div class="product-card__footer">
          <span class="price">${formatPrice(product.price)}</span>
          <button type="button" class="btn btn--primary btn--sm" data-add-to-cart="${product.id}"
            aria-label="Add ${product.name} to cart" ${unavailable ? raw("disabled") : ""}>${unavailable ? "Sold out" : "Add to cart"}</button>
        </div>
      </div>
    </article>`;
}

/** One delegated listener makes every "Add to cart" button inside `container` work. */
function wireAddToCart(container) {
  container.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-add-to-cart]");
    if (button) await withBusy(button, () => addToCart(Number(button.dataset.addToCart)));
  });
}

const productGrid = (products) => html`<div class="product-grid">${products.map(productCard)}</div>`;

// ---------------------------------------------------------------------------
// Home page
// ---------------------------------------------------------------------------

export function initHomePage() {
  const categoriesRoot = document.querySelector("#home-categories");
  const productsRoot = document.querySelector("#home-products");

  async function loadCategories() {
    mount(categoriesRoot, loadingState("Loading categories\u2026"));
    try {
      const categories = await api.get("/categories");
      if (categories.length === 0) {
        mount(categoriesRoot, emptyState({ title: "No categories yet", message: "Check back soon." }));
        return;
      }
      mount(
        categoriesRoot,
        html`<div class="category-grid">
          ${categories.map(
            (category) => html`<a class="category-card" href="${siteUrl("pages/products.html")}?category=${category.slug}">
              ${icon(categoryIcon(category.slug))}
              <strong>${category.name}</strong>
              <span>${category.description ?? "Browse the range"}</span>
            </a>`,
          )}
        </div>`,
      );
    } catch (error) {
      renderError(categoriesRoot, error, loadCategories);
    }
  }

  async function loadNewArrivals() {
    mount(productsRoot, skeletonGrid(4));
    try {
      const { items } = await api.get("/products", { limit: 8, sort: "newest" });
      if (items.length === 0) {
        mount(productsRoot, emptyState({ title: "No products yet", message: "New hardware is on its way." }));
        return;
      }
      mount(productsRoot, productGrid(items));
    } catch (error) {
      renderError(productsRoot, error, loadNewArrivals);
    }
  }

  wireAddToCart(productsRoot);
  loadCategories();
  loadNewArrivals();
}

// ---------------------------------------------------------------------------
// Product listing page
// ---------------------------------------------------------------------------

export async function initProductsPage() {
  const form = document.querySelector("#filter-form");
  const results = document.querySelector("#product-results");
  const pager = document.querySelector("#pagination");
  const summary = document.querySelector("#results-summary");

  async function loadCategoryOptions() {
    try {
      const categories = await api.get("/categories");
      for (const category of categories) {
        form.elements.category.append(new Option(category.name, category.slug));
      }
    } catch {
      form.elements.category.append(new Option("Categories unavailable", "", false, false));
      form.elements.category.lastElementChild.disabled = true;
    }
  }

  const readForm = () => ({
    search: form.elements.search.value.trim(),
    category: form.elements.category.value,
    min_price: form.elements.min_price.value,
    max_price: form.elements.max_price.value,
    sort: form.elements.sort.value === "newest" ? "" : form.elements.sort.value,
  });

  function fillForm(query) {
    form.elements.search.value = query.search ?? "";
    form.elements.category.value = query.category ?? "";
    form.elements.min_price.value = query.min_price ?? "";
    form.elements.max_price.value = query.max_price ?? "";
    form.elements.sort.value = query.sort ?? "newest";
  }

  async function load() {
    const query = readQuery();
    fillForm(query);
    const page = Math.max(1, Number.parseInt(query.page, 10) || 1);

    mount(results, skeletonGrid(8));
    pager.innerHTML = "";
    summary.textContent = "Loading products\u2026";

    try {
      const data = await api.get("/products", {
        search: query.search,
        category: query.category,
        min_price: query.min_price,
        max_price: query.max_price,
        sort: query.sort,
        page,
        limit: PAGE_SIZE,
      });

      if (data.total > 0 && data.items.length === 0) {
        writeQuery({ ...query, page: data.pages }, { replace: true }); // asked for a page that does not exist
        return load();
      }
      if (data.items.length === 0) {
        summary.textContent = "No products found";
        mount(
          results,
          html`<div class="state">
            ${icon("search", "state__icon")}
            <h2>No products match your filters</h2>
            <p>Try a different search term, widen the price range or pick another category.</p>
            <button type="button" class="btn btn--secondary" data-reset>Clear filters</button>
          </div>`,
        );
        return;
      }

      const first = (data.page - 1) * data.limit + 1;
      summary.textContent = `Showing ${first}\u2013${first + data.items.length - 1} of ${data.total} products`;
      mount(results, productGrid(data.items));
      renderPagination(pager, data, (nextPage) => {
        writeQuery({ ...query, page: nextPage });
        load();
        document.querySelector("#main").scrollIntoView({ behavior: "smooth" });
      });
    } catch (error) {
      summary.textContent = "";
      renderError(results, error, load);
    }
  }

  function applyFilters(values) {
    if (values.min_price && values.max_price && Number(values.min_price) > Number(values.max_price)) {
      toast("The minimum price cannot be higher than the maximum price.", "error");
      return;
    }
    writeQuery({ ...values, page: 1 });
    load();
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    applyFilters(readForm());
  });
  form.querySelector("[data-reset]").addEventListener("click", () => applyFilters({}));
  results.addEventListener("click", (event) => {
    if (event.target.closest("[data-reset]")) applyFilters({});
  });
  window.addEventListener("popstate", load);
  wireAddToCart(results);

  await loadCategoryOptions();
  await load();
}

// ---------------------------------------------------------------------------
// Product detail page
// ---------------------------------------------------------------------------

function productView(product) {
  const stock = stockInfo(product);
  const unavailable = !product.is_active || product.stock <= 0;
  const maxQuantity = Math.max(1, Math.min(product.stock, MAX_QUANTITY));
  return html`
    <nav aria-label="Breadcrumb">
      <ol class="breadcrumb">
        <li><a href="${siteUrl("index.html")}">Home</a></li>
        <li><a href="${siteUrl("pages/products.html")}">Shop</a></li>
        <li><a href="${siteUrl("pages/products.html")}?category=${product.category.slug}">${product.category.name}</a></li>
        <li aria-current="page">${product.name}</li>
      </ol>
    </nav>
    <div class="product-detail">
      <div class="product-detail__media">
        <img src="${imageUrl(product.image_url)}" alt="${product.name}" />
      </div>
      <div>
        <div class="product-detail__meta">
          ${product.brand ? html`<span class="badge badge--accent badge--plain">${product.brand}</span>` : ""}
          <span class="badge badge--plain">${product.category.name}</span>
        </div>
        <h1>${product.name}</h1>
        <p class="product-detail__price">${formatPrice(product.price)}</p>
        <p class="stock stock--lg ${stock.className}">${stock.label}</p>
        ${product.description ? html`<p class="product-detail__description">${product.description}</p>` : ""}
        <div class="product-detail__buy">
          <div class="qty">
            <button type="button" class="qty__btn" data-qty-step="-1" aria-label="Decrease quantity" ${unavailable ? raw("disabled") : ""}>\u2212</button>
            <input class="qty__input" type="number" inputmode="numeric" min="1" max="${maxQuantity}" value="1"
              aria-label="Quantity" data-qty-input ${unavailable ? raw("disabled") : ""} />
            <button type="button" class="qty__btn" data-qty-step="1" aria-label="Increase quantity" ${unavailable ? raw("disabled") : ""}>+</button>
          </div>
          <button type="button" class="btn btn--primary" data-add ${unavailable ? raw("disabled") : ""}>${unavailable ? "Sold out" : "Add to cart"}</button>
        </div>
      </div>
    </div>`;
}

export async function initProductPage() {
  const root = document.querySelector("#product-root");
  const id = Number.parseInt(readQuery().id, 10);

  const notFound = () =>
    mount(
      root,
      emptyState({
        title: "Product not found",
        message: "This product does not exist or is no longer for sale.",
        action: { href: siteUrl("pages/products.html"), label: "Browse products" },
        iconName: "search",
      }),
    );

  async function load() {
    if (!Number.isInteger(id) || id < 1) return notFound();
    mount(root, loadingState("Loading product\u2026"));
    try {
      const product = await api.get(`/products/${id}`);
      document.title = `${product.name} \u00b7 Arad Store`;
      mount(root, productView(product));
      wireProduct(product);
    } catch (error) {
      if (error.status === 404) notFound();
      else renderError(root, error, load);
    }
  }

  function wireProduct(product) {
    const input = root.querySelector("[data-qty-input]");
    const max = Number(input.max);
    const clamp = (value) => Math.min(max, Math.max(1, Number.parseInt(value, 10) || 1));

    root.querySelectorAll("[data-qty-step]").forEach((button) =>
      button.addEventListener("click", () => {
        input.value = clamp(Number(input.value) + Number(button.dataset.qtyStep));
      }),
    );
    input.addEventListener("change", () => {
      input.value = clamp(input.value);
    });
    const addButton = root.querySelector("[data-add]");
    addButton.addEventListener("click", () => withBusy(addButton, () => addToCart(product.id, clamp(input.value))));
  }

  await load();
}
