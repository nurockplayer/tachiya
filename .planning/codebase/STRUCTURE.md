# Codebase Structure

**Analysis Date:** 2026-04-04

## Directory Layout

```
tachiya/                              # Repo root
├── api/                              # Tachiya FastAPI — custom business logic
│   ├── main.py                       # FastAPI app entry point
│   ├── pyproject.toml                # Python dependencies (uv)
│   ├── uv.lock                       # Locked dependency tree
│   └── Dockerfile                    # Production image (python:3.12-slim + uv)
├── backend/                          # Saleor media mount point only
│   └── media/                        # Saleor uploaded media (Docker volume)
├── dashboard/                        # Saleor Dashboard fork (Traditional Chinese)
│   ├── src/                          # Dashboard TypeScript source
│   │   ├── [module]/                 # Feature modules (products, orders, etc.)
│   │   │   ├── components/           # React components for this module
│   │   │   ├── views/                # Page-level view components
│   │   │   └── hooks/                # Module-specific hooks
│   │   ├── components/               # Shared components
│   │   ├── graphql/                  # Generated Apollo hooks + types
│   │   ├── hooks/                    # Global hooks
│   │   └── index.tsx                 # App entry point
│   ├── locale/                       # i18n JSON files (zh-Hant.json, etc.)
│   ├── nginx/                        # Nginx SPA serve config
│   │   └── default.conf              # Nginx config (try_files for SPA)
│   ├── playwright/                   # E2E test suite
│   └── translations/                 # (see also root translations/)
├── docs/                             # Design documents
│   ├── architecture-overview.md      # Multi-tenancy & Saleor App architecture
│   ├── product-decisions.md          # ADR-style product decisions
│   └── security-owasp.md            # OWASP Top 10 checklist for this stack
├── frontend/                         # Saleor Storefront fork (Next.js)
│   ├── src/
│   │   ├── app/                      # Next.js App Router root
│   │   │   ├── layout.tsx            # Root HTML shell
│   │   │   ├── page.tsx              # Root redirect (→ channel)
│   │   │   ├── [channel]/            # Channel-scoped shop routes
│   │   │   │   ├── layout.tsx        # Channel layout
│   │   │   │   └── (main)/           # Route group (shared nav/footer)
│   │   │   │       ├── page.tsx      # Homepage
│   │   │   │       ├── products/     # Product listing + detail
│   │   │   │       ├── categories/   # Category pages
│   │   │   │       ├── collections/  # Collection pages (per-streamer)
│   │   │   │       ├── cart/         # Cart
│   │   │   │       ├── account/      # Account, orders, addresses
│   │   │   │       ├── search/       # Search
│   │   │   │       ├── login/        # Login
│   │   │   │       └── signup/       # Registration
│   │   │   ├── checkout/             # Checkout flow (outside channel scope)
│   │   │   └── api/                  # Next.js API routes
│   │   │       └── auth/             # Auth endpoints (register, reset-password)
│   │   ├── checkout/                 # Checkout module (components, hooks, views)
│   │   ├── graphql/                  # Generated hooks + .graphql queries
│   │   ├── gql/                      # GraphQL client setup
│   │   ├── config/                   # App config (brand.ts, locale.ts)
│   │   ├── hooks/                    # Global hooks
│   │   ├── lib/                      # Utility libraries
│   │   │   ├── auth/                 # Auth helpers
│   │   │   ├── search/               # Search utilities
│   │   │   └── seo/                  # SEO / metadata helpers
│   │   ├── ui/                       # UI primitives
│   │   │   ├── atoms/                # Atomic components
│   │   │   └── components/           # Composed UI components
│   │   └── styles/                   # Global CSS
│   ├── next.config.js                # Next.js config (PPR, image, cache headers)
│   ├── Dockerfile                    # Standalone Next.js production image
│   └── .git/                         # Independent git repo (not tracked by tachiya)
├── translations/                     # Custom translation overrides
│   └── dashboard-zh-Hant.json        # Traditional Chinese dashboard strings
├── docker-compose.yml                # Production service definitions
├── docker-compose.override.yml       # Dev overrides (hot-reload, port exposure)
├── Makefile                          # Developer commands (setup, up, down, etc.)
├── .env.example                      # Required env vars template
├── .env                              # Local secrets (gitignored)
├── CLAUDE.md                         # Claude Code project guidelines
└── README.md                         # Developer quick-start
```

