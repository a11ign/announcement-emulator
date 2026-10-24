import { test } from "node:test";
import assert from "node:assert/strict";
import { wrapperSource } from "./wrapper.ts";

test("the zero-line wrapper imports the user's config as it is and wraps it", () => {
  assert.equal(wrapperSource("/p/playwright.config.ts"), 'import config from "./playwright.config";\nimport { withAnnouncements } from "@a11ign/announcement-emulator";\nexport default withAnnouncements(config);\n');
  assert.match(wrapperSource("/p/playwright.config.mjs"), /from "\.\/playwright\.config\.mjs"/);
});
