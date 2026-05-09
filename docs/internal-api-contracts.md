# Internal API Contracts

本文記錄 Tachiya FastAPI 目前提供給 Storefront、Tachigo backend、營運腳本與受信任後台服務使用的內部 API 合約。產品決策背景見 [`docs/product-decisions.md`](product-decisions.md)。

## 共通認證

所有內部 API endpoint 都必須帶：

```http
X-Tachiya-Internal-Secret: <TACHIYA_INTERNAL_SHARED_SECRET>
```

- 未設定 `TACHIYA_INTERNAL_SHARED_SECRET`：API fail closed，回傳 `500 internal shared secret is not configured`。
- header 缺失或不相符：回傳 `401 invalid internal secret`。
- 這個 secret 同時用於 Tachiya 呼叫 Tachigo internal API 時的 outbound header。

## Webhook 簽章

Webhook endpoint 除 internal secret 外，還必須帶 HMAC 簽章：

```http
X-Tachiya-Webhook-Event-Id: <stable-event-id>
X-Tachiya-Webhook-Timestamp: <unix-seconds>
X-Tachiya-Webhook-Signature: <hex-hmac-sha256>
```

簽章 payload 為：

```text
<timestamp>.<raw-request-body>
```

驗證規則：

- HMAC secret：`TACHIYA_INTERNAL_SHARED_SECRET`。
- timestamp tolerance：`TACHIYA_WEBHOOK_TOLERANCE_SECONDS`，預設 `300` 秒。
- tolerance 非整數、零或負數：回傳 `500 webhook tolerance is not configured correctly`。
- timestamp 超出 tolerance：回傳 `401 stale webhook timestamp`。
- event id 重放：回傳 `409 webhook event already processed`。

參考實作：

- `api/security.py`
- `api/services/webhook_event_service.py`
- `api/models/webhook_event.py`

## Coupons

### `POST /coupons/redeem`

用途：受信任服務把 Tachigo token 價值兌換成 Saleor voucher。

Request：

```json
{
  "coupon_id": "discount_100",
  "tcg_cost": 100,
  "idempotency_key": "tachigo-redemption-123"
}
```

Response：

```json
{
  "voucher_code": "DEMO-ABC123",
  "redemption_token": "uuid",
  "status": "ok"
}
```

規則：

- `coupon_id` 必須存在於 `api/services/saleor_voucher.py` 的 `COUPON_CONFIG`。
- `tcg_cost` 必須大於 0，且必須等於 coupon 設定成本。
- `idempotency_key` 重放時回傳同一筆 voucher 與 redemption token。
- 成功、失敗、重放都會寫入 coupon redemption audit event。

錯誤：

- 未知 coupon：`400 unknown coupon_id: <id>`。
- 成本小於等於 0：`400 tcg_cost must be positive`。
- 成本不符：`400 tcg_cost mismatch for coupon_id: <id>`。

### `GET /coupons/redemption-audit-events`

用途：查詢最近 coupon redemption audit events。

Query：

- `limit`：預設 `20`，範圍 `1..100`。

## Points

### `GET /points/balance`

用途：查詢 Tachiya soulbound points 餘額。

Query：

- `user_id`：Saleor customer id，必填。

Response：

```json
{
  "user_id": "saleor-user-1",
  "balance": 120
}
```

### `GET /points/ledger`

用途：查詢使用者 points ledger。

Query：

- `user_id`：Saleor customer id，必填。
- `limit`：預設 `20`，範圍 `1..100`。

Response entry 欄位：

- `id`
- `amount`
- `entry_type`：`credit` 或 `debit`
- `source_type`
- `reference_id`
- `expires_at`
- `created_at`

### `POST /points/transactions`

用途：受信任營運或系統服務建立 manual points credit/debit。

Request：

```json
{
  "user_id": "saleor-user-1",
  "entry_type": "credit",
  "amount": 120,
  "reference_id": "manual:grant-123",
  "source_type": "manual",
  "expires_at": null
}
```

規則：

- `entry_type` 只接受 `credit` / `debit`。
- `amount` 必須大於 0。
- `user_id`、`reference_id`、`source_type` 不可為空字串。
- 同一個使用者、同一個 `reference_id`、同一個 `entry_type` 重送時維持 idempotent。
- debit 不可讓 balance 變成負數。

### `POST /points/webhooks/order-rewarded`

用途：訂單回饋點數 webhook。

Request：

```json
{
  "order_id": "saleor-order-1",
  "user_id": "saleor-user-1",
  "reward_points": 60
}
```

規則：

- 需要 webhook 簽章。
- `reward_points` 必須大於 0。
- ledger `reference_id` 使用 `order-reward:<order_id>`。
- ledger `source_type` 使用 `order-reward`。

## Referrals

### `POST /referrals/webhooks/order-completed`

用途：訂單完成後處理推薦獎勵。

Request：

```json
{
  "order_id": "saleor-order-1",
  "referee_id": "saleor-user-2",
  "order_total_amount": 1200
}
```

規則：

- 需要 webhook 簽章。
- event id 重放回傳 `409 webhook event already processed`。
- 若訂單沒有符合推薦關係，回傳 `{"rewarded": false}`。
- 若有獎勵，回傳 `reward_points` 與 `ledger_entry_id`。

