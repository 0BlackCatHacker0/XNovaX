$f='C:\ProgramData\NovaX\app\shell\static\servers.html'
$c=Get-Content $f -Raw -Encoding UTF8
$c=$c -replace '(?s)<div class="server-card"[^>]*>[\s\S]*?</div>[\s\S]*?</div>[\s\S]*?</div>',''
$c=$c -replace '(?s)<!-- NEW SERVERS[\s\S]*?</div>\s*</div>\s*</div>',''
if($c -notmatch 'card-redis'){
$nc='<div class="card" id="card-redis"><div class="card-name">Redis Cache</div><div class="card-status st-offline">CHECKING</div><p>Cache sessions pub/sub</p><p>Port: 6379</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>'
$nc+='<div class="card" id="card-meili"><div class="card-name">Meilisearch</div><div class="card-status st-offline">CHECKING</div><p>Full-text search engine</p><p>Port: 7700</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>'
$nc+='<div class="card" id="card-caddy"><div class="card-name">Caddy Proxy</div><div class="card-status st-offline">CHECKING</div><p>Unified reverse proxy</p><p>Port: 8080</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>'
$nc+='<div class="card" id="card-relay"><div class="card-name">Nova Relay</div><div class="card-status st-offline">CHECKING</div><p>File exec API 9 endpoints</p><p>Port: 9877</p><div class="progress-bar"><div class="progress"></div></div><div class="actions"></div></div>'
$c=$c -replace '(</div>\s*)</body>',"$nc`$1</body>"
}
Set-Content -Path $f -Value $c -Encoding UTF8
echo CARDS_DONE
