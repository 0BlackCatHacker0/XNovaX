
f = r'C:\ProgramData\NovaX\app\shell\static\servers.html'
with open(f, 'r', encoding='utf-8') as fh:
    c = fh.read()

# Step 1: Find server-grid opening tag
grid_start = c.find('id="server-grid"')
if grid_start < 0:
    print('NO GRID')
    exit()

# Find the > that closes the grid opening tag
tag_end = c.find('>', grid_start) + 1

# Step 2: Count div depth to find grid's closing </div>
depth = 1
i = tag_end
grid_close = -1
while i < len(c) and depth > 0:
    # Find next <div or </div>
    next_open = c.find('<div', i)
    next_close = c.find('</div>', i)
    if next_close < 0:
        break
    if next_open >= 0 and next_open < next_close:
        depth += 1
        i = next_open + 4
    else:
        depth -= 1
        if depth == 0:
            grid_close = next_close
            break
        i = next_close + 6

if grid_close < 0:
    print('GRID CLOSE NOT FOUND')
    exit()

print(f'Grid closes at pos {grid_close}')

# Step 3: New cards
nc = '''
<div class="card" id="card-redis"><div class="card-name">Redis Cache</div><div class="card-status st-offline">OFFLINE</div><p>Cache, sessions, pub/sub</p><p>Port: 6379</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>
<div class="card" id="card-meili"><div class="card-name">Meilisearch</div><div class="card-status st-offline">OFFLINE</div><p>Full-text search engine</p><p>Port: 7700</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>
<div class="card" id="card-caddy"><div class="card-name">Caddy Proxy</div><div class="card-status st-offline">OFFLINE</div><p>Unified reverse proxy</p><p>Port: 8080</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>
<div class="card" id="card-relay"><div class="card-name">Nova Relay</div><div class="card-status st-offline">OFFLINE</div><p>File/exec API (9 endpoints)</p><p>Port: 9877</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>
'''

# Insert cards before grid close
c = c[:grid_close] + nc + c[grid_close:]
print('Cards inserted inside grid')

# Step 4: Health check script
hs = """<script>
async function nh(){
var g=document.getElementById('server-grid');if(!g)return;
var checks={'Bridge':'http://localhost:9999/api/status','Ollama':'http://localhost:11434/api/tags','9990':'http://localhost:9990/status','Redis':null,'Meilisearch':'http://localhost:7700/health','Caddy':'http://localhost:8080/','Relay':'http://localhost:9877/status'};
for(var card of g.querySelectorAll('.card')){
var nd=card.querySelector('.card-name');if(!nd)continue;
var b=card.querySelector('.card-status');if(!b)continue;
var nm=nd.textContent,url=null,found=false;
for(var k in checks){if(nm.indexOf(k)>=0){url=checks[k];found=true;break;}}
if(!found)continue;
if(url===null){b.textContent='ONLINE';b.className='card-status st-online';continue;}
try{await fetch(url,{signal:AbortSignal.timeout(2000)});b.textContent='ONLINE';b.className='card-status st-online';}
catch(e){b.textContent='OFFLINE';b.className='card-status st-offline';}
}}
nh();setInterval(nh,10000);
</script>"""

# Remove any existing health scripts
import re
c = re.sub(r'<script>\s*async function nh\(\)[\s\S]*?</script>', '', c)

# Add before </body>
c = c.replace('</body>', hs + '\n</body>')
print('Health check added')

with open(f, 'w', encoding='utf-8') as fh:
    fh.write(c)
print('SAVED')
