# Arad Store

**A full-stack online shop for PC components and gaming gear** — graphics cards, processors, memory, storage and accessories.
FastAPI + PostgreSQL on the back end, plain HTML / CSS / vanilla JavaScript on the front end, everything runnable with one `docker compose up`.

| | |
|---|---|
| **Back end** | Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 17, JWT + bcrypt |
| **Front end** | HTML5, CSS3 (own design system with CSS variables), ES-module vanilla JS — no framework, no build step |
| **Quality** | 215 pytest tests on a real PostgreSQL database (99 % coverage), GitHub Actions CI, axe-core accessibility audit with 0 violations |

---

## Table of contents

[Features](#features) · [Tech stack](#tech-stack) · [Architecture](#architecture) · [Project structure](#project-structure) · [Screenshots](#screenshots) · [Getting started](#getting-started) · [Environment variables](#environment-variables) · [Docker setup](#docker-setup) · [Database migration](#database-migration) · [Seed data](#seed-data) · [Running tests](#running-tests) · [API documentation](#api-documentation) · [Default development account](#default-development-account) · [CI/CD](#cicd) · [Future improvements](#future-improvements)

---

## Features

**Customers**
- Browse the catalogue with **search, category and price filters, sorting and pagination** (state is kept in the URL, so filtered views can be shared).
- Product detail pages with live stock levels ("In stock", "Only 3 left", "Out of stock").
- Register / log in (with *Remember me*), a persistent **cart**, and **checkout** that turns the cart into an order.
- Order history with the status of each order and the exact lines, names and prices that were bought.

**Admins**
- Dashboard with stat cards and the latest orders.
- Product CRUD (including hiding a product without deleting it), category CRUD, user list with enable/disable.
- Order list with status filter, status changes (pending → processing → shipped → completed, or cancelled) and order details.

**Engineering**
- Prices are `Decimal` / `NUMERIC(12,2)` end to end — never floats.
- **Order creation is one database transaction** with row locks: the server recomputes prices and totals, checks stock, decrements it and empties the cart. The client cannot send a price, a total or a user id. Two shoppers racing for the last unit, or a double-clicked *Place order*, cannot oversell or duplicate (covered by tests that make the overlap real).
- Passwords are hashed with bcrypt; JWTs carry `sub` and `exp`; secrets come only from environment variables.
- Uniform JSON errors with safe messages (no SQL, no stack traces, validation errors never echo the submitted value).
- Frontend states for **Loading / Empty / Error / Success** on every data view; responsive grid (4 columns desktop, 2 tablet, 1 mobile) and a mobile menu; keyboard and screen-reader friendly.

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
        JS --> APIJS["api.js<br/>the only code that calls fetch()"]
    end
    APIJS -->|"JSON over HTTP<br/>Authorization: Bearer JWT"| Routes
    subgraph FastAPI["FastAPI backend"]
        Routes["api/routes<br/>HTTP, auth dependencies, response models"] --> Services["services<br/>business rules and transactions"]
        Services --> Models["models<br/>SQLAlchemy 2.x"]
        Schemas["schemas<br/>Pydantic v2"] -.-> Routes
    end
    Models --> PG[("PostgreSQL")]
    Alembic["Alembic migrations"] --> PG
```

- **Layers:** routes handle HTTP only; services hold the business rules and know nothing about HTTP (they raise domain errors that one handler turns into JSON); models map tables. This keeps every rule testable and in one place.
- **Order creation** (`services/order_service.py`), all inside one transaction:
  1. lock the user's cart row (`SELECT … FOR UPDATE`) — a double submit queues here and finds an empty cart;
  2. lock the products in id order — no deadlocks, no overselling;
  3. verify every line against the *current* product (active? enough stock?) → `409` otherwise;
  4. snapshot `product_name` and `unit_price` into `order_items`, decrement stock, empty the cart, commit.
- **Cancelling** an order (admin) puts the items back into stock; a cancelled order is final and a completed one cannot be cancelled.
- **Deleting a product** is permanent. Past orders keep their lines (`order_items.product_id` becomes `NULL`, the name and price are snapshots). To merely hide a product, set `is_active` to `false`.
- **CORS** origins come from `CORS_ORIGINS`; tokens travel in the `Authorization` header (no cookies), so there is no CSRF surface.
- **Front end:** every page is a static HTML file with `<body data-page="…">`; `main.js` renders the shared navbar/footer and starts the page's controller. All data comes from the real API through `api.js`, and everything interpolated into markup goes through an escaping `html` template tag, so product names or descriptions can never inject HTML.

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

Creates **1 admin, 3 customers, 5 categories** (Graphics Cards, Processors, Memory, Storage, Gaming Accessories), **20 products** (one sold out, one low on stock, one hidden) and **4 sample orders** in four different statuses. Sample orders are placed through the real order service, so stock and totals are consistent. The script is idempotent (running it again changes nothing), reads the passwords from `SEED_ADMIN_PASSWORD` / `SEED_CUSTOMER_PASSWORD`, and refuses to run when `APP_ENV=production`. Product images are local SVG illustrations under `frontend/img/products/`; the API itself only stores image URLs, so any hosting works.

## Running tests

```bash
docker compose exec backend pytest                     # inside the container (Python 3.12)

# or on your machine (needs PostgreSQL and the dev dependencies):
cd backend && pytest --cov=app --cov-report=term-missing
```

The suite has **215 tests** and covers 99 % of the application code.

**How the tests stay safe and honest**
- They run against **real PostgreSQL**, never SQLite and never mocks of the database.
- The test database is separate: `DATABASE_URL` with `_test` appended (or `TEST_DATABASE_URL`). It is created automatically and the suite **refuses to start** if the name does not end in `_test` — your development data can never be touched.
- At the start of a session the schema is rebuilt **by the Alembic migrations**, so the migrations themselves are tested; every table is truncated after each test.
- A migration test fails when the models and the migrated schema differ, and another checks a full downgrade → upgrade round trip.
- Concurrency is tested for real: a test holds a row lock, fires two checkouts and releases the lock only when both are waiting. Removing the `FOR UPDATE` locks from the order service makes these tests fail (checked by hand), so they really guard against overselling and duplicate orders. Similar tests make two clients collide on a unique value (email, slug, category, first cart) and expect a clean `409`.

| File | Covers |
|---|---|
| `test_auth.py` | register, login (email or username), `/me`, JWT edge cases (expired, forged, unsigned, deleted or disabled user), password hashing |
| `test_products.py`, `test_categories.py` | listing, search, filters, sorting, pagination, admin CRUD, validation, permissions |
| `test_cart.py` | add / update / remove / clear, stock limits, isolation between users |
| `test_orders.py` | checkout, empty cart, insufficient stock (all-or-nothing), snapshots, server-side prices, overselling and double submit |
| `test_admin.py` | access control for every admin endpoint, order status rules and restocking, user enable/disable |
| `test_health.py`, `test_config.py`, `test_migrations.py`, `test_seed.py`, `test_races.py` | health checks, CORS, error handling, settings validation, migrations, seed, unique-value races |

**Frontend checks.** The pages were verified during development in a real browser (Playwright): customer and admin flows against the live API, the Loading / Empty / Error states (by delaying, failing and aborting requests), responsive layouts at three widths, expired-token handling, XSS attempts, and an axe-core audit (WCAG 2.0/2.1 A + AA and best practices) over every page at two widths: **0 violations**. Those browser scripts are not part of this repository.

## API documentation

Interactive docs: **<http://localhost:8000/docs>** (Swagger UI, with an *Authorize* button) · ReDoc at `/redoc` · schema at `/openapi.json`.

| Method | Path | Access | Description |
|---|---|---|---|
| `GET` | `/health` | Public | Liveness check |
| `GET` | `/health/db` | Public | Readiness check (database); `503` when PostgreSQL is unreachable |
| `POST` | `/api/v1/auth/register` | Public | Register a customer account |
| `POST` | `/api/v1/auth/login` | Public | Log in (OAuth2 form) and get an access token |
| `GET` | `/api/v1/auth/me` | Customer | Get the current user |
| `GET` | `/api/v1/products` | Public | List products: `search`, `category`, `category_id`, `brand`, `min_price`, `max_price`, `sort`, `page`, `limit` (default 12, max 100) |
| `GET` | `/api/v1/products/{product_id}` | Public | Get a product |
| `POST` | `/api/v1/products` | Admin | Create a product |
| `PATCH` | `/api/v1/products/{product_id}` | Admin | Update a product (partial) |
| `DELETE` | `/api/v1/products/{product_id}` | Admin | Delete a product |
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
| `GET` | `/api/v1/admin/orders` | Admin | List all orders; optional `status` filter |
| `PATCH` | `/api/v1/admin/orders/{order_id}/status` | Admin | Change an order's status |
| `GET` | `/api/v1/admin/users` | Admin | List users; optional `search` |
| `PATCH` | `/api/v1/admin/users/{user_id}` | Admin | Enable or disable an account |

*Public* needs no token, *Customer* needs any valid token, *Admin* needs a token of an admin. Beyond the required endpoints this API adds `/admin/products` (hidden products), `/admin/stats` (dashboard), `PATCH /admin/users/{id}` (disable accounts) and `/health/db`.

### Conventions

- **Paginated lists** return `{"items": [...], "total": 19, "page": 1, "limit": 12, "pages": 2}`.
- **Money** is a decimal on the server and a JSON number in responses (`599.99`).
- **Errors** are `{"detail": "message"}`; validation errors (`422`) are `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` without the submitted value. Status codes: `400` bad request, `401` missing/invalid token, `403` not allowed or account disabled, `404` not found, `409` conflict (duplicate, insufficient stock, category in use, final order status), `422` validation, `500` generic message only.

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
    A-->>B: 200 {access_token, token_type, expires_in}
    Note over B: JWT claims: sub (user id), iat, exp.<br/>Stored in localStorage (Remember me) or sessionStorage.
    B->>A: GET /orders  with  Authorization: Bearer token
    A->>A: verify signature and exp
    A->>D: load the user, check is_active and role
    A-->>B: 200 data
    Note over B,A: Expired or invalid token: 401. api.js clears the session<br/>and sends protected pages to the login page.
```

### Try it with curl

```bash
# Register a customer (the role is always "customer", whatever the client sends)
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"jane@example.com","username":"jane","password":"S3cure-pass!","first_name":"Jane","last_name":"Doe"}'

# Log in: "username" accepts the email address or the username
curl -s -X POST http://localhost:8000/api/v1/auth/login -d 'username=jane@example.com&password=S3cure-pass!'
# {"access_token":"eyJ...","token_type":"bearer","expires_in":3600}

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
2. **Docker**: build the lean production image, then `cp .env.example .env`, `docker compose up -d --build --wait`, seed, and a smoke test (health checks, product list, the frontend, an admin login and `/admin/stats`). Logs are printed when something fails, and the stack is always torn down.

The workflow passes `actionlint`, and both jobs were rehearsed locally on a clean checkout (both Python versions with a password-less PostgreSQL; the Docker steps executed straight from the YAML file).

## Future improvements

Deliberately **out of scope** for this version, in roughly the order I would add them:

- **Payments** — a payment gateway with webhooks (the current checkout takes no money).
- **Email notifications** — order confirmation and status-change emails; password reset.
- **Image upload** — object storage and thumbnails instead of image URLs.
- **Redis caching** — cache the product catalogue and category list; also a store for rate limiting.
- **Reviews and ratings** on products.
- **Wishlist** per customer.
- **Advanced analytics** — revenue over time, best sellers, stock alerts in the admin dashboard.
- Security hardening: refresh tokens and logout/revocation, login rate limiting, httpOnly-cookie sessions, password change.
- Browser end-to-end tests (Playwright) and an accessibility check in CI.
- Switch the test client from `httpx` to `httpx2` when Starlette drops its `httpx` fallback (it currently only emits a deprecation warning, which `pytest.ini` filters).
