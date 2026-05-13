# Codex Autonomous Workflow

本文件定義 tachiya 的 autonomous product work 規範。目標是讓 Codex 作為總控 agent，在 issue-first / PR-first 流程下，自主拆解任務、指派 worker、驗證成果，並把產品級工作穩定推進到 `develop`。

## 核心原則

- autonomous work 必須先過 Start-of-work Delegation Gate，然後才可以讀專案資料、開始計劃、建立 issue、或撰寫 PR body。
- 總控 agent 負責架構、計劃、scope、最終 review、guarded merge、closeout。
- worker/subagent 負責可切分的探索、實作、文件、測試、GitHub readback、CI log 分析。
- 資訊來回、GitHub PR/issue readback、CI/check 狀態讀回、PR body/comment 整理、review closeout evidence 蒐集與 resolve 狀態確認，預設交給 `ops_spark` 或同級低強度 worker。
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

## Autonomous Workflow Dialog

Autonomous Workflow Dialog 是給 Codex / Claude / reviewer 使用的 agent-facing checklist，不是 runtime UI，也不是要在產品裡實作的對話框。它的目標是在三個容易漏證據的時點，強制先問完必要欄位，再繼續開工、closeout 或 merge。

本段只定義最小可用流程：

- `spec workflow-check` 已可作為 current local gate；使用時只保存 `status + ref`，未使用或工具不可用時才走 manual checklist / `not_using_spec` fallback。
- spec evidence 只保存 `status + ref`；不得把完整 private context、generated output、或 `.spec-injector/` 內容提交到 repo。
- threshold calibration 的量測資料放在 #375 ledger comment，不塞進 PR body；PR body 只引用 #375 issue/comment URL 或寫明 pending/not applicable。
- Scope Police 只檢查 evidence ref/status 是否存在，不解析 #375 comment，也不解析完整 spec evidence body。
- AWP review triage / root-cause gate 在 tachiya 只做 thin wiring：PR body 只放短 evidence ref，不在本 repo 內重做 full parser/checker。schema/checker source of truth 在 `Erick52106/spec-injector#232`、`Erick52106/spec-injector#233`、`Erick52106/spec-injector#234`、`Erick52106/spec-injector#235`。

### Start Dialog（開工前）

Start Dialog 必須在正式讀碼、拆 task、開 issue、寫 PR body 或實作前完成。若缺少 source of truth、worker routing plan、或 spec/threshold 證據路徑，必須停止開工。

| 欄位 | 可接受答案 | 何時停止 |
|---|---|---|
| Source issue / source of truth | GitHub issue、PR、或明確文件 ref，例如 `#375`、`#376` | 沒有 source of truth，或 source 不涵蓋本次 scope |
| Autonomous PR | `yes` / `no`；若 `yes`，必須走 delegation gate | 標成 autonomous 但沒有 delegation plan |
| Worker routing plan | 至少一筆 `profile=<profile> model=<model> reasoning=<level> controller_fallback=<not_allowed\|allowed>` | routine readback / PR metadata / CI closeout 沒有安排 `ops_spark` 或同級 worker |
| Spawn directives | 每個 worker 一筆 spawn directive；若不 spawn，必須填 `Trivial/self-only exception reason` | 缺 model、reasoning、controller_fallback，或 fallback allowed 但沒有 reason |
| controller_fallback_reason | `n/a`，或 `fallback_reason=<category>: <why>; impact=<decision>; evidence=<url\|sha\|command>` | controller 取代 worker 但沒有可審核原因 |
| spec_gate_status | `workflow_check_pass`、`spec_validate_pass`、`manual_checklist`、`not_using_spec`、`blocked` | `blocked`、未知、或說使用 spec 但沒有 local-only evidence |
| spec_evidence_ref | issue comment、PR comment、local note summary；只放 status/ref，不放 private output | ref 缺失，或要求提交 `.spec-injector/` / generated output |
| threshold ledger plan | `will_comment_#375`、`not_needed`、`blocked`，並說明是否會在 #375 留 comment | 需要 calibration 但沒有 #375 ledger plan，或試圖把 metrics 改塞 PR body |

Start Dialog 建議輸出：

```text
source_of_truth=#375,#376
autonomous_pr=yes
spawn=profile=ops_spark model=gpt-5.3-codex-spark reasoning=medium controller_fallback=not_allowed
controller_fallback_reason=n/a
spec_gate_status=spec_validate_pass
spec_evidence_ref=workflow-check:start:issue-<number> or local note: spec validate --repo . pass at <time>
threshold_ledger_plan=will_comment_#375
stop_reason=none
```

### Closeout Dialog（PR ready / review 後）

Closeout Dialog 在 PR ready、review finding 修完、或準備進 final merge gate 前執行。若 CI、review、thread 或 worker closeout 有任何 pending/unknown，必須停止 closeout，先補 readback、修正、留言或拆 follow-up。

