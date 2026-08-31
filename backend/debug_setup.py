"""Debug auth + conversation"""
import requests, json, time

BASE = 'http://127.0.0.1:8000'
username = f'debug_{int(time.time())}'
password = 'Test1234!'

print('=== REGISTER ===')
try:
    r = requests.post(f'{BASE}/api/auth/register',
                     json={'username': username, 'password': password}, timeout=5)
    print(r.status_code, r.text[:500])
except Exception as e:
    print('ERR:', e)

print('\n=== LOGIN ===')
try:
    r = requests.post(f'{BASE}/api/auth/login',
                     json={'username': username, 'password': password}, timeout=5)
    print(r.status_code, r.text[:500])
    token = r.json().get('access_token')
    print('token:', token[:30] if token else None)
except Exception as e:
    print('ERR:', e)

if token:
    headers = {'Authorization': f'Bearer {token}'}
    print('\n=== CREATE CONVERSATION ===')
    r = requests.post(f'{BASE}/api/conversations', headers=headers, timeout=5)
    print(r.status_code, r.text[:500])

    conv_id = r.json().get('id')
    print('\n=== CHAT (SSE) ===')
    with requests.post(
        f'{BASE}/api/chat/{conv_id}',
        headers=headers,
        json={'content': '你好'},
        stream=True, timeout=30
    ) as r:
        print('status:', r.status_code)
        print('headers:', dict(r.headers))
        raw = r.text
        print('raw length:', len(raw))
        print('raw preview:')
        print(raw[:2000])
