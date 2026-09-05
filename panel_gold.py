import asyncio
import os
from datetime import datetime, timedelta
import aiohttp

GB = 1024 * 1024 * 1024
SERVICE = "gold"


def _clean_url(url):
    url = str(url or "").strip()
    for marker in ("/dashboard", "/login", "/#", "#"):
        pos = url.lower().find(marker.lower())
        if pos > 0:
            url = url[:pos]
            break
    return url.rstrip("/")


def _config():
    return (
        _clean_url(os.getenv("GOLD_PANEL_URL") or os.getenv("PANEL_URL")),
        (os.getenv("GOLD_PANEL_USERNAME") or os.getenv("PANEL_USERNAME") or "").strip(),
        (os.getenv("GOLD_PANEL_PASSWORD") or os.getenv("PANEL_PASSWORD") or "").strip(),
    )


async def _json(response):
    raw = await response.text()
    try:
        return await response.json(content_type=None)
    except Exception:
        return {"raw": raw[:4000]}


def _normalize(value, panel_url=""):
    if not value:
        return ""
    value = str(value).strip()
    if value.startswith(("http://", "https://", "vless://", "vmess://", "trojan://", "ss://")):
        return value
    if value.startswith("//"):
        return "https:" + value
    if panel_url and value.startswith("/"):
        return _clean_url(panel_url) + value
    return value


def _walk(obj, panel_url=""):
    found = []
    if isinstance(obj, dict):
        keys = (
            "subscription_url", "subscriptionUrl", "subscription_uri", "subscriptionUri",
            "sub_url", "subUrl", "subscription_link", "subscriptionLink",
            "config_url", "configUrl", "connection_url", "connectionUrl", "link", "url",
        )
        for key in keys:
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                found.append(_normalize(value, panel_url))
        nested = ("subscription", "subscriptions", "links", "connection", "connections",
                  "proxy_settings", "proxySettings", "data", "result", "user")
        for key in nested:
            if key in obj:
                found.extend(_walk(obj[key], panel_url))
        for key, value in obj.items():
            if key not in nested and isinstance(value, (dict, list)):
                found.extend(_walk(value, panel_url))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk(item, panel_url))
    result, seen = [], set()
    for value in found:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


async def _login(session):
    panel_url, username, password = _config()
    if not panel_url:
        raise RuntimeError("Gold panel URL is not configured")
    if not username or not password:
        raise RuntimeError("Gold panel credentials are not configured")
    async with session.post(
        f"{panel_url}/api/admin/token",
        data={"grant_type": "password", "username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "Accept": "application/json, */*"},
    ) as response:
        data = await _json(response)
        if response.status != 200:
            raise RuntimeError(f"Gold login HTTP {response.status}: {data}")
        token = data.get("access_token") or data.get("token") if isinstance(data, dict) else None
        if not token:
            raise RuntimeError(f"Gold login returned no token: {data}")
        return token, panel_url


async def create_customer(username, gb, unlimited=False, days=30, group_ids=None, note=""):
    timeout = aiohttp.ClientTimeout(total=45, connect=10, sock_connect=10, sock_read=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            token, panel_url = await _login(session)
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
            group_ids = group_ids if group_ids is not None else [int(os.getenv("DEFAULT_GROUP_ID", "1") or 1)]
            hwid = int(os.getenv("DEFAULT_HWID_LIMIT", "0") or 0)
            method = os.getenv("SHADOWSOCKS_METHOD", "chacha20-ietf-poly1305")
            expire = (datetime.now().astimezone() + timedelta(days=int(days))).isoformat(timespec="seconds")
            payload = {
                "username": str(username).strip(),
                "status": os.getenv("DEFAULT_STATUS", "active") or "active",
                "data_limit": 0 if unlimited else int(float(gb) * GB),
                "expire": expire,
                "group_ids": group_ids,
                "hwid_limit": None if hwid == 0 else hwid,
                "next_plan": None,
                "note": note or "AlphaShop Gold",
                "proxy_settings": {"shadowsocks": {"method": method}},
            }
            async with session.post(f"{panel_url}/api/user", headers=headers, json=payload) as response:
                data = await _json(response)
                print(f"🟡 GOLD CREATE HTTP {response.status}: {data}")
                if response.status not in (200, 201):
                    return {"ok": False, "data": data, "subscription_url": "", "connection_details": "", "config": ""}

            links = _walk(data, panel_url)
            connection = links[0] if links else ""
            user_data = {}
            if not connection:
                for path in (f"{panel_url}/api/user/by-username/{username}", f"{panel_url}/api/user/{username}"):
                    try:
                        async with session.get(path, headers=headers) as response:
                            candidate = await _json(response)
                            if response.status == 200:
                                user_data = candidate
                                links = _walk(candidate, panel_url)
                                if links:
                                    connection = links[0]
                                    break
                    except (aiohttp.ClientError, asyncio.TimeoutError):
                        pass
            if not connection:
                user_id = data.get("id") if isinstance(data, dict) else None
                for path in ([f"{panel_url}/api/user/{user_id}/subscription/links"] if user_id else []) + [f"{panel_url}/api/user/{username}/subscription/links"]:
                    try:
                        async with session.get(path, headers=headers) as response:
                            candidate = await _json(response)
                            if response.status == 200:
                                links = _walk(candidate, panel_url)
                                if links:
                                    connection = links[0]
                                    break
                    except (aiohttp.ClientError, asyncio.TimeoutError):
                        pass
            if not connection:
                raise RuntimeError(f"Gold user created but no connection link returned: {data}")
            merged = dict(data) if isinstance(data, dict) else {"response": data}
            if user_data:
                merged["user"] = user_data
            return {"ok": True, "data": merged, "username": str(username).strip(), "subscription_url": connection, "connection_details": connection, "config": connection}
        except Exception as exc:
            print(f"❌ GOLD EXCEPTION: {exc!r}")
            return {"ok": False, "data": {"error": str(exc)}, "subscription_url": "", "connection_details": "", "config": ""}
