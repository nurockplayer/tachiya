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

- [`.github/workflows/api-ci.yml`](/Users/erickwang/Desktop/tachiya/.github/workflows/api-ci.yml)
  - scope: `api/**`、API contract docs、workflow regression、docker compose 相關 root 檔
  - checks: `git diff --check`、`pytest`、`ruff check`、`ruff format --check`、`python -m compileall`、API image build

目前 root repo 明確不再依賴 weekly release workflow，也不把任何本機未追蹤的 workflow 草案算進正式 gate。`frontend/` 在架構上是獨立 git repo，因此 frontend 的 PR CI 由 `nurockplayer/storefront` repo 自己擁有，不在 root repo duplicated 一套。

### Storefront repo

Storefront 目前有明確可執行的本地驗證指令：

- `pnpm run lint`
- `pnpm run test:run`
- `SKIP_CODEGEN=1 pnpm run build`

目前已追蹤的 workflow：

- [frontend/.github/workflows/check-licenses.yaml](/Users/erickwang/Desktop/tachiya/frontend/.github/workflows/check-licenses.yaml)
- [frontend/.github/workflows/lint.yml](/Users/erickwang/Desktop/tachiya/frontend/.github/workflows/lint.yml)
- [frontend/.github/workflows/update_types.yml](/Users/erickwang/Desktop/tachiya/frontend/.github/workflows/update_types.yml)

目前缺口：

- Storefront repo 自己的 PR gate 與 root repo 的 API / contract docs 還沒有 cross-repo contract 對照。
- 沒有把 Tachiya 特有 route hardening 與 API contract drift 做成跨 repo required check。
- root repo 內仍缺少一個可以驗證「文件宣告的 storefront contract 是否與獨立 storefront repo 現況一致」的自動 gate。

## 現有測試對應

### Backend request / router contracts

- [api/tests/test_coupon_internal_secret.py](/Users/erickwang/Desktop/tachiya/api/tests/test_coupon_internal_secret.py)
- [api/tests/test_points_router.py](/Users/erickwang/Desktop/tachiya/api/tests/test_points_router.py)
- [api/tests/test_referral_service.py](/Users/erickwang/Desktop/tachiya/api/tests/test_referral_service.py)
- [api/tests/test_streamers_router.py](/Users/erickwang/Desktop/tachiya/api/tests/test_streamers_router.py)

保護的內容：

- strict integer payload rejection
- blank string normalization
- webhook signature / secret gate
- endpoint response shape

### Backend domain / service logic

- [api/tests/test_points_service.py](/Users/erickwang/Desktop/tachiya/api/tests/test_points_service.py)
- [api/tests/test_revenue_share_service.py](/Users/erickwang/Desktop/tachiya/api/tests/test_revenue_share_service.py)
- [api/tests/test_streamer_service.py](/Users/erickwang/Desktop/tachiya/api/tests/test_streamer_service.py)

保護的內容：

- points FIFO balance 與 expired credit exposure
- coupon / referral / revenue share 的業務規則
- streamer profile 與 assignment 行為

### Frontend route / runtime contracts

- [frontend/src/app/api/revalidate/route.test.ts](/Users/erickwang/Desktop/tachiya/frontend/src/app/api/revalidate/route.test.ts)
- [frontend/src/app/api/auth/register/route.test.ts](/Users/erickwang/Desktop/tachiya/frontend/src/app/api/auth/register/route.test.ts)
- [frontend/src/app/api/auth/reset-password/route.test.ts](/Users/erickwang/Desktop/tachiya/frontend/src/app/api/auth/reset-password/route.test.ts)
- [frontend/src/app/api/auth/set-password/route.test.ts](/Users/erickwang/Desktop/tachiya/frontend/src/app/api/auth/set-password/route.test.ts)
- [frontend/src/lib/graphql.test.ts](/Users/erickwang/Desktop/tachiya/frontend/src/lib/graphql.test.ts)

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
  目前在 `frontend/.github/workflows/pr-ci.yml` 定義 lint、test、e2e、build 與 whitespace check。
- 其他 repo-local workflow
  例如 license、dependency inventory、type update automation，維持 storefront repo 自己管理。

## 還沒補上的 gate

- Tachiya API contract docs 與 request schema 的 drift check。
- Points / referral / revenue share 的 end-to-end smoke test。
- Storefront 與 Tachiya 間的 cross-repo contract test。
- release 前的 webhook replay / idempotency smoke checklist。

## 實作優先序

1. 先把 root repo 正式 workflow 納入版控。
2. 再把 root repo 與獨立 storefront repo 的 required checks 對齊成同一份 contract matrix。
3. 最後補 cross-repo smoke 與 contract drift check。

這個順序的原因很直接：沒有穩定的 PR gate，後面的產品級測試再多，也會因為沒有被持續執行而失去保護效果。
