# Codex Autonomous Workflow

本文件定義 tachiya 的 autonomous product work 規範。目標是讓 Codex 作為總控 agent，在 issue-first / PR-first 流程下，自主拆解任務、指派 worker、驗證成果，並把產品級工作穩定推進到 `develop`。

## 核心原則

- autonomous work 必須先過 Start-of-work Delegation Gate，然後才可以讀專案資料、開始計劃、建立 issue、或撰寫 PR body。
- 總控 agent 負責架構、計劃、scope、最終 review、guarded merge、closeout。
- worker/subagent 負責可切分的探索、實作、文件、測試、GitHub readback、CI log 分析。
- 能用較快模型完成的工作優先交給 Spark / low-cost worker；高風險決策保留給總控或高推理 worker。
- 每個實作任務都必須先有 GitHub issue，並以 PR 合併到 `develop`。
- 不直接 push 到 `develop`、`main`、`master`。
- merge 前必須 fresh readback PR head SHA、CI/check 狀態、review/thread 狀態與 issue closeout scope。
- merge 前必須等待 CodeRabbit 與 `chatgpt-codex-connector` review/readback；`chatgpt-codex-connector` 無 finding 時可用第一則 PR comment 的 reaction 作為已看過證據，若有 actionable finding，必須修正或留下不採用佐證 comment 並 resolve。
- 不得只用 CodeRabbit success status 判定 review 完成，因為 skipped review 也可能回報 success。
- 只有單檔、單用途、沒有共享狀態、沒有跨檔驗證擴散風險的 trivial/self-only 任務，才可以不派 worker；這種例外必須在 issue plan 與 PR log 明確寫出 reason。
- `scope-exception` 只 bypass 一般 scope / size / product-surface gate，不會 bypass autonomous delegation gate。

## Start-of-work Delegation Gate

- 總控 agent 必須先建立 Issue Delegation Plan，再讀專案資料、拆 task、寫 issue body、或建立 PR。
- 總控 agent 必須先指派至少一個 worker profile，才可以開始正式工作；只有 trivial/self-only exception 才能不派 worker。
- 總控 agent 不得先讀碼、先寫方案、先開 issue，然後才回頭補委派。
- 總控 agent 不得把「只是先看一下」、「只是驗證標題」、「只是補一句說明」當成委派豁免。
- trivial/self-only exception 只有在工作範圍單一、沒有跨檔脈絡、沒有 CI / schema / API / PR 連動風險時才成立。
- 任何例外都必須同時寫進 Issue Delegation Plan 與 PR Delegation Execution Log。

## Issue Delegation Plan

Issue body 必須先寫出 delegation plan，然後才可以進入實作或 PR。

- 必須列出 worker profile 名稱。
- 必須列出每個 worker 只負責的 task。
- 必須列出 model strength，並且明確寫出預期推理強度或 preferred model。
- 必須列出 evidence / verification，包含要讀回的證據、驗證命令、或回收點。
- 只有 trivial/self-only exception 才能不填 worker profile；這時仍然必須寫清楚 exception reason。
- 不得把 issue 當成純描述票；只要是 autonomous work，就必須可從 issue body 讀出分工與驗證。

建議格式如下，欄位名稱不得省略：

- `Worker profile`
- `Task`
- `Model strength`
- `Evidence / verification`
- `Trivial/self-only exception reason`（只有例外時才可填）

## PR Delegation Execution Log

PR body 必須保留 execution log，讓總控與 reviewer 能回頭核對實際分工。

- 必須列出實際執行的 worker profile 名稱。
- 必須列出每個 worker 的實際工作結果，不得只寫「已完成」。
- 必須列出驗證結果與證據來源，包含測試、readback、或 CI 結果。
- 必須把 issue plan 中的 trivial/self-only exception reason 原樣帶到 PR log；如果沒有例外，就不得亂寫例外。
- 不得把 execution log 省略成一般摘要；只要是 autonomous PR，就必須看得到 delegation 與驗證的對應關係。

## 總控責任

總控 agent 保留下列責任，不交給 worker 最終決策：

- 產品級 roadmap、phase、優先順序判斷。
- schema、migration、points ledger、金流、權限模型的最終架構決策。
- issue 拆分、PR scope、non-goals、dependency order。
- worker 任務設計與結果審查。
- failed checks、merge conflict、stale review、schema/data risk 的處置判斷。
- 最終 validation strategy。
- `gh pr merge`、merge method、`--match-head-commit` guarded merge。
- merge 後 issue evidence、closeout 與最終回報。

## Worker Profiles

| Profile | Preferred model | Reasoning | 用途 |
|---|---|---|---|
| `controller` | GPT-5.5 | high / xhigh | 總控、架構、計劃、最終 review、merge decision |
| `ops_spark` | GPT-5.3-Codex-Spark | low / medium | GitHub issue/PR metadata、CI readback、label/milestone、routine terminal |
| `repo_scout` | GPT-5.3-Codex-Spark | medium | 快速掃 codebase、找既有 pattern、列測試缺口、產出摘要 |
| `docs_worker` | GPT-5.3-Codex-Spark | medium | docs、issue body、PR body、驗證摘要、規格草稿 |
| `test_worker` | GPT-5.4-mini / GPT-5.4 | medium / high | 單元測試、fixture 整理、workflow regression、測試補強 |
| `backend_worker` | GPT-5.4 | high | FastAPI routers/services、錯誤處理、API tests、CI gates |
| `frontend_worker` | GPT-5.4 | medium / high | storefront/dashboard UI、component、互動狀態、前端測試 |
| `schema_worker` | GPT-5.5 | high / xhigh | DB schema、migration、idempotency、ledger、資料一致性 |
| `integration_worker` | GPT-5.4 | high | 跨 repo contract、Docker、build、API/frontend integration |
| `review_worker` | GPT-5.4 / GPT-5.5 | high | PR diff review、regression risk、缺測檢查 |

