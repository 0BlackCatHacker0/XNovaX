$f='C:\ProgramData\NovaX\app\shell\static\servers.html'
$c=Get-Content $f -Raw -Encoding UTF8
# Remove old misplaced cards (outside grid)
$c=$c -replace '<div class="card" id="card-redis">[\s\S]*?</div>\s*</div>',''
$c=$c -replace '<div class="card" id="card-meili">[\s\S]*?</div>\s*</div>',''
$c=$c -replace '<div class="card" id="card-caddy">[\s\S]*?</div>\s*</div>',''
$c=$c -replace '<div class="card" id="card-relay">[\s\S]*?</div>\s*</div>',''
$c=$c -replace '<!-- NEW SERVERS[\s\S]*?-->',''
# Find last </div> before </main> or </body> — that's the grid close
# Insert new cards right before the CUDA card's parent closing div
if($c -notmatch 'card-redis'){
$nc='<div class="card" id="card-redis"><div class="card-name">Redis Cache</div><div class="card-status st-offline">CHECKING</div><p>Cache, sessions, pub/sub</p><p>Port: 6379</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>'
$nc+='<div class="card" id="card-meili"><div class="card-name">Meilisearch</div><div class="card-status st-offline">CHECKING</div><p>Full-text search engine</p><p>Port: 7700</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>'
$nc+='<div class="card" id="card-caddy"><div class="card-name">Caddy Proxy</div><div class="card-status st-offline">CHECKING</div><p>Unified reverse proxy</p><p>Port: 8080</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>'
$nc+='<div class="card" id="card-relay"><div class="card-name">Nova Relay</div><div class="card-status st-offline">CHECKING</div><p>File/exec API (9 endpoints)</p><p>Port: 9877</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>'
# Insert before the closing of server-grid div
$c=$c -replace '(id="server-grid"[\s\S]*?)(</div>\s*</main>)',"\$1$nc\$2"
if($c -notmatch 'card-redis'){
# Fallback: insert before </main>
$c=$c -replace '</main>',"$nc</main>"
}
}
Set-Content -Path $f -Value $c -Encoding UTF8
echo FIXED