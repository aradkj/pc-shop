# Arad Store

**A full-stack online shop for PC components and gaming gear** — graphics cards, processors, memory, storage and accessories.
FastAPI + PostgreSQL on the back end, plain HTML / CSS / vanilla JavaScript on the front end, everything runnable with one `docker compose up`.

| | |
|---|---|
| **Back end** | Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 17, JWT + bcrypt, HttpOnly cookies, CSRF protection, rate limiting |
| **Front end** | HTML5, CSS3 (own design system with CSS variables), ES-module vanilla JS — no framework, no build step |
| **Quality** | 253 pytest tests on a real PostgreSQL database (97 % coverage), Playwright E2E suite (16 tests), axe-core accessibility audit with color-contrast enabled (0 violations), GitHub Actions CI |

---

## Table of contents

[Features](#features) · [Tech stack](#tech-stack) · [Architecture](#architecture) · [Order state machine](#order-state-machine) · [Project structure](#project-structure) · [Screenshots](#screenshots) · [Getting started](#getting-started) · [Environment variables](#environment-variables) · [Docker setup](#docker-setup) · [Database migration](#database-migration) · [Seed data](#seed-data) · [Running tests](#running-tests) · [API documentation](#api-documentation) · [Default development account](#default-development-account) · [CI/CD](#cicd)

---

## Features

**Customers**
- Browse the catalogue with **search, category and price filters, sorting and pagination**; product pages support clean slug-based URLs (`?slug=...`) with fallback to ID.
- Product detail pages with live stock levels ("In stock", "Only 3 left", "Out of stock").
- Register / log in with secure **HttpOnly cookies**, session refresh, password change on profile, and forgot password reset flow.
- Persistent **cart** with concurrency row-locking guards against stock races.
- **Checkout** that converts the cart into an order with a unique order number (`ORD-YYYYMMDD-XXXX`).
- Order history with the status of each order and the exact lines, names, prices and order numbers.

**Admins**
- Dashboard with stat cards and the latest orders.
- Product CRUD (including hiding a product without deleting it), category CRUD, user list with enable/disable.
- Order management with real-time **search** (by order number, customer email, username, or name), status transitions via strict state machine, and order details.
- Comprehensive **audit logs** tracking administrative product changes, order status transitions, and user account status updates.

**Engineering & Security**
- **Precise money representation**: Strict end-to-end pipeline: PostgreSQL (`NUMERIC(12, 2)`) → SQLAlchemy (`Decimal`) → Pydantic (`Decimal`) → JSON exact decimal strings (e.g. `{"price": "599.99"}`). Never serialized as JSON numbers, floats, or IEEE-754 approximations (e.g. `{"price": 599.99}` is rejected in favor of `"599.99"`).
- **HttpOnly cookie authentication** with `SameSite=Lax` and `Secure` (in production). Login and token refresh endpoints issue tokens via cookies and return safe metadata only (`expires_in`, `authenticated`) without exposing raw JWTs in JSON bodies or frontend JavaScript storage (`localStorage`/`sessionStorage`).
- **Refresh token rotation & revocation**: Refresh tokens are single-use and rotated on every `/auth/refresh` request; all tokens are revoked upon logout or password change.
- **Double-submit CSRF protection**: `csrf_token` cookie paired with `X-CSRF-Token` header on state-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`).
- **IP rate limiting** on authentication endpoints (5 attempts per minute with sliding window, `Retry-After` headers, and automatic reset upon successful login).
- **Security headers**: HSTS, Content-Security-Policy (CSP), X-Content-Type-Options: nosniff, X-Frame-Options: DENY, Referrer-Policy, and Permissions-Policy.
- **Order state machine**: validated transitions (`pending` → `processing` → `shipped` → `completed`, or `cancelled` from `pending`/`processing`) returning HTTP 409 on invalid transitions. Restocks inventory upon cancellation.
- **Cart concurrency row locking**: Strict lock ordering (`Cart` row lock via `SELECT ... FOR UPDATE`, followed by `Product`/`CartItem` lock) prevents race conditions and overselling.
- **Idempotent and repairable seed data**: Deterministic record keys (`SEED-ORD-0001` through `SEED-ORD-0004`) and audit markers ensure transaction-safe repairs without double-decrementing inventory.
- **Automated tests**: Playwright E2E suite and automated axe-core WCAG A/AA audits with `color-contrast` testing enabled (0 violations across all audited pages).

## Tech stack

Every dependency is here for a reason; nothing is installed "just in case".

| Package | Version | Why it is needed |
|---|---|---|
| **FastAPI** | 0.142.2 | Web framework: routing, dependency injection, automatic OpenAPI docs at `/docs` |
| **Uvicorn** | 0.54.0 | ASGI server that runs the app |
| **SQLAlchemy** | 2.1.2 | ORM and SQL toolkit (2.x typed `Mapped[...]` style) |
| **psycopg[binary]** | 3.3.6 | PostgreSQL driver (v3); the `binary` extra bundles `libpq`, so no system packages are needed |
| **Alembic** | 1.20.0 | Schema migrations — the only way tables are created |
| **Pydantic** | 2.13.5 | Request/response validation (a FastAPI core dependency) |
| **PyJWT** | 2.15.1 | Signing and verifying access tokens |
| **bcrypt** | 5.0.0 | Password hashing |
| **python-dotenv** | 1.2.4 | Loads `.env` for local runs |
| **python-multipart** | 0.0.32 | Required by FastAPI to read the OAuth2 login *form* |
| **email-validator** | 2.3.0 | Required by Pydantic's `EmailStr` |
| *pytest, pytest-cov, httpx* | 9.1.1 / 7.1.0 / 0.28.1 | Dev only: test runner, coverage, and the HTTP client behind FastAPI's `TestClient` |

Front end: **no dependencies at all** (no npm, no bundler). Infrastructure: PostgreSQL 17, Docker / Compose, nginx (static files), GitHub Actions.

## Architecture

```mermaid
flowchart TB
    subgraph Browser["Browser (static files, no build step)"]
        HTML["HTML pages"] --> JS["ES modules<br/>main · auth · products · cart · orders · admin"]
        JS --> APIJS["api.js<br/>fetch() with credentials & X-CSRF-Token"]
    end
    APIJS -->|"JSON over HTTP<br/>HttpOnly Cookies / Bearer JWT"| Routes
    subgraph FastAPI["FastAPI backend"]
        Middleware["SecurityHeadersMiddleware<br/>RateLimitMiddleware"] --> Routes
        Routes["api/routes<br/>HTTP, auth dependencies, response models"] --> Services["services<br/>business rules and transactions"]
        Services --> Models["models<br/>SQLAlchemy 2.x"]
        Schemas["schemas<br/>Pydantic v2"] -.-> Routes
    end
    Models --> PG[("PostgreSQL")]
    Alembic["Alembic migrations"] --> PG
```

- **Layers:** routes handle HTTP only; services hold the business rules and know nothing about HTTP (they raise domain errors that one handler turns into JSON); models map tables. This keeps every rule testable and in one place.
- **Authentication & CSRF:** 
  - Standard logins set `access_token` and `refresh_token` as `HttpOnly`, `SameSite=Lax` cookies, preventing JavaScript token exfiltration.
  - A double-submit `csrf_token` cookie is matched against the `X-CSRF-Token` request header on mutating HTTP requests (`POST`, `PUT`, `PATCH`, `DELETE`).
  - Dual-mode support: standalone API clients (e.g. mobile or tests) can alternatively supply `Authorization: Bearer <token>` without CSRF cookies.
- **Order creation** (`services/order_service.py`), all inside one transaction:
  1. lock the user's cart row (`SELECT … FOR UPDATE`) — a double submit queues here and finds an empty cart;
  2. lock the products in id order — no deadlocks, no overselling;
  3. verify every line against the *current* product (active? enough stock?) → `409` otherwise;
  4. generate unique human-readable `order_number` (`ORD-YYYYMMDD-XXXX`), snapshot `product_name` and `unit_price` into `order_items`, decrement stock, empty the cart, commit.
- **Cancelling** an order (admin) puts the items back into stock; a cancelled or completed order cannot transition to another state.
- **Deleting a product** is permanent. Past orders keep their lines (`order_items.product_id` becomes `NULL`, the name and price are snapshots). To merely hide a product, set `is_active` to `false`.
- **Front end:** every page is a static HTML file with `<body data-page="…">`; `main.js` renders the shared navbar/footer and starts the page's controller. All data comes from the real API through `api.js`, and everything interpolated into markup goes through an escaping `html` template tag, so product names or descriptions can never inject HTML.

## Order state machine

Orders follow a strict, validated finite state machine. Invalid status transitions raise an `InvalidStateTransitionError` resulting in an HTTP `409 Conflict`.

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> processing: Admin confirms
    pending --> cancelled: Cancelled (restocks inventory)
    processing --> shipped: Order dispatched
    processing --> cancelled: Cancelled (restocks inventory)
    shipped --> completed: Delivered to customer
    completed --> [*]: Terminal state
    cancelled --> [*]: Terminal state
```

| Current Status | Allowed Next Statuses | Notes |
|---|---|---|
| `pending` | `processing`, `cancelled` | Initial status on checkout |
| `processing` | `shipped`, `cancelled` | Being prepared for dispatch |
| `shipped` | `completed` | In transit to customer |
| `completed` | *(none)* | Terminal state |
| `cancelled` | *(none)* | Terminal state; restores reserved product stock back to inventory |

## Project structure

```text
arad-store/
├── backend/
│   ├── app/
│   │   ├── main.py                 # app factory, CORS, routers, lifespan
│   │   ├── seed.py                 # idempotent development data
│   │   ├── core/                   # config (env), database, security (JWT/bcrypt), errors, logging
│   │   ├── models/                 # SQLAlchemy models: user, category, product, cart, order, order_item
│   │   ├── schemas/                # Pydantic request/response models
│   │   ├── services/               # business logic (auth, catalogue, cart, orders, admin)
│   │   └── api/
│   │       ├── deps.py             # DB session, current user, admin guard
│   │       ├── router.py           # mounts everything under /api/v1
│   │       └── routes/             # auth, products, categories, cart, orders, admin, health
│   ├── alembic/                    # migration environment + versions/
│   ├── tests/                      # pytest suite (real PostgreSQL)
│   ├── Dockerfile · pytest.ini · alembic.ini
│   └── requirements.txt · requirements-dev.txt
├── frontend/
│   ├── index.html
│   ├── pages/                      # products, product, login, register, cart, orders, profile, admin, 404
│   ├── css/                        # style.css (tokens, layout) · components.css · responsive.css
│   ├── js/                         # config, session, api, ui, auth, products, cart, orders, admin(+admin/), main
│   └── img/                        # logo, placeholder and the product illustrations (SVG)
├── docker/nginx.conf               # serves the static frontend
├── docker-compose.yml              # postgres + backend + frontend
├── .github/workflows/ci.yml        # tests + Docker build + smoke test
├── docs/screenshots/
└── .env.example
```

## Screenshots

| Home | Shop (filters + 4-column grid) |
|---|---|
| ![Home page](docs/screenshots/home.png) | ![Shop page](docs/screenshots/shop.png) |
| **Product detail** | **Cart and checkout** |
| ![Product detail](docs/screenshots/product.png) | ![Cart](docs/screenshots/cart.png) |
| **My orders** | **Admin: dashboard** |
| ![Orders](docs/screenshots/orders.png) | ![Admin dashboard](docs/screenshots/admin-dashboard.png) |
| **Admin: products** | **Admin: product form** |
| ![Admin products](docs/screenshots/admin-products.png) | ![Admin product form](docs/screenshots/admin-product-form.png) |

| Mobile shop (1 column) | Mobile menu |
|---|---|
| <img src="docs/screenshots/mobile-shop.png" alt="Mobile shop page" width="300"> | <img src="docs/screenshots/mobile-menu.png" alt="Mobile navigation menu" width="300"> |

## Getting started

### Option A — Docker (recommended)

Requires Docker with Compose v2.

```bash
git clone <your-fork-or-clone-url> arad-store
cd arad-store
cp .env.example .env                           # every value in it is a development placeholder
docker compose up --build                      # first start builds the images and applies the migrations
```

In a second terminal, load the sample data:

```bash
docker compose exec backend python -m app.seed
```

Open:

| What | URL |
|---|---|
| Shop (frontend) | <http://localhost:5500> |
| Interactive API docs (Swagger UI) | <http://localhost:8000/docs> |
| Health checks | <http://localhost:8000/health> · <http://localhost:8000/health/db> |

Log in with the [development accounts](#default-development-account). Stop with `Ctrl+C`; `docker compose down` keeps your data, `docker compose down -v` deletes it.

> **Port 5432 already in use** (a local PostgreSQL)? The database port is only published for convenience: run `POSTGRES_PORT=5433 docker compose up --build`, or set `POSTGRES_PORT=5433` in `.env`.
> An error ending in **`is missing a value: Copy .env.example to .env first`** means the `cp` step was skipped.

### Option B — run it directly on your machine

Requires Python 3.12+ and a running PostgreSQL (15 or newer).

```bash
# 1. Create the database role and database (the role may create databases: the tests create their own)
sudo -u postgres psql -c "CREATE ROLE arad_user LOGIN PASSWORD 'change-me-db-password' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE arad_store OWNER arad_user;"

# 2. Configure (the defaults in .env.example match the two commands above)
cp .env.example .env

# 3. Install, migrate, seed, run
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload                          # API on http://localhost:8000
```

In another terminal, serve the frontend from the repository root:

```bash
python -m http.server 5500 --directory frontend         # shop on http://localhost:5500
```

`frontend/js/config.js` holds the API address (`http://localhost:8000/api/v1`); it is the only place to change if the API lives elsewhere. Add the frontend's origin to `CORS_ORIGINS` when you do.

## Environment variables

Configuration comes only from environment variables (a `.env` file is read for local development; real environment variables win). `.env` is git-ignored; `.env.example` documents everything.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development`, `test` or `production`. In production the app **refuses to start** with a placeholder or shorter-than-32-character `SECRET_KEY`, and the seed script refuses to run |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `DATABASE_URL` | *required* | SQLAlchemy URL, e.g. `postgresql+psycopg://user:password@localhost:5432/arad_store`. Under Compose it is built from the `POSTGRES_*` values |
| `SECRET_KEY` | *required* | Signs the JWTs. Generate one: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Lifetime of an access token |
| `CORS_ORIGINS` | *(empty)* | Comma-separated frontend origins allowed by CORS; empty means no cross-origin access |
| `BCRYPT_ROUNDS` | `12` | bcrypt cost factor (4–31) |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | — | Used by the `postgres` container (Compose requires them) |
| `POSTGRES_PORT` | `5432` | Host port the database is published on (`127.0.0.1` only) |
| `SEED_ADMIN_PASSWORD`, `SEED_CUSTOMER_PASSWORD` | — | Passwords of the seeded accounts; `python -m app.seed` stops if they are missing |
| `TEST_DATABASE_URL` | derived | Optional. By default the tests use `DATABASE_URL` with `_test` appended to the database name. The name **must** end in `_test` |

## Docker setup

```mermaid
flowchart LR
    Browser["Your browser"]
    subgraph Compose["docker compose (arad-store_default network)"]
        FE["frontend<br/>nginx:1.27-alpine<br/>serves ./frontend"]
        BE["backend<br/>python:3.12-slim, uvicorn<br/>runs as non-root uid 1000"]
        DB[("postgres<br/>postgres:17-alpine")]
        VOL[("volume<br/>postgres_data")]
    end
    Browser -->|"localhost:5500 static files"| FE
    Browser -->|"localhost:8000 /api/v1 JSON, CORS"| BE
    BE -->|"postgresql+psycopg, host postgres:5432"| DB
    DB --- VOL
```

| Service | Image | Notes |
|---|---|---|
| `postgres` | `postgres:17-alpine` | Data in the named volume `postgres_data`; healthcheck with `pg_isready`; port published on `127.0.0.1:${POSTGRES_PORT:-5432}` only |
| `backend` | built from `backend/Dockerfile` | Waits for a healthy database, runs `alembic upgrade head`, then starts uvicorn with `--reload`. The `backend/` folder is bind-mounted, so code edits reload instantly. Healthcheck calls `/health` |
| `frontend` | `nginx:1.27-alpine` | Serves `./frontend` read-only; unknown URLs get the styled 404 page |

The Compose build installs the dev dependencies (`INSTALL_DEV=true`) so the tests can run in the container. The **plain** image, built without that argument, contains runtime dependencies only:

```bash
docker build -t arad-store-backend backend        # lean image: no pytest, non-root user, healthcheck
```

Useful commands:

```bash
docker compose up --build -d                       # start in the background
docker compose logs -f backend                     # follow the API log
docker compose exec backend alembic upgrade head   # apply migrations manually (a no-op when up to date)
docker compose exec backend python -m app.seed     # load development data (safe to repeat)
docker compose exec backend pytest                 # run the test suite inside the container
docker compose down                                # stop; the data survives in postgres_data
docker compose down -v                             # stop and delete the database volume
```

> The Compose file is a **development** stack (code reload, bind mount, dev dependencies). For a real deployment use the plain image, drop `--reload` and the bind mount, set `APP_ENV=production` with a strong `SECRET_KEY`, and put HTTPS in front.

## Database migration

The schema is created **only by Alembic** — the application never calls `create_all()`. The Compose backend applies migrations on every start; to run them yourself:

```bash
docker compose exec backend alembic upgrade head      # with Docker
cd backend && alembic upgrade head                     # without Docker
```

Other handy commands (from `backend/`): `alembic current`, `alembic downgrade -1`, and after changing a model `alembic revision --autogenerate -m "describe the change"` — review the generated file before committing. A test fails whenever the models and the migrated schema drift apart.

### Schema

```mermaid
erDiagram
    USERS ||--o| CARTS : "has one"
    USERS ||--o{ ORDERS : places
    USERS ||--o{ REFRESH_TOKENS : has
    USERS ||--o{ PASSWORD_RESET_TOKENS : requests
    USERS ||--o{ AUDIT_LOGS : performs
    CATEGORIES ||--o{ PRODUCTS : contains
    CARTS ||--o{ CART_ITEMS : holds
    PRODUCTS ||--o{ CART_ITEMS : "appears in"
    ORDERS ||--|{ ORDER_ITEMS : contains
    PRODUCTS |o--o{ ORDER_ITEMS : "is snapshotted by"

    USERS {
        int id PK
        string email UK
        string username UK
        string hashed_password "bcrypt hash"
        string first_name
        string last_name
        string role "customer or admin"
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }
    CATEGORIES {
        int id PK
        string name UK
        string slug UK
        text description
        timestamptz created_at
    }
    PRODUCTS {
        int id PK
        string name
        string slug UK
        text description
        numeric price "NUMERIC(12,2)"
        int stock "never negative"
        string image_url "a URL, no upload"
        string brand
        int category_id FK
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }
    CARTS {
        int id PK
        int user_id FK, UK
        timestamptz created_at
        timestamptz updated_at
    }
    CART_ITEMS {
        int id PK
        int cart_id FK
        int product_id FK
        int quantity "at least 1"
    }
    ORDERS {
        int id PK
        string order_number UK
        int user_id FK
        numeric total_price "NUMERIC(12,2)"
        string status "pending, processing, shipped, completed, cancelled"
        timestamptz created_at
        timestamptz updated_at
    }
    ORDER_ITEMS {
        int id PK
        int order_id FK
        int product_id FK "NULL after the product is deleted"
        string product_name "snapshot"
        numeric unit_price "snapshot"
        int quantity
        numeric subtotal
    }
    REFRESH_TOKENS {
        int id PK
        int user_id FK
        string token_hash UK
        timestamptz expires_at
        bool revoked
        timestamptz created_at
    }
    PASSWORD_RESET_TOKENS {
        int id PK
        int user_id FK
        string token_hash UK
        timestamptz expires_at
        bool used
        timestamptz created_at
    }
    AUDIT_LOGS {
        int id PK
        int user_id FK
        string action
        string entity_type
        int entity_id
        json details
        string ip_address
        timestamptz created_at
    }
```

| Rule | Where it is enforced |
|---|---|
| A product appears **once per cart** | `UNIQUE (cart_id, product_id)` on `cart_items` |
| One cart per user | `UNIQUE (user_id)` on `carts` |
| Roles and order statuses are valid | `CHECK` constraints on `users.role` and `orders.status` |
| No negative prices, totals or stock; quantity ≥ 1 | `CHECK` constraints |
| A category with products cannot be deleted | `products.category_id` → `ON DELETE RESTRICT` (the API answers `409`) |
| A user with orders cannot be deleted | `orders.user_id` → `ON DELETE RESTRICT` |
| Deleting a product keeps order history | `order_items.product_id` → `ON DELETE SET NULL` |
| Carts clean up after themselves | `ON DELETE CASCADE` from users to carts and from carts/products to `cart_items` |

## Seed data

```bash
docker compose exec backend python -m app.seed        # with Docker
cd backend && python -m app.seed                       # without Docker
```

Creates **1 admin, 3 customers, 5 categories** (Graphics Cards, Processors, Memory, Storage, Gaming Accessories), **20 products** (one sold out, one low on stock, one hidden) and **4 sample orders** (`SEED-ORD-0001` through `SEED-ORD-0004`) in four different statuses (`pending`, `processing`, `shipped`, `completed`). Sample orders are created with deterministic order numbers and transitioned through the state machine. The script is idempotent (running it again changes nothing and retains existing orders), reads passwords from `SEED_ADMIN_PASSWORD` / `SEED_CUSTOMER_PASSWORD`, and refuses to run when `APP_ENV=production`. Every seeded product gets `image_url` pointing at `/images/products/<category>/<slug>.svg` — local SVG illustrations generated by `scratch/generate_images.py`. `backend/tests/test_seed.py` asserts each of those paths exists on disk, so a regenerated image set that drifts from the catalogue fails the suite instead of silently serving placeholders.

## Running tests

### Backend Pytest Suite

```bash
docker compose exec backend pytest                     # inside the container (Python 3.12)

# or on your machine (needs PostgreSQL and the dev dependencies):
cd backend && pytest --cov=app --cov-report=term-missing
```

The suite has **253 tests** and covers 97 % of the application code.

**How the tests stay safe and honest**
- They run against **real PostgreSQL**, never SQLite and never mocks of the database.
- The test database is separate: `DATABASE_URL` with `_test` appended (or `TEST_DATABASE_URL`). It is created automatically and the suite **refuses to start** if the name does not end in `_test` — your development data can never be touched.
- At the start of a session the schema is rebuilt **by the Alembic migrations**, so the migrations themselves are tested; every table is truncated after each test.
- A migration test fails when the models and the migrated schema differ, and another checks a full downgrade → upgrade round trip.
- Concurrency is tested for real: a test holds a row lock, fires two checkouts and releases the lock only when both are waiting. Cart concurrency and order creation row locks prevent overselling and duplicate orders.

| File | Covers |
|---|---|
| `test_auth.py` | register, login (email or username), `/me`, JWT edge cases (expired, forged, unsigned, deleted or disabled user), password hashing |
| `test_auth_enhanced.py` | HttpOnly cookies, refresh token rotation, logout revocation, password reset tokens |
| `test_rate_limit.py` | IP rate limiting on login/register/forgot-password, Retry-After header, counter reset on login |
| `test_products.py`, `test_categories.py` | listing, search (including slug lookup and pg_trgm), filters, sorting, pagination, admin CRUD, validation, permissions |
| `test_cart.py` | add / update / remove / clear, stock limits, isolation between users |
| `test_cart_concurrency.py` | concurrent cart modifications, row locking order, stock isolation |
| `test_orders.py` | checkout, order numbers, state machine transitions, empty cart, insufficient stock, snapshots, server-side prices, overselling and double submit |
| `test_admin.py` | access control for every admin endpoint, order search, order status rules and restocking, user enable/disable |
| `test_audit_logs.py` | audit logging on product CRUD, order status changes, user activation toggle, admin log query API |
| `test_health.py`, `test_config.py`, `test_migrations.py`, `test_seed.py`, `test_races.py` | health checks, security headers, CORS, error handling, settings validation, migrations, seed idempotency, unique-value races |

### End-to-End & Accessibility Tests (Playwright + axe-core)

Playwright runs automated browser tests against the live frontend and backend, covering the complete user journeys as well as automated WCAG 2.0/2.1 A+AA accessibility audits with `@axe-core/playwright`.

```bash
# Install dependencies & Playwright browser
npm install
npx playwright install --with-deps chromium

# Run the complete E2E and accessibility test suite
npm test

# Run only E2E functional tests
npm run test:e2e

# Run only axe-core accessibility tests (0 violations expected)
npm run test:a11y
```

| E2E Test Suite | Covers |
|---|---|
| `e2e/auth.spec.js` | User login, cookie authentication, logout, registration validation, forgot password flow |
| `e2e/products.spec.js` | Catalogue browsing, slug-based navigation, live search, category filtering |
| `e2e/cart.spec.js` | Adding products, quantity increment/decrement, cart item removal, subtotal computation |
| `e2e/checkout.spec.js` | Checkout flow, order placement, order confirmation view, customer orders history |
| `e2e/admin.spec.js` | Admin dashboard counters, order search, status transitions, audit log viewer |
| `e2e/accessibility.spec.js` | Full axe-core WCAG A/AA audits across Homepage, Login, Register, Product detail, Cart, and Admin dashboard |

## API documentation

Interactive docs: **<http://localhost:8000/docs>** (Swagger UI, with an *Authorize* button) · ReDoc at `/redoc` · schema at `/openapi.json`.

| Method | Path | Access | Description |
|---|---|---|---|
| `GET` | `/health` | Public | Liveness check |
| `GET` | `/health/db` | Public | Readiness check (database); `503` when PostgreSQL is unreachable |
| `POST` | `/api/v1/auth/register` | Public | Register a customer account (rate limited) |
| `POST` | `/api/v1/auth/login` | Public | Log in, receive HttpOnly `access_token` & `refresh_token` cookies and `csrf_token` cookie; returns safe metadata only (`authenticated`, `expires_in`) |
| `POST` | `/api/v1/auth/refresh` | Public | Rotate refresh token and issue new cookies; returns safe metadata only |
| `POST` | `/api/v1/auth/logout` | Authenticated | Revoke refresh token and clear auth cookies |
| `POST` | `/api/v1/auth/change-password` | Authenticated | Change password with current password verification |
| `POST` | `/api/v1/auth/forgot-password` | Public | Request a password reset token (rate limited) |
| `POST` | `/api/v1/auth/reset-password` | Public | Reset password using a valid reset token |
| `GET` | `/api/v1/auth/me` | Customer | Get the current authenticated user |
| `GET` | `/api/v1/products` | Public | List products: `search`, `category`, `category_id`, `brand`, `min_price`, `max_price`, `sort`, `page`, `limit` (default 12, max 100) |
| `GET` | `/api/v1/products/{product_id}` | Public | Get a product by ID |
| `GET` | `/api/v1/products/by-slug/{slug}` | Public | Get a product by unique slug |
| `POST` | `/api/v1/products` | Admin | Create a product (recorded in audit logs) |
| `PATCH` | `/api/v1/products/{product_id}` | Admin | Update a product (partial; recorded in audit logs) |
| `DELETE` | `/api/v1/products/{product_id}` | Admin | Delete a product (recorded in audit logs) |
| `GET` | `/api/v1/categories` | Public | List categories |
| `GET` | `/api/v1/categories/{category_id}` | Public | Get a category |
| `POST` | `/api/v1/categories` | Admin | Create a category |
| `PATCH` | `/api/v1/categories/{category_id}` | Admin | Update a category |
| `DELETE` | `/api/v1/categories/{category_id}` | Admin | Delete a category (`409` if it still has products) |
| `GET` | `/api/v1/cart` | Customer | Get my cart |
| `DELETE` | `/api/v1/cart` | Customer | Empty my cart |
| `POST` | `/api/v1/cart/items` | Customer | Add a product (increases the quantity if already there) |
| `PATCH` | `/api/v1/cart/items/{item_id}` | Customer | Set the quantity of a cart item |
| `DELETE` | `/api/v1/cart/items/{item_id}` | Customer | Remove an item |
| `POST` | `/api/v1/orders` | Customer | Place an order from my cart (no request body) |
| `GET` | `/api/v1/orders` | Customer | List my orders, newest first |
| `GET` | `/api/v1/orders/{order_id}` | Customer | Get one of my orders (`404` for anybody else's) |
| `GET` | `/api/v1/admin/stats` | Admin | Dashboard counters |
| `GET` | `/api/v1/admin/products` | Admin | List all products, including hidden ones |
| `GET` | `/api/v1/admin/orders` | Admin | List orders; filters: `status`, `search` (order number or user info) |
| `PATCH` | `/api/v1/admin/orders/{order_id}/status` | Admin | Change order status via state machine (recorded in audit logs) |
| `GET` | `/api/v1/admin/users` | Admin | List users; optional `search` |
| `PATCH` | `/api/v1/admin/users/{user_id}` | Admin | Enable or disable an account (recorded in audit logs) |
| `GET` | `/api/v1/admin/audit-logs` | Admin | Query audit log trail; filters: `action`, `entity_type`, pagination |

### Conventions

- **Paginated lists** return `{"items": [...], "total": 19, "page": 1, "limit": 12, "pages": 2}`.
- **Money** follows a strict pipeline: PostgreSQL `NUMERIC` → SQLAlchemy `Decimal` → Pydantic `Decimal` → JSON exact decimal string (e.g. `{"price": "599.99"}`). It is never returned as a JSON number or float (e.g. `599.99`).
- **Errors** are `{"detail": "message"}`; validation errors (`422`) are `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` without the submitted value. Status codes: `400` bad request, `401` missing/invalid token, `403` not allowed or account disabled, `404` not found, `409` conflict (duplicate, insufficient stock, category in use, invalid order state transition), `422` validation, `429` rate limit exceeded, `500` generic message only.

### Authentication flow

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (vanilla JS)
    participant A as FastAPI
    participant D as PostgreSQL
    B->>A: POST /auth/login (form: username, password)
    A->>D: find the user by email or username
    A->>A: bcrypt check (also run for unknown users)
    A->>D: persist RefreshToken record
    A-->>B: 200 OK + Set-Cookie: access_token, refresh_token (HttpOnly), csrf_token
    Note over B: Zero tokens stored in localStorage/sessionStorage.<br/>api.js reads csrf_token cookie and sends X-CSRF-Token header.
    B->>A: POST /orders  with  Cookie: access_token=... & X-CSRF-Token: ...
    A->>A: verify CSRF token and access token signature/expiration
    A->>D: load the user, check is_active and role
    A-->>B: 200 Order Created
    Note over B,A: On access token expiry (401), api.js transparently calls<br/>POST /auth/refresh using HttpOnly refresh_token cookie and retries original request.
```

### Try it with curl

```bash
# Register a customer (the role is always "customer", whatever the client sends)
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"jane@example.com","username":"jane","password":"S3cure-pass!","first_name":"Jane","last_name":"Doe"}'

# Log in: "username" accepts the email address or the username
curl -s -X POST http://localhost:8000/api/v1/auth/login -d 'username=jane@example.com&password=S3cure-pass!'
# Sets HttpOnly cookies and returns safe metadata only (authenticated, expires_in)

TOKEN=eyJ...    # paste the access_token value here

curl -s http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
curl -s "http://localhost:8000/api/v1/products?search=ryzen&max_price=300&sort=price_asc"
curl -s -X POST http://localhost:8000/api/v1/cart/items -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"product_id":6,"quantity":1}'
curl -s -X POST http://localhost:8000/api/v1/orders -H "Authorization: Bearer $TOKEN"
```

## Default development account

> ### ⚠️ Development only — never deploy these credentials
> `python -m app.seed` creates accounts whose passwords come from `SEED_ADMIN_PASSWORD` and `SEED_CUSTOMER_PASSWORD`. The values in `.env.example` are **public** (they are in this repository), so anyone can log in as the admin of an instance that uses them.
> Use them on your own machine only. Never run the seed on a shared or public server (the script refuses when `APP_ENV=production`), and if you ever do, change the passwords or delete the accounts immediately.

| Role | Email | Username | Password (default in `.env.example`) |
|---|---|---|---|
| Admin | `admin@example.com` | `admin` | `Admin12345!` |
| Customer | `alice@example.com` | `alice` | `Customer12345!` |
| Customer | `bob@example.com` | `bob` | `Customer12345!` |
| Customer | `carol@example.com` | `carol` | `Customer12345!` |

You can log in with either the email or the username. Changing the password variables in `.env` before seeding changes the passwords.

## CI/CD

`.github/workflows/ci.yml` runs on every **push** and **pull request**:

1. **Tests** (Python 3.12 and 3.13): checkout → set up Python → install `requirements-dev.txt` → `pytest --cov` against a PostgreSQL 17 service container. The service uses `trust` authentication, so there is no database password in the repository.
2. **Docker, Smoke Tests & Playwright E2E**: build the lean production image, then `cp .env.example .env`, `docker compose up -d --build --wait`, seed, smoke test (health checks, product list, the frontend, an admin login and `/admin/stats`), set up Node.js, install Playwright browsers, and execute the complete Playwright E2E and axe-core accessibility suite (`NO_WEBSERVER=1 npx playwright test`). Uploads HTML reports and traces on failure.

The workflow passes `actionlint`, and both jobs were rehearsed locally on a clean checkout.

## Future improvements

Deliberately **out of scope** for this version, in roughly the order to consider next:

- **Payments** — a payment gateway with webhooks (e.g., Stripe) to transition orders from pending to paid.
- **Email notifications** — asynchronous transactional email sending via SMTP / SendGrid for order confirmation and status changes.
- **Image upload** — S3/MinIO object storage and automatic thumbnail generation instead of image URLs.
- **Redis caching & distributed rate limiting** — cache the product catalogue and category list; store rate limiting across multi-replica deployments.
- **Reviews and ratings** on products.
- **Wishlist** per customer.
- **Advanced analytics** — revenue over time charts, top-selling categories, and low-stock alerts in the admin dashboard.