| 欄位 | 可接受答案 | 何時停止 |
|---|---|---|
| latest head SHA | 最新 PR `headRefOid` | SHA 讀不到，或和驗證紀錄不一致 |
| CI / Scope Police 狀態 | required checks pass；pending/fail 必須列 blocker | required check fail/pending 且沒有明確等待或修正計劃 |
| CodeRabbit 狀態 | reviewed、rate limit fallback+self-review、或明確 skipped 並有替代證據 | 只有 status success 但實際 comment 是 skipped，或 rate limit 後仍反覆重叫 |
| chatgpt-codex-connector 狀態 | comment/review、reaction-only、或已要求 `@codex review` | 沒 comment/reaction 且未要求 review |
| unresolved review threads count | `0`，或列出每條 thread 的 disposition | unresolved thread 未處理 |
| finding disposition | `fixed`、`not adopted with rationale`、`converted to follow-up`、`blocked` | finding 只寫「已看過」但沒有 comment/resolve/follow-up |
| review_triage_ref | PR comment、issue comment、spec-injector output ref，或 `fallback=<reason>` | autonomous PR 缺 triage ref/fallback |
| root_cause_gate_ref | PR comment、issue comment、spec-injector output ref，或 `fallback=<reason>` | duplicate/root-cause gate 缺 ref/fallback |
| finding_disposition_ref | `adopted=<ref>`、`partial=<ref>`、`rejected=<ref>`、`deferred=<ref>`，或 `fallback=<reason>` | 沒有 disposition evidence ref/fallback |
| worker session closeout | worker 已讀回且不需要追加任務；已 close 或記錄 close failure | worker 仍可能執行中，或 close failure 沒記錄 |
| threshold ledger comment | `#375 comment URL`、`pending until final closeout`、`not needed` | closeout 需要 calibration 但沒有 ledger ref 或 pending reason |

Closeout Dialog 建議輸出：

```text
latest_head_sha=<sha>
ci_check_summary=pass
scope_police=pass
coderabbit_status=reviewed|rate_limit_fallback|skipped_with_self_review
codex_connector_status=reviewed|reaction-only|requested
unresolved_thread_count=0
finding_disposition=fixed|not_adopted_with_rationale|converted_to_follow_up|blocked
worker_session_closeout=closed
threshold_ledger_ref=#375 comment URL
review_triage_ref=https://github.com/.../pull/123#issuecomment-...
root_cause_gate_ref=https://github.com/.../issues/378#issuecomment-...
finding_disposition_ref=adopted=https://github.com/.../pull/123#discussion_r...
stop_reason=none
```

### Merge Gate Dialog（merge 前）

Merge Gate Dialog 是最後一道 merge 前檢查。任何欄位為 `pending`、`unknown`、`missing`、或 `blocked`，都必須停止 merge；總控不得用「應該沒問題」取代 fresh readback。

| 欄位 | 可接受答案 | 何時停止 |
|---|---|---|
| ready_to_merge | `true` / `false` | 不是 `true` 就停止 |
| latest head SHA | 最新 PR head SHA，且 match 本地/PR body final evidence | SHA 缺失或不一致 |
| required checks | `pass`；可列出 skipped non-required checks | required check fail/pending |
| unresolved_thread_count | `0` | 非 0、unknown、或未讀完整 pagination |
| spec_gate_status | `spec_validate_pass`、`manual_checklist`、`not_using_spec` | `blocked`、pending、unknown |
| spec_evidence_ref | PR comment、issue comment、local note summary；只放 status/ref | 缺 ref，或 ref 指向不可公開/private output |
| threshold_ledger_ref | #375 issue/comment URL、`not_needed`，或明確 pending blocker；若 `ready_to_merge=true` 不可再填 `pending` | 需要 ledger 但沒有 #375 ref，或 merge gate ready 後仍是 pending |
| review_triage_ref / root_cause_gate_ref / finding_disposition_ref | evidence ref 或 `fallback=<reason>`；若 `ready_to_merge=true` 不可再填 `pending`、`unknown`、`missing`、`blocked` | merge gate ready 後仍是 pending/unknown/missing/blocked |
| final PR body update | `updated_once_after_stable_evidence` 或 `not_needed` | final gate 反覆更新、仍有 pending placeholder |

Final merge gate 建議輸出：

```text
ready_to_merge=true
latest_head_sha=<sha>
required_checks=pass
unresolved_thread_count=0
spec_gate_status=spec_validate_pass
spec_evidence_ref=PR body Spec gate evidence
threshold_ledger_ref=https://github.com/nurockplayer/tachiya/issues/375#issuecomment-...
review_triage_ref=https://github.com/.../pull/123#issuecomment-...
root_cause_gate_ref=https://github.com/.../issues/378#issuecomment-...
finding_disposition_ref=adopted=https://github.com/.../pull/123#discussion_r...
final_pr_body_update=updated_once_after_stable_evidence
stop_reason=none
```

## Issue Delegation Plan

Issue body 必須先寫出 delegation plan，然後才可以進入實作或 PR。

- 必須列出 worker profile 名稱。
- 必須列出 `model` 與 `reasoning`。
- 每個 spawn 都必須顯式記錄 `controller_fallback`，若為 `allowed`，必須補說明原因。
- 必須列出每個 worker 只負責的 task。
- 如果是 routine GitHub/readback/comment/closeout/metadata/simple terminal，預設不得使用 controller 的 GPT-5.5（除非有 `controller_fallback=allowed` 並附原因）。
- 必須列出 evidence / verification，包含要讀回的證據、驗證命令、或回收點。
- 只有 trivial/self-only exception 才能不填 worker profile；這時仍然必須寫清楚 exception reason。
- 不得把 issue 當成純描述票；只要是 autonomous work，就必須可從 issue body 讀出分工與驗證。

建議格式如下，欄位名稱不得省略：

- `Worker profile`
- `model`
- `reasoning`
- `controller_fallback`
- `Task`
- `Evidence / verification`
- `Trivial/self-only exception reason`（只有例外時才可填）

## PR Delegation Execution Log

PR body 必須保留 execution log，讓總控與 reviewer 能回頭核對實際分工。

- PR 一建立就必須把 execution log 主要欄位填完整，不得先用空白殼或只留一句 placeholder，等 closeout 才一次補齊。
- 必須列出實際執行的 worker profile 名稱。
- 必須列出每個 worker 的實際工作結果，不得只寫「已完成」。
- 必須列出驗證結果與證據來源，包含測試、readback、或 CI 結果。
- 必須把 issue plan 中的 trivial/self-only exception reason 原樣帶到 PR log；如果沒有例外，就不得亂寫例外。
- 不得把 execution log 省略成一般摘要；只要是 autonomous PR，就必須看得到 delegation 與驗證的對應關係。
- closeout 只在 merge-ready 且 evidence 穩定時更新一次最終彙總；在那之前，PR body 只增量補證據，不反覆重寫 final gate 結論。

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

