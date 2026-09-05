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

    # Marzban can also be used with a pre-issued bearer token.
    if service == "silver" and SILVER_PANEL_API_TOKEN:
        return SILVER_PANEL_API_TOKEN.strip(), panel_url

    if not username or not password:
        raise RuntimeError(f"{service.title()} panel credentials are not configured")

    status, data, raw = await _request_json(
        session, "POST", f"{panel_url}/api/admin/token",
        data={"grant_type": "password", "username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    if status != 200:
        raise RuntimeError(f"Login Error ({service}) HTTP {status}: {data or raw}")
    token = data.get("access_token") if isinstance(data, dict) else None
    if not token:
        raise RuntimeError(f"Login response has no access_token ({service}): {data or raw}")
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
    """Normalize Marzban /api/inbounds responses across versions."""
    found = []

    def add(proto, tag):
        proto = str(proto or "").strip().lower()
        tag = str(tag or "").strip()
        if proto and tag and (proto, tag) not in found:
            found.append((proto, tag))

    def walk(obj, protocol_hint=None):
        if isinstance(obj, dict):
            # Common Marzban shape: {"vless": [{"tag": "..."}], ...}
            for key, value in obj.items():
                key_l = str(key).lower()
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            proto = item.get("protocol") or item.get("type") or key_l
                            tag = item.get("tag") or item.get("remark") or item.get("name") or item.get("id")
                            add(proto, tag)
                            walk(item, proto)
                        elif isinstance(item, str):
                            add(key_l, item)
                elif isinstance(value, dict):
                    proto = value.get("protocol") or value.get("type") or key_l
                    tag = value.get("tag") or value.get("remark") or value.get("name") or value.get("id")
                    add(proto, tag)
                    walk(value, proto)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    proto = item.get("protocol") or item.get("type") or protocol_hint
                    tag = item.get("tag") or item.get("remark") or item.get("name") or item.get("id")
                    add(proto, tag)
                    walk(item, proto)
                elif isinstance(item, str) and protocol_hint:
                    add(protocol_hint, item)

    walk(data)
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
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # /api/inbounds returns: {"vless": [{"tag": ..., ...}], "vmess": [...]}
    # But an inbound list is optional in POST /api/user: an empty inbounds
    # object means all inbounds for that protocol. Therefore failure to read
    # /api/inbounds must not block account creation.
    inbounds = []
    try:
        status, inbound_data, raw = await _request_json(
            session, "GET", f"{panel_url}/api/inbounds", headers=headers
        )
        if status == 200:
            inbounds = _parse_inbounds(inbound_data)
        else:
            print(f"⚠️ Marzban /api/inbounds HTTP {status}: {inbound_data or raw}")
    except Exception as exc:
        print("⚠️ Marzban /api/inbounds lookup failed:", repr(exc))

    wanted_name = str(SILVER_INBOUND_NAME or "").strip().lower()
    wanted_protocol = str(SILVER_PROTOCOL or "").strip().lower()
    supported = {"vless", "vmess", "trojan", "shadowsocks"}

    # Prefer the explicitly configured inbound/protocol, but never force a
    # disabled protocol. Marzban rejects POST /api/user with HTTP 400 when
    # the proxy type is not enabled in Xray. If the configured protocol is
    # unavailable, automatically use the first protocol actually reported by
    # /api/inbounds.
    selected = []
    if wanted_name and inbounds:
        selected = [x for x in inbounds if x[1].lower() == wanted_name]
    if not selected and wanted_protocol in supported and inbounds:
        selected = [x for x in inbounds if x[0] == wanted_protocol]
    if not selected and inbounds:
        selected = [inbounds[0]]

    if selected:
        protocol = selected[0][0] if selected[0][0] in supported else "vless"
        tags = [tag for proto, tag in selected if proto == protocol and tag]
        inbound_map = {protocol: tags} if tags else {}
    else:
        protocol = wanted_protocol if wanted_protocol in supported else "vless"
        inbound_map = {}

    protocols = {protocol: _marzban_proxy(protocol)}

    expire = 0 if unlimited else int(
        (datetime.now().astimezone() + timedelta(days=days)).timestamp()
    )
    payload = {
        "username": username,
        "proxies": protocols,
        "inbounds": inbound_map,
        "expire": expire,
        "data_limit": 0 if unlimited else int(float(gb) * GB),
        "data_limit_reset_strategy": "no_reset",
        "status": "active",
        "note": note or "",
    }

    print(f"🟣 MARZBAN CREATE -> user={username} protocol={protocol} inbounds={inbound_map}")

    status, data, raw = await _request_json(
        session, "POST", f"{panel_url}/api/user", headers=headers, json=payload
    )

    # If the configured protocol is disabled, try each protocol actually
    # present in /api/inbounds. This is important for panels where the admin
    # changed the active inbound from VLESS to VMess/Trojan/etc.
    if status == 400 and inbounds:
        tried = {protocol}
        for candidate in [proto for proto, _tag in inbounds]:
            if candidate not in supported or candidate in tried:
                continue
            tried.add(candidate)
            candidate_tags = [tag for proto, tag in inbounds if proto == candidate and tag]
            retry_payload = dict(payload)
            retry_payload["proxies"] = {candidate: _marzban_proxy(candidate)}
            retry_payload["inbounds"] = {candidate: candidate_tags} if candidate_tags else {}
            print(f"🔁 MARZBAN RETRY -> protocol={candidate} inbounds={retry_payload['inbounds']}")
            status, data, raw = await _request_json(
                session, "POST", f"{panel_url}/api/user", headers=headers, json=retry_payload
            )
            if status in (200, 201, 409):
                break

    # A 422 can happen when an installation has a different proxy/inbound
    # combination. Retry with empty inbounds so Marzban uses all inbounds for
    # the selected protocol.
    if status == 422 and inbound_map:
        fallback = dict(payload)
        fallback["inbounds"] = {}
        status, data, raw = await _request_json(
            session, "POST", f"{panel_url}/api/user", headers=headers, json=fallback
        )

    if status == 409:
        recovered = await _get_subscription(session, token, panel_url, username)
        if recovered:
            return {"username": username, "subscription_url": recovered, "links": [recovered]}
        raise RuntimeError(f"Marzban user already exists HTTP 409: {data or raw}")

    if status not in (200, 201):
        raise RuntimeError(f"Marzban create user failed HTTP {status}: {data or raw}")

    # UserResponse officially contains subscription_url and links.
    verified_status, verified_data, verified_raw = await _request_json(
        session, "GET", f"{panel_url}/api/user/{username}", headers=headers
    )
    if verified_status == 200 and isinstance(verified_data, dict):
        merged = dict(data) if isinstance(data, dict) else {}
        merged.update(verified_data)
        return merged

    return data


async def _get_subscription(session, token, panel_url, username):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    for path in (
        f"/api/user/{username}",
        f"/api/user/{username}/subscription/links",
        f"/api/user/{username}/subscription",
        f"/api/user/by-username/{username}",
        f"/api/user/by-username/{username}/subscription/links",
        f"/api/user/by-username/{username}/subscription",
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
                    # Explicitly inspect the canonical UserResponse fields first.
                    if isinstance(data, dict):
                        connection = _normalize_url(data.get("subscription_url"), panel_url)
                        if not connection:
                            connection = _normalize_url(data.get("subscriptionUrl"), panel_url)
                        if not connection:
                            connection = _normalize_url(data.get("links"), panel_url)
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
