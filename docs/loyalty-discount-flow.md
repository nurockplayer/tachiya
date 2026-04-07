# 忠誠點數兌換 Saleor 折扣設計稿

本文件整理目前已確認的背景、現況調查、推薦方案與下一步實作方向，供之後回頭接續開發時快速恢復上下文。

## 文件編修註記

- 最近更新：2026-04-07
- 修改工具：Codex
- 修改摘要：整理忠誠點數兌換 Saleor 折扣的現況、方案比較與 API contract 草案

---

## 1. 問題背景

Tachiya 的目標之一是讓使用者能把姊妹專案 `tachigo` 中取得的忠誠點數，兌換成可在 Saleor 商城使用的折扣。

預期高階流程：

1. 使用者在 `tachigo` 累積忠誠點數
2. 使用者發起兌換
3. `tachigo` 驗證資格並扣點
4. `tachiya api/` 建立可在 Saleor 使用的折扣憑證
5. 使用者在 `tachiya/frontend/` checkout 套用折扣
6. Saleor 計算折扣後總額並完成結帳

這代表 `tachigo`、`tachiya api/`、`Saleor`、`frontend` 之間需要一條清楚且可追蹤的兌換鏈路。

---

## 2. 現況結論

### 已有的產品方向

在 [product-decisions.md](product-decisions.md) 中，已經先確立以下方向：

- `tachigo` 與 `tachiya` 維持獨立 repo
- 兩者透過 API 邊界串接
- `tachigo` 負責忠誠點數 / token
- `tachiya api/` 負責 Saleor 自訂邏輯
- Saleor 負責結帳、訂單與折扣計算

既有文件中的串接點描述為：

```text
Twitch 觀眾
  → tachigo extension（累積 token）
  → tachigo go backend（驗證 token）
  → tachiya FastAPI（銷毀 token，產生折扣碼）
  → Saleor（套用折扣碼結帳）
```

### 本次額外確認到的事

- 目前 storefront 已經具備顯示 Saleor 折扣的基礎能力
- 商品頁、商品列表、購物車、checkout summary 都已有折扣 UI
- 但 checkout 的折扣碼輸入目前仍是 UI mock，尚未真正呼叫 Saleor mutation

---

## 3. 現有前端如何顯示折扣

目前 `frontend/` 的折扣顯示分成兩類：

1. 商品級折扣
2. Checkout 級折扣

### 商品級折扣

核心判斷集中在 [frontend/src/lib/pricing.ts](../frontend/src/lib/pricing.ts)：

- `undiscountedPrice > currentPrice` 即視為有折扣
- `discountPercent` 由兩者差額計算

目前已接上的畫面：

- PDP 商品頁  
  來源：
  [frontend/src/ui/components/pdp/variant-section-dynamic.tsx](../frontend/src/ui/components/pdp/variant-section-dynamic.tsx)  
  顯示：
  - 主價格
  - 刪除線原價
  - 折扣百分比
  - `Sale` badge

- PLP 商品列表  
  來源：
  [frontend/src/ui/components/plp/utils.ts](../frontend/src/ui/components/plp/utils.ts)  
  [frontend/src/ui/components/plp/product-card.tsx](../frontend/src/ui/components/plp/product-card.tsx)  
  顯示：
  - 現價
  - 刪除線原價
  - `Sale` badge

- Cart 購物車  
  來源：
  [frontend/src/ui/components/cart/cart-drawer.tsx](../frontend/src/ui/components/cart/cart-drawer.tsx)  
  顯示：
  - line total
  - 有折扣時顯示刪除線原價

對應 GraphQL 欄位：

- [frontend/src/graphql/ProductListItem.graphql](../frontend/src/graphql/ProductListItem.graphql)
- [frontend/src/graphql/VariantDetailsFragment.graphql](../frontend/src/graphql/VariantDetailsFragment.graphql)

### Checkout 級折扣

Checkout summary 已經有讀取折扣相關欄位：

- `checkout.discount`
- `voucherCode`
- `discountName`

來源：

- [frontend/src/checkout/graphql/checkout.graphql](../frontend/src/checkout/graphql/checkout.graphql)
- [frontend/src/checkout/views/saleor-checkout/order-summary.tsx](../frontend/src/checkout/views/saleor-checkout/order-summary.tsx)

目前狀態：

- UI 有「Discount code」輸入框
- UI 會顯示折扣金額列
- 但套用折扣碼目前仍是 mock
- 尚未真正呼叫 Saleor 的 promo code mutation

