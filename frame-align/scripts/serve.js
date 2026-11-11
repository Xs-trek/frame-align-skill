#!/usr/bin/env node
// frame-align page server. No dependencies.
// Usage: node serve.js [state-dir] [--port N]
// Serves the prebuilt page with the current state, and writes each submitted
// return to <state-dir>/returns/round-N.txt for the agent to read.
// Starting it again for the same state-dir reuses the server already running.
"use strict";
const http = require("http"), fs = require("fs"), path = require("path"), crypto = require("crypto");

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
const serverFile = path.join(dir, "server.json");
const IDLE_MS = 12 * 60 * 60 * 1000;
const MAX_BODY = 1024 * 1024;
const token = crypto.randomBytes(16).toString("hex");

let idle;
function touch() { clearTimeout(idle); idle = setTimeout(() => process.exit(0), IDLE_MS); }
function samePath(a, b) {
  a = path.resolve(a); b = path.resolve(b);
  return process.platform === "win32" ? a.toLowerCase() === b.toLowerCase() : a === b;
}

function send(res, code, type, body, headers) {
  res.writeHead(code, Object.assign({ "Content-Type": type, "Cache-Control": "no-store" }, headers || {}));
  res.end(body);
}
function sendFile(res, file, type, headers) {
  fs.readFile(file, (err, data) => err ? send(res, 404, "text/plain; charset=utf-8", "not found") : send(res, 200, type, data, headers));
}
// Only the page this server handed out may read the state or submit a return.
// Browsers that send Sec-Fetch-Site are judged by it; older ones by a cookie
// that is never sent along with requests started by another site.
function fromOwnPage(req, self) {
  const site = req.headers["sec-fetch-site"];
  if (site) return site === "same-origin" || site === "none";
  return (req.headers.cookie || "").split(/;\s*/).indexOf("fa_" + self + "=" + token) >= 0;
}

const server = http.createServer((req, res) => {
  const self = server.address().port, url = req.url.split("?")[0];
  const host = req.headers.host;
  if (host !== "127.0.0.1:" + self && host !== "localhost:" + self) return send(res, 403, "text/plain; charset=utf-8", "forbidden");

  if (req.method === "GET" && (url === "/" || url === "/page.html")) {
    touch();
    return sendFile(res, pageFile, "text/html; charset=utf-8", { "Set-Cookie": "fa_" + self + "=" + token + "; Path=/; HttpOnly; SameSite=Strict" });
  }
  if (req.method === "GET" && url === "/health") return send(res, 200, "application/json", JSON.stringify({ app: "frame-align", dir: dir }));

  if (!fromOwnPage(req, self)) return send(res, 403, "text/plain; charset=utf-8", "forbidden");

  if (req.method === "GET" && url === "/state.js") { touch(); return sendFile(res, stateFile, "text/javascript; charset=utf-8"); }
  if (req.method === "GET" && url === "/stamp") {
    // Polling from an open page does not count as activity.
    return fs.stat(stateFile, (err, st) => send(res, 200, "application/json", JSON.stringify({ stamp: err ? 0 : st.mtimeMs })));
  }
  if (req.method === "POST" && url === "/return") {
    touch();
    const origin = req.headers.origin;
    if (origin && origin !== "http://127.0.0.1:" + self && origin !== "http://localhost:" + self) {
      return send(res, 403, "text/plain; charset=utf-8", "forbidden");
    }
    const chunks = []; let size = 0;
    req.on("data", c => { size += c.length; if (size > MAX_BODY) req.destroy(); else chunks.push(c); });
    req.on("end", () => {
      const text = Buffer.concat(chunks).toString("utf8");
      const m = /^\[frame-align\] round (\d+)\s*$/.exec(text.split("\n")[0] || "");
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
  const url = "http://127.0.0.1:" + server.address().port + "/";
  try {
    fs.writeFileSync(serverFile, JSON.stringify({ url: url, pid: process.pid, dir: dir, started: new Date().toISOString() }) + "\n", "utf8");
  } catch (e) {
    console.error("frame-align: could not write " + serverFile + ". Is this the right folder? " + dir);
  }
  if (!fs.existsSync(stateFile)) console.error("frame-align: no state.js in " + dir + " yet. The page stays empty until it is written.");
  console.log("frame-align page: " + url);
  touch();
});
process.on("exit", () => {
  try { if (JSON.parse(fs.readFileSync(serverFile, "utf8")).pid === process.pid) fs.unlinkSync(serverFile); } catch (e) {}
});
process.on("SIGINT", () => process.exit(0));
process.on("SIGTERM", () => process.exit(0));

// Reuse a server that is already running for this state-dir.
let started = false;
function start() { if (!started) { started = true; server.listen(port, "127.0.0.1"); } }
let known = null;
try { known = JSON.parse(fs.readFileSync(serverFile, "utf8")); } catch (e) {}
if (known && /^http:\/\/127\.0\.0\.1:\d+\/$/.test(known.url || "")) {
  const probe = http.get(known.url + "health", { timeout: 1000 }, res => {
    let body = "";
    res.on("data", c => { body += c; });
    res.on("end", () => {
      try {
        const j = JSON.parse(body);
        if (j.app === "frame-align" && samePath(j.dir, dir)) {
          console.log("frame-align page: " + known.url);
          console.log("frame-align: already running, reusing it.");
          process.exit(0);
        }
      } catch (e) {}
      start();
    });
  });
  probe.on("timeout", () => probe.destroy());
  probe.on("error", start);
} else {
  start();
}
