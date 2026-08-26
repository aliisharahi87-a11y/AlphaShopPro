import aiohttp
from datetime import datetime, timedelta

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
)

GB = 1024 * 1024 * 1024


def _panel_config(service="gold"):
    service = (service or "gold").lower()

    if service == "silver":
        return (
            SILVER_PANEL_URL,
            SILVER_PANEL_USERNAME,
            SILVER_PANEL_PASSWORD,
        )

    return (
        GOLD_PANEL_URL or PANEL_URL,
        GOLD_PANEL_USERNAME or PANEL_USERNAME,
        GOLD_PANEL_PASSWORD or PANEL_PASSWORD,
    )


def _fix_url(value, panel_url=""):
    """
    لینک اتصال را کامل می‌کند.
    اگر پنل لینک را بدون http/https برگرداند،
    https:// به آن اضافه می‌شود.
    """
    if not value:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    # اگر لینک کامل است، دست نزن
    if value.startswith(("http://", "https://")):
        return value

    # اگر //example.com بود
    if value.startswith("//"):
        return "https:" + value

    # اگر خود پنل URL دارد و مقدار relative است
    if panel_url:
        base = panel_url.rstrip("/")

        if value.startswith("/"):
            return base + value

        return base + "/" + value

    return "https://" + value


def _extract_connection(data, panel_url=""):
    """
    لینک اتصال را از پاسخ‌های مختلف API پیدا می‌کند.
    """

    if not isinstance(data, dict):
        return ""

    candidates = [
        data.get("subscription_url"),
        data.get("subscription"),
        data.get("config"),
        data.get("link"),
        data.get("url"),
        data.get("subscription_link"),
        data.get("client_link"),
    ]

    # بعضی پنل‌ها اطلاعات را داخل proxy_settings برمی‌گردانند
    proxy = data.get("proxy_settings")

    if isinstance(proxy, dict):
        candidates.extend([
            proxy.get("subscription_url"),
            proxy.get("subscription"),
            proxy.get("config"),
            proxy.get("link"),
            proxy.get("url"),
        ])

    for value in candidates:
        if value:
            return _fix_url(value, panel_url)

    return ""


async def _login(session, service="gold"):
    panel_url, username, password = _panel_config(service)

    if not panel_url or not username or not password:
        raise RuntimeError(
            f"{service.title()} panel credentials are not configured"
        )

    panel_url = panel_url.rstrip("/")

    data = {
        "grant_type": "password",
        "username": username,
        "password": password,
    }

    async with session.post(
        f"{panel_url}/api/admin/token",
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Accept": "*/*",
        },
    ) as r:

        js = await r.json(content_type=None)

        print(f"LOGIN {service.upper()} STATUS:", r.status)
        print(f"LOGIN {service.upper()} RESPONSE:", js)

        if r.status != 200:
            raise Exception(
                f"Login Error ({service}): {js}"
            )

        token = js.get("access_token")

        if not token:
            raise Exception(
                f"Login response has no access_token ({service}): {js}"
            )

        return token, panel_url


async def create_customer(
    username,
    gb,
    unlimited=False,
    days=30,
    group_ids=None,
    note="",
    service="gold",
):
    if group_ids is None:
        group_ids = [1]

    service = (service or "gold").lower()

    timeout = aiohttp.ClientTimeout(
        total=25,
        connect=8,
        sock_connect=8,
        sock_read=15,
    )

    try:
        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            token, panel_url = await _login(
                session,
                service,
            )

            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            payload = {
                "username": username,
                "status": "active",
                "data_limit": (
                    0
                    if unlimited
                    else int(float(gb) * GB)
                ),
                "expire": (
                    datetime.now().astimezone()
                    + timedelta(days=days)
                ).isoformat(
                    timespec="seconds"
                ),
                "group_ids": group_ids,
                "hwid_limit": None,
                "next_plan": None,
                "note": note,
                "proxy_settings": {
                    "shadowsocks": {
                        "method": "chacha20-ietf-poly1305"
                    }
                },
            }

            print(
                f"CREATE {service.upper()} REQUEST:",
                payload
            )

            async with session.post(
                f"{panel_url}/api/user",
                headers=headers,
                json=payload,
            ) as r:

                data = await r.json(
                    content_type=None
                )

                print(
                    f"CREATE {service.upper()} STATUS:",
                    r.status
                )

                print(
                    f"CREATE {service.upper()} USER RESPONSE:",
                    data
                )

                if r.status not in (200, 201):
                    return {
                        "ok": False,
                        "data": data,
                        "subscription_url": "",
                        "connection_details": "",
                        "config": "",
                        "error": (
                            f"HTTP {r.status}: {data}"
                        ),
                    }

                connection = _extract_connection(
                    data,
                    panel_url,
                )

                return {
                    "ok": True,
                    "data": data,
                    "subscription_url": connection,
                    "connection_details": connection,
                    "config": connection,
                }

    except asyncio.TimeoutError:
        print(
            f"CREATE {service.upper()} ERROR: timeout"
        )

        return {
            "ok": False,
            "data": {},
            "subscription_url": "",
            "connection_details": "",
            "config": "",
            "error": "Panel request timeout",
        }

    except Exception as e:
        print(
            f"CREATE {service.upper()} ERROR:",
            repr(e)
        )

        return {
            "ok": False,
            "data": {},
            "subscription_url": "",
            "connection_details": "",
            "config": "",
            "error": str(e),
        }
