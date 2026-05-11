# Product-grade Readiness Plan

本文整理 Tachiya 在 2026-05-10 時點已經落地的產品級基線、目前缺口，以及 Phase 5 之後應該怎麼往前推。這份文件描述的是「現況與下一步」，不是把尚未實作的東西包裝成已完成。

## 目標

- 把最近一波 hardening 的成果從 issue / PR / 驗證紀錄沉澱回 repo 內文件。
- 讓後續實作者知道哪些邊界已經是產品契約，不能再靠隱性型別轉換或前端僥倖處理。
- 把下一階段應該補的 testing、CI、observability 與 release gate 排成可執行的順序。

## Repo 邊界

- `tachiya/`：FastAPI、自家文件、docker-compose 與整體整合脈絡。
- `tachiya/frontend/`：本機 checkout 目錄；正式獨立 git repo 是 `nurockplayer/storefront`，負責 Next.js Storefront。
- `tachigo/`：參考來源與未來共同商城需求輸入；本 repo 不直接修改它。

這代表產品級 readiness 不是只看 `api/`，也必須同時看 `nurockplayer/storefront` 的 request validation、runtime env 防呆與 revalidation 邊界。Tachiya root repo 不 duplicated Storefront PR CI，而是用 cross-repo contract gate 監控雙方契約漂移。

## 已完成基線

### 1. FastAPI 輸入邊界 hardening

近期已 merge 的後端修補把金額、點數與 basis points 類欄位改成 strict integer 邊界，避免字串、布林值或浮點數在 schema 或 service 中被隱性轉型。

| 範圍 | 目前基線 | 參考 |
|---|---|---|
| Coupons | `POST /coupons/redeem` 的 `tcg_cost` 必須是 strict integer，且先驗證再碰 Saleor | `#294` / `#295` |
| Points | `POST /points/transactions` 的 `amount`、`POST /points/webhooks/order-rewarded` 的 `reward_points` 必須是 strict integer | `#296` / `#297` |
| Referrals | `POST /referrals/webhooks/order-completed` 的 `order_total_amount` 必須是 strict integer | `#298` / `#299` |
| Streamers | `POST /streamers` 與 `PATCH /streamers/{slug}` 的 `commission_bps` 必須是 strict integer | `#292` / `#293` |
| Revenue shares | `POST /streamers/revenue-shares/preview` 與 `record` 的 `lines[].gross_amount` 必須是 strict integer | `#290` / `#291` |

### 2. Storefront request / runtime validation hardening

Storefront 近期完成的是「把不乾淨 payload 擋在 route / runtime 邊界」，而不是把錯誤一路丟到 Saleor 或執行期才爆。

| 範圍 | 目前基線 | 參考 |
|---|---|---|
| Revalidate webhook | webhook payload 的 slug / channel 欄位會檢查型別與空白 fallback 行為 | root issue `#284` / storefront PR `#32` |
| Manual revalidate | `path`、`tag`、`profile`、`all` 會 trim 並拒絕空白目標 | root issue `#285` / storefront PR `#33` |
| Auth register | `email`、`password`、`channel`、`redirectUrl` 必填且 trim 後才呼叫 Saleor | root issue `#286` / storefront PR `#34` |
| Auth reset-password | `email`、`channel`、`redirectUrl` 必填且 trim 後才呼叫 Saleor | root issue `#287` / storefront PR `#35` |
| Auth set-password | `email`、`token`、`password` 必填且 trim 後才呼叫 Saleor | root issue `#288` / storefront PR `#36` |
| GraphQL runtime env | runtime 整數 env 會 fallback / clamp，不接受 blank 或非數字值 | root issue `#289` / storefront PR `#37` |

### 3. 文件化進度

目前已經有的長期文件：

- [docs/product-decisions.md](/Users/erickwang/Desktop/tachiya/docs/product-decisions.md)
- [docs/internal-api-contracts.md](/Users/erickwang/Desktop/tachiya/docs/internal-api-contracts.md)

這次補寫後，會把最近一波 hardening 的契約、測試基線與 CI 缺口一起落到 repo，避免只存在於 GitHub 討論串。

## 目前測試基線

### Backend

後端目前有兩層測試已經形成基線：

- Router / request schema 層：
  [api/tests/test_coupon_internal_secret.py](/Users/erickwang/Desktop/tachiya/api/tests/test_coupon_internal_secret.py)
  [api/tests/test_points_router.py](/Users/erickwang/Desktop/tachiya/api/tests/test_points_router.py)
  [api/tests/test_referral_service.py](/Users/erickwang/Desktop/tachiya/api/tests/test_referral_service.py)
  [api/tests/test_streamers_router.py](/Users/erickwang/Desktop/tachiya/api/tests/test_streamers_router.py)
