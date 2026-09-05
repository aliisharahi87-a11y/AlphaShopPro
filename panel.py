import asyncio
import os
import time
import uuid
from datetime import datetime, timedelta

import aiohttp

from config import (
    PANEL_URL,
    PANEL_USERNAME,
    PANEL_PASSWORD,
    GOLD_PANEL_URL,
    GOLD_PANEL_USERNAME,
    GOLD_PANEL_PASSWORD,
    SILVER_PANEL_URL,
    SILVER_PANEL_USERNAME,
    SILVER_PANEL_PASSWORD,
    DEFAULT_GROUP_ID,
    DEFAULT_HWID_LIMIT,
    DEFAULT_STATUS,
    SHADOWSOCKS_METHOD,
)

GB = 1024 * 1024 * 1024


def _clean_panel_url(url: str) -> str:
    """Return a clean panel base URL without dashboard/hash/query parts."""
    if not url:
        return ""

    url = str(url).strip()
    if not url:
        return ""

    # A common value is https://panel.example.com/dashboard/#/
    for marker in ("/dashboard", "/login", "/#/", "#"):
        pos = url.lower().find(marker.lower())
        if pos > 0:
            url = url[:pos]
            break

    return url.rstrip("/")


def _panel_config(service="gold"):
    """Get URL/credentials for Gold, Silver or Bronze."""
    service = (service or "gold").lower()

    if service == "silver":
        return (
            _clean_panel_url(
                os.getenv("SILVER_PANEL_URL_NEW", SILVER_PANEL_URL or "")
            ),
            os.getenv(
                "SILVER_PANEL_USERNAME_NEW",
                SILVER_PANEL_USERNAME or "",
            ).strip(),
            os.getenv(
                "SILVER_PANEL_PASSWORD_NEW",
                SILVER_PANEL_PASSWORD or "",
            ).strip(),
        )

    if service == "bronze":
        return (
            _clean_panel_url(
                os.getenv(
                    "BRONZE_PANEL_URL",
                    os.getenv("SILVER_PANEL_URL", ""),
                )
            ),
            os.getenv(
                "BRONZE_PANEL_USERNAME",
                os.getenv("SILVER_PANEL_USERNAME", ""),
            ).strip(),
            os.getenv(
                "BRONZE_PANEL_PASSWORD",
                os.getenv("SILVER_PANEL_PASSWORD", ""),
            ).strip(),
        )

    return (
        _clean_panel_url(GOLD_PANEL_URL or PANEL_URL or ""),
        (GOLD_PANEL_USERNAME or PANEL_USERNAME or "").strip(),
        (GOLD_PANEL_PASSWORD or PANEL_PASSWORD or "").strip(),
    )


def _normalize_url(value, panel_url=""):
    if not value:
        return ""

    value = str(value).strip()
    if not value:
        return ""

    if value.startswith(("http://", "https://")):
        return value

    if value.startswith("//"):
        return "https:" + value

    if panel_url:
        base = _clean_panel_url(panel_url)
        if value.startswith("/"):
            return base + value

        # hostname/path without scheme
        if "." in value.split("/")[0]:
            return "https://" + value

    return value


def _walk_connection_values(obj, panel_url=""):
    """Recursively collect URL-like connection/subscription values."""
    found = []

    if isinstance(obj, dict):
        preferred_keys = (
            "subscription_url",
            "subscriptionUrl",
            "subscription_uri",
            "subscriptionUri",
            "sub_url",
            "subUrl",
            "subscription_link",
            "subscriptionLink",
            "config_url",
            "configUrl",
            "connection_url",
            "connectionUrl",
            "link",
            "url",
        )

        for key in preferred_keys:
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                found.append(_normalize_url(value, panel_url))

        # Common nested containers.
        for key in (
            "subscription",
            "subscriptions",
            "links",
            "connection",
            "connections",
            "proxy_settings",
            "proxySettings",
            "data",
            "result",
            "user",
        ):
            if key in obj:
                found.extend(_walk_connection_values(obj[key], panel_url))

        # Also inspect unknown nested structures.
        for key, value in obj.items():
            if key in {
                "subscription", "subscriptions", "links", "connection",
                "connections", "proxy_settings", "proxySettings", "data",
                "result", "user",
            }:
                continue
            if isinstance(value, (dict, list)):
                found.extend(_walk_connection_values(value, panel_url))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk_connection_values(item, panel_url))

    # Remove duplicates while preserving order.
    result = []
    seen = set()
    for value in found:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _extract_connection(data, panel_url=""):
    values = _walk_connection_values(data, panel_url)
    return values[0] if values else ""


def _extract_all_connections(data, panel_url=""):
    return _walk_connection_values(data, panel_url)


async def _read_json(response):
    raw = await response.text()
    try:
        data = await response.json(content_type=None)
    except Exception:
        data = {"raw": raw}
    return data


