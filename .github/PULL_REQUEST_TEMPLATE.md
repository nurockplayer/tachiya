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
- Spawn directive format:
  - 需填入的格式：`profile=<profile> model=<model> reasoning=<low|medium|high|xhigh> controller_fallback=<not_allowed|allowed> fallback_reason=<reason if allowed>`
  - 例：spawn 指令格式（不要直接複製這一行）：profile=ops_spark model=gpt-5.3-codex-spark reasoning=medium controller_fallback=not_allowed
- Task:
  - <!-- 每個 worker 實際負責的切片；請把 GitHub readback、CI status、PR body/comment cleanup、review closeout evidence、pre-commit checklist、post-push readback 拆成獨立 ops_spark slice -->
- Model strength:
  - <!-- 例：controller = high；docs_worker = medium -->
- Trivial/self-only exception reason:
  - <!-- 若無例外請填 n/a -->
- Evidence / verification:
  - <!-- 例：git diff --check；node --test .github/workflow-tests/*.test.mjs；commit SHA；push branch；PR head SHA；CI/check/review/thread readback 摘要；若 git write 由 controller 執行，記錄原因與 ops_spark checklist/readback -->
- Review conversation closeout:
  - <!-- autonomous: 填「已完成 closeout」，並補註 comment/resolve/thread URL/readback 驗證；非 autonomous human PR 填 n/a -->

## Validation
- [ ] 本地測試過
- [ ] 有寫 / 更新測試

```text
（貼上關鍵驗證摘要；若不適用請填 n/a）
```

## Notes for Review
<!-- 需要 reviewer 特別注意的風險、假設或 follow-up -->
