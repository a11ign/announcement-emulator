import { defineToolchainConfig } from "@a11ign/toolchain/rstest-config";

export default {
  ...defineToolchainConfig({
    root: import.meta.dirname,
    include: ["src/**/*.test.ts", "test-setup/**/*.test.ts"],
  }),
  // A11-279: one private TMPDIR per run, removed at its end, so the tests' `ae-*` folders never reach /tmp.
  globalSetup: ["./test-setup/private-tmp.mjs"],
};
