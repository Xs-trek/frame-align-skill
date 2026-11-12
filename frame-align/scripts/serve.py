#!/usr/bin/env python3
"""frame-align page server. Standard library only.

Usage: python serve.py [state-dir] [--wait SECONDS] [--port N] [--no-open]
Runs for one round and then stops. It serves the prebuilt page with the
current state, waits for the user to submit, writes the return to
<state-dir>/returns/round-N.txt, prints it, and exits. With no return inside
the wait it says so and exits too. Nothing is left running.
"""
import http.client
import json
import os
import re
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

state_dir, port, wait, open_page = ".frame-align", 0, 540.0, True
args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == "--port":
        i += 1
        port = int(args[i])
    elif args[i] == "--wait":
        i += 1
        try:
            wait = float(args[i])
        except (IndexError, ValueError):
            wait = 0
    elif args[i] == "--no-open":
        open_page = False
    else:
        state_dir = args[i]
    i += 1
state_dir = os.path.abspath(state_dir)
# The wait is always finite: nine minutes unless told otherwise, an hour at most.
wait = min(wait if wait > 0 else 540.0, 3600.0)
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "page.html")
STATE = os.path.join(state_dir, "state.js")
RETURNS = os.path.join(state_dir, "returns")
SERVER_FILE = os.path.join(state_dir, "server.json")
MAX_BODY = 1024 * 1024
FIRST_LINE = re.compile(r"^\[frame-align\] round (\d+)\s*$")
TEXT = "text/plain; charset=utf-8"

# The address and the key stay the same from one run to the next, so a page
# left open can reach the next run and no other project's server. Each
# project starts from a port of its own, so two projects rarely meet.
known = {}
try:
    with open(SERVER_FILE, encoding="utf-8") as f:
        known = json.load(f)
    if not isinstance(known, dict):
        known = {}
except (OSError, ValueError):
    pass
KEY = known.get("key") if re.match(r"^[0-9a-f]{32}$", str(known.get("key") or "")) else secrets.token_hex(16)
known_port = known.get("port") if isinstance(known.get("port"), int) and known.get("port") > 0 else 0
h = 0
for ch in state_dir.lower():
    h = (h * 31 + ord(ch)) & 0xFFFFFFFF
first = known_port or 4173 + h % 200
ports = [port] if port > 0 else []
ports += [p for p in range(first, first + 21) if p not in ports]

page_seen = False
lock = threading.Lock()


def say(text):
    # Bytes, so that the console's own encoding never gets in the way.
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def finish(text):
    """The run ends when the user submits, or when the wait is over.
    Stopping must not depend on anyone still listening to the output."""
    with lock:
        try:
            say(text)
        finally:
            os._exit(0)


def returned(name, text):
    return "frame-align return: %s/returns/%s\n%s" % (os.path.basename(state_dir), name, text.rstrip())


def waiting_return():
    """A return for the state now on the page may already be on disk: an
    earlier run took it after the agent had stopped listening."""
    try:
        with open(STATE, encoding="utf-8") as f:
            m = re.search(r'"round"\s*:\s*(\d+)', f.read())
        if not m:
            return None
        name = "round-%d.txt" % int(m.group(1))
        path = os.path.join(RETURNS, name)
        if os.stat(path).st_mtime <= os.stat(STATE).st_mtime:
            return None
        with open(path, encoding="utf-8") as f:
            text = f.read()
        return returned(name, text) if FIRST_LINE.match(text.split("\n")[0]) else None
    except (OSError, ValueError):
        return None


