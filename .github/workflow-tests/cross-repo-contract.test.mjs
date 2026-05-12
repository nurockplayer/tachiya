import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";

const repoRoot = process.cwd();
const requireStorefront = process.env.REQUIRE_STOREFRONT_CONTRACT === "1";
const storefrontRoot = resolveStorefrontRoot();
const shouldCheckStorefrontContract = Boolean(storefrontRoot || requireStorefront);
const contractAsset = readContractAsset();

function readRepoFile(relativePath) {
  return readFileSync(path.join(repoRoot, relativePath), "utf8");
}

function readStorefrontFile(relativePath) {
  assert.ok(
    storefrontRoot,
    "Storefront checkout is required. Set STOREFRONT_PATH or checkout nurockplayer/storefront to .ci/storefront.",
  );
  return readFileSync(path.join(storefrontRoot, relativePath), "utf8");
}

function resolveStorefrontRoot() {
  const candidates = [
    process.env.STOREFRONT_PATH,
    path.join(repoRoot, ".ci/storefront"),
    path.resolve(repoRoot, "../storefront"),
  ].filter(Boolean);

  return candidates.find((candidate) => existsSync(path.join(candidate, "package.json"))) ?? null;
}

function readContractAsset() {
  return JSON.parse(readRepoFile(".github/workflow-tests/cross-repo-contracts.fixture.json"));
}

function assertFileContains(fileLabel, content, snippets, context) {
  for (const snippet of snippets) {
    assert.ok(
      content.includes(snippet),
      `${context.rowName}: ${fileLabel} is missing snippet ${JSON.stringify(snippet)}. expected behavior: ${context.expectedBehavior}; suggested file: ${context.suggestedFile}`,
    );
  }
}

function assertObjectHasExpectedFiles(row, fieldName, expectedFiles) {
  const checks = row[fieldName];
  assert.ok(checks && typeof checks === "object" && !Array.isArray(checks), schemaError(row, [`${fieldName} must be an object keyed by file path`]));

  const actualFiles = Object.keys(checks).sort();
  const expectedFilesSorted = [...expectedFiles].sort();
  assert.deepEqual(
    actualFiles,
    expectedFilesSorted,
    schemaError(
      row,
      [
        `${fieldName} must cover exactly these files: ${expectedFilesSorted.join(", ")}`,
        `actual files: ${actualFiles.join(", ") || "(none)"}`,
      ],
    ),
  );

  for (const [filePath, snippets] of Object.entries(checks)) {
    assert.ok(Array.isArray(snippets) && snippets.length > 0, schemaError(row, [`${fieldName}.${filePath} must be a non-empty array of snippets`]));
    for (const snippet of snippets) {
      assert.equal(typeof snippet, "string", schemaError(row, [`${fieldName}.${filePath} snippet values must be strings`]));
      assert.ok(snippet.length > 0, schemaError(row, [`${fieldName}.${filePath} snippet values must not be blank`]));
    }
  }
}

function schemaError(row, missingParts) {
  const rowName = row?.name ?? "<unnamed row>";
  const expectedBehavior = row?.expectedBehavior ?? "n/a";
  const suggestedFile = row?.suggestedFile ?? "docs/cross-repo-contracts.md";
  return `Contract asset row "${rowName}" is missing or malformed: ${missingParts.join("; ")}. expected behavior: ${expectedBehavior}; suggested file: ${suggestedFile}`;
}

