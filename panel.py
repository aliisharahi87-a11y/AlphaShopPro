import asyncio
import uuid
from datetime import datetime, timedelta

import aiohttp

from config import *

GB = 1024 * 1024 * 1024


def _clean_url(value):
    value = (value or "").strip().rstrip("/")
    for suffix in ("/dashboard/#", "/dashboard/", "/dashboard", "/#"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value.rstrip("/")


def _panel_config(service="gold"):
    service = (service or "gold").lower()
    if service == "silver":
        return _clean_url(SILVER_PANEL_URL), SILVER_PANEL_USERNAME, SILVER_PANEL_PASSWORD
    if service == "bronze":
        return _clean_url(BRONZE_PANEL_URL), BRONZE_PANEL_USERNAME, BRONZE_PANEL_PASSWORD
    return _clean_url(GOLD_PANEL_URL or PANEL_URL), GOLD_PANEL_USERNAME or PANEL_USERNAME, GOLD_PANEL_PASSWORD or PANEL_PASSWORD


def _normalize_url(value, panel_url=""):
    if not value:
        return ""
    if isinstance(value, (list, tuple)):
        return "\n".join(str(x) for x in value if x)
    value = str(value).strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("/") and panel_url:
        return panel_url.rstrip("/") + value
    return value


def _extract_connection(data, panel_url=""):
    if isinstance(data, str):
        return _normalize_url(data, panel_url)
    if isinstance(data, list):
        vals = [x for x in (_extract_connection(v, panel_url) for v in data) if x]
        return "\n".join(vals)
    if not isinstance(data, dict):
        return ""

    keys = (
        "subscription_url", "subscriptionUrl", "sub_url", "subUrl",
        "subscription", "config", "link", "url", "links", "links_base64",
        "xray", "vless", "vmess", "trojan", "clash", "clash_meta", "sing_box",
    )
    for key in keys:
        value = data.get(key)
        if isinstance(value, (str, list)) and value:
            result = _normalize_url(value, panel_url)
            if result:
                return result
        if isinstance(value, dict):
            result = _extract_connection(value, panel_url)
            if result:
                return result

    for value in data.values():
        if isinstance(value, (dict, list)):
            result = _extract_connection(value, panel_url)
            if result:
                return result
    return ""


async def _request_json(session, method, url, **kwargs):
    async with session.request(method, url, **kwargs) as r:
        raw = await r.text()
        try:
            data = await r.json(content_type=None)
        except Exception:
            data = {"raw": raw}
        return r.status, data, raw


async def _login(session, service="gold"):
    panel_url, username, password = _panel_config(service)
    if not panel_url:
        raise RuntimeError(f"{service.title()} panel URL is not configured")
    if not username or not password:
        raise RuntimeError(f"{service.title()} panel credentials are not configured")

    status, data, _ = await _request_json(
        session, "POST", f"{panel_url}/api/admin/token",
        data={"grant_type": "password", "username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    if status != 200:
        raise RuntimeError(f"Login Error ({service}) HTTP {status}: {data}")
    token = data.get("access_token") if isinstance(data, dict) else None
    if not token:
        raise RuntimeError(f"Login response has no access_token ({service}): {data}")
    return token, panel_url


def _expire(days):
    return (datetime.now().astimezone() + timedelta(days=days)).isoformat(timespec="seconds")


def _pasargard_payload(username, gb, unlimited, days, group_ids, note):
    return {
        "username": username,
        "status": DEFAULT_STATUS,
        "data_limit": 0 if unlimited else int(float(gb) * GB),
        "expire": _expire(days),
        "group_ids": group_ids,
        "hwid_limit": None if DEFAULT_HWID_LIMIT == 0 else DEFAULT_HWID_LIMIT,
        "next_plan": None,
        "note": note,
        "proxy_settings": {"shadowsocks": {"method": SHADOWSOCKS_METHOD}},
    }


def _parse_inbounds(data):
    found = []
    if isinstance(data, dict):
        for protocol, items in data.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        tag = item.get("tag") or item.get("remark") or item.get("name") or item.get("id")
                        proto = str(item.get("protocol") or protocol).lower()
                        if tag:
                            found.append((proto, str(tag)))
                    elif isinstance(item, str):
                        found.append((str(protocol).lower(), item))
            elif isinstance(items, dict):
                tag = items.get("tag") or items.get("remark") or items.get("name")
                if tag:
                    found.append((str(items.get("protocol") or protocol).lower(), str(tag)))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                tag = item.get("tag") or item.get("remark") or item.get("name")
                proto = str(item.get("protocol") or item.get("type") or "vless").lower()
                if tag:
                    found.append((proto, str(tag)))
    return found


def _marzban_proxy(protocol):
    ident = str(uuid.uuid4())
    protocol = protocol.lower()
    if protocol == "vless":
        value = {"id": ident}
        if SILVER_VLESS_FLOW:
            value["flow"] = SILVER_VLESS_FLOW
        return value
    if protocol == "vmess":
        return {"id": ident, "alterId": 0}
    if protocol == "trojan":
        return {"password": ident}
    if protocol == "shadowsocks":
        return {"method": SILVER_SHADOWSOCKS_METHOD, "password": ident}
    return {"id": ident}


async def _create_marzban(session, token, panel_url, username, gb, unlimited, days, note):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
    status, inbound_data, _ = await _request_json(session, "GET", f"{panel_url}/api/inbounds", headers=headers)
    if status != 200:
        raise RuntimeError(f"Marzban /api/inbounds failed HTTP {status}: {inbound_data}")

    inbounds = _parse_inbounds(inbound_data)
    wanted_name = SILVER_INBOUND_NAME.lower()
    selected = None
    if wanted_name:
        selected = next((x for x in inbounds if x[1].lower() == wanted_name), None)
    if not selected:
        selected = next((x for x in inbounds if x[0] == SILVER_PROTOCOL), None)
    if not selected and inbounds:
        selected = inbounds[0]
    if not selected:
        raise RuntimeError("Marzban returned no usable inbounds; set SILVER_INBOUND_NAME")

    protocol, inbound_name = selected
    proxy = _marzban_proxy(protocol)
    payload = {
        "username": username,
        "proxies": {protocol: proxy},
        "inbounds": {protocol: [inbound_name]},
        "data_limit": 0 if unlimited else int(float(gb) * GB),
        "expire": int((datetime.now().astimezone() + timedelta(days=days)).timestamp()),
        "data_limit_reset_strategy": "no_reset",
        "status": "active",
        "note": note,
    }
    status, data, _ = await _request_json(session, "POST", f"{panel_url}/api/user", headers=headers, json=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Marzban create user failed HTTP {status}: {data}")
    return data


async def _get_subscription(session, token, panel_url, username):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    for path in (
        f"/api/user/{username}/subscription/links",
        f"/api/user/by-username/{username}/subscription/links",
        f"/api/user/{username}",
        f"/api/user/by-username/{username}",
    ):
        try:
            status, data, raw = await _request_json(session, "GET", panel_url + path, headers=headers)
            if status == 200:
                result = _extract_connection(data, panel_url)
                if result:
                    return result
                if isinstance(data, str) and data.strip():
                    return data.strip()
                if isinstance(raw, str) and raw.strip() and not raw.lstrip().startswith("{"):
                    return raw.strip()
        except Exception as exc:
            print("Subscription lookup failed:", path, repr(exc))
    return ""


async def create_customer(username, gb, unlimited=False, days=30, group_ids=None, note="", service="gold"):
    """Provision a customer with retries and recovery for lost API responses."""
    service = (service or "gold").lower()
    if group_ids is None:
        group_ids = [DEFAULT_GROUP_ID]

    # Panel APIs can occasionally take a few seconds or reset a connection.
    # Keep the operation bounded, but retry transient failures.
    timeout = aiohttp.ClientTimeout(total=60, connect=12, sock_connect=12, sock_read=35)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        last_error = None
        for attempt in range(1, 4):
            try:
                token, panel_url = await _login(session, service)

                if service == "silver":
                    try:
                        data = await _create_marzban(session, token, panel_url, username, gb, unlimited, days, note)
                    except Exception as create_exc:
                        # A request may have succeeded server-side while the response
                        # was lost. Check the user before declaring failure.
                        recovered = await _get_subscription(session, token, panel_url, username)
                        if recovered:
                            return {
                                "ok": True,
                                "data": {"username": username},
                                "username": username,
                                "subscription_url": recovered,
                                "connection_details": recovered,
                                "config": recovered,
                            }
                        raise create_exc
                else:
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    }
                    payload = _pasargard_payload(username, gb, unlimited, days, group_ids, note)
                    status, data, _ = await _request_json(
                        session, "POST", f"{panel_url}/api/user",
                        headers=headers, json=payload
                    )

                    # Some Pasargard versions reject optional fields.
                    if status in (400, 422):
                        minimal = {
                            "username": username,
                            "status": DEFAULT_STATUS,
                            "data_limit": payload["data_limit"],
                            "expire": payload["expire"],
                            "note": note,
                            "proxy_settings": payload["proxy_settings"],
                        }
                        status, data, _ = await _request_json(
                            session, "POST", f"{panel_url}/api/user",
                            headers=headers, json=minimal
                        )

                    if status not in (200, 201):
                        # If the first POST actually created the user but its response
                        # was lost, the user/subscription lookup can recover it.
                        recovered = await _get_subscription(session, token, panel_url, username)
                        if recovered:
                            data = {"username": username}
                        else:
                            raise RuntimeError(
                                f"{service.title()} create user failed HTTP {status}: {data}"
                            )

                    connection = _extract_connection(data, panel_url)
                    if not connection:
                        connection = await _get_subscription(session, token, panel_url, username)

                    final_username = data.get("username", username) if isinstance(data, dict) else username
                    if not connection:
                        raise RuntimeError(
                            f"{service.title()} user was created but no subscription/config was returned"
                        )

                    return {
                        "ok": True,
                        "data": data,
                        "username": final_username,
                        "subscription_url": connection,
                        "connection_details": connection,
                        "config": connection,
                    }

                # Marzban path: always verify/retrieve subscription after creation.
                connection = _extract_connection(data, panel_url)
                if not connection:
                    connection = await _get_subscription(session, token, panel_url, username)
                final_username = data.get("username", username) if isinstance(data, dict) else username
                if not connection:
                    raise RuntimeError(
                        f"{service.title()} user was created but no subscription/config was returned"
                    )
                return {
                    "ok": True,
                    "data": data,
                    "username": final_username,
                    "subscription_url": connection,
                    "connection_details": connection,
                    "config": connection,
                }

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc
                print(f"⚠️ {service.upper()} transient panel error (attempt {attempt}/3): {exc!r}")
                if attempt < 3:
                    await asyncio.sleep(2 * attempt)
                    continue
            except Exception as exc:
                last_error = exc
                print(f"❌ {service.upper()} PANEL ERROR (attempt {attempt}/3):", repr(exc))
                # For API 5xx/temporary failures hidden inside RuntimeError, retry.
                msg = str(exc)
                if attempt < 3 and any(x in msg for x in ("HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504", "timeout", "Timeout")):
                    await asyncio.sleep(2 * attempt)
                    continue
                break

        return {
            "ok": False,
            "data": {"error": str(last_error or "Panel provisioning failed")},
            "subscription_url": "",
            "connection_details": "",
            "config": "",
        }
