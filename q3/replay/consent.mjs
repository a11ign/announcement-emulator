// The consent rule (A11-166): which control of a page is "accept all", found by its role and accessible name in the page's accessibility tree, from the one list in consent-names.json.
//   import { classify } from "./consent.mjs"        classify(nodes) -> { outcome: "control" | "dialog" | "none", control?, why }
//   node consent.mjs < nodes.json                   the same over a JSON list of { role, name, ignored, backendId } on stdin, printed as JSON (the unit tests drive it so)
// `nodes` are the page's accessibility nodes as `nodesOf` makes them from CDP's Accessibility.getFullAXTree. A node the tree marks ignored (hidden) is never a control and never a dialog.
//   control   a control whose normalised name is in `acceptNames`, or in `acceptNamesInADialog` when the page also has a dialog or a cookie-named region; the earlier entry of the list wins, then the earlier node.
//   dialog    a dialog role or a cookie-named region is in the page and no control matched (the sidecar's `not-matched`).
//   none      neither (`no-dialog`).
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

export const RULE = JSON.parse(readFileSync(new URL("./consent-names.json", import.meta.url), "utf8"));

/** A name as the list is compared: lower case, typographic apostrophes straight, anything that is not a letter, digit or space a space. */
export const normalise = (s) => String(s ?? "").toLowerCase().replace(/[‘’ʼ`´]/g, "'").replace(/'/g, " ").replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();

const ACCEPT = RULE.acceptNames.map(normalise);
const ACCEPT_IN_A_DIALOG = RULE.acceptNamesInADialog.map(normalise);
const cookieNamed = (name) => RULE.regionWords.some((w) => new RegExp(`\\b${w}\\b`).test(normalise(name)));

/** The accessibility nodes CDP returns, as { role, name, ignored, backendId }. */
export const nodesOf = (axNodes) => axNodes.map((n) => ({ role: n.role?.value ?? "", name: n.name?.value ?? "", ignored: !!n.ignored, backendId: n.backendDOMNodeId }));

export function dialogsOf(nodes) {
  return nodes.filter((n) => !n.ignored && (RULE.dialogRoles.includes(n.role) || (RULE.regionRoles.includes(n.role) && cookieNamed(n.name))));
}

const CHOICE = /\b(cookie|cookies|accept|agree|allow|consent|preferences|settings|reject|decline|customi[sz]e|necessary)\b/;
/** The names of the controls that look like a consent choice, for the sidecar's account of a dialog nothing matched. */
const choicesOf = (nodes) => nodes.filter((n) => !n.ignored && RULE.controlRoles.includes(n.role) && CHOICE.test(normalise(n.name))).map((n) => n.name.trim());

export function classify(nodes) {
  const dialogs = dialogsOf(nodes);
  const rank = (n) => {
    const name = normalise(n.name), plain = ACCEPT.indexOf(name), bare = dialogs.length ? ACCEPT_IN_A_DIALOG.indexOf(name) : -1;
    return plain >= 0 ? plain : bare >= 0 ? ACCEPT.length + bare : -1;
  };
  const found = nodes.map((n, order) => ({ n, order, rank: !n.ignored && RULE.controlRoles.includes(n.role) ? rank(n) : -1 })).filter((x) => x.rank >= 0)
    .sort((a, b) => a.rank - b.rank || a.order - b.order);
  if (found.length) return { outcome: "control", control: found[0].n, why: `a ${found[0].n.role} named ${JSON.stringify(found[0].n.name)}` };
  if (dialogs.length) return { outcome: "dialog", why: `${dialogs.length} dialog or cookie region (${dialogs.slice(0, 3).map((d) => `${d.role} ${JSON.stringify(d.name)}`).join(", ")}) and no control in the list; controls that look like a choice: ${JSON.stringify(choicesOf(nodes).slice(0, 8))}`, choices: choicesOf(nodes) };
  return { outcome: "none", why: "no dialog and no cookie region" };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  let text = ""; process.stdin.setEncoding("utf8");
  for await (const chunk of process.stdin) text += chunk;
  console.log(JSON.stringify(classify(JSON.parse(text))));
}
