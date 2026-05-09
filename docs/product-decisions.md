# Product Decisions

紀錄重要的產品設計決策，包含考慮過的選項與最終選擇的理由。

---

## 平台定位：經紀公司模式

**決策：一個商城，區分旗下每個實況主。**

### 考慮過的選項

| 模式 | 說明 | 放棄理由 |
|------|------|----------|
| Marketplace | 跨實況主的開放市集，觀眾可逛所有人的店 | 實況主品牌認同低、平台內部競爭、退款糾紛複雜 |
| 獨立店（Shopify 模式） | 每個實況主完全獨立的店面 | 觀眾體驗割裂、流量孤立、難以做平台層級行銷 |
| **經紀公司模式** | 一個商城，商品依實況主區分 | **採用** |

### 選擇理由

- 觀眾在同一個店、同一個帳號結帳，體驗一致
- 實況主有自己的頁面與品牌識別感
- 平台可以做統一的行銷活動
- 分潤計算清楚，依商品歸屬實況主拆帳

---

## 實況主區分方式：Collection + Metadata

**決策：使用 Saleor Collection + 商品 Metadata 區分實況主。**

### 考慮過的選項

| 方案 | 說明 | 放棄理由 |
|------|------|----------|
| Saleor Channel | 每個實況主一個 Channel | 跨 Channel 無法合併結帳，觀眾要分開下單 |
| Category | 每個實況主一個分類 | 實況主沒有獨立頁面感 |
| **Collection + Metadata** | 一個 Channel，每人一個 Collection，商品打 metadata | **採用** |

### 實作重點

- **一個 Saleor Channel**：統一結帳流程
- **每個實況主一個 Collection**：獨立頁面與視覺識別
- **商品 Metadata**：記錄歸屬（`streamer: <id>`），供分潤計算使用
- **分潤計算**：由 Tachiya API 負責，依訂單內商品的 metadata 拆帳

---

## 實況主入駐方式：雙軌並行

**決策：以經紀公司談判為主，同時保留自助申請入口（需人工審核）。**

### 考慮過的選項

| 方式 | 優點 | 缺點 |
|------|------|------|
| 純經紀公司談判 | 一次帶來一批實況主、品質有保障 | 沒有經紀公司的實況主無法入駐 |
| 純自助申請 | 開放給所有實況主 | 需要自己審核品質、冷啟動靠行銷 |
| **雙軌並行** | 兩者兼顧 | **採用** |

### 執行方式

- 早期以洽談經紀公司為主要拓展方式
- 同時開放自助申請入口，設人工審核機制
- 無經紀公司的獨立實況主可申請，通過審核後入駐

---

## Repo 結構：Tachigo 與 Tachiya 分開

**決策：兩個系統維持獨立的 repo。**

- **Tachigo**：Twitch extension + Web3 token 獎勵系統（Go + React）
- **Tachiya**：直播電商平台（Saleor + Tachiya API）

### 選擇理由

- 部署週期不同（Twitch extension 有審核流程）
- 關注點完全不同，團隊可獨立作業
- 兩者透過 API 邊界連接（例如：Tachigo token 換取 Tachiya 折扣碼）

---

## 系統架構總覽

### Tachigo（獨立 repo）

```
tachigo/
├── extension      # Twitch 擴充功能（React）
└── go backend     # 會員系統、Token 發放（Go）
```

### Tachiya（此 repo）

```
tachiya/
├── Saleor backend   # 電商核心，拉官方 Docker image，不改動
├── Saleor dashboard # 電商後台，build 自己的 image（繁體中文化）
├── api/             # FastAPI，處理折扣與區塊鏈代幣銷毀的中間層
└── frontend/        # Storefront（獨立 git repo，掛在此目錄下）
```

### Storefront（`tachiya/frontend/`）

```
tachiya/frontend/    # 電商前端，自己的 fork（nurockplayer/storefront，fork 自 saleor/storefront）
```

- 獨立的 git repo（有自己的 `.git`），不是 git submodule，也不在此 repo 的 git 管理範圍內
- 以獨立 VSCode workspace + Claude Code 開發

### 串接點

```
Twitch 觀眾
  → tachigo extension（累積 token）
  → tachigo go backend（驗證 token）
  → tachiya FastAPI（銷毀 token，產生折扣碼）
  → Saleor（套用折扣碼結帳）
```

### 各服務維護方式

| 服務 | 來源 | 維護方式 |
|------|------|----------|
| Saleor backend | 官方 Docker image | 不改動，直接拉 |
| Saleor dashboard | fork 官方，自行 build | 繁體中文化，推 GHCR |
| Saleor frontend | 自己的 fork（`nurockplayer/storefront`） | 見 `frontend/` 目錄 |
| FastAPI | 自行開發 | 在此 repo 的 `api/` 目錄 |

