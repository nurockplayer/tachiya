# tachiya — Codex Guidelines

## 語言設定

永遠使用台灣正體中文回覆，不得使用日文、韓文或簡體中文。

---

## 工作原則

### 先規劃再動手

收到非簡單的任務時（跨檔案修改、新功能、架構調整），先用 Plan Mode 提出方案，等使用者確認後再開始寫 code。不要一收到需求就直接動手。

### Autonomous 開工入口

autonomous work 一開始必須先看 [docs/codex-autonomous-workflow.md](docs/codex-autonomous-workflow.md)，然後先做 delegation，再讀專案資料、寫 plan、開 issue、發 PR。

- 必須先指派 worker，才可以開始正式工作。
- 只有 trivial/self-only 任務才可以不派 worker，但一定要寫明 exception reason。
- 總控負責決策與驗收，worker 只做被分派的切片。

### 驗證迴圈

寫完 code 之後，主動跑相關的檢查來確認沒有問題：

- `pnpm build` 確認編譯通過
- `pnpm lint` 確認沒有 lint 錯誤
- `pnpm test:run` 跑測試（如果有相關的 test）

測試沒過就修，不要丟回來讓使用者自己 debug。

### 回覆風格

- 簡潔直接，不要重複使用者說過的話
- 先講結論或行動，再講原因
- 一句話能說完就不要用三句

---

## GitHub Issue 慣例

### 標題前綴

所有 issue 標題必須有前綴：

| 前綴 | 用途 |
|---|---|
| `[backend]` | 後端開發任務（Go） |
| `[frontend]` | 前端開發任務（React / TypeScript） |
| `[discussion]` | 架構決策、設計討論，尚未有結論 |

範例：
- `[backend] PointsService — 雙帳本記帳`
- `[frontend] Extension — 點數餘額顯示`
- `[discussion] Token 經濟設計與 Soulbound 衝突`

### Label

| Label | 用途 |
|---|---|
| `feature` | 開發任務 |
| `discussion` | 討論票（搭配 `[discussion]` 前綴使用） |

### Issue 內容格式

開發任務（`[backend]` / `[frontend]`）需包含：

- **背景** — 這個功能是為了解決什麼問題
- **任務** — 具體要做什麼（用 checklist）
- **介面／規格** — Go interface、API 規格、或 component props
- **參考** — 現有的範本檔案路徑
- **完成條件** — PR merge 前必須達成的條件（checklist）

討論票（`[discussion]`）不需要固定格式，但要列出待決定的問題點。

---

## 開發流程

1. 從 `develop` 拉新的 feature branch：

   ```bash
   git checkout develop
   git pull
   git checkout -b feat/points-service
   ```

2. 開發完成後推上 remote：

   ```bash
   git push -u origin feat/points-service
   ```

3. 在 GitHub 發 PR，目標分支：`develop`（不直接推 `main`）

## Branch 命名

`<type>/<short-description>`

例：`feat/points-service`、`fix/bits-receipt`、`docs/architecture`

## Commit 訊息格式

每個 commit 必須用 `refs #<issue號碼>` 標記相關 issue，方便日後追溯當初的規格與討論。

```
<type>: <short description>

refs #27

Co-Authored-By: Codex Sonnet 4.6 <noreply@anthropic.com>
```

- 實作過程中的 commit 用 `refs #號碼`
- PR 的最後一個 commit 或 PR 描述用 `closes #號碼`（merge 後自動關閉 issue）

Type：`feat` / `fix` / `docs` / `chore` / `refactor` / `test`

---

## 專案結構

```
tachiya/
├── api/              # Tachiya FastAPI（自訂業務邏輯、分潤）
├── dashboard/        # Saleor Dashboard（本機 checkout，不由此 repo 版控）
├── frontend/         # Saleor Storefront（本機 checkout；正式 repo 是 nurockplayer/storefront）
├── docs/             # 設計文件
└── translations/     # 翻譯檔（備份用）
```

`frontend/` 與 `dashboard/` 不進 Tachiya root repo git。Storefront 實作、測試、CI 與 PR 應在
`<workspace>/storefront` / `nurockplayer/storefront` 處理；Tachiya root repo 只負責 API、docker-compose、
文件與 cross-repo contract gate。

## 開發指令

```bash
make setup  # 第一次從零啟動（build + migrate + superuser + up）
make up     # 啟動所有服務
make down   # 停止所有服務
make logs   # 查看 logs
```

## AI 分工

本專案使用 Codex + Codex CLI 協作開發：

| 角色 | 工具 | 職責 |
|---|---|---|
| **指揮** | Codex | 分析需求、規劃架構、拆解任務、審查結果、決策取捨 |
| **執行** | Codex CLI | 實際寫程式碼、跑測試、改檔案、執行指令 |

