#!/usr/bin/env node
// frame-align page server. No dependencies.
// Usage: node serve.js [state-dir] [--port N]
// Serves the prebuilt page with the current state, and writes each submitted
// return to <state-dir>/returns/round-N.txt for the agent to read.
"use strict";
const http = require("http"), fs = require("fs"), path = require("path");

let dir = ".frame-align", port = 4173;
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--port") port = parseInt(args[++i], 10);
  else dir = args[i];
}
dir = path.resolve(dir);
const pageFile = path.join(__dirname, "..", "assets", "page.html");
const stateFile = path.join(dir, "state.js");
const returnsDir = path.join(dir, "returns");
const IDLE_MS = 12 * 60 * 60 * 1000;
const MAX_BODY = 1024 * 1024;

let idle;
function touch() { clearTimeout(idle); idle = setTimeout(() => process.exit(0), IDLE_MS); }

function send(res, code, type, body) {
  res.writeHead(code, { "Content-Type": type, "Cache-Control": "no-store" });
  res.end(body);
}
function sendFile(res, file, type) {
  fs.readFile(file, (err, data) => err ? send(res, 404, "text/plain; charset=utf-8", "not found") : send(res, 200, type, data));
}

const server = http.createServer((req, res) => {
  touch();
  const url = req.url.split("?")[0];
  if (req.method === "GET" && (url === "/" || url === "/page.html")) return sendFile(res, pageFile, "text/html; charset=utf-8");
  if (req.method === "GET" && url === "/state.js") return sendFile(res, stateFile, "text/javascript; charset=utf-8");
  if (req.method === "GET" && url === "/stamp") {
    return fs.stat(stateFile, (err, st) => send(res, 200, "application/json", JSON.stringify({ stamp: err ? 0 : st.mtimeMs })));
  }
  if (req.method === "POST" && url === "/return") {
    const origin = req.headers.origin, self = server.address().port;
    if (origin && origin !== "http://127.0.0.1:" + self && origin !== "http://localhost:" + self) {
      return send(res, 403, "text/plain; charset=utf-8", "forbidden");
    }
    const chunks = []; let size = 0;
    req.on("data", c => { size += c.length; if (size > MAX_BODY) req.destroy(); else chunks.push(c); });
    req.on("end", () => {
      const text = Buffer.concat(chunks).toString("utf8");
      const m = /^\[frame-align\] round (\d+)\s*$/m.exec(text.split("\n")[0] || "");
      if (!m) return send(res, 400, "text/plain; charset=utf-8", "first line must be: [frame-align] round N");
      const name = "round-" + parseInt(m[1], 10) + ".txt";
      try {
        fs.mkdirSync(returnsDir, { recursive: true });
        fs.writeFileSync(path.join(returnsDir, name), text, "utf8");
      } catch (e) {
        return send(res, 500, "text/plain; charset=utf-8", "could not write the return file");
      }
      send(res, 200, "application/json", JSON.stringify({ ok: true, file: path.basename(dir) + "/returns/" + name }));
    });
    return;
  }
  send(res, 404, "text/plain; charset=utf-8", "not found");
});

let tries = 0;
server.on("error", err => {
  if (err.code === "EADDRINUSE" && tries++ < 20) return server.listen(++port, "127.0.0.1");
  console.error("frame-align: could not start the page server: " + err.message);
  process.exit(1);
});
server.on("listening", () => {
  console.log("frame-align page: http://127.0.0.1:" + server.address().port + "/");
  touch();
});
server.listen(port, "127.0.0.1");
