import asyncio
import os
import time
import uuid
from datetime import datetime, timedelta

import aiohttp

from config import *

GB = 1024 * 1024 * 1024


def _clean_url(url):
    url = str(url or '').strip().rstrip('/')
    for marker in ('/dashboard', '/login', '/#/'):
        p = url.lower().find(marker)
        if p > 0:
            url = url[:p]
            break
    return url.rstrip('/')


def _cfg(service):
    service = (service or 'gold').lower()
    if service == 'silver':
        return (
            _clean_url(os.getenv('SILVER_PANEL_URL', globals().get('SILVER_PANEL_URL', '')) or 'https://pan.linkesubs.com'),
            os.getenv('SILVER_PANEL_USERNAME', globals().get('SILVER_PANEL_USERNAME', '')).strip(),
            os.getenv('SILVER_PANEL_PASSWORD', globals().get('SILVER_PANEL_PASSWORD', '')).strip(),
        )
    if service == 'bronze':
        return (
            _clean_url(os.getenv('BRONZE_PANEL_URL', os.getenv('SILVER_PANEL_URL', globals().get('SILVER_PANEL_URL', '')))),
            os.getenv('BRONZE_PANEL_USERNAME', os.getenv('SILVER_PANEL_USERNAME', globals().get('SILVER_PANEL_USERNAME', ''))).strip(),
            os.getenv('BRONZE_PANEL_PASSWORD', os.getenv('SILVER_PANEL_PASSWORD', globals().get('SILVER_PANEL_PASSWORD', ''))).strip(),
        )
    return (
        _clean_url(globals().get('GOLD_PANEL_URL') or globals().get('PANEL_URL')),
        (globals().get('GOLD_PANEL_USERNAME') or globals().get('PANEL_USERNAME') or '').strip(),
        (globals().get('GOLD_PANEL_PASSWORD') or globals().get('PANEL_PASSWORD') or '').strip(),
    )


async def _json(response):
    raw = await response.text()
    try:
        return await response.json(content_type=None)
    except Exception:
        return {'raw': raw[:4000]}


def _first_url(obj):
    if isinstance(obj, str):
        s = obj.strip()
        if s.startswith(('http://', 'https://')) or s.startswith(('vless://', 'vmess://', 'trojan://', 'ss://')):
            return s
        return ''
    if isinstance(obj, dict):
        for k in ('subscription_url','subscriptionUrl','sub_url','subUrl','link','url'):
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for k in ('links','subscription','data','user','result'):
            v = obj.get(k)
            r = _first_url(v)
            if r:
                return r
    if isinstance(obj, list):
        for v in obj:
            r = _first_url(v)
            if r:
                return r
    return ''


def _protocols_from_inbounds(data):
    """Normalize Marzban /api/inbounds responses to {protocol: [tags]} ."""
    out = {}
    if isinstance(data, dict):
        # Common Marzban shape: {"vless": ["tag1"], "vmess": ["tag2"]}
        for proto, tags in data.items():
            p = str(proto).lower()
            if p in {'vless','vmess','trojan','shadowsocks'}:
                if isinstance(tags, list):
                    vals = [str(x) for x in tags if x]
                elif isinstance(tags, dict):
                    vals = [str(k) for k in tags.keys()]
                else:
                    vals = []
                if vals or tags == {}:
                    out[p] = vals
        # Sometimes wrapped in data/inbounds.
        if not out:
            for key in ('data','inbounds','result'):
                if key in data:
                    return _protocols_from_inbounds(data[key])
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            proto = str(item.get('protocol') or item.get('type') or '').lower()
            tag = item.get('tag') or item.get('remark') or item.get('name')
            if proto in {'vless','vmess','trojan','shadowsocks'} and tag:
                out.setdefault(proto, []).append(str(tag))
    return out


def _proxy_settings(protocol):
    uid = str(uuid.uuid4())
    if protocol == 'vless':
        d = {'id': uid}
        flow = os.getenv('SILVER_VLESS_FLOW', '').strip()
        if flow:
            d['flow'] = flow
        return d
    if protocol == 'vmess':
        return {'id': uid, 'alterId': 0, 'security': 'auto'}
    if protocol == 'trojan':
        return {'password': uid}
    if protocol == 'shadowsocks':
        return {
            'method': os.getenv('SILVER_SHADOWSOCKS_METHOD', globals().get('SHADOWSOCKS_METHOD', 'chacha20-ietf-poly1305')),
            'password': uid,
        }
    raise ValueError(f'Unsupported Marzban protocol: {protocol}')


