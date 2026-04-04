# Architecture

**Analysis Date:** 2026-04-04

## Pattern Overview

**Overall:** Headless e-commerce with layered extension pattern

Tachiya is a live-streaming e-commerce platform built on Saleor (headless GraphQL engine) extended by a custom FastAPI service. Saleor is never modified — all custom business logic lives in the FastAPI layer (`api/`). The system connects to an external sister system, Tachigo (separate repo), which handles Twitch identity and loyalty tokens.

**Key Characteristics:**
- Saleor is consumed as a black-box Docker image (no source modifications)
- All custom logic (revenue sharing, streamer bonuses, discount generation) is externalized into `api/`
- The Dashboard is a fork of the upstream Saleor Dashboard, customized for Traditional Chinese and published as a separate Docker image
- The Storefront (`frontend/`) is an independent git repository nested inside this repo; it is not tracked by this repo's git

---

## Service Topology

```
Browser
 ├── Storefront     :3000   (Next.js, consumer-facing)
 └── Dashboard      :9000   (Saleor Dashboard fork, admin)
          │ GraphQL
          ▼
     Saleor Core    :8000   (Django + GraphQL, official image)
          │ Webhook / GraphQL API
          ▼
     Tachiya API    :8001   (FastAPI, custom business logic)

Infrastructure (Docker internal, no external exposure in prod):
  PostgreSQL        :5432   (shared DB for Saleor + Tachiya API)
  Valkey/Redis      :6379   (cache + Celery broker/result)
  Mailpit           :8025   (email testing, dev only)

External system (separate repo — tachigo):
  Go backend        ----→   Tachiya API  (HTTP, service token auth)
  Twitch Extension  ----→   Go backend
```

**Port map:**
| Service | Port | Notes |
|---|---|---|
| Saleor Core | 8000 | GraphQL at `/graphql/` |
| Tachiya API | 8001 | FastAPI OpenAPI at `/docs` |
| Dashboard | 9000 | Nginx-served SPA |
| Storefront | 3000 | Next.js, optional profile |
| Mailpit UI | 8025 | Dev email inbox |
| PostgreSQL | 5432 | Exposed in dev override only |
| Valkey | 6379 | Exposed in dev override only |

---

## Layers

**Saleor Core:**
- Purpose: All e-commerce primitives — products, orders, checkout, payment, inventory, accounts
- Image: `ghcr.io/saleor/saleor:3.22` (official, not forked)
- Location: No source in repo; runtime only via Docker
- Database: PostgreSQL (shared volume `postgres_data`)
- Async work: `saleor-worker` container runs Celery with `-B` (beat scheduler)
- Config: `.env` file at repo root
- Depends on: PostgreSQL (`db`), Valkey (`cache`)

**Tachiya API:**
- Purpose: Custom extension layer — revenue sharing, streamer perks, webhook handling, discount code generation, token redemption bridge from Tachigo
- Location: `api/`
- Runtime: Python 3.12, FastAPI, served by Uvicorn on port 8001
- Package manager: `uv` (lockfile at `api/uv.lock`)
- Key dependency: `httpx` for calling Saleor GraphQL
- Current state: Skeleton only — `api/main.py` has a single `/health` endpoint
- Depends on: PostgreSQL (`db`), Valkey (`cache`), Saleor GraphQL (internal HTTP)

**Saleor Dashboard:**
- Purpose: Admin UI for platform operators and agency managers
- Location: `dashboard/` (fork of `saleor/dashboard`, built locally)
- Image: `ghcr.io/nurockplayer/tachiya-dashboard:3.22` (custom GHCR image)
- Served by: Nginx on port 9000 (SPA with `try_files` fallback)
- Localization: Traditional Chinese (`zh-Hant.json` in `dashboard/locale/`)
- Custom translations: `translations/dashboard-zh-Hant.json`
- API target: `DASHBOARD_API_URL` → Saleor GraphQL

**Storefront (Frontend):**
- Purpose: Consumer-facing shopping experience
- Location: `frontend/` (independent git repo, fork of `nurockplayer/storefront`)
- Framework: Next.js (App Router), TypeScript
- Routing: Channel-based — all shop routes under `src/app/[channel]/(main)/`
- Key routes: `/products`, `/categories/[slug]`, `/collections/[slug]`, `/cart`, `/checkout`, `/account`
- GraphQL: Codegen-generated hooks in `src/graphql/`, `.graphql` files beside them
- API target: `NEXT_PUBLIC_SALEOR_API_URL` → Saleor GraphQL
- Docker profile: `frontend` (opt-in, `make frontend`)

