"""P5.3 8 核心场景验证 - 修正版"""
import requests, json, time, sys

BASE = 'http://127.0.0.1:8000'

def setup():
    username = f'tester_{int(time.time())}'
    password = 'Test1234!'
    try:
        requests.post(f'{BASE}/register', json={'username': username, 'password': password}, timeout=5)
    except Exception:
        pass
    # login uses OAuth2PasswordRequestForm => form-data, not JSON
    r = requests.post(f'{BASE}/login', data={'username': username, 'password': password}, timeout=5)
    token = r.json().get('access_token')
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.post(f'{BASE}/conversations', headers=headers, json={'title': f'test_{int(time.time())}'}, timeout=5)
    conv_id = r.json().get('id')
    return headers, conv_id

def run_scenario(headers, conv_id, sid, query, expected_routes):
    print(f'\n{"="*60}')
    print(f'{sid}: {query}')
    print(f'Expected routes: {expected_routes}')

    try:
        with requests.post(
            f'{BASE}/chat',
            headers=headers,
            json={'user_input': query, 'conversation_id': conv_id},
            stream=True,
            timeout=30
        ) as r:
            raw = r.text

        category = None
        rag_used = False
        citation_count = 0
        tool_names = []
        has_error = False
        event_sequence = []
        current_event = None
        all_data = {}

        for line in raw.split('\n'):
            line = line.strip()
            if line.startswith('event:'):
                current_event = line.split(':', 1)[1].strip()
                event_sequence.append(current_event)
                all_data.setdefault(current_event, []).append(None)
            elif line.startswith('data:') and current_event:
                data_str = line.split(':', 1)[1].strip()
                try:
                    j = json.loads(data_str)
                except Exception:
                    j = data_str
                all_data[current_event][-1] = j

                if current_event == 'category':
                    category = j.get('route') if isinstance(j, dict) else str(j)
                elif current_event == 'rag':
                    if isinstance(j, dict) and j.get('used'):
                        rag_used = True
                elif current_event == 'tool_start':
                    if isinstance(j, dict):
                        tool_names.append(j.get('name', ''))
                elif current_event == 'citation':
                    citation_count += 1
                elif current_event == 'error':
                    has_error = True

        done_last = event_sequence and event_sequence[-1] == 'done'
        route_ok = any(e in str(category) for e in expected_routes) if category else False
        status = 'PASS' if (route_ok and done_last and not has_error) else 'FAIL'

        print(f'  Route:       {category}  [{"OK" if route_ok else "FAIL"}]')
        print(f'  RAG used:    {rag_used}')
        print(f'  Citations:   {citation_count}')
        print(f'  Tools:       {tool_names}')
        print(f'  Error:       {has_error}')
        print(f'  Done last:   {done_last}')
        print(f'  Events:      {event_sequence}')
        print(f'  ===> {status}')

        return {
            'sid': sid, 'status': status, 'route': category,
            'rag': rag_used, 'citations': citation_count,
            'tools': tool_names, 'done': done_last, 'error': has_error
        }
    except Exception as e:
        print(f'  ERROR: {e}')
        return {'sid': sid, 'status': 'ERROR', 'error': str(e)}

def main():
    print('=' * 60)
    print('P5.3 核心场景验证')
    print('=' * 60)

    headers, conv_id = setup()
    print(f'\nUser ready, conv_id={conv_id}')

    scenarios = [
        ('S1', '你好，在吗？',           ['normal_chat']),
        ('S2', '我刚收到东西没几天，不想要了还能把钱退回来吗？', ['rag']),
        ('S3', '我的订单10001现在什么状态？', ['order_query']),
        ('S4', '帮我查一下订单10001，如果已经发货，再告诉我物流到哪里了。', ['order_query']),
        ('S5', '我的订单99999已经发货了吗？如果发货了告诉我物流。', ['order_query']),
        ('S6', '我的快递到哪里了？',     ['logistics_query']),
        ('S7', '我要人工客服',           ['human_service']),
        ('S8', '退货退款规则是什么？',   ['rag']),
    ]

    results = []
    for sid, query, expected in scenarios:
        results.append(run_scenario(headers, conv_id, sid, query, expected))

    print(f'\n{"="*60}')
    print('SUMMARY')
    print(f'{"="*60}')
    for r in results:
        route_str = r.get('route', '-') or '-'
        print(f"  {r['sid']}: {r['status']:5s} | route={route_str:16s} rag={r.get('rag')} cit={r.get('citations',0)} tools={r.get('tools',[])} done={r.get('done')}")

    pass_count = sum(1 for r in results if r['status'] == 'PASS')
    print(f'\nPASS: {pass_count}/{len(results)}')
    sys.exit(0 if pass_count == len(results) else 1)

if __name__ == '__main__':
    main()
