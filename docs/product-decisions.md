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
├──tachiya/frontend/    # 電商前端，獨立repo（nurockplayer/storefront，fork 自 saleor/storefront）
├── 獨立的 git repo（有自己的 `.git`），不是 git submodule
└── 以獨立 VSCode workspace + Claude Code 開發，不在此 repo 的 git 管理範圍內
```

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
