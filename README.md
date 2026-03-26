# Tachiya

每位實況主都有各自賣場的直播電商平台。

## 架構

```text
┌────────────────────────────────────────────────────┐
│  Browser                                           │
│  ┌──────────────┐  ┌──────────────┐                │
│  │  Storefront  │  │  Dashboard   │                │
│  │  :3000       │  │  :9000       │                │
│  └──────┬───────┘  └──────┬───────┘                │
└─────────┼─────────────────┼───────────────────────-┘
          │ GraphQL          │ GraphQL
          ▼                  ▼
┌───────────────────────────────────────────────────┐
│  Saleor  :8000  (headless e-commerce API)         │
│  - 商品、訂單、付款、庫存                             │
│  - 多 Channel（每個實況主一個賣場）                   │
└──────────────┬────────────────────────────────────┘
               │ Webhook / GraphQL
               ▼
┌───────────────────────────────────────────────────┐
│  Tachiya API  :8001  (FastAPI)                 │
│  - 實況主管理、粉絲消費增益、分潤計算                    │
│  - 直播串接                                         │
└────────────────────────────────────────────────────┘
```

| Service | Port | 說明 |
|---------|------|------|
| Saleor API | 8000 | GraphQL 電商引擎 |
| Tachiya API | 8001 | FastAPI 業務邏輯 |
| Dashboard | 9000 | Saleor 後台管理（繁體中文） |
| Storefront | 3000 | 顧客購物前台（dev 用 pnpm dev） |
| Mailpit | 8025 | 本地 email 測試 |
| PostgreSQL | 5432 | 資料庫（dev 直連用） |
| Valkey | 6379 | Cache / Celery broker |

## 快速開始

```bash
# 安裝需求：Docker、Python 3.12+、pnpm（storefront 用）

make setup        # 一鍵建環境、跑 migration、建 superuser
make frontend     # 另開終端機跑 storefront（本機 pnpm dev）
```

預設帳號：`admin@example.com` / `admin`（`.env` 可修改）

## 常用指令

```bash
make up           # 啟動所有服務
make down         # 停止所有服務
make migrate      # 跑 Saleor migration
make superuser    # 建立 Saleor 管理員帳號
make logs         # 看所有 log
make shell        # 進 Saleor Django shell
```

## 目錄結構

```text
tachiya/
├── api/                # Tachiya FastAPI（自訂業務邏輯）
├── translations/       # 自訂翻譯（繁體中文 Dashboard）
├── docker-compose.yml
├── docker-compose.override.yml  # Dev 覆蓋設定
├── Makefile
└── .env.example
```

> `frontend/` 和 `dashboard/` 由 `make clone-deps` 自動從上游 clone，不進 git。
