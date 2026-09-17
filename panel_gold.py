import asyncio
import os
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

    # Current PasarGuard versions prefer ID-based user endpoints.
    if user_id is not None:
        candidates.append(f"{panel_url}/api/user/by-id/{user_id}/subscription/links")
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



async def _get_all_gold_group_ids(session, panel_url, headers):
    """Return every usable PasarGuard group id for Gold."""
    endpoints = (
        f"{panel_url}/api/groups/simple",
        f"{panel_url}/api/groups",
        f"{panel_url}/api/group",
    )

    for endpoint in endpoints:
        try:
            async with session.get(endpoint, headers=headers) as response:
                data = await _read_json(response)
                print(f"🟡 GOLD GROUP HTTP {response.status}: {endpoint}")
                print(f"📥 GOLD GROUP RESPONSE: {data}")

                if response.status != 200:
                    continue

                items = data
                if isinstance(data, dict):
                    for key in ("groups", "items", "data", "results"):
                        if isinstance(data.get(key), list):
                            items = data[key]
                            break

                if not isinstance(items, list):
                    continue

                ids = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    gid = item.get("id") or item.get("group_id") or item.get("_id")
                    if gid is None or item.get("is_disabled") is True:
                        continue
                    try:
                        gid = int(gid)
                    except (TypeError, ValueError):
                        continue
                    if gid not in ids:
                        ids.append(gid)

                if ids:
                    print(f"✅ GOLD ALL GROUP IDS: {ids}")
                    return ids
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            print(f"⚠️ GOLD GROUP REQUEST FAILED: {endpoint}: {exc!r}")
        except Exception as exc:
            print(f"❌ GOLD GROUP ERROR: {endpoint}: {exc!r}")

    return []


