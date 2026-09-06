import asyncio
import os
from datetime import datetime, timedelta

import aiohttp

GB = 1024 * 1024 * 1024


def _env(*names, default=""):
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _clean_url(url):
    url = str(url or "").strip().rstrip("/")
    for marker in ("/dashboard", "/login", "/#/", "#"):
        pos = url.lower().find(marker.lower())
        if pos > 0:
            url = url[:pos].rstrip("/")
    return url


def _config(service):
    s = str(service or "gold").lower()
    if s == "bronze":
        return (
            _clean_url(_env("BRONZE_PANEL_URL", "SILVER_PANEL_URL")),
            _env("BRONZE_PANEL_USERNAME", "SILVER_PANEL_USERNAME"),
            _env("BRONZE_PANEL_PASSWORD", "SILVER_PANEL_PASSWORD"),
        )
    return (
        _clean_url(_env("GOLD_PANEL_URL", "PANEL_URL")),
        _env("GOLD_PANEL_USERNAME", "PANEL_USERNAME"),
        _env("GOLD_PANEL_PASSWORD", "PANEL_PASSWORD"),
    )


def _normalize(value, base=""):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("/") and base:
        return base.rstrip("/") + value
    if "." in value.split("/")[0]:
        return "https://" + value
    return value


def _connections(obj, base=""):
    keys = (
        "subscription_url", "subscriptionUrl", "subscription_uri", "subscriptionUri",
        "sub_url", "subUrl", "subscription_link", "subscriptionLink",
        "config_url", "configUrl", "connection_url", "connectionUrl", "link", "url",
    )
    out = []
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                out.append(_normalize(v, base))
        for v in obj.values():
            if isinstance(v, (dict, list)):
                out.extend(_connections(v, base))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_connections(v, base))
    result, seen = [], set()
    for v in out:
        if v and v not in seen:
            seen.add(v)
            result.append(v)
    return result


async def _json(response):
    raw = await response.text()
    try:
        return await response.json(content_type=None)
    except Exception:
        return {"raw": raw}


async def _login(session, service):
    url, user, password = _config(service)
    if not url or not user or not password:
        raise RuntimeError(f"{service.title()} panel credentials are not configured")
    async with session.post(
        f"{url}/api/admin/token",
        data={"grant_type": "password", "username": user, "password": password},
        headers={"Accept": "application/json, */*", "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
    ) as r:
        data = await _json(r)
        print(f"🔐 {service.upper()} LOGIN HTTP {r.status}")
        if r.status != 200:
            raise RuntimeError(f"Login HTTP {r.status}: {data}")
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token and isinstance(data, dict):
            token = data.get("token")
        if not token:
            raise RuntimeError(f"Login response has no token: {data}")
        return token, url


async def _get_user(session, base, headers, username):
    for endpoint in (
        f"/api/user/by-username/{username}",
        f"/api/user/{username}",
    ):
        try:
            async with session.get(base + endpoint, headers=headers) as r:
                data = await _json(r)
                print(f"🔎 GET USER HTTP {r.status}: {endpoint}")
                if r.status == 200 and isinstance(data, dict):
                    return data
        except Exception as exc:
            print(f"⚠️ GET USER ERROR {endpoint}: {exc!r}")
    return {}


async def _get_subscription(session, base, headers, user_data):
    uid = None
    if isinstance(user_data, dict):
        uid = user_data.get("id") or user_data.get("user_id") or user_data.get("userId")
        if not uid and isinstance(user_data.get("data"), dict):
            nested = user_data["data"]
            uid = nested.get("id") or nested.get("user_id") or nested.get("userId")
    if uid is None:
        return ""

    # This is the subscription route used by the uploaded Pasargard frontend.
    for endpoint in (f"/sub/{uid}/info", f"/sub/{uid}/"):
        try:
            async with session.get(base + endpoint, headers=headers) as r:
                raw = await r.text()
                print(f"🔗 SUB HTTP {r.status}: {endpoint}")
                if r.status != 200:
                    continue
                try:
                    data = await r.json(content_type=None)
                    links = _connections(data, base)
                    if links:
                        return links[0]
                except Exception:
                    pass
                if raw.strip() and endpoint.endswith("/info"):
                    return raw.strip()
                if raw.strip() and (raw.strip().startswith(("http://", "https://", "vless://", "vmess://", "trojan://", "ss://", "wg://", "hysteria://"))):
                    return raw.strip()
        except Exception as exc:
            print(f"⚠️ SUB ERROR {endpoint}: {exc!r}")
    return ""


async def create_pasargard_customer(username, gb, unlimited=False, days=30, group_ids=None, note="", service="gold"):
    service = str(service or "gold").lower()
    base_group = int(os.getenv("DEFAULT_GROUP_ID", "1") or 1)
    groups = group_ids if group_ids is not None else [base_group]
    status = os.getenv("DEFAULT_STATUS", "active") or "active"
    hwid_raw = os.getenv("DEFAULT_HWID_LIMIT", "0")
    hwid = None if str(hwid_raw).strip() in ("", "0", "none", "null") else int(hwid_raw)
    method = os.getenv("SHADOWSOCKS_METHOD", "chacha20-ietf-poly1305") or "chacha20-ietf-poly1305"

    timeout = aiohttp.ClientTimeout(total=35, connect=8, sock_connect=8, sock_read=22)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            token, base = await _login(session, service)
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
            expire = (datetime.now().astimezone() + timedelta(days=int(days))).isoformat(timespec="seconds")
            payload = {
                "username": str(username).strip(),
                "status": status,
                "data_limit": 0 if unlimited else int(float(gb) * GB),
                "expire": expire,
                "group_ids": groups,
                "hwid_limit": hwid,
                "next_plan": None,
                "note": note or f"AlphaShop {service}",
                "proxy_settings": {"shadowsocks": {"method": method}},
            }
            print(f"👤 CREATE {service.upper()} {username} | {gb} GB | groups={groups}")
            async with session.post(base + "/api/user", headers=headers, json=payload) as r:
                created = await _json(r)
                print(f"👤 CREATE {service.upper()} HTTP {r.status}")
                print(f"📥 CREATE RESPONSE: {created}")
                if r.status not in (200, 201):
                    return {"ok": False, "data": created, "subscription_url": "", "connection_details": "", "config": ""}

            user = await _get_user(session, base, headers, str(username).strip())
            merged = dict(created) if isinstance(created, dict) else {"created": created}
            if user:
                merged["user"] = user

            links = _connections(created, base) + _connections(user, base)
            connection = next((x for x in links if x), "")
            if not connection:
                connection = await _get_subscription(session, base, headers, user or created)

            final_username = (user.get("username") if isinstance(user, dict) else None) or (created.get("username") if isinstance(created, dict) else None) or str(username).strip()
            print(f"🔗 {service.upper()} RESULT: {connection or '<EMPTY>'}")

            if not connection:
                return {"ok": False, "data": {"error": "User created but subscription/config was not returned", "response": merged}, "subscription_url": "", "connection_details": "", "config": "", "username": final_username}

            return {
                "ok": True,
                "data": merged,
                "username": final_username,
                "subscription_url": connection,
                "connection_details": connection,
                "config": connection,
                "subscription_links": [connection],
            }
        except asyncio.TimeoutError:
            return {"ok": False, "data": {"error": "Panel request timeout"}, "subscription_url": "", "connection_details": "", "config": ""}
        except Exception as exc:
            print(f"❌ {service.upper()} EXCEPTION: {exc!r}")
            return {"ok": False, "data": {"error": str(exc)}, "subscription_url": "", "connection_details": "", "config": ""}
