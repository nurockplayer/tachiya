# Security Checklist — OWASP Top 10

針對 tachiya 架構（Saleor + FastAPI + tachigo）的資安對照清單。

## 文件編修註記

- 最近更新：2026-04-07
- 修改工具：Codex
- 修改摘要：補上文件來源註記，納入正式安全文件治理

---

## 架構快速回顧

```
Twitch 觀眾
  → tachigo extension（累積 token）
  → tachigo Go backend（驗證 token）
  → tachiya FastAPI（銷毀 token，產生折扣碼）    ← 高風險區
  → Saleor（套用折扣碼結帳）
```

服務邊界是主要攻擊面：任何跨服務的 API 呼叫都需要驗證來源身份。

---

## A01 — Broken Access Control（存取控制失效）

**風險點**

- FastAPI 的折扣碼 endpoint 若未驗證呼叫方，任何人都能直接觸發 token 銷毀
- Saleor GraphQL API 若暴露在外，攻擊者可直接操作訂單

**對策**

- [ ] FastAPI ↔ tachigo Go backend 之間使用共享 secret（HMAC 簽章或 service token），不信任純 IP 限制
- [ ] FastAPI endpoint 不對外公開，僅允許 tachigo Go backend 呼叫（docker-compose 網路隔離 + 不 expose port）
- [ ] Saleor GraphQL mutation（createOrder、applyVoucher 等）只透過 FastAPI 觸發，不直接給 frontend 呼叫
- [ ] 每個使用者只能查詢自己的訂單（Saleor 預設有保護，確認未被 override）

---

## A02 — Cryptographic Failures（加密失效）

**風險點**

- 折扣碼若可預測，攻擊者可暴力枚舉
- 服務間通訊若走明文 HTTP，token 可被攔截

**對策**

- [ ] 折扣碼使用 `secrets.token_urlsafe(32)` 或同等方式產生（不用 UUID v4，熵值不夠）
- [ ] 生產環境服務間通訊走 HTTPS（即使是 internal）
- [ ] 敏感設定（`SECRET_KEY`、資料庫密碼、service token）放環境變數，不進 repo
- [ ] 確認 Saleor 的 `SECRET_KEY` 在 `.env` 中有設定且夠長（至少 50 字元隨機字串）

---

## A03 — Injection（注入）

**風險點**

- FastAPI 若把 user input 直接拼接進 Saleor GraphQL query，可能造成 GraphQL injection
- FastAPI 若有 ORM 查詢，需確認不使用原始字串拼接

**對策**

- [ ] Saleor GraphQL 呼叫一律使用 variables 傳參，不拼接字串

  ```python
  # 正確
  query = """
  mutation ApplyVoucher($checkoutId: ID!, $code: String!) {
    checkoutAddPromoCode(checkoutId: $checkoutId, promoCode: $code) { ... }
  }
  """
  variables = {"checkoutId": checkout_id, "code": code}

  # 錯誤（有 injection 風險）
  query = f"mutation {{ checkoutAddPromoCode(checkoutId: \"{checkout_id}\", ...) }}"
  ```

- [ ] FastAPI 的 ORM（若使用 SQLAlchemy）使用 parameterized query，不用 `text()` 拼接

---

## A04 — Insecure Design（不安全設計）

**風險點**

- Token 銷毀流程若沒有冪等性保護，同一個請求重試可能重複發折扣碼

**對策**

- [ ] Token 銷毀 + 折扣碼產生設計為原子操作（先扣點、再產碼，失敗則 rollback）
- [ ] 使用 idempotency key（如 request UUID）防止重複處理
- [ ] 折扣碼設定為一次性使用（Saleor Voucher 的 `usageLimit: 1`）

---

## A05 — Security Misconfiguration（安全設定錯誤）

**風險點**

- Saleor / FastAPI 開發設定流入生產（DEBUG 模式、詳細錯誤訊息）
- Docker 服務 port 不必要地暴露在外

**對策**

