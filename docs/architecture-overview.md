# Tachiya 專案架構與多租戶設計規範

本文件旨在紀錄 Tachiya 平台的技術架構決策、核心組成元件，以及針對經紀公司與實況主設計的多租戶（Multi-tenancy）隔離方案。

## 文件編修註記

- 最近更新：2026-04-07
- 修改工具：Codex
- 修改摘要：補上文件來源註記，納入正式設計文件治理

---

## 1. 核心系統架構

Tachiya 採用以 **Saleor** 為核心的無頭（Headless）電商架構，並透過 **FastAPI** 擴展業務邏輯。

*   **Saleor Core (Port 8000)**: 基於 Django 的 GraphQL API，處理所有核心電商邏輯（訂單、庫存、金流）。
*   **Tachiya API (Port 8001)**: 使用 FastAPI 實作，負責處理平台特有的業務邏輯（如：分潤計算、實況主增益、多租戶權限過濾）。
*   **Saleor Dashboard (Port 9000)**: 管理後台，供平台與經紀公司管理人員使用。
*   **Storefront (Port 3000)**: Next.js 前台，提供消費者瀏覽與下單。

## 2. 技術選型：Headless UI 與 GraphQL

### 優點
*   **多通路支持 (Multi-channel)**: 一套後端可同時支援 Web、App、Twitch 擴充功能等多個前端介面。
*   **精確資料獲取**: GraphQL 允許前端僅請求所需欄位，減少流量消耗。
*   **前端開發自由度**: 經紀公司未來可開發專屬的前端風格而不影響後端邏輯。

### 挑戰
*   **架構複雜度**: 需要管理多個服務與跨服務的認證。
*   **SEO 處理**: 需依賴 Next.js 的 SSR/ISR 技術確保搜尋引擎爬取。

## 3. 多租戶架構設計 (Agency & Streamer)

為了實現「平台 > 經紀公司 > 實況主」的三層架構，我們採用以下邏輯：

### 層級對應關係
1.  **平台 (Tachiya)**: 系統最高管理權限。
2.  **經紀公司 (Agency)**: 對應 Saleor 的 **Staff Group**。
3.  **實況主 (Streamer)**: 對應 Saleor 的 **Channel**。

### 資料隔離方案實作邏輯
我們討論了兩種主要的隔離實作方式：

#### 方案 A：GraphQL Proxy (中介代理)
*   **做法**: 將 Dashboard 的 API 指向 FastAPI，由 FastAPI 解析 GraphQL AST 並注入 `channel` 過濾參數。
*   **缺點**: 實作 AST 解析邏輯較為複雜且有維護成本。

#### 方案 B：獨立 Agency Portal (目前推薦)
*   **做法**: 為經紀公司開發一個輕量級後台，專門呼叫 FastAPI 端點。
*   **優點**: 邏輯最乾淨，開發成本與風險較低。

## 4. Saleor App 通訊機制

Tachiya 與 Saleor 之間的通訊依賴於 Saleor App 架構，主要包含三種管道：

### 註冊握手 (Handshake)
App 提供 `manifest.json` 定義權限，安裝時透過 Token 交換建立信任關係。

### Webhooks (事件驅動)
*   **非同步 Webhooks**: 用於訂單成立後的後續處理（如：分潤計算）。
*   **同步 Webhooks**: 用於攔截特定操作（如：自定義稅率計算或運費）。
*   **安全性**: 必須透過 `X-Saleor-Signature` 與共享密鑰（Shared Secret）驗證簽章。

### GraphQL API
App 使用專屬 Access Token 主動呼叫 Saleor Core 修改資料。

### App Bridge
當 App UI 嵌入 Dashboard 時，透過 iframe 的 `postMessage` 與父視窗進行跨域通訊。

## 5. 開發建議

1.  **安全性**: 在 FastAPI 中務必實作簽章驗證與多租戶過濾依賴項（Dependencies）。
2.  **效能**: 針對頻繁的 GraphQL 查詢，建議在 FastAPI 層級實作快取機制。
3.  **擴充性**: 保持 `Tachiya API` 的獨立性，使其成為一個標準化的 OpenAPI 服務，方便未來第三方經紀公司對接。
