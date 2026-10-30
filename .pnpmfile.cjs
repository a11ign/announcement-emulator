// typescript-eslint has no TypeScript 7 support (its peer range stops below 6.1.0, upstream typescript-eslint#10940), and TypeScript 7 ships no
// compiler API at its main entry (#12518). Upstream's advice is to run it on a TypeScript 6 beside the 7 that `tsc` and `rslib` use. This hook
// gives typescript-eslint and its @typescript-eslint packages that 6 as a dependency of their own, so they stop taking the importer's 7 as a peer.
// Remove it, and middleware/.npmrc with it, once typescript-eslint supports TypeScript 7.
const TYPESCRIPT_FOR_TYPESCRIPT_ESLINT = "npm:typescript@6.0.3";

function readPackage(pkg) {
  if (pkg.name !== "typescript-eslint" && !pkg.name.startsWith("@typescript-eslint/")) return pkg;
  if (!pkg.peerDependencies?.typescript) return pkg;
  delete pkg.peerDependencies.typescript;
  if (pkg.peerDependenciesMeta) delete pkg.peerDependenciesMeta.typescript;
  pkg.dependencies = { ...pkg.dependencies, typescript: TYPESCRIPT_FOR_TYPESCRIPT_ESLINT };
  return pkg;
}

module.exports = { hooks: { readPackage } };