---

## 後端架構：三服務拆法

**決策：Go（tachigo）、FastAPI（tachiya api/）、Saleor 三者維持獨立，不整合。**

### 考慮過的選項

| 方案 | 說明 | 放棄理由 |
|------|------|----------|
| 用 Go 取代 FastAPI | 把折扣/分潤邏輯移進 tachigo Go backend | 把兩個不同域的關注點混在一起，長期難維護 |
| **三服務各自獨立** | Go / FastAPI / Saleor 分開部署 | **採用** |

### 各服務職責

- **Saleor**：電商核心（購物車、訂單、結帳、Saleor 自己的帳號系統）
- **Go（tachigo）**：Twitch 身份、忠誠點數、token 發放——自建會員系統
- **FastAPI（tachiya api/）**：Saleor 的自訂邏輯出口（折扣計算、分潤、webhook 處理）；不動 Saleor 原始碼的前提下擴充業務邏輯

### 會員系統不衝突

Saleor Account 只管「能結帳的帳號」（購物車、訂單、地址），Go 會員系統管忠誠點數與 Twitch 身份，兩者用 Saleor customer ID 關聯，職責不重疊。

### 維持三服務的理由

- FastAPI 是保護層：沒有它，未來要自訂邏輯只能 fork Saleor
- 三服務用 docker-compose 管理，部署成本低，FastAPI 輕量可與其他服務共機
- 等未來 FastAPI 真的不再成長、只剩一兩支 API，再評估是否併入 Go

---

## Token 經濟：Tachiya 點數採 Soulbound 商店信用

**決策：Tachiya MVP 的點數是綁定 Saleor/Tachiya 使用者帳號的商店信用，不提供使用者之間轉移。**

Tachigo 可以維持自己的 token / Web3 / Twitch 忠誠點數規則；一旦透過 API 轉入 Tachiya，該價值在 Tachiya 內會被視為電商場景的折扣、點數或分潤信用，不再繼續承擔可自由轉移的 token 語意。

### 考慮過的選項

| 方案 | 說明 | 放棄理由 |
|------|------|----------|
| 使用者可自由轉移 Tachiya 點數 | 點數可像 token 一樣在使用者間流通 | 退款、洗點、盜帳與分潤追蹤成本過高；也會讓 Saleor 訂單信用與 Tachigo token 邊界混在一起 |
| 特定關係內可轉移 | 例如家庭帳號、好友或公會內轉移 | MVP 需要額外關係模型、風控與爭議處理，會延後商城核心驗證 |
| **帳號綁定商店信用** | 點數只能由受信任服務入帳/扣帳，使用者不能互轉 | **採用** |

### 邊界規則

- **Tachigo token**：屬於 Tachigo domain，可以依 Tachigo 的產品規則處理累積、驗證、鏈上或鏈下流通。
- **Tachiya points**：屬於 Tachiya domain，是商城內的帳號信用，只能折抵、回饋或做分潤紀錄。
- **轉換邊界**：Tachigo 透過內部 API 或兌換流程把 token 價值交給 Tachiya 後，Tachiya 只保存兌換結果與 ledger，不保存可轉移 token 狀態。
- **使用者體驗**：Storefront 可以顯示餘額、折抵紀錄與兌換結果，但不提供轉移入口。

### 實作原則

- Soulbound 以後端與資料模型為準，不依賴前端隱藏按鈕作為唯一限制。
- Tachiya API 不提供使用者對使用者的 transfer endpoint。
- 點數異動必須經過受信任服務，例如 `PointsService.credit()`、`PointsService.debit()`、referral webhook、coupon redemption 或未來的 Tachigo 兌換 webhook。
- `PointsLedger` 的 `entry_type` 保持為 `credit` / `debit`；業務來源暫時放在 `reference_id` namespace，例如 `referral:<order_id>`、`tachigo:<redemption_id>`、`coupon:<code>`。
- 過期點數不放進 MVP；若未來需要點數到期，應新增 ledger 層級的 `expires_at` 或 policy 欄位，不用前端倒數或批次字串規則處理。

### 後續待補

- 若營運需要區分「消費回饋」、「分潤」、「Tachigo 兌換」等來源，新增 `PointsLedger.source_type`。
- 若法務或活動規則需要點數到期，新增 `PointsLedger.expires_at` 與到期扣帳流程。
- 若 Tachigo 仍需要可流通 token，維持在 Tachigo repo 內設計，不回填成 Tachiya 使用者可互轉點數。
