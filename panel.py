import asyncio
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import aiohttp

from config import (
    PANEL_URL, PANEL_USERNAME, PANEL_PASSWORD,
    GOLD_PANEL_URL, GOLD_PANEL_USERNAME, GOLD_PANEL_PASSWORD,
    SILVER_PANEL_URL_NEW, SILVER_PANEL_USERNAME_NEW, SILVER_PANEL_PASSWORD_NEW,
    BRONZE_PANEL_URL, BRONZE_PANEL_USERNAME, BRONZE_PANEL_PASSWORD,
    DEFAULT_GROUP_ID, DEFAULT_HWID_LIMIT, DEFAULT_STATUS,
    SHADOWSOCKS_METHOD, SILVER_VLESS_FLOW,
)

GB = 1024 * 1024 * 1024
SUPPORTED_SERVICES = {"gold", "silver", "bronze"}


def _clean_panel_url(value):
    value = (value or "").strip().rstrip("/")
    for suffix in ("/dashboard/#", "/dashboard/", "/dashboard", "/#"):
        if value.endswith(suffix):
            value = value[:-len(suffix)].rstrip("/")
    return value


def _panel_config(service="gold"):
    service = (service or "gold").lower()
    if service not in SUPPORTED_SERVICES:
        raise RuntimeError(f"Unsupported service: {service}")
    if service == "silver":
        return _clean_panel_url(SILVER_PANEL_URL_NEW), SILVER_PANEL_USERNAME_NEW, SILVER_PANEL_PASSWORD_NEW
    if service == "bronze":
        return _clean_panel_url(BRONZE_PANEL_URL), BRONZE_PANEL_USERNAME, BRONZE_PANEL_PASSWORD
    return (
        _clean_panel_url(GOLD_PANEL_URL or PANEL_URL),
        GOLD_PANEL_USERNAME or PANEL_USERNAME,
        GOLD_PANEL_PASSWORD or PANEL_PASSWORD,
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
    if value.startswith("/") and panel_url:
        return urljoin(panel_url.rstrip("/") + "/", value.lstrip("/"))
    return value


def _extract_connection(data, panel_url=""):
    if isinstance(data, str):
        return _normalize_url(data, panel_url)
    if not isinstance(data, dict):
        return ""

    candidates = [
        data.get("subscription_url"), data.get("subscriptionUrl"),
        data.get("sub_url"), data.get("subUrl"), data.get("subscription"),
        data.get("config"), data.get("link"), data.get("url"), data.get("links"),
    ]
    for key in ("subscription", "subscription_info", "subscription_data"):
        obj = data.get(key)
        if isinstance(obj, dict):
            candidates.extend([
                obj.get("url"), obj.get("subscription_url"),
                obj.get("subscriptionUrl"), obj.get("link"), obj.get("links"),
            ])

    for value in candidates:
        if isinstance(value, str) and value.strip():
            return _normalize_url(value, panel_url)
        if isinstance(value, list) and value:
            text = "\n".join(str(x) for x in value if x)
            if text:
                return text
    return ""


async def _json_or_text(response):
    raw = await response.text()
    try:
        return await response.json(content_type=None)
    except Exception:
        return {"raw": raw}


async def _login(session, service="gold"):
    panel_url, username, password = _panel_config(service)
    if not panel_url:
        raise RuntimeError(f"{service.title()} panel URL is not configured")
    if not username or not password:
        raise RuntimeError(f"{service.title()} panel credentials are not configured")

    payload = {"grant_type": "password", "username": username, "password": password}
    async with session.post(
        f"{panel_url}/api/admin/token",
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    ) as response:
        data = await _json_or_text(response)
        print(f"🔐 LOGIN {service.upper()} HTTP {response.status}")
        if response.status != 200:
            raise RuntimeError(f"Login Error ({service}) HTTP {response.status}: {data}")
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            raise RuntimeError(f"Login response has no access_token ({service})")
        return token, panel_url


async def _get_pasargard_subscription(session, headers, panel_url, username):
    for path in (
        f"/api/user/{username}/subscription/links",
        f"/api/user/by-username/{username}/subscription/links",
        f"/api/user/{username}",
        f"/api/user/by-username/{username}",
    ):
        try:
            async with session.get(f"{panel_url}{path}", headers=headers) as response:
                data = await _json_or_text(response)
                if response.status != 200:
                    continue
                value = _extract_connection(data, panel_url)
                if value:
                    return value, data
        except (aiohttp.ClientError, asyncio.TimeoutError):
            continue
    return "", {}


async def _get_marzban_inbounds(session, headers, panel_url):
    async with session.get(f"{panel_url}/api/inbounds", headers=headers) as response:
        data = await _json_or_text(response)
        if response.status != 200:
            raise RuntimeError(f"Marzban inbounds HTTP {response.status}: {data}")

    result = {}
    if not isinstance(data, dict):
        return result

    for protocol, entries in data.items():
        if not isinstance(entries, list):
            continue
        tags = []
        for entry in entries:
            if isinstance(entry, dict):
                tag = entry.get("tag") or entry.get("remark") or entry.get("name")
                if tag:
                    tags.append(str(tag))
            elif isinstance(entry, str) and entry.strip():
                tags.append(entry.strip())
        if tags:
            result[protocol] = tags
    return result


async def _create_marzban_customer(session, token, panel_url, username, gb, days, note=""):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Marzban requires protocol/inbound information. We read the enabled
    # inbounds from the panel itself so no hard-coded inbound names are needed.
    inbounds = await _get_marzban_inbounds(session, headers, panel_url)
    if not inbounds:
        raise RuntimeError("Marzban returned no enabled inbounds")

    proxies = {protocol: {} for protocol in inbounds}
    if "vless" in proxies and SILVER_VLESS_FLOW:
        proxies["vless"]["flow"] = SILVER_VLESS_FLOW

    expire = 0 if days <= 0 else int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())
    payload = {
        "username": username,
        "status": "active",
        "expire": expire,
        "data_limit": int(float(gb) * GB),
        "data_limit_reset_strategy": "no_reset",
        "proxies": proxies,
        "inbounds": inbounds,
        "note": note or "Alpha Shop",
    }

    async with session.post(f"{panel_url}/api/user", headers=headers, json=payload) as response:
        data = await _json_or_text(response)
        print(f"👤 CREATE SILVER/MARZBAN {username} HTTP {response.status}")
        if response.status not in (200, 201):
            return {"ok": False, "data": data}

    # Marzban normally returns subscription_url/links in the user response.
    connection = _extract_connection(data, panel_url)
    if not connection:
        try:
            async with session.get(f"{panel_url}/api/user/{username}", headers=headers) as response:
                user_data = await _json_or_text(response)
                if response.status == 200:
                    connection = _extract_connection(user_data, panel_url)
                    if isinstance(data, dict) and isinstance(user_data, dict):
                        data = {**data, **user_data}
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass

    return {"ok": True, "data": data, "connection": connection}


