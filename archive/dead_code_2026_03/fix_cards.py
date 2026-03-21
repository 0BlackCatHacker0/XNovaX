import re
f = r'C:\ProgramData\NovaX\app\shell\static\servers.html'
with open(f, 'r', encoding='utf-8') as fh:
    c = fh.read()

# Remove old misplaced card divs
c = re.sub(r'<div class="card" id="card-redis">[\s\S]*?</div>\s*</div>', '', c)
c = re.sub(r'<div class="card" id="card-meili">[\s\S]*?</div>\s*</div>', '', c)
c = re.sub(r'<div class="card" id="card-caddy">[\s\S]*?</div>\s*</div>', '', c)
c = re.sub(r'<div class="card" id="card-relay">[\s\S]*?</div>\s*</div>', '', c)

# New cards HTML
nc = '''<div class="card" id="card-redis"><div class="card-name">Redis Cache</div><div class="card-status st-offline">CHECKING</div><p>Cache, sessions, pub/sub</p><p>Port: 6379</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>
<div class="card" id="card-meili"><div class="card-name">Meilisearch</div><div class="card-status st-offline">CHECKING</div><p>Full-text search engine</p><p>Port: 7700</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>
<div class="card" id="card-caddy"><div class="card-name">Caddy Proxy</div><div class="card-status st-offline">CHECKING</div><p>Unified reverse proxy</p><p>Port: 8080</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>
<div class="card" id="card-relay"><div class="card-name">Nova Relay</div><div class="card-status st-offline">CHECKING</div><p>File/exec API (9 endpoints)</p><p>Port: 9877</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>'''

if 'card-redis' not in c:
    # Find the closing </div> of server-grid by finding the last card and inserting after it
    # Strategy: find CUDA Toolkit card (last original card), insert after its closing </div></div>
    cuda_match = re.search(r'(CUDA Toolkit.*?</div>\s*</div>)', c, re.DOTALL)
    if cuda_match:
        pos = cuda_match.end()
        c = c[:pos] + '\n' + nc + '\n' + c[pos:]
        print('INSERTED after CUDA')
    else:
        # Fallback: insert before </body>
        c = c.replace('</body>', nc + '\n</body>')
        print('INSERTED before body')

with open(f, 'w', encoding='utf-8') as fh:
    fh.write(c)
print('SAVED')
