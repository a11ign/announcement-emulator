// What the structure page-selection rule asks of a live page, read from its DOM only (no accessibility tree, no screen reader, nothing the fleet or the emulator said):
//   node dom_check_structure.mjs <address> [chrome executable]     prints the counts below as JSON
// A table is a <table> or an element with role table, grid or treegrid; a cell is a td, th or an element with role cell, gridcell, columnheader or rowheader, inside one. A list is a ul, ol or an element with
// role list, tree, listbox, menu or menubar; an item is an li or an element with role listitem, treeitem, option, menuitem, menuitemradio or menuitemcheckbox, inside one. Only visible elements count. A tab stop
// is as in dom_check.mjs (the visible, enabled elements the keyboard can reach).
import { chromium } from "@playwright/test";

const [address, executablePath] = process.argv.slice(2);
const browser = await chromium.launch({ ...(executablePath ? { executablePath } : {}), headless: true, args: ["--no-sandbox"] });
try {
  const page = await (await browser.newContext({ viewport: { width: 1008, height: 729 } })).newPage();
  await page.goto(address, { waitUntil: "load", timeout: 60_000 });
  await page.waitForTimeout(2500);
  const counts = await page.evaluate(() => {
    const visible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none"; };
    const stop = (el) => !el.disabled && !(el.tabIndex < 0) && visible(el);
    const stops = [...document.querySelectorAll('a[href], button, input:not([type="hidden"]), select, textarea, [tabindex]')].filter(stop);
    const TABLE = 'table, [role="table"], [role="grid"], [role="treegrid"]';
    const CELL = 'td, th, [role="cell"], [role="gridcell"], [role="columnheader"], [role="rowheader"]';
    const HEADER = 'th, [role="columnheader"], [role="rowheader"]';
    const LIST = 'ul, ol, [role="list"], [role="tree"], [role="listbox"], [role="menu"], [role="menubar"]';
    const ITEM = 'li, [role="listitem"], [role="treeitem"], [role="option"], [role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]';
    const inside = (el, selector) => !!el.closest(selector);
    const cells = [...document.querySelectorAll(CELL)].filter((c) => inside(c, TABLE) && visible(c));
    const tables = [...document.querySelectorAll(TABLE)].filter(visible);
    const biggest = (groups, parts) => Math.max(0, ...groups.map((g) => [...g.querySelectorAll(parts)].filter(visible).length));
    const items = [...document.querySelectorAll(ITEM)].filter((i) => inside(i, LIST) && visible(i));
    const lists = [...document.querySelectorAll(LIST)].filter(visible);
    return {
      tabStops: stops.length,
      tableCells: cells.length,
      headerCells: cells.filter((c) => c.matches(HEADER)).length,
      largestTable: biggest(tables, CELL),
      tabStopsInCells: stops.filter((s) => inside(s, CELL) && inside(s, TABLE)).length,
      listItems: items.length,
      largestList: biggest(lists, ITEM),
      nestedLists: lists.filter((l) => l.parentElement && l.parentElement.closest(ITEM) && l.parentElement.closest(LIST)).length,
      tabStopsInItems: stops.filter((s) => inside(s, ITEM) && inside(s, LIST)).length,
      title: document.title,
    };
  });
  console.log(JSON.stringify({ address, ...counts }));
} finally { await browser.close(); }
