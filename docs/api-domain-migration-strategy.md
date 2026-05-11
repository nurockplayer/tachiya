# API Domain 套件化遷移策略

## 簡介

目前 `api/` 仍採單層模組（`models/`、`services/`、`routers/`、`tests/`）維運。
當 domain 邏輯越來越重（如 points、streamer、referral）後，最容易出現跨層 import 雜亂、檔案命名對不上、測試責任不清。

這份文件定義 `api/domains/<domain>/` 的討論與採行原則。
**目前只定義策略，不要求本次實作建立新目錄。**

## 一、是否採用 `api/domains/<domain>/`

**結論：採用「有條件導入」的策略，不在此提議立即重構全部。**

- 同意採用的條件：單一 domain 已經有穩定 API contract、service 規則、tests，且可分離成明確責任邊界。
- 不同意一次性推倒式導入：會造成長時間雙軌路徑並增加回歸風險，不利於在 PR scope 內維持可回滾性。
- 在穩定前，沿用現有檔名/匯入，不新增 `api/domains/` 實作，只做文件承諾與 PR gating。

### 建議目錄語意（落地前設計稿）

未來落地時，`api/domains/<domain>/` 建議先收斂成這幾類：

- `domain_contracts/`（可選）：可讀性高的型別映射、跨層常用常數、資料轉換工具。
- `models.py`：該 domain 專有資料模型／查詢資料形狀描述（未來若超過 1 個檔再切 `models/`）。
- `services.py`：所有 domain 的業務規則與跨 model/外部服務協作。
- `routers.py`：路由行為與錯誤回應封裝；僅含 request/response 與薄 adapter。
- `schema.py`（可選）：Pydantic 輸入輸出 schema，避免與 `routers` 混合臨時結構。
- `tests/`：該 domain 的 router/service 專屬 test package，逐步聚合。

**`api/domains/<domain>/` 內不放共用 infra code**（例如 DB session、環境設定、共用 exception、shared auth）。
共用元件仍保留於頂層 `api/*`，以避免 domain 間繞行邊界。

## 二、命名與 import 邊界

### Router / Service / Model / Test 命名規範

- Router 文件以 endpoint 命名，不以 handler 命名：
  - `points_router.py`、`referral_router.py`、`streamer_router.py`（現有保留）或 `routers.py`（domain 目錄中）。
- Service 檔名固定 `service.py` 或 `services/<domain>_service.py`，命名一律 domain 名詞，不帶 framework 後綴。
- Model 命名以「資料載體」與「業務名詞」為主：
  - `ReferralRelationship`、`CouponRedemptionAudit`、`PointsLedger` 等保留一致。
- Test 按責任分層：
  - `test_<domain>_router.py`：request、schema、路由錯誤行為。
  - `test_<domain>_service.py` / `test_<domain>_service_*.py`：domain 規則與計算。
  - `test_<domain>_model.py`（如有資料模型獨立行為）視情況加入。

### Import 邊界

- `routers` 只可 import 該 domain 的 service 及共用 schema/依賴，不可直接 import 其他 domain 的 service/model。
- `services` 可 import 該 domain models + 共用 infra，但不應跨 domain 直接 import 其他 service（除必要的 domain service contract）。
- `tests` 只可 import 被測試層與少量 `api/main` fixture；避免測試互相引用其他 domain 專屬常量。
- 新 domain 在 router 和 service 之間的共用資料轉換，優先以「純函式」放在 domain 內，避免由 `models` 扣回其他層。

違反 import 邊界的 PR 視為架構污染，需先停 PR 並拆分為更小可回滾提交。

## 三、新功能 vs 既有功能的遷移規則

### 1) 新功能（建議優先走 domain package）

如果是新 endpoint / 新 service 行為，直接以 domain package 路徑實作：
- 先建立該 domain 的 domain contract（文件 + 路由參數 + service contract）。
- 寫 domain-level tests。
- 在 `main.py` 路由註冊維持原有方式即可，不要求先改路徑層級。

### 2) 既有功能（分階段遷移）

既有功能改動遵循以下條件才遷移：

