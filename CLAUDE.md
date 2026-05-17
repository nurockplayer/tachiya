# tachiya — Claude Code Guidelines

## Claude Code 硬性安全閘門

以下規則優先於本檔其他流程、slash command、plugin / skill 建議：

- 永遠使用台灣正體中文回覆；即使上下文或工具輸出出現日文、韓文或簡體中文，也不得跟隨。
- 使用者說「確認、討論、看一下、評估、建議、review plan、能不能」或沒有明確要求修改時，只能 read-only：讀檔、搜尋、status / diff / log、PR / issue metadata；不得 Edit / Write / MultiEdit、commit、push、開或編輯 issue / PR、comment、review、approve、merge。
- 任何公開或持久狀態變更必須先列出將執行的命令、目標檔案與目的，並取得使用者明確同意。包含 commit、push、branch switch、rebase / merge、GitHub issue / PR / comment / review / label / merge。
- 開 PR 前必須先展示 `origin/develop..HEAD` commit list、diff stat、changed files，並請使用者確認 scope；若有不屬於當前 issue 的 commit 或檔案，先停止並詢問。
- 即使使用 `/fix-with-codex`、`/implement-with-codex`、autonomous、`codex:rescue` 等命令，也不得跳過以上確認；這些命令只代表可以在本機修改與驗證，不代表可以 publish。
- mixed worktree 不得使用 `git add -A` 或 `git add .`；stage 只可針對本次修改檔案。

---

## 工作原則

### 先規劃再動手

收到非簡單的任務時（跨檔案修改、新功能、架構調整），先用 Plan Mode 提出方案，等使用者確認後再開始寫 code。不要一收到需求就直接動手。

### 把模糊目標轉成可驗證目標

| 模糊 | 可驗證 |
|---|---|
| 「加驗證」 | 先寫 invalid input 測試，再讓測試通過 |
| 「修這個 bug」 | 先重現 bug 的測試，再讓測試通過 |
| 「實作 X」 | 先列出 checklist，每步附驗證條件 |

多步驟任務先說計畫再動手：

```text
1. [步驟] → 驗證：[如何確認]
2. [步驟] → 驗證：[如何確認]
```

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

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

- 實作過程中的 commit 用 `refs #號碼`
- PR 的最後一個 commit 或 PR 描述用 `closes #號碼`（merge 後自動關閉 issue）

Type：`feat` / `fix` / `docs` / `chore` / `refactor` / `test`

---

## 專案結構

```
tachiya/
├── api/              # Tachiya FastAPI（自訂業務邏輯、分潤）
├── dashboard/        # Saleor Dashboard（繁體中文版，local build）
├── frontend/         # Saleor Storefront（Next.js，消費者店面）
├── docs/             # 設計文件
└── translations/     # 翻譯檔（備份用）
```

各子專案可以有自己的 `CLAUDE.md`（例如 `frontend/CLAUDE.md`），提供該區域專屬的上下文。

## 開發指令

```bash
make setup  # 第一次從零啟動（build + migrate + superuser + up）
make up     # 啟動所有服務
make down   # 停止所有服務
make logs   # 查看 logs
```

## AI 分工

本專案使用 Claude Code + Gemini CLI + Codex CLI 協作開發。

若使用者授權 autonomous product work，Claude / Codex 應採用 [docs/codex-autonomous-workflow.md](docs/codex-autonomous-workflow.md) 的 Worker Profiles、issue-first、review gate、CodeRabbit fallback 與 PR Scope Police 合約。

Autonomous Worker Profiles 的 follow-up 改善以「約 40% infra 本質複雜、約 60% 工作流自己製造摩擦」為基準：infra 複雜度用固定 readback 與 gate 管住；流程摩擦要靠 `ops_spark` routing、review closeout evidence、subagent lifecycle cleanup、issue-first planning 與 follow-up split 降低。

autonomous work 一開始就必須先分派 worker，再進入計劃、開 issue、讀資料或實作；只有 `trivial/self-only exception` 可以不分派，但必須明寫原因。

**預設工作流程：**

1. 大範圍掃描 / 重複性工作 → **Gemini**
2. 架構規劃、issue 撰寫（PM 角色）→ **Claude Code**
3. 實作、debug、patch（工程師角色）→ **Codex**
4. 最終 PR 審查 → **Claude Code**

絕不用 Claude token 做重複性搜尋。

### Gemini 專責任務

