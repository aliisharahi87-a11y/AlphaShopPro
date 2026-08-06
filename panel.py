import aiohttp
from datetime import datetime, timedelta

from config import (
    PANEL_URL,
    PANEL_USERNAME,
    PANEL_PASSWORD,
)

GB = 1024 * 1024 * 1024


async def _login(session):
    data = {
        "grant_type": "password",
        "username": PANEL_USERNAME,
        "password": PANEL_PASSWORD,
    }

    async with session.post(
        f"{PANEL_URL}/api/admin/token",
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Accept": "*/*",
        },
    ) as r:

        js = await r.json(content_type=None)

        if r.status != 200:
            raise Exception(f"Login Error: {js}")

        return js["access_token"]


async def create_customer(
    username,
    gb,
    unlimited=False,
    days=30,
    group_ids=None,
    note=""
):
    if group_ids is None:
        group_ids = [1]

    async with aiohttp.ClientSession() as session:

        token = await _login(session)

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        payload = {
            "username": username,
            "status": "active",
            "data_limit": 0 if unlimited else int(float(gb) * GB),
            "expire": (
                datetime.now().astimezone()
                + timedelta(days=days)
            ).isoformat(timespec="seconds"),
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

        async with session.post(
            f"{PANEL_URL}/api/user",
            headers=headers,
            json=payload,
        ) as r:

            data = await r.json(content_type=None)

            print("CREATE USER RESPONSE:", data)

            return {
                "ok": r.status in (200, 201),
                "data": data,
                "subscription_url": data.get("subscription_url"),
                "connection_details": data.get("subscription_url"),
            }