| 任務場景 | Profile | model | reasoning | controller_fallback |
|---|---|---|---|---|
| GitHub issue/label/PR body/check readback、CI log 初步分析、routine terminal | `ops_spark` | `gpt-5.3-codex-spark` | `low` / `medium` | `not_allowed` |
| 大範圍找檔案、找既有 pattern、測試缺口掃描 | `repo_scout` | `gpt-5.3-codex-spark` | `medium` | `not_allowed` |
| 文件、規格、issue/PR 草稿、驗證摘要 | `docs_worker` | `gpt-5.3-codex-spark` | `medium` | `not_allowed` |
| 單檔或小範圍 workflow / unit 測試補強 | `test_worker` | `gpt-5.4-mini` 或 `gpt-5.4` | `medium` / `high` | `not_allowed` |
| API/FastAPI router、service、CI 相關實作 | `backend_worker` | `gpt-5.4` | `high` | `allowed only with fallback_reason` |
| storefront/dashboard 前端修補 | `frontend_worker` | `gpt-5.4` | `medium` / `high` | `allowed only with fallback_reason` |
| 跨 repo contract、Docker、build contract 驗證 | `integration_worker` | `gpt-5.4` | `high` | `allowed only with fallback_reason` |
| schema / migration / ledger / 資料一致性 | `schema_worker` | `gpt-5.5` | `high` / `xhigh` | `allowed only with fallback_reason` |
| merge 前風險掃描與最終 review 判斷 | `review_worker` | `gpt-5.5` | `high` | `allowed only with fallback_reason` |
| controller / merge decision | `controller` | `gpt-5.5` | `high` / `xhigh` | `N/A (no fallback)` |

profile 是路由單位，`model`、`reasoning` 為硬規則欄位；除非 `controller_fallback=allowed` 且有 `fallback_reason`，不得使用 controller profile 的 GPT-5.5。

### Threshold Calibration v2

Threshold calibration v2 的目的不是把所有工作都升級成高推理，而是把「何時可 controller 直做、何時必須先走 Spark、何時需要 5.4 或 5.5」寫成可回看的資料化決策。每張 autonomous PR 都必須在 issue plan 與 PR `Delegation Execution Log` 留下 threshold 決策與 calibration data。

#### 1. Controller direct / trivial / self-only allowed

只有同時滿足下列條件，總控才可以不先派 worker，直接處理：

- 單檔或極小範圍修改，沒有跨檔共享狀態。
- 不需要 CI/check readback、review thread readback、PR body/comment cleanup、或 closeout evidence 蒐集。
- 不牽涉 schema、migration、ledger、auth、跨 repo contract、merge gate、或 review disposition 決策。
- 不需要額外 spawn worker 才能把證據補齊。

若走這條路，必須明寫 `Trivial/self-only exception reason`，不得只寫 `small task` 或 `quick fix` 這種空泛描述。

#### 2. ops_spark required

下列工作預設一定要先交給 `ops_spark`，或在其不可用時交給同級低成本替代 worker：

- routine GitHub readback、CI/check 摘要、review thread 計數、PR body/comment 整理。
- 文件整理、規格改寫、驗證摘要、檔案定位與既有 pattern 掃描。
- pre-commit checklist、post-push readback、review closeout evidence 蒐集。
- issue / PR / label / milestone / branch readback。
- CodeRabbit / `chatgpt-codex-connector` review/comment/reaction 狀態讀回。

同級低成本替代 worker 白名單只有 `repo_scout`、`docs_worker`。若 `ops_spark` 不可用，PR log 必須寫明 fallback profile 與原因；若連低成本替代 worker 都不可用，才可由 controller 補位，並把 `worker unavailable` 寫進 evidence。

#### 3. 5.4 worker required

任務已超過 routine readback / docs / summary，但還沒進入 schema 或 merge decision 層級時，預設要升級到 `gpt-5.4` 或 `gpt-5.4-mini` worker：

- 單檔或小範圍 workflow / unit test 補強。
- API/FastAPI router、service、CI 相關實作。
- storefront / dashboard 前端修補。
- 跨 repo contract、Docker、build contract 驗證。

這類工作仍然不應直接吃 controller 的 `gpt-5.5`，除非低一階 worker 已經證明不足，且有明確 fallback reason。

#### 4. 5.5 / schema / review / controller decision

下列情況才進入 `gpt-5.5` 或 controller decision 層級：

- schema、migration、ledger、資料一致性、帳務、金流、權限模型。
- merge 前風險掃描、review finding disposition、blocking technical decision。
- scope-exception、merge method、guarded merge、branch protection、stale review、rebase / merge conflict 決策。
- low-cost worker 或 5.4 worker 回報互相矛盾 evidence，且需要總控做最後判斷。

這些情況可以用 `schema_worker`、`review_worker` 或 controller 處理，但必須能從 issue/PR 讀出為什麼前一層 threshold 不足。

#### 5. Controller fallback reason format

只要 `controller_fallback=allowed`，就必須在 spawn directive 同時補 `fallback_reason`，並在 PR log 的 `Controller fallback reason` 欄位展開。建議格式如下：

- `fallback_reason=<category>: <why lower tier was insufficient>; impact=<decision or blocker>; evidence=<url|sha|command>`

`category` 只能從下列集合挑選，避免自由發揮：

- `worker_unavailable`
- `tool_unavailable`
- `rate_limited`
- `conflicting_evidence`
- `schema_or_data_risk`
- `review_or_merge_decision`

可接受範例：

