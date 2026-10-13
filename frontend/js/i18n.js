/**
 * Arad Store - Bilingual (English & Persian) i18n Module
 * Supports seamless switching between English (LTR) and فارسی (RTL).
 * State is persisted in localStorage ('arad_store_lang').
 */

import { html, openDialog } from "./ui.js";

const STORAGE_KEY = "arad_store_lang";

export const translations = {
  en: {
    // General
    site_title: "Arad Store",
    promo_text: "Build a complete PC — 8 core parts — and get 5% off // Live stock telemetry",
    promo_badge: "PROMO",
    skip_link: "Skip to main content",
    lang_name: "English",
    lang_name_persian: "English",
    change_lang: "Language",
    select_language: "Select Language",
    select_language_desc: "Choose your preferred display language for Arad Store.",
    lang_en: "English (US)",
    lang_en_desc: "Default store language \u00b7 Left-to-Right (LTR)",
    lang_fa: "فارسی (Persian)",
    lang_fa_desc: "زبان فارسی \u00b7 راست‌چین کامل (RTL)",
    apply: "Apply",
    close: "Close",
    cancel: "Cancel",

    // Navigation
    nav_home: "Home",
    nav_shop: "Shop",
    nav_builder: "Build Your PC",
    nav_orders: "My orders",
    nav_admin: "Admin",
    nav_cart: "Cart",
    nav_login: "Log in",
    nav_signup: "Sign up",
    nav_profile: "My profile",
    nav_logout: "Log out",

    // Homepage Hero
    hero_eyebrow: "ENTERPRISE & ENTHUSIAST RIGS // 2026 TELEMETRY",
    hero_title_1: "Precision hardware.",
    hero_title_accent: "Engineered",
    hero_title_2: "for peak compute.",
    hero_desc: "High-throughput graphics architecture, AM5 & LGA1700 processors, ultra-low latency memory and enterprise NVMe storage. Authoritative stock telemetry and server-verified builds.",
    hero_search_placeholder: "Search SKU e.g. RTX 4080, Ryzen 7, NVMe...",
    hero_search_btn: "Search",
    hero_cta_builder: "Build Your PC",
    hero_cta_shop: "Browse all products",

    // Sections
    sec_categories_title: "Explore Hardware Classes",
    sec_categories_subtitle: "Eight core categories engineered for complete compatibility verification",
    sec_arrivals_title: "New arrivals // Direct Telemetry",
    sec_arrivals_subtitle: "Latest production runs fresh from verified distributors",
    sec_all_products: "Complete Catalogue \u2192",

    // Trust Band
    trust_stock_title: "Authoritative Stock",
    trust_stock_desc: "Real-time inventory reserve. If it is shown in stock, it is ready for immediate allocation.",
    trust_pricing_title: "Server-Verified Pricing",
    trust_pricing_desc: "Transparent price computation with automated 5% full-build discount verification.",
    trust_orders_title: "Order Telemetry",
    trust_orders_desc: "End-to-end status tracking from order confirmation through final fulfillment.",

    // Promo Banners
    promo_builder_eyebrow: "CUSTOM RIG WORKSHOP",
    promo_builder_title: "Configure your machine with 100% verified compatibility.",
    promo_builder_desc: "Select all 8 core hardware components through our interactive builder. Automated socket and headroom validation ensures zero hardware conflicts, plus an instant 5% discount on the entire system.",
    promo_builder_cta: "Launch PC Builder",

    // Shop & Products
    shop_title: "Shop \u00b7 Hardware Catalogue",
    filter_matrix: "Filter Matrix",
    filter_search: "Search component",
    filter_category: "Architecture category",
    filter_all_cats: "All Categories",
    filter_price: "Price envelope (USD)",
    filter_sort: "Sort sequence",
    filter_sort_newest: "Newest Releases",
    filter_sort_price_asc: "Price: Low to High",
    filter_sort_price_desc: "Price: High to Low",
    filter_sort_name_asc: "Name: A to Z",
    filter_sort_name_desc: "Name: Z to A",
    filter_apply: "Apply",
    filter_reset: "Reset",

    // Product Card
    stock_in: "In stock",
    stock_low: "Only {count} left",
    stock_out: "Out of stock",
    stock_unavailable: "Unavailable",
    add_to_cart: "Add to cart",
    inspect_specimen: "Inspect Specimen",

    // Product Details
    tech_specs: "Technical Specifications",
    qty: "Qty",

    // PC Builder
    builder_title: "Build Your Own PC",
    builder_subtitle: "Select compatible components step-by-step. Complete all 8 core components to receive an authoritative 5% discount on your entire build.",
    builder_summary_title: "Build Summary",
    builder_components_count: "{count} of 8 components",
    builder_discount_banner: "Get 5% Off Your Build",
    builder_discount_desc: "Add all 8 core components to unlock an authoritative 5% discount on your entire build.",
    builder_discount_unlocked: "5% Build Your Own PC discount unlocked",
    builder_discount_label: "5% Build Discount:",
    builder_subtotal: "Build Subtotal:",
    builder_total: "Final Total:",
    builder_add_cart: "Complete Build!",
    select: "Select",
    selected: "Selected",
    not_selected: "Not selected",

    // Cart
    cart_title: "Your cart",
    cart_empty: "Your cart is empty",
    cart_items: "Items",
    cart_total: "Total",
    place_order: "Place order",
    continue_shopping: "Continue shopping",
    order_success: "Thank you! Order #{id} is placed.",

    // Footer
    footer_blurb: "PC components and gaming gear: graphics cards, processors, memory, storage and accessories.",
    footer_shop_col: "Shop",
    footer_account_col: "Account",
    footer_legal: "A demo project: no payments are processed and nothing is shipped.",
  },

  fa: {
    // General
    site_title: "فروشگاه آراد",
    promo_text: "اسمبل سیستم کامل گیمینگ — ۸ قطعه اصلی — با ۵٪ تخفیف ویژه // استعلام لحظه‌ای موجودی",
    promo_badge: "تخفیف ویژه",
    skip_link: "رفتن به محتوای اصلی",
    lang_name: "فارسی",
    lang_name_persian: "فارسی",
    change_lang: "زبان",
    select_language: "انتخاب زبان سایت",
    select_language_desc: "زبان مورد نظر خود را برای نمایش سایت انتخاب کنید.",
    lang_en: "English (انگلیسی)",
    lang_en_desc: "نمایش پیش‌فرض چپ‌چین (LTR)",
    lang_fa: "فارسی (Persian)",
    lang_fa_desc: "نمایش کاملاً راست‌چین و بومی (RTL)",
    apply: "اعمال تغییرات",
    close: "بستن",
    cancel: "انصراف",

    // Navigation
    nav_home: "خانه",
    nav_shop: "فروشگاه",
    nav_builder: "اسمبل آنلاین سیستم",
    nav_orders: "سفارش‌های من",
    nav_admin: "پنل مدیریت",
    nav_cart: "سبد خرید",
    nav_login: "ورود به حساب",
    nav_signup: "ثبت‌نام",
    nav_profile: "پروفایل کاربری",
    nav_logout: "خروج",

    // Homepage Hero
    hero_eyebrow: "سخت‌افزار انترپرایز و گیمینگ // تلمتری ۲۰۲۶",
    hero_title_1: "سخت‌افزار دقیق.",
    hero_title_accent: "مهندسی‌شده",
    hero_title_2: "برای بالاترین توان پردازش.",
    hero_desc: "معماری گرافیکی فوق‌سریع، پردازنده‌های پیشرفته AM5 و LGA1700، حافظه‌های رم کم‌تاخیر و حافظه‌های پرسرعت NVMe. استعلام زنده موجودی انبار و سیستم‌های تأییدشده سازگاری.",
    hero_search_placeholder: "جستجوی قطعه مثلاً RTX 4080، Ryzen 7، NVMe...",
    hero_search_btn: "جستجو",
    hero_cta_builder: "اسمبل آنلاین سیستم",
    hero_cta_shop: "مشاهده تمام محصولات",

    // Sections
    sec_categories_title: "دسته‌بندی‌های سخت‌افزار",
    sec_categories_subtitle: "هشت گروه قطعات اصلی مهندسی‌شده برای سازگاری کامل در اسمبل",
    sec_arrivals_title: "جدیدترین محصولات // موجودی انبار",
    sec_arrivals_subtitle: "تازه‌ترین قطعات اورجینال از توزیع‌کنندگان معتبر",
    sec_all_products: "مشاهده کاتالوگ کامل \u2190",

    // Trust Band
    trust_stock_title: "موجودی لحظه‌ای و واقعی",
    trust_stock_desc: "رزرو قطعی انبار در لحظه ثبت سفارش. قطعات دارای برچسب موجود، بلافاصله آماده تخصیص هستند.",
    trust_pricing_title: "قیمت‌گذاری شفاف و سروری",
    trust_pricing_desc: "محاسبه دقیق قیمت‌ها با تخفیف قطعی ۵ درصدی روی اسمبل سیستم کامل ۸ قطعه‌ای.",
    trust_orders_title: "رهگیری لحظه‌ای وضعیت",
    trust_orders_desc: "امکان رهگیری گام‌به‌گام سفارش از زمان ثبت نهایی تا آماده‌سازی و ارسال کالا.",

    // Promo Banners
    promo_builder_eyebrow: "کارگاه اسمبل اختصاصی",
    promo_builder_title: "سیستم مورد نیازتان را با تضمین ۱۰۰٪ سازگاری اسمبل کنید.",
    promo_builder_desc: "هر ۸ قطعه اصلی را مرحله به مرحله انتخاب نمایید. هوش بررسی سازگاری سوکت و توان پاور مانع از هرگونه تداخل سخت‌افزاری می‌شود؛ همراه با تخفیف خودکار ۵٪ روی کل سیستم.",
    promo_builder_cta: "ورود به بخش اسمبل سیستم",

    // Shop & Products
    shop_title: "فروشگاه · کاتالوگ سخت‌افزار",
    filter_matrix: "فیلتر قطعات",
    filter_search: "جستجوی نام یا مدل قطعه",
    filter_category: "دسته‌بندی سخت‌افزار",
    filter_all_cats: "همه دسته‌ها",
    filter_price: "محدوده قیمت (دلار)",
    filter_sort: "ترتیب نمایش",
    filter_sort_newest: "جدیدترین‌ها",
    filter_sort_price_asc: "ارزان‌ترین به گران‌ترین",
    filter_sort_price_desc: "گران‌ترین به ارزان‌ترین",
    filter_sort_name_asc: "نام: الف تا ی",
    filter_sort_name_desc: "نام: ی تا الف",
    filter_apply: "اعمال فیلتر",
    filter_reset: "پاک کردن",

    // Product Card
    stock_in: "موجود در انبار",
    stock_low: "تنها {count} عدد در انبار",
    stock_out: "ناموجود",
    stock_unavailable: "عدم دسترسی",
    add_to_cart: "افزودن به سبد",
    inspect_specimen: "مشاهده جزئیات",

    // Product Details
    tech_specs: "مشخصات فنی قطعه",
    qty: "تعداد",

    // PC Builder
    builder_title: "اسمبل آنلاین سیستم (PC Builder)",
    builder_subtitle: "قطعات سازگار را مرحله به مرحله انتخاب کنید. با انتخاب هر ۸ قطعه اصلی، ۵٪ تخفیف ویژه روی تمام قطعات سیستم دریافت نمایید.",
    builder_summary_title: "خلاصه سیستم انتخابی",
    builder_components_count: "{count} از ۸ قطعه انتخاب شده",
    builder_discount_banner: "دریافت ۵٪ تخفیف ویژه اسمبل",
    builder_discount_desc: "تمام ۸ قطعه اصلی را انتخاب کنید تا ۵٪ تخفیف روی کل سیستم فعال شود.",
    builder_discount_unlocked: "تخفیف ۵٪ اسمبل سیستم با موفقیت فعال شد",
    builder_discount_label: "۵٪ تخفیف اسمبل:",
    builder_subtotal: "جمع اولیه قطعات:",
    builder_total: "مبلغ قابل پرداخت:",
    builder_add_cart: "افزودن سیستم به سبد خرید!",
    select: "انتخاب قطعه",
    selected: "انتخاب شد",
    not_selected: "انتخاب نشده",

    // Cart
    cart_title: "سبد خرید شما",
    cart_empty: "سبد خرید شما خالی است",
    cart_items: "تعداد کالاها",
    cart_total: "مجموع نهایی",
    place_order: "ثبت نهایی سفارش",
    continue_shopping: "ادامه خرید",
    order_success: "با تشکر! سفارش #{id} ثبت گردید.",

    // Footer
    footer_blurb: "تخصصی‌ترین مرجع قطعات سخت‌افزار کامپیوتر و گیمینگ: کارت‌های گرافیک، پردازنده، رم، حافظه و تجهیزات جانبی.",
    footer_shop_col: "فروشگاه",
    footer_account_col: "حساب کاربری",
    footer_legal: "پروژه فروشگاهی آزمایشی: هیچ پرداخت و ارسالی انجام نمی‌شود.",
  },
};