## Streamers

Streamer profile 是 Tachiya marketplace 的實況主主檔，用來連接 Saleor Collection、前台展示與後續分潤計算。

### `POST /streamers`

Request：

```json
{
  "slug": "streamer-one",
  "display_name": "Streamer One",
  "saleor_collection_id": "collection-1",
  "commission_bps": 1000,
  "active": true
}
```

規則：

- `slug` 會 trim 並轉成小寫，且必須唯一。
- `display_name` 會 trim，且不可為空。
- `saleor_collection_id` 可選；空白視為未設定；有值時必須唯一。
- `commission_bps` 是 basis points，範圍 `0..10000`，預設 `1000`。
- `active` 預設 `true`。

錯誤：

- 重複 slug 或 Saleor collection：`409 streamer profile already exists`。

### `GET /streamers/{slug}`

用途：依 streamer slug 讀取 profile。`slug` 查詢時會 trim 並轉小寫。

找不到時回傳 `404 streamer profile not found`。

### `POST /streamers/product-assignments`

用途：將 Saleor product id 指派給 streamer profile，作為前台歸屬與後續分潤計算的資料基礎。

Request：

```json
{
  "saleor_product_id": "product-1",
  "streamer_slug": "streamer-one",
  "source": "saleor-metadata"
}
```

規則：

- `saleor_product_id` 會 trim，且必須唯一。
- `streamer_slug` 會 trim 並轉小寫，且必須對應已存在的 streamer profile。
- `source` 會 trim，預設 `manual`。
- 同一 product id 重送給同一 streamer/source 會回傳既有 assignment。
- 同一 product id 改指到不同 streamer 或 source 時，會更新既有 assignment。

錯誤：

- streamer 不存在：`404 streamer profile not found`。

### `GET /streamers/product-assignments/{saleor_product_id}`

用途：依 Saleor product id 查詢目前 streamer assignment。

找不到時回傳 `404 streamer product assignment not found`。

## Identity Mappings

Identity mapping 將外部身份連到 Tachiya canonical user id，也就是 Saleor customer id。

### `POST /identity-mappings`

Request：

```json
{
  "saleor_customer_id": "saleor-user-1",
  "provider": "tachigo",
  "external_subject": "tachigo-user-1",
  "actor": "system",
  "reason": "initial link"
}
```

規則：

- `provider` 會正規化成小寫。
- 同一外部身份只能有一個 active mapping。
- 同一 Saleor customer id 同 provider 只能有一個 active mapping。
- link / unlink 都會寫入 identity audit event。

錯誤：

- 衝突：`409 identity mapping already exists` 或 `409 saleor customer already has active provider mapping`。

### `GET /identity-mappings/resolve`

Query：

- `provider`
- `external_subject`

成功時回傳 `saleor_customer_id`；找不到回傳 `404 identity mapping not found`。

### `DELETE /identity-mappings/{mapping_id}`

Query：

- `actor`：預設 `system`。
- `reason`：可選。

用途：解除外部身份連結並留下 audit trail。

### `GET /identity-mappings/audit-events`

Query：

- `limit`：預設 `20`，範圍 `1..100`。

用途：檢視最近身份連結 audit events。

## Tachigo Bridge

### `GET /tachigo/users/points`

用途：依 email 查 Tachigo points 的 demo/local bridge。產品級串接應逐步改用 identity mapping。

Query：

- `email`：必填，最短 3 字元。

Tachiya 會呼叫：

```http
GET <TACHIGO_API_URL>/internal/users/points?email=<email>
X-Tachiya-Internal-Secret: <TACHIYA_INTERNAL_SHARED_SECRET>
```

### `GET /tachigo/identity/{provider}/{external_subject}/points`

用途：依外部身份查 Tachigo points，並確認 Tachiya 端已有 active identity mapping。

規則：

- `provider` 正規化為小寫。
- `external_subject` 會 trim。
- Tachiya 找不到 mapping 時回傳 `404 identity mapping not found`，不呼叫 Tachigo upstream。
- Tachigo upstream 非 200、連線失敗、payload 不合法或 outbound secret 缺失時，router 回傳 `502`。

## 環境變數

| 變數 | 用途 | 預設 |
| --- | --- | --- |
| `DATABASE_URL` | Tachiya API database | `postgresql://saleor:saleor@localhost:5432/saleor` |
| `TACHIYA_INTERNAL_SHARED_SECRET` | internal API 與 webhook HMAC secret | 無，缺失時 fail closed |
| `TACHIYA_WEBHOOK_TOLERANCE_SECONDS` | webhook timestamp 容忍秒數 | `300` |
| `TACHIYA_CORS_ALLOWED_ORIGINS` | 逗號分隔的 API CORS origins | `http://localhost:3000,http://localhost:3001` |
| `TACHIGO_API_URL` | Tachigo backend base URL | `http://localhost:8080` |

## 維護原則

- 新增內部 endpoint 時，同步更新本文件與對應 tests。
- 若 endpoint 會被 Tachigo 或 Storefront 使用，先確認身份主鍵是否仍以 Saleor customer id 為準。
- 新增 webhook 時必須使用 shared signature verifier 與 `WebhookEventService` replay guard。
- 新增 points 異動時必須透過 `PointsService`，不可直接寫 ledger。
