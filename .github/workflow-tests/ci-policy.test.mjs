import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const readWorkflow = (name) => readFileSync(new URL(`../workflows/${name}`, import.meta.url), "utf8");
const readRepoFile = (relativePath) => readFileSync(new URL(`../../${relativePath}`, import.meta.url), "utf8");
const extractWorkflowSection = (workflow, startMarker, endMarker) => {
  const start = workflow.indexOf(startMarker);
  assert.notEqual(start, -1, `${startMarker} section missing`);
  const end = workflow.indexOf(endMarker, start + startMarker.length);
  assert.notEqual(end, -1, `${endMarker} section missing`);
  return workflow.slice(start, end);
};
const makePrBody = ({ delegationRows = [], sections = ["## Validation\n- node --test .github/workflow-tests/ci-policy.test.mjs"] }) => {
  const delegationSection =
    delegationRows.length === 0
      ? ""
      : `## Delegation Execution Log\n${delegationRows
          .map(
            ({ label, value }) =>
              `- ${label}:\n${value
                .split("\n")
                .map((line) => `  - ${line}`)
                .join("\n")}`,
          )
          .join("\n")}`;
  return [delegationSection, ...sections].filter(Boolean).join("\n");
};

const buildGateExpected = (overrides = {}) =>
  ({
    autonomousDetected: false,
    hasDelegationExecutionLog: false,
    hasMeaningfulDelegationExecutionLog: false,
    hasTrivialExceptionReason: false,
    hasOpsSparkMention: false,
    hasRoutineOpsWork: false,
    hasSpawnDirective: false,
    hasSpawnModel: false,
    hasSpawnReasoning: false,
    hasSpawnControllerFallback: false,
    hasSpawnDirectiveWithModelReasoning: false,
    hasSpawnAllowedWithoutReason: false,
    hasRoutineOpsDelegationWarning: false,
    hasControllerFallbackReasonField: false,
    hasMeaningfulControllerFallbackReason: false,
    hasSpecGateEvidence: false,
    hasMeaningfulSpecGateEvidence: false,
    hasFinalMergeGate: false,
    hasMeaningfulFinalMergeGate: false,
    hasFinalMergeGateRequiredKeys: false,
    finalMergeGateReadyFlag: "absent",
    finalMergeGateHasExplicitPendingInitialGate: false,
    finalMergeGateReadyWithResolvedThreadsOnly: false,
    hasReviewConversationCloseout: false,
    hasMeaningfulReviewConversationCloseout: false,
    ...withSpawnDefaults({}),
    ...overrides,
  });

const assertGate = (name, body, labels, expectedOverrides) => {
  assert.deepEqual(evaluateAutonomousCloseoutGate({ body, labels }), buildGateExpected(expectedOverrides), name);
};

const stripTemplateComments = (body) => body.replace(/<!--[\s\S]*?-->/g, "");

const evaluateScopeBudget = ({ filenames = [], diffLines = 0, labels = [] }) => {
  const bypassed = labels.includes("scope-exception");
  const hardMaxChangedFiles = 35;
  const warningDiffLines = 600;
  const hardMaxDiffLines = 1000;
  const failures = [];
  const warnings = [];

  if (!bypassed && filenames.length > hardMaxChangedFiles) {
    failures.push(`PR changes ${filenames.length} files, which exceeds the hard limit of ${hardMaxChangedFiles}.`);
  }

  if (!bypassed && diffLines > hardMaxDiffLines) {
    failures.push(`PR diff size is ${diffLines} lines (+/-), which exceeds the hard limit of ${hardMaxDiffLines}.`);
  } else if (!bypassed && diffLines > warningDiffLines) {
    warnings.push(`PR diff size is ${diffLines} lines (+/-), which exceeds the soft limit of ${warningDiffLines}.`);
  }

  return { failures, warnings };
};