async def _login_marzban(session, panel_url):
    token = os.getenv('SILVER_PANEL_API_TOKEN', '').strip()
    if token:
        return token
    user = os.getenv('SILVER_PANEL_USERNAME', globals().get('SILVER_PANEL_USERNAME', '')).strip()
    password = os.getenv('SILVER_PANEL_PASSWORD', globals().get('SILVER_PANEL_PASSWORD', '')).strip()
    if not user or not password:
        raise RuntimeError('Silver Marzban credentials are missing (SILVER_PANEL_USERNAME/PASSWORD)')
    async with session.post(
        f'{panel_url}/api/admin/token',
        data={'grant_type':'password','username':user,'password':password},
        headers={'Accept':'application/json','Content-Type':'application/x-www-form-urlencoded'},
    ) as r:
        data = await _json(r)
        if r.status != 200:
            raise RuntimeError(f'Marzban login HTTP {r.status}: {data}')
        token = data.get('access_token') if isinstance(data, dict) else None
        if not token:
            token = data.get('token') if isinstance(data, dict) else None
        if not token:
            raise RuntimeError(f'Marzban login returned no token: {data}')
        return token


async def _create_marzban(session, username, gb, days):
    panel_url = _clean_url(os.getenv('SILVER_PANEL_URL', 'https://pan.linkesubs.com'))
    token = await _login_marzban(session, panel_url)
    headers = {'Authorization': f'Bearer {token}', 'Accept':'application/json', 'Content-Type':'application/json'}

    # Read actual enabled inbounds first. This avoids forcing VLESS when the panel only has VMess/Trojan/etc.
    async with session.get(f'{panel_url}/api/inbounds', headers=headers) as r:
        inb_data = await _json(r)
        if r.status != 200:
            raise RuntimeError(f'Marzban /api/inbounds HTTP {r.status}: {inb_data}')
    inbound_map = _protocols_from_inbounds(inb_data)
    if not inbound_map:
        raise RuntimeError(f'Marzban returned no usable inbounds: {inb_data}')

    wanted = os.getenv('SILVER_PROTOCOL', '').strip().lower()
    wanted_name = os.getenv('SILVER_INBOUND_NAME', '').strip()
    if wanted not in inbound_map:
        wanted = ''
    protocol = wanted or next(iter(inbound_map))
    tags = inbound_map.get(protocol) or []
    if wanted_name and wanted_name in tags:
        tags = [wanted_name]

    # Marzban Add User API expects proxies + inbounds, not the Pasargard proxy_settings/group_ids shape.
    payload = {
        'username': username,
        'status': 'active',
        'data_limit': int(float(gb) * GB),
        'expire': int(time.time()) + int(days) * 86400,
        'proxies': {protocol: _proxy_settings(protocol)},
        'inbounds': {protocol: tags},
        'note': f'AlphaShop Silver',
    }

    async def post(payload_):
        async with session.post(f'{panel_url}/api/user', headers=headers, json=payload_) as r:
            return r.status, await _json(r)

    status, data = await post(payload)
    print(f'🥈 MARZBAN CREATE {username}: HTTP {status} protocol={protocol} inbounds={tags}')
    print(f'🥈 MARZBAN RESPONSE: {data}')

    # If a selected inbound is stale, retry with all inbounds of that protocol.
    if status >= 400 and tags:
        retry = dict(payload)
        retry['inbounds'] = {protocol: []}
        status, data = await post(retry)
        print(f'🥈 MARZBAN RETRY-ALL-INBOUNDS: HTTP {status} protocol={protocol}')
        print(f'🥈 MARZBAN RETRY RESPONSE: {data}')

    # If the configured protocol is disabled/misconfigured, try every actually enabled protocol.
    if status >= 400:
        last = data
        for p, p_tags in inbound_map.items():
            if p == protocol:
                continue
            trial = {
                'username': username,
                'status': 'active',
                'data_limit': int(float(gb) * GB),
                'expire': int(time.time()) + int(days) * 86400,
                'proxies': {p: _proxy_settings(p)},
                'inbounds': {p: p_tags},
                'note': 'AlphaShop Silver',
            }
            st, dat = await post(trial)
            print(f'🥈 MARZBAN FALLBACK: HTTP {st} protocol={p} inbounds={p_tags}')
            print(f'🥈 MARZBAN FALLBACK RESPONSE: {dat}')
            last = dat
            if st in (200, 201, 409):
                status, data, protocol = st, dat, p
                break
        else:
            data = last

    if status == 409:
        # User already exists: fetch it and return its current subscription instead of refunding.
        pass
    elif status not in (200, 201):
        raise RuntimeError(f'Marzban create user HTTP {status}: {data}')

    # POST /api/user normally contains subscription_url, but some versions return only user fields.
    connection = _first_url(data)
    user_data = data
    if not connection:
        async with session.get(f'{panel_url}/api/user/{username}', headers=headers) as r:
            user_data = await _json(r)
            print(f'🥈 MARZBAN GET USER HTTP {r.status}: {user_data}')
            if r.status == 200:
                connection = _first_url(user_data)

    # Modern Marzban exposes the canonical subscription URL in user info. Keep a final fallback
    # for versions where it is nested under links/subscription_url.
    if not connection:
        connection = _first_url(user_data)
    if not connection:
        raise RuntimeError(f'Marzban user created but no subscription_url/links returned: {user_data}')

    merged = {}
    if isinstance(data, dict):
        merged.update(data)
    if isinstance(user_data, dict):
        merged['user'] = user_data
    merged['subscription_url'] = connection
    merged['protocol_used'] = protocol
    return merged, connection


