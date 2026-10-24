// The mechanical half of the Clean Code limits, as the other a11ign repositories carry them (screenreader-worker's eslint.config.mjs).
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import globals from "globals";

export default tseslint.config(
  { ignores: ["node_modules/**", "**/dist/**", "**/*.json", "sample-suite/**"] },
  js.configs.recommended,
  {
    files: ["**/*.{ts,mjs}"],
    languageOptions: { ecmaVersion: 2023, sourceType: "module", globals: { ...globals.node } },
    rules: {
      "max-lines-per-function": ["error", { max: 70, skipBlankLines: true, skipComments: true }],
      complexity: ["error", 15],
      "max-depth": ["error", 3],
      "max-params": ["error", 4],
      "no-empty": ["error", { allowEmptyCatch: false }],
    },
  },
  // dom_check.mjs hands a function to the page; it runs in the browser
  { files: ["agreement/dom_check.mjs"], languageOptions: { globals: { ...globals.browser } } },
  ...tseslint.configs.recommended.map((c) => ({ ...c, files: ["**/*.ts"] })),
);
