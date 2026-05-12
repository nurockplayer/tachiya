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
<!-- autonomous PR 的 Spawn directive 必須填在欄位同一行；多個 worker 請重複此欄位。格式：profile=<profile> model=<model> reasoning=<level> controller_fallback=<not_allowed|allowed>。非 autonomous human PR 可填 n/a。 -->
- Spawn directive:
- Task:
  - <!-- 每個 worker 實際負責的切片；請把 GitHub readback、CI status、PR body/comment cleanup、review closeout evidence、pre-commit checklist、post-push readback 拆成獨立 ops_spark slice -->
- Model strength:
  - <!-- 例：controller = high；docs_worker = medium -->
- Trivial/self-only exception reason:
  - <!-- 若無例外請填 n/a -->
- Evidence / verification:
  - <!-- 例：git diff --check；node --test .github/workflow-tests/*.test.mjs；commit SHA；push branch；PR head SHA；CI/check/review/thread readback 摘要；若 git write 由 controller 執行，記錄原因與 ops_spark checklist/readback -->
- Worker session closeout:
  - <!-- 例：已讀回 worker 結果，不需追加任務的 worker session 已 close；若 close_agent 失敗，列出 handle、重試次數與 fallback 紀錄 -->
- Workflow friction / follow-up split:
  - <!-- autonomous PR 請說明本次約 40% infra 複雜 / 約 60% 工作流摩擦中，哪些已由 routing / closeout / lifecycle / follow-up issue 收斂；非 autonomous PR 可填 n/a -->
- Review conversation closeout:
  - <!-- autonomous: 請填 latest_head_sha、ci_check_summary、coderabbit_status、codex_connector_status、unresolved_thread_count、finding_disposition、evidence_urls；若 metadata rerun，請註明是否用新的 PR edited/labeled event，不要只 rerun 舊 payload。非 autonomous human PR 填 n/a -->

## Validation
- [ ] 本地測試過
- [ ] 有寫 / 更新測試

```text
（貼上關鍵驗證摘要；若不適用請填 n/a）
```

## Notes for Review
<!-- 需要 reviewer 特別注意的風險、假設或 follow-up -->
