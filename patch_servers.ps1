$f='C:\ProgramData\NovaX\app\shell\static\servers.html'
$c=Get-Content $f -Raw -Encoding UTF8
# Remove old health script injection
$c=$c -replace '(?s)<script>\s*async function healthCheck.*?</script>',''
# Build health script
$hs='<script>'
$hs+='async function nh(){'
$hs+='var nc={Bridge:"http://localhost:9999/api/status",Ollama:"http://localhost:11434/api/tags","9990":"http://localhost:9990/status",Redis:null,Meilisearch:"http://localhost:7700/health",Caddy:"http://localhost:8080/",Relay:"http://localhost:9877/status"};'
$hs+='var g=document.getElementById("server-grid");if(!g)return;'
$hs+='for(var c of g.querySelectorAll(".card")){'
$hs+='var n=c.querySelector(".card-name");if(!n)continue;'
$hs+='var b=c.querySelector(".card-status");if(!b)continue;'
$hs+='var nm=n.textContent,url=null,ok=false;'
$hs+='for(var k in nc){if(nm.indexOf(k)>=0){url=nc[k];ok=true;break;}}'
$hs+='if(!ok)continue;'
$hs+='if(url===null){b.textContent="ONLINE";b.className="card-status st-online";continue;}'
$hs+='try{await fetch(url,{signal:AbortSignal.timeout(2000)});b.textContent="ONLINE";b.className="card-status st-online";}'
$hs+='catch(e){b.textContent="OFFLINE";b.className="card-status st-offline";}}'
$hs+='}nh();setInterval(nh,10000);'
$hs+='</script>'
$c=$c -replace '</body>',"$hs</body>"
Set-Content -Path $f -Value $c -Encoding UTF8
echo DONE