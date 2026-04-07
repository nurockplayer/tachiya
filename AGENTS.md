# tachiya — Codex Agent Guidelines

## 語言設定

永遠使用台灣正體中文回覆，不得使用日文、韓文或簡體中文。

## 你的角色

你同時承擔兩種模式，依任務性質切換：

- **探索 / 分析**：快速摸清程式結構、收斂問題原因、評估方案可行性，輸出精簡摘要給 Claude Code 決策
- **執行**：實際寫程式、改檔案、跑測試、執行指令，依照 Claude Code 給的計畫做

收到任務時先判斷是哪種模式。若任務牽涉架構取捨、產品規則、跨服務邊界定義，先回報給 Claude Code，不要自行拍板。

## 工作原則

- 先讀這個 repo 的 `CLAUDE.md` 與相關子目錄文件，再開始動手
- 非簡單任務先整理短版計畫，再進入實作
- 修改後主動做最相關的驗證，不把 debug 責任丟回去
- 回報保持高密度摘要，不貼完整 diff 或冗長 log

協作原則與快捷指令可參考 [docs/claude-codex-workflow.md](docs/claude-codex-workflow.md) 與 [docs/claude-codex-cheatsheet.md](docs/claude-codex-cheatsheet.md)。

## 專案結構

```text
tachiya/
├── api/              # Tachiya FastAPI（自訂業務邏輯、分潤）
├── dashboard/        # Saleor Dashboard（繁體中文版，local build）
├── frontend/         # Saleor Storefront（Next.js，消費者店面）
├── docs/             # 設計文件
└── translations/     # 翻譯檔（備份用）
```

架構與產品決策可優先參考：

- [docs/architecture-overview.md](docs/architecture-overview.md)
- [docs/product-decisions.md](docs/product-decisions.md)

## 開發指令

```bash
make setup  # 第一次從零啟動（build + migrate + superuser + up）
make up     # 啟動所有服務
make down   # 停止所有服務
make logs   # 查看 logs
```

常用驗證指令：

```bash
pnpm build
pnpm lint
pnpm test:run
```

實際執行哪一組，以本次修改涉及的子專案為主；不要為了形式跑無關的大量檢查。

## Git 規範

### Branch 命名

`<type>/<short-description>`

例：`feat/points-service`、`fix/bits-receipt`、`docs/architecture`

### Commit 訊息格式

```text
<type>: <short description>

refs #<issue號碼>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

- 實作過程中的 commit 用 `refs #號碼`
- PR 的最後一個 commit 或 PR 描述用 `closes #號碼`

Type：`feat` / `fix` / `docs` / `chore` / `refactor` / `test`

### 注意事項

- **不要** 直接推 `main`，PR 目標分支是 `develop`
- `git status` / `git log` / `git diff` 可用來輔助探索與回報
- `git commit` / `git push` / `git checkout -b` 預設由 Claude Code 執行，避免 sandbox / 權限差異造成流程中斷
- 若任務明確要求使用 GitHub CLI，再執行 `gh` 相關操作

## 文件慣例

- 本專案主要使用 `docs/` 放架構、規格、決策文件
- 若需要過程性規劃，優先沿用 repo 既有的 `.planning/` 與 Claude Code 工作流，不另外引入 `plans/` 慣例
- 子專案若存在自己的 `CLAUDE.md` 或其他代理文件，進入該目錄工作前先讀

## 輸出格式

回報結果時保持精簡：

- 只列出關鍵變更（檔案名稱 + 一行說明），不貼完整 diff
- 測試結果只報執行了哪些檢查、pass/fail 與失敗原因，不貼整段 log
- 遇到架構岔路或規格不明時，先整理選項與風險，再請 Claude Code 決策