async def _create_pasargard(session, username, gb, unlimited, days, service):
    panel_url, panel_user, panel_pass = _cfg(service)
    if not panel_url:
        raise RuntimeError(f'{service.title()} panel URL is not configured')
    if not panel_user or not panel_pass:
        raise RuntimeError(f'{service.title()} panel credentials are not configured')

    async with session.post(
        f'{panel_url}/api/admin/token',
        data={'grant_type':'password','username':panel_user,'password':panel_pass},
        headers={'Content-Type':'application/x-www-form-urlencoded','Accept':'application/json'},
    ) as r:
        login = await _json(r)
        if r.status != 200:
            raise RuntimeError(f'{service.title()} login HTTP {r.status}: {login}')
        token = login.get('access_token') or login.get('token') if isinstance(login, dict) else None
        if not token:
            raise RuntimeError(f'{service.title()} login returned no token: {login}')

    headers = {'Authorization':f'Bearer {token}','Accept':'application/json','Content-Type':'application/json'}
    payload = {
        'username': username,
        'status': globals().get('DEFAULT_STATUS','active') or 'active',
        'data_limit': 0 if unlimited else int(float(gb)*GB),
        'expire': (datetime.now().astimezone() + timedelta(days=int(days))).isoformat(timespec='seconds'),
        'group_ids': [globals().get('DEFAULT_GROUP_ID',1)],
        'hwid_limit': None if globals().get('DEFAULT_HWID_LIMIT',0)==0 else globals().get('DEFAULT_HWID_LIMIT'),
        'next_plan': None,
        'note': f'AlphaShop {service}',
        'proxy_settings': {'shadowsocks': {'method': globals().get('SHADOWSOCKS_METHOD','chacha20-ietf-poly1305')}},
    }
    async with session.post(f'{panel_url}/api/user', headers=headers, json=payload) as r:
        data = await _json(r)
        if r.status not in (200,201):
            raise RuntimeError(f'{service.title()} create HTTP {r.status}: {data}')
    connection = _first_url(data)
    if not connection:
        async with session.get(f'{panel_url}/api/user/{username}', headers=headers) as r:
            user_data = await _json(r)
            connection = _first_url(user_data)
            if isinstance(user_data, dict):
                data = {**(data if isinstance(data,dict) else {}), 'user':user_data}
    if not connection:
        raise RuntimeError(f'{service.title()} user created but no connection link returned: {data}')
    return data, connection


async def create_customer(username, gb, unlimited=False, days=30, group_ids=None, note='', service='gold'):
    service = (service or 'gold').lower()
    timeout = aiohttp.ClientTimeout(total=45, connect=10, sock_connect=10, sock_read=30)
    connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        try:
            if service == 'silver':
                data, connection = await _create_marzban(session, str(username).strip(), gb, days)
            else:
                data, connection = await _create_pasargard(session, str(username).strip(), gb, unlimited, days, service)
            return {
                'ok': True,
                'data': data,
                'username': str(username).strip(),
                'subscription_url': connection,
                'connection_details': connection,
                'config': connection,
            }
        except asyncio.TimeoutError:
            return {'ok':False,'data':{'error':f'{service.title()} panel request timeout'},'subscription_url':'','connection_details':'','config':''}
        except (aiohttp.ClientError, Exception) as exc:
            print(f'❌ CREATE {service.upper()} EXCEPTION: {exc!r}')
            return {'ok':False,'data':{'error':str(exc)},'subscription_url':'','connection_details':'','config':''}
