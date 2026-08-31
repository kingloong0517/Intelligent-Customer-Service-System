import requests, json, time

BASE = 'http://127.0.0.1:8000'
username = f'check_{int(time.time())}'
requests.post(f'{BASE}/register', json={'username': username, 'password': 'Test1234!'}, timeout=5)
r = requests.post(f'{BASE}/login', data={'username': username, 'password': 'Test1234!'}, timeout=5)
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

print('=== KB LIST ===')
r = requests.get(f'{BASE}/kb', headers=headers, timeout=5)
print(f'  status={r.status_code} body={r.text[:500]}')

print('\n=== VECTOR STORE ===')
import os
vs_dir = r'd:\vscode program\ai_chat\backend\vector_store'
if os.path.exists(vs_dir):
    for f in os.listdir(vs_dir):
        fp = os.path.join(vs_dir, f)
        print(f'  {f} size={os.path.getsize(fp)}')
else:
    print(f'  dir not found: {vs_dir}')

print('\n=== DIRECT CHAT: 退货退款规则 ===')
conv_r = requests.post(f'{BASE}/conversations', headers=headers, json={'title': 'test'}, timeout=5)
conv_id = conv_r.json()['id']

with requests.post(f'{BASE}/chat', headers=headers, json={'user_input': '退货退款规则是什么？', 'conversation_id': conv_id}, stream=True, timeout=30) as r:
    raw = r.text

for line in raw.split('\n'):
    line = line.strip()
    if line.startswith('data:') or line.startswith('event:'):
        print(line[:200])
