"""Μικρός βοηθός για έλεγχο του site σε πραγματικό Chrome (headless), μόνο με βασική Python.

Χρησιμοποιείται από τα measure_sizes.py και check_browser.py. Σερβίρει το docs/ τοπικά και μιλά στο Chrome
με το DevTools Protocol. Δεν εγκαθιστά τίποτα· χρειάζεται μόνο εγκατεστημένο Google Chrome.
"""
import base64, contextlib, functools, http.server, json, os, socket, struct, subprocess, tempfile, threading, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DOCS = os.environ.get('SYNOIDA_DOCS') or os.path.join(ROOT, 'docs')   # άλλος φάκελος εξόδου για δοκιμές: SYNOIDA_DOCS=/διαδρομή
CHROME_PATHS = ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                '/Applications/Chromium.app/Contents/MacOS/Chromium', '/usr/bin/google-chrome', '/usr/bin/chromium')
PAGES = [p[:-5] for p in json.load(open(os.path.join(ROOT, '_build', 'pages.json'), encoding='utf-8'))]


class WS:
    """Ελάχιστος WebSocket client για το DevTools Protocol."""

    def __init__(self, url):
        host, rest = url[len('ws://'):].split('/', 1)
        h, p = host.split(':')
        self.s = socket.create_connection((h, int(p)))
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f'GET /{rest} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                        f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        buf = b''
        while b'\r\n\r\n' not in buf:
            buf += self.s.recv(4096)
        self.buf = buf.split(b'\r\n\r\n', 1)[1]
        self.i = 0
        self.events = []

    def _recv(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(1 << 20)
            if not chunk:
                raise EOFError
            self.buf += chunk
        d, self.buf = self.buf[:n], self.buf[n:]
        return d

    def _read(self):
        payload = b''
        while True:
            b1, b2 = self._recv(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack('>H', self._recv(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._recv(8))[0]
            payload += self._recv(n)
            if b1 & 0x80:
                return json.loads(payload)

    def send(self, method, params=None):
        self.i += 1
        data = json.dumps({'id': self.i, 'method': method, 'params': params or {}}).encode()
        hdr = bytearray([0x81]); n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126); hdr += struct.pack('>H', n)
        else:
            hdr.append(0x80 | 127); hdr += struct.pack('>Q', n)
        mask = os.urandom(4)
        self.s.sendall(bytes(hdr) + mask + bytes(b ^ mask[k % 4] for k, b in enumerate(data)))
        want = self.i
        while True:
            msg = self._read()
            if msg.get('id') == want:
                if 'error' in msg:
                    raise RuntimeError(msg['error'])
                return msg.get('result', {})
            if 'method' in msg:
                self.events.append(msg)

    def js(self, expr):
        r = self.send('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
        if r.get('exceptionDetails'):
            raise RuntimeError(json.dumps(r['exceptionDetails'])[:500])
        return r.get('result', {}).get('value')

    def viewport(self, width, height=None, dpr=1):
        mobile = width < 700
        self.send('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height or (844 if mobile else 900), 'deviceScaleFactor': dpr, 'mobile': mobile})
        self.send('Emulation.setTouchEmulationEnabled', {'enabled': mobile})

    def open(self, url, settle=1.2):
        self.events.clear()
        self.send('Page.navigate', {'url': url})
        time.sleep(0.4)
        t0 = time.time()
        while time.time() - t0 < 45:
            try:
                if self.js('document.readyState') == 'complete':
                    break
            except RuntimeError:
                pass
            time.sleep(0.2)
        self.js('document.fonts.ready.then(()=>1)')
        time.sleep(settle)

    def scroll_through(self, pause=0.3):
        """Κυλά όλη τη σελίδα (ξυπνά lazy εικόνες και εφέ) και γυρίζει στην κορυφή."""
        total = self.js('document.documentElement.scrollHeight'); vh = self.js('innerHeight'); y = 0
        while y < total:
            self.js('window.scrollTo({top:%d,behavior:"instant"});1' % y); time.sleep(pause); y += int(vh * 0.7)
        self.js('window.scrollTo({top:document.documentElement.scrollHeight,behavior:"instant"});1'); time.sleep(pause * 2)

    def screenshot(self, path, quality=75):
        r = self.send('Page.captureScreenshot', {'format': 'jpeg', 'quality': quality})
        open(path, 'wb').write(base64.b64decode(r['data']))


def site_prefix(docs=None):
    """Το πρόθεμα διαδρομής του site (π.χ. /synoida-site-fable-5.2/), όπως το γράφει το <base> του 404.html."""
    import re
    try:
        m = re.search(r'<base href="([^"]+)"', open(os.path.join(docs or DOCS, '404.html'), encoding='utf-8').read())
        return m.group(1) if m else '/'
    except OSError:
        return '/'


class _Quiet(http.server.SimpleHTTPRequestHandler):
    """Σερβίρει το docs/ και στη ρίζα και κάτω από το πρόθεμα του site, και δίνει το 404.html για ό,τι δεν υπάρχει (όπως το GitHub Pages)."""
    prefix = '/'

    def log_message(self, *a):
        pass

    def translate_path(self, path):
        if self.prefix != '/' and path.startswith(self.prefix):
            path = '/' + path[len(self.prefix):]
        return super().translate_path(path)

    def send_error(self, code, message=None, explain=None):
        page = os.path.join(self.directory, '404.html')
        if code == 404 and os.path.exists(page):
            data = open(page, 'rb').read()
            self.send_response(404); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
            return
        super().send_error(code, message, explain)


@contextlib.contextmanager
def session(docs=DOCS):
    """Σερβίρει το docs/ σε ελεύθερη θύρα και ανοίγει headless Chrome. Δίνει (ws, base_url)."""
    chrome = next((c for c in CHROME_PATHS if os.path.exists(c)), None)
    if not chrome:
        raise SystemExit('Δεν βρέθηκε Google Chrome.')
    _Quiet.prefix = site_prefix(docs)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(_Quiet, directory=docs))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    prof = tempfile.mkdtemp(prefix='synoida-chrome-')
    proc = subprocess.Popen([chrome, '--headless=new', '--remote-debugging-port=%d' % port, '--user-data-dir=' + prof, '--no-first-run',
                             '--hide-scrollbars', '--window-size=1440,900', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        page = None
        for _ in range(80):
            try:
                tabs = json.load(urllib.request.urlopen('http://127.0.0.1:%d/json' % port))
                page = next(t for t in tabs if t['type'] == 'page'); break
            except Exception:
                time.sleep(0.25)
        if not page:
            raise SystemExit('Το Chrome δεν ξεκίνησε.')
        ws = WS(page['webSocketDebuggerUrl'])
        for m in ('Page.enable', 'Runtime.enable', 'Network.enable', 'Log.enable'):
            ws.send(m)
        ws.send('Network.setCacheDisabled', {'cacheDisabled': True})
        yield ws, 'http://127.0.0.1:%d/' % srv.server_address[1]
    finally:
        proc.terminate(); srv.shutdown()
