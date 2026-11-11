#!/usr/bin/env python3
"""frame-align page server. Standard library only.

Usage: python serve.py [state-dir] [--port N]
Serves the prebuilt page with the current state, and writes each submitted
return to <state-dir>/returns/round-N.txt for the agent to read.
Starting it again for the same state-dir reuses the server already running.
"""
import atexit
import datetime
import json
import os
import re
import secrets
import signal
import sys
import threading
import urllib.request
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
SERVER_FILE = os.path.join(state_dir, "server.json")
IDLE_SECONDS = 12 * 60 * 60
MAX_BODY = 1024 * 1024
FIRST_LINE = re.compile(r"^\[frame-align\] round (\d+)\s*$")
TOKEN = secrets.token_hex(16)
TEXT = "text/plain; charset=utf-8"

idle = None


def same_path(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def cleanup():
    try:
        with open(SERVER_FILE, encoding="utf-8") as f:
            if json.load(f).get("pid") == os.getpid():
                os.remove(SERVER_FILE)
    except (OSError, ValueError):
        pass


def stop(*_):
    cleanup()
    os._exit(0)


def touch():
    global idle
    if idle:
        idle.cancel()
    idle = threading.Timer(IDLE_SECONDS, stop)
    idle.daemon = True
    idle.start()


class Server(ThreadingHTTPServer):
    # On Windows, address reuse would let two servers share one port.
    allow_reuse_address = os.name != "nt"
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, ctype, body, headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def reply_file(self, path, ctype, headers=None):
        try:
            with open(path, "rb") as f:
                self.reply(200, ctype, f.read(), headers)
        except OSError:
            self.reply(404, TEXT, "not found")

    def own_port(self):
        return self.server.server_address[1]

    def host_ok(self):
        own = self.own_port()
        return self.headers.get("Host") in ("127.0.0.1:%d" % own, "localhost:%d" % own)

    def from_own_page(self):
        # Only the page this server handed out may read the state or submit a
        # return. Browsers that send Sec-Fetch-Site are judged by it; older
        # ones by a cookie that is never sent with another site's requests.
        site = self.headers.get("Sec-Fetch-Site")
        if site:
            return site in ("same-origin", "none")
        cookies = re.split(r";\s*", self.headers.get("Cookie") or "")
        return "fa_%d=%s" % (self.own_port(), TOKEN) in cookies

    def do_GET(self):
        if not self.host_ok():
            return self.reply(403, TEXT, "forbidden")
        url = self.path.split("?")[0]
        if url in ("/", "/page.html"):
            touch()
            cookie = "fa_%d=%s; Path=/; HttpOnly; SameSite=Strict" % (self.own_port(), TOKEN)
            return self.reply_file(PAGE, "text/html; charset=utf-8", {"Set-Cookie": cookie})
        if url == "/health":
            return self.reply(200, "application/json", json.dumps({"app": "frame-align", "dir": state_dir}))
        if not self.from_own_page():
            return self.reply(403, TEXT, "forbidden")
        if url == "/state.js":
            touch()
            return self.reply_file(STATE, "text/javascript; charset=utf-8")
        if url == "/stamp":
            # Polling from an open page does not count as activity.
            try:
                stamp = os.stat(STATE).st_mtime * 1000
            except OSError:
                stamp = 0
            return self.reply(200, "application/json", json.dumps({"stamp": stamp}))
        self.reply(404, TEXT, "not found")

    def do_POST(self):
        if not self.host_ok() or not self.from_own_page():
            return self.reply(403, TEXT, "forbidden")
        if self.path.split("?")[0] != "/return":
            return self.reply(404, TEXT, "not found")
        touch()
        own = self.own_port()
        origin = self.headers.get("Origin")
        if origin and origin not in ("http://127.0.0.1:%d" % own, "http://localhost:%d" % own):
            return self.reply(403, TEXT, "forbidden")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self.reply(413, TEXT, "too large")
        text = self.rfile.read(length).decode("utf-8", "replace")
        m = FIRST_LINE.match(text.split("\n")[0] if text else "")
        if not m:
            return self.reply(400, TEXT, "first line must be: [frame-align] round N")
        name = "round-%d.txt" % int(m.group(1))
        try:
            os.makedirs(RETURNS, exist_ok=True)
            with open(os.path.join(RETURNS, name), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        except OSError:
            return self.reply(500, TEXT, "could not write the return file")
        self.reply(200, "application/json", json.dumps({"ok": True, "file": os.path.basename(state_dir) + "/returns/" + name}))


# Reuse a server that is already running for this state-dir.
try:
    with open(SERVER_FILE, encoding="utf-8") as f:
        known = json.load(f).get("url") or ""
    if re.match(r"^http://127\.0\.0\.1:\d+/$", known):
        with urllib.request.urlopen(known + "health", timeout=1) as r:
            info = json.loads(r.read().decode("utf-8"))
        if info.get("app") == "frame-align" and same_path(info.get("dir", ""), state_dir):
            print("frame-align page: " + known, flush=True)
            print("frame-align: already running, reusing it.", flush=True)
            sys.exit(0)
except (OSError, ValueError):
    pass

server = None
for attempt in range(21):
    try:
        server = Server(("127.0.0.1", port + attempt), Handler)
        break
    except OSError:
        continue
if server is None:
    sys.stderr.write("frame-align: could not start the page server\n")
    sys.exit(1)

url = "http://127.0.0.1:%d/" % server.server_address[1]
try:
    with open(SERVER_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"url": url, "pid": os.getpid(), "dir": state_dir,
                   "started": datetime.datetime.now(datetime.timezone.utc).isoformat()}, f)
        f.write("\n")
except OSError:
    sys.stderr.write("frame-align: could not write %s. Is this the right folder? %s\n" % (SERVER_FILE, state_dir))
if not os.path.exists(STATE):
    sys.stderr.write("frame-align: no state.js in %s yet. The page stays empty until it is written.\n" % state_dir)
print("frame-align page: " + url, flush=True)

atexit.register(cleanup)
signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
touch()
try:
    server.serve_forever()
except KeyboardInterrupt:
    stop()