模型名稱是 preferred profile，不是硬依賴。若當前環境不可用，總控需選擇同級或較保守的替代模型。

## Routing Rules

| 場景 | 預設指派 |
|---|---|
| GitHub issue/label/PR body/check readback | `ops_spark` |
| GitHub issue creation with known scope/body | `ops_spark` drafts and creates, controller reviews scope before implementation |
| CI log 初步分析、routine terminal 檢查 | `ops_spark` |
| 大範圍找檔案、讀 code pattern | `repo_scout` |
| 文件、計劃、issue/PR 草稿 | `docs_worker` |
| 單檔或小範圍 test 補強 | `test_worker` |
| 一般 API router/service 實作 | `backend_worker` |
| schema、migration、資料一致性、ledger | `schema_worker` |
| 一般 storefront/dashboard UI | `frontend_worker` |
| 跨 tachiya / storefront / Docker / contract | `integration_worker` |
| merge 前風險掃描 | `review_worker`，總控 final decision |

## GitHub 操作分工

`ops_spark` 可以處理：

- 依總控核准的 scope 建 issue、查 issue、補 issue comment。
- 驗證 issue label / state / URL readback。
- 建 PR、更新 PR body。
- 查 labels、milestones、review state、CI checks。
- 抓 failed check logs 並整理摘要。
- 讀回 latest head SHA、merge state、status rollup。
- 準備 closeout evidence。

總控保留：

- 是否 merge。
- merge method。
- `gh pr merge --match-head-commit`。
- conflict / failed check / stale review 的決策。
- issue close 的最終 scope 判斷。

## Automated Review Gate

任何 autonomous PR merge 前，總控必須完成 fresh review readback：

1. 確認最新 PR head SHA、base branch、mergeability 與 CI/check 狀態。
2. 確認 CodeRabbit 已產生實際 review；若 CodeRabbit 明確回 rate limit，同一張 PR 不再重複要求 review，改由總控做 self-review 並留下替代 review 證據。
3. 確認 `chatgpt-codex-connector` 已留下 review/comment，或在第一則 PR comment 左下角留下 reaction。只有兩者都沒有時，才手動 comment `@codex review`。
4. 針對每個 actionable automated review finding，merge 前只能選一條路：
   - 修正、push、重跑相關驗證；
   - 留下技術佐證 comment 說明為何不採用。
5. GitHub 允許時，將已處理的 review thread/comment resolve。
6. 若 push 過新 commit，merge 前重新讀回 head SHA。

CodeRabbit 由 `.coderabbit.yaml` 設定 `reviews.auto_review.base_branches: [".*"]`，讓 PR target branch 不限 default branch 都能觸發 auto review。

## PR Scope Police Contract

開 PR 前必須先符合 `.github/workflows/pr-scope-police.yml` 的固定格式，避免靠 CI 打回才修：

- PR title 必須以 `[backend]`、`[frontend]`、`[discussion]` 其中之一開頭。
- PR body 必須引用至少一個 issue 或 PR 編號，例如 `#329`。
- PR body 必須包含一行 `Source of truth: ...`，不能只用 heading。
- PR body 必須包含一行 `Depends on PR: none` 或 `Depends on PR: #123`，不能只用 heading。
- PR body 必須包含 `本 PR 明確不做` section。
- Changed files 不得超過 35；diff lines 不得超過 1000，超過 600 會警告。
- 同一 PR 不得同時改 API 與 dashboard 產品面；`[backend]` 不得改 dashboard，`[frontend]` 不得改 api。
- 只有明確 scope review 後才可使用 `scope-exception` label bypass。

## Standard Autonomous Loop

1. 評估現況與產品級缺口。
2. 總控決定 issue scope；`ops_spark` 可負責建立或更新 GitHub issue，並讀回 URL、state、labels。
3. 從 `develop` 切 scoped branch。
4. 依任務類型指派 worker。
5. worker 回報變更與驗證；總控審查 diff。
6. 總控或 worker 補必要修正。
7. 跑 relevant validation；高風險改動需 full validation。
8. 開 PR 到 `develop`，PR body 包含 Source of truth、Depends on PR、non-goals、validation。
9. 等 CI/checks/review 狀態 fresh readback。
10. 總控用 guarded merge 合併。
11. 補 issue evidence comment，確認 issue state / labels / closeout。
12. 更新本機 `develop`，回報 merge commit、驗證與剩餘風險。

## Validation Policy

- API 變更至少跑 `uv run --group dev pytest`、`ruff check`、必要 compile/build。
- CI/workflow 變更需跑 workflow regression test 與 YAML parse。
- Docker/build 變更需跑對應 image build 或明確回報阻礙。
- Frontend 變更需在 storefront repo 跑 lint/test/build/e2e，依變更風險調整。
- Docs-only 變更至少跑 markdown/file diff sanity check；若 workflow/command 被文件化，需確認命令仍合理。

## Storage Boundaries

| 位置 | 用途 |
|---|---|
| `docs/codex-autonomous-workflow.md` | 團隊可見的正式 autonomous policy |
| `AGENTS.md` | 短版入口規則與本文件連結 |
| Codex memory | 使用者偏好與歷史決策輔助，不作為唯一規範來源 |
| `.codex/config.toml` / router script | 未來 CLI 自動路由實作；目前不在本文件 PR 範圍 |

## Out of Scope

本文件只定義 policy。以下需要另開 issue / PR：

- CLI `tachiya-auto` router。
- `.codex/config.toml` profile 實作。
- 自動化 task queue / long-running daemon。
- 跨 repo release orchestration。
