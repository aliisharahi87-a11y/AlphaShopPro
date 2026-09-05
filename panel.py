import os
import uuid
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

    BRONZE_PANEL_URL,
    BRONZE_PANEL_USERNAME,
    BRONZE_PANEL_PASSWORD,

    DEFAULT_GROUP_ID,
    DEFAULT_HWID_LIMIT,
    DEFAULT_STATUS,
    SHADOWSOCKS_METHOD,
)


def _clean_panel_url(url: str) -> str:
    if not url:
        return ""

    url = url.strip()

    # حذف مسیرهای dashboard و #/
    if "/dashboard" in url:
        url = url.split("/dashboard", 1)[0]

    url = url.split("#", 1)[0]

    return url.rstrip("/")


def _panel_config(service="gold"):
    service = (service or "gold").lower()

    # -------------------------
    # SILVER - NEW PANEL
    # -------------------------
    if service == "silver":
        return (
            _clean_panel_url(
                os.getenv(
                    "SILVER_PANEL_URL_NEW",
                    SILVER_PANEL_URL or ""
                )
            ),
            os.getenv(
                "SILVER_PANEL_USERNAME_NEW",
                SILVER_PANEL_USERNAME or ""
            ),
            os.getenv(
                "SILVER_PANEL_PASSWORD_NEW",
                SILVER_PANEL_PASSWORD or ""
            ),
        )

    # -------------------------
    # BRONZE - OLD SILVER PANEL
    # -------------------------
    if service == "bronze":
        return (
            _clean_panel_url(
                os.getenv(
                    "BRONZE_PANEL_URL",
                    BRONZE_PANEL_URL or ""
                )
            ),
            os.getenv(
                "BRONZE_PANEL_USERNAME",
                BRONZE_PANEL_USERNAME or ""
            ),
            os.getenv(
                "BRONZE_PANEL_PASSWORD",
                BRONZE_PANEL_PASSWORD or ""
            ),
        )

    # -------------------------
    # GOLD
    # -------------------------
    return (
        _clean_panel_url(
            GOLD_PANEL_URL or PANEL_URL or ""
        ),
        GOLD_PANEL_USERNAME or PANEL_USERNAME,
        GOLD_PANEL_PASSWORD or PANEL_PASSWORD,
    )


async def _login(session, service="gold"):
    panel_url, username, password = _panel_config(service)

    if not panel_url:
        raise RuntimeError(
            f"Panel URL is empty for service={service}"
        )

    if not username or not password:
        raise RuntimeError(
            f"Panel credentials are empty for service={service}"
        )

    url = f"{panel_url}/api/admin/token"

    data = {
        "username": username,
        "password": password,
    }

    async with session.post(
        url,
        data=data,
        timeout=aiohttp.ClientTimeout(total=30),
    ) as response:

        text = await response.text()

        if response.status != 200:
            raise RuntimeError(
                f"Panel login failed [{service}] "
                f"HTTP {response.status}: {text[:1000]}"
            )

        try:
            result = await response.json()
        except Exception:
            raise RuntimeError(
                f"Panel login returned invalid JSON [{service}]: "
                f"{text[:1000]}"
            )

        token = result.get("access_token")

        if not token:
            raise RuntimeError(
                f"Panel login succeeded but access_token is missing "
                f"[{service}]"
            )

        return token


async def _get_inbounds(session, panel_url, token):
    url = f"{panel_url}/api/inbounds"

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    async with session.get(
        url,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=30),
    ) as response:

        text = await response.text()

        if response.status != 200:
            raise RuntimeError(
                f"Get inbounds failed HTTP {response.status}: "
                f"{text[:1000]}"
            )

        try:
            return await response.json()
        except Exception:
            raise RuntimeError(
                f"Invalid inbounds JSON: {text[:1000]}"
            )


def _build_marzban_inbounds(inbounds_data):
    """
    تبدیل پاسخ /api/inbounds به ساختار مورد نیاز Marzban:
    {
        "vless": ["tag1", "tag2"],
        "vmess": ["tag3"],
        ...
    }
    """

    result = {}

    if not isinstance(inbounds_data, dict):
        return result

    # حالت رایج:
    # {
    #   "vless": [...],
    #   "vmess": [...],
    #   ...
    # }
    for protocol in (
        "vless",
        "vmess",
        "trojan",
        "shadowsocks",
        "wireguard",
        "hysteria",
        "hysteria2",
    ):
        items = inbounds_data.get(protocol)

        if not isinstance(items, list):
            continue

        tags = []

        for item in items:
            if isinstance(item, str):
                tags.append(item)
                continue

            if isinstance(item, dict):
                tag = (
                    item.get("tag")
                    or item.get("remark")
                    or item.get("name")
                )

                if tag:
                    tags.append(tag)

        if tags:
            result[protocol] = tags

    return result


def _build_proxies(inbounds):
    """
    برای هر پروتکلی که inbound فعال دارد،
    proxy خالی می‌سازیم تا Marzban UUID/تنظیمات لازم را تولید کند.
    """

    proxies = {}

    for protocol in inbounds.keys():

        if protocol in (
            "vless",
            "vmess",
            "trojan",
            "shadowsocks",
            "wireguard",
            "hysteria",
            "hysteria2",
        ):
            proxies[protocol] = {}

    # اگر VLESS فعال باشد، flow استاندارد Reality را اضافه می‌کنیم
    if "vless" in proxies:
        proxies["vless"]["flow"] = "xtls-rprx-vision"

    return proxies


