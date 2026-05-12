# Observability And Operations Runbook

本文定義 Tachiya 現階段的 observability 與營運處置基線。第一階段 MVP 已在 API 落地 request-id middleware 與 HTTPException structured error logging；本文聚焦這些已實作行為，以及仍待後續補齊的 logging pipeline、alert 平台與 dashboard。

## 目標

- 統一 structured logging 欄位標準，避免各 domain 用不同 key 導致查詢困難。
- 把 webhook、idempotency、coupon、revenue share 的錯誤分類整理成可操作的 taxonomy。
- 提供營運查詢、人工復原與 release 前 smoke checklist。
- 明確區分哪些檢查應進 CI，哪些仍屬於人工 runbook。

## 適用範圍

- Tachiya API contract 與受信任營運查詢面：見 [internal-api-contracts.md](internal-api-contracts.md)。
- 測試與正式 CI gate：見 [testing-and-ci-gates.md](testing-and-ci-gates.md)。
- 產品級 readiness 里程碑：見 [product-grade-readiness-plan.md](product-grade-readiness-plan.md)。

## Structured Logging 欄位標準

目前 API 已有第一階段 MVP：每個 HTTP request 都會帶 `X-Request-ID`，若 upstream 未提供則由 API 產生 `uuid4`；所有 `HTTPException` 會保留既有 `{ "detail": ... }` response contract，同時記錄 structured error event。未處理的非 `HTTPException` 500 會回傳 `{ "detail": "Internal Server Error" }` 並保留同一個 request id header。後續新增或整理 log 時，欄位命名應延續以下基線。

### 已實作 MVP 行為

- request middleware 先讀取 incoming `X-Request-ID`；若缺少，建立新的 UUID。
- request id 會掛在 request state，並回寫到 response header `X-Request-ID`；CORS response 會暴露此 header，讓 browser client 可以讀取。
- `HTTPException` 交給自訂 handler 記錄 structured event，但 response body 仍維持 `{ "detail": ... }`。
- 未處理的非 `HTTPException` 500 會交給 generic handler 記錄 structured event，並維持 request id response header。
- 第一版 structured error event 固定包含：
  - `service`
  - `event_name`
  - `domain`
  - `outcome`
  - `severity`
  - `error_code`
  - `request_id`
  - `status_code`
  - `path`：優先記錄 FastAPI route template，避免把 path params、PII 或高基數外部識別值寫進 log。
  - `method`

### 必填共用欄位

| 欄位 | 說明 |
|---|---|
| `timestamp` | ISO-8601 UTC 時間。 |
| `level` | `INFO`、`WARNING`、`ERROR`。 |
| `service` | 固定為 `tachiya-api`。 |
| `environment` | `local`、`staging`、`production`。 |
| `event_name` | 穩定事件名稱，例如 `points.order_rewarded.accepted`。 |
| `domain` | `webhook`、`points`、`coupons`、`referrals`、`revenue_share`、`identity_mapping`。 |
| `outcome` | `accepted`、`replayed`、`rejected`、`conflict`、`failed`、`completed`。 |
| `request_id` | 每次 HTTP request 的追蹤 id；若未來由 proxy 注入，沿用同一值。 |
| `actor_type` | `system`、`operator`、`webhook`、`internal-service`。 |

### 條件式欄位

| 欄位 | 何時出現 |
|---|---|
| `event_id` | 所有 webhook 與 replay guard 流程。 |
| `event_type` | webhook event，例如 `points.order_rewarded`、`revenue_share.order_completed`。 |
| `idempotency_key` | coupon redemption 或任何 idempotent write path。 |
| `order_id` | points reward、referral、revenue share。 |
| `user_id` | points / referral / identity mapping 相關事件。 |
| `coupon_id` | coupon redemption 與 audit event。 |
| `redemption_token` | coupon 查詢、客服查核、replay 分析。 |
| `record_id` | revenue share status 轉換。 |
| `streamer_slug` | streamer / revenue share 流程。 |
| `status_code` | HTTP response code。 |
| `error_code` | 穩定錯誤碼，格式建議 `<domain>.<reason>`。 |
| `reference_id` | points ledger 與手動補單。 |

