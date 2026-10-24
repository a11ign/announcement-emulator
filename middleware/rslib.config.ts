import { defineConfig } from "@rslib/core";
import { libraryPreset } from "@a11ign/toolchain/rslib-presets";
import pkg from "./package.json" with { type: "json" };

const [library] = libraryPreset(pkg, { dir: import.meta.dirname }).lib;

// `cli` is built beside the `exports` entries because `bin` names it and is not an `exports` key, so the preset cannot see it.
export default defineConfig({
  lib: [{ ...library, source: { tsconfigPath: "./tsconfig.build.json", entry: { ...library.source.entry, cli: "./src/cli.ts" } } }],
  // named chunks, so that what the entries share (`bundle`, `pins`) reads as itself in `dist` and not as `6.mjs`
  tools: { rspack: { optimization: { chunkIds: "named" } } },
});