---

## Directory Purposes

**`api/`:**
- Purpose: All Tachiya-specific business logic not supported by Saleor out of the box
- Contains: FastAPI app, Python dependencies, Dockerfile
- Entry point: `api/main.py` (`app = FastAPI(...)`)
- Build: `uv` package manager; `uv.lock` must be committed
- Key files: `api/main.py`, `api/pyproject.toml`, `api/Dockerfile`

**`dashboard/`:**
- Purpose: Operator/admin UI — fork of upstream Saleor Dashboard
- Contains: TypeScript/React source, locale files, nginx config, Playwright tests
- Build: Compiled to static assets, served via Nginx SPA
- Published as: `ghcr.io/nurockplayer/tachiya-dashboard:3.22`
- Localization: `dashboard/locale/zh-Hant.json` (merged from `translations/`)
- Key files: `dashboard/src/index.tsx`, `dashboard/nginx/default.conf`

**`dashboard/src/[module]/`:**
- Pattern: Feature-first modules (e.g., `products/`, `orders/`, `channels/`, `discounts/`)
- Each module contains: `components/`, `views/`, `hooks/`, sometimes `ripples/` (GraphQL mutations)
- Modules present: `attributes`, `auth`, `categories`, `channels`, `collections`, `customers`, `discounts`, `extensions`, `featureFlags`, `files`, `giftCards`, `graphql`, `hooks`, `icons`, `modeling`, `modelTypes`, `orders`, `permissionGroups`, `products`, `productTypes`, `refundsSettings`, `search`, `services`, `shipping`, `siteSettings`, `staff`, `taxes`, `utils`, `warehouses`, `welcomePage`

**`frontend/`:**
- Purpose: Consumer storefront — independent git repo nested here
- Contains: Next.js App Router application
- Important: Has its own `.git` — commits here are NOT tracked by the parent repo
- Key files: `frontend/src/app/layout.tsx`, `frontend/src/app/page.tsx`, `frontend/next.config.js`

**`frontend/src/app/[channel]/`:**
- Purpose: All shop routes are scoped under a channel slug (e.g., `/default-channel/products`)
- The `(main)` route group wraps all standard shop pages with shared layout (nav, footer)
- Checkout lives outside the channel scope at `/checkout`

**`backend/`:**
- Purpose: Mount point for Saleor's uploaded media files (Docker volume `saleor_media`)
- Contains: Only `media/` directory — no source code
- Note: Saleor itself runs from official Docker image; no source is stored here

**`docs/`:**
- Purpose: Engineering design documents (ADRs, architecture, security)
- Not auto-generated; manually maintained
- Key files: `docs/product-decisions.md`, `docs/architecture-overview.md`, `docs/security-owasp.md`

**`translations/`:**
- Purpose: Override/supplement upstream Dashboard locale strings for Traditional Chinese
- Key file: `translations/dashboard-zh-Hant.json`

---

## Key File Locations

**Entry Points:**
- `api/main.py`: FastAPI app instantiation and route registration
- `dashboard/src/index.tsx`: Dashboard SPA bootstrap
- `frontend/src/app/layout.tsx`: Next.js root layout (HTML shell)
- `frontend/src/app/[channel]/layout.tsx`: Channel-scoped layout

**Configuration:**
- `.env.example`: All required environment variables with defaults
- `docker-compose.yml`: Service definitions, port bindings, volume mounts
- `docker-compose.override.yml`: Dev-specific overrides (hot-reload, exposed DB/cache ports)
- `Makefile`: Developer lifecycle commands
- `api/pyproject.toml`: FastAPI Python dependencies
- `frontend/next.config.js`: Next.js build config (PPR, image domains, cache headers)

**Design Decisions:**
- `docs/product-decisions.md`: Platform model, multi-tenancy approach, repo structure rationale
- `docs/architecture-overview.md`: Saleor App integration, multi-tenant design options
- `docs/security-owasp.md`: OWASP Top 10 checklist mapped to this specific stack

