/**
 * Shopping cart: the navbar badge, "add to cart" from anywhere, and the cart + checkout page.
 * Prices, stock and totals always come from the API - the page never calculates money itself.
 */

import { api } from "./api.js";
import { isLoggedIn, requireUser, redirectToLogin } from "./auth.js";
import {
  confirmDialog,
  emptyState,
  formatPrice,
  html,
  icon,
  imageUrl,
  loadingState,
  mount,
  plural,
  raw,
  renderError,
  siteUrl,
  stockInfo,
  toast,
  withBusy,
} from "./ui.js";

const MAX_QUANTITY = 100; // mirrors the API limit per cart line

// ---------------------------------------------------------------------------
// Navbar badge and "add to cart"
// ---------------------------------------------------------------------------

let cartCount = 0; // remembered so the badge survives the navbar being re-rendered

export const getCartCount = () => cartCount;

export function setCartBadge(count) {
  cartCount = count;
  const badge = document.querySelector("[data-cart-count]");
  if (!badge) return;
  badge.textContent = count;
  badge.hidden = count === 0;
  badge.closest("a")?.setAttribute("aria-label", `Cart, ${plural(count, "item")}`);
}

/** Reads the item count from the API. The badge is a convenience, so a failure just leaves it as it was. */
export async function refreshCartBadge() {
  if (!isLoggedIn()) {
    setCartBadge(0);
    return;
  }
  try {
    const cart = await api.get("/cart");
    setCartBadge(cart.total_items);
  } catch {
    // Expired sessions are handled globally; other errors will surface on the cart page itself.
  }
}

/** Adds a product to the signed-in user's cart. Returns true on success. */
export async function addToCart(productId, quantity = 1) {
  if (!isLoggedIn()) {
    redirectToLogin("Please log in to add items to your cart.");
    return false;
  }
  try {
    await api.post("/cart/items", { product_id: productId, quantity });
    toast("Added to your cart.", "success");
    await refreshCartBadge();
    return true;
  } catch (error) {
    toast(error.message, "error");
    return false;
  }
}

// ---------------------------------------------------------------------------
// Cart page
// ---------------------------------------------------------------------------

const lineProblem = (item) => {
  if (!item.product.is_active) return "This product is no longer available. Remove it to check out.";
  if (item.quantity > item.product.stock) {
    return item.product.stock === 0 ? "Out of stock. Remove it to check out." : `Only ${item.product.stock} left in stock.`;
  }
  return null;
};

function cartItemRow(item) {
  const { product } = item;
  const problem = lineProblem(item);
  const maxQuantity = Math.max(1, Math.min(product.stock, MAX_QUANTITY));
  const stock = stockInfo(product);
  return html`
    <li class="cart-item" data-item-id="${item.id}">
      <a class="cart-item__media" data-media href="${siteUrl("pages/product.html")}?slug=${product.slug || product.id}" tabindex="-1" aria-hidden="true">
        <img class="cart-item__img" src="${imageUrl(product.image_url)}" alt="${product.name}" loading="lazy"
          decoding="async" width="160" height="160" />
      </a>
      <div>
        <h2 class="cart-item__title"><a href="${siteUrl("pages/product.html")}?slug=${product.slug || product.id}">${product.name}</a></h2>

        <p class="cart-item__unit">${formatPrice(product.price)} each \u00b7 <span class="stock ${stock.className}">${stock.label}</span></p>
        ${problem ? html`<p class="cart-item__warning" role="alert">${problem}</p>` : ""}
      </div>
      <div class="cart-item__qty qty">
        <button type="button" class="qty__btn" data-qty-step="-1" aria-label="Decrease quantity of ${product.name}" ${item.quantity <= 1 ? raw("disabled") : ""}>\u2212</button>
        <input class="qty__input" type="number" inputmode="numeric" min="1" max="${maxQuantity}" value="${item.quantity}" aria-label="Quantity of ${product.name}" data-qty-input />
        <button type="button" class="qty__btn" data-qty-step="1" aria-label="Increase quantity of ${product.name}" ${item.quantity >= maxQuantity ? raw("disabled") : ""}>+</button>
      </div>
      <div class="cart-item__total">
        <p class="cart-item__subtotal" aria-label="Line total">${formatPrice(item.subtotal)}</p>
        <button type="button" class="btn btn--ghost btn--sm" data-remove aria-label="Remove ${product.name} from cart">Remove</button>
      </div>
    </li>`;
}