---

## Data Flow

**Consumer Purchase Flow:**
1. Storefront (`frontend/`) fetches product data via GraphQL → Saleor `:8000/graphql/`
2. User adds to cart → Saleor Checkout mutation
3. User applies discount/voucher code → Saleor `checkoutAddPromoCode` mutation
4. Checkout completes → Saleor creates Order
5. Saleor fires async webhook → Tachiya API `:8001` (e.g., `ORDER_CREATED`)
6. Tachiya API calculates revenue share using product metadata (`streamer: <id>`) and records split

**Token Redemption Flow (Tachigo → Tachiya):**
```
Twitch viewer accumulates tokens in Tachigo extension
  → Tachigo Go backend validates token balance
  → HTTP POST to Tachiya API `:8001` (with service token auth)
  → Tachiya API burns token, generates discount voucher via Saleor GraphQL
  → Returns voucher code to Go backend → viewer
  → Viewer applies code at Saleor checkout
```

**Admin Management Flow:**
- Platform admin / agency staff → Dashboard `:9000`
- Dashboard calls Saleor GraphQL directly
- No Tachiya API involvement in Dashboard flows (by design; future agency portal may use FastAPI)

---

## Key Design Decisions

**Multi-tenancy: Collection + Metadata (not Channels)**
- One Saleor Channel for unified checkout
- Each streamer has one Saleor Collection (independent page/identity)
- Products tagged with metadata `streamer: <id>` for revenue split attribution
- Decision rationale in `docs/product-decisions.md`

**Saleor as Black Box**
- Saleor source never modified; always run from official image
- Custom logic isolated in `api/` to avoid fork maintenance burden
- Tachiya API is the "extension seam" — all customization routes through it
- Decision rationale: `docs/product-decisions.md` (三服務拆法)

**Three-Service Backend Split**
- Saleor: e-commerce core
- Go (Tachigo, external repo): Twitch identity + loyalty token system
- FastAPI (this repo, `api/`): Saleor extension — discounts, revenue share, webhooks
- These three never merge; communicate only over HTTP/webhooks

**Dashboard Fork Strategy**
- Dashboard is forked (not submoduled) to enable Traditional Chinese localization
- Published as a custom GHCR image; pulled by docker-compose like any other image
- Translation source maintained in `translations/dashboard-zh-Hant.json`

---

## Communication Patterns

**GraphQL (Saleor ↔ Frontend/Dashboard):**
- All frontend/dashboard communication with Saleor is via GraphQL
- Queries/mutations use typed codegen hooks (`hooks.generated.ts`)
- Fragments defined separately, composed in queries

**Webhooks (Saleor → Tachiya API):**
- Saleor fires async webhooks to `api/` on business events (orders, etc.)
- Must be verified with `Saleor-Signature` HMAC header (documented in `docs/security-owasp.md`)
- Signature verification pattern: `hmac.new(secret, payload, sha256)`

**Service-to-Service (Tachigo → Tachiya API):**
- Bearer token in `Authorization` header
- Token stored in environment variable, not URL parameter
- Tachiya API port not exposed publicly in production (docker-compose network isolation)

**Saleor App Integration (planned):**
- `manifest.json` for app registration
- Token exchange handshake on install
- App Bridge (`postMessage`) for embedding UI in Dashboard via iframe

---

## Error Handling

**FastAPI layer:**
- Exception handlers should wrap all errors (stack traces must not reach clients)
- Financial operations (token burn + voucher creation) must be atomic with rollback on failure
- Idempotency key required on token redemption endpoints to prevent double-issue

**Saleor layer:**
- Handled by upstream Django; errors returned as GraphQL `errors` array

---

## Cross-Cutting Concerns

**Authentication:**
- Consumer auth: Saleor accounts (JWT), managed by Storefront
- Admin auth: Saleor staff accounts, managed by Dashboard
- Service auth (Tachigo→Tachiya): Bearer token with expiry, rotated manually
- Saleor webhook auth: HMAC signature verification

**Caching:**
- Valkey (Redis-compatible) shared between Saleor (Django cache) and Celery
- Frontend uses Next.js `cacheComponents` (Partial Prerendering) and per-route cache headers
- FastAPI layer: caching recommended for frequent GraphQL calls (not yet implemented)

**Email:**
- Dev: Mailpit SMTP at `mailpit:1025`, UI at `:8025`
- Prod: Real SMTP via `EMAIL_URL` environment variable

---

*Architecture analysis: 2026-04-04*
