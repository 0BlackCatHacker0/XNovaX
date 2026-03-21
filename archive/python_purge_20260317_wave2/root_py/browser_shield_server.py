"""NovaX Browser Shield Service — Python bridge on port 9892"""
import http.server, json, re, sys

class ShieldHandler(http.server.BaseHTTPRequestHandler):
    stats = {'total_scans': 0, 'threats_found': 0, 'downloads_scanned': 0, 'proxy_requests': 0}

    DANGER_PATTERNS = [
        r'coinhive|cryptonight|minero',
        r'\.(tk|ml|ga|cf|gq)/',
        r'eval\s*\(\s*atob',
        r'document\.cookie\s*[+=]',
        r'xn--.*\.(com|net|org|io)'
    ]

    SAFE_DOMAINS = {
        '127.0.0.1','localhost','github.com','gitlab.com','google.com',
        'googleapis.com','anthropic.com','claude.ai','openai.com','huggingface.co',
        'microsoft.com','brave.com','mozilla.org','wikipedia.org','stackoverflow.com',
        'python.org','nodejs.org','rust-lang.org','npmjs.com','pypi.org','crates.io',
        'youtube.com','reddit.com','amazon.com','cloudflare.com','vercel.app',
        'discord.com','twitch.tv','twitter.com','x.com','linkedin.com'
    }

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == '/health':
            self._json({'status':'ok','service':'browser_shield','trit':1})
        elif '/api/security/stats' in self.path:
            self._json({'trit':1,'stats':self.stats})
        else:
            self._json({'trit':1,'service':'browser_shield','version':'1.0.0'})

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}
        if '/api/security/scan' in self.path:
            self.stats['total_scans'] += 1
            self._json(self._scan(body))
        elif '/api/proxy/process' in self.path:
            self.stats['proxy_requests'] += 1
            self._json({'trit':1,'processed':True,'content_length':len(body.get('content','')),'source':body.get('source','unknown')})
        else:
            self._json({'trit':0,'error':'unknown endpoint'})

    def _scan(self, body):
        url = body.get('url','')
        domain = body.get('domain','')
        if body.get('scan_type') == 'download':
            self.stats['downloads_scanned'] += 1
            return self._scan_dl(body)
        if domain in self.SAFE_DOMAINS:
            return {'trit':1,'source':'allowlist','domain':domain,'confidence':1.0}
        for pat in self.DANGER_PATTERNS:
            if re.search(pat, url, re.I):
                self.stats['threats_found'] += 1
                return {'trit':-1,'source':'pattern_match','confidence':0.9}
        parts = domain.split('.')
        if len(parts) > 5:
            return {'trit':0,'source':'excessive_subdomains','confidence':0.6}
        if len(url) > 2000:
            return {'trit':0,'source':'url_length','confidence':0.5}
        if domain.startswith('xn--'):
            self.stats['threats_found'] += 1
            return {'trit':-1,'source':'homograph','confidence':0.85}
        return {'trit':1,'source':'clean','confidence':0.9}

    def _scan_dl(self, body):
        fn = body.get('filename','').lower()
        danger = ['.exe','.bat','.cmd','.ps1','.vbs','.scr','.pif','.msi','.dll','.hta']
        for ext in danger:
            if fn.endswith(ext):
                if fn.count('.') > 1:
                    return {'trit':-1,'source':'double_extension','confidence':0.95}
                return {'trit':0,'source':'dangerous_type','confidence':0.7}
        return {'trit':1,'source':'clean','confidence':0.9}

    def _json(self, data):
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type')

    def log_message(self, fmt, *args):
        pass

if __name__ == '__main__':
    server = http.server.HTTPServer(('127.0.0.1', 9892), ShieldHandler)
    print('[browser_shield] Running on http://127.0.0.1:9892')
    print('[browser_shield] Ternary security active +1')
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('[browser_shield] Shutting down')
        server.shutdown()