/**
 * Returns current language code ('en' or 'fa').
 */
export function getCurrentLang() {
  try {
    return localStorage.getItem(STORAGE_KEY) || "en";
  } catch {
    return "en";
  }
}

/**
 * Translates a key with fallback to English text.
 */
export function t(key, fallback = "") {
  const lang = getCurrentLang();
  return translations[lang]?.[key] ?? translations.en[key] ?? fallback;
}

/**
 * Applies language setting to DOM (lang attribute, dir attribute, font classes).
 */
export function applyHtmlDirection(lang = getCurrentLang()) {
  const isRtl = lang === "fa";
  document.documentElement.lang = lang;
  document.documentElement.dir = isRtl ? "rtl" : "ltr";
  document.documentElement.classList.toggle("is-rtl", isRtl);
  document.body.classList.toggle("is-rtl", isRtl);
}

/**
 * Sets current language and reloads page to apply.
 */
export function setLanguage(newLang) {
  const current = getCurrentLang();
  if (current === newLang) return;
  try {
    localStorage.setItem(STORAGE_KEY, newLang);
  } catch (err) {
    console.error("Failed to store language preference", err);
  }
  applyHtmlDirection(newLang);
  window.location.reload();
}

/**
 * Language Selector Pop-up Modal
 */
export function openLanguageModal() {
  const currentLang = getCurrentLang();

  const content = html`
    <div class="modal__body lang-popup">
      <p class="text-muted" style="margin-bottom:1.25rem;">
        ${currentLang === "fa"
          ? "زبان مورد نظر خود را برای نمایش سایت انتخاب فرمایید:"
          : "Choose your preferred display language for the store interface:"}
      </p>

      <div class="lang-popup__options">
        <div class="lang-option ${currentLang === "en" ? "is-active" : ""}" data-choose-lang="en" tabindex="0" role="button" aria-pressed="${currentLang === "en"}">
          <div class="lang-option__info">
            <span class="lang-option__flag" aria-hidden="true">\u{1F1FA}\u{1F1F8}</span>
            <div>
              <div class="lang-option__title">English (US)</div>
              <div class="lang-option__desc">Default store language \u00b7 Left-to-Right (LTR)</div>
            </div>
          </div>
          <div class="lang-option__check" aria-hidden="true">&#10003;</div>
        </div>

        <div class="lang-option ${currentLang === "fa" ? "is-active" : ""}" data-choose-lang="fa" tabindex="0" role="button" aria-pressed="${currentLang === "fa"}">
          <div class="lang-option__info">
            <span class="lang-option__flag" aria-hidden="true">\u{1F1EE}\u{1F1F7}</span>
            <div>
              <div class="lang-option__title">فارسی (Persian)</div>
              <div class="lang-option__desc">زبان فارسی \u00b7 راست‌چین کامل (RTL)</div>
            </div>
          </div>
          <div class="lang-option__check" aria-hidden="true">&#10003;</div>
        </div>
      </div>
    </div>
    <div class="modal__footer">
      <button type="button" class="btn btn--secondary" data-close>
        ${currentLang === "fa" ? "انصراف" : "Cancel"}
      </button>
    </div>`;

  const dialog = openDialog({
    title: currentLang === "fa" ? "انتخاب زبان سایت" : "Language Settings",
    content,
    wide: false,
  });

  dialog.querySelectorAll("[data-choose-lang]").forEach((el) => {
    const handleSelect = () => {
      const selected = el.dataset.chooseLang;
      if (selected !== currentLang) {
        setLanguage(selected);
      } else {
        dialog.close();
      }
    };
    el.addEventListener("click", handleSelect);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleSelect();
      }
    });
  });
}

