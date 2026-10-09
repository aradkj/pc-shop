/**
 * Build Your Own PC configurator page.
 *
 * Provides a stepped, interactive component selection experience across
 * all 8 required core PC categories:
 * CPU, Motherboard, RAM, GPU, Storage, PSU, PC Case, Cooler.
 *
 * Real-time compatibility hints and GPU recommendations guide the customer,
 * while authoritative pricing, discount (5% on complete builds), and validation
 * are strictly computed by the PostgreSQL backend.
 */

import { api } from "./api.js";
import { isLoggedIn, redirectToLogin } from "./auth.js";
import { refreshCartBadge } from "./cart.js";
import {
  errorState,
  formatPrice,
  html,
  icon,
  imageUrl,
  loadingState,
  mount,
  openDialog,
  raw,
  renderError,
  siteUrl,
  stockInfo,
  toast,
  withBusy,
} from "./ui.js";

const DRAFT_STORAGE_KEY = "arad_pc_builder_draft";

const CATEGORIES = [
  { slug: "cpu", name: "Processor (CPU)", iconName: "cpu", hint: "Choose your central processor first" },
  { slug: "motherboard", name: "Motherboard", iconName: "motherboard", hint: "Socket and memory type match your CPU" },
  { slug: "ram", name: "Memory (RAM)", iconName: "memory", hint: "DDR4 or DDR5 matching your motherboard" },
  { slug: "gpu", name: "Graphics Card (GPU)", iconName: "gpu", hint: "Ranked recommendations based on your CPU" },
  { slug: "storage", name: "Storage (SSD)", iconName: "storage", hint: "High-speed NVMe M.2 or SATA drive" },
  { slug: "psu", name: "Power Supply (PSU)", iconName: "psu", hint: "Sufficient wattage with safety headroom" },
  { slug: "pc-case", name: "PC Case", iconName: "case", hint: "Supports your motherboard form factor" },
  { slug: "cooler", name: "CPU Cooler", iconName: "cooler", hint: "Socket-compatible air or AIO liquid cooler" },
];

