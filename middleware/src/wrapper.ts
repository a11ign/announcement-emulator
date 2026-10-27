import { basename } from "node:path";

/** The route with no line to add: a config that imports yours and wraps it, beside it so that every relative path in yours still means what it did. */
export function wrapperSource(configFile: string): string {
  const ext = configFile.endsWith(".ts") || configFile.endsWith(".mts") ? "" : configFile.slice(configFile.lastIndexOf("."));
  const base = basename(configFile).replace(/\.[cm]?[jt]s$/, "");
  return `import config from "./${base}${ext}";\nimport { withAnnouncements } from "@a11ign/foresay";\nexport default withAnnouncements(config);\n`;
}