### 命名原則

- key 一律使用 `snake_case`，不要混用 `eventId` / `event_id`。
- `event_name` 用「動作結果」命名，例如 `coupon.redeem.conflict`，不要直接塞 exception class 名稱。
- `error_code` 要可聚合，不要把使用者輸入直接拼進 key；細節放在額外欄位或訊息內。
- 涉及 PII 或 secret 的原始值不得直接記錄；若真的需要 trace，應只記錄已知安全的 id、slug、token prefix 或 hash。

## Error Taxonomy

### 1. Webhook / Signature / Replay

| 類型 | 代表情況 | 典型回應 | 建議 `outcome` | 是否需要人工介入 |
|---|---|---|---|---|
| `webhook.signature_invalid` | 缺 header、簽章錯、event id 被竄改 | `401 invalid webhook signature` | `rejected` | 否，先查上游設定或攻擊流量 |
| `webhook.timestamp_stale` | event timestamp 超出 tolerance | `401 stale webhook timestamp` | `rejected` | 視情況，若 staging / prod 持續發生需查時鐘與 queue 延遲 |
| `webhook.config_invalid` | tolerance 或 secret 設定錯 | `500 webhook tolerance is not configured correctly` 等 | `failed` | 是，屬於環境設定問題 |
| `webhook.replayed` | 同一 `event_id` 已處理過 | `409 webhook event already processed` | `replayed` | 否，通常視為 guard 生效 |

判讀原則：

- `401` 類錯誤優先當成來源或環境設定問題，不要立刻重送 payload。
- `409 webhook event already processed` 預設是正常防重；只有當業務結果缺失時，才往資料不一致方向追。

### 2. Coupon / Idempotency

| 類型 | 代表情況 | 典型回應 | 建議 `outcome` | 是否需要人工介入 |
|---|---|---|---|---|
| `coupon.validation_failed` | 空白或未知 `coupon_id`、成本不符、非正整數 | `400 ...` | `rejected` | 否，先修 caller |
| `coupon.idempotency_replayed` | 同一 `idempotency_key` 與相同 payload 重送 | `200` 同一結果 | `replayed` | 否 |
| `coupon.idempotency_conflict` | 同一 `idempotency_key` 對到不同 `coupon_id` 或 `tcg_cost` | `409 idempotency key conflict` | `conflict` | 是，需人工判定哪筆請求有效 |
| `coupon.audit_gap` | redemption 結果與 audit event / admin 查詢對不起來 | 查詢面不一致 | `failed` | 是 |

判讀原則：

- `409 idempotency key conflict` 不應自動重試；應先保留原始 payload 與第一次成功/失敗結果。
- 使用者回報「有扣 token 但沒拿到券」時，先查 audit event，再查 admin coupon 列表，不要直接重發。

### 3. Revenue Share / Webhook 業務衝突

| 類型 | 代表情況 | 典型回應 | 建議 `outcome` | 是否需要人工介入 |
|---|---|---|---|---|
| `revenue_share.record_conflict` | 同一 `order_id + streamer_slug` 重送但金額或狀態不一致 | `409 revenue share record conflict` | `conflict` | 是 |
| `revenue_share.status_conflict` | terminal status 想從 `paid` 改成 `void` 或反向 | `409 revenue share status conflict` | `conflict` | 是 |
| `revenue_share.record_missing` | 人工更新 status 時找不到 record | `404 revenue share record not found` | `failed` | 是 |
| `revenue_share.validation_failed` | webhook / record payload 欄位錯誤 | `4xx` | `rejected` | 否，先修 caller |

判讀原則：

- `record_conflict` 代表同一訂單的分潤事實不一致，不能只靠重試解掉。
- `status_conflict` 代表 payout 流程已進 terminal state，若要更正必須留下人工稽核紀錄。

### 4. Points / Referral 業務錯誤

