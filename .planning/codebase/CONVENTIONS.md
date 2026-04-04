# Coding Conventions

**Analysis Date:** 2026-04-04

## Subproject Overview

Three active subprojects with distinct conventions:
- `frontend/` — Next.js 19 / React 19 storefront (TypeScript strict)
- `dashboard/` — Saleor Dashboard admin panel (TypeScript with selective strict plugin)
- `api/` — FastAPI (Python 3.12, minimal codebase)

---

## Naming Patterns

**Files (frontend):**
- React components: PascalCase, e.g., `ProductCard.tsx`
- Utility/logic files: kebab-case, e.g., `filter-utils.ts`, `variant-selection/utils.ts`
- Test files: co-located, same name with `.test.ts` suffix, e.g., `filter-utils.test.ts`
- Fixture files: `__fixtures__/` subdirectory, e.g., `__fixtures__/products.ts`

**Files (dashboard):**
- React components: PascalCase, e.g., `ConfigurationPage.tsx`
- Storybook files: `ComponentName.stories.tsx`
- Test files: co-located inside feature directories, e.g., `src/customers/components/CustomerDetails/CustomerDetails.test.ts`
- Fixture files: `fixtures.ts` per feature module
- GraphQL generated files: suffixed `.generated.ts` — never manually edit

**Directories (dashboard):**
- Feature-based: `src/products/`, `src/orders/`, `src/customers/`
- Each feature contains: `views/`, `components/`, `mutations.ts`, `queries.ts`, `urls.ts`, `fixtures.ts`

**Functions:**
- camelCase throughout TypeScript/JavaScript
- Python: snake_case (following PEP 8)

**Types / Interfaces:**
- PascalCase, e.g., `MenuSection`, `UserFragment`
- Props interfaces named `ComponentNameProps`

**CSS / Styling (dashboard):**
- CSS Modules: `Component.module.css` files, accessed via `import styles from "./Component.module.css"`
- Do not use plain `.css` files (would pollute global namespace)

---

## Code Style

**Formatting (frontend — `frontend/.prettierrc.json`):**
- Print width: 110
- Tabs: yes (`useTabs: true`)
- Semicolons: yes
- Single quotes: no (double quotes)
- Trailing commas: all
- Tailwind CSS class sorting via `prettier-plugin-tailwindcss`

**Formatting (dashboard — `dashboard/.prettierrc`):**
- Print width: 100
- Tabs: no (spaces)
- Semicolons: default (yes)
- Single quotes: no (double quotes)
- Trailing commas: all
- Arrow parens: avoid (omit parens for single-arg arrows)

**Lint-staged (dashboard — `dashboard/lint-staged.config.cjs`):**
- On commit: ESLint auto-fix + Prettier write for `*.{js,jsx,ts,tsx,mjs,cjs}`
- Prettier write for `*.{json,css,md,yml,yaml}`
- `sort-package-json` for `package.json`

---

## Linting

### frontend (`frontend/eslint.config.mjs`)

- Extends `eslint-config-next/core-web-vitals`
- Ignores: `.next/**`, `out/**`, `build/**`, `next-env.d.ts`
- No additional custom rules beyond Next.js defaults

### dashboard (`dashboard/eslint.config.mjs`)

Extensive configuration with many plugins:

**Active plugins:**
- `typescript-eslint` (recommended)
- `eslint-plugin-react` + `eslint-plugin-react-hooks` (React Compiler rules as warnings)
- `eslint-plugin-simple-import-sort` — import ordering enforced as error
- `eslint-plugin-import` — no default exports (warning), no duplicates (error)
- `eslint-plugin-unused-imports` — unused imports as error
- `eslint-plugin-unicorn` — `no-empty-file` as error
- `eslint-plugin-formatjs` — i18n message ID enforcement
- `@graphql-eslint/eslint-plugin` — GraphQL operation linting
- `eslint-plugin-storybook`
- Local custom rules: `local-rules/named-styles` (error), `local-rules/no-deprecated-icons` (warning)
  - Rule source: `dashboard/lint/rules/`

**Key rules enforced (errors):**
- `unused-imports/no-unused-imports`
- `simple-import-sort/imports` and `simple-import-sort/exports`
- `import/no-duplicates`
- `formatjs/enforce-id` (sha512 hash pattern for i18n IDs)
- `no-console` (except `warn` and `error`)
- `@typescript-eslint/no-unused-vars` (local vars and args after used; ignore `_` prefix)
- `local-rules/named-styles`

**Key rules as warnings (migration in progress):**
- `@typescript-eslint/no-non-null-assertion`
- `@typescript-eslint/explicit-function-return-type`
- `import/no-default-export` (except stories and config files)
- React Compiler hook rules (purity, refs, set-state-in-render, etc.)

**Disabled (intentionally):**
- `@typescript-eslint/no-explicit-any` — migration in progress
- `prefer-const`
- `react/prop-types`
- `@typescript-eslint/ban-types`
- `@typescript-eslint/no-empty-object-type`

