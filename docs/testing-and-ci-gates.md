# Testing And CI Gates

本文定義 Tachiya 目前的測試基線、現有 CI 現況、各 gate 的 scope，以及還沒補完的缺口。目標不是把所有檢查塞進同一個 workflow，而是讓 root repo、Storefront repo 與跨 repo 邊界各自有清楚責任。

## 原則

- 改了 request schema，就要有對應 router / route test。
- 改了 domain 邏輯，就要有對應 service test。
- 改了部署或 runtime 邊界，就要有 build-time 或 env validation gate。
- 文件不是免測區；只要文件宣告某個欄位是產品契約，實作與測試就必須能對上。

## 現況

### Tachiya root repo

目前 root repo 已有的驗證習慣：

- backend focused pytest
- backend full pytest
- `python -m compileall api`
- `docker compose build api dashboard` 或等價 image build
- `git diff --check`

目前 root repo 已追蹤並正式生效的 CI gate：

- [`.github/workflows/api-ci.yml`](../.github/workflows/api-ci.yml)
  - scope: `api/**`、API contract docs、workflow regression、docker compose 相關 root 檔
  - checks: `git diff --check`、`pytest`、`ruff check`、`ruff format --check`、`python -m compileall`、API image build

目前 root repo 明確不再依賴 weekly release workflow，也不把任何本機未追蹤的 workflow 草案算進正式 gate。`frontend/` 在架構上是本機 checkout 目錄；正式 Storefront repo 是 `nurockplayer/storefront`，因此 frontend 的 PR CI 由 Storefront repo 自己擁有，不在 root repo duplicated 一套。

Root repo 目前另有 cross-repo contract gate：

- [`.github/workflows/cross-repo-contract.yml`](../.github/workflows/cross-repo-contract.yml)
  - scope: Tachiya API contract docs、Tachiya router surface、Storefront develop consumer helper / tests
  - checks: checkout `nurockplayer/storefront@develop`，執行 `.github/workflow-tests/cross-repo-contract.test.mjs`

### Storefront repo

Storefront 目前有明確可執行的本地驗證指令：

- `pnpm run lint`
- `pnpm run test:run`
- `SKIP_CODEGEN=1 pnpm run build`

Storefront repo 目前已追蹤的核心 workflow：

- `ci/storefront`：diff whitespace、lint、unit tests、Playwright browser smoke、build
- `PR Scope Police`
- `Dependabot Auto Merge`
- `Notify PRs needing rebase`
- dependency / inventory 類 workflow 由 Storefront repo 自己管理

目前缺口：

- Tachiya 特有 route hardening 與 API contract drift 已有 static cross-repo sanity gate，但尚未升級成 mock server / fixture-level runtime contract smoke。
- Storefront authenticated points balance 仍主要由 unit / component tests 保護，E2E 目前只覆蓋未登入 fallback。

## 現有測試對應

### Backend request / router contracts

- [api/tests/test_coupon_internal_secret.py](../api/tests/test_coupon_internal_secret.py)
- [api/tests/test_points_router.py](../api/tests/test_points_router.py)
- [api/tests/test_referral_service.py](../api/tests/test_referral_service.py)
- [api/tests/test_streamers_router.py](../api/tests/test_streamers_router.py)

保護的內容：

- strict integer payload rejection
- blank string normalization
- webhook signature / secret gate
- endpoint response shape

### Backend domain / service logic

- [api/tests/test_points_service.py](../api/tests/test_points_service.py)
- [api/tests/test_revenue_share_service.py](../api/tests/test_revenue_share_service.py)
- [api/tests/test_streamer_service.py](../api/tests/test_streamer_service.py)

保護的內容：

- points FIFO balance 與 expired credit exposure
- coupon / referral / revenue share 的業務規則
- streamer profile 與 assignment 行為

### Frontend route / runtime contracts

- `src/app/api/revalidate/route.test.ts`
- `src/app/api/auth/register/route.test.ts`
- `src/app/api/auth/reset-password/route.test.ts`
- `src/app/api/auth/set-password/route.test.ts`
- `src/lib/graphql.test.ts`
- `src/lib/tachiya-points.test.ts`
- `src/checkout/lib/tachiya-coupons.test.ts`
- `src/lib/tachiya-streamer-catalog.test.ts`
- `tests/e2e/storefront-smoke.spec.ts`

保護的內容：

- auth payload trim / reject blank
- revalidate webhook 與 manual trigger sanitize / fallback
- GraphQL runtime integer env fallback / clamp

## 目前 required gates

### Root repo API / docs gate

所有修改 `api/`、API contract docs、`docker-compose` 或 API 相關 workflow 的 PR，至少應該跑：

- `cd api && uv run --group dev pytest`
- `cd api && python -m compileall config.py database.py main.py security.py models routers services tests`
- `docker compose build api dashboard`
- `git diff --check`
- `node --test .github/workflow-tests/*.test.mjs`（若有改 workflow / workflow tests）

### Storefront PR gate

所有修改獨立 `storefront` repo 自身檔案的 PR，至少應該跑：

- `pnpm install --frozen-lockfile`
- `pnpm run lint`
- `pnpm run test:run`
- `SKIP_CODEGEN=1 pnpm run build`
- `git diff --check`

### Docs-only gate

純文件 PR 不需要硬跑整套 backend / frontend full suite，但至少應該跑：

- `git diff --check`
- `node --test .github/workflow-tests/*.test.mjs`（若文件同步改到 workflow / CI gate）
- 檢查文件引用的檔名、issue / PR 編號與 workflow 現況是否正確

如果文件宣告的是新的產品契約，而 repo 內還沒有對應 test，這不應視為可 merge 的 docs-only 變更，而應拆出補測工作。

## 目前 workflow 拆法

### Tachiya root repo

- `ci/api`
  跑 backend pytest、lint、compile、image build 與 workflow regression。
- root repo contract / docs checks
  目前仍由 `ci/api` 的 workflow regression 與 docs sanity 共同承接；尚未拆成獨立 workflow。

### Storefront repo

- `ci/storefront`
  在 `nurockplayer/storefront` GitHub repo 的 `.github/workflows/pr-ci.yml` 定義 lint、test、e2e、build 與 whitespace check。
- 其他 repo-local workflow
  例如 license、dependency inventory、type update automation，維持 storefront repo 自己管理。

## 還沒補上的 gate

- Tachiya API contract docs 與 request schema 的更完整 drift check。
- Points / referral / revenue share 的 end-to-end smoke test。
- Storefront 與 Tachiya 間的 runtime-level cross-repo contract smoke。
- release 前的 webhook replay / idempotency smoke checklist。

## 實作優先序

1. 保持 root repo 正式 workflow 與 docs 同步。
2. 維持 root repo 與獨立 storefront repo 的 required checks 對齊在同一份 contract matrix。
3. 最後補 runtime-level cross-repo smoke、PostgreSQL migration gate 與 release checklist。

這個順序的原因很直接：沒有穩定的 PR gate，後面的產品級測試再多，也會因為沒有被持續執行而失去保護效果。