| 類型 | 代表情況 | 典型回應 | 建議 `outcome` | 是否需要人工介入 |
|---|---|---|---|---|
| `points.validation_failed` | `reward_points`、`amount`、`user_id`、`order_id` 型別或空白錯誤 | `4xx` | `rejected` | 否 |
| `points.insufficient_balance` | manual debit 導致餘額負數 | `4xx` | `rejected` | 視情況 |
| `points.replayed` | webhook event 已處理過 | `409 webhook event already processed` | `replayed` | 否 |
| `referral.replayed` | referral webhook event 已處理過 | `409 webhook event already processed` | `replayed` | 否 |

## 營運查詢 Runbook

以下查詢都應優先透過既有受信任 API 完成，而不是直接假設需要進資料庫。

### 1. Webhook 是否真的進來過

先查 [internal-api-contracts.md](internal-api-contracts.md) 定義的 `GET /webhooks/events`：

- 以 `event_id` 精準查單筆 webhook。
- 若只知道流程，改用 `event_type` 加 `received_from` / `received_to` 查時間窗。
- 查到事件不代表業務一定成功，還要對照下游 domain 查詢面。

適用問題：

- 上游說已重送 webhook，但 Tachiya 是否有收到。
- staging smoke 失敗時，判斷是 webhook 沒到、簽章失敗，還是 replay guard 擋下來。

### 2. Coupon redemption 查核

依序查：

1. `GET /coupons/redemption-audit-events`
2. `GET /coupons/admin`
3. 必要時再讓使用者端用 `GET /coupons?redemption_token=...` 驗證公開讀取面

建議 filter：

- 有 `idempotency_key` 時，先用 `idempotency_key` 查 audit event。
- 使用者只提供 voucher code 或 token 時，先從 `GET /coupons/admin` 反查。
- 若 audit event 有 `failed` 或 `replayed`，對照同時間窗的成功事件，避免誤補發。

### 3. Points 餘額與過期查核

依序查：

1. `GET /points/balance`
2. `GET /points/ledger`
3. `GET /points/ledger/entries`
4. `GET /points/ledger/expired-credits`

判讀原則：

- 使用者看到的餘額以 `/points/balance` 為準。
- 要查為什麼少了點數，先看 `/points/ledger` 與 `/points/ledger/entries` 的 `reference_id`、`source_type`、`entry_type`。
- 要查「明明還有歷史 credit，為什麼不能花」，再看 `/points/ledger/expired-credits`。

### 4. Revenue share / payout queue 查核

依序查：

1. `GET /streamers/revenue-shares/records`
2. `GET /streamers/revenue-shares/summary`
3. 若懷疑 webhook 重放，再補查 `GET /webhooks/events?event_type=revenue_share.order_completed`

建議 filter：

- 對單筆訂單，用 `order_id` 查 records。
- 對單一實況主 payout queue，用 `streamer_slug + status=pending`。
- 對 release 前整體健康度，用 summary 看 `pending` / `paid` / `void` 分布是否異常。

## 手動復原 Runbook

### 1. Webhook replay 判讀

- 若查到 `409 webhook event already processed`，先確認同一 `event_id` 是否已存在於 `GET /webhooks/events`。
- 若事件存在，接著查對應 domain 結果是否也存在，例如 points ledger entry 或 revenue share record。
- 只有在「event 不存在，且業務結果也不存在」時，才把它當成真正漏處理。

### 2. Coupon redemption 異常

- `coupon.validation_failed`：修上游 payload，不做人工作業補償。
- `coupon.idempotency_replayed`：直接回收第一次結果，不建立第二張券。
- `coupon.idempotency_conflict`：停止自動重試，保留原 payload，人工確認哪個 `coupon_id` / `tcg_cost` 才是正確請求。
- 若確認第一次請求成功但使用者沒拿到結果，應優先從 `GET /coupons/admin` 或 audit event 回傳既有 voucher code / redemption token，而不是再呼叫一次兌換。

### 3. Points 手動補正