- `fallback_reason=conflicting_evidence: ops_spark readback and CI summary disagree on required check set; impact=controller must decide merge gate; evidence=gh pr checks #370`
- `fallback_reason=schema_or_data_risk: docs task escalated into ledger consistency decision; impact=needs schema_worker review; evidence=issue #370 comment`

#### 6. Calibration data fields

新 autonomous PR 的 `Calibration data` 以 key=value 記錄精簡 contract 即可：

- `threshold_ledger_ref`：指向 `#375` 的 issue/comment URL、`#375`、或 `not_needed`。若 final merge gate 已 `ready_to_merge=true` / `merge_ready=true`，不得再填 `pending`。
- `status`：此筆 calibration 狀態，例如 `logged`、`open_followup`、`not_needed`。

完整 calibration metrics 以 `#375` ledger comment 為主，不要求每張新 PR 都重複貼進 PR body。

下列 legacy metrics 僅供相容舊 PR 或過渡期使用，非新 PR 必填：

- `spawn_count`
- `ci_rerun_count`
- `review_thread_count`
- `rework_reason`
- `threshold_decision`
- `threshold_followup_needed`

若是 manual / human PR，`Calibration data` 可填 `n/a` 或省略；若是 autonomous PR，至少要有可判讀的 `threshold_ledger_ref` / `status`，或保留 legacy metrics 相容格式。

#### 7. Calibration review cadence

Threshold calibration 不是寫完一次就算。至少每累積 3 張 autonomous PR，就要回看一次最近資料，決定 threshold 是否調整。

- 最小回看樣本：最近 3 張 autonomous PR。
- 若連續出現 `spawn_count` 過高、`ci_rerun_count` 過高、或 `review_thread_count` 常靠 controller 人工收斂，應考慮把更多 routine 工作下放或先拆 follow-up。
- 若連續出現 `threshold_followup_needed=yes`，必須在 docs、PR template、或 routing policy 開 follow-up，不要只留在口頭判斷。
- 若資料顯示現有規則運作正常，仍要在回看紀錄中明寫 `no threshold change`，避免默默漂移。

## Cost Model 與摩擦預算

Tachiya 的 autonomous workflow 優化先採用工作假設：目前約 40% 時間消耗來自 infra 本質複雜，約 60% 來自工作流自己製造摩擦。這不是精準量測，而是用來決定治理優先序的分類。

| 類型 | 例子 | 處理方式 |
|---|---|---|
| infra 本質複雜 | GitHub API / review thread 狀態、CI check rollup、rate limit、跨 repo metadata、不同模型額度 | 接受其存在，用固定 readback 欄位與驗證命令降低不確定性 |
| 工作流自己製造摩擦 | 忘記先派 worker、總控自己做 routine readback、worker 完成後未 close、PR 後期無限加碼、review finding 沒有 comment/resolve 證據 | 用 routing map、lifecycle checklist、review closeout checklist、follow-up split policy 消除 |

每張 autonomous PR 的 `Delegation Execution Log` 應說明這次是否遇到 60% 類型的流程摩擦，以及已如何避免它重現。若只是 infra 本質複雜，應留下讀回證據；若是流程摩擦，優先修流程或另開 follow-up issue。

## Routing Rules

依 `Worker Profiles` 表格路由，特別注意：

- `ops_spark` / `repo_scout` / `docs_worker` 一律顯式使用 `gpt-5.3-codex-spark`，不得繼承 controller 的 `gpt-5.5`。
- routine readback、PR body/comment、closeout evidence、CI log、simple terminal 都走 `ops_spark`。
- schema、migration、ledger、金流、權限模型與 merge decision 才保留 `gpt-5.5` high/xhigh。

### ops_spark Routing Hardening

預設一定要交給 `ops_spark` 或同級低成本 worker 的工作：

- issue / PR / label / milestone / branch readback。
- CI check rollup、failed log 第一輪摘要、required check 名稱比對。
- CodeRabbit / `chatgpt-codex-connector` review/comment/reaction 狀態讀回。
- review thread list、resolved/unresolved count、thread URL 蒐集。
- PR body、issue comment、closeout evidence 草稿。
- pre-commit checklist 與 post-push readback。

不得預設交給 `ops_spark` 的工作：

- schema、migration、資料一致性、帳務/points ledger、金流、權限模型。
- 是否接受 review finding 的技術取捨。
- scope-exception、merge method、guarded merge。
- 需要跨產品架構取捨的決策。

升級條件：

- `ops_spark` 回報資料互相矛盾、缺權限、rate limit、或無法判定 required gate。
- finding 涉及 schema / auth / wallet / ledger / migration / production data。
- PR scope 需要拆分、rebase、merge conflict 或 branch protection 決策。

若 `ops_spark` 額度、工具或模型不可用，總控可以改用同級低成本替代 worker，白名單限制為 `repo_scout`、`docs_worker`。並且必須在 `Delegation Execution Log` 寫明 fallback profile 與替代理由。若低成本 worker 都不可用，總控可以完成必要收斂工作，但必須把 `worker unavailable` 列為 closeout evidence，不得假裝已正常委派。

Spawn 指令為硬規則（建議每個 worker 一筆）：

- `spawn: <profile> model=<model> reasoning=<low|medium|high|xhigh> controller_fallback=<not_allowed|allowed> [fallback_reason=<reason>]`
- `profile` 可用 profile 名稱，不加前綴。
- `controller_fallback=allowed` 時，必須補 `fallback_reason`。
- 若無 fallback reason，預設視為 `controller_fallback=not_allowed`，不得將 `ops_spark`、`repo_scout`、`docs_worker` 拉到 controller 高階推理上。

## GitHub 操作分工

`ops_spark` 可以處理：