因此，如果要最快把「忠誠點數換折扣」做通，最短路徑會是補完 checkout promo code flow。

---

## 4. 為什麼優先選 Saleor Voucher

本次調查比較了三種 Saleor 原生折扣機制：

1. Voucher
2. Order Promotion
3. Catalogue Promotion

### 推薦：Voucher

最適合目前需求的是 `Voucher`，原因如下：

- 它天然符合「外部資格兌換後，得到一組可在結帳使用的折扣碼」
- 可限制使用次數、有效期限、channel、折扣型別
- 前端現有 checkout summary 結構已經能承接
- 不需要先把 `tachigo` 的忠誠點數模型塞進 Saleor 內部規則系統

適合的使用情境：

- `100 points -> 折抵固定金額`
- `200 points -> 9 折 voucher`
- 單次兌換、一次性使用

### 不優先：Order Promotion

`Order Promotion` 更適合站內自動規則，例如：

- 滿額折
- 滿件折
- 訂單條件達成後自動打折

它比較不像「外部系統先驗證忠誠點數，再授予特定使用者一筆折抵資格」。

### 不優先：Catalogue Promotion

`Catalogue Promotion` 比較適合商品本身進入促銷狀態，例如：

- 某個商品或分類本月特價
- 所有人看到的商品價格直接變低

這不符合「由使用者個人兌換而來的折扣資格」。

---

## 5. 建議的最小可行方案

先不把鏈上 / token 流程直接接進 Saleor，先做「點數兌換 voucher code」的最小可行版本。

### MVP 流程

1. 使用者在 `tachigo` 選擇一個兌換方案
2. `tachigo` 驗證點數足夠
3. `tachigo` 扣點並建立 `redemption` 紀錄
4. `tachigo` 以 server-to-server 方式呼叫 `tachiya api/`
5. `tachiya api/` 透過 Saleor Admin API 建立或配發一組 voucher code
6. `tachiya api/` 回傳 code 與折扣資訊
7. 使用者跳轉到 `tachiya` checkout
8. storefront 呼叫 Saleor 的 promo code mutation
9. checkout summary 顯示折扣結果

### 先建議固定的規則

- 固定兌換面額，不先做自由輸入
- 先只做一種折扣型別
- 每次兌換產生單次使用 code
- code 綁定 channel
- code 設有效期限

範例：

- `100 points -> 5 EUR off`
- `200 points -> 10% off`

---

## 6. 服務責任切分

### `tachigo`

- 保管忠誠點數帳本
- 定義可兌換的 reward catalog
- 驗證兌換資格
- 扣點
- 防止重複兌換

### `tachiya api/`

- 接收來自 `tachigo` 的兌換請求
- 驗證 service-to-service 請求是否合法
- 與 Saleor Admin API 溝通
- 建立或配發 voucher code
- 記錄 redemption 與 Saleor voucher 的對應

### `Saleor`

- 真正執行折扣計算
- 維護 voucher 規則
- 在 checkout / order 上反映折扣結果

### `frontend`

- 顯示折扣碼輸入或自動套用流程
- 呼叫 Saleor promo code mutation
- 顯示已套用折扣的 checkout summary

---

## 7. 建議資料流

```text
使用者
  → tachigo frontend / extension
  → tachigo backend
      - 驗證點數
      - 扣點
      - 建立 redemption
  → tachiya api
      - 驗證請求簽章
      - 建立 / 配發 Saleor voucher code
      - 回傳 code
  → tachiya frontend checkout
      - 套用 promo code
  → Saleor
      - 計算 discount / total
      - 建立 order
```

---

## 8. API Contract 草案

這是下一步可直接拿去實作的 server-to-server contract 草案。

### Endpoint

`POST /internal/redemptions`

用途：

- 由 `tachigo backend` 呼叫
- 要求 `tachiya api/` 建立一筆對應 Saleor 折扣的 redemption

### Request body

```json
{
  "requestId": "red_20260407_001",
  "sourceProject": "tachigo",
  "sourceUserId": "user_123",
  "saleorCustomerId": "Q3VzdG9tZXI6MQ==",
  "channelSlug": "default-channel",
  "reward": {
    "type": "fixed_amount",
    "value": "5.00",
    "currency": "EUR"
  },
  "pointsSpent": 100,
  "expiresAt": "2026-04-30T23:59:59Z",
  "metadata": {
    "campaign": "loyalty-launch"
  }
}
```

### Response body