def stamp():
    try:
        return int(os.stat(STATE).st_mtime * 1000)
    except OSError:
        return 0


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
        self.wfile.flush()

    def own_port(self):
        return self.server.server_address[1]

    def host_ok(self):
        own = self.own_port()
        return self.headers.get("Host") in ("127.0.0.1:%d" % own, "localhost:%d" % own)

    def from_own_page(self):
        # Only the page this server handed out may read the state. Browsers
        # that send Sec-Fetch-Site are judged by it; older ones by a cookie
        # that is never sent with another site's requests.
        site = self.headers.get("Sec-Fetch-Site")
        if site:
            return site in ("same-origin", "none")
        cookies = re.split(r";\s*", self.headers.get("Cookie") or "")
        return "fa_%d=%s" % (self.own_port(), KEY) in cookies

    def names_project(self):
        # A page of another project that was left open on this address is
        # turned away.
        global page_seen
        if self.headers.get("X-FA-Id") != KEY:
            self.reply(409, TEXT, "this address now serves another project")
            return False
        page_seen = True
        return True

    def do_GET(self):
        global page_seen
        if not self.host_ok():
            return self.reply(403, TEXT, "forbidden")
        url = self.path.split("?")[0]
        if url in ("/", "/page.html"):
            page_seen = True
            try:
                with open(PAGE, "rb") as f:
                    body = f.read()
            except OSError:
                return self.reply(404, TEXT, "not found")
            cookie = "fa_%d=%s; Path=/; HttpOnly; SameSite=Strict" % (self.own_port(), KEY)
            return self.reply(200, "text/html; charset=utf-8", body, {"Set-Cookie": cookie})
        if not self.from_own_page():
            return self.reply(403, TEXT, "forbidden")
        if url == "/state.js":
            # The page learns which project it belongs to and how fresh its state is.
            try:
                with open(STATE, encoding="utf-8") as f:
                    body = f.read()
            except (OSError, ValueError):
                return self.reply(404, TEXT, "not found")
            body += "\n;window.FRAME_ALIGN_PAGE=%s;\n" % json.dumps({"id": KEY, "stamp": stamp()})
            return self.reply(200, "text/javascript; charset=utf-8", body)
        if not self.names_project():
            return
        if url == "/stamp":
            return self.reply(200, "application/json", json.dumps({"stamp": stamp()}))
        self.reply(404, TEXT, "not found")

    def do_POST(self):
        if not self.host_ok() or not self.from_own_page():
            return self.reply(403, TEXT, "forbidden")
        if not self.names_project():
            return
        if self.path.split("?")[0] == "/quit":
            self.reply(200, TEXT, "ok")
            finish("frame-align: replaced by a newer run for this project.")
        if self.path.split("?")[0] != "/return":
            return self.reply(404, TEXT, "not found")
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
        finish(returned(name, text))


def take_over(p):
    """An earlier run for this project may still be waiting on its address.
    The newest run takes over, so there is never more than one."""
    try:
        conn = http.client.HTTPConnection("127.0.0.1", p, timeout=1)
        conn.request("POST", "/quit", headers={"X-FA-Id": KEY, "Cookie": "fa_%d=%s" % (p, KEY)})
        conn.getresponse().read()
        conn.close()
    except (OSError, http.client.HTTPException):
        pass
    time.sleep(0.4)


already = waiting_return()
if already:
    finish("frame-align page: http://127.0.0.1:%d/\n%s" % (ports[0], already))

server = None
for p in ports:
    try:
        server = Server(("127.0.0.1", p), Handler)
        break
    except OSError:
        if p != known_port:
            continue
    take_over(p)
    try:
        server = Server(("127.0.0.1", p), Handler)
        break
    except OSError:
        continue
if server is None:
    sys.stderr.write("frame-align: could not start the page server\n")
    sys.exit(1)

own_port = server.server_address[1]
url = "http://127.0.0.1:%d/" % own_port
if not known_port or known.get("key") != KEY:
    try:
        with open(SERVER_FILE, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"port": known_port or own_port, "key": KEY}, f)
            f.write("\n")
    except OSError:
        sys.stderr.write("frame-align: could not write %s. Is this the right folder? %s\n" % (SERVER_FILE, state_dir))
if not os.path.exists(STATE):
    sys.stderr.write("frame-align: no state.js in %s yet. The page stays empty until it is written.\n" % state_dir)
say("frame-align page: " + url)


def open_browser():
    # A page left open from the last round finds this server by itself.
    # Only when none shows up is a new one opened. The first run opens at once.
    time.sleep(8 if known.get("key") else 0.3)
    if not page_seen:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass


def give_up():
    finish("frame-align: no return yet. The page server has stopped. Run this again when the user is back.")


# The wait has a timer of its own, so nothing else can hold it up.
timer = threading.Timer(wait, give_up)
timer.daemon = True
timer.start()
if open_page:
    threading.Thread(target=open_browser, daemon=True).start()
try:
    server.serve_forever()
except KeyboardInterrupt:
    os._exit(0)