- 依總控核准的 scope 建 issue、查 issue、補 issue comment。
- 驗證 issue label / state / URL readback。
- 建 PR、更新 PR body。
- 整理 PR body、PR comment、issue comment、review closeout evidence。
- 查 labels、milestones、review state、CI checks。
- 抓 failed check logs 並整理摘要。
- 讀回 latest head SHA、merge state、status rollup。
- 準備 closeout evidence。
- 確認 review thread 是否 resolved，並彙整 comment URL、discussion URL、thread id、head SHA、讀回時間點。

`ops_spark` 回報必須包含可被總控核對的證據摘要，不只寫「已確認」。至少列出：

- 讀回來源與指令摘要。
- PR head SHA 或 issue/comment URL。
- CI/check、review、thread/comment 的目前狀態。
- 缺權限、rate limit、工具限制或需要總控判斷的 blocker。

任何 `ops_spark` / low-cost handoff 的最小欄位為：

- `evidence_url`：PR、issue、workflow run、review thread、comment 或 log URL。
- `state_snapshot`：讀回當下的 state / conclusion / reviewDecision / head SHA。
- `blockage_reason`：若 blocked，寫出是權限、rate limit、tool unavailable、CI failure、review finding 或 scope conflict；若未 blocked，填 `none`。
- `next_action`：建議總控下一步採取 wait / fix / comment / resolve / merge / split follow-up。
- `readback_at`：讀回時間點或相對時間，避免 stale evidence 被誤用。

總控保留：

- 是否 merge。
- merge method。
- `gh pr merge --match-head-commit`。
- conflict / failed check / stale review 的決策。
- issue close 的最終 scope 判斷。
- review finding 是否採納、是否需要補修、是否可用替代證據 closeout 的最終判斷。

## Commit / push 分工

實際 git write 目前由 controller 擁有：建立或切換 branch、產生 commit、push branch、force-with-lease、以及任何會改動 `.git`、credential、remote tracking 或目前 branch 狀態的操作，都不得預設交給 worker。

`ops_spark` 預設負責 git write 前後的例行證據工作：

- pre-commit checklist：確認 working tree scope、預期驗證命令、commit message 是否含 `refs #...` 或 PR closeout 所需 reference。
- post-push readback：讀回 commit SHA、push branch、remote branch、PR head SHA、CI/check 狀態、review/readback 狀態。
- PR log/evidence 整理：把 controller-owned git write 的原因、ops_spark checklist、post-push readback 與剩餘 blocker 寫進 PR log 或 closeout evidence。

如果 controller 因工具故障、權限不足、trivial/self-only exception，或任務切片太小而自行完成 pre-commit checklist / post-push readback，PR Delegation Execution Log 必須寫明原因，並列出等價證據：commit SHA、push branch、PR head SHA、CI/check readback 與讀回時間點。

## spec-injector Local-only Gate

如果 repo 有使用 `spec-injector`，autonomous workflow 必須把它當成 local-only gate，而不是可隨意提交的產物來源。

AWP review triage / root-cause gate 的 source issue 也以 spec-injector 為主：`Erick52106/spec-injector#232`、`Erick52106/spec-injector#233`、`Erick52106/spec-injector#234`、`Erick52106/spec-injector#235`。tachiya 只保留 template / docs / Scope Police 的薄接線，不在本 repo 複製完整 checker。

### Bootstrap contract

Autonomous worker 開工前應先確認目前環境拿到的 `spec-injector` 版本支援 `Erick52106/spec-injector#242` 的 workflow gate。canonical source 是 `https://github.com/Erick52106/spec-injector`。

優先使用現有 `spec`；若沒有新版能力，再用 local fallback runner，不要求全域 `pnpm link`：

```bash
export SPEC_INJECTOR_DIR="${SPEC_INJECTOR_DIR:-$HOME/dev/spec-injector}"

spec_has_awp_gates() {
  command -v spec >/dev/null 2>&1 &&
  spec workflow-check --help 2>/dev/null | grep -q -- "--finding-disposition" &&
  spec workflow-check --help 2>/dev/null | grep -q -- "--threshold-evidence" &&
  spec workflow-check --help 2>/dev/null | grep -q -- "--pr"
}

if spec_has_awp_gates; then
  SPEC_CMD="spec"
else
  if [ ! -d "$SPEC_INJECTOR_DIR/.git" ]; then
    git clone https://github.com/Erick52106/spec-injector.git "$SPEC_INJECTOR_DIR"
  fi

  git -C "$SPEC_INJECTOR_DIR" pull --ff-only
  cd "$SPEC_INJECTOR_DIR"
  pnpm install --frozen-lockfile
  pnpm build

  SPEC_CMD="node $SPEC_INJECTOR_DIR/dist/cli/index.js"
fi

$SPEC_CMD workflow-check --help
```

若 clone、pull、install、build 或 capability check 失敗，必須停止 autonomous 開工並回報 `tool/bootstrap blocker`。不得改用舊版 `spec` 假裝通過，也不得把 `.spec-injector/`、generated output、routing JSON、threshold JSON、finding disposition JSON 或 private context commit 進 repo。

### Required checkpoints

- 開工前：先跑 `spec validate --repo .`，再跑 `$SPEC_CMD workflow-check --repo . --phase start --issue <issue-number-or-url>`。start gate 用於 bounded context、Hybrid AWP routing 與 fallback 判定。
- commit 前：再次跑 `spec validate --repo .`，再跑 `$SPEC_CMD workflow-check --repo . --phase commit --pr-body <path> [--routing-evidence <json>]`。commit gate 用於 staged artifact、安全邊界、Spec gate status/ref 與 routing evidence alignment。
- review / closeout 後：若有 automated/human findings，使用 `$SPEC_CMD workflow-check --repo . --phase merge --pr-body <path> [--finding-disposition <json>] [--threshold-evidence <json>]` 驗證 finding disposition 與 threshold evidence 只以 status/ref 進入 PR body。
- merge 前：final readback 前再跑一次 `spec validate --repo .`，再跑 `$SPEC_CMD workflow-check --repo . --phase merge --pr-body <path> --head-sha <sha> [--routing-evidence <json>] [--finding-disposition <json>] [--threshold-evidence <json>]`。需要 GitHub readback 時，可另外跑 `$SPEC_CMD workflow-check --repo . --phase merge --pr <number-or-url> --format json`。結果寫進 PR body 的 `Spec gate evidence` 與 `Final merge gate`。

