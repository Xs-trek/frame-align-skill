#!/usr/bin/env node
// frame-align page server. No dependencies.
// Usage: node serve.js [state-dir] [--wait SECONDS] [--port N] [--no-open]
// Runs for one round and then stops. It serves the prebuilt page with the
// current state, waits for the user to submit, writes the return to
// <state-dir>/returns/round-N.txt, prints it, and exits. With no return
// inside the wait it says so and exits too. Nothing is left running.
"use strict";
const http = require("http"), fs = require("fs"), path = require("path"), crypto = require("crypto");

let dir = ".frame-align", port = 0, wait = 540, open = true;
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--port") port = parseInt(args[++i], 10);
  else if (args[i] === "--wait") wait = parseFloat(args[++i]);
  else if (args[i] === "--no-open") open = false;
  else dir = args[i];
}
dir = path.resolve(dir);
// The wait is always finite: nine minutes unless told otherwise, an hour at most.
wait = Math.min(wait > 0 ? wait : 540, 3600);
const pageFile = path.join(__dirname, "..", "assets", "page.html");
const stateFile = path.join(dir, "state.js");
const returnsDir = path.join(dir, "returns");
const serverFile = path.join(dir, "server.json");
const MAX_BODY = 1024 * 1024, TEXT = "text/plain; charset=utf-8";
const started = Date.now();

// The address and the key stay the same from one run to the next, so a page
// left open can reach the next run and no other project's server. Each
// project starts from a port of its own, so two projects rarely meet.
let known = {};
try { known = JSON.parse(fs.readFileSync(serverFile, "utf8")) || {}; } catch (e) {}
const key = /^[0-9a-f]{32}$/.test(known.key || "") ? known.key : crypto.randomBytes(16).toString("hex");
let h = 0;
for (const c of dir.toLowerCase()) h = (h * 31 + c.charCodeAt(0)) >>> 0;
const first = known.port > 0 ? known.port : 4173 + h % 200;
const ports = port > 0 ? [port] : [];
for (let p = first; p <= first + 20; p++) if (ports.indexOf(p) < 0) ports.push(p);

let pageSeen = false;
function send(res, code, type, body, headers) {
  res.writeHead(code, Object.assign({ "Content-Type": type, "Cache-Control": "no-store" }, headers || {}));
  res.end(body);
}
// Only the page this server handed out may read the state. Browsers that send
// Sec-Fetch-Site are judged by it; older ones by a cookie that is never sent
// along with requests started by another site.
function fromOwnPage(req, self) {
  const site = req.headers["sec-fetch-site"];
  if (site) return site === "same-origin" || site === "none";
  return (req.headers.cookie || "").split(/;\s*/).indexOf("fa_" + self + "=" + key) >= 0;
}

const server = http.createServer((req, res) => {
  const self = server.address().port, url = req.url.split("?")[0];
  const host = req.headers.host;
  if (host !== "127.0.0.1:" + self && host !== "localhost:" + self) return send(res, 403, TEXT, "forbidden");

  if (req.method === "GET" && (url === "/" || url === "/page.html")) {
    pageSeen = true;
    return fs.readFile(pageFile, (err, data) => err ? send(res, 404, TEXT, "not found")
      : send(res, 200, "text/html; charset=utf-8", data, { "Set-Cookie": "fa_" + self + "=" + key + "; Path=/; HttpOnly; SameSite=Strict" }));
  }
  if (!fromOwnPage(req, self)) return send(res, 403, TEXT, "forbidden");

  if (req.method === "GET" && url === "/state.js") {
    // The page learns which project it belongs to and how fresh its state is.
    return fs.readFile(stateFile, "utf8", (err, data) => {
      if (err) return send(res, 404, TEXT, "not found");
      let stamp = 0; try { stamp = Math.floor(fs.statSync(stateFile).mtimeMs); } catch (e) {}
      send(res, 200, "text/javascript; charset=utf-8", data + "\n;window.FRAME_ALIGN_PAGE=" + JSON.stringify({ id: key, stamp: stamp }) + ";\n");
    });
  }
  // From here on the page must name its project. A page of another project
  // that was left open on this address is turned away.
  if (req.headers["x-fa-id"] !== key) return send(res, 409, TEXT, "this address now serves another project");
  pageSeen = true;

  if (req.method === "POST" && url === "/quit") {
    send(res, 200, TEXT, "ok");
    return finish("frame-align: replaced by a newer run for this project.");
  }
  if (req.method === "POST" && url === "/pause") {
    send(res, 200, TEXT, "ok");
    return finish("frame-align: paused. The user is taking a break. Do not go on. When they are back and say so, run this again.");
  }
  if (req.method === "GET" && url === "/stamp") {
    return fs.stat(stateFile, (err, st) => send(res, 200, "application/json", JSON.stringify({ stamp: err ? 0 : Math.floor(st.mtimeMs) })));
  }
  if (req.method === "POST" && url === "/return") {
    const origin = req.headers.origin;
    if (origin && origin !== "http://127.0.0.1:" + self && origin !== "http://localhost:" + self) return send(res, 403, TEXT, "forbidden");
    const chunks = []; let size = 0;
    req.on("data", c => { size += c.length; if (size > MAX_BODY) req.destroy(); else chunks.push(c); });
    req.on("end", () => {
      const text = Buffer.concat(chunks).toString("utf8");
      const m = /^\[frame-align\] round (\d+)\s*$/.exec(text.split("\n")[0] || "");
      if (!m) return send(res, 400, TEXT, "first line must be: [frame-align] round N");
      const name = "round-" + parseInt(m[1], 10) + ".txt";
      try {
        fs.mkdirSync(returnsDir, { recursive: true });
        fs.writeFileSync(path.join(returnsDir, name), text, "utf8");
      } catch (e) {
        return send(res, 500, TEXT, "could not write the return file");
      }
      res.on("finish", () => finish(returned(name, text)));
      send(res, 200, "application/json", JSON.stringify({ ok: true, file: path.basename(dir) + "/returns/" + name }));
    });
    return;
  }
  send(res, 404, TEXT, "not found");
});