async def _create_pasargard_customer(session, token, panel_url, username, gb, unlimited, days, group_ids, note):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    expire = 0 if days <= 0 else (datetime.now().astimezone() + timedelta(days=days)).isoformat(timespec="seconds")
    payload = {
        "username": username,
        "status": DEFAULT_STATUS or "active",
        "data_limit": 0 if unlimited else int(float(gb) * GB),
        "expire": expire,
        "group_ids": group_ids,
        "hwid_limit": None if DEFAULT_HWID_LIMIT == 0 else DEFAULT_HWID_LIMIT,
        "next_plan": None,
        "note": note,
        "proxy_settings": {"shadowsocks": {"method": SHADOWSOCKS_METHOD}},
    }
    async with session.post(f"{panel_url}/api/user", headers=headers, json=payload) as response:
        data = await _json_or_text(response)
        print(f"👤 CREATE {username} PASARGARD HTTP {response.status}")
        if response.status not in (200, 201):
            return {"ok": False, "data": data, "connection": ""}

    final_username = data.get("username", username) if isinstance(data, dict) else username
    connection = _extract_connection(data, panel_url)
    if not connection:
        connection, subscription_data = await _get_pasargard_subscription(
            session, headers, panel_url, final_username
        )
        if isinstance(data, dict) and subscription_data:
            data = {**data, "subscription": subscription_data}
    return {"ok": True, "data": data, "username": final_username, "connection": connection}


async def create_customer(username, gb, unlimited=False, days=30, group_ids=None, note="", service="gold"):
    service = (service or "gold").lower()
    if service not in SUPPORTED_SERVICES:
        return {"ok": False, "data": {"error": "Unsupported service"}, "subscription_url": "", "connection_details": "", "config": ""}

    if group_ids is None:
        group_ids = [DEFAULT_GROUP_ID]

    timeout = aiohttp.ClientTimeout(total=45, connect=10, sock_connect=10, sock_read=25)
    connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        try:
            token, panel_url = await _login(session, service)

            if service == "silver":
                result = await _create_marzban_customer(
                    session, token, panel_url, username, gb, days, note
                )
            else:
                result = await _create_pasargard_customer(
                    session, token, panel_url, username, gb, unlimited, days, group_ids, note
                )

            if not result.get("ok"):
                return {
                    "ok": False,
                    "data": result.get("data", {}),
                    "subscription_url": "",
                    "connection_details": "",
                    "config": "",
                }

            data = result.get("data") or {}
            final_username = result.get("username") or (data.get("username", username) if isinstance(data, dict) else username)
            connection = result.get("connection") or _extract_connection(data, panel_url)

            return {
                "ok": True,
                "data": data,
                "username": final_username,
                "subscription_url": connection,
                "connection_details": connection,
                "config": connection,
            }
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            print(f"🌐 CREATE {service.upper()} NETWORK ERROR: {e!r}")
            return {"ok": False, "data": {"error": str(e)}, "subscription_url": "", "connection_details": "", "config": ""}
        except Exception as e:
            print(f"❌ CREATE {service.upper()} ERROR: {e!r}")
            return {"ok": False, "data": {"error": str(e)}, "subscription_url": "", "connection_details": "", "config": ""}