- 只用 `POST /points/transactions` 做人工 credit/debit。
- `reference_id` 應帶可稽核前綴，例如 `manual:ops-incident-20260511-01`。
- 補正前先查 `/points/balance` 與 `/points/ledger/entries`，避免重複補單。
- 補正後再查一次 `/points/balance`，確認結果與預期一致。

### 4. Revenue share 手動處理

- 單筆 payout 完成後，只透過 `POST /streamers/revenue-shares/records/{record_id}/status` 將 `pending` 標成 `paid` 或 `void`。
- 若遇到 `revenue_share.status_conflict`，不要直接改資料；先查原 terminal status 與對應 payout 證據。
- 若遇到 `revenue_share.record_conflict`，先把同一 `order_id` 全部 record 撈出來，再對照上游訂單明細與 product assignment，不要先重送 webhook。

## Staging / Release 前 Smoke Checklist

### 必跑人工 smoke

- webhook signature smoke：送一筆合法 webhook，確認可成功寫入對應 domain 結果。
- webhook replay smoke：立刻重送同一 `event_id`，確認回 `409 webhook event already processed`。
- coupon redemption smoke：用固定測試 `coupon_id` 成功兌換一次，再以相同 `idempotency_key` 重送一次，確認回同一結果。
- coupon conflict smoke：以相同 `idempotency_key` 改 `coupon_id` 或 `tcg_cost`，確認被拒。
- points smoke：查一次 `/points/balance`，建立一筆 `POST /points/transactions` 測試 credit/debit，再重新查餘額。
- expired credit smoke：若 staging 有到期測試資料，確認 `/points/ledger/expired-credits` 可見 exposure。
- revenue share smoke：送一筆 `POST /streamers/webhooks/order-completed` 測試單，確認 records / summary 可查到，且重送會被 replay guard 擋下。
- payout status smoke：把 staging 測試 record 從 `pending` 更新到 `paid` 或 `void`，確認 terminal status 行為符合契約。

### Release 前判讀重點

- 任何 `500` 類 webhook 設定錯誤都應先擋 release。
- `409` replay 如果數量穩定且都對得上既有業務結果，不算 blocker。
- `409` conflict 若來自 idempotency payload 不一致或 revenue share record 不一致，算 blocker，需先釐清資料真相。

## 哪些檢查應進 CI，哪些留在 Runbook

### 應進 CI 的檢查

| 類型 | 原因 | 現況 |
|---|---|---|
| request schema / strict integer rejection | 穩定、可重現、適合單元或 router test | 已由 `api/tests` 與 `ci/api` 保護 |
| webhook signature / tolerance / replay guard 行為 | 可用 fixture 驗證，避免 release 後才發現 guard 壞掉 | 已有測試基線，應持續留在 CI |
| coupon idempotency replay / conflict | 純契約邏輯，適合固定化測試 | 已有 contract 與測試基線，應留在 CI |
| revenue share record / status conflict | 純 domain 契約，應由測試保護 | 已有 router/service 測試基線，應留在 CI |
| workflow regression / `git diff --check` | 防止文件與 workflow 漂移 | 已在 docs / workflow gate 使用 |

### 應留在 Runbook 的檢查

| 類型 | 原因 |
|---|---|
| 真實 webhook provider 到 staging 的端對端送達 | 依賴外部 secret、時鐘與網路，不適合每次 PR CI 都跑 |
| 手動補點、補券、payout 狀態轉換 | 需要人工判斷事故背景與補償策略 |
| release 前跨 domain smoke | 涉及可變測試資料、staging 環境狀態與外部依賴 |
| 異常量判讀與客服查核 | 需要把 audit event、ledger、records 與實際使用者回報一起看 |

## 後續文件化缺口

- 若未來真的落地 log sink、dashboard 或 alert rule，應在本文件追加「事件名稱對應告警規則」而不是另外發散命名。
- 若新增新的 webhook domain，應同步補 error taxonomy、查詢面與 smoke checklist。
- 若 runbook 依賴的新查詢面尚未有測試保護，應先補測試或 issue，再把它升格為 release gate。