async def _pasargard_create_customer(
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

    # Do not force a group ID: PasarGuard allows user creation without a group,
    # and a stale/nonexistent DEFAULT_GROUP_ID causes HTTP 422 on some panels.
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

            if service == "gold" and not group_ids:
                group_ids = await _get_all_gold_group_ids(session, panel_url, headers)

            group_ids = list(group_ids or [])
            if service == "gold" and not group_ids:
                return {
                    "ok": False,
                    "data": {"error": "No Gold groups were returned by PasarGuard"},
                    "subscription_url": "",
                    "connection_details": "",
                    "config": "",
                }

            print(f"🎯 GOLD GROUPS TO ASSIGN: {group_ids}")

            expire = (
                datetime.now().astimezone() + timedelta(days=int(days))
            ).isoformat(timespec="seconds")

            data_limit = 0 if unlimited else int(float(gb) * GB)

            # Keep the create payload compatible with current PasarGuard API.
            # Extra/null fields can make older installations reject the request.
            payload = {
                "username": str(username).strip(),
                "proxy_settings": {},
                "expire": expire,
                "data_limit": data_limit,
                "data_limit_reset_strategy": "no_reset",
                "status": DEFAULT_STATUS or "active",
            }

            if group_ids:
                payload["group_ids"] = group_ids
            if DEFAULT_HWID_LIMIT > 0:
                payload["hwid_limit"] = DEFAULT_HWID_LIMIT
            if note:
                payload["note"] = note

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
                    # PasarGuard returns 409 when this username already exists.
                    # In that case, reuse the existing user and retrieve its
                    # subscription link instead of treating the purchase as failed.
                    detail = ""
                    if isinstance(data, dict):
                        detail = str(data.get("detail") or data.get("message") or "").strip()

                    if response.status == 409 and "already exists" in detail.lower():
                        print(f"♻️ GOLD USER ALREADY EXISTS: {username}")
                        print("🔎 Fetching existing Gold user...")

                        existing_user = await _get_created_user(
                            session,
                            panel_url,
                            headers,
                            str(username).strip(),
                        )

                        connection = ""
                        if isinstance(existing_user, dict):
                            connection = str(
                                existing_user.get("subscription_url")
                                or existing_user.get("subscriptionUrl")
                                or ""
                            ).strip()

                            if not connection:
                                connection = _extract_connection(
                                    existing_user,
                                    panel_url,
                                )

                        if not connection:
                            links = await _get_subscription_links(
                                session,
                                panel_url,
                                headers,
                                existing_user if isinstance(existing_user, dict) else {},
                                str(username).strip(),
                            )
                            if links:
                                connection = links[0]

                        if connection:
                            merged = dict(existing_user) if isinstance(existing_user, dict) else {}
                            merged["username"] = str(username).strip()

                            return {
                                "ok": True,
                                "data": merged,
                                "username": str(username).strip(),
                                "subscription_url": connection,
                                "connection_details": connection,
                                "config": connection,
                            }

                        print("❌ Existing Gold user found, but no subscription link was returned.")

                    return {
                        "ok": False,
                        "data": data,
                        "subscription_url": "",
                        "connection_details": "",
                        "config": "",
                    }

            # 1) PasarGuard normally returns the subscription URL directly.
            connection = ""
            links = []

            if isinstance(data, dict):
                direct_subscription = (
                    data.get("subscription_url")
                    or data.get("subscriptionUrl")
                )
                if direct_subscription:
                    connection = str(direct_subscription).strip()
                    links = [connection]

            # 2) Fallback: extract a connection from the creation response.
            if not connection:
                connection = _extract_connection(data, panel_url)

            # 3) Fallback: fetch the newly-created user.
            user_data = {}
            if not connection:
                user_data = await _get_created_user(
                    session,
                    panel_url,
                    headers,
                    str(username).strip(),
                )

                if isinstance(user_data, dict):
                    direct_subscription = (
                        user_data.get("subscription_url")
                        or user_data.get("subscriptionUrl")
                    )
                    if direct_subscription:
                        connection = str(direct_subscription).strip()
                        links = [connection]

                if not connection:
                    connection = _extract_connection(
                        user_data,
                        panel_url,
                    )

            # 4) Final fallback: explicitly request subscription links.
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



async def _pasarguard_user_info(username, service="gold"):
    timeout = aiohttp.ClientTimeout(total=40, connect=10, sock_connect=10, sock_read=25)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            token, panel_url = await _login(session, service)
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
            username = str(username).strip()
            user_data = await _get_created_user(session, panel_url, headers, username)
            if not user_data:
                return {"ok": False, "error": "User not found on panel"}
            links = await _get_subscription_links(session, panel_url, headers, user_data, username)
            connection = _extract_connection(user_data, panel_url) or (links[0] if links else "")
            return {"ok": True, "user": user_data, "subscription_url": connection, "expire": user_data.get("expire"), "data_limit": user_data.get("data_limit"), "status": user_data.get("status")}
        except Exception as exc:
            print(f"❌ {service.upper()} USER INFO EXCEPTION: {exc!r}")
            return {"ok": False, "error": str(exc)}


def _expire_timestamp(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    try:
        return int(float(text))
    except ValueError:
        pass
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


async def _extend_pasarguard_customer(username, days=30, service="gold"):
    timeout = aiohttp.ClientTimeout(total=40, connect=10, sock_connect=10, sock_read=25)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            token, panel_url = await _login(session, service)
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
            username = str(username).strip()
            current = await _get_created_user(session, panel_url, headers, username)
            if not current:
                raise RuntimeError("User not found on panel")
            old = _expire_timestamp(current.get("expire"))
            now = int(datetime.now().timestamp())
            new_ts = max(old or now, now) + int(days) * 86400
            # PasarGuard accepts ISO expiration on user update.
            new_expire = datetime.fromtimestamp(new_ts).astimezone().isoformat(timespec="seconds")
            payload = {"expire": new_expire, "status": "active"}
            endpoints = (f"{panel_url}/api/user/by-username/{username}", f"{panel_url}/api/user/{username}")
            last = None
            for endpoint in endpoints:
                async with session.put(endpoint, headers=headers, json=payload) as r:
                    data = await _read_json(r)
                    print(f"🔄 {service.upper()} EXTEND HTTP {r.status}: {data}")
                    last = data
                    if r.status in (200, 201):
                        links = await _get_subscription_links(session, panel_url, headers, data if isinstance(data, dict) else current, username)
                        connection = _extract_connection(data, panel_url) or _extract_connection(current, panel_url) or (links[0] if links else "")
                        return {"ok": True, "data": data, "subscription_url": connection, "connection_details": connection, "config": connection, "expire": new_expire}
            raise RuntimeError(f"PasarGuard modify user failed: {last}")
        except Exception as exc:
            print(f"❌ {service.upper()} EXTEND EXCEPTION: {exc!r}")
            return {"ok": False, "data": {"error": str(exc)}, "subscription_url": "", "connection_details": "", "config": ""}


async def get_customer_info(username):
    return await _pasarguard_user_info(username, service="gold")

async def create_customer(username, gb, unlimited=False, days=30, group_ids=None, note=""):
    return await _pasargard_create_customer(
        username=username, gb=gb, unlimited=unlimited, days=days,
        group_ids=group_ids, note=note, service="gold"
    )

async def extend_customer(username, days=30):
    return await _extend_pasargard_customer(username, days=days, service="gold")
