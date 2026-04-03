# tachiya — Claude Code Guidelines

## 語言設定

永遠使用台灣正體中文回覆，不得使用日文、韓文或簡體中文。

---

## 工作原則

### 先規劃再動手

收到非簡單的任務時（跨檔案修改、新功能、架構調整），先用 Plan Mode 提出方案，等使用者確認後再開始寫 code。不要一收到需求就直接動手。

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

本專案使用 Claude Code + Codex CLI 協作開發：

| 角色 | 工具 | 職責 |
|---|---|---|
| **指揮** | Claude Code | 分析需求、規劃架構、拆解任務、審查結果、決策取捨 |
| **執行** | Codex CLI | 實際寫程式碼、跑測試、改檔案、執行指令 |

**工作流程：**
1. Claude Code 理解需求，擬定實作計畫
2. Claude Code 下指令給 Codex CLI 執行
3. Codex 完成後回報結果
4. Claude Code 審查、驗收、或進一步調整指令

**委派原則（節省 Claude token）：**

- 任何涉及寫程式、改檔案、跑測試的任務，一律透過 `codex:rescue` 派給 Codex 執行
- Claude Code 只負責：理解需求、規劃架構、給 Codex 下指令、審查結果
- 僅在極簡單的單行修改時，Claude Code 才直接動手

**指令操作的分界：**

| 操作 | 誰執行 | 原因 |
|---|---|---|
| `git status` / `git log` / `git diff` | Claude Code | 需要即時看輸出來做決策 |
| `git commit` / `git push` / `git checkout -b` | Codex | 純執行，不需要即時輸出 |
| 檔案搜尋（探索用） | Claude Code（用 Glob / Grep 工具） | 規劃階段，需要結果判斷下一步 |
| 複雜 bash 腳本、批次操作 | Codex | 純執行，只需確認最終結果 |

核心判斷：Claude 需要即時看輸出來決策 → 自己做；純執行 → 交給 Codex

## Claude Code 設定

`.claude/settings.json` 是共享設定，已 commit 進 repo，**請勿直接修改**。

個人設定請放在 `.claude/settings.local.json`（已 gitignore，不會影響其他人）。

## 文件放置規範

| 位置 | 對象 | 內容 |
|---|---|---|
| `README.md` | 所有人 | 開發環境建置（快速上手） |
| `docs/` | 工程師 | 架構設計、API 規格、技術決策 |
| GitHub Wiki | 全體人員 | 產品說明、功能介紹、非技術文件 |

## 架構參考

見 [docs/product-decisions.md](docs/product-decisions.md)
