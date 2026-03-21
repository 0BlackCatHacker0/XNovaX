import http.server,json,base64,os
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n=int(self.headers.get('Content-Length',0))
        d=json.loads(self.rfile.read(n))
        p=d.get('path','')
        c=d.get('content','')
        b=d.get('b64',False)
        os.makedirs(os.path.dirname(p),exist_ok=True)
        if b:
            open(p,'wb').write(base64.b64decode(c))
        else:
            open(p,'w',encoding='utf-8').write(c)
        sz=os.path.getsize(p)
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
        self.wfile.write(json.dumps({'ok':True,'size':sz,'path':p}).encode())
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','POST')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.end_headers()
    def log_message(self,*a):pass
s=http.server.HTTPServer(('0.0.0.0',9801),H)
print('Deploy server on :9801')
s.serve_forever()
