#!/usr/bin/env python3
"""frame-align page server. Standard library only.

Usage: python serve.py [state-dir] [--port N]
Serves the prebuilt page with the current state, and writes each submitted
return to <state-dir>/returns/round-N.txt for the agent to read.
"""
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

state_dir, port = ".frame-align", 4173
args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == "--port":
        i += 1
        port = int(args[i])
    else:
        state_dir = args[i]
    i += 1
state_dir = os.path.abspath(state_dir)
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "page.html")
STATE = os.path.join(state_dir, "state.js")
RETURNS = os.path.join(state_dir, "returns")
IDLE_SECONDS = 12 * 60 * 60
MAX_BODY = 1024 * 1024
FIRST_LINE = re.compile(r"^\[frame-align\] round (\d+)\s*$")

idle = None


def touch():
    global idle
    if idle:
        idle.cancel()
    idle = threading.Timer(IDLE_SECONDS, lambda: os._exit(0))
    idle.daemon = True
    idle.start()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, ctype, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def reply_file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                self.reply(200, ctype, f.read())
        except OSError:
            self.reply(404, "text/plain; charset=utf-8", "not found")

    def do_GET(self):
        touch()
        url = self.path.split("?")[0]
        if url in ("/", "/page.html"):
            return self.reply_file(PAGE, "text/html; charset=utf-8")
        if url == "/state.js":
            return self.reply_file(STATE, "text/javascript; charset=utf-8")
        if url == "/stamp":
            try:
                stamp = os.stat(STATE).st_mtime * 1000
            except OSError:
                stamp = 0
            return self.reply(200, "application/json", json.dumps({"stamp": stamp}))
        self.reply(404, "text/plain; charset=utf-8", "not found")

    def do_POST(self):
        touch()
        if self.path.split("?")[0] != "/return":
            return self.reply(404, "text/plain; charset=utf-8", "not found")
        own = self.server.server_address[1]
        origin = self.headers.get("Origin")
        if origin and origin not in ("http://127.0.0.1:%d" % own, "http://localhost:%d" % own):
            return self.reply(403, "text/plain; charset=utf-8", "forbidden")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self.reply(413, "text/plain; charset=utf-8", "too large")
        text = self.rfile.read(length).decode("utf-8", "replace")
        m = FIRST_LINE.match(text.split("\n")[0] if text else "")
        if not m:
            return self.reply(400, "text/plain; charset=utf-8", "first line must be: [frame-align] round N")
        name = "round-%d.txt" % int(m.group(1))
        try:
            os.makedirs(RETURNS, exist_ok=True)
            with open(os.path.join(RETURNS, name), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        except OSError:
            return self.reply(500, "text/plain; charset=utf-8", "could not write the return file")
        self.reply(200, "application/json", json.dumps({"ok": True, "file": os.path.basename(state_dir) + "/returns/" + name}))


server = None
for attempt in range(21):
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port + attempt), Handler)
        break
    except OSError:
        continue
if server is None:
    sys.stderr.write("frame-align: could not start the page server\n")
    sys.exit(1)
print("frame-align page: http://127.0.0.1:%d/" % server.server_address[1], flush=True)
touch()
server.serve_forever()