export async function initPcBuilderPage() {
  const root = document.querySelector("#builder-root");
  if (!root) return;

  mount(root, loadingState("Loading PC Builder catalog…"));

  let allOptions = {};
  const selectedProducts = {
    cpu: null,
    motherboard: null,
    ram: null,
    gpu: null,
    storage: null,
    psu: null,
    "pc-case": null,
    cooler: null,
  };
  let openSlot = "cpu"; // open CPU picker first by default
  const searchQueries = {};
  let gpuRecommendations = [];
  let validationResult = {
    compatible: true,
    complete: false,
    issues: [],
    warnings: [],
    recommendations: [],
    subtotal: "0.00",
    discount_percent: "0",
    discount_amount: "0.00",
    total: "0.00",
  };

  // ---------------------------------------------------------------------------
  // Data Loading
  // ---------------------------------------------------------------------------

  async function loadCatalog() {
    try {
      const response = await api.get("/pc-builder/options");
      allOptions = response.options || {};
      restoreDraft();
      await triggerValidation();
      render();
    } catch (err) {
      renderError(root, err, loadCatalog);
    }
  }

  function restoreDraft() {
    try {
      const rawDraft = sessionStorage.getItem(DRAFT_STORAGE_KEY);
      if (!rawDraft) return;
      const draft = JSON.parse(rawDraft);
      for (const [slot, pid] of Object.entries(draft)) {
        if (slot in selectedProducts && allOptions[slot]) {
          const found = allOptions[slot].find((p) => p.id === pid);
          if (found) selectedProducts[slot] = found;
        }
      }
    } catch {
      // ignore draft parse failure
    }
  }

  function saveDraft() {
    try {
      const draft = {};
      for (const [slot, prod] of Object.entries(selectedProducts)) {
        if (prod) draft[slot] = prod.id;
      }
      sessionStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
    } catch {
      // ignore storage failure
    }
  }

  // ---------------------------------------------------------------------------
  // Authoritative Backend Validation & Recommendations
  // ---------------------------------------------------------------------------

  async function triggerValidation() {
    const components = {};
    let selectedCount = 0;
    for (const [slot, prod] of Object.entries(selectedProducts)) {
      if (prod) {
        components[slot] = prod.id;
        selectedCount++;
      }
    }

    // Refresh GPU recommendations if CPU is selected
    if (selectedProducts.cpu) {
      try {
        gpuRecommendations = await api.get("/pc-builder/recommendations/gpu", {
          cpu_id: selectedProducts.cpu.id,
        });
      } catch {
        gpuRecommendations = [];
      }
    } else {
      gpuRecommendations = [];
    }

    if (selectedCount === 0) {
      validationResult = {
        compatible: true,
        complete: false,
        issues: [],
        warnings: [],
        recommendations: [],
        subtotal: "0.00",
        discount_percent: "0",
        discount_amount: "0.00",
        total: "0.00",
      };
      return;
    }

    try {
      validationResult = await api.post("/pc-builder/validate", { components });
    } catch (err) {
      toast(err.message, "error");
    }
  }

  // ---------------------------------------------------------------------------
  // Component Evaluation Hints for Candidates
  // ---------------------------------------------------------------------------

  function evaluateCandidate(catSlug, prod) {
    if (prod.is_active === false) {
      return { status: "err", badge: "Unavailable", reason: "Product is no longer available.", canSelect: false };
    }
    if (typeof prod.stock === "number" && prod.stock <= 0) {
      return { status: "err", badge: "Out of Stock", reason: "Currently out of stock.", canSelect: false };
    }

    // GPU recommendations
    if (catSlug === "gpu" && selectedProducts.cpu && gpuRecommendations.length > 0) {
      const rec = gpuRecommendations.find((r) => r.product_id === prod.id);
      if (rec) {
        if (rec.match_level === "recommended") {
          return { status: "rec", badge: "Recommended", reason: rec.reason, canSelect: true };
        }
        if (rec.match_level === "good match") {
          return { status: "good", badge: "Good Match", reason: rec.reason, canSelect: true };
        }
        return { status: "warn", badge: "Not Ideal", reason: rec.reason, canSelect: true };
      }
    }

    // Motherboard <-> CPU socket
    if (catSlug === "motherboard" && selectedProducts.cpu) {
      const cpuSocket = selectedProducts.cpu.specifications?.socket;
      const moboSocket = prod.specifications?.socket;
      if (cpuSocket && moboSocket) {
        if (cpuSocket.trim().toUpperCase() !== moboSocket.trim().toUpperCase()) {
          return {
            status: "err",
            badge: "Incompatible",
            reason: `Socket mismatch: CPU uses ${cpuSocket}, this motherboard uses ${moboSocket}.`,
            canSelect: true,
          };
        }
        return { status: "ok", badge: "Compatible", reason: `Matches CPU socket (${cpuSocket}).`, canSelect: true };
      }
    }

    // RAM <-> Motherboard memory type
    if (catSlug === "ram" && selectedProducts.motherboard) {
      const moboMem = selectedProducts.motherboard.specifications?.memory_type;
      const ramMem = prod.specifications?.memory_type;
      if (moboMem && ramMem) {
        if (moboMem.trim().toUpperCase() !== ramMem.trim().toUpperCase()) {
          return {
            status: "err",
            badge: "Incompatible",
            reason: `Motherboard requires ${moboMem} memory, but this RAM is ${ramMem}.`,
            canSelect: true,
          };
        }
        return { status: "ok", badge: "Compatible", reason: `Matches motherboard (${moboMem}).`, canSelect: true };
      }
    }

    // Cooler <-> CPU socket
    if (catSlug === "cooler" && selectedProducts.cpu) {
      const cpuSocket = selectedProducts.cpu.specifications?.socket;
      const coolerSockets = prod.specifications?.socket_support;
      if (cpuSocket && coolerSockets) {
        const supported = coolerSockets.split(",").map((s) => s.trim().toUpperCase());
        if (!supported.includes(cpuSocket.trim().toUpperCase())) {
          return {
            status: "err",
            badge: "Incompatible",
            reason: `Cooler does not support CPU socket ${cpuSocket}.`,
            canSelect: true,
          };
        }
        return { status: "ok", badge: "Compatible", reason: `Supports ${cpuSocket} socket.`, canSelect: true };
      }
    }

    // Case <-> Motherboard form factor
    if (catSlug === "pc-case" && selectedProducts.motherboard) {
      const moboFf = selectedProducts.motherboard.specifications?.form_factor;
      const caseSupport = prod.specifications?.motherboard_support;
      if (moboFf && caseSupport) {
        const supported = caseSupport.split(",").map((s) => s.trim().toUpperCase());
        const normFf = moboFf.trim().toUpperCase();
        const fits =
          supported.includes(normFf) ||
          (["MICRO-ATX", "MINI-ITX"].includes(normFf) && (supported.includes("ATX") || supported.includes("E-ATX")));
        if (!fits) {
          return {
            status: "err",
            badge: "Incompatible",
            reason: `Case does not fit ${moboFf} motherboards.`,
            canSelect: true,
          };
        }
        return { status: "ok", badge: "Compatible", reason: `Supports ${moboFf} form factor.`, canSelect: true };
      }
    }

    // PSU <-> GPU recommended wattage
    if (catSlug === "psu" && selectedProducts.gpu) {
      const gpuRecRaw = selectedProducts.gpu.specifications?.recommended_psu;
      const psuWattRaw = prod.specifications?.wattage;
      const gpuRec = parseInt(gpuRecRaw?.match(/\d+/)?.[0] || "0", 10);
      const psuWatt = parseInt(psuWattRaw?.match(/\d+/)?.[0] || "0", 10);
      if (gpuRec && psuWatt) {
        if (psuWatt < gpuRec) {
          return {
            status: "err",
            badge: "Insufficient Wattage",
            reason: `Below GPU recommendation of ${gpuRec}W.`,
            canSelect: true,
          };
        }
        return { status: "ok", badge: "Sufficient Wattage", reason: `Meets GPU requirement (${gpuRec}W).`, canSelect: true };
      }
    }

    return { status: "ok", badge: "Compatible", reason: null, canSelect: true };
  }

  // ---------------------------------------------------------------------------
  // User Actions
  // ---------------------------------------------------------------------------

  async function handleSelectProduct(slot, product) {
    selectedProducts[slot] = product;
    saveDraft();
    openSlot = null; // collapse picker after selection
    await triggerValidation();
    render();
  }

  async function handleRemoveProduct(slot) {
    selectedProducts[slot] = null;
    saveDraft();
    await triggerValidation();
    render();
  }

  function handleToggleSlot(slot) {
    openSlot = openSlot === slot ? null : slot;
    render();
  }

  async function handleAddToCart(btn) {
    if (!validationResult.complete) {
      toast("Please select all 8 core components to complete your build.", "warning");
      return;
    }
    if (!validationResult.compatible) {
      toast("Please resolve compatibility errors before adding to cart.", "error");
      return;
    }

    if (!isLoggedIn()) {
      saveDraft();
      redirectToLogin("Please log in to add your completed PC build to your cart.");
      return;
    }

    await withBusy(btn, async () => {
      const components = {};
      for (const [slot, prod] of Object.entries(selectedProducts)) {
        if (prod) components[slot] = prod.id;
      }
      try {
        await api.post("/pc-builder/add-to-cart", { components, clear_existing: true });
        await refreshCartBadge();
        sessionStorage.removeItem(DRAFT_STORAGE_KEY);
        toast("Complete PC Build added to cart with 5% discount!", "success");

        openDialog({
          title: "Build Added to Cart!",
          content: html`
            <div class="modal__body">
              <p>All 8 core components have been added to your shopping cart with the authoritative <strong>5% Build Your Own PC discount</strong> applied.</p>
              <div class="builder-summary__pricing" style="margin-top:1rem;background:var(--surface-2);padding:1rem;border-radius:var(--radius-sm);">
                <div class="builder-summary__pricing-row"><span>Build Subtotal:</span><span>${formatPrice(validationResult.subtotal)}</span></div>
                <div class="builder-summary__pricing-row builder-summary__pricing-row--discount"><span>5% Build Discount:</span><span>-${formatPrice(validationResult.discount_amount)}</span></div>
                <div class="builder-summary__pricing-row builder-summary__pricing-row--total"><span>Final Total:</span><span>${formatPrice(validationResult.total)}</span></div>
              </div>
            </div>
            <div class="modal__footer">
              <a href="${siteUrl("pages/cart.html")}" class="btn btn--primary">View Cart &amp; Checkout</a>
              <button type="button" class="btn btn--secondary" data-close>Continue Building</button>
            </div>`,
        });
      } catch (err) {
        toast(err.message, "error");
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Rendering Views
  // ---------------------------------------------------------------------------

  function renderSelectedBox(slot, product) {
    const stock = stockInfo(product);
    return html`
      <div class="builder-step__selected-box" data-selected-slot="${slot}">
        <div class="builder-step__selected-info">
          <div data-media>
            <img class="builder-step__thumb" src="${imageUrl(product.image_url)}" alt="${product.name}" loading="lazy" />
          </div>
          <div class="builder-step__details">
            <h3 class="builder-step__name">${product.name}</h3>
            <p class="builder-step__specs">
              ${product.brand ? html`<span>${product.brand}</span> \u00b7 ` : ""}
              <span class="stock-badge ${stock.className}">${stock.label}</span>
            </p>
          </div>
        </div>
        <div class="builder-step__actions">
          <span class="builder-step__price">${formatPrice(product.price)}</span>
          <button type="button" class="btn btn--secondary btn--sm" data-action="toggle-slot" data-slot="${slot}">Change</button>
          <button type="button" class="btn btn--ghost btn--sm" data-action="remove-slot" data-slot="${slot}" aria-label="Remove ${product.name}">&times;</button>
        </div>
      </div>`;
  }

  function renderPicker(slot) {
    const products = allOptions[slot] || [];
    const query = (searchQueries[slot] || "").toLowerCase().trim();
    const filtered = query
      ? products.filter((p) => p.name.toLowerCase().includes(query) || (p.brand && p.brand.toLowerCase().includes(query)))
      : products;

    return html`
      <div class="builder-step__picker" data-picker-slot="${slot}">
        <div class="builder-picker__controls">
          <input
            type="search"
            class="input builder-picker__search"
            placeholder="Filter components\u2026"
            value="${searchQueries[slot] || ""}"
            data-search-slot="${slot}"
            aria-label="Filter ${slot} components"
          />
          <span class="builder-picker__count">${filtered.length} products available</span>
        </div>
        ${filtered.length === 0
          ? html`<div class="state state--empty"><p>No products match your search.</p></div>`
          : html`
              <div class="builder-picker__grid">
                ${filtered.map((prod) => {
                  const evalInfo = evaluateCandidate(slot, prod);
                  const stock = stockInfo(prod);
                  const isCardRecommended = evalInfo.status === "rec";
                  const isCardIncompatible = evalInfo.status === "err" || !evalInfo.canSelect;

                  let tagClass = "badge";
                  if (evalInfo.status === "rec") tagClass = "badge badge--success";
                  else if (evalInfo.status === "good") tagClass = "badge badge--info";
                  else if (evalInfo.status === "warn") tagClass = "badge badge--warning";
                  else if (evalInfo.status === "err") tagClass = "badge badge--danger";

                  return html`
                    <div
                      class="builder-card ${isCardRecommended ? "is-recommended" : ""} ${isCardIncompatible ? "is-incompatible" : ""}"
                      data-builder-product="${prod.id}"
                      data-product-card
                    >
                      <div class="builder-card__top">
                        <div data-media>
                          <img class="builder-card__img" src="${imageUrl(prod.image_url)}" alt="${prod.name}" loading="lazy" />
                        </div>
                        <div class="builder-card__meta">
                          <h3 class="builder-card__title">${prod.name}</h3>
                          ${prod.brand ? html`<div class="builder-card__brand">${prod.brand}</div>` : ""}
                        </div>
                      </div>
                      <div class="builder-card__tags">
                        <span class="${tagClass}" data-compat-status="${evalInfo.status === "rec" ? "recommended" : (evalInfo.status === "err" ? "incompatible" : "compatible")}">
                          ${evalInfo.badge}
                        </span>
                        <span class="stock-badge ${stock.className}">${stock.label}</span>
                      </div>
                      ${evalInfo.reason
                        ? html`
                            <p
                              class="builder-card__reason ${evalInfo.status === "warn" ? "builder-card__reason--warn" : ""} ${evalInfo.status === "err" ? "builder-card__reason--danger" : ""}"
                              data-recommendation-reason
                            >
                              ${evalInfo.reason}
                            </p>`
                        : ""}
                      <div class="builder-card__bottom">
                        <span class="builder-card__price">${formatPrice(prod.price)}</span>
                        <button
                          type="button"
                          class="btn ${isCardRecommended ? "btn--primary" : "btn--secondary"} btn--sm"
                          data-action="select-product"
                          data-slot="${slot}"
                          data-product-id="${prod.id}"
                          ${!evalInfo.canSelect ? raw('disabled aria-disabled="true"') : ""}
                          aria-label="Select ${prod.name}"
                        >
                          Select
                        </button>
                      </div>
                    </div>`;
                })}
              </div>`}
      </div>`;
  }

  function renderStep(category, index) {
    const slot = category.slug;
    const selected = selectedProducts[slot];
    const isOpen = openSlot === slot;
    const hasError = validationResult.issues.some((i) => i.components.includes(slot));

    return html`
      <div
        class="builder-step ${selected ? "is-selected" : ""} ${hasError ? "has-error" : ""}"
        data-category="${slot}"
      >
        <div class="builder-step__header">
          <div class="builder-step__title-wrap">
            <span class="builder-step__icon">${icon(category.iconName)}</span>
            <div>
              <h2 class="builder-step__title">Step ${index + 1}: ${category.name}</h2>
              <span class="text-muted" style="font-size:0.8rem;">${category.hint}</span>
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:0.75rem;">
            ${selected
              ? html`<span class="badge badge--success builder-step__status-badge">Selected</span>`
              : html`<span class="badge builder-step__status-badge">Not selected</span>`}
            <button
              type="button"
              class="btn btn--ghost btn--sm"
              data-action="toggle-slot"
              data-slot="${slot}"
              data-choose-slot="${slot}"
              aria-expanded="${String(isOpen)}"
              aria-label="${isOpen ? "Close " + category.name + " selection" : "Choose " + category.name}"
            >
              ${isOpen ? "Close" : selected ? "Change" : "Choose"}
            </button>
          </div>
        </div>

        ${selected && !isOpen ? renderSelectedBox(slot, selected) : ""}
        ${isOpen ? renderPicker(slot) : ""}
      </div>`;
  }

  function renderSummary() {
    const selectedCount = Object.values(selectedProducts).filter(Boolean).length;
    const isComplete = validationResult.complete;
    const isCompatible = validationResult.compatible;

    return html`
      <aside class="builder-summary" data-build-summary aria-label="Build Summary">
        <div class="builder-summary__header">
          <h2>Build Summary</h2>
          <span class="badge ${isComplete ? "badge--success" : ""}" style="font-size:0.85rem;">
            ${selectedCount} of 8 components
          </span>
        </div>

        <div class="builder-summary__slots">
          ${CATEGORIES.map((cat) => {
            const prod = selectedProducts[cat.slug];
            return html`
              <div class="builder-summary__slot">
                <span class="builder-summary__slot-name">${cat.name.split(" ")[0]}</span>
                ${prod
                  ? html`
                      <span class="builder-summary__slot-val" title="${prod.name}">${prod.name}</span>
                      <span class="builder-summary__slot-price">${formatPrice(prod.price)}</span>`
                  : html`<span class="builder-summary__slot-val is-empty">Not selected</span>`}
              </div>`;
          })}
        </div>

        <!-- 5% Discount Promotion Banner -->
        <div
          class="builder-summary__discount-banner ${isComplete && isCompatible ? "is-unlocked" : ""}"
          data-discount-banner
          role="status"
          aria-live="polite"
        >
          ${isComplete && isCompatible
            ? html`
                <strong>✓ Complete Build!</strong><br />
                5% Build Your Own PC discount unlocked. You save
                <strong>${formatPrice(validationResult.discount_amount)}</strong> on this build.
              `
            : html`
                <strong>Get 5% Off Your Build</strong><br />
                Add all 8 core components to unlock an authoritative 5% discount on your entire build.
              `}
        </div>

        <!-- Validation Issues / Warnings -->
        ${validationResult.issues.length > 0
          ? html`
              <div class="builder-summary__issues" role="alert" data-validation-issues>
                <strong>Compatibility Issues:</strong>
                <ul style="margin:0.4rem 0 0;padding-left:1.2rem;">
                  ${validationResult.issues.map((i) => html`<li>${i.message}</li>`)}
                </ul>
              </div>`
          : ""}
        ${validationResult.warnings.length > 0
          ? html`
              <div class="builder-summary__warnings" role="status">
                <strong>Recommendations &amp; Headroom:</strong>
                <ul style="margin:0.4rem 0 0;padding-left:1.2rem;">
                  ${validationResult.warnings.map((w) => html`<li>${w.message}</li>`)}
                </ul>
              </div>`
          : ""}

        <!-- Pricing Breakdown -->
        <div class="builder-summary__pricing">
          <div class="builder-summary__pricing-row">
            <span>Subtotal</span>
            <span data-summary-subtotal>${formatPrice(validationResult.subtotal)}</span>
          </div>
          <div class="builder-summary__pricing-row builder-summary__pricing-row--discount">
            <span>Build Discount (5%)</span>
            <span data-summary-discount>-${formatPrice(validationResult.discount_amount)}</span>
          </div>
          <div class="builder-summary__pricing-row builder-summary__pricing-row--total">
            <span>Total</span>
            <span data-summary-total>${formatPrice(validationResult.total)}</span>
          </div>
        </div>

        <!-- Action Button -->
        <button
          type="button"
          class="btn btn--primary btn--block"
          data-action="add-build-to-cart"
          ${!isComplete || !isCompatible ? raw('disabled aria-disabled="true"') : ""}
        >
          ${icon("cart")} Add Complete Build to Cart
        </button>
      </aside>`;
  }

  function render() {
    mount(
      root,
      html`
        <div class="builder-layout">
          <div class="builder-steps">
            ${CATEGORIES.map((cat, idx) => renderStep(cat, idx))}
          </div>
          ${renderSummary()}
        </div>`,
    );

    wireEvents();
  }

  function wireEvents() {
    // Slot toggling (open/close picker)
    root.querySelectorAll("[data-action='toggle-slot']").forEach((btn) => {
      btn.addEventListener("click", () => handleToggleSlot(btn.dataset.slot));
    });

    // Remove slot
    root.querySelectorAll("[data-action='remove-slot']").forEach((btn) => {
      btn.addEventListener("click", () => handleRemoveProduct(btn.dataset.slot));
    });

    // Select candidate product
    root.querySelectorAll("[data-action='select-product']").forEach((btn) => {
      btn.addEventListener("click", () => {
        const slot = btn.dataset.slot;
        const pid = parseInt(btn.dataset.productId, 10);
        const prod = (allOptions[slot] || []).find((p) => p.id === pid);
        if (prod) handleSelectProduct(slot, prod);
      });
    });

    // Filter search inside picker
    root.querySelectorAll("[data-search-slot]").forEach((input) => {
      input.addEventListener("input", (e) => {
        const slot = input.dataset.searchSlot;
        const query = (e.target.value || "").toLowerCase().trim();
        searchQueries[slot] = e.target.value;
        const picker = root.querySelector(`[data-picker-slot='${slot}']`);
        if (!picker) return;
        const cards = picker.querySelectorAll("[data-builder-product]");
        let visibleCount = 0;
        cards.forEach((card) => {
          const title = (card.querySelector(".builder-card__title")?.textContent || "").toLowerCase();
          const brand = (card.querySelector(".builder-card__brand")?.textContent || "").toLowerCase();
          const matches = !query || title.includes(query) || brand.includes(query);
          card.style.display = matches ? "" : "none";
          card.hidden = !matches;
          if (matches) visibleCount++;
        });
        const countEl = picker.querySelector(".builder-picker__count");
        if (countEl) countEl.textContent = `${visibleCount} products available`;
      });
    });

    // Add Complete Build to Cart button
    root.querySelector("[data-action='add-build-to-cart']")?.addEventListener("click", (e) => {
      handleAddToCart(e.currentTarget);
    });
  }

  // Load the initial catalog
  await loadCatalog();
}
