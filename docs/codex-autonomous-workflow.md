# Codex Autonomous Workflow

本文件定義 tachiya 的 autonomous product work 規範。目標是讓 Codex 作為總控 agent，在 issue-first / PR-first 流程下，自主拆解任務、指派 worker、驗證成果，並把產品級工作穩定推進到 `develop`。

## 核心原則

- 總控 agent 負責架構、計劃、scope、最終 review、guarded merge、closeout。
- worker/subagent 負責可切分的探索、實作、文件、測試、GitHub readback、CI log 分析。
- 能用較快模型完成的工作優先交給 Spark / low-cost worker；高風險決策保留給總控或高推理 worker。
- 每個實作任務都必須先有 GitHub issue，並以 PR 合併到 `develop`。
- 不直接 push 到 `develop`、`main`、`master`。
- merge 前必須 fresh readback PR head SHA、CI/check 狀態、review/thread 狀態與 issue closeout scope。
- merge 前必須等待 CodeRabbit 與 `chatgpt-codex-connector` review/readback；若有 actionable finding，必須修正或留下不採用佐證 comment 並 resolve。
- 不得只用 CodeRabbit success status 判定 review 完成，因為 skipped review 也可能回報 success。

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

- 建 issue、查 issue、補 issue comment。
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
2. 確認 CodeRabbit 已產生實際 review，或留下為何不可用的 comment。
3. 確認 `chatgpt-codex-connector` 已產生 review/comment，或留下為何不可用的 comment。
4. 針對每個 actionable automated review finding，merge 前只能選一條路：
   - 修正、push、重跑相關驗證；
   - 留下技術佐證 comment 說明為何不採用。
5. GitHub 允許時，將已處理的 review thread/comment resolve。
6. 若 push 過新 commit，merge 前重新讀回 head SHA。

CodeRabbit 由 `.coderabbit.yaml` 設定 `reviews.auto_review.base_branches: [".*"]`，讓 PR target branch 不限 default branch 都能觸發 auto review。

## Standard Autonomous Loop

1. 評估現況與產品級缺口。
2. 建立或更新 GitHub issue，明確寫背景、任務、規格、參考、完成條件。
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