### Storage / commit boundaries

- 不得 commit `.spec-injector/` 目錄內容、generated output、暫存 prompt/context 檔，除非 source issue 明確授權且 PR scope 也明寫。
- `spec-injector` 在此流程的預設用途是 local validation、context generation、manual checklist 對照，不是 repo artifact producer。
- 若 `spec validate --repo .` 失敗，先修 template/docs/checklist 契約，再考慮 commit；不得把失敗狀態直接帶進 merge gate。

### Manual checklist fallback

- 若作者或 reviewer 沒有使用 `spec-injector`，仍必須走同一套欄位契約：以 PR template 的 `Spec gate evidence` 填 manual checklist 結果，至少記錄 `not using spec-injector`、人工檢查範圍、檢查時間點與剩餘風險。
- manual path 至少要覆蓋：delegation 欄位完整、review closeout 欄位完整、final merge gate 欄位完整、不可提交 `.spec-injector/` 或輸出。
- 未使用 `spec-injector`、`workflow-check` 不可用、或工具 bootstrap 被 blocker 擋住時，manual checklist 與 template 欄位就是正式替代路徑；不得把 manual fallback 寫成 fake pass。

## Automated Review Gate

任何 autonomous PR merge 前，總控必須完成 fresh review readback：

1. 先指派 `ops_spark` 讀回最新 PR head SHA、base branch、mergeability 與 CI/check 狀態；總控審核讀回結果。
2. 先指派 `ops_spark` 確認 CodeRabbit 是否已產生實際 review；若 CodeRabbit 明確回 rate limit，同一張 PR 不再重複要求 review，改由總控做 self-review 並留下替代 review 證據。
3. 先指派 `ops_spark` 確認 `chatgpt-codex-connector` 已留下 review/comment，或在第一則 PR comment 左下角留下 reaction。只有兩者都沒有時，才手動 comment `@codex review`。
4. 針對每個 actionable automated review finding，merge 前只能選一條路：
   - 修正、push、重跑相關驗證；
   - 留下技術佐證 comment 說明為何不採用。
5. GitHub 允許時，將已處理的 review thread/comment resolve；routine comment/resolve/readback 由 `ops_spark` 執行或整理，總控負責判斷處置是否足夠。
6. 若 push 過新 commit，merge 前由 `ops_spark` 重新讀回 head SHA 與 automated review 狀態。

review comments 必須先做 necessity assessment，不可因 reviewer 是 CodeRabbit、Codex 或 human 就盲目採用。triage 時至少要確認：

- 這個 finding 是否真的指向當前 PR 的 scope、不是已被後續 commit 消掉的舊 head、也不是 template/parser 誤讀。
- review batch 必須綁定 reviewed head SHA；新 commit push 後，舊 finding 只能作為背景，不可直接拿來當最新 merge gate 結論。
- CodeRabbit、Codex、human 的 duplicate finding 要 collapse 成同一個 root cause，不要為同一個症狀連續疊 patch。
- repeated same-concept edge case 代表需要 root-cause / state-model assessment，不是再補第三個局部 if/regex。
- parser / gate / workflow follow-up 優先用 matrix-first / table-driven tests 收斂；tachiya 只保留 thin wiring，完整 schema/checker 追到 `Erick52106/spec-injector#232`、`Erick52106/spec-injector#233`、`Erick52106/spec-injector#234`、`Erick52106/spec-injector#235`。
- 如果 follow-up patch budget 已經吃掉原 PR 約 25-30% 以上，必須重新判斷是 split/follow-up issue，還是當前 PR 仍應繼續承接。

CodeRabbit 由 `.coderabbit.yaml` 設定 `reviews.auto_review.base_branches: [".*"]`，讓 PR target branch 不限 default branch 都能觸發 auto review。

## Review Conversation Closeout Gate

每個 autonomous PR 都要把 automated review conversation 收斂到可追溯狀態，無論是修正還是不採用：

1. 對每一則 actionable finding，總控需先列出處置；`ops_spark` 負責蒐集 thread/comment/readback 證據：
   - `fix`：推上修正 commit，補上「已修正」comment（可含驗證證據），並在可見 thread 上 resolve。
   - `not adopted`：保留不採用理由 comment，並在可見 thread 上 resolve。
2. 如果沒有權限/工具不允許 resolve thread，必須在 PR comment 補一則替代紀錄，包含 thread URL、處置原因與剩餘風險或後續追蹤狀態。
3. 新增 commit 後，指派 `ops_spark` 回到 PR 做 fresh readback，重確認：
   - review/auto-review 狀態
   - 每則 finding 的處置紀錄仍保留完整
   - head SHA 與最新 conversation 狀態一致
4. PR closeout 前，review conversation 要求不得是「僅有文字變更描述」，最少要有 comment 或 resolve 證據可被 reviewer/readback 看到。
5. 總控不得把「留證據並 resolve」這類資訊搬運工作預設留給自己做；只有工具故障、權限不足、或任務小到符合 trivial/self-only exception 時才可自行處理，且必須在 PR log 寫明原因。
6. 每條 actionable finding 都必須有固定 disposition：`fix`、`not adopted`、`converted to follow-up`、`rate limit fallback`、`connector reaction-only` 或 `blocked`；不得只寫「已看過」而沒有 comment/resolve 或替代證據。
7. PR body 的 `review_triage_ref`、`root_cause_gate_ref`、`finding_disposition_ref` 只放短 evidence ref 或 `fallback=<reason>`，不要把 full matrix、統計表、或完整 comment body 再複製進 template。

