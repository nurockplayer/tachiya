# Tachiya / Storefront Cross-Repo Contracts

本文件是 Tachiya API 與 `nurockplayer/storefront` 的共享契約矩陣。Tachiya 是 contract owner；Storefront 是 consumer。跨 repo 改動時，PR body 需指出對應 issue、contract row、以及是否需要同步另一個 repo。

這份矩陣與 `.github/workflow-tests/cross-repo-contracts.fixture.json` 同步維護；fixture 是 cross-repo contract gate 的 row source。測試會先驗 asset schema，再驗 docs / router / storefront path alignment。

## Contract Matrix

| Domain | Tachiya API contract | Storefront consumer | Required checks |
| --- | --- | --- | --- |
| Points balance | `GET /points/balance?user_id=<saleor customer id>` 回傳 `user_id` 與 strict integer `balance`。需要 `X-Tachiya-Internal-Secret`。 | `src/lib/tachiya-points.ts` 的 `buildTachiyaPointsBalanceUrl()`、`fetchTachiyaPointsBalance()`；account layout 透過 `PointsBalance` 顯示餘額；`src/lib/tachiya-points.test.ts` 保護 URL 與 missing-config fallback。 | Tachiya router/service tests；Storefront `src/lib/tachiya-points.test.ts`；Storefront account E2E fallback smoke。 |
| Points ledger | `GET /points/ledger?user_id=<saleor customer id>&limit=1..100` 回傳 `entries[]`，entry 欄位為 `id`、`amount`、`entry_type`、`source_type`、`reference_id`、`expires_at`、`created_at`。需要 `X-Tachiya-Internal-Secret`。 | `src/lib/tachiya-points.ts` 的 `buildTachiyaPointsLedgerUrl()`、`fetchTachiyaPointsLedger()`；`PointsBalance` 顯示近期紀錄或 unavailable fallback；`src/lib/tachiya-points.test.ts` 也覆蓋 ledger URL 與 missing-config fallback。 | Tachiya points router tests；Storefront `src/lib/tachiya-points.test.ts` 與 points balance component tests。 |
| Coupons | `GET /coupons?redemption_token=<token>` 只回傳符合 token 且 active 的 coupon array。`POST /coupons/redeem` 仍由受信任 caller 建立 redemption token，不是公開 Storefront write path。 | `src/checkout/lib/tachiya-coupons.ts` 從 URL/local storage 解析 `tachiya_redemption_token`，呼叫 `/coupons?redemption_token=...` 後選第一個 active voucher；`src/checkout/lib/tachiya-coupons.test.ts` 覆蓋 token 與 active coupon 選取。 | Tachiya coupon router tests；Storefront coupon helper tests；checkout no-id smoke 保持不依賴真實付款。 |
| Streamer list | `GET /streamers?limit=1..100` 回傳 active streamer summaries，不含 commission 或 revenue share 欄位。需要 `X-Tachiya-Internal-Secret`。 | `src/lib/tachiya-streamer-catalog.ts` 的 `buildTachiyaStreamerListUrl()` 與首頁 / streamers listing；`src/lib/tachiya-streamer-catalog.test.ts` 會驗證 limit 上下界。 | Tachiya streamers router tests；Storefront streamer catalog helper tests；homepage smoke。 |
| Streamer catalog | `GET /streamers/{slug}/catalog` 回傳 streamer summary 與 `saleor_product_ids[]`，inactive 或 missing streamer 回 `404 streamer catalog not found`。需要 `X-Tachiya-Internal-Secret`。 | `src/lib/tachiya-streamer-catalog.ts` 的 `buildTachiyaStreamerCatalogUrl()` 與 streamer detail page，再由 Saleor product ids 查商品；`src/lib/tachiya-streamer-catalog.test.ts` 覆蓋 catalog URL。 | Tachiya streamers router tests；Storefront streamer display/catalog tests。 |

## Drift Gate

`.github/workflows/cross-repo-contract.yml` 會在 Tachiya PR / develop push 上執行 cross-repo sanity test：

- checkout Tachiya 目前 commit。
- checkout `nurockplayer/storefront@develop` 到 `.ci/storefront`。
- 執行 `.github/workflow-tests/cross-repo-contract.test.mjs`。

這個 gate 是 asset-driven static gate，不是 runtime mock server，也不是完整 integration test。它不打真實金流或真實訂單，只確認 contract docs、Tachiya router surface、Storefront consumer helper、以及 Storefront consumer tests 仍同時存在並含有關鍵欄位 / URL / header。若未來 Storefront 改檔名或 API contract 改 endpoint，必須同一張 PR 更新本文件、fixture、與 sanity test。

