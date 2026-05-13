## 什麼改動
<!-- 簡要說明這個 PR 做了什麼 -->

## Scope 對齊
Source of truth: <!-- issue / PR / docs，例如 #345 -->
Depends on PR: <!-- `none` 或 `#123` -->

## 本 PR 明確不做
- <!-- 請列出 non-goals；若無請填 n/a -->

## Delegation Execution Log
<!-- Codex autonomous PR 必填；非 autonomous human PR 可填 n/a。 -->
- Source issue delegation plan:
  - <!-- 例：#345 的 Issue Delegation Plan -->
- Actual worker profile(s):
  - <!-- 例：controller / docs_worker / ops_spark；routine readback / CI status / PR comment 整理 / review closeout evidence 預設要列出 ops_spark -->
<!-- autonomous PR 的 Spawn directive 必須填在欄位同一行；多個 worker 請重複此欄位。格式：profile=<profile> model=<model> reasoning=<level> controller_fallback=<not_allowed|allowed> [fallback_reason=<category>: <why>; impact=<decision>; evidence=<url|sha|command>]。非 autonomous human PR 可填 n/a。 -->
- Spawn directive:
- Controller fallback reason:
  - <!-- autonomous 例：fallback_reason=conflicting_evidence: ops_spark readback and CI summary disagree; impact=controller merge gate decision; evidence=gh pr checks #370。若無任何 worker 使用 controller_fallback=allowed，填 n/a；manual/human PR 也填 n/a -->
- Task:
  - <!-- 每個 worker 實際負責的切片；請把 GitHub readback、CI status、PR body/comment cleanup、review closeout evidence、pre-commit checklist、post-push readback 拆成獨立 ops_spark slice -->
- Model strength:
  - <!-- 例：controller = high；docs_worker = medium -->
- Trivial/self-only exception reason:
  - <!-- 若無例外請填 n/a -->
- Threshold decision:
  - <!-- autonomous 例：decision=ops_spark_required; rationale=routine readback and PR body cleanup; escalated_to=none。manual/human PR 填 n/a -->
- Calibration data:
  - <!-- autonomous 請只填 #375 ledger ref/status，例如 threshold_ledger_ref=#375 pending until closeout，或 threshold_ledger_ref=https://github.com/nurockplayer/tachiya/issues/375#issuecomment-...。不要把 threshold metrics 展開塞進 PR body；metrics 請留在 #375 ledger comment。manual/human PR 填 n/a -->
- Threshold follow-up:
  - <!-- autonomous 例：status=no_change; next_review_after_prs=3; followup_issue=none。若需要調整，例：status=open_followup; next_review_after_prs=3; followup_issue=#370。manual/human PR 填 n/a -->
- Evidence / verification:
  - <!-- 例：git diff --check；node --test .github/workflow-tests/*.test.mjs；commit SHA；push branch；PR head SHA；CI/check/review/thread readback 摘要；若 git write 由 controller 執行，記錄原因與 ops_spark checklist/readback -->
- Spec gate evidence:
  - <!-- status + ref only。請填 start-of-work / pre-commit / pre-merge 的 `spec validate --repo .` 狀態與 evidence ref；若未使用 spec-injector，填 `not_using_spec` 或 `manual_checklist`，並補 issue comment / PR comment / local note summary。不得提交 `.spec-injector/`、generated output 或 private context。未來若接上 `spec workflow-check`，只引用 evidence ref。 -->
- Worker session closeout:
  - <!-- 例：已讀回 worker 結果，不需追加任務的 worker session 已 close；若 close_agent 失敗，列出 handle、重試次數與 fallback 紀錄 -->
- Workflow friction / follow-up split:
  - <!-- autonomous PR 請說明本次約 40% infra 複雜 / 約 60% 工作流摩擦中，哪些已由 routing / closeout / lifecycle / follow-up issue 收斂；非 autonomous PR 可填 n/a -->
- Review conversation closeout:
  - <!-- autonomous: 請填 latest_head_sha、ci_check_summary、coderabbit_status、codex_connector_status、unresolved_thread_count、finding_disposition、evidence_urls；若 metadata rerun，請註明是否用新的 PR edited/labeled event，不要只 rerun 舊 payload。非 autonomous human PR 填 n/a -->
- Final merge gate:
  - <!-- 只在 merge-ready 且 evidence 穩定時更新一次。初始 PR 請先用 key=value 填 `pending initial gate`，例如 latest_head_sha=pending initial gate、unresolved_thread_count=pending initial gate、spec_gate_status=pending initial gate、evidence_urls=pending initial gate。最終 closeout 請改成 latest_head_sha、ci_check_summary、coderabbit_status、codex_connector_status、unresolved_thread_count、finding_disposition、evidence_urls、spec_gate_status、worker_sessions_closed、pr_body_pending_status，並加 ready_to_merge=true 或 merge_ready=true；ready 時 unresolved_thread_count 必須是 0，且不得留下 pending initial gate。不要反覆覆寫 final 結論。 -->

## Validation
- [ ] 本地測試過
- [ ] 有寫 / 更新測試

```text
（貼上關鍵驗證摘要；若不適用請填 n/a）
```

## Notes for Review
<!-- 需要 reviewer 特別注意的風險、假設或 follow-up -->