### Review Closeout Evidence Matrix

每個 automated review finding 在 merge 前都必須落入下列其中一種狀態：

| 狀態 | 必備證據 | 可 merge 條件 |
|---|---|---|
| fixed | 修正 commit、相關驗證命令、finding thread/comment URL、resolved 狀態 | 可 merge |
| not adopted | 技術理由 comment、剩餘風險、thread/comment URL、resolved 狀態 | 可 merge，但需 reviewer 可讀 |
| converted to follow-up | follow-up issue URL、此 PR 不做的理由、finding URL | 只有非 blocking finding 可用 |
| rate limit fallback | CodeRabbit 明確 rate limit 證據、總控 self-review comment、驗證結果 | 可以，但不得重複要求同一張 PR 的 CodeRabbit review |
| connector reaction-only | `chatgpt-codex-connector` 對 latest head 的 reaction 或明確 review/comment readback | 可以 |
| blocked | 無法驗證、無法 resolve、finding 仍 actionable | 不可 merge |

closeout comment 至少要列出 latest head SHA、CI/check 結論、unresolved thread count、CodeRabbit 狀態、`chatgpt-codex-connector` 狀態，以及每條 finding 的採納/不採納結果。

最終 closeout 必須能把每個 finding 收斂到 `adopted`、`partial`、`rejected`、`deferred` 其中之一，並且各自有 evidence ref。若因 source issue / upstream checker 尚未完成而暫緩，`deferred` 也必須附對應 issue/comment ref。

final closeout summary 只應在下列條件都穩定後更新一次：

- latest head SHA 已固定，且沒有新的 push/metadata rerun 在排隊
- CI/check summary、CodeRabbit、`chatgpt-codex-connector` 狀態已對上最新 head
- unresolved thread count 與 finding disposition 已完成最後一次 readback
- `Spec gate evidence` 已填入最新 `spec validate --repo .` 加 `spec workflow-check` status/ref，或明確 manual fallback 結果
- `Final merge gate` 使用 key-value 形式；初始 PR 可用 `pending initial gate` 標記尚未穩定的值，但 `ready_to_merge=true` 或 `merge_ready=true` 時必須把 `latest_head_sha`、`unresolved_thread_count`、`spec_gate_status`、`evidence_urls` 改成實際證據，且 `unresolved_thread_count=0`

## Autonomous Review Closeout Evidence Runbook

這是一頁式 closeout 操作清單。策略規則仍以前面的 `Automated Review Gate` 與 `Review Conversation Closeout Gate` 為準；本段只定義實際跑 PR closeout 時要留下哪些證據。

### 責任分工

- `ops_spark`：讀回 PR head SHA、CI/check 狀態、CodeRabbit 狀態、`chatgpt-codex-connector` comment/reaction、review thread list、resolved/unresolved count、comment URL 與 artifact URL。
- `controller`：判斷 finding 是否 blocking、是否採納、是否拆 follow-up、是否允許 merge。
- `controller`：只能在 final readback 後執行 `gh pr merge --match-head-commit <head-sha>`。

### 最小 readback 指令集

closeout 前至少要有等價於下列資訊的讀回；指令可依工具可用性調整，但 evidence 欄位不可少：

```bash
gh pr view <pr> --json headRefOid,mergeStateStatus,mergeable,state,url
gh pr checks <pr>
gh pr view <pr> --json comments,latestReviews
gh api graphql ... reviewThreads(first:50, after: $cursor) {
  pageInfo { hasNextPage endCursor }
  nodes { isResolved isOutdated comments { nodes { url author { login } body } } }
}

必須循環呼叫，直到 `pageInfo.hasNextPage == false`，每次使用上一頁的 `pageInfo.endCursor` 作為 `$cursor`。
```

讀回結果必須整理到 PR `Review conversation closeout` 或 closeout comment，至少包含：

- `latest_head_sha`
- `ci_check_summary`
- `coderabbit_status`
- `codex_connector_status`
- `unresolved_thread_count`
- `finding_disposition`：`fixed`、`not adopted`、`converted to follow-up`、`rate limit fallback`、`connector reaction-only` 或 `blocked`
- `evidence_urls`：review comment、thread、workflow run、artifact、follow-up issue URL

若 PR template 有 `Final merge gate` 欄位，以上資訊必須以該欄位為主；closeout comment 只作補充，不取代 PR body 的最終欄位。

### Reviewer fallback

- CodeRabbit 明確 rate limit：同一張 PR 不再重複要求 CodeRabbit review；改由 controller self-review，並留下 self-review comment、驗證命令與剩餘風險。
- CodeRabbit status 為 success 但內容是 skipped：不得視為完成，必須讀 comment 或 run configuration 判定是否真的 review。
- `chatgpt-codex-connector` 若沒有 comment，但在最新 PR comment 留下 reaction，可以記為 `connector reaction-only`。
- `chatgpt-codex-connector` 若沒有 reaction/comment，才由 controller 留 `@codex review`；若第二次仍無回應，記為 `blocked` 或開 follow-up，不得默默 merge。

### Metadata rerun 規則

- PR body 或 label 類 metadata 修正後，要觸發新的 PR `edited` / `labeled` event，讓 gate 用最新 payload 重跑。
- 不要只 rerun 舊的 failed workflow run；舊 run 可能重用舊 event payload，導致 sticky comment 被舊狀態覆蓋。
- Scope Police sticky comment 以最新成功 run 的內容為準；若 pass/fail comment 互相覆蓋，先讀 workflow run started/completed time，再用新的 metadata event 重新觸發。

