import asyncio
from datetime import datetime, timedelta

import aiohttp

from config import (
    PANEL_URL,
    PANEL_USERNAME,
    PANEL_PASSWORD,

    GOLD_PANEL_URL,
    GOLD_PANEL_USERNAME,
    GOLD_PANEL_PASSWORD,

    SILVER_PANEL_URL_NEW,
    SILVER_PANEL_USERNAME_NEW,
    SILVER_PANEL_PASSWORD_NEW,

    BRONZE_PANEL_URL,
    BRONZE_PANEL_USERNAME,
    BRONZE_PANEL_PASSWORD,

    DEFAULT_GROUP_ID,
    DEFAULT_HWID_LIMIT,
    DEFAULT_STATUS,
    SHADOWSOCKS_METHOD,
)

GB = 1024 * 1024 * 1024


def _clean_panel_url(url):
    if not url:
        return ""

    url = str(url).strip().rstrip("/")

    # حذف مسیر داشبورد از URL
    for suffix in (
        "/dashboard/#",
        "/dashboard",
    ):
        if url.lower().endswith(suffix.lower()):
            url = url[: -len(suffix)].rstrip("/")

    return url


def _panel_config(service="gold"):
    service = (service or "gold").lower()

    if service == "silver":
        return (
            _clean_panel_url(SILVER_PANEL_URL_NEW),
            SILVER_PANEL_USERNAME_NEW,
            SILVER_PANEL_PASSWORD_NEW,
        )

    if service == "bronze":
        return (
            _clean_panel_url(BRONZE_PANEL_URL),
            BRONZE_PANEL_USERNAME,
            BRONZE_PANEL_PASSWORD,
        )

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

    if panel_url and value.startswith("/"):
        return panel_url.rstrip("/") + value

    if "." in value.split("/")[0]:
        return "https://" + value

    return value


def _extract_connection(data, panel_url=""):
    if not isinstance(data, dict):
        return ""

    candidates = [
        data.get("subscription_url"),
        data.get("subscriptionUrl"),
        data.get("subscription"),
        data.get("sub_url"),
        data.get("subUrl"),
        data.get("config"),
        data.get("link"),
        data.get("url"),
    ]

    subscription = data.get("subscription")

    if isinstance(subscription, dict):
        candidates.extend([
            subscription.get("url"),
            subscription.get("subscription_url"),
            subscription.get("subscriptionUrl"),
            subscription.get("link"),
        ])

    proxy_settings = data.get("proxy_settings")

    if isinstance(proxy_settings, dict):
        for value in proxy_settings.values():
            if isinstance(value, dict):
                candidates.extend([
                    value.get("subscription_url"),
                    value.get("subscriptionUrl"),
                    value.get("url"),
                    value.get("link"),
                ])

    for value in candidates:
        if isinstance(value, str) and value.strip():
            return _normalize_url(value, panel_url)

    return ""


async def _login(session, service="gold"):
    panel_url, username, password = _panel_config(service)

    if not panel_url:
        raise RuntimeError(
            f"{service.title()} panel URL is not configured"
        )

    if not username or not password:
        raise RuntimeError(
            f"{service.title()} panel credentials are not configured"
        )

    data = {
        "grant_type": "password",
        "username": username,
        "password": password,
    }

    print(
        f"🔐 LOGIN {service.upper()} -> "
        f"{panel_url} | user={username}"
    )

    try:
        async with session.post(
            f"{panel_url}/api/admin/token",
            data=data,
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        ) as r:

            raw = await r.text()

            try:
                js = await r.json(content_type=None)
            except Exception:
                js = {"raw": raw}

            print(
                f"🔐 LOGIN {service.upper()} STATUS:",
                r.status,
            )

            if r.status != 200:
                print(
                    f"❌ LOGIN {service.upper()} ERROR:",
                    js,
                )
                raise RuntimeError(
                    f"Login Error ({service}) HTTP {r.status}: {js}"
                )

            token = js.get("access_token")

            if not token:
                raise RuntimeError(
                    f"Login response has no access_token "
                    f"({service}): {js}"
                )

            print(f"✅ LOGIN {service.upper()} SUCCESS")

            return token, panel_url

    except asyncio.TimeoutError:
        raise RuntimeError(
            f"{service.title()} panel login timeout"
        )

    except aiohttp.ClientError as e:
        print(
            f"🌐 LOGIN {service.upper()} NETWORK ERROR:",
            repr(e),
        )
        raise RuntimeError(
            f"{service.title()} panel network error: {e}"
        )


async def create_customer(
    username,
    gb,
    unlimited=False,
    days=30,
    group_ids=None,
    note="",
    service="gold",
):
    service = (service or "gold").lower()

    if group_ids is None:
        group_ids = [DEFAULT_GROUP_ID]

    timeout = aiohttp.ClientTimeout(
        total=30,
        connect=10,
        sock_connect=10,
        sock_read=15,
    )

    connector = aiohttp.TCPConnector(
        limit=10,
        ttl_dns_cache=300,
    )

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
    ) as session:

        try:
            token, panel_url = await _login(
                session,
                service,
            )

            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            expire = (
                datetime.now().astimezone()
                + timedelta(days=days)
            ).isoformat(timespec="seconds")

            payload = {
                "username": username,
                "status": DEFAULT_STATUS or "active",
                "data_limit": (
                    0
                    if unlimited
                    else int(float(gb) * GB)
                ),
                "expire": expire,
                "group_ids": group_ids,
                "hwid_limit": (
                    None
                    if DEFAULT_HWID_LIMIT == 0
                    else DEFAULT_HWID_LIMIT
                ),
                "next_plan": None,
                "note": note,
                "proxy_settings": {
                    "shadowsocks": {
                        "method": SHADOWSOCKS_METHOD
                    }
                },
            }

            print(
                f"👤 CREATE {service.upper()} USER:",
                username,
            )
            print(
                f"📦 CREATE {service.upper()} GB:",
                gb,
            )

            async with session.post(
                f"{panel_url}/api/user",
                headers=headers,
                json=payload,
            ) as r:

                raw = await r.text()

                try:
                    data = await r.json(
                        content_type=None
                    )
                except Exception:
                    data = {"raw": raw}

                print(
                    f"👤 CREATE {service.upper()} STATUS:",
                    r.status,
                )
                print(
                    f"📥 CREATE {service.upper()} RESPONSE:",
                    data,
                )

                if r.status not in (200, 201):
                    return {
                        "ok": False,
                        "data": data,
                        "subscription_url": "",
                        "connection_details": "",
                        "config": "",
                    }

                subscription_url = _extract_connection(
                    data,
                    panel_url,
                )

                final_username = (
                    data.get("username", username)
                    if isinstance(data, dict)
                    else username
                )

                print(
                    f"🔗 {service.upper()} CONNECTION:",
                    subscription_url or "<EMPTY>",
                )

                return {
                    "ok": True,
                    "data": data,
                    "username": final_username,
                    "subscription_url": subscription_url,
                    "connection_details": subscription_url,
                    "config": subscription_url,
                }

        except asyncio.TimeoutError:
            return {
                "ok": False,
                "data": {"error": "Panel request timeout"},
                "subscription_url": "",
                "connection_details": "",
                "config": "",
            }

        except Exception as e:
            print(
                f"❌ CREATE {service.upper()} EXCEPTION:",
                repr(e),
            )

            return {
                "ok": False,
                "data": {"error": str(e)},
                "subscription_url": "",
                "connection_details": "",
                "config": "",
            }