**Restricted imports (warn):**
- `@material-ui/*` — deprecated, use `@saleor/macaw-ui-next`
- `@saleor/macaw-ui` — legacy, use `@saleor/macaw-ui-next`
- `react-sortable-hoc` — use `@dnd-kit`
- `moment` / `moment-timezone` — use `react-intl formatDate`
- `import React from 'react'` (default import) — use named imports
- `lodash` (direct) — use `lodash/<function>` sub-imports
- `classnames` — use `clsx`

**Type imports:**
```typescript
// Use inline type imports (enforced as warning):
import { type UserFragment } from "../graphql";
```

---

## Import Organization

**dashboard — enforced by `simple-import-sort`:**
Imports must be sorted. Blank line required after the import block (enforced by `padding-line-between-statements`).

**Path aliases:**

| Project | Alias | Resolves to |
|---|---|---|
| frontend | `@/*` | `./src/*` |
| frontend | `@ui/*` | `./src/components/*` |
| dashboard | `@dashboard/*` | `src/*` |
| dashboard | `@assets/*` | `assets/*` |
| dashboard | `@locale/*` | `locale/*` |
| dashboard | `@test/*` | `testUtils/*` |

**No barrel/index files (dashboard):**
Use direct imports. Index files are an anti-pattern being removed:
```typescript
// Avoid:
import { Component } from "./components";

// Prefer:
import { Component } from "./components/Component";
```

---

## TypeScript Configuration

### frontend (`frontend/tsconfig.json`)

- Target: `ES2022`
- `strict: true` — full strict mode
- `noUnusedLocals: true`, `noUnusedParameters: true`
- `noUncheckedIndexedAccess: false`
- `isolatedModules: true`
- `allowJs: true`, `skipLibCheck: true`
- Excludes `src/_reference` from compilation

### dashboard (`dashboard/tsconfig.json`)

- Target: `ES2020`
- `strict: false` — strict mode disabled globally
- Uses `typescript-strict-plugin` for gradual strictness adoption per file
- `skipLibCheck: true`
- Excludes `playwright/` from main tsconfig (separate `playwright/tsconfig.json`)
- New code should be written strict-mode compatible

---

## React Patterns (dashboard)

**Component exports:**
- Named exports only — no default exports (enforced as warning)
- Exception: `.stories.tsx` files and config files allow default exports

**Component structure:**
```typescript
// Component.tsx
import { Box, Text } from "@saleor/macaw-ui-next";
import { Trash2 } from "lucide-react";
import { useCallback } from "react";
import { FormattedMessage } from "react-intl";

import styles from "./Component.module.css";

interface ComponentProps {
  title: string;
  onDelete: (id: string) => void;
}

export const Component = ({ title, onDelete }: ComponentProps) => {
  const handleDelete = useCallback(() => {
    onDelete(title);
  }, [title, onDelete]);

  return (
    <Box className={styles.container}>
      <Text>{title}</Text>
      <button onClick={handleDelete}>
        <Trash2 size={16} />
        <FormattedMessage defaultMessage="Delete" id="deleteBtn" />
      </button>
    </Box>
  );
};
```

**Icons:**
- Use `lucide-react` directly — Macaw icons are deprecated
- `import { Trash2 } from "lucide-react"`

**UI library:**
- Use `@saleor/macaw-ui-next` — not legacy `@saleor/macaw-ui` or `@material-ui/*`

**Storybook:**
- Every new component must have a `.stories.tsx` file

**Type assertions:**
```typescript
// Avoid:
const style = { display: "flex" } as React.CSSProperties;

// Prefer:
const style: React.CSSProperties = { display: "flex" };
```

---

## Internationalization (dashboard)

- All user-facing strings must use `react-intl`
- Check `src/intl.ts` for existing messages before creating new ones
- Message IDs enforced by ESLint `formatjs/enforce-id` as sha512 hash: `[sha512:contenthash:base64:6]`
- Extract messages: `pnpm run extract-messages`

---

## Error Handling

**Python (api):**
- FastAPI default exception handling (minimal codebase, no custom handlers yet)

**TypeScript (frontend/dashboard):**
- React Error Boundary pattern (`react-error-boundary` package in frontend)
- `no-console` enforced — only `console.warn` and `console.error` allowed

---

## Comments

**Dashboard CLAUDE.md guidance:**
- Add `// Arrange // Act // Assert` comments in test files
- Avoid `// @ts-strict-ignore` — write properly typed code instead

---

## Padding / Blank Lines (dashboard)

`padding-line-between-statements` enforced as error:
- Blank line required after imports (before first non-import)
- Blank line before and after variable declarations (`const`, `let`, `var`) sequences
- Blank line before and after `if`, `while`, `switch`, `try`, `class`
- Blank line before `return` statements

---

## Python (api)

- Runtime: Python 3.12+
- Package manager: `uv` (lockfile: `api/uv.lock`)
- Dependencies defined in `api/pyproject.toml`
- No linting/formatting configuration detected (ruff, black, etc. not configured)
- No test files present — `api/` is a minimal stub

---

*Convention analysis: 2026-04-04*