const evaluateAutonomousCloseoutGate = ({ body, labels = [] }) => {
  const bodyForAutonomousGate = stripTemplateComments(body);
  const normalizedLabels = labels.map((label) => (label || "").toLowerCase());
  const autonomousLabels = new Set(["codex", "codex-automation", "auto-ready"]);
  const hasAutonomousLabel = normalizedLabels.some((label) => autonomousLabels.has(label));
  const hasDelegationExecutionLog = /(?:^|\n)\s*(?:#{1,6}\s*)?Delegation Execution Log\b/i.test(bodyForAutonomousGate);
  const extractSectionBody = (label) => {
    const pattern = new RegExp(
      `(?:^|\\n)\\s*(?:-\\s*)?(?:#{1,6}\\s*)?${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*[：:]\\s*([\\s\\S]*?)(?=\\n\\s*##\\s|\\n*$)`,
      "i",
    );
    const match = bodyForAutonomousGate.match(pattern);
    return match?.[1] ?? "";
  };
  const extractDelegationFieldBody = (label) => {
    const delegatedLabels = [
      "Source issue delegation plan",
      "Actual worker profile(s)",
      "Task",
      "Model strength",
      "Spawn directive",
      "Controller fallback reason",
      "Trivial/self-only exception reason",
      "Evidence / verification",
      "Spec gate evidence",
      "Final merge gate",
      "Worker session closeout",
      "Workflow friction / follow-up split",
      "Review conversation closeout",
    ];
    const pattern = new RegExp(
      `(?:^|\\n)\\s*-\\s*${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*[：:]\\s*([\\s\\S]*?)(?=\\n\\s*-\\s*(?:${delegatedLabels
        .map((value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        .join("|")})\\s*[：:]|\\n\\s*##\\s|\\n*$)`,
      "i",
    );
    const match = bodyForAutonomousGate.match(pattern);
    return match?.[1] ?? "";
  };
  const extractSpawnDirectives = () => {
    const spawnFieldPattern = /(?:^|\n)[^\S\n]*-[^\S\n]*(?:Spawn directive|spawn)[^\S\n]*[：:][^\S\n]*([^\n]+)/gi;
    const spawnValuePattern = (key, line) => {
      const pattern = new RegExp(`${key}\\s*[=:]\\s*([^\\s]+)`, "i");
      const match = line.match(pattern);
      return match?.[1]?.trim() ?? "";
    };
    const spawnFallbackReasonPattern = (line) => {
      const pattern = /fallback_reason\s*[=:]\s*(.+)/i;
      const match = line.match(pattern);
      return match?.[1]?.trim() ?? "";
    };
    const parseSpawn = (line) => {
      const trimmed = line.trim();
      const profileMatch = trimmed.match(/^\s*profile\s*[=:]\s*([A-Za-z0-9_]+)\s/i);
      const profile = profileMatch?.[1] ?? trimmed.split(/\s+/)[0];
      const model = spawnValuePattern("model", trimmed);
      const reasoning = spawnValuePattern("reasoning", trimmed);
      const controllerFallback = spawnValuePattern("controller_fallback", trimmed);
      const fallbackReason = spawnFallbackReasonPattern(trimmed);
      return { line: trimmed, profile, model, reasoning, controllerFallback, fallbackReason };
    };
    return [...bodyForAutonomousGate.matchAll(spawnFieldPattern)].map((match) => parseSpawn(match[1] || ""));
  };
  const normalizeLine = (line) =>
    line
      .replace(/^\s*[-*]\s*/, "")
      .replace(/^[`"'“”‘’]+|[`"'“”‘’]+$/g, "")
      .replace(/[.,。:：;；!?！？]+$/g, "")
      .trim();
  const normalizePlaceholderValue = (value) => value.trim().replace(/[.,。:：;；!?！？]+$/g, "").toLowerCase();

  const placeholderValues = new Set([
    "n/a",
    "none",
    "無",
    "不適用",
    "na",
    "n.a",
    "tbd",
    "todo",
    "pending",
    "-",
    "—",
    "待定",
    "尚未",
    "略",
    "略過",
    "待補",
  ]);
  const isPlaceholderLine = (line) => placeholderValues.has(normalizePlaceholderValue(line));
  const hasMeaningfulLine = (line) => !isPlaceholderLine(line) && /[A-Za-z0-9\u4e00-\u9fff]/.test(line);
  const extractMeaningfulFieldLines = (label) =>
    extractDelegationFieldBody(label)
      .split("\n")
      .map(normalizeLine)
      .filter(Boolean);
  const hasMeaningfulDelegationField = (label) => extractMeaningfulFieldLines(label).some((line) => hasMeaningfulLine(line));
  const pendingInitialGatePattern =
    /\b(?:pending|awaiting)\s+(?:initial|first)\s+(?:spec|merge|review|ci|gate|readback)\b|\binitial gate pending\b|待(?:補|跑|初次|首次).{0,8}(?:gate|讀回|驗證|證據)/i;
  const isExplicitPendingInitialGate = (value) => pendingInitialGatePattern.test(value);
  const parseKeyValueLines = (lines) =>
    Object.fromEntries(
      lines
        .map((line) => {
          const match = line.match(/^([A-Za-z0-9_.-]+)\s*[=:]\s*(.+)$/);
          if (!match) return null;
          return [match[1].trim().toLowerCase(), match[2].trim()];
        })
        .filter(Boolean),
    );
  const trivialExceptionMatch = bodyForAutonomousGate.match(
    /(?:^|\n)\s*(?:#{1,6}\s*)?(?:Trivial(?:\s*\/\s*self-only)? exception reason|Self-only exception reason|Self-review\s*\/\s*exception reason)\s*[：:]\s*(.+)/i,
  );
  const trivialExceptionReason = trivialExceptionMatch?.[1]?.trim();
  const hasMeaningfulTrivialExceptionField = hasMeaningfulDelegationField("Trivial/self-only exception reason");
  const hasTrivialExceptionReason =
    hasMeaningfulTrivialExceptionField ||
    (Boolean(trivialExceptionReason) && !placeholderValues.has(normalizePlaceholderValue(normalizeLine(trivialExceptionReason))));
  const delegationExecutionLogLabels = [
    "Source issue delegation plan",
    "Actual worker profile(s)",
    "Task",
    "Model strength",
    "Spawn directive",
    "Controller fallback reason",
    "Spec gate evidence",
    "Final merge gate",
    "Trivial/self-only exception reason",
  ];
  const hasMeaningfulDelegationExecutionLog = delegationExecutionLogLabels.some((label) => hasMeaningfulDelegationField(label));
  const spawnDirectives = extractSpawnDirectives();
  const hasSpawnDirective = spawnDirectives.length > 0;
  const hasSpawnModel = spawnDirectives.some((spawn) => spawn.model && !isPlaceholderLine(spawn.model));
  const hasSpawnReasoning = spawnDirectives.some((spawn) => spawn.reasoning && !isPlaceholderLine(spawn.reasoning));
  const hasSpawnControllerFallback = spawnDirectives.some((spawn) =>
    ["not_allowed", "allowed"].includes(normalizePlaceholderValue(spawn.controllerFallback)),
  );
  const hasSpawnAllowedWithoutReason = spawnDirectives.some(
    (spawn) =>
      normalizePlaceholderValue(spawn.controllerFallback) === "allowed" &&
      (!spawn.fallbackReason || isPlaceholderLine(spawn.fallbackReason)),
  );
  const hasSpawnDirectiveWithModelReasoning = spawnDirectives.length > 0 && spawnDirectives.every(
    (spawn) =>
      spawn.model &&
      !isPlaceholderLine(spawn.model) &&
      spawn.reasoning &&
      !isPlaceholderLine(spawn.reasoning) &&
      ["not_allowed", "allowed"].includes(normalizePlaceholderValue(spawn.controllerFallback)) &&
      (!/\bops_spark\b/i.test(spawn.line) || normalizePlaceholderValue(spawn.model) === "gpt-5.3-codex-spark"),
  );
  const autonomousDetected = hasAutonomousLabel || hasMeaningfulDelegationExecutionLog;
  const hasOpsSparkMention = bodyForAutonomousGate.toLowerCase().includes("ops_spark");
  const routineOpsKeywords = [
    "readback",
    "ci status",
    "check status",
    "review closeout",
    "review conversation closeout",
    "closeout evidence",
    "commit",
    "push",
    "pre-commit",
    "post-push",
    "head sha",
    "branch",
    "pr body",
    "pr comment",
    "issue comment",
    "thread",
    "resolve",
    "resolved",
    "讀回",
    "狀態讀回",
    "留言",
    "證據",
    "收斂",
    "關閉對話",
  ];
  const hasRoutineOpsWork = routineOpsKeywords.some((keyword) =>
    bodyForAutonomousGate.toLowerCase().includes(keyword.toLowerCase()),
  );
  const hasRoutineOpsDelegationWarning = autonomousDetected && hasRoutineOpsWork && !hasOpsSparkMention && !hasTrivialExceptionReason;
  const controllerFallbackReasonLines = extractMeaningfulFieldLines("Controller fallback reason");
  const hasControllerFallbackReasonField = controllerFallbackReasonLines.length > 0;
  const hasMeaningfulControllerFallbackReason = controllerFallbackReasonLines.some((line) => hasMeaningfulLine(line));
  const specGateEvidenceLines = extractMeaningfulFieldLines("Spec gate evidence");
  const hasSpecGateEvidence = specGateEvidenceLines.length > 0;
  const hasMeaningfulSpecGateEvidence =
    specGateEvidenceLines.some((line) => hasMeaningfulLine(line)) &&
    specGateEvidenceLines.some((line) => hasMeaningfulLine(line) || isExplicitPendingInitialGate(line));
  const finalMergeGateLines = extractMeaningfulFieldLines("Final merge gate");
  const hasFinalMergeGate = finalMergeGateLines.length > 0;
  const finalMergeGateHasExplicitPendingInitialGate = finalMergeGateLines.some((line) => isExplicitPendingInitialGate(line));
  const finalMergeGateKeyValues = parseKeyValueLines(finalMergeGateLines);
  const finalMergeGateRequiredKeys = [
    "latest_head_sha",
    "unresolved_thread_count",
    "spec_gate_status",
    "evidence_urls",
  ];
  const hasFinalMergeGateRequiredKeys = finalMergeGateRequiredKeys.every((key) => {
    const value = finalMergeGateKeyValues[key];
    return Boolean(value) && (hasMeaningfulLine(value) || isExplicitPendingInitialGate(value));
  });
  const readyValue = finalMergeGateKeyValues.ready_to_merge ?? finalMergeGateKeyValues.merge_ready ?? "";
  const finalMergeGateReadyFlag =
    !readyValue ? "absent" : /^true$/i.test(readyValue) ? "true" : /^false$/i.test(readyValue) ? "false" : "other";
  const unresolvedThreadCountValue = finalMergeGateKeyValues.unresolved_thread_count ?? "";
  const finalMergeGateReadyWithResolvedThreadsOnly =
    finalMergeGateReadyFlag !== "true" ||
    (/^0$/i.test(unresolvedThreadCountValue) && !finalMergeGateHasExplicitPendingInitialGate);
  const hasMeaningfulFinalMergeGate =
    finalMergeGateLines.some((line) => hasMeaningfulLine(line)) &&
    (finalMergeGateHasExplicitPendingInitialGate || hasFinalMergeGateRequiredKeys) &&
    finalMergeGateReadyWithResolvedThreadsOnly;
  const reviewConversationCloseoutLines = extractDelegationFieldBody("Review conversation closeout")
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
    hasMeaningfulDelegationExecutionLog,
    hasTrivialExceptionReason,
    hasOpsSparkMention,
    hasRoutineOpsWork,
    hasSpawnDirective,
    hasSpawnModel,
    hasSpawnReasoning,
    hasSpawnControllerFallback,
    hasSpawnDirectiveWithModelReasoning,
    hasSpawnAllowedWithoutReason,
    hasRoutineOpsDelegationWarning,
    hasControllerFallbackReasonField,
    hasMeaningfulControllerFallbackReason,
    hasSpecGateEvidence,
    hasMeaningfulSpecGateEvidence,
    hasFinalMergeGate,
    hasMeaningfulFinalMergeGate,
    hasFinalMergeGateRequiredKeys,
    finalMergeGateReadyFlag,
    finalMergeGateHasExplicitPendingInitialGate,
    finalMergeGateReadyWithResolvedThreadsOnly,
    hasReviewConversationCloseout,
    hasMeaningfulReviewConversationCloseout,
  };
};

const withSpawnDefaults = (values = {}) => ({
  hasSpawnDirective: false,
  hasSpawnModel: false,
  hasSpawnReasoning: false,
  hasSpawnControllerFallback: false,
  hasSpawnDirectiveWithModelReasoning: false,
  hasSpawnAllowedWithoutReason: false,
  ...values,
});

test("Autonomous delegation gate ships root templates and workflow body checks", () => {
  const prTemplate = readRepoFile(".github/PULL_REQUEST_TEMPLATE.md");
  const issueTemplate = readRepoFile(".github/ISSUE_TEMPLATE/codex-task.yml");
  const issueConfig = readRepoFile(".github/ISSUE_TEMPLATE/config.yml");
  const workflow = readWorkflow("pr-scope-police.yml");

  for (const pattern of [/Source of truth/, /Depends on PR/, /本 PR 明確不做/, /Delegation Execution Log/, /Spawn directive/, /model=/, /reasoning=/, /controller_fallback=/, /Validation/]) {
    assert.match(prTemplate, pattern);
  }
  assert.equal(evaluateAutonomousCloseoutGate({ body: prTemplate, labels: [] }).hasSpawnDirective, false);

  assert.match(issueTemplate, /Worker profile/);
  assert.match(issueTemplate, /controller_fallback/);
  assert.match(issueTemplate, /gpt-5\.3-codex-spark/);
  assert.match(issueTemplate, /Task/);
  assert.match(issueTemplate, /Model strength/);
  assert.match(issueTemplate, /Evidence \/ verification/);
  assert.match(issueTemplate, /Trivial\/self-only exception reason/);
  assert.match(issueConfig, /blank_issues_enabled:\s*false/);

  assert.match(workflow, /const autonomousLabels = new Set\(\['codex', 'codex-automation', 'auto-ready'\]\)/);
  assert.match(workflow, /const bodyForAutonomousGate = body\.replace\(\/<!--\[\\s\\S\]\*\?-->\//);
  assert.match(workflow, /const extractDelegationFieldBody = \(label\) =>/);
  assert.match(workflow, /hasDelegationExecutionLog/);
  assert.match(workflow, /Controller fallback reason/);
  assert.match(workflow, /Spec gate evidence/);
  assert.match(workflow, /Final merge gate/);
  assert.match(workflow, /Worker session closeout/);
  assert.match(workflow, /Workflow friction \/ follow-up split/);
  assert.match(workflow, /hasMeaningfulDelegationExecutionLog/);
  assert.match(workflow, /hasWorkerProfileMention/);
  assert.match(workflow, /const hasOpsSparkMention = bodyForAutonomousGate\.toLowerCase\(\)\.includes\('ops_spark'\)/);
  assert.match(workflow, /const routineOpsKeywords = \[/);
  assert.match(workflow, /hasRoutineOpsWork && !hasOpsSparkMention && !hasTrivialExceptionReason/);
  assert.match(workflow, /const hasMeaningfulTrivialExceptionField = hasMeaningfulDelegationField\('Trivial\/self-only exception reason'\)/);
  assert.match(workflow, /Routine ops delegation hint: \$\{hasRoutineOpsWork && !hasOpsSparkMention && !hasTrivialExceptionReason \? 'missing ops_spark' : 'ok'\}/);
  assert.match(workflow, /spawnDirectives\.length > 0 &&/);
  assert.match(workflow, /spawnDirectives\.every\(/);
  assert.match(workflow, /gpt-5\.3-codex-spark/);
  assert.match(workflow, /isPlaceholderCloseoutLine\(spawn\.fallbackReason\)/);
  assert.doesNotMatch(workflow, /isPlaceholderLine\(spawn\.fallbackReason\)/);
  assert.match(workflow, /hasTrivialExceptionReason/);
  assert.match(workflow, /const normalizePlaceholderValue = \(value\) =>/);
  assert.match(workflow, /pending initial gate/i);
  assert.match(workflow, /latest_head_sha/);
  assert.match(workflow, /unresolved_thread_count/);
  assert.match(workflow, /spec_gate_status/);
  assert.match(workflow, /evidence_urls/);
  assert.match(workflow, /ready_to_merge/);
  assert.match(workflow, /merge_ready/);
  assert.match(workflow, /- Controller fallback reason: \$\{.+\}/);
  assert.match(workflow, /- Spec gate evidence: \$\{.+\}/);
  assert.match(workflow, /- Final merge gate: \$\{.+\}/);
  assert.match(workflow, /- Review conversation closeout present: \$\{hasReviewConversationCloseout \? 'yes' : 'no'\}/);
  assert.match(workflow, /- Review conversation closeout meaningful: \$\{hasMeaningfulReviewConversationCloseout \? 'yes' : 'no'\}/);
  assert.match(workflow, /hasMeaningfulReviewConversationCloseout/);
  assert.match(workflow, /const reviewConversationCloseoutBody = extractDelegationFieldBody\('Review conversation closeout'\)/);
  assert.match(workflow, /const placeholderValues = new Set\(\[/);
  assert.match(workflow, /placeholderValues\.has\(normalizePlaceholderValue\(normalizeSectionLine\(trivialExceptionReason\)\)\)/);
  assert.ok(workflow.includes("Self-review\\s*\\/\\s*exception reason"));
  assert.match(workflow, /Scope checks bypassed by scope-exception label; autonomous delegation gate still enforced\./);
  assert.doesNotMatch(workflow, /Scope police bypassed by scope-exception label\.'\)\n\s+return/);
  assert.match(workflow, /Autonomous PRs must include a `Delegation Execution Log` section\./);
  assert.match(workflow, /Autonomous PRs must name at least one worker profile or give an explicit trivial\/self-only exception reason\./);
  assert.match(workflow, /Autonomous PRs must include a meaningful `Spec gate evidence` field\./);
  assert.match(workflow, /Autonomous PRs must include a meaningful `Final merge gate` field\./);
  assert.match(workflow, /Autonomous PRs with `ready_to_merge=true` or `merge_ready=true` must set `unresolved_thread_count=0` and remove pending initial gate placeholders\./);
  assert.match(workflow, /Autonomous PRs must include a meaningful `Review conversation closeout` field\./);
  assert.match(workflow, /Autonomous PRs with routine readback\/comment\/closeout or commit-push checklist work should delegate that slice to `ops_spark`/);
  assert.match(workflow, /'commit'/);
  assert.match(workflow, /'push'/);
  assert.match(workflow, /'pre-commit'/);
  assert.match(workflow, /'post-push'/);
  assert.match(workflow, /'head sha'/);
  assert.match(workflow, /'branch'/);
  assert.match(workflow, /scope-exception/);
  assert.match(prTemplate, /Worker session closeout/);
  assert.match(prTemplate, /Workflow friction \/ follow-up split/);
  assert.match(prTemplate, /latest_head_sha/);
  assert.match(prTemplate, /ci_check_summary/);
  assert.match(prTemplate, /coderabbit_status/);
  assert.match(prTemplate, /codex_connector_status/);
  assert.match(prTemplate, /unresolved_thread_count/);
  assert.match(prTemplate, /finding_disposition/);
  assert.match(prTemplate, /evidence_urls/);
  assert.match(prTemplate, /新的 PR edited\/labeled event/);
  assert.match(prTemplate, /不要只 rerun 舊 payload/);
  assert.match(prTemplate, /約 40% infra 複雜 \/ 約 60% 工作流摩擦/);
  assert.match(prTemplate, /Spawn directive 必須填在欄位同一行/);
  assert.doesNotMatch(
    prTemplate,
    /- Spawn directive:\n\s+- <!--/,
    "PR template must not put spawn directive examples on a nested bullet that the scope-police parser cannot read",
  );
  assert.equal(evaluateAutonomousCloseoutGate({ body: prTemplate, labels: [] }).hasSpawnDirective, false);
});

test("Autonomous workflow docs cover routing, closeout, lifecycle, and follow-up policies", () => {
  const workflowDocs = readRepoFile("docs/codex-autonomous-workflow.md");
  const agents = readRepoFile("AGENTS.md");
  const claude = readRepoFile("CLAUDE.md");

  for (const pattern of [
    /## Cost Model 與摩擦預算/,
    /## Subagent Lifecycle 與 Thread-limit Cleanup/,
    /## Issue-first 與 Follow-up Split Policy/,
    /## PR Template 與 Policy-test Hardening/,
    /## Autonomous Review Closeout Evidence Runbook/,
    /### Review Closeout Evidence Matrix/,
    /### Metadata rerun 規則/,
    /ops_spark Routing Hardening/,
    /約 40% 時間消耗來自 infra 本質複雜，約 60% 來自工作流自己製造摩擦/,
    /latest_head_sha/,
    /ci_check_summary/,
    /coderabbit_status/,
    /codex_connector_status/,
    /unresolved_thread_count/,
    /finding_disposition/,
    /evidence_urls/,
    /reviewThreads\(first:50,\s*after:\s*\$cursor\)/,
    /hasNextPage/,
    /endCursor/,
    /hasNextPage == false/,
    /endCursor.*cursor/,
    /不要只 rerun 舊的 failed workflow run/,
    /舊 run 可能重用舊 event payload/,
    /evidence_url/,
    /state_snapshot/,
    /blockage_reason/,
    /next_action/,
    /readback_at/,
    /green.*可用 worker slots >= 2/,
    /yellow.*只剩 1 個可用 worker slot/,
    /red.*無可用 worker slot/,
    /worker unavailable/,
    /follow-up issue/,
    /closeout comment 至少要列出 latest head SHA/,
  ]) {
    assert.match(workflowDocs, pattern);
  }

  assert.match(agents, /約 40% infra 本質複雜、約 60% 工作流自己製造摩擦/);
  assert.match(agents, /Autonomous Review Closeout Evidence Runbook/);
  assert.match(claude, /約 40% infra 本質複雜、約 60% 工作流自己製造摩擦/);
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

test("PR scope police scope budget has warning, hard-fail, and bypass examples", () => {
  const workflow = readWorkflow("pr-scope-police.yml");

  assert.match(workflow, /const hardMaxChangedFiles = 35/);
  assert.match(workflow, /const warningDiffLines = 600/);
  assert.match(workflow, /const hardMaxDiffLines = 1000/);
  assert.match(workflow, /PR changes \$\{filenames\.length\} files, which exceeds the hard limit/);
  assert.match(workflow, /PR diff size is \$\{diffLines\} lines \(\+\/-\), which exceeds the soft limit/);
  assert.match(workflow, /PR diff size is \$\{diffLines\} lines \(\+\/-\), which exceeds the hard limit/);

  assert.deepEqual(evaluateScopeBudget({ filenames: Array.from({ length: 35 }, (_, index) => `docs/${index}.md`), diffLines: 600 }), {
    failures: [],
    warnings: [],
  });
  assert.deepEqual(evaluateScopeBudget({ filenames: ["docs/a.md"], diffLines: 601 }), {
    failures: [],
    warnings: ["PR diff size is 601 lines (+/-), which exceeds the soft limit of 600."],
  });
  assert.deepEqual(evaluateScopeBudget({ filenames: ["docs/a.md"], diffLines: 1001 }), {
    failures: ["PR diff size is 1001 lines (+/-), which exceeds the hard limit of 1000."],
    warnings: [],
  });
  assert.deepEqual(evaluateScopeBudget({ filenames: Array.from({ length: 36 }, (_, index) => `docs/${index}.md`), diffLines: 10 }), {
    failures: ["PR changes 36 files, which exceeds the hard limit of 35."],
    warnings: [],
  });
  assert.deepEqual(
    evaluateScopeBudget({
      filenames: Array.from({ length: 40 }, (_, index) => `docs/${index}.md`),
      diffLines: 1200,
      labels: ["scope-exception"],
    }),
    {
      failures: [],
      warnings: [],
    },
  );
});

test("Autonomous PR closeout gate treats template bullets as meaningful only when filled", () => {
  const placeholderVariants = ["na", "n.a.", "tbd", "todo", "pending", "-", "—", "待定", "尚未", "略", "略過", "待補"];
  const toRows = (rows) => rows.map(([label, value]) => ({ label, value }));
  const normalizeRows = (rows = []) => {
    if (rows.length === 0) return [];
    if (Array.isArray(rows[0])) return toRows(rows);
    return rows;
  };
  const asPrBody = (rows = []) => makePrBody({ delegationRows: normalizeRows(rows) });
  const closeoutBaseTemplateRows = [
    ["Source issue delegation plan", "n/a"],
    ["Actual worker profile(s)", "n/a"],
    ["Task", "n/a"],
    ["Model strength", "n/a"],
    ["Trivial/self-only exception reason", "n/a"],
    ["Evidence / verification", "n/a"],
    ["Review conversation closeout", "n/a"],
  ];
  const closeoutExpectedBase = {
    hasDelegationExecutionLog: true,
    hasMeaningfulDelegationExecutionLog: false,
    hasTrivialExceptionReason: false,
    hasOpsSparkMention: false,
    hasRoutineOpsWork: true,
    hasRoutineOpsDelegationWarning: false,
    hasControllerFallbackReasonField: false,
    hasMeaningfulControllerFallbackReason: false,
    hasSpecGateEvidence: false,
    hasMeaningfulSpecGateEvidence: false,
    hasFinalMergeGate: false,
    hasMeaningfulFinalMergeGate: false,
    hasFinalMergeGateRequiredKeys: false,
    finalMergeGateReadyFlag: "absent",
    finalMergeGateHasExplicitPendingInitialGate: false,
    finalMergeGateReadyWithResolvedThreadsOnly: true,
    hasReviewConversationCloseout: true,
    hasMeaningfulReviewConversationCloseout: false,
  };
  const closeoutExpectedAutonomous = {
    ...closeoutExpectedBase,
    autonomousDetected: true,
    hasMeaningfulDelegationExecutionLog: true,
    hasRoutineOpsDelegationWarning: true,
  };
  const placeholderRows = (closeoutValue, taskValue = "review policy gate", workerValue = "controller") => [
    ["Actual worker profile(s)", workerValue],
    ["Task", taskValue],
    ["Review conversation closeout", closeoutValue],
  ];
  const closeoutCases = [
    {
      name: "autonomous missing closeout is not meaningful",
      body: asPrBody(placeholderRows("n/a")),
      labels: ["codex"],
      expected: {
        ...closeoutExpectedAutonomous,
      },
    },
    {
      name: "autonomous meaningful closeout passes when review closeout filled",
      body: asPrBody(placeholderRows("已完成 closeout；已回覆 CodeRabbit 與 reviewer thread，並確認 resolve 紀錄可讀回")),
      labels: ["auto-ready"],
      expected: {
        ...closeoutExpectedAutonomous,
        hasMeaningfulReviewConversationCloseout: true,
      },
    },
    {
      name: "autonomous placeholder trivial exception reason is not meaningful",
      body: asPrBody([
        ["Actual worker profile(s)", "controller"],
        ["Task", "review policy gate"],
        ["Trivial/self-only exception reason", "tbd"],
        ["Review conversation closeout", "已完成 closeout；已回覆 CodeRabbit 與 reviewer thread，並確認 resolve 紀錄可讀回"],
      ]),
      labels: ["codex"],
      expected: {
        ...closeoutExpectedAutonomous,
        hasMeaningfulReviewConversationCloseout: true,
      },
    },
    {
      name: "template-only human closeout stays non-autonomous",
      body: asPrBody(toRows(closeoutBaseTemplateRows)),
      labels: [],
      expected: {
        ...closeoutExpectedBase,
      },
    },
    {
      name: "human meaningful closeout is allowed",
      body: asPrBody(
        [
          ...closeoutBaseTemplateRows.filter(([label]) => label !== "Review conversation closeout"),
          ["Review conversation closeout", "Not applicable - human-authored PR"],
        ].map(([label, value]) => ({ label, value })),
      ),
      labels: [],
      expected: {
        ...closeoutExpectedBase,
        hasMeaningfulReviewConversationCloseout: true,
      },
    },
    {
      name: "human evidence-only with placeholder delegation remains non-autonomous",
      body: asPrBody(
        [
          ...closeoutBaseTemplateRows.filter(
            ([label]) =>
              label !== "Trivial/self-only exception reason" &&
              label !== "Review conversation closeout" &&
              label !== "Evidence / verification",
          ),
          ["Evidence / verification", "pnpm test\nnode --test .github/workflow-tests/ci-policy.test.mjs"],
          ["Review conversation closeout", "n/a"],
        ].map(([label, value]) => ({ label, value })),
      ),
      labels: [],
      expected: {
        ...closeoutExpectedBase,
      },
    },
    ...placeholderVariants.map((placeholderVariant) => ({
      name: `placeholder variant ${placeholderVariant} should stay non-meaningful`,
      body: asPrBody(placeholderRows(placeholderVariant, placeholderVariant, placeholderVariant)),
      labels: [],
      expected: {
        ...closeoutExpectedBase,
      },
    })),
    {
      name: "real delegation content marks autonomous",
      body: asPrBody([
        ["Actual worker profile(s)", "pending reviewer reply, evidence attached in thread"],
        ["Task", "review policy gate"],
        ["Review conversation closeout", "follow-up evidence remains pending on the thread"],
      ]),
      labels: [],
      expected: {
        ...closeoutExpectedAutonomous,
        hasMeaningfulReviewConversationCloseout: true,
      },
    },
    {
      name: "human-only text without delegation log is not autonomous",
      body: makePrBody({
        delegationRows: [],
        sections: ["## Notes for Review\n- This is a human-authored change."],
      }),
      labels: [],
      expected: {
        autonomousDetected: false,
        hasDelegationExecutionLog: false,
        hasMeaningfulDelegationExecutionLog: false,
        hasTrivialExceptionReason: false,
        hasOpsSparkMention: false,
        hasRoutineOpsWork: false,
        hasRoutineOpsDelegationWarning: false,
        hasControllerFallbackReasonField: false,
        hasMeaningfulControllerFallbackReason: false,
        hasSpecGateEvidence: false,
        hasMeaningfulSpecGateEvidence: false,
        hasFinalMergeGate: false,
        hasMeaningfulFinalMergeGate: false,
        hasFinalMergeGateRequiredKeys: false,
        finalMergeGateReadyFlag: "absent",
        finalMergeGateHasExplicitPendingInitialGate: false,
        finalMergeGateReadyWithResolvedThreadsOnly: true,
        hasReviewConversationCloseout: false,
        hasMeaningfulReviewConversationCloseout: false,
      },
    },
    {
      name: "scope-exception still applies routine ops gating",
      body: asPrBody(placeholderRows("無")),
      labels: ["codex", "scope-exception"],
      expected: {
        ...closeoutExpectedAutonomous,
        hasMeaningfulReviewConversationCloseout: false,
      },
    },
    {
      name: "codex-automation label enforces autonomous detection",
      body: asPrBody([
        ["Actual worker profile(s)", "controller"],
        ["Review conversation closeout", "n/a"],
      ]),
      labels: ["codex-automation"],
      expected: {
        ...closeoutExpectedAutonomous,
        hasMeaningfulReviewConversationCloseout: false,
      },
    },
  ];

  for (const { name, body, labels, expected } of closeoutCases) {
    assertGate(name, body, labels, expected);
  }
});

test("Autonomous PR closeout gate enforces spawn model/reasoning rules", () => {
  const bodyWithSpawnDirective = ({
    profile = "ops_spark",
    task = "readback CI status and comment evidence",
    spawnDirective,
    spawnDirectives = spawnDirective ? [spawnDirective] : [],
  }) =>
    makePrBody({
      delegationRows: [
        { label: "Source issue delegation plan", value: profile === "backend_worker" ? "closeout only" : "closeout only" },
        { label: "Actual worker profile(s)", value: profile },
        { label: "Task", value: task },
        ...spawnDirectives.map((value) => ({ label: "Spawn directive", value })),
        { label: "Review conversation closeout", value: "已完成 closeout 並回補證據鏈" },
      ],
    });
  const spawnExpectedBase = {
    autonomousDetected: true,
    hasDelegationExecutionLog: true,
    hasMeaningfulDelegationExecutionLog: true,
    hasTrivialExceptionReason: false,
    hasOpsSparkMention: false,
    hasRoutineOpsWork: true,
    hasSpawnDirective: true,
    hasSpawnControllerFallback: true,
    hasSpawnDirectiveWithModelReasoning: true,
    hasControllerFallbackReasonField: false,
    hasMeaningfulControllerFallbackReason: false,
    hasSpecGateEvidence: false,
    hasMeaningfulSpecGateEvidence: false,
    hasFinalMergeGate: false,
    hasMeaningfulFinalMergeGate: false,
    hasFinalMergeGateRequiredKeys: false,
    finalMergeGateReadyFlag: "absent",
    finalMergeGateHasExplicitPendingInitialGate: false,
    finalMergeGateReadyWithResolvedThreadsOnly: true,
    hasReviewConversationCloseout: true,
    hasMeaningfulReviewConversationCloseout: true,
  };
  const spawnCases = [
    {
      name: "missing model fails spawn gating",
      body: bodyWithSpawnDirective({ spawnDirective: "spawn: ops_spark controller_fallback=not_allowed" }),
      labels: ["codex"],
      expected: {
        ...spawnExpectedBase,
        hasOpsSparkMention: true,
        hasSpawnModel: false,
        hasSpawnReasoning: false,
        hasSpawnDirectiveWithModelReasoning: false,
        hasSpawnAllowedWithoutReason: false,
      },
    },
    {
      name: "missing reasoning fails spawn gating",
      body: bodyWithSpawnDirective({
        spawnDirective: "spawn: ops_spark model=gpt-5.3-codex-spark controller_fallback=not_allowed",
      }),
      labels: ["codex"],
      expected: {
        ...spawnExpectedBase,
        hasOpsSparkMention: true,
        hasSpawnModel: true,
        hasSpawnReasoning: false,
        hasSpawnDirectiveWithModelReasoning: false,
        hasSpawnAllowedWithoutReason: false,
      },
    },
    ["mixed spawn directives require each directive to be complete", ["spawn: backend_worker model=gpt-5.4 reasoning=high controller_fallback=not_allowed", "spawn: docs_worker model=gpt-5.4 reasoning=high"], { hasOpsSparkMention: true, hasSpawnModel: true, hasSpawnReasoning: true, hasSpawnControllerFallback: true, hasSpawnDirectiveWithModelReasoning: false }],
    ["ops_spark rejects non-codex-spark model", "spawn: ops_spark model=gpt-5.5 reasoning=medium controller_fallback=not_allowed", { hasOpsSparkMention: true, hasSpawnModel: true, hasSpawnReasoning: true, hasSpawnControllerFallback: true, hasSpawnDirectiveWithModelReasoning: false }],
    ["valid spawn with model/reasoning passes", "spawn: ops_spark model=gpt-5.3-codex-spark reasoning=medium controller_fallback=not_allowed", { hasOpsSparkMention: true, hasSpawnModel: true, hasSpawnReasoning: true, hasSpawnAllowedWithoutReason: false }],
    {
      name: "fallback allowed must include reason",
      body: bodyWithSpawnDirective({
        profile: "backend_worker",
        spawnDirective: "spawn: backend_worker model=gpt-5.4 reasoning=high controller_fallback=allowed",
        task: "review policy gate",
      }),
      labels: ["codex"],
      expected: {
        ...spawnExpectedBase,
        hasSpawnModel: true,
        hasSpawnReasoning: true,
        hasSpawnAllowedWithoutReason: true,
        hasRoutineOpsDelegationWarning: true,
      },
    },
    {
      name: "fallback allowed with reason passes",
      body: bodyWithSpawnDirective({
        profile: "backend_worker",
        spawnDirective:
          "spawn: backend_worker model=gpt-5.4 reasoning=high controller_fallback=allowed fallback_reason=high-risk schema drift check",
        task: "review policy gate",
      }),
      labels: ["codex"],
      expected: {
        ...spawnExpectedBase,
        hasSpawnModel: true,
        hasSpawnReasoning: true,
        hasSpawnAllowedWithoutReason: false,
        hasRoutineOpsDelegationWarning: true,
      },
    },
  ];

  for (const item of spawnCases) {
    const { name, body, labels, expected } = Array.isArray(item)
      ? { name: item[0], body: bodyWithSpawnDirective({ spawnDirective: item[1], spawnDirectives: Array.isArray(item[1]) ? item[1] : undefined }), labels: ["codex"], expected: { ...spawnExpectedBase, ...item[2] } }
      : item;
    assertGate(name, body, labels, expected);
  }
});

test("Autonomous PR spec gate and final merge gate require meaningful evidence", () => {
  const bodyWithAutonomousGates = ({
    specGateEvidence = "pending initial spec gate: waiting for first CI readback",
    finalMergeGate = [
      "latest_head_sha=pending initial gate",
      "unresolved_thread_count=pending initial gate",
      "spec_gate_status=pending initial gate",
      "evidence_urls=pending initial gate",
    ].join("\n"),
    reviewConversationCloseout = "已建立 closeout tracking，等待第一輪 reviewer / bot feedback",
  } = {}) =>
    makePrBody({
      delegationRows: [
        { label: "Source issue delegation plan", value: "#123" },
        { label: "Actual worker profile(s)", value: "ops_spark" },
        { label: "Task", value: "ops_spark: CI readback and PR evidence upkeep" },
        {
          label: "Spawn directive",
          value: "spawn: ops_spark model=gpt-5.3-codex-spark reasoning=medium controller_fallback=not_allowed",
        },
        { label: "Spec gate evidence", value: specGateEvidence },
        { label: "Final merge gate", value: finalMergeGate },
        { label: "Review conversation closeout", value: reviewConversationCloseout },
      ],
    });

  assertGate("missing spec gate evidence", bodyWithAutonomousGates({ specGateEvidence: "n/a" }), ["codex"], {
    autonomousDetected: true,
    hasDelegationExecutionLog: true,
    hasMeaningfulDelegationExecutionLog: true,
    hasOpsSparkMention: true,
    hasRoutineOpsWork: true,
    hasSpawnDirective: true,
    hasSpawnModel: true,
    hasSpawnReasoning: true,
    hasSpawnControllerFallback: true,
    hasSpawnDirectiveWithModelReasoning: true,
    hasRoutineOpsDelegationWarning: false,
    hasSpecGateEvidence: true,
    hasMeaningfulSpecGateEvidence: false,
    hasFinalMergeGate: true,
    hasMeaningfulFinalMergeGate: true,
    hasFinalMergeGateRequiredKeys: true,
    finalMergeGateReadyFlag: "absent",
    finalMergeGateHasExplicitPendingInitialGate: true,
    finalMergeGateReadyWithResolvedThreadsOnly: true,
    hasReviewConversationCloseout: true,
    hasMeaningfulReviewConversationCloseout: true,
  });

  assertGate("missing final merge gate evidence", bodyWithAutonomousGates({ finalMergeGate: "n/a" }), ["codex"], {
    autonomousDetected: true,
    hasDelegationExecutionLog: true,
    hasMeaningfulDelegationExecutionLog: true,
    hasOpsSparkMention: true,
    hasRoutineOpsWork: true,
    hasSpawnDirective: true,
    hasSpawnModel: true,
    hasSpawnReasoning: true,
    hasSpawnControllerFallback: true,
    hasSpawnDirectiveWithModelReasoning: true,
    hasRoutineOpsDelegationWarning: false,
    hasSpecGateEvidence: true,
    hasMeaningfulSpecGateEvidence: true,
    hasFinalMergeGate: true,
    hasMeaningfulFinalMergeGate: false,
    hasFinalMergeGateRequiredKeys: false,
    finalMergeGateReadyFlag: "absent",
    finalMergeGateHasExplicitPendingInitialGate: false,
    finalMergeGateReadyWithResolvedThreadsOnly: true,
    hasReviewConversationCloseout: true,
    hasMeaningfulReviewConversationCloseout: true,
  });

  assertGate(
    "review closeout parser does not consume final merge gate evidence",
    bodyWithAutonomousGates({
      finalMergeGate: [
        "latest_head_sha=abc1234",
        "unresolved_thread_count=0",
        "spec_gate_status=pass",
        "evidence_urls=https://example.com/pr/closeout",
        "ready_to_merge=true",
      ].join("\n"),
      reviewConversationCloseout: "n/a",
    }),
    ["codex"],
    {
      autonomousDetected: true,
      hasDelegationExecutionLog: true,
      hasMeaningfulDelegationExecutionLog: true,
      hasOpsSparkMention: true,
      hasRoutineOpsWork: true,
      hasSpawnDirective: true,
      hasSpawnModel: true,
      hasSpawnReasoning: true,
      hasSpawnControllerFallback: true,
      hasSpawnDirectiveWithModelReasoning: true,
      hasRoutineOpsDelegationWarning: false,
      hasSpecGateEvidence: true,
      hasMeaningfulSpecGateEvidence: true,
      hasFinalMergeGate: true,
      hasMeaningfulFinalMergeGate: true,
      hasFinalMergeGateRequiredKeys: true,
      finalMergeGateReadyFlag: "true",
      finalMergeGateHasExplicitPendingInitialGate: false,
      finalMergeGateReadyWithResolvedThreadsOnly: true,
      hasReviewConversationCloseout: true,
      hasMeaningfulReviewConversationCloseout: false,
    },
  );

  assertGate(
    "ready gate fails when unresolved threads are non-zero",
    bodyWithAutonomousGates({
      specGateEvidence: "spec validate=pass; evidence_url=https://example.com/spec/1",
      finalMergeGate: [
        "latest_head_sha=abc1234",
        "unresolved_thread_count=2",
        "spec_gate_status=pass",
        "evidence_urls=https://example.com/pr/1",
        "ready_to_merge=true",
      ].join("\n"),
      reviewConversationCloseout: "已整理 open thread，仍待兩則 reviewer finding closeout",
    }),
    ["auto-ready"],
    {
      autonomousDetected: true,
      hasDelegationExecutionLog: true,
      hasMeaningfulDelegationExecutionLog: true,
      hasOpsSparkMention: true,
      hasRoutineOpsWork: true,
      hasSpawnDirective: true,
      hasSpawnModel: true,
      hasSpawnReasoning: true,
      hasSpawnControllerFallback: true,
      hasSpawnDirectiveWithModelReasoning: true,
      hasRoutineOpsDelegationWarning: false,
      hasSpecGateEvidence: true,
      hasMeaningfulSpecGateEvidence: true,
      hasFinalMergeGate: true,
      hasMeaningfulFinalMergeGate: false,
      hasFinalMergeGateRequiredKeys: true,
      finalMergeGateReadyFlag: "true",
      finalMergeGateHasExplicitPendingInitialGate: false,
      finalMergeGateReadyWithResolvedThreadsOnly: false,
      hasReviewConversationCloseout: true,
      hasMeaningfulReviewConversationCloseout: true,
    },
  );

  assertGate(
    "ready gate passes when unresolved threads are zero",
    bodyWithAutonomousGates({
      specGateEvidence: "spec validate=pass; evidence_url=https://example.com/spec/2",
      finalMergeGate: [
        "latest_head_sha=def5678",
        "unresolved_thread_count=0",
        "spec_gate_status=pass",
        "evidence_urls=https://example.com/pr/2,https://example.com/check/2",
        "merge_ready=true",
      ].join("\n"),
      reviewConversationCloseout: "所有 actionable finding 已 comment/resolve，readback 與 head 一致",
    }),
    ["auto-ready"],
    {
      autonomousDetected: true,
      hasDelegationExecutionLog: true,
      hasMeaningfulDelegationExecutionLog: true,
      hasOpsSparkMention: true,
      hasRoutineOpsWork: true,
      hasSpawnDirective: true,
      hasSpawnModel: true,
      hasSpawnReasoning: true,
      hasSpawnControllerFallback: true,
      hasSpawnDirectiveWithModelReasoning: true,
      hasRoutineOpsDelegationWarning: false,
      hasSpecGateEvidence: true,
      hasMeaningfulSpecGateEvidence: true,
      hasFinalMergeGate: true,
      hasMeaningfulFinalMergeGate: true,
      hasFinalMergeGateRequiredKeys: true,
      finalMergeGateReadyFlag: "true",
      finalMergeGateHasExplicitPendingInitialGate: false,
      finalMergeGateReadyWithResolvedThreadsOnly: true,
      hasReviewConversationCloseout: true,
      hasMeaningfulReviewConversationCloseout: true,
    },
  );
});

test("Autonomous PR routine ops work warns when ops_spark is missing", () => {
  const withoutOpsSpark = `
## Delegation Execution Log
- Actual worker profile(s):
  - controller
- Task:
  - review closeout evidence readback and PR comment cleanup
- Review conversation closeout:
  - discussion_r123 resolved, PR comment evidence added
`;
  const withOpsSpark = `
## Delegation Execution Log
- Actual worker profile(s):
  - controller
  - ops_spark
- Task:
  - ops_spark: review closeout evidence readback and PR comment cleanup
- Review conversation closeout:
  - discussion_r123 resolved, PR comment evidence added
`;
  const withException = `
## Delegation Execution Log
- Actual worker profile(s):
  - controller
- Task:
  - review closeout evidence readback and PR comment cleanup
- Trivial/self-only exception reason:
  - one-line metadata-only readback in the same PR after worker outage
- Review conversation closeout:
  - discussion_r123 resolved, PR comment evidence added
`;

  assert.equal(evaluateAutonomousCloseoutGate({ body: withoutOpsSpark, labels: ["codex"] }).hasRoutineOpsDelegationWarning, true);
  assert.equal(evaluateAutonomousCloseoutGate({ body: withOpsSpark, labels: ["codex"] }).hasRoutineOpsDelegationWarning, false);
  assert.equal(evaluateAutonomousCloseoutGate({ body: withException, labels: ["codex"] }).hasRoutineOpsDelegationWarning, false);
});

test("Autonomous PR commit-push checklist work warns when ops_spark is missing", () => {
  const withoutOpsSpark = `
## Delegation Execution Log
- Actual worker profile(s):
  - controller
- Task:
  - commit/push checklist with pre-commit validation, post-push readback, branch and PR head SHA verification
- Review conversation closeout:
  - no automated review threads were open
`;
  const withOpsSpark = `
## Delegation Execution Log
- Actual worker profile(s):
  - controller
  - ops_spark
- Task:
  - ops_spark: pre-commit checklist and post-push readback for branch and PR head SHA
- Review conversation closeout:
  - no automated review threads were open
`;
  const withException = `
## Delegation Execution Log
- Actual worker profile(s):
  - controller
- Task:
  - commit/push checklist with pre-commit validation, post-push readback, branch and PR head SHA verification
- Trivial/self-only exception reason:
  - controller ran the checklist directly because this was a single docs-only follow-up and ops_spark was unavailable
- Review conversation closeout:
  - no automated review threads were open
`;

  assert.equal(evaluateAutonomousCloseoutGate({ body: withoutOpsSpark, labels: ["codex"] }).hasRoutineOpsDelegationWarning, true);
  assert.equal(evaluateAutonomousCloseoutGate({ body: withOpsSpark, labels: ["codex"] }).hasRoutineOpsDelegationWarning, false);
  assert.equal(evaluateAutonomousCloseoutGate({ body: withException, labels: ["codex"] }).hasRoutineOpsDelegationWarning, false);
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
  assert.match(workflow, /\.github\/workflow-tests\/cross-repo-contracts\.fixture\.json/);
  assert.match(workflow, /REQUIRE_STOREFRONT_CONTRACT: "1"/);
  assert.match(workflow, /node --test \.github\/workflow-tests\/cross-repo-contract\.test\.mjs/);
  assert.match(workflow, /timeout-minutes: 10/);
  assert.doesNotMatch(workflow, /pnpm install/);
  assert.doesNotMatch(workflow, /pnpm (run )?build/);
});

test("PostgreSQL migration gate stays path-filtered and secret-free", () => {
  const workflow = readWorkflow("postgres-migration-gate.yml");
  const pullRequestSection = extractWorkflowSection(workflow, "  pull_request:", "  push:");
  const pushSection = extractWorkflowSection(workflow, "  push:", "\nconcurrency:");

  assert.match(workflow, /workflow_dispatch:/);
  assert.match(workflow, /schedule:/);
  assert.match(workflow, /pull_request:/);
  assert.match(workflow, /push:/);
  assert.match(workflow, /api\/migrations\/\*\*/);
  assert.match(workflow, /api\/models\/\*\*/);
  assert.match(pullRequestSection, /api\/tests\/test_migrations\.py/);
  assert.match(pushSection, /api\/tests\/test_migrations\.py/);
  assert.match(workflow, /services:\s+postgres:/);
  assert.match(workflow, /image: postgres:16/);
  assert.match(workflow, /timeout-minutes: 10/);
  assert.match(workflow, /working-directory: api/);
  assert.match(workflow, /DATABASE_URL: postgresql:\/\/tachiya:tachiya@localhost:5432\/tachiya/);
  assert.match(workflow, /TACHIYA_MIGRATION_SMOKE_USE_DATABASE_URL: "1"/);
  assert.match(workflow, /uv run --group dev pytest -o addopts='' --junitxml=postgres-migration-smoke\.xml tests\/test_migrations\.py/);
  assert.match(workflow, /uses: actions\/upload-artifact@v4/);
  assert.match(workflow, /name: postgres-migration-smoke/);
  assert.match(workflow, /path: api\/postgres-migration-smoke\.xml/);
  assert.match(workflow, /retention-days: 7/);
  assert.doesNotMatch(workflow, /uv run --group dev alembic upgrade head/);
  assert.doesNotMatch(workflow, /secrets\./);
  assert.doesNotMatch(workflow, /production/i);
});