- Service / domain 邏輯層：
  [api/tests/test_points_service.py](/Users/erickwang/Desktop/tachiya/api/tests/test_points_service.py)
  [api/tests/test_revenue_share_service.py](/Users/erickwang/Desktop/tachiya/api/tests/test_revenue_share_service.py)
  [api/tests/test_streamer_service.py](/Users/erickwang/Desktop/tachiya/api/tests/test_streamer_service.py)

這些測試已經能保住最近那批 strict integer、idempotency、FIFO balance、revenue share aggregation 的核心行為。

### Storefront

Storefront 目前有 route / library / E2E smoke 測試基線。這些檔案屬於獨立 repo `nurockplayer/storefront`；若在本機操作，請使用 `/Users/erickwang/Desktop/storefront`，不要把 root repo 的 `frontend/` checkout 當成 Tachiya 版控內容。

- `src/app/api/revalidate/route.test.ts`
- `src/app/api/auth/register/route.test.ts`
- `src/app/api/auth/reset-password/route.test.ts`
- `src/app/api/auth/set-password/route.test.ts`
- `src/lib/graphql.test.ts`
- `tests/e2e/storefront-smoke.spec.ts`

這些測試能保住「trim / reject blank / env fallback」這類邊界，但還不是完整使用者流程測試。

## 目前還缺什麼

### 1. Contract tests beyond static drift checks

目前已經有 `.github/workflows/cross-repo-contract.yml` 與 `.github/workflow-tests/cross-repo-contract.test.mjs`，可確認 Tachiya docs / router surface 與 Storefront develop consumer helper / tests 的基本契約沒有漂移。下一階段缺的是更接近 runtime 的 smoke：

- Tachiya API contract 變更後，Storefront 以 mock / fixture payload 仍能吃得下來。
- Storefront route hardening 沒有把既有 Saleor / Tachiya 呼叫格式打斷。
- 文件中的 contract 欄位能轉成更完整的 test matrix。

### 2. CI gate 不完整

目前觀察到的現況：

- root repo 目前有正式追蹤的 [`.github/workflows/api-ci.yml`](/Users/erickwang/Desktop/tachiya/.github/workflows/api-ci.yml)，覆蓋 API、workflow regression 與相關 contract docs。
- root repo 已移除 weekly release PR automation，release promotion 不再假設由排程 workflow 代辦。
- storefront repo 自己擁有前端 PR CI；由於 `frontend/` 在架構上是獨立 git repo，root repo 不 duplicated 一套 frontend lint / test / build workflow。
- root repo 與 storefront repo 之間已有 static cross-repo contract gate；尚未有需要真實服務或 mock server 的 end-to-end contract smoke。

### 3. E2E 與營運驗證不足

目前還缺：

- 訂單完成後 points / referral / revenue share 串接的整體 smoke test。
- Tachiya API 與 Storefront 之間更完整的 runtime contract smoke。
- 營運視角的 replay、idempotency、payout queue、expired credit 對帳流程驗證。

### 4. Observability 與 release gate

目前 repo 內還沒有完整文件化：

- 哪些 API error 需要 structured logging。
- 哪些 webhook / queue / payout 狀態要被 dashboard 或 alert 觀測。
- release 前哪些 smoke checks 是必跑。

## Phase 5 後的建議順序

### Phase 6: 文件與 CI 基線收斂

- 補齊 contract docs、testing docs、CI gate docs。
- 維持 root repo 的 `ci/api` 與 storefront repo 的 `ci/storefront` 為正式 required gate。
- 對齊 root repo 與 storefront repo 的 PR 必跑 lint / test / build contract。

### Phase 7: Cross-repo contract 與 smoke coverage

- 擴充 Tachiya API 與 Storefront 的 cross-repo smoke tests。
- 針對 points、coupon、referral、revenue share 建立最小 happy path / bad input path 契約測試。
- 將文件中的產品契約欄位轉成可驗證的 test matrix。

### Phase 8: 營運與 release readiness

- 補 structured logs、error taxonomy 與 replay / idempotency 觀測面。
- 定義 staging / production release checklist。
- 補 payout、expired credits、webhook replay 的營運手冊與稽核查詢範本。

## 本文件的使用方式

- 要改 API request schema 前，先更新 [docs/internal-api-contracts.md](/Users/erickwang/Desktop/tachiya/docs/internal-api-contracts.md)。
- 要改測試或 CI 流程前，先對照 [docs/testing-and-ci-gates.md](/Users/erickwang/Desktop/tachiya/docs/testing-and-ci-gates.md)。
- 若下一步要從「可開發」推到「可上線」，應優先做 Phase 6 的 CI gate 收斂，而不是再繼續只補單點 validation。
