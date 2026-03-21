import json

with open(r'C:\NovaX\cloud_config.json', 'r', encoding='utf-8') as f:
    c = json.load(f)

providers = ['groq','mistral','deepseek','cohere','google','openrouter','together',
             'sambanova_direct','google_ai_studio','cerebras_direct','anthropic','openai']

for p in providers:
    info = c.get(p, {})
    key = info.get('key', '')
    key_preview = (key[:25] + '...') if key and len(key) > 5 else 'NONE'
    via = info.get('via', 'direct')
    url = info.get('url', 'N/A')
    print(f"{p:22s} key={key_preview:30s} via={via:15s} url={url[:50]}")
