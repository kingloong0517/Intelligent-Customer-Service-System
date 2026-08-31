import requests, json, time

BASE = 'http://127.0.0.1:8000'
username = f'debug_{int(time.time())}'
password = 'Test1234!'

print('1. REGISTER')
r = requests.post(f'{BASE}/register', json={'username': username, 'password': password}, timeout=5)
print(f'  status={r.status_code} body={r.text[:500]}')

print('\n2. LOGIN (form-data)')
r = requests.post(f'{BASE}/login', data={'username': username, 'password': password}, timeout=5)
print(f'  status={r.status_code} body={r.text[:500]}')
token = None
try:
    token = r.json().get('access_token')
except Exception:
    pass
print(f'  token={token[:50] if token else "NONE"}')

if token:
    headers = {'Authorization': f'Bearer {token}'}
    print('\n3. CREATE CONV')
    r = requests.post(f'{BASE}/conversations', headers=headers, timeout=5)
    print(f'  status={r.status_code}')
    print(f'  body={r.text[:500]}')
    try:
        print(f'  json={r.json()}')
    except Exception as e:
        print(f'  json parse err: {e}')
    conv_id = None
    try:
        conv_id = r.json().get('id')
    except Exception:
        pass
    print(f'  conv_id={conv_id}')

    if conv_id:
        print('\n4. CHAT SSE')
        with requests.post(f'{BASE}/chat/{conv_id}', headers=headers, json={'content': '你好'}, stream=True, timeout=30) as r:
            print(f'  status={r.status_code}')
            raw = r.text
            print(f'  len={len(raw)}')
            print(f'  preview:')
            print(raw[:2000])
    else:
        print('\n  SKIP chat - no conv_id')
else:
    print('\n  SKIP conv - no token')
