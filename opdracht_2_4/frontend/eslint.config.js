// ESLint flat config for the React/TypeScript SPA.
//
// Run through pre-commit (see ../.pre-commit-config.yaml), which invokes the
// ESLint installed in this package. The flat config uses native ESM ``import``,
// whose resolution walks up from this file and ignores NODE_PATH, so the plugins
// must live in frontend/node_modules; their versions are pinned in package.json
// and package-lock.json.
import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";
import prettier from "eslint-config-prettier";

export default tseslint.config(
  { ignores: ["dist", "node_modules"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
    },
  },
  // Keep ESLint out of Prettier's way (formatting is enforced separately).
  prettier,
);