function cartView(cart) {
  const blocked = cart.items.some((item) => lineProblem(item));
  return html`
    <div class="cart-layout">
      <section aria-label="Items in your cart">
        <ul class="cart-list">${cart.items.map(cartItemRow)}</ul>
        <p class="section-actions"><button type="button" class="btn btn--ghost btn--sm" data-clear>Empty cart</button></p>
      </section>
      <aside class="panel cart-summary" aria-labelledby="summary-title">
        <h2 class="panel__title" id="summary-title">Order summary</h2>
        <dl class="cart-summary__list">
          <div class="cart-summary__row"><dt>Items</dt><dd>${cart.total_items}</dd></div>
          <div class="cart-summary__row cart-summary__row--total"><dt>Total</dt><dd>${formatPrice(cart.total_price)}</dd></div>
        </dl>
        <button type="button" class="btn btn--primary btn--block" data-checkout ${blocked ? raw("disabled") : ""}>Place order</button>
        <p class="muted note">
          This is a demo store: no payment is taken. Stock is reserved when you place the order.
        </p>
      </aside>
    </div>`;
}

const confirmationView = (order) => html`
  <div class="confirmation" role="status">
    ${icon("check", "confirmation__icon")}
    <h2>Thank you! Order #${order.id} is placed.</h2>
    <p>${plural(order.items.length, "item")} \u00b7 total ${formatPrice(order.total_price)} \u00b7 status: ${order.status}</p>
    <div class="confirmation__actions">
      <a class="btn btn--primary" href="${siteUrl("pages/orders.html")}?highlight=${order.id}">View my orders</a>
      <a class="btn btn--secondary" href="${siteUrl("pages/products.html")}">Continue shopping</a>
    </div>
  </div>`;

export async function initCartPage() {
  if (!(await requireUser())) return;
  const root = document.querySelector("#cart-root");

  async function load({ showSpinner = true } = {}) {
    if (showSpinner) mount(root, loadingState("Loading your cart\u2026"));
    try {
      const cart = await api.get("/cart");
      setCartBadge(cart.total_items);
      if (cart.items.length === 0) {
        mount(
          root,
          emptyState({
            title: "Your cart is empty",
            message: "Find something you like and it will wait for you here.",
            action: { href: siteUrl("pages/products.html"), label: "Browse products" },
            iconName: "cart",
          }),
        );
        return;
      }
      mount(root, cartView(cart));
    } catch (error) {
      renderError(root, error, () => load());
    }
  }

  /** Runs an API change, then re-reads the cart so the page always shows the server's numbers. */
  async function change(task, successMessage) {
    try {
      await task();
      if (successMessage) toast(successMessage, "success");
    } catch (error) {
      toast(error.message, "error");
    }
    await load({ showSpinner: false });
  }

  const itemIdOf = (element) => element.closest("[data-item-id]").dataset.itemId;
  const setQuantity = (element, quantity) =>
    change(() => api.patch(`/cart/items/${itemIdOf(element)}`, { quantity }));

  root.addEventListener("click", async (event) => {
    const stepButton = event.target.closest("[data-qty-step]");
    if (stepButton) {
      const input = stepButton.closest(".qty").querySelector("[data-qty-input]");
      await setQuantity(stepButton, Number(input.value) + Number(stepButton.dataset.qtyStep));
      return;
    }

    const removeButton = event.target.closest("[data-remove]");
    if (removeButton) {
      await withBusy(removeButton, () => change(() => api.delete(`/cart/items/${itemIdOf(removeButton)}`), "Item removed."));
      return;
    }

    if (event.target.closest("[data-clear]")) {
      const confirmed = await confirmDialog({
        title: "Empty your cart?",
        message: "All items will be removed from your cart.",
        confirmLabel: "Empty cart",
        danger: true,
      });
      if (confirmed) await change(() => api.delete("/cart"), "Your cart is empty.");
      return;
    }

    const checkoutButton = event.target.closest("[data-checkout]");
    if (checkoutButton) {
      await withBusy(checkoutButton, async () => {
        try {
          const order = await api.post("/orders");
          setCartBadge(0);
          mount(root, confirmationView(order));
          root.querySelector("a")?.focus();
        } catch (error) {
          toast(error.message, "error"); // e.g. 409 "Insufficient stock for ..."
          await load({ showSpinner: false });
        }
      });
    }
  });

  root.addEventListener("change", async (event) => {
    const input = event.target.closest("[data-qty-input]");
    if (!input) return;
    const quantity = Number.parseInt(input.value, 10);
    if (Number.isNaN(quantity) || quantity < 1) {
      await load({ showSpinner: false }); // put the stored quantity back
      return;
    }
    await setQuantity(input, quantity);
  });

  await load();
}