function validateRowSchema(row) {
  const missing = [];

  if (!row || typeof row !== "object" || Array.isArray(row)) {
    assert.fail(`Contract asset row must be an object, got ${describeValue(row)}`);
  }

  if (typeof row.name !== "string" || row.name.trim() === "") missing.push("name");
  if (typeof row.endpoint !== "string" && typeof row.pathPattern !== "string") missing.push("endpoint or pathPattern");
  if (!Array.isArray(row.requiredHeaders)) missing.push("requiredHeaders");
  if (!Array.isArray(row.queryParams)) missing.push("queryParams");
  if (!Array.isArray(row.responseFields)) missing.push("responseFields");
  if (!Array.isArray(row.tachiyaDocsFiles)) missing.push("tachiyaDocsFiles");
  if (!Array.isArray(row.tachiyaRouterFiles)) missing.push("tachiyaRouterFiles");
  if (!Array.isArray(row.storefrontConsumerFiles)) missing.push("storefrontConsumerFiles");
  if (!Array.isArray(row.storefrontTestFiles)) missing.push("storefrontTestFiles");
  if (typeof row.expectedBehavior !== "string" || row.expectedBehavior.trim() === "") missing.push("expectedBehavior");
  if (typeof row.suggestedFile !== "string" || row.suggestedFile.trim() === "") missing.push("suggestedFile");
  if (!row.tachiyaDocsChecks || typeof row.tachiyaDocsChecks !== "object" || Array.isArray(row.tachiyaDocsChecks)) missing.push("tachiyaDocsChecks");
  if (!row.tachiyaRouterChecks || typeof row.tachiyaRouterChecks !== "object" || Array.isArray(row.tachiyaRouterChecks)) missing.push("tachiyaRouterChecks");
  if (
    !row.storefrontConsumerChecks ||
    typeof row.storefrontConsumerChecks !== "object" ||
    Array.isArray(row.storefrontConsumerChecks)
  )
    missing.push("storefrontConsumerChecks");
  if (!row.storefrontTestChecks || typeof row.storefrontTestChecks !== "object" || Array.isArray(row.storefrontTestChecks)) missing.push("storefrontTestChecks");

  assert.ok(missing.length === 0, schemaError(row, missing));

  const arrayFields = [
    "requiredHeaders",
    "queryParams",
    "responseFields",
    "tachiyaDocsFiles",
    "tachiyaRouterFiles",
    "storefrontConsumerFiles",
    "storefrontTestFiles",
  ];

  for (const fieldName of arrayFields) {
    const values = row[fieldName];
    const mustBeNonEmpty = fieldName !== "queryParams" && fieldName !== "requiredHeaders";
    assert.ok(
      Array.isArray(values) && (!mustBeNonEmpty || values.length > 0),
      schemaError(row, [`${fieldName} must be an array${mustBeNonEmpty ? " with at least one item" : ""}`]),
    );
    for (const value of values) {
      assert.equal(typeof value, "string", schemaError(row, [`${fieldName} entries must be strings`]));
      assert.ok(value.trim().length > 0, schemaError(row, [`${fieldName} entries must not be blank`]));
    }
  }

  assertObjectHasExpectedFiles(row, "tachiyaDocsChecks", row.tachiyaDocsFiles);
  assertObjectHasExpectedFiles(row, "tachiyaRouterChecks", row.tachiyaRouterFiles);
  assertObjectHasExpectedFiles(row, "storefrontConsumerChecks", row.storefrontConsumerFiles);
  assertObjectHasExpectedFiles(row, "storefrontTestChecks", row.storefrontTestFiles);
}

function describeValue(value) {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (Array.isArray(value)) return `array(${value.length})`;
  return typeof value;
}

function validateContractAsset() {
  assert.ok(contractAsset && typeof contractAsset === "object" && !Array.isArray(contractAsset), "Contract asset must be a JSON object.");
  assert.ok(Array.isArray(contractAsset.rows), "Contract asset must define rows[]");

  const requiredRows = [
    "Points balance",
    "Points ledger",
    "Coupons",
    "Streamer list",
    "Streamer catalog",
  ];

  const rowsByName = new Map();
  for (const row of contractAsset.rows) {
    validateRowSchema(row);
    assert.ok(!rowsByName.has(row.name), schemaError(row, ["duplicate row name"]));
    rowsByName.set(row.name, row);
  }

  for (const rowName of requiredRows) {
    assert.ok(rowsByName.has(rowName), `Contract asset is missing required row "${rowName}". suggested file: .github/workflow-tests/cross-repo-contracts.fixture.json`);
  }

  return rowsByName;
}

