# Testing And CI Gates

本文定義 Tachiya 目前的測試基線、現有 CI 現況，以及接下來應該補上的 required gates。目標不是把所有檢查塞進同一個 workflow，而是讓 root repo、Storefront repo 與跨 repo 邊界各自有清楚責任。

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

目前 root repo 的 CI 狀態：

- 本機存在 [`.github/workflows/build.yml`](/Users/erickwang/Desktop/tachiya/.github/workflows/build.yml) 草案。
- 但 `.github/` 目前未被 git 追蹤，代表它還不是正式生效中的 repo gate。
- 現有草案只涵蓋 API image build 與 storefront app build，沒有 backend test gate。

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

- `lint.yml` 是 `deployment_status` 觸發，不是每張 PR 必跑。
- 沒有看見針對每張 PR 的 `test:run` 與 `build` gate。
- 沒有把 Tachiya 特有 route hardening 視為 required check。

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

## 建議 required gates

### Root repo PR gate

所有修改 `api/`、`docs/`、`docker-compose` 或整體整合文件的 PR，至少應該跑：

- `cd api && uv run --group dev pytest`
- `cd api && python -m compileall .`
- `docker compose build api dashboard`
- `git diff --check`

若 PR 也依賴 Storefront 現況，應額外做一次整合 build：

- `cd frontend && pnpm install --frozen-lockfile`
- `cd frontend && SKIP_CODEGEN=1 pnpm run build`

### Storefront PR gate

所有修改 `frontend/src`、`frontend/package.json`、`frontend/pnpm-lock.yaml` 或 `frontend/.github/workflows` 的 PR，至少應該跑：

- `pnpm install --frozen-lockfile`
- `pnpm run lint`
- `pnpm run test:run`
- `SKIP_CODEGEN=1 pnpm run build`
- `git diff --check`

### Docs-only gate

純文件 PR 不需要硬跑整套 backend / frontend full suite，但至少應該跑：

- `git diff --check`
- 檢查文件引用的檔名、issue / PR 編號與 workflow 現況是否正確

如果文件宣告的是新的產品契約，而 repo 內還沒有對應 test，這不應視為可 merge 的 docs-only 變更，而應拆出補測工作。

## 建議新增的 workflow 拆法

### Tachiya root repo

- `ci/api-test`
  跑 backend pytest 與 compile gate。
- `ci/api-image`
  只負責 API image build。
- `ci/storefront-build-reference`
  以 Tachiya 角度確認目前指定的 storefront `develop` 還 build 得起來。

### Storefront repo

- `ci/lint`
  每張 PR 必跑。
- `ci/test`
  跑 `pnpm run test:run`。
- `ci/build`
  跑 `SKIP_CODEGEN=1 pnpm run build`。
- `ci/license`
  維持既有 license check。

## 還沒補上的 gate

- Tachiya API contract docs 與 request schema 的 drift check。
- Points / referral / revenue share 的 end-to-end smoke test。
- Storefront 與 Tachiya 間的 cross-repo contract test。
- release 前的 webhook replay / idempotency smoke checklist。

## 實作優先序

1. 先把 root repo 正式 workflow 納入版控。
2. 再把 storefront PR 必跑的 lint / test / build gate 補齊。
3. 最後補 cross-repo smoke 與 contract drift check。

這個順序的原因很直接：沒有穩定的 PR gate，後面的產品級測試再多，也會因為沒有被持續執行而失去保護效果。
