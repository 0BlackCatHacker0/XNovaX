const http = require('http');
const https = require('https');
const PORT = 9878;

const PROVIDERS = {
  ollama:     { base: 'http://127.0.0.1:11434', key: null },
  openai:     { base: 'https://api.openai.com/v1', key: process.env.OPENAI_API_KEY || '' },
  anthropic:  { base: 'https://api.anthropic.com/v1', key: process.env.ANTHROPIC_API_KEY || '' },
  groq:       { base: 'https://api.groq.com/openai/v1', key: process.env.GROQ_API_KEY || '' },
  google:     { base: 'https://generativelanguage.googleapis.com/v1beta', key: process.env.GOOGLE_API_KEY || '' },
  openrouter: { base: 'https://openrouter.ai/api/v1', key: process.env.OPENROUTER_API_KEY || '' },
  together:   { base: 'https://api.together.xyz/v1', key: process.env.TOGETHER_API_KEY || '' },
  mistral:    { base: 'https://api.mistral.ai/v1', key: process.env.MISTRAL_API_KEY || '' }
};

const ROUTES = {
  'gpt-4':          { provider:'openai', model:'gpt-4' },
  'gpt-4o':         { provider:'openai', model:'gpt-4o' },
  'gpt-4-turbo':    { provider:'openai', model:'gpt-4-turbo' },
  'gpt-3.5-turbo':  { provider:'openai', model:'gpt-3.5-turbo' },
  'o1-preview':     { provider:'openai', model:'o1-preview' },
  'o1-mini':        { provider:'openai', model:'o1-mini' },
  'claude-opus':    { provider:'anthropic', model:'claude-3-opus-20240229' },
  'claude-sonnet':  { provider:'anthropic', model:'claude-3-5-sonnet-20241022' },
  'claude-haiku':   { provider:'anthropic', model:'claude-3-haiku-20240307' },
  'groq-llama70b':  { provider:'groq', model:'llama-3.1-70b-versatile' },
  'groq-llama8b':   { provider:'groq', model:'llama-3.1-8b-instant' },
  'groq-mixtral':   { provider:'groq', model:'mixtral-8x7b-32768' },
  'groq-gemma':     { provider:'groq', model:'gemma2-9b-it' },
  'gemini-pro':     { provider:'google', model:'gemini-1.5-pro' },
  'gemini-flash':   { provider:'google', model:'gemini-1.5-flash' },
  'gemini-ultra':   { provider:'google', model:'gemini-ultra' },
  'or-claude':      { provider:'openrouter', model:'anthropic/claude-3.5-sonnet' },
  'or-gpt4':        { provider:'openrouter', model:'openai/gpt-4-turbo' },
  'or-llama405b':   { provider:'openrouter', model:'meta-llama/llama-3.1-405b-instruct' },
  'or-deepseek':    { provider:'openrouter', model:'deepseek/deepseek-r1' },
  'tog-llama70b':   { provider:'together', model:'meta-llama/Llama-3-70b-chat-hf' },
  'tog-mixtral':    { provider:'together', model:'mistralai/Mixtral-8x7B-Instruct-v0.1' },
  'mistral-large':  { provider:'mistral', model:'mistral-large-latest' },
  'mistral-medium': { provider:'mistral', model:'mistral-medium-latest' },
  'codestral-api':  { provider:'mistral', model:'codestral-latest' },
  'pixtral':        { provider:'mistral', model:'pixtral-large-latest' }
};

function proxyRequest(url, method, headers, body) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const opts = { hostname:u.hostname, port:u.port||(u.protocol==='https:'?443:80), path:u.pathname+u.search, method, headers };
    const mod = u.protocol === 'https:' ? https : http;
    const req = mod.request(opts, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve({ status:res.statusCode, body:data }));
    });
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin','*');
  res.setHeader('Access-Control-Allow-Headers','*');
  res.setHeader('Access-Control-Allow-Methods','*');
  if (req.method === 'OPTIONS') { res.writeHead(200); return res.end(); }

  let body = '';
  req.on('data', c => body += c);
  req.on('end', async () => {
    try {
      if (req.url === '/status') {
        const ollamaRes = await proxyRequest('http://127.0.0.1:11434/api/tags','GET',{}).catch(()=>({body:'{}'}));
        const ollama = JSON.parse(ollamaRes.body).models || [];
        res.writeHead(200,{'Content-Type':'application/json'});
        return res.end(JSON.stringify({
          ok:true, gateway:'NovaX AI Gateway v1.0', port:PORT,
          cloud_models: Object.keys(ROUTES).length,
          local_models: ollama.length,
          total: Object.keys(ROUTES).length + ollama.length,
          providers: Object.keys(PROVIDERS)
        }));
      }

      if (req.url === '/models') {
        const ollamaRes = await proxyRequest('http://127.0.0.1:11434/api/tags','GET',{}).catch(()=>({body:'{}'}));
        const ollama = (JSON.parse(ollamaRes.body).models || []).map(m => ({name:m.name, provider:'ollama', type:'local', size:m.size}));
        const cloud = Object.entries(ROUTES).map(([k,v]) => ({name:k, provider:v.provider, model:v.model, type:'cloud'}));
        res.writeHead(200,{'Content-Type':'application/json'});
        return res.end(JSON.stringify({local:ollama, cloud, total:ollama.length+cloud.length}));
      }

      if (req.url === '/chat' && req.method === 'POST') {
        const payload = JSON.parse(body);
        const modelName = payload.model || 'groq-llama8b';
        const messages = payload.messages || [{role:'user',content:payload.prompt||'hello'}];

        if (!ROUTES[modelName]) {
          const ollamaBody = JSON.stringify({model:modelName, messages, stream:false});
          const r = await proxyRequest('http://127.0.0.1:11434/api/chat','POST',{'Content-Type':'application/json'},ollamaBody);
          res.writeHead(r.status,{'Content-Type':'application/json'});
          return res.end(r.body);
        }

        const route = ROUTES[modelName];
        const prov = PROVIDERS[route.provider];

        let url, headers, reqBody;

        if (route.provider === 'anthropic') {
          url = prov.base + '/messages';
          headers = {'Content-Type':'application/json','x-api-key':prov.key,'anthropic-version':'2023-06-01'};
          reqBody = JSON.stringify({model:route.model, max_tokens:4096, messages});
        } else if (route.provider === 'google') {
          url = prov.base + '/models/' + route.model + ':generateContent?key=' + prov.key;
          headers = {'Content-Type':'application/json'};
          reqBody = JSON.stringify({contents:messages.map(m=>({role:m.role==='assistant'?'model':'user',parts:[{text:m.content}]}))});
        } else {
          url = prov.base + '/chat/completions';
          headers = {'Content-Type':'application/json','Authorization':'Bearer '+prov.key};
          if (route.provider === 'openrouter') { headers['HTTP-Referer'] = 'http://novax.local'; headers['X-Title'] = 'NovaX'; }
          reqBody = JSON.stringify({model:route.model, messages, max_tokens:4096});
        }

        const r = await proxyRequest(url, 'POST', headers, reqBody);
        res.writeHead(r.status,{'Content-Type':'application/json'});
        return res.end(r.body);
      }

      res.writeHead(404);
      res.end(JSON.stringify({error:'Use /status, /models, or POST /chat'}));
    } catch(e) {
      res.writeHead(500);
      res.end(JSON.stringify({error:e.message}));
    }
  });
});

server.listen(PORT, () => console.log('NovaX AI Gateway :' + PORT + ' | ' + Object.keys(ROUTES).length + ' cloud + Ollama local'));