function checkRowDocsAndPaths(row) {
  const context = {
    rowName: row.name,
    expectedBehavior: row.expectedBehavior,
    suggestedFile: row.suggestedFile,
  };

  for (const filePath of row.tachiyaDocsFiles) {
    assert.ok(
      existsSync(path.join(repoRoot, filePath)),
      `${row.name}: missing docs file ${filePath}. expected behavior: ${row.expectedBehavior}; suggested file: ${row.suggestedFile}`,
    );
    const content = readRepoFile(filePath);
    assertFileContains(filePath, content, row.tachiyaDocsChecks[filePath], context);
  }

  for (const filePath of row.tachiyaRouterFiles) {
    assert.ok(
      existsSync(path.join(repoRoot, filePath)),
      `${row.name}: missing router file ${filePath}. expected behavior: ${row.expectedBehavior}; suggested file: ${row.suggestedFile}`,
    );
    const content = readRepoFile(filePath);
    assertFileContains(filePath, content, row.tachiyaRouterChecks[filePath], context);
  }

  for (const filePath of row.storefrontConsumerFiles) {
    if (!shouldCheckStorefrontContract) break;
    assert.ok(
      storefrontRoot && existsSync(path.join(storefrontRoot, filePath)),
      `${row.name}: missing storefront consumer file ${filePath}. expected behavior: ${row.expectedBehavior}; suggested file: ${row.suggestedFile}`,
    );
    const content = readStorefrontFile(filePath);
    assertFileContains(filePath, content, row.storefrontConsumerChecks[filePath], context);
  }

  for (const filePath of row.storefrontTestFiles) {
    if (!shouldCheckStorefrontContract) break;
    assert.ok(
      storefrontRoot && existsSync(path.join(storefrontRoot, filePath)),
      `${row.name}: missing storefront test file ${filePath}. expected behavior: ${row.expectedBehavior}; suggested file: ${row.suggestedFile}`,
    );
    const content = readStorefrontFile(filePath);
    assertFileContains(filePath, content, row.storefrontTestChecks[filePath], context);
  }
}

test("cross-repo contract asset stays schema-complete for the minimum rows", () => {
  validateContractAsset();
});

test("cross-repo contract docs and path surfaces stay aligned with the asset", () => {
  const rowsByName = validateContractAsset();

  for (const row of rowsByName.values()) {
    checkRowDocsAndPaths(row);
  }
});

test("cross-repo contract docs describe Tachiya-owned Storefront contracts", () => {
  const contracts = readRepoFile("docs/cross-repo-contracts.md");

  assertFileContains(
    "docs/cross-repo-contracts.md",
    contracts,
    [
      "## Contract Matrix",
      "## Failure Report Format",
      "## Repair Priority",
      ".github/workflows/cross-repo-contract.yml",
      ".github/workflow-tests/cross-repo-contracts.fixture.json",
    ],
    {
      rowName: "cross-repo contract docs",
      expectedBehavior: "The cross-repo contract docs should explain the asset-driven gate and how to repair failures.",
      suggestedFile: "docs/cross-repo-contracts.md",
    },
  );
});

test("Tachiya API docs and routers keep Storefront-facing endpoint surfaces", () => {
  const apiContracts = readRepoFile("docs/internal-api-contracts.md");
  const pointsRouter = readRepoFile("api/routers/points.py");
  const couponsRouter = readRepoFile("api/routers/coupons.py");
  const streamersRouter = readRepoFile("api/routers/streamers.py");

  assertFileContains(
    "docs/internal-api-contracts.md",
    apiContracts,
    [
      "### `GET /points/balance`",
      "### `GET /points/ledger`",
      "### `GET /coupons`",
      "### `GET /streamers`",
      "### `GET /streamers/{slug}/catalog`",
      "X-Tachiya-Internal-Secret",
    ],
    {
      rowName: "internal api contract docs",
      expectedBehavior: "The internal API docs must keep the Storefront-facing contract rows and internal secret boundary visible.",
      suggestedFile: "docs/internal-api-contracts.md",
    },
  );

  assertFileContains(
    "api/routers/points.py",
    pointsRouter,
    ['router = APIRouter(prefix="/points"', '"/balance"', '"/ledger"'],
    {
      rowName: "points router",
      expectedBehavior: "Points routes should continue to expose balance and ledger under the same prefix.",
      suggestedFile: "api/routers/points.py",
    },
  );
  assertFileContains(
    "api/routers/coupons.py",
    couponsRouter,
    ['router = APIRouter(prefix="/coupons"', '"/redeem"', "redemption_token"],
    {
      rowName: "coupons router",
      expectedBehavior: "Coupons routes should continue to expose redeem and public lookup surfaces.",
      suggestedFile: "api/routers/coupons.py",
    },
  );
  assertFileContains(
    "api/routers/streamers.py",
    streamersRouter,
    ['router = APIRouter(prefix="/streamers"', '"/{slug}/catalog"', "streamers"],
    {
      rowName: "streamers router",
      expectedBehavior: "Streamer routes should continue to expose list, profile, and catalog paths.",
      suggestedFile: "api/routers/streamers.py",
    },
  );
});