## Runtime Smoke Coverage

目前 cross-repo gate 保護的是靜態契約漂移；runtime smoke 仍是下一層檢查。這層的目標不是覆蓋完整購物流程，而是證明 Storefront 在執行時能用測試 fixture 呼叫 Tachiya-owned contract row，並在 auth、schema、空資料與錯誤狀態上產出可讀的失敗訊號。

建議 runtime smoke 拆成兩段落地：

1. Tachiya repo 保有本文件、fixture、router/docs alignment 與 failure report 規格。
2. Storefront repo 擁有 Playwright 或 route-level runtime smoke，使用 mock Tachiya base URL 驗證 helper 在瀏覽器流程中的實際行為。

最小 smoke row 不應一次全部打完。第一批建議只選：

- Points balance：驗證 `X-Tachiya-Internal-Secret`、`user_id` query、strict integer `balance`，以及 unavailable fallback。
- Coupons：驗證 `tachiya_redemption_token` 解析、`GET /coupons?redemption_token=...`、只接受 active coupon。
- Streamer catalog：驗證 slug encode、`saleor_product_ids[]`、missing catalog fallback。

Runtime smoke 的啟動序列應保持可重複：

1. 啟動 Storefront test server，注入 mock Tachiya base URL 與 shared secret。
2. mock Tachiya 回傳 contract row 對應的 success、empty、unauthorized、schema mismatch fixture。
3. 執行 Storefront smoke route，確認 UI fallback 或 helper result 符合 contract。
4. 輸出 JUnit 或 Playwright HTML artifact，失敗訊息必須包含 row name、endpoint、fixture name 與建議修復檔案。

Runtime smoke 不應在 Tachiya PR 裡 checkout Storefront 後啟動完整 Storefront app，除非該 PR 同時更新了 Storefront 對應 workflow 並證明執行時間穩定。Tachiya 這邊只負責 contract row 與 failure vocabulary；Storefront repo 負責把 row 套進使用者可見流程。

## Runtime Smoke Acceptance Criteria

- 每個 smoke row 都要對應 `.github/workflow-tests/cross-repo-contracts.fixture.json` 的 row name。
- 每個 failure 都要包含 `row name`、`endpoint or pathPattern`、`fixture name`、`expected behavior`、`suggested file`。
- Mock response 必須同時覆蓋 success 與至少一個 fallback path；只測 happy path 不算完成。
- Auth-required row 必須驗證 `X-Tachiya-Internal-Secret` 缺失或錯誤時的 fallback。
- Storefront 端 smoke 必須可用單一指令在 CI 跑，且不得依賴 production secret、真實付款、真實訂單或外部 Twitch/Saleor network。
- 若 runtime smoke 尚未落地，PR body 必須把它列為 non-goal 或 follow-up，不能把 static gate 說成 end-to-end coverage。

## Failure Report Format

當 gate 失敗時，先用 row 為單位報告：

1. row name
2. 缺少的欄位或缺少的 pattern
3. expected behavior
4. suggested file

如果同一輪有多個 row fail，修復順序請先從 docs / fixture 開始，再修 router path，最後才修 storefront consumer/test path。

Runtime smoke 失敗時也用同一個 row-first 格式，但需額外附上：

1. fixture name
2. runtime surface，例如 browser route、server action、route handler 或 helper
3. artifact link，例如 JUnit XML、Playwright trace 或 HTML report
4. 是否為 Storefront-owned fix、Tachiya-owned contract fix，或跨 repo follow-up

## Repair Priority

1. 先對齊 `.github/workflow-tests/cross-repo-contracts.fixture.json` 與 `docs/internal-api-contracts.md`。
2. 再對齊 Tachiya router surface 與 `docs/cross-repo-contracts.md` 的 row 說明。
3. 最後再對齊 Storefront consumer / test file path 與 helper 行為。

## PR Checklist

- Tachiya endpoint path、query、response 欄位或 auth header 有變更時，更新 `docs/internal-api-contracts.md` 與本文件。
- Storefront consumer helper 有變更時，確認 `nurockplayer/storefront` 有對應 PR，或在 Tachiya PR body 的 `本 PR 明確不做` 說明原因。
- Cross-repo gate fail 時，優先判斷是 contract drift、檔案移動未更新測試、或 checkout/token 問題；如果是 row-driven failure，先看 asset / docs / router 的順序。