- [ ] 生產環境確認 `DEBUG=False`（Saleor Django 設定）
- [ ] FastAPI 不回傳 stack trace 給 client（用 exception handler 包裝）
- [ ] `docker-compose.prod.yml` 只 expose 必要的 port（Nginx/Caddy 在前面擋）
- [ ] Saleor Dashboard 設定 `ALLOWED_CLIENT_HOSTS`，不用 `*`
- [ ] 移除或停用未使用的 Saleor plugin

---

## A06 — Vulnerable & Outdated Components（已知漏洞元件）

**風險點**

- Saleor 官方 Docker image 有 upstream 漏洞時，需要追蹤並更新
- FastAPI 的 Python 套件可能有已知 CVE

**對策**

- [ ] 訂閱 [Saleor releases](https://github.com/saleor/saleor/releases)，有 security patch 時優先更新 image tag
- [ ] CI 加入 `pip audit`（Python）掃描 FastAPI 的依賴
- [ ] Frontend 加入 `npm audit`（或 `pnpm audit`）定期掃描
- [ ] 固定 Docker image tag（不用 `latest`），變更時有明確的版本紀錄

---

## A07 — Identification & Authentication Failures（身份驗證失效）

**風險點**

- tachigo → FastAPI 的服務間驗證若只靠 IP，容易被繞過
- Saleor 使用者帳號若無速率限制，可被暴力破解

**對策**

- [ ] 服務間呼叫使用 bearer token（在 `Authorization` header），並在 FastAPI 中驗證
- [ ] Token 設定過期時間，定期輪換
- [ ] Saleor 前面的 Nginx/Caddy 設定登入 endpoint 的 rate limit（例如 `/graphql/` 的 mutation 限速）
- [ ] 不在 URL query string 傳遞 token（會被記進 log）

---

## A08 — Software & Data Integrity Failures（軟體與資料完整性失效）

**風險點**

- CI/CD pipeline 若從外部拉取未驗證的 image 或 script，可能被供應鏈攻擊
- Saleor webhook 若不驗簽，任何人都可以偽造事件

**對策**

- [ ] Saleor webhook 使用 signature header 驗證（Saleor 會附 `Saleor-Signature`，需在 FastAPI 中驗證）

  ```python
  import hmac, hashlib

  def verify_saleor_webhook(payload: bytes, signature: str, secret: str) -> bool:
      expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
      return hmac.compare_digest(expected, signature)
  ```

- [ ] Docker image 固定 digest（`sha256:...`）或至少固定版本 tag，不用 `latest`
- [ ] GitHub Actions 使用固定版本的 action（`uses: actions/checkout@v4`，不用 `@main`）

---

## A09 — Security Logging & Monitoring Failures（日誌與監控不足）

**風險點**

- Token 銷毀與折扣碼產生是金流相關操作，若沒有稽核日誌，事後無法追蹤異常

**對策**

- [ ] FastAPI 記錄所有 token 銷毀事件：`user_id`、`token_amount`、`voucher_code`、`timestamp`、`request_ip`
- [ ] 記錄失敗的驗證請求（可能是攻擊探測）
- [ ] 日誌不記錄敏感資料（完整的 token 值、折扣碼明文建議只記錄 hash）
- [ ] 設定異常告警：短時間內同一使用者大量 token 銷毀請求

---

## A10 — Server-Side Request Forgery（SSRF）

**風險點**

- FastAPI 呼叫 Saleor GraphQL 的 URL 若可被使用者影響，攻擊者可讓 FastAPI 去打內網其他服務

**對策**

- [ ] FastAPI 呼叫的 Saleor URL 固定寫在環境變數（`SALEOR_API_URL`），不接受來自 request 的 URL 參數
- [ ] 若有任何「呼叫外部 URL」的功能，需驗證 URL 的 scheme 與 hostname

---

## 優先順序建議

| 優先 | 項目 | 理由 |
|---|---|---|
| P0（上線前必做） | A01、A07、A08（webhook 驗簽） | 金流邊界，缺少會有實際損失 |
| P1（早期衝刺） | A02（折扣碼產生）、A05（生產設定）、A09（稽核日誌） | 資料正確性與事後追蹤 |
| P2（穩定後維護） | A06（套件掃描 CI）、A03、A04、A10 | 降低長期風險 |