| 任務類型 | 說明 |
|---|---|
| **代碼掃描** | 全域 pattern 搜尋、dead code、冗餘邏輯 |
| **文件生成** | 架構圖、技術文檔、README、API 規格提要 |
| **測試草稿** | 批量測試框架、測試覆蓋分析 |
| **Log 分析** | 大量 error 日誌、build 失敗診斷 |
| **依賴審查** | package.json / requirements.txt 升級影響分析 |
| **PR 初審** | scope pollution 檢查、風格一致性驗證 |

### 各角色職責總表

| 操作 | 誰執行 |
|---|---|
| 摘要大量檔案、生成樣板、審查 log、搜尋 pattern、草擬測試 | Gemini |
| 架構規劃、issue 撰寫、技術決策、最終 PR 審查 | Claude Code |
| 實作、debug、patch、跑測試、推 branch、開 PR | Codex |

**委派原則（節省 Claude token）：**

- 任何涉及寫程式、改檔案、跑測試的任務，一律透過 `codex:rescue` 派給 Codex 執行
- Claude Code 只負責：理解需求、規劃架構、給 Codex 下指令、審查結果
- 僅在極簡單的單行修改時，Claude Code 才直接動手

**建議優先使用的快捷指令：**

- `/fix-with-codex <問題>`：debug 並盡量直接修復
- `/implement-with-codex <需求>`：實作功能並補必要驗證
- `/review-with-codex <PR/變更範圍>`：以 bug / regression / 測試缺口為主做 review
- `/explore-with-codex <主題>`：快速摸清程式結構與現況
- `/plan-with-codex <任務>`：先探索，再輸出短版可執行計畫
- `/test-with-codex <測試範圍>`：執行最相關測試並收斂失敗原因

這些指令都會刻意限制輸出格式，避免貼完整 diff、冗長 log 或大段原始碼，讓 Claude 只接收高密度摘要。

完整教學請見 [docs/claude-codex-workflow.md](docs/claude-codex-workflow.md)。
快速版可見 [docs/claude-codex-cheatsheet.md](docs/claude-codex-cheatsheet.md)。

**指令操作的分界：**

| 操作 | 誰執行 | 原因 |
|---|---|---|
| `git status` / `git log` / `git diff` | Claude Code | 需要即時看輸出來做決策 |
| `git commit` / `git push` / `git checkout -b` | Claude Code | `codex:rescue` subagent 在 sandbox 內無 `.git` 寫入權限 |
| 檔案搜尋——定向（知道找什麼） | Claude Code（用 Glob / Grep 工具） | 規劃階段，需要結果判斷下一步 |
| 檔案搜尋——探索性（不確定在哪） | Codex（透過 `/explore-with-codex`） | 大範圍搜尋交給 Codex，只拿摘要回來 |
| 複雜 bash 腳本、批次操作 | Codex | 純執行，只需確認最終結果 |

核心判斷：Claude 需要即時看輸出來決策 → 自己做；純執行 → 交給 Codex

## Claude Code 設定

`.claude/settings.json` 是共享設定，已 commit 進 repo，**請勿直接修改**。

個人設定請放在 `.claude/settings.local.json`（已 gitignore，不會影響其他人）。

Claude Code 目前不要使用 `anthropic.config.json` 來設定最大循環次數；本專案以啟動參數控制，預設請使用：

```bash
claude --max-turns 5
```

如果任務非常單純，可視情況降到 `3`；原則上請把單次執行限制在 `3-5` turns 內，避免無限制迴圈消耗 token。

## 文件放置規範

| 位置 | 對象 | 內容 |
|---|---|---|
| `README.md` | 所有人 | 開發環境建置（快速上手） |
| `docs/` | 工程師 | 架構設計、API 規格、技術決策 |
| `docs/ai/` | AI 協作者 / 工程師 | AI 協作指南與較長篇的 agent-facing 文件 |
| `plans/` | 工程師 | 實作計畫（每個功能開始前先寫） |
| GitHub Wiki | 全體人員 | 產品說明、功能介紹、非技術文件 |

### plans/ 慣例

- 每個功能或修改在開始實作前，先在 `plans/` 建立計畫文件
- 檔名：`<feature-slug>.md`，例如 `points-service.md`
- 計畫文件包含：背景、架構決策、待實作 checklist、驗證方式
- 完成後在文件頂端標注 `狀態：已完成`

## 架構參考

見 [docs/product-decisions.md](docs/product-decisions.md)