### Storage boundaries

- Issue comment：保存開工前 delegation plan 與 source-of-truth。
- PR body：保存實際 worker profile、spawn directive、validation、closeout summary。
- PR review thread/comment：保存每條 finding 的處置證據。
- Repo docs：只保存通用流程與模板，不保存單一 PR 的完整 log。

## Subagent Lifecycle 與 Thread-limit Cleanup

總控必須把 worker 視為有生命週期的資源，而不是只把 spawn 當成背景工作：

1. spawn 前先確認任務是否真的需要 worker，並保留 thread buffer；同類 routine readback 盡量合併成一個 `ops_spark` 任務。
2. spawn prompt 必須列出 write scope、禁止事項、驗證命令、回報格式與 closeout 需求。
3. worker 回報後，總控先讀回結果；若不需追加任務，立即 close worker session。
4. close 後在 PR `Worker session closeout` 欄位記錄「已讀回結果並 close」，或至少記錄 `close_agent` 的 `retry_count`、`last_error`、`next_retry_eta`、`final_outcome` 與 fallback。
5. `close_agent` 失敗時，硬性重試規則為：
   - `MAX_CLOSE_RETRIES=3`。
   - Backoff 分別為 30 秒、90 秒、180 秒。
   - 累計超過 5 分鐘即視為 hard cutoff，必須停止再重試。
6. 若 close 失敗但 worker 已完成且無 active handle，標記 `stale/unavailable`；若仍可能執行中，禁止再派同類 worker，改走 controller fallback 或人工釐清，並在 `Worker session closeout` 記錄 `final_outcome=worker unavailable/stale`。

spawn 前名額檢查採下列警戒線：

- `green`：可用 worker slots >= 2，可正常 spawn。
- `yellow`：只剩 1 個可用 worker slot，只能 spawn 最必要的 `ops_spark` / reviewer；其他探索或 polish 必須延後或合併。
- `red`：無可用 worker slot，禁止新 spawn；先 close 已完成 worker、等待 stale handle 釐清，或改成總控 fallback 並在 PR log 寫明 `worker unavailable`。
- 若無法讀到精準 slot 數，採保守模式：同時 active worker 不超過 2，且每完成一個 worker 都要先 close 再 spawn 下一個。

spawn 前若已知 worker 額度或 thread limit 不足，先選低成本替代 worker；若替代 worker 也不可用，才使用總控 fallback。總控 fallback 必須寫入 PR body 的 `Worker session closeout` 或 `Trivial/self-only exception reason`，避免把資源限制誤記成正常委派。

## Issue-first 與 Follow-up Split Policy

所有 autonomous work 都要先落在 issue scope 內；PR 後期不應把新發現的優化塞回同一張 PR。

- 開工前由 `repo_scout` / `ops_spark` 先收斂 source issue、相關 PR、必跑驗證、review gate 與 scope police 風險。
- issue body 若缺 delegation plan，先補 issue comment 或在 PR body 明確引用既有 plan；不得用 PR 才第一次定義 scope。
- PR 後期只修 blocking review finding、CI failure、scope police failure、merge conflict。
- 新的優化、文件補強、流程 polish、非 blocking reviewer 建議，必須拆成 follow-up issue。
- 若一張 PR 反覆因新想法加碼，總控應停止擴張，將剩餘優化移出當前 PR。

follow-up issue 至少要包含：背景、當前 PR 不做的理由、建議輸出、完成條件、參考 PR/comment URL。若 follow-up issue 為 `[backend]` 或 `[frontend]` 開發任務，還必須額外補上：Task checklist、Interface/Specification、Reference file paths。這讓人類與後續 agent 都能從 issue 直接接手，不必重新翻整段對話。

## PR Template 與 Policy-test Hardening

PR template、issue template 與 policy test 必須 lockstep 維護：

- PR template 的示例不得是可被 workflow parser 誤判為正式欄位的可執行指令；示例若可能觸發 gate，必須放在 HTML comment 或改成非 executable wording。
- `.github/workflow-tests/ci-policy.test.mjs` 必須覆蓋 template、autonomous detection、placeholder、spawn directive、worker closeout、workflow friction、scope budget 與 `scope-exception` 不 bypass autonomous gate 的 regression。
- policy test 至少要有正例與反例，涵蓋 placeholder / spawn / `ops_spark` model / fallback / scope budget。
- policy test 只鎖住可機器檢查的契約；更大範圍的 router / daemon / CLI profile 自動化必須另開 issue，不放進同一張 governance PR。
- PR diff 接近 600 行時應優先壓縮或拆分；超過 1000 行時不得靠 `scope-exception` 當常態解法。

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
2. 總控決定 issue scope；`ops_spark` 負責建立或更新 GitHub issue，並讀回 URL、state、labels。
3. 從 `develop` 切 scoped branch。
4. 依任務類型指派 worker。
5. worker 回報變更與驗證；總控審查 diff。
6. 總控讀回 worker 結果；若不需追加任務，立即 close worker session，並在 PR log 記錄 closeout。
7. 總控或 worker 補必要修正。
8. 跑 relevant validation；高風險改動需 full validation。
9. `ops_spark` 可依總控核准內容開 PR 到 `develop` 或更新 PR body；PR body 包含 Source of truth、Depends on PR、non-goals、validation。
10. `ops_spark` 做 CI/checks/review 狀態 fresh readback，總控判斷是否需要補修或等待。
11. 總控用 guarded merge 合併。
12. `ops_spark` 補 issue evidence comment，確認 issue state / labels / closeout；總控審核 closeout scope。
13. 更新本機 `develop`，回報 merge commit、驗證與剩餘風險。

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