/**
 * Renders the Language Selector Trigger Button for the Header
 */
export function renderLanguageButton() {
  const currentLang = getCurrentLang();
  const label = currentLang === "fa" ? "فارسی" : "EN";
  return html`
    <button type="button" class="lang-btn" id="lang-picker-btn" aria-haspopup="dialog" aria-label="Language selector / انتخاب زبان" title="Change Language / تغییر زبان">
      <svg class="lang-btn__icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="2" y1="12" x2="22" y2="12"></line>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
      </svg>
      <span class="lang-btn__badge">${label}</span>
    </button>`;
}

/**
 * Translates existing static and dynamic DOM text when language is Persian ('fa').
 */
export function translatePageContent() {
  const lang = getCurrentLang();
  if (lang !== "fa") return;

  // Title
  if (document.title.includes("Arad Store")) {
    document.title = document.title.replace("Arad Store", "فروشگاه آراد");
  }

  // Header announcement
  const announcementText = document.querySelector(".announcement-bar__text");
  if (announcementText) announcementText.textContent = translations.fa.promo_text;
  const announcementBadge = document.querySelector(".announcement-bar__badge");
  if (announcementBadge) announcementBadge.textContent = translations.fa.promo_badge;

  // Navigation links
  const navMap = {
    "Home": translations.fa.nav_home,
    "Shop": translations.fa.nav_shop,
    "Build Your PC": translations.fa.nav_builder,
    "My orders": translations.fa.nav_orders,
    "Admin": translations.fa.nav_admin,
  };
  document.querySelectorAll(".site-nav__links a").forEach((link) => {
    const text = link.textContent.trim();
    if (navMap[text]) link.textContent = navMap[text];
  });

  // User menu / Auth buttons in header
  const loginBtn = document.querySelector(".site-nav__actions .btn--ghost");
  if (loginBtn && loginBtn.textContent.trim() === "Log in") loginBtn.textContent = translations.fa.nav_login;
  const signupBtn = document.querySelector(".site-nav__actions .btn--primary");
  if (signupBtn && signupBtn.textContent.trim() === "Sign up") signupBtn.textContent = translations.fa.nav_signup;

  const userMenu = document.querySelector(".user-menu");
  if (userMenu) {
    userMenu.querySelectorAll("a").forEach((a) => {
      if (a.textContent.trim() === "My profile") a.textContent = translations.fa.nav_profile;
      if (a.textContent.trim() === "My orders") a.textContent = translations.fa.nav_orders;
    });
    const logoutBtn = userMenu.querySelector("button[data-logout]");
    if (logoutBtn) logoutBtn.textContent = translations.fa.nav_logout;
  }

  // Footer translations
  const footerBlurb = document.querySelector(".site-footer__blurb");
  if (footerBlurb) footerBlurb.textContent = translations.fa.footer_blurb;
  const footerH2s = document.querySelectorAll(".site-footer nav h2");
  if (footerH2s[0]) footerH2s[0].textContent = translations.fa.footer_shop_col;
  if (footerH2s[1]) footerH2s[1].textContent = translations.fa.footer_account_col;
  const footerLegal = document.querySelector(".site-footer__legal");
  if (footerLegal) footerLegal.textContent = `\u00a9 ${new Date().getFullYear()} فروشگاه آراد \u00b7 ${translations.fa.footer_legal}`;

  // Homepage hero & features
  const heroEyebrow = document.querySelector(".hero__eyebrow");
  if (heroEyebrow) heroEyebrow.textContent = translations.fa.hero_eyebrow;
  const heroDesc = document.querySelector(".hero__desc");
  if (heroDesc) heroDesc.textContent = translations.fa.hero_desc;
  const heroSearchInput = document.querySelector("#hero-search input");
  if (heroSearchInput) heroSearchInput.placeholder = translations.fa.hero_search_placeholder;
  const heroSearchBtn = document.querySelector("#hero-search button");
  if (heroSearchBtn) heroSearchBtn.textContent = translations.fa.hero_search_btn;

  const heroBuilderBtn = document.querySelector(".hero__actions .btn--primary");
  if (heroBuilderBtn && heroBuilderBtn.textContent.trim() === "Build Your PC") {
    heroBuilderBtn.textContent = translations.fa.hero_cta_builder;
  }
  const heroShopBtn = document.querySelector(".hero__actions .btn--secondary");
  if (heroShopBtn && heroShopBtn.textContent.trim() === "Browse all products") {
    heroShopBtn.textContent = translations.fa.hero_cta_shop;
  }

  const catHeader = document.querySelector("#cat-title");
  if (catHeader) catHeader.textContent = translations.fa.sec_categories_title;
  const catSub = document.querySelector(".section:not(.section--alt) .section__header p");
  if (catSub) catSub.textContent = translations.fa.sec_categories_subtitle;

  const newHeader = document.querySelector("#new-title");
  if (newHeader) newHeader.textContent = translations.fa.sec_arrivals_title;
  const newSub = document.querySelector(".section--alt .section__header p");
  if (newSub) newSub.textContent = translations.fa.sec_arrivals_subtitle;
  const allProdsLink = document.querySelector(".section--alt .section__header a");
  if (allProdsLink) allProdsLink.textContent = translations.fa.sec_all_products;

  // Split feature banner
  const splitEyebrow = document.querySelector(".split-feature__eyebrow");
  if (splitEyebrow) splitEyebrow.textContent = translations.fa.promo_builder_eyebrow;
  const splitTitle = document.querySelector(".split-feature__title");
  if (splitTitle) splitTitle.textContent = translations.fa.promo_builder_title;
  const splitDesc = document.querySelector(".split-feature__text");
  if (splitDesc) splitDesc.textContent = translations.fa.promo_builder_desc;
  const splitCta = document.querySelector(".split-feature__actions .btn");
  if (splitCta) splitCta.textContent = translations.fa.promo_builder_cta;

  // Trust cards
  const trustHeaders = document.querySelectorAll(".trust-card h3");
  const trustTexts = document.querySelectorAll(".trust-card p");
  if (trustHeaders[0]) trustHeaders[0].textContent = translations.fa.trust_stock_title;
  if (trustTexts[0]) trustTexts[0].textContent = translations.fa.trust_stock_desc;
  if (trustHeaders[1]) trustHeaders[1].textContent = translations.fa.trust_pricing_title;
  if (trustTexts[1]) trustTexts[1].textContent = translations.fa.trust_pricing_desc;
  if (trustHeaders[2]) trustHeaders[2].textContent = translations.fa.trust_orders_title;
  if (trustTexts[2]) trustTexts[2].textContent = translations.fa.trust_orders_desc;

  // Shop page filters
  const filterTitle = document.querySelector(".panel__title");
  if (filterTitle && filterTitle.textContent.includes("Filter")) filterTitle.textContent = translations.fa.filter_matrix;
  const searchLabel = document.querySelector('label[for="filter-search"]');
  if (searchLabel) searchLabel.textContent = translations.fa.filter_search;
  const catLabel = document.querySelector('label[for="filter-category"]');
  if (catLabel) catLabel.textContent = translations.fa.filter_category;
  const priceLegend = document.querySelector(".filter-panel fieldset legend");
  if (priceLegend) priceLegend.textContent = translations.fa.filter_price;
  const sortLabel = document.querySelector('label[for="filter-sort"]');
  if (sortLabel) sortLabel.textContent = translations.fa.filter_sort;

  const filterSubmit = document.querySelector('#filter-form button[type="submit"]');
  if (filterSubmit) filterSubmit.textContent = translations.fa.filter_apply;
  const filterReset = document.querySelector('#filter-form button[type="button"]');
  if (filterReset) filterReset.textContent = translations.fa.filter_reset;

  // Buttons and badges
  document.querySelectorAll("[data-add-to-cart]").forEach((btn) => {
    if (btn.textContent.includes("Add to cart") || btn.textContent.includes("ADD TO CART")) {
      btn.textContent = translations.fa.add_to_cart;
    }
  });

  // Observe dynamically loaded elements (products, builder steps, etc.)
  const observer = new MutationObserver(() => {
    document.querySelectorAll("[data-add-to-cart]").forEach((btn) => {
      if (btn.textContent.includes("Add to cart") || btn.textContent.includes("ADD TO CART")) {
        btn.textContent = translations.fa.add_to_cart;
      }
    });
    document.querySelectorAll(".stock").forEach((s) => {
      if (s.textContent.trim() === "In stock") s.textContent = translations.fa.stock_in;
      if (s.textContent.trim() === "Out of stock") s.textContent = translations.fa.stock_out;
    });
    document.querySelectorAll(".builder-card__bottom .btn").forEach((btn) => {
      if (btn.textContent.trim() === "Select") btn.textContent = translations.fa.select;
    });
  });

  observer.observe(document.body, { childList: true, subtree: true });
}

/**
 * Initializes language direction on startup and attaches popup listeners.
 */
export function initI18n() {
  applyHtmlDirection();
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("#lang-picker-btn");
    if (btn) {
      e.preventDefault();
      openLanguageModal();
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => translatePageContent());
  } else {
    translatePageContent();
  }
}