test(
  "Storefront develop still consumes the Tachiya contract rows",
  { skip: !storefrontRoot && !requireStorefront },
  () => {
    assert.ok(storefrontRoot, "Storefront checkout is required when REQUIRE_STOREFRONT_CONTRACT=1");

    const pointsConsumer = readStorefrontFile("src/lib/tachiya-points.ts");
    const pointsTests = readStorefrontFile("src/lib/tachiya-points.test.ts");
    const couponsConsumer = readStorefrontFile("src/checkout/lib/tachiya-coupons.ts");
    const couponsTests = readStorefrontFile("src/checkout/lib/tachiya-coupons.test.ts");
    const streamerConsumer = readStorefrontFile("src/lib/tachiya-streamer-catalog.ts");
    const streamerTests = readStorefrontFile("src/lib/tachiya-streamer-catalog.test.ts");

    assertFileContains(
      "src/lib/tachiya-points.ts",
      pointsConsumer,
      ["/points/balance?user_id=", "/points/ledger?user_id=", "X-Tachiya-Internal-Secret", "NEXT_PUBLIC_TACHIYA_API_URL"],
      {
        rowName: "points consumer",
        expectedBehavior: "The points helper should continue to build balance and ledger URLs with the internal secret header.",
        suggestedFile: "src/lib/tachiya-points.ts",
      },
    );
    assertFileContains(
      "src/lib/tachiya-points.test.ts",
      pointsTests,
      ["points/balance", "points/ledger", "missing-config"],
      {
        rowName: "points consumer tests",
        expectedBehavior: "The points helper tests should continue to cover URL construction and config fallback.",
        suggestedFile: "src/lib/tachiya-points.test.ts",
      },
    );

    assertFileContains(
      "src/checkout/lib/tachiya-coupons.ts",
      couponsConsumer,
      ["tachiya_redemption_token", "/coupons?redemption_token=", "selectActiveTachiyaCoupon"],
      {
        rowName: "coupons consumer",
        expectedBehavior: "The coupons helper should keep using redemption token lookup and active coupon selection.",
        suggestedFile: "src/checkout/lib/tachiya-coupons.ts",
      },
    );
    assertFileContains(
      "src/checkout/lib/tachiya-coupons.test.ts",
      couponsTests,
      ["redemption_token", "active coupon"],
      {
        rowName: "coupons consumer tests",
        expectedBehavior: "The coupons helper tests should keep covering token resolution and active coupon selection.",
        suggestedFile: "src/checkout/lib/tachiya-coupons.test.ts",
      },
    );

    assertFileContains(
      "src/lib/tachiya-streamer-catalog.ts",
      streamerConsumer,
      ["/streamers?limit=", "/streamers/${encodeURIComponent(slug)}/catalog", "X-Tachiya-Internal-Secret"],
      {
        rowName: "streamer consumer",
        expectedBehavior: "The streamer helper should continue to build list and catalog URLs with the internal secret header.",
        suggestedFile: "src/lib/tachiya-streamer-catalog.ts",
      },
    );
    assertFileContains(
      "src/lib/tachiya-streamer-catalog.test.ts",
      streamerTests,
      ["streamers?limit=", "/streamers/streamer-one/catalog"],
      {
        rowName: "streamer consumer tests",
        expectedBehavior: "The streamer helper tests should keep covering list and catalog URL construction.",
        suggestedFile: "src/lib/tachiya-streamer-catalog.test.ts",
      },
    );
  },
);