**工作流程：**
1. Codex 理解需求，擬定實作計畫
2. Codex 下指令給 Codex CLI 執行
3. Codex 完成後回報結果
4. Codex 審查、驗收、或進一步調整指令

**委派原則（節省 Codex token）：**

- 任何涉及寫程式、改檔案、跑測試的任務，一律透過 `codex:rescue` 派給 Codex 執行
- Codex 只負責：理解需求、規劃架構、給 Codex 下指令、審查結果
- 僅在極簡單的單行修改時，Codex 才直接動手
- 任何 delegation 必須寫清 `profile`、`model`、`reasoning`；ops_spark 類工作必須明確指定 `gpt-5.3-codex-spark`，不得直接繼承 controller 的 `gpt-5.5`，除非 `controller_fallback=allowed` 並有原因。

**建議優先使用的快捷指令：**

- `/fix-with-codex <問題>`：debug 並盡量直接修復
- `/implement-with-codex <需求>`：實作功能並補必要驗證
- `/review-with-codex <PR/變更範圍>`：以 bug / regression / 測試缺口為主做 review
- `/explore-with-codex <主題>`：快速摸清程式結構與現況
- `/plan-with-codex <任務>`：先探索，再輸出短版可執行計畫
- `/test-with-codex <測試範圍>`：執行最相關測試並收斂失敗原因

這些指令都會刻意限制輸出格式，避免貼完整 diff、冗長 log 或大段原始碼，讓 Codex 只接收高密度摘要。

完整教學請見 [docs/claude-codex-workflow.md](docs/claude-codex-workflow.md)。
快速版可見 [docs/claude-codex-cheatsheet.md](docs/claude-codex-cheatsheet.md)。

**指令操作的分界：**

| 操作 | 誰執行 | 原因 |
|---|---|---|
| `git status` / `git log` / `git diff` | Codex | 需要即時看輸出來做決策 |
| 實際 git branch / commit / push write（如 `git checkout -b`、`git commit`、`git push`） | Codex controller | 涉及 `.git`、credential、目前 branch 狀態與 guarded write 風險，現階段由 controller 擁有 |
| pre-commit checklist / post-push readback | `ops_spark` | 例行驗證與證據讀回預設交給 `ops_spark`，包含 commit SHA、push branch、PR head SHA、CI/check 狀態 |
| 檔案搜尋——定向（知道找什麼） | Codex（用 Glob / Grep 工具） | 規劃階段，需要結果判斷下一步 |
| 檔案搜尋——探索性（不確定在哪） | Codex（透過 `/explore-with-codex`） | 大範圍搜尋交給 Codex，只拿摘要回來 |
| 複雜 bash 腳本、批次操作 | Codex | 純執行，只需確認最終結果 |

核心判斷：Codex 需要即時看輸出來決策 → 自己做；純執行 → 交給 Codex

### OpenSpec SDD Workflow

新 feature 或 behavior change 預設使用 OpenSpec 作為 proposal / specs / design / tasks 的 implementation source of truth。完整規範見 [docs/ai/openspec-workflow.md](docs/ai/openspec-workflow.md)。

- 先確認 GitHub source issue，再建立 `openspec/changes/<change-id>/`；PR body 的 `Source of truth` 必須同時指向 issue 與 OpenSpec change path。
- OpenSpec change 至少包含 `.openspec.yaml`、`proposal.md`、`design.md`、`tasks.md`、以及 `specs/<domain>/spec.md` delta specs。
- 實作只能對齊 `tasks.md` 與 delta specs；OpenSpec artifacts 不授權擴張 issue scope。
- `openspec/specs/**` 只放已採納的 living behavior；proposal 尚未完成前不得直接寫入 main specs。
- OpenSpec 不取代 autonomous Spec gate；autonomous workflow 仍遵守 `docs/codex-autonomous-workflow.md`。
- 不得自行安裝 OpenSpec CLI 或提交未 review generated output；若本機沒有 OPSX 或 `openspec` 指令，可用人工 artifacts fallback，但仍要保留完整 change 結構。

### Autonomous Worker Profiles

當使用者授權 autonomous product work 時，Codex 作為總控 agent，負責架構、計劃、scope、最終 review、guarded merge 與 closeout。

autonomous work 一開始必須先看 [docs/codex-autonomous-workflow.md](docs/codex-autonomous-workflow.md)，先指派 worker，再讀專案資料、寫 plan、開 issue 或發 PR；只有 `trivial/self-only exception` 可以不分派，但必須明寫原因。

