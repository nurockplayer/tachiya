import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const readWorkflow = (name) => readFileSync(new URL(`../workflows/${name}`, import.meta.url), "utf8");
const readRepoFile = (relativePath) => readFileSync(new URL(`../../${relativePath}`, import.meta.url), "utf8");

const stripTemplateComments = (body) => body.replace(/<!--[\s\S]*?-->/g, "");

const evaluateAutonomousCloseoutGate = ({ body, labels = [] }) => {
  const bodyForAutonomousGate = stripTemplateComments(body);
  const normalizedLabels = labels.map((label) => (label || "").toLowerCase());
  const autonomousLabels = new Set(["codex", "codex-automation", "auto-ready"]);
  const hasAutonomousLabel = normalizedLabels.some((label) => autonomousLabels.has(label));
  const hasDelegationExecutionLog = /(?:^|\n)\s*(?:#{1,6}\s*)?Delegation Execution Log\b/i.test(bodyForAutonomousGate);
  const autonomousDetected = hasAutonomousLabel || hasDelegationExecutionLog;

  const extractSectionBody = (label) => {
    const pattern = new RegExp(
      `(?:^|\\n)\\s*(?:-\\s*)?(?:#{1,6}\\s*)?${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*[：:]\\s*([\\s\\S]*?)(?=\\n\\s*##\\s|\\n*$)`,
      "i",
    );
    const match = bodyForAutonomousGate.match(pattern);
    return match?.[1] ?? "";
  };

  const normalizeLine = (line) =>
    line
      .replace(/^\s*[-*]\s*/, "")
      .replace(/^[`"'“”‘’]+|[`"'“”‘’]+$/g, "")
      .replace(/[.,。:：;；!?！？]+$/g, "")
      .trim();

  const isPlaceholderLine = (line) => /^(?:n\/a|none|無|不適用)(?:$|[\s:：.,，。;；!?！？-].*)/i.test(line);
  const reviewConversationCloseoutLines = extractSectionBody("Review conversation closeout")
    .split("\n")
    .map(normalizeLine)
    .filter(Boolean);
  const hasReviewConversationCloseout = reviewConversationCloseoutLines.length > 0;
  const hasMeaningfulReviewConversationCloseout = reviewConversationCloseoutLines.some(
    (line) => !isPlaceholderLine(line) && /[A-Za-z0-9\u4e00-\u9fff]/.test(line),
  );

  return {
    autonomousDetected,
    hasDelegationExecutionLog,
    hasReviewConversationCloseout,
    hasMeaningfulReviewConversationCloseout,
  };
};

test("Autonomous delegation gate ships root templates and workflow body checks", () => {
  const prTemplate = readRepoFile(".github/PULL_REQUEST_TEMPLATE.md");
  const issueTemplate = readRepoFile(".github/ISSUE_TEMPLATE/codex-task.yml");
  const issueConfig = readRepoFile(".github/ISSUE_TEMPLATE/config.yml");
  const workflow = readWorkflow("pr-scope-police.yml");

  assert.match(prTemplate, /Source of truth/);
  assert.match(prTemplate, /Depends on PR/);
  assert.match(prTemplate, /本 PR 明確不做/);
  assert.match(prTemplate, /Delegation Execution Log/);
  assert.match(prTemplate, /Validation/);

  assert.match(issueTemplate, /Worker profile/);
  assert.match(issueTemplate, /Task/);
  assert.match(issueTemplate, /Model strength/);
  assert.match(issueTemplate, /Evidence \/ verification/);
  assert.match(issueTemplate, /Trivial\/self-only exception reason/);
  assert.match(issueConfig, /blank_issues_enabled:\s*false/);

  assert.match(workflow, /const autonomousLabels = new Set\(\['codex', 'codex-automation', 'auto-ready'\]\)/);
  assert.match(workflow, /const bodyForAutonomousGate = body\.replace\(\/<!--\[\\s\\S\]\*\?-->\//);
  assert.match(workflow, /hasDelegationExecutionLog/);
  assert.match(workflow, /hasWorkerProfileMention/);
  assert.match(workflow, /hasTrivialExceptionReason/);
  assert.match(workflow, /Review conversation closeout/);
  assert.match(workflow, /hasMeaningfulReviewConversationCloseout/);
  assert.ok(workflow.includes("Self-review\\s*\\/\\s*exception reason"));
  assert.match(workflow, /Scope checks bypassed by scope-exception label; autonomous delegation gate still enforced\./);
  assert.doesNotMatch(workflow, /Scope police bypassed by scope-exception label\.'\)\n\s+return/);
  assert.match(workflow, /Autonomous PRs must include a `Delegation Execution Log` section\./);
  assert.match(workflow, /Autonomous PRs must name at least one worker profile or give an explicit trivial\/self-only exception reason\./);
  assert.match(workflow, /Autonomous PRs must include a meaningful `Review conversation closeout` field\./);
  assert.match(workflow, /scope-exception/);
});

test("PR scope police keeps Tachiya title, body, and size gates", () => {
  const workflow = readWorkflow("pr-scope-police.yml");

  assert.match(workflow, /branches:\s*\[develop,\s*master\]/);
  assert.match(workflow, /const allowedPrefixes = \['\[backend\]', '\[frontend\]', '\[discussion\]'\]/);
  assert.match(workflow, /const hardMaxChangedFiles = 35/);
  assert.match(workflow, /const hardMaxDiffLines = 1000/);
  assert.match(workflow, /Source of truth/);
  assert.match(workflow, /Depends on PR/);
  assert.match(workflow, /本 PR 明確不做/);
  assert.match(workflow, /scope-exception/);
});

test("Autonomous PR closeout gate treats template bullets as meaningful only when filled", () => {
  const autonomousMissingCloseout = `
## Delegation Execution Log
- Actual worker profile(s):
  - controller
- Task:
  - review policy gate
- Review conversation closeout:
  - n/a
## Validation
- node --test .github/workflow-tests/ci-policy.test.mjs
`;
  const autonomousFilledCloseout = `
## Delegation Execution Log
- Actual worker profile(s):
  - controller
- Task:
  - review policy gate
- Review conversation closeout:
  - 已完成 closeout；已回覆 CodeRabbit 與 reviewer thread，並確認 resolve 紀錄可讀回
## Validation
- node --test .github/workflow-tests/ci-policy.test.mjs
`;
  const humanMissingCloseout = `
## Notes for Review
- This is a human-authored change.
## Validation
- node --test .github/workflow-tests/ci-policy.test.mjs
`;
  const autonomousScopeExceptionMissingCloseout = `
## Delegation Execution Log
- Actual worker profile(s):
  - controller
- Task:
  - review policy gate
- Review conversation closeout:
  - 無
## Validation
- node --test .github/workflow-tests/ci-policy.test.mjs
`;

  assert.deepEqual(evaluateAutonomousCloseoutGate({ body: autonomousMissingCloseout, labels: ["codex"] }), {
    autonomousDetected: true,
    hasDelegationExecutionLog: true,
    hasReviewConversationCloseout: true,
    hasMeaningfulReviewConversationCloseout: false,
  });
  assert.deepEqual(evaluateAutonomousCloseoutGate({ body: autonomousFilledCloseout, labels: ["auto-ready"] }), {
    autonomousDetected: true,
    hasDelegationExecutionLog: true,
    hasReviewConversationCloseout: true,
    hasMeaningfulReviewConversationCloseout: true,
  });
  assert.deepEqual(evaluateAutonomousCloseoutGate({ body: humanMissingCloseout, labels: [] }), {
    autonomousDetected: false,
    hasDelegationExecutionLog: false,
    hasReviewConversationCloseout: false,
    hasMeaningfulReviewConversationCloseout: false,
  });
  assert.deepEqual(
    evaluateAutonomousCloseoutGate({
      body: autonomousScopeExceptionMissingCloseout,
      labels: ["codex", "scope-exception"],
    }),
    {
      autonomousDetected: true,
      hasDelegationExecutionLog: true,
      hasReviewConversationCloseout: true,
      hasMeaningfulReviewConversationCloseout: false,
    },
  );
  assert.deepEqual(
    evaluateAutonomousCloseoutGate({
      body: `
## Delegation Execution Log
- Actual worker profile(s):
  - controller
- Review conversation closeout:
  - n/a
`,
      labels: ["codex-automation"],
    }),
    {
      autonomousDetected: true,
      hasDelegationExecutionLog: true,
      hasReviewConversationCloseout: true,
      hasMeaningfulReviewConversationCloseout: false,
    },
  );
});

test("Dependabot auto-merge policy stays narrow", () => {
  const workflow = readWorkflow("dependabot-automerge.yml");

  assert.match(workflow, /github\.actor == 'dependabot\[bot\]'/);
  assert.match(workflow, /safe-to-automerge/);
  assert.match(workflow, /security update/);
  assert.match(workflow, /production dependency requires manual review/);
  assert.match(workflow, /typescript update requires manual review/);
  assert.match(workflow, /@types\/\* update requires manual review/);
  assert.match(workflow, /vite update requires manual review/);
  assert.match(workflow, /react runtime update requires manual review/);
  assert.match(workflow, /eslint\/tooling update requires manual review/);
  assert.match(workflow, /safe devDependency patch\/minor update/);
});

test("develop merge issue closer only closes explicit same-repo references", () => {
  const workflow = readWorkflow("close-issue-on-develop-merge.yml");

  assert.match(workflow, /branches:\s*\[develop\]/);
  assert.match(workflow, /github\.event\.pull_request\.merged == true/);
  assert.match(workflow, /sameRepoPrefix/);
  assert.match(workflow, /stripIgnoredMarkdown/);
  assert.match(workflow, /last PR commit message/);
  assert.match(workflow, /state_reason: 'completed'/);
  assert.doesNotMatch(workflow, /pull_request_target/);
});

test("API CI keeps lint, timeout, and compile-scope hardening", () => {
  const workflow = readWorkflow("api-ci.yml");

  assert.match(workflow, /api-lint:/);
  assert.match(workflow, /name: API lint/);
  assert.match(workflow, /uv run --group dev ruff check \./);
  assert.match(workflow, /uv run --group dev ruff format --check config\.py database\.py main\.py security\.py migrations models routers services tests/);
  assert.match(workflow, /timeout-minutes: 5/);
  assert.match(workflow, /timeout-minutes: 10/);
  assert.match(workflow, /timeout-minutes: 20/);
  assert.match(workflow, /python -m compileall config\.py database\.py main\.py security\.py models routers services tests/);
  assert.doesNotMatch(workflow, /python -m compileall \./);
  assert.doesNotMatch(workflow, /weekly-release-pr\.yml/);
});

test("cross-repo contract gate owns Storefront drift checks without duplicating Storefront CI", () => {
  const workflow = readWorkflow("cross-repo-contract.yml");

  assert.match(workflow, /repository: nurockplayer\/storefront/);
  assert.match(workflow, /ref: develop/);
  assert.match(workflow, /REQUIRE_STOREFRONT_CONTRACT: "1"/);
  assert.match(workflow, /node --test \.github\/workflow-tests\/cross-repo-contract\.test\.mjs/);
  assert.match(workflow, /timeout-minutes: 10/);
  assert.doesNotMatch(workflow, /pnpm install/);
  assert.doesNotMatch(workflow, /pnpm (run )?build/);
});

test("PostgreSQL migration gate stays path-filtered and secret-free", () => {
  const workflow = readWorkflow("postgres-migration-gate.yml");

  assert.match(workflow, /workflow_dispatch:/);
  assert.match(workflow, /schedule:/);
  assert.match(workflow, /pull_request:/);
  assert.match(workflow, /push:/);
  assert.match(workflow, /api\/migrations\/\*\*/);
  assert.match(workflow, /api\/models\/\*\*/);
  assert.match(workflow, /services:\s+postgres:/);
  assert.match(workflow, /image: postgres:16/);
  assert.match(workflow, /timeout-minutes: 10/);
  assert.match(workflow, /working-directory: api/);
  assert.match(workflow, /DATABASE_URL: postgresql:\/\/tachiya:tachiya@localhost:5432\/tachiya/);
  assert.match(workflow, /uv run --group dev alembic upgrade head/);
  assert.doesNotMatch(workflow, /secrets\./);
  assert.doesNotMatch(workflow, /production/i);
});