```json
{
  "redemptionId": "rdm_01",
  "status": "issued",
  "saleorVoucherCode": "TG-5OFF-ABCD1234",
  "reward": {
    "type": "fixed_amount",
    "value": "5.00",
    "currency": "EUR"
  },
  "channelSlug": "default-channel",
  "expiresAt": "2026-04-30T23:59:59Z"
}
```

### Error cases

- `400 Bad Request`
  - 欄位缺漏
  - reward 型別不支援

- `401 Unauthorized`
  - service secret / 簽章驗證失敗

- `409 Conflict`
  - `requestId` 已使用
  - 同一 redemption 已建立過 voucher

- `422 Unprocessable Entity`
  - Saleor voucher 建立失敗
  - channel 不存在

- `500 Internal Server Error`
  - 非預期錯誤

### 重要原則

- 必須支援 idempotency，以 `requestId` 去重
- 不信任前端直接發請求
- 僅接受 `tachigo backend` 的 server-to-server 呼叫

---

## 9. 資料表草案

`tachiya api/` 建議至少有一張 `redemptions` 表：

| 欄位 | 用途 |
|---|---|
| `id` | 內部 redemption ID |
| `source_project` | 來源系統，例如 `tachigo` |
| `source_user_id` | 來源使用者 ID |
| `saleor_customer_id` | 對應 Saleor customer |
| `channel_slug` | voucher 適用 channel |
| `points_spent` | 本次扣除點數 |
| `reward_type` | `fixed_amount` / `percentage` |
| `reward_value` | 折扣值 |
| `reward_currency` | 幣別 |
| `saleor_voucher_code` | 實際發出的 code |
| `status` | `issued` / `applied` / `expired` / `cancelled` |
| `request_id` | idempotency key |
| `issued_at` | 發券時間 |
| `applied_at` | 使用時間 |
| `expires_at` | 過期時間 |
| `metadata_json` | 額外上下文 |

後續若需要更強的稽核能力，可再補：

- `saleor_checkout_id`
- `saleor_order_id`
- `signature_verified`
- `source_payload_hash`

---

## 10. 資安要求

這條流程必須符合既有安全假設，特別是 [security-owasp.md](security-owasp.md) 中已提到的要求：

- `tachigo backend -> tachiya api/` 必須使用共享 secret 或 HMAC 簽章
- FastAPI endpoint 不應暴露給一般前端直接呼叫
- 呼叫 Saleor GraphQL 時一律使用 variables，不拼接 query
- voucher 應限制為一次性或低次數使用
- 需記錄兌換、發券、套用與失敗事件

---

## 11. 前端下一步

目前 storefront 最值得先做的不是改商品頁，而是補完 checkout promo code flow。

### 要補的能力

1. 在 checkout 呼叫 Saleor promo code mutation
2. mutation 成功後重新抓 checkout
3. 在 summary 顯示：
   - voucher code
   - 折扣名稱
   - 折扣金額
4. 支援從 query param 或 session 預帶 code

### 可能的入口

- `/checkout?promo=TG-5OFF-ABCD1234`
- 或從 `tachigo` 深連結到 `tachiya`

---

## 12. 推薦的執行順序

### Phase 1

- 文件定稿
- 確定 reward catalog
- 確定 voucher 規則

### Phase 2

- `tachiya api/` 建立 `POST /internal/redemptions`
- 實作 Saleor Admin API 呼叫
- 補 redemption persistence

### Phase 3

- `frontend` 接上 checkout promo code mutation
- 顯示實際折扣結果
- 支援預帶 promo code

### Phase 4

- `tachigo` 串接正式兌換流程
- 做 end-to-end 測試

---

## 13. 當前決策摘要

目前先採用以下方向：

- 忠誠點數兌換 Saleor 折扣，優先走 `Voucher`
- 折扣以 checkout 套用為主，不先改成 catalogue discount
- `tachigo` 管點數與兌換資格
- `tachiya api/` 管 Saleor voucher 配發
- `frontend` 先補齊 checkout promo code flow

這是最短、最容易驗證、也最符合現有前端結構的路徑。

---

## 變更記錄

| 日期 | 執行者 | 說明 |
| --- | --- | --- |
| 2026-04-07 | Claude Code | 初版文件建立（問題背景、現況結論、推薦方案、API contract、資料表、資安要求、執行順序） |
| 2026-04-07 | Codex | 實際搜尋 `api/` 與 `frontend/` 確認現有折扣程式碼分布，補充 §2、§3 的「已額外確認到的事」與 storefront 現況細節 |