**GraphQL (generated):**
- `dashboard/src/graphql/hooks.generated.ts`: Apollo hooks for Dashboard
- `dashboard/src/graphql/types.generated.ts`: Dashboard GraphQL types
- `frontend/src/graphql/hooks.generated.ts`: Codegen hooks for Storefront
- `frontend/src/graphql/*.graphql`: Raw query/mutation definitions

---

## Naming Conventions

**Files (api/):**
- Python modules: `snake_case.py`
- Entry point: `main.py` (FastAPI convention)
- Future router files: `routers/orders.py`, `routers/webhooks.py` (anticipated pattern)

**Files (dashboard/ and frontend/):**
- React components: `PascalCase.tsx`
- Utility/hook files: `camelCase.ts`
- Generated files: `*.generated.ts` (do not edit manually)
- GraphQL definitions: `PascalCase.graphql`

**Directories (dashboard/src/):**
- Feature modules: `camelCase` (e.g., `products`, `giftCards`, `featureFlags`)
- Within modules: `components/`, `views/`, `hooks/` (lowercase)

**Directories (frontend/src/):**
- Route segments: `[param]` for dynamic, `(group)` for route groups, `_name` for private
- Module directories: `camelCase` (e.g., `checkout`, `gql`, `lib`)
- UI layer: `ui/atoms/`, `ui/components/`

---

## Where to Add New Code

**New FastAPI endpoint (business logic):**
- Create router file: `api/routers/<domain>.py`
- Register in: `api/main.py` with `app.include_router(...)`
- Example domains: `api/routers/webhooks.py`, `api/routers/discounts.py`, `api/routers/revenue.py`

**New FastAPI dependency (auth, DB session):**
- Create: `api/dependencies.py` or `api/deps/<name>.py`

**New Dashboard feature module:**
- Create: `dashboard/src/<moduleName>/`
- Include: `components/`, `views/`, `hooks/` subdirectories
- Register routes in: `dashboard/src/index.tsx`

**New Storefront page:**
- Create: `frontend/src/app/[channel]/(main)/<page-name>/page.tsx`
- Shared layout already applies via `(main)/layout.tsx`

**New Storefront API route:**
- Create: `frontend/src/app/api/<route-name>/route.ts`

**New GraphQL query (Storefront):**
- Add `.graphql` file to: `frontend/src/graphql/`
- Run codegen to regenerate: `frontend/src/graphql/hooks.generated.ts`

**New GraphQL query (Dashboard):**
- Add `.graphql` file under relevant `dashboard/src/<module>/`
- Regenerate: `dashboard/src/graphql/hooks.generated.ts`

**Design documents:**
- All engineering ADRs and architecture notes: `docs/`
- Format: Markdown, options-considered + decision + rationale pattern (see `docs/product-decisions.md`)

**Translation overrides:**
- Dashboard zh-Hant strings: `translations/dashboard-zh-Hant.json`

---

## Special Directories

**`frontend/` (nested independent git repo):**
- Purpose: Storefront source code (Next.js fork)
- Generated: No
- Committed: The directory exists in this repo, but its contents are managed by `frontend/.git`; changes to `frontend/` do not appear in `tachiya` git status
- Note: Develop with a separate VSCode workspace or Claude Code session scoped to `frontend/`

**`backend/media/`:**
- Purpose: Docker volume mount for Saleor uploaded images and files
- Generated: By Saleor at runtime
- Committed: No — the `media/` directory is present but empty; actual files come from Docker volume `saleor_media`

**`api/__pycache__/`:**
- Purpose: Python bytecode cache
- Generated: Yes (automatically by Python)
- Committed: No (gitignored)

**`api/.venv/`:**
- Purpose: Local Python virtualenv created by `uv`
- Generated: Yes (`uv sync`)
- Committed: No (gitignored)

**`.planning/`:**
- Purpose: GSD planning documents (codebase maps, phase plans)
- Generated: By GSD map-codebase / plan-phase commands
- Committed: Yes

---

*Structure analysis: 2026-04-04*