- 這個 domain 本身有「可關閉的邊界改動」：例如改一組 service 規則、測試更新、router 參數收斂。
- 或已有相關 issue 需要「同時 touch router + service + 測試」三層；否則只在原層直接修正。
- 單點 hotfix（例如 message/typing/錯字）不做目錄遷移。

### 3) 過渡規則

1. 不改 API contract：先補 `docs`、測試、註解；維持原路徑，先完成需求。
2. 改 API contract / service 行為：可先在既有目錄實作，並在 PR body 註記「仍未 domain 化」；PR 合併後再進行 domain migration PR。
3. 同步重構時：若需重構，必須在 PR 中同時提供 `before/after` 行為對等，並補回歸測試。

## 四、遷移次序（pilot domain 優先序）

建議 pilot 順序（依可預期影響與規則複雜度）：

1. **points**
   - 理由：核心帳務與 ledger 規則集中，重構收益高，且規則變更影響明確。
2. **referrals**
   - 理由：與 points 緊耦合、邏輯可獨立驗證，先完成可降低後續 points/referral 混流風險。
3. **streamers**
   - 理由：endpoint 多，與 product assignment、revenue share 有較多交錯，應最後整包搬遷避免中間態影響大。
4. **coupons**
   - 理由：範圍相對集中，適合作為「驗證 migration 節奏」的最後小步遷移驗證，而非第一個主案。

> 任何 pilot 進度不足或回歸風險上升，下一個 domain 可暫停，回到既有平面結構穩定補丁。

## 五、何時做「實際 Refactor PR」：Go / No-go

### 值得做

- 同一 domain 在一個週期內有 2 次以上結構面更動（schema、service、router、測試）。
- 已有明確 API contract（例如內部契約文件已更新）且可以寫出 `domain` 內的回歸測試。
- 需要拆掉 legacy 命名、跨檔 import 雜亂，或明顯阻塞新功能接進。
- 有能力在一個 PR 中完成「功能等價」與測試穩定，且不要求一次遷移所有 domain。

### 不該做

- 只做單一欄位/訊息修正、或只補 docs 的小修補。
- PR 目標本身是臨時 hotfix，且回滾成本要可控。
- 遷移會拖垮現有 PR 範圍（超過當前需求 2 倍工作量）或造成三個以上 domain 同時混線。
- 測試無法一次補齊的高風險狀態，尤其涉及 webhook + revenue share 同步流程時，先補測試再談 refactor。

## 六、度量與門檻（每個 migration PR 的停機標準）

- 每個 domain PR 需有：
  - 需求對應的 `tests`（router + service）至少一層完整覆蓋。
  - `rg`/code review 追溯下，該 domain 的 import 只從其 own domain 進出，外部僅保留 infra boundary。
  - 路由/回應/錯誤碼與既有文件對齊（尤其 `/cross-repo-contracts` / `internal-api-contracts`）。
  - PR body 明確標示「僅 docs + migration scaffold / 完整實作」。

未達門檻者，不接受 domain package 引入，只能以既有平面結構完成需求。

## 七、與現有文件關聯

- API contract 落地與 domain 邊界變更時，需先同步更新：
  - [internal-api-contracts.md](internal-api-contracts.md)
  - [cross-repo-contracts.md](cross-repo-contracts.md)
  - [testing-and-ci-gates.md](testing-and-ci-gates.md)

## 八、open questions

- 是否要為每個 domain 建 `schemas/` 子目錄，還是統一保留 `schema.py`？
- `api/domains/<domain>/` 要不要保留 `__init__.py` 做 registry（建議有，未來才能統一 export）。
- 是否要保留 legacy flat 檔名作為 thin wrapper，避免一次到位 migration 的 PR 覆蓋太廣？

## 九、本策略的落地結論

Issue #339 在目前文件優化階段採納：

- 維持 `api/` 現有目錄結構，先補文件與遷移準則；
- 新 domain 實作優先走「domain package 設計稿 + 完整 PR boundary」；
- 將 `points -> referrals -> streamers -> coupons` 作為 pilot 順序（可依實際風險調整）；
- 未滿門檻不做實際 refactor PR，改以既有結構穩定交付功能。