async def _login(session, service="gold"):
    panel_url, username, password = _panel_config(service)

    if not panel_url:
        raise RuntimeError(f"{service.title()} panel URL is not configured")
    if not username or not password:
        raise RuntimeError(f"{service.title()} panel credentials are not configured")

    payload = {
        "grant_type": "password",
        "username": username,
        "password": password,
    }

    print(f"🔐 LOGIN {service.upper()} -> {panel_url} | user={username}")

    try:
        async with session.post(
            f"{panel_url}/api/admin/token",
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Accept": "application/json, */*",
            },
        ) as response:
            data = await _read_json(response)
            print(f"🔐 LOGIN {service.upper()} STATUS: {response.status}")

            if response.status != 200:
                print(f"❌ LOGIN {service.upper()} ERROR: {data}")
                raise RuntimeError(
                    f"Login Error ({service}) HTTP {response.status}: {data}"
                )

            token = data.get("access_token") if isinstance(data, dict) else None
            if not token and isinstance(data, dict):
                token = data.get("token")

            if not token:
                raise RuntimeError(
                    f"Login response has no token ({service}): {data}"
                )

            print(f"✅ LOGIN {service.upper()} SUCCESS")
            return token, panel_url

    except asyncio.TimeoutError:
        raise RuntimeError(f"{service.title()} panel login timeout")
    except aiohttp.ClientError as exc:
        raise RuntimeError(f"{service.title()} panel network error: {exc}")


async def _get_created_user(session, panel_url, headers, username):
    """Fetch the user after creation when the POST response is incomplete."""
    urls = (
        f"{panel_url}/api/user/by-username/{username}",
        f"{panel_url}/api/user/{username}",
    )

    for url in urls:
        try:
            async with session.get(url, headers=headers) as response:
                data = await _read_json(response)
                print(f"🔎 GET USER STATUS: {response.status} -> {url}")
                if response.status == 200 and isinstance(data, dict):
                    return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            print(f"⚠️ GET USER FAILED: {url} -> {exc!r}")

    return {}


async def _get_subscription_links(session, panel_url, headers, created_data, username):
    """Pasargard/Marzban-compatible fallbacks for the actual subscription links."""
    candidates = []

    user_id = None
    if isinstance(created_data, dict):
        user_id = (
            created_data.get("id")
            or created_data.get("user_id")
            or created_data.get("userId")
        )
        nested = created_data.get("data")
        if isinstance(nested, dict):
            user_id = user_id or nested.get("id") or nested.get("user_id")

    # Pasargard installations may expose subscription links by numeric user id.
    if user_id is not None:
        candidates.append(f"{panel_url}/api/user/{user_id}/subscription/links")

    # Some versions expose the same endpoint by username.
    candidates.append(f"{panel_url}/api/user/{username}/subscription/links")

    for url in candidates:
        try:
            async with session.get(url, headers=headers) as response:
                data = await _read_json(response)
                print(f"🔗 SUB LINKS STATUS: {response.status} -> {url}")
                if response.status == 200:
                    links = _extract_all_connections(data, panel_url)
                    if links:
                        return links
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            print(f"⚠️ SUB LINKS FAILED: {url} -> {exc!r}")

    return []




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
    user = os.getenv('SILVER_PANEL_USERNAME_NEW', os.getenv('SILVER_PANEL_USERNAME', globals().get('SILVER_PANEL_USERNAME', ''))).strip()
    password = os.getenv('SILVER_PANEL_PASSWORD_NEW', os.getenv('SILVER_PANEL_PASSWORD', globals().get('SILVER_PANEL_PASSWORD', ''))).strip()
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
    panel_url = _clean_url(os.getenv('SILVER_PANEL_URL_NEW', os.getenv('SILVER_PANEL_URL', 'https://pan.linkesubs.com')))
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

    wanted = os.getenv('SILVER_PROTOCOL', globals().get('SILVER_PROTOCOL', 'vless')).strip().lower()
    wanted_name = os.getenv('SILVER_INBOUND_NAME', globals().get('SILVER_INBOUND_NAME', '')).strip()
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




async def _create_pasargard_legacy(
    username,
    gb,
    unlimited=False,
    days=30,
    group_ids=None,
    note="",
    service="gold",
):
    """
    Create a user on the selected panel.

    Gold   -> Pasargard
    Silver -> Marzban
    Bronze -> Pasargard

    The function keeps the legacy arguments used by bot.py so existing
    purchase/trial handlers do not break.
    """
    service = (service or "gold").lower()

    if group_ids is None:
        group_ids = [DEFAULT_GROUP_ID]

    timeout = aiohttp.ClientTimeout(
        total=30,
        connect=8,
        sock_connect=8,
        sock_read=18,
    )
    connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        try:
            token, panel_url = await _login(session, service)

            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            expire = (
                datetime.now().astimezone() + timedelta(days=int(days))
            ).isoformat(timespec="seconds")

            data_limit = 0 if unlimited else int(float(gb) * GB)

            # This is the API shape used by the Pasargard/Marzban frontend
            # shipped with the project ZIP.
            payload = {
                "username": str(username).strip(),
                "status": DEFAULT_STATUS or "active",
                "data_limit": data_limit,
                "expire": expire,
                "group_ids": group_ids,
                "hwid_limit": (
                    None if DEFAULT_HWID_LIMIT == 0 else DEFAULT_HWID_LIMIT
                ),
                "next_plan": None,
                "note": note or f"AlphaShop {service}",
                "proxy_settings": {
                    "shadowsocks": {
                        "method": SHADOWSOCKS_METHOD,
                    }
                },
            }

            print(f"👤 CREATE {service.upper()} USER: {username}")
            print(f"📦 CREATE {service.upper()} GB: {gb} UNLIMITED: {unlimited}")

            async with session.post(
                f"{panel_url}/api/user",
                headers=headers,
                json=payload,
            ) as response:
                data = await _read_json(response)
                print(f"👤 CREATE {service.upper()} STATUS: {response.status}")
                print(f"📥 CREATE {service.upper()} RESPONSE: {data}")

                if response.status not in (200, 201):
                    return {
                        "ok": False,
                        "data": data,
                        "subscription_url": "",
                        "connection_details": "",
                        "config": "",
                    }

            # 1) Try the creation response.
            connection = _extract_connection(data, panel_url)

            # 2) Fetch the newly-created user. This fixes panels that return
            # only {id, username, ...} from POST /api/user.
            user_data = {}
            if not connection:
                user_data = await _get_created_user(
                    session, panel_url, headers, str(username).strip()
                )
                connection = _extract_connection(user_data, panel_url)

            # 3) Pasargard fallback: explicitly request subscription links.
            links = []
            if not connection:
                links = await _get_subscription_links(
                    session,
                    panel_url,
                    headers,
                    data if isinstance(data, dict) else {},
                    str(username).strip(),
                )
                if links:
                    connection = links[0]

            merged = {}
            if isinstance(data, dict):
                merged.update(data)
            if isinstance(user_data, dict):
                merged.setdefault("user", user_data)

            final_username = (
                (user_data.get("username") if isinstance(user_data, dict) else None)
                or (data.get("username") if isinstance(data, dict) else None)
                or str(username).strip()
            )

            print(f"🔗 {service.upper()} CONNECTION: {connection or '<EMPTY>'}")

            return {
                "ok": True,
                "data": merged,
                "username": final_username,
                "subscription_url": connection,
                "connection_details": connection,
                "config": connection,
                "subscription_links": links,
            }

        except asyncio.TimeoutError:
            print(f"⏱️ CREATE {service.upper()} TIMEOUT")
            return {
                "ok": False,
                "data": {"error": "Panel request timeout"},
                "subscription_url": "",
                "connection_details": "",
                "config": "",
            }

        except Exception as exc:
            print(f"❌ CREATE {service.upper()} EXCEPTION: {exc!r}")
            return {
                "ok": False,
                "data": {"error": str(exc)},
                "subscription_url": "",
                "connection_details": "",
                "config": "",
            }


async def create_customer(username, gb, unlimited=False, days=30, group_ids=None, note="", service="gold"):
    service = (service or "gold").lower()
    username = str(username).strip()

    if service == "silver":
        timeout = aiohttp.ClientTimeout(total=60, connect=12, sock_connect=12, sock_read=35)
        connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            last_error = None
            for attempt in range(1, 4):
                try:
                    data, connection = await _create_marzban(session, username, gb, days)
                    return {"ok": True, "data": data, "username": username, "subscription_url": connection, "connection_details": connection, "config": connection}
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    last_error = exc
                    print(f"⚠️ SILVER transient panel error (attempt {attempt}/3): {exc!r}")
                    if attempt < 3:
                        await asyncio.sleep(2 * attempt)
                except Exception as exc:
                    last_error = exc
                    print(f"❌ SILVER PANEL ERROR (attempt {attempt}/3): {exc!r}")
                    msg = str(exc)
                    if attempt < 3 and any(x in msg for x in ("HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504", "timeout", "Timeout")):
                        await asyncio.sleep(2 * attempt)
                        continue
                    break
            return {"ok": False, "data": {"error": str(last_error or "Silver panel provisioning failed")}, "subscription_url": "", "connection_details": "", "config": ""}

    # GOLD + BRONZE: original working Pasargard implementation.
    return await _create_pasargard_legacy(username=username, gb=gb, unlimited=unlimited, days=days, group_ids=group_ids, note=note, service=service)