- PR body 要從一開始就把 delegation / evidence 主要欄位填完整，不要等 closeout 才一次補。
- low-cost/routine 工作先走 `ops_spark`、`repo_scout`、`docs_worker`；若升級到 controller fallback，必須在 issue/PR 寫明原因。
- threshold calibration v2 的 authoritative 規則、`controller_fallback reason` 格式、`Calibration data` 欄位、以及「至少每 3 張 autonomous PR 回看一次 threshold」都以 [docs/codex-autonomous-workflow.md](docs/codex-autonomous-workflow.md) 為準；`AGENTS.md` 不重複展開細節。
- 使用 `spec-injector` 時，開工前、commit 前、merge 前都要跑 `spec validate --repo .` 與 current `spec workflow-check` gate；bootstrap、fallback runner 與 status/ref evidence 規則以 [docs/codex-autonomous-workflow.md](docs/codex-autonomous-workflow.md) 為準；不得 commit `.spec-injector/` 或 generated output。
- 沒有使用 `spec-injector` 時，也要用 PR template 的 `Spec gate evidence` 走 manual checklist。
- final closeout 只在 merge-ready 且證據穩定時更新一次；每個 actionable finding 都必須 comment/resolve，或留下不採用證據。

可切分的探索、文件、測試、一般實作、GitHub readback、CI log 分析，可以依任務風險委派給 worker/subagent。routine GitHub / terminal / repo 探索優先使用 Spark 或較低推理成本的 worker；schema、migration、ledger、金流、權限模型與 merge decision 必須由總控或高推理 worker 審查。

資訊來回、GitHub PR/issue readback、CI/check 狀態讀回、PR body/comment 整理、review closeout evidence 蒐集與 resolve 狀態確認，預設都是 `ops_spark` 工作。總控不得把這類資料搬運當成自己的預設工作；總控只審核 worker 證據是否足以支持後續修正、等待、merge 或 closeout 決策。

Autonomous Worker Profiles 的 follow-up 改善以「約 40% infra 本質複雜、約 60% 工作流自己製造摩擦」為基準：infra 複雜度用固定 readback 與 gate 管住；流程摩擦要靠 `ops_spark` routing、review closeout evidence、subagent lifecycle cleanup、issue-first planning 與 follow-up split 降低。

完整 worker profile、路由規則與 GitHub 操作分工見 [docs/codex-autonomous-workflow.md](docs/codex-autonomous-workflow.md)。
Review closeout 的一頁式執行清單 `Autonomous Review Closeout Evidence Runbook` 以 [docs/codex-autonomous-workflow.md#autonomous-review-closeout-evidence-runbook](docs/codex-autonomous-workflow.md#autonomous-review-closeout-evidence-runbook) 為權威來源。

### Automated Review Gate

Autonomous PR merge 前必須等待 CodeRabbit 與 `chatgpt-codex-connector` review/readback。`chatgpt-codex-connector` 若沒有問題，通常會在第一則 PR comment 左下角留下 reaction；只有沒有 reaction、也沒有 review/comment 時才手動 comment `@codex review`。CodeRabbit 若明確回 rate limit，同一張 PR 不再重複要求 review，改由總控做 self-review 並留下替代 review 證據。若 reviewer 提出 actionable finding，merge 前每一條 finding 都必須有固定處置紀錄：修正並補上 comment/resolve，或留下不採用的技術佐證並 comment/resolve；至少要有一筆可見 comment 或 resolve 紀錄。不得只因 CodeRabbit status context 是 success 就視為 review 完成，因為 skip path 也可能回報 success。

CodeRabbit 由 `.coderabbit.yaml` 設定為對所有 PR target branch 啟用 auto review。

## Codex 設定

`.Codex/settings.json` 是共享設定，已 commit 進 repo，**請勿直接修改**。

個人設定請放在 `.Codex/settings.local.json`（已 gitignore，不會影響其他人）。

Codex 目前不要使用 `anthropic.config.json` 來設定最大循環次數；本專案以啟動參數控制，預設請使用：

```bash
Codex --max-turns 5
```

如果任務非常單純，可視情況降到 `3`；原則上請把單次執行限制在 `3-5` turns 內，避免無限制迴圈消耗 token。

## 文件放置規範

| 位置 | 對象 | 內容 |
|---|---|---|
| `README.md` | 所有人 | 開發環境建置（快速上手） |
| `docs/` | 工程師 | 架構設計、API 規格、技術決策 |
| `docs/ai/` | AI 協作者 / 工程師 | AI 協作指南與較長篇的 agent-facing 文件 |
| GitHub Wiki | 全體人員 | 產品說明、功能介紹、非技術文件 |

## 架構參考

見 [docs/product-decisions.md](docs/product-decisions.md)
