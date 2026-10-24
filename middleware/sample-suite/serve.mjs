// Serves ./pages on the port in $PORT (default 4173): what the `webServer` of playwright.config.ts starts. Static files and nothing else.
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { extname, join, normalize } from "node:path";

const root = join(import.meta.dirname, "pages");
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css" };
createServer((req, res) => {
  const path = normalize(new URL(req.url, "http://x").pathname).replace(/^(\.\.[/\\])+/, "");
  try {
    const body = readFileSync(join(root, path === "/" ? "index.html" : path));
    res.writeHead(200, { "content-type": types[extname(path)] ?? "application/octet-stream" }); res.end(body);
  } catch { res.writeHead(404); res.end("not found"); }
}).listen(Number(process.env.PORT ?? 4173), "127.0.0.1");