// The run ends when the user submits, or when the wait is over.
let ended = false;
function finish(text) {
  if (ended) return;
  ended = true;
  // Stopping must not depend on anyone still listening to the output.
  setTimeout(() => process.exit(0), 1500);
  try { process.stdout.write(text + "\n", () => process.exit(0)); } catch (e) { process.exit(0); }
}
process.stdout.on("error", () => process.exit(0));
function returned(name, text) {
  return "frame-align return: " + path.basename(dir) + "/returns/" + name + "\n" + text.replace(/\s*$/, "");
}
// The state is checked before anything is shown, so a slip in an edit is
// reported to the agent at once instead of reaching the user as a broken page.
function stateProblem() {
  let src;
  try { src = fs.readFileSync(stateFile, "utf8"); } catch (e) { return "no state.js in " + dir + ". Is this the right folder?"; }
  const m = /^\uFEFF?\s*window\.FRAME_ALIGN_STATE\s*=\s*([\s\S]*?);?\s*$/.exec(src);
  if (!m) return "state.js must start with: window.FRAME_ALIGN_STATE = ";
  try { JSON.parse(m[1]); } catch (e) { return "state.js is not valid JSON after the assignment. " + e.message + "."; }
  return null;
}
// A return for the state now on the page may already be on disk: an earlier
// run took it after the agent had stopped listening. Hand it over at once.
function waitingReturn() {
  try {
    const m = /"round"\s*:\s*(\d+)/.exec(fs.readFileSync(stateFile, "utf8"));
    if (!m) return null;
    const name = "round-" + parseInt(m[1], 10) + ".txt", file = path.join(returnsDir, name);
    if (fs.statSync(file).mtimeMs <= fs.statSync(stateFile).mtimeMs) return null;
    const text = fs.readFileSync(file, "utf8");
    return /^\[frame-align\] round \d+\s*(\n|$)/.test(text) ? returned(name, text) : null;
  } catch (e) { return null; }
}

function openBrowser(url) {
  try {
    const cp = require("child_process");
    const cmd = process.platform === "win32" ? ["cmd", ["/c", "start", "", url]]
      : process.platform === "darwin" ? ["open", [url]] : ["xdg-open", [url]];
    const child = cp.spawn(cmd[0], cmd[1], { stdio: "ignore", detached: true, windowsHide: true });
    child.on("error", () => {});
    child.unref();
  } catch (e) {}
}

// An earlier run for this project may still be waiting on its address.
// The newest run takes over, so there is never more than one.
function takeOver(p, then) {
  let done = false;
  const next = () => { if (!done) { done = true; setTimeout(then, 400); } };
  const req = http.request({ host: "127.0.0.1", port: p, path: "/quit", method: "POST", timeout: 1000,
    headers: { "X-FA-Id": key, "Cookie": "fa_" + p + "=" + key } }, res => { res.resume(); res.on("end", next); });
  req.on("timeout", () => req.destroy());
  req.on("error", next);
  req.end();
}
let n = 0, asked = false;
server.on("error", err => {
  if (err.code === "EADDRINUSE" && !asked && ports[n] === known.port) {
    asked = true;
    return takeOver(ports[n], () => server.listen(ports[n], "127.0.0.1"));
  }
  if (err.code === "EADDRINUSE" && ++n < ports.length) return server.listen(ports[n], "127.0.0.1");
  console.error("frame-align: could not start the page server: " + err.message);
  process.exit(1);
});
server.on("listening", () => {
  const self = server.address().port, url = "http://127.0.0.1:" + self + "/";
  if (!(known.port > 0) || known.key !== key) {
    try { fs.writeFileSync(serverFile, JSON.stringify({ port: known.port > 0 ? known.port : self, key: key }) + "\n", "utf8"); }
    catch (e) { console.error("frame-align: could not write " + serverFile + ". Is this the right folder? " + dir); }
  }
  console.log("frame-align page: " + url);
  setTimeout(() => finish("frame-align: no return yet. The page server has stopped. Run this again when the user is back."), wait * 1000);
  // A page left open from the last round finds this server by itself.
  // Only when none shows up is a new one opened. The first run opens at once.
  if (open) setTimeout(() => { if (!pageSeen) openBrowser(url); }, known.key ? 8000 : 300);
});
process.on("SIGINT", () => process.exit(0));
process.on("SIGTERM", () => process.exit(0));
const problem = stateProblem();
if (problem) { console.error("frame-align: " + problem + " Fix it and run this again."); process.exit(1); }
const already = waitingReturn();
if (already) finish("frame-align page: http://127.0.0.1:" + ports[0] + "/\n" + already);
else server.listen(ports[0], "127.0.0.1");
