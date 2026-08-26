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
        return SILVER_PANEL_URL, SILVER_PANEL_USERNAME, SILVER_PANEL_PASSWORD
    # Backward compatible: Gold is the existing panel.
    return (GOLD_PANEL_URL or PANEL_URL,
            GOLD_PANEL_USERNAME or PANEL_USERNAME,
            GOLD_PANEL_PASSWORD or PANEL_PASSWORD)


async def _login(session, service="gold"):
    panel_url, username, password = _panel_config(service)
    if not panel_url or not username or not password:
        raise RuntimeError(f"{service.title()} panel credentials are not configured")

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
        if r.status != 200:
            raise Exception(f"Login Error ({service}): {js}")
        token = js.get("access_token")
        if not token:
            raise Exception(f"Login response has no access_token ({service}): {js}")
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

    async with aiohttp.ClientSession() as session:
        token, panel_url = await _login(session, service)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "username": username,
            "status": "active",
            "data_limit": 0 if unlimited else int(float(gb) * GB),
            "expire": (datetime.now().astimezone() + timedelta(days=days)).isoformat(timespec="seconds"),
            "group_ids": group_ids,
            "hwid_limit": None,
            "next_plan": None,
            "note": note,
            "proxy_settings": {
                "shadowsocks": {"method": "chacha20-ietf-poly1305"}
            },
        }
        async with session.post(
            f"{panel_url}/api/user",
            headers=headers,
            json=payload,
        ) as r:
            data = await r.json(content_type=None)
            print(f"CREATE {service.upper()} USER RESPONSE:", data)
            return {
                "ok": r.status in (200, 201),
                "data": data,
                "subscription_url": data.get("subscription_url"),
                "connection_details": data.get("subscription_url"),
            }
