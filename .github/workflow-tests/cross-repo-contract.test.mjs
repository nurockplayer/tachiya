import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";

const repoRoot = process.cwd();
const requireStorefront = process.env.REQUIRE_STOREFRONT_CONTRACT === "1";
const storefrontRoot = resolveStorefrontRoot();

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

function assertFileContains(fileLabel, content, patterns) {
  for (const pattern of patterns) {
    assert.match(content, pattern, `${fileLabel} must contain ${pattern}`);
  }
}

function resolveStorefrontRoot() {
  const candidates = [
    process.env.STOREFRONT_PATH,
    path.join(repoRoot, ".ci/storefront"),
    path.resolve(repoRoot, "../storefront"),
  ].filter(Boolean);

  return candidates.find((candidate) => existsSync(path.join(candidate, "package.json"))) ?? null;
}

test("cross-repo contract docs describe Tachiya-owned Storefront contracts", () => {
  const contracts = readRepoFile("docs/cross-repo-contracts.md");

  assertFileContains("docs/cross-repo-contracts.md", contracts, [
    /## Contract Matrix/,
    /GET \/points\/balance/,
    /GET \/points\/ledger/,
    /GET \/coupons\?redemption_token=/,
    /GET \/streamers\?limit=/,
    /GET \/streamers\/\{slug\}\/catalog/,
    /\.github\/workflows\/cross-repo-contract\.yml/,
  ]);
});

test("Tachiya API docs and routers keep Storefront-facing endpoint surfaces", () => {
  const apiContracts = readRepoFile("docs/internal-api-contracts.md");
  const pointsRouter = readRepoFile("api/routers/points.py");
  const couponsRouter = readRepoFile("api/routers/coupons.py");
  const streamersRouter = readRepoFile("api/routers/streamers.py");

  assertFileContains("docs/internal-api-contracts.md", apiContracts, [
    /### `GET \/points\/balance`/,
    /### `GET \/points\/ledger`/,
    /### `GET \/coupons`/,
    /### `GET \/streamers`/,
    /### `GET \/streamers\/\{slug\}\/catalog`/,
    /X-Tachiya-Internal-Secret/,
  ]);

  assertFileContains("api/routers/points.py", pointsRouter, [/router = APIRouter\(prefix="\/points"/, /"\/balance"/, /"\/ledger"/]);
  assertFileContains("api/routers/coupons.py", couponsRouter, [/router = APIRouter\(prefix="\/coupons"/, /"\/redeem"/, /redemption_token/]);
  assertFileContains("api/routers/streamers.py", streamersRouter, [
    /router = APIRouter\(prefix="\/streamers"/,
    /"\/\{slug\}\/catalog"/,
    /streamers/,
  ]);
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

    assertFileContains("src/lib/tachiya-points.ts", pointsConsumer, [
      /\/points\/balance\?user_id=/,
      /\/points\/ledger\?user_id=/,
      /X-Tachiya-Internal-Secret/,
      /NEXT_PUBLIC_TACHIYA_API_URL/,
    ]);
    assertFileContains("src/lib/tachiya-points.test.ts", pointsTests, [/points\/balance/, /points\/ledger/, /missing-config/]);

    assertFileContains("src/checkout/lib/tachiya-coupons.ts", couponsConsumer, [
      /tachiya_redemption_token/,
      /\/coupons\?redemption_token=/,
      /selectActiveTachiyaCoupon/,
    ]);
    assertFileContains("src/checkout/lib/tachiya-coupons.test.ts", couponsTests, [/redemption_token/, /active coupon/]);

    assertFileContains("src/lib/tachiya-streamer-catalog.ts", streamerConsumer, [
      /\/streamers\?limit=/,
      /\/streamers\/\$\{encodeURIComponent\(slug\)\}\/catalog/,
      /X-Tachiya-Internal-Secret/,
    ]);
    assertFileContains("src/lib/tachiya-streamer-catalog.test.ts", streamerTests, [/streamers\?limit=/, /\/streamers\/streamer-one\/catalog/]);
  },
);