def _extract_subscription_url(data):
    if not isinstance(data, dict):
        return None

    # نام‌های رایج در نسخه‌های مختلف
    for key in (
        "subscription_url",
        "subscriptionUrl",
        "sub_url",
        "subscription",
    ):
        value = data.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    # بعضی نسخه‌ها لینک را داخل links می‌دهند
    links = data.get("links")

    if isinstance(links, list) and links:
        for link in links:
            if isinstance(link, str) and link.startswith(("http://", "https://")):
                return link

    return None


async def create_customer(
    username,
    data_limit_gb,
    service="gold",
    expire_days=30,
    note="",
):
    """
    ساخت کاربر در Gold / Silver / Bronze.

    data_limit_gb:
        حجم بر حسب GB

    service:
        gold
        silver
        bronze
    """

    service = (service or "gold").lower()

    panel_url, panel_username, panel_password = _panel_config(service)

    if not panel_url:
        raise RuntimeError(
            f"Panel URL not configured for {service}"
        )

    if not panel_username or not panel_password:
        raise RuntimeError(
            f"Panel credentials not configured for {service}"
        )

    # نام کاربری فقط حروف/اعداد/_
    safe_username = str(username)

    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789_"
    )

    safe_username = "".join(
        c if c in allowed else "_"
        for c in safe_username
    )

    if len(safe_username) < 3:
        safe_username = (
            f"user_{safe_username}"
        )

    safe_username = safe_username[:32]

    # جلوگیری از username تکراری
    safe_username = (
        f"{safe_username}_{uuid.uuid4().hex[:6]}"
    )

    data_limit_bytes = int(
        float(data_limit_gb) * 1024 * 1024 * 1024
    )

    if expire_days:
        expire = int(
            (datetime.utcnow() + timedelta(days=expire_days)).timestamp()
        )
    else:
        expire = 0

    async with aiohttp.ClientSession() as session:

        # -------------------------
        # LOGIN
        # -------------------------
        token = await _login(
            session,
            service=service,
        )

        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        # -------------------------
        # GET INBOUNDS
        # -------------------------
        inbounds_data = await _get_inbounds(
            session,
            panel_url,
            token,
        )

        inbounds = _build_marzban_inbounds(
            inbounds_data
        )

        if not inbounds:
            raise RuntimeError(
                f"No active inbounds found on {service} panel"
            )

        proxies = _build_proxies(inbounds)

        if not proxies:
            raise RuntimeError(
                f"No supported protocols found on {service} panel"
            )

        # -------------------------
        # CREATE USER
        # -------------------------
        payload = {
            "username": safe_username,
            "status": DEFAULT_STATUS or "active",
            "expire": expire,
            "data_limit": data_limit_bytes,
            "data_limit_reset_strategy": "no_reset",
            "proxies": proxies,
            "inbounds": inbounds,
            "note": note or f"AlphaShop {service}",
        }

        url = f"{panel_url}/api/user"

        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=45),
        ) as response:

            text = await response.text()

            if response.status not in (200, 201):
                raise RuntimeError(
                    f"Create user failed [{service}] "
                    f"HTTP {response.status}: {text[:2000]}"
                )

            try:
                result = await response.json()
            except Exception:
                raise RuntimeError(
                    f"Create user returned invalid JSON [{service}]: "
                    f"{text[:2000]}"
                )

        subscription_url = _extract_subscription_url(result)

        # DEBUG: ساختار پاسخ پنل بدون نمایش توکن/رمز
        print(
            f"[PANEL DEBUG] service={service} "
            f"username={safe_username} "
            f"response_keys={list(result.keys()) if isinstance(result, dict) else type(result).__name__}"
        )
        if isinstance(result, dict):
            print(
                f"[PANEL DEBUG] service={service} "
                f"subscription_url={result.get('subscription_url')!r} "
                f"subscriptionUrl={result.get('subscriptionUrl')!r} "
                f"links_type={type(result.get('links')).__name__}"
            )

        # -------------------------
        # GET FULL USER DATA
        # بعضی نسخه‌های Marzban لینک Subscription
        # را در پاسخ POST /api/user نمی‌فرستند.
        # -------------------------
        if not subscription_url:
            try:
                user_url = f"{panel_url}/api/user/{safe_username}"

                async with session.get(
                    user_url,
                    headers={
                        "accept": "application/json",
                        "Authorization": f"Bearer {token}",
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as user_response:

                    user_text = await user_response.text()

                    if user_response.status == 200:
                        try:
                            full_user = await user_response.json()

                            found_url = _extract_subscription_url(full_user)

                            if found_url:
                                subscription_url = found_url

                            # اطلاعات کامل‌تر را نگه می‌داریم
                            if isinstance(full_user, dict):
                                result = full_user

                        except Exception:
                            pass

            except Exception:
                pass

        # -------------------------
        # RETURN STANDARD RESULT
        # -------------------------
        final_username = result.get(
            "username",
            safe_username
        )

        # خروجی سازگار با bot.py قدیمی و جدید
        return {
            "ok": True,
            "success": True,
            "service": service,
            "username": final_username,

            "subscription_url": subscription_url,

            # bot.py این کلیدها را هم بررسی می‌کند
            "connection_details": subscription_url or "",
            "config": subscription_url or "",

            "links": result.get("links", []),

            "data": {
                "username": final_username,
                "subscription_url": subscription_url,
                "subscriptionUrl": subscription_url,
                "config": subscription_url,
                "link": subscription_url,
                "url": subscription_url,
            },

            "expire": result.get("expire", expire),

            "data_limit": result.get(
                "data_limit",
                data_limit_bytes
            ),

            "raw": result,
        }
