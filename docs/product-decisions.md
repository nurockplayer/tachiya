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
└── frontend/        # Storefront 本機 checkout（正式 repo: nurockplayer/storefront）
```

### Storefront（`tachiya/frontend/`）

```
tachiya/frontend/    # 電商前端，自己的 fork（nurockplayer/storefront，fork 自 saleor/storefront）
```

- 獨立的 git repo（正式 repo: `nurockplayer/storefront`），不是 git submodule，也不在此 repo 的 git 管理範圍內。
- 本機建議使用 `/Users/erickwang/Desktop/storefront` 作為 Storefront 工作區；`tachiya/frontend/` 只視為可被 `make clone-deps` 重新建立的 checkout。
- Storefront 的 lint / test / build / E2E PR gate 在 Storefront repo 自己執行；Tachiya root repo 只用 cross-repo contract gate 檢查共享契約。

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
- 點數異動必須經過受信任服務，例如 `PointsService.credit()`、`PointsService.debit()`、referral webhook、coupon redemption 或 Tachigo 兌換 webhook。
- `PointsLedger` 的 `entry_type` 保持為 `credit` / `debit`；業務來源使用 `source_type`，具體事件仍放在 `reference_id` namespace，例如 `referral:<order_id>`、`tachigo:<redemption_id>`、`coupon:<code>`。
- `PointsLedger.expires_at` 由後端餘額與扣帳流程生效；目前可用餘額排除已過期且未消耗的 credit。
- 扣帳以 ledger 時序計算，並以 FIFO 優先消耗較早到期的 credit；已在到期前花掉的 credit 不會在到期後被重複扣回。
- 前端可以顯示 `expires_at` 作為資訊，但不得自行用倒數、字串規則或 client-side 過濾取代後端餘額。

### 後續待補

- 補到期點數的營運報表與批次對帳；MVP 已能在可用餘額與扣帳流程排除過期 credit，但尚未產生獨立 expiration adjustment ledger。
- 補營運層級的點數來源分類規則；`PointsLedger.source_type` 已落地，但各活動來源仍需明確命名慣例。
- 若 Tachigo 仍需要可流通 token，維持在 Tachigo repo 內設計，不回填成 Tachiya 使用者可互轉點數。

---

## 身份映射：Tachiya 以 Saleor customer id 作為 canonical user id

**決策：Tachiya domain 內的點數、推薦、折扣與分潤紀錄，長期以 Saleor customer id 作為 canonical `user_id`。**

Email、Twitch user id、Tachigo member id、wallet address 都是可連結身份或查詢屬性，不應直接成為 Tachiya ledger 的長期主鍵。這讓使用者更換 email、解除 Twitch 連結或更換 wallet 時，不會讓既有訂單、點數與推薦紀錄失去歸屬。

### 考慮過的選項

| 方案 | 說明 | 放棄理由 |
|------|------|----------|
| Email 作為主鍵 | Storefront 與 Tachigo 都容易取得 | Email 會變更，也可能大小寫、別名或社群登入同步不一致 |
| Twitch user id 作為主鍵 | 與 Tachigo extension 最接近 | 非所有商城使用者都有 Twitch；也會把 Tachigo 身份語意帶進 Tachiya |
| Tachiya 自建 identity id | 最彈性，可管理多身份連結 | MVP 需要多一層 identity service，短期成本高 |
| **Saleor customer id 作為 Tachiya canonical id** | 與訂單、結帳、帳戶頁一致 | **採用** |

### 邊界規則

- **Tachiya canonical `user_id`**：使用 Saleor customer id；`PointsLedger.user_id`、`ReferralRelationship.referrer_id`、`ReferralRelationship.referee_id` 以此為準。
- **Email**：只作為登入聯絡資訊、搜尋 fallback 或 demo bridge，不作為永久歸屬鍵。
- **Tachigo / Twitch identity**：透過受信任 server-to-server API 對應到 Saleor customer id；Tachigo 不直接寫入 Tachiya ledger。
- **Wallet address**：視為可連結的 claim/login 屬性，不代表 Tachiya 點數可隨 wallet 轉移。
- **帳號合併**：不得自動依 email 或 wallet 合併；需要人工審核或明確的 signed identity proof，並留下 audit trail。

### Tachigo 串接過渡策略

目前以 email 查詢 Tachigo points 的做法只適合 demo / local bridge。產品級串接應改為：

1. Storefront 取得 Saleor customer id。
2. Tachiya API 以 internal secret 或 webhook signature 接收 Tachigo 事件。
3. Tachiya 驗證 Tachigo event id / timestamp / signature。
4. Tachiya 透過 identity mapping 找到 Saleor customer id。
5. Tachiya 用 `PointsService` 寫入 Soulbound ledger。

### 更換與解除連結

- 更換 email 不搬移 ledger；ledger 仍屬於同一 Saleor customer id。
- 解除 Twitch 連結不刪除既有 Tachiya 點數或推薦紀錄，只停止新的 Tachigo 兌換。
- 更換 wallet 或重新連結外部身份需要重新驗證持有權；Tachiya 點數不因 wallet 轉移而轉移。
- 已解除連結的外部身份可在重新驗證後 relink，並必須留下 `identity.relinked` audit trail。
- 若真的需要帳號合併，必須以後台操作或 migration 方式執行，並記錄來源帳號、目標帳號、操作者與原因。

### 後續待補

- 將 identity mapping 串進 Tachigo/Twitch/wallet 的 signed identity lookup，不再依 demo email bridge 做產品級查詢。
- 規劃並淘汰 `GET /tachigo/users/points?email=...` 的前台依賴。
- 補帳號合併、identity proof、解除連結後台操作規格；目前 link / unlink 已有基本 audit trail。
