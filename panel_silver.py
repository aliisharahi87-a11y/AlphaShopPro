import asyncio
import os
import time
import uuid
import aiohttp

GB = 1024 * 1024 * 1024


def _clean_url(url):
    url = str(url or "").strip().rstrip("/")
    for marker in ("/dashboard", "/login", "/#", "#"):
        pos = url.lower().find(marker.lower())
        if pos > 0:
            url = url[:pos]
            break
    return url.rstrip("/")


def _config():
    return (
        _clean_url(os.getenv("SILVER_PANEL_URL_NEW") or os.getenv("SILVER_PANEL_URL") or "https://pan.linkesubs.com"),
        (os.getenv("SILVER_PANEL_USERNAME_NEW") or os.getenv("SILVER_PANEL_USERNAME") or "").strip(),
        (os.getenv("SILVER_PANEL_PASSWORD_NEW") or os.getenv("SILVER_PANEL_PASSWORD") or "").strip(),
    )


async def _json(response):
    raw = await response.text()
    try:
        return await response.json(content_type=None)
    except Exception:
        return {"raw": raw[:4000]}


def _normalize_connection_url(value):
    s = str(value or "").strip()
    if not s:
        return ""
    if s.startswith(("http://", "https://", "vless://", "vmess://", "trojan://", "ss://")):
        return s
    if s.startswith("//"):
        return "https:" + s
    # Marzban deployments may return the subscription URL without a scheme.
    if s.startswith(("pan.", "sub.", "link.", "localhost", "127.", "10.", "172.", "192.")) or "/" in s:
        return "https://" + s.lstrip("/")
    return "https://" + s.lstrip("/")


def _first_url(obj):
    if isinstance(obj, str):
        return _normalize_connection_url(obj)
    if isinstance(obj, dict):
        for k in ("subscription_url", "subscriptionUrl", "sub_url", "subUrl", "link", "url"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip(): return v.strip()
        for k in ("links", "subscription", "data", "user", "result"):
            if k in obj:
                r = _first_url(obj[k])
                if r: return r
    if isinstance(obj, list):
        for v in obj:
            r = _first_url(v)
            if r: return r
    return ""


def _protocols(data):
    out = {}

    if isinstance(data, dict):
        for proto, tags in data.items():
            p = str(proto).lower()

            if p in {"vless", "vmess", "trojan", "shadowsocks"}:
                vals = []

                if isinstance(tags, list):
                    for item in tags:
                        if isinstance(item, dict):
                            tag = (
                                item.get("tag")
                                or item.get("remark")
                                or item.get("name")
                            )
                            if tag:
                                vals.append(str(tag).strip())
                        elif item:
                            vals.append(str(item).strip())

                elif isinstance(tags, dict):
                    tag = (
                        tags.get("tag")
                        or tags.get("remark")
                        or tags.get("name")
                    )
                    if tag:
                        vals.append(str(tag).strip())
                    else:
                        vals.extend(
                            str(k).strip()
                            for k in tags.keys()
                            if k
                        )

                elif tags:
                    vals.append(str(tags).strip())

                vals = list(dict.fromkeys(v for v in vals if v))

                if vals or tags == {}:
                    out[p] = vals

        if not out:
            for key in ("data", "inbounds", "result"):
                if key in data:
                    return _protocols(data[key])

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                p = str(
                    item.get("protocol")
                    or item.get("type")
                    or ""
                ).lower()

                tag = (
                    item.get("tag")
                    or item.get("remark")
                    or item.get("name")
                )

                if (
                    p in {"vless", "vmess", "trojan", "shadowsocks"}
                    and tag
                ):
                    out.setdefault(p, []).append(str(tag).strip())

    for proto in list(out):
        out[proto] = list(dict.fromkeys(out[proto]))

    return out


def _proxy(protocol):
    uid = str(uuid.uuid4())
    if protocol == "vless":
        d = {"id": uid}
        flow = os.getenv("SILVER_VLESS_FLOW", "").strip()
        if flow: d["flow"] = flow
        return d
    if protocol == "vmess": return {"id": uid, "alterId": 0, "security": "auto"}
    if protocol == "trojan": return {"password": uid}
    if protocol == "shadowsocks": return {"method": os.getenv("SILVER_SHADOWSOCKS_METHOD", os.getenv("SHADOWSOCKS_METHOD", "chacha20-ietf-poly1305")), "password": uid}
    raise ValueError(f"Unsupported Marzban protocol: {protocol}")


async def _login(session, panel_url):
    token = os.getenv("SILVER_PANEL_API_TOKEN", "").strip()
    if token: return token
    _, user, password = _config()
    if not user or not password:
        raise RuntimeError("Silver Marzban credentials are missing")
    async with session.post(
        f"{panel_url}/api/admin/token",
        data={"grant_type": "password", "username": user, "password": password},
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
    ) as r:
        data = await _json(r)
        if r.status != 200: raise RuntimeError(f"Marzban login HTTP {r.status}: {data}")
        token = data.get("access_token") or data.get("token") if isinstance(data, dict) else None
        if not token: raise RuntimeError(f"Marzban login returned no token: {data}")
        return token


async def create_customer(username, gb, unlimited=False, days=30, group_ids=None, note=""):
    """
    Create a Silver/Marzban user using all available inbounds by default.

    SILVER_PROTOCOL:
      all      -> use every available inbound/protocol
      vless    -> use only VLESS
      vmess    -> use only VMess
      trojan   -> use only Trojan
      shadowsocks -> use only Shadowsocks
    """
    panel_url, _, _ = _config()
    timeout = aiohttp.ClientTimeout(
        total=60,
        connect=12,
        sock_connect=12,
        sock_read=35,
    )

    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            token = await _login(session, panel_url)

            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            # Get every available Marzban inbound.
            async with session.get(
                f"{panel_url}/api/inbounds",
                headers=headers,
            ) as r:
                inbound_data = await _json(r)

                if r.status != 200:
                    raise RuntimeError(
                        f"Marzban /api/inbounds HTTP {r.status}: {inbound_data}"
                    )

            inbound_map = _protocols(inbound_data)

            if not inbound_map:
                raise RuntimeError(
                    f"Marzban returned no usable inbounds: {inbound_data}"
                )

            wanted = os.getenv("SILVER_PROTOCOL", "all").strip().lower()
            wanted_name = os.getenv("SILVER_INBOUND_NAME", "").strip()

            # By default use ALL protocols/inbounds.
            if wanted in ("", "all", "*", "auto"):
                selected_map = {
                    proto: list(tags)
                    for proto, tags in inbound_map.items()
                }
            else:
                if wanted not in inbound_map:
                    raise RuntimeError(
                        f"Requested Silver protocol '{wanted}' is not available. "
                        f"Available: {', '.join(inbound_map.keys())}"
                    )

                selected_map = {
                    wanted: list(inbound_map[wanted])
                }

            # Optional explicit inbound name filter.
            if wanted_name:
                filtered = {}
                for proto, tags in selected_map.items():
                    if wanted_name in tags:
                        filtered[proto] = [wanted_name]

                if filtered:
                    selected_map = filtered

            if not selected_map:
                raise RuntimeError(
                    f"No Silver inbounds selected. Available: {inbound_map}"
                )

            limit = 0 if unlimited else int(float(gb) * GB)
            expire = int(time.time()) + int(days) * 86400

            # Build a proxy for EVERY selected protocol.
            proxies = {}
            for proto in selected_map:
                proxies[proto] = _proxy(proto)

            payload = {
                "username": str(username).strip(),
                "status": "active",
                "data_limit": limit,
                "expire": expire,
                "proxies": proxies,
                "inbounds": selected_map,
                "note": note or "AlphaShop Silver",
            }

            print(f"🥈 SILVER INBOUNDS: {selected_map}")
            print(f"🥈 SILVER PROTOCOLS: {list(selected_map.keys())}")

            async def post(p):
                async with session.post(
                    f"{panel_url}/api/user",
                    headers=headers,
                    json=p,
                ) as r:
                    return r.status, await _json(r)

            status, data = await post(payload)

            print(f"🥈 SILVER CREATE HTTP {status}: {data}")

            # If the panel rejects the combined configuration, retry
            # without explicit inbounds. This keeps compatibility with
            # Marzban installations that manage inbounds automatically.
            if status >= 400 and selected_map:
                fallback_payload = dict(payload)
                fallback_payload["inbounds"] = {}

                status, data = await post(fallback_payload)

                print(
                    f"🥈 SILVER ALL-INBOUND FALLBACK HTTP {status}: {data}"
                )

            # Final compatibility fallback: try each protocol separately.
            if status >= 400:
                last = data

                for proto, tags in selected_map.items():
                    trial = dict(payload)
                    trial["proxies"] = {proto: _proxy(proto)}
                    trial["inbounds"] = {proto: tags}

                    st, dat = await post(trial)

                    print(
                        f"🥈 SILVER PROTOCOL FALLBACK {proto} "
                        f"HTTP {st}: {dat}"
                    )

                    last = dat

                    if st in (200, 201, 409):
                        status = st
                        data = dat
                        break
                else:
                    data = last

            if status == 409:
                raise RuntimeError(f"Marzban user already exists: {username}")
            elif status not in (200, 201):
                raise RuntimeError(
                    f"Marzban create user HTTP {status}: {data}"
                )

            connection = _normalize_connection_url(_first_url(data))
            user_data = data

            if not connection:
                async with session.get(
                    f"{panel_url}/api/user/{username}",
                    headers=headers,
                ) as r:
                    user_data = await _json(r)

                    if r.status == 200:
                        connection = _first_url(user_data)

            if not connection:
                raise RuntimeError(
                    "Marzban user created but no subscription_url returned: "
                    f"{user_data}"
                )

            merged = (
                dict(data)
                if isinstance(data, dict)
                else {"response": data}
            )

            if isinstance(user_data, dict):
                merged["user"] = user_data

            # Silver subscription URL: force exactly one https://
            connection = str(connection or "").strip()

            while connection.startswith("https:/"):
                connection = connection[7:]

            while connection.startswith("http:/"):
                connection = connection[6:]

            connection = "https://" + connection.lstrip("/")

            if connection.startswith("https:///sub/"):
                connection = (
                    "https://pan.linkesubs.com/sub/"
                    + connection.split("/sub/", 1)[1]
                )
            elif connection.startswith("https://sub/"):
                connection = (
                    "https://pan.linkesubs.com/sub/"
                    + connection.split("https://sub/", 1)[1]
                )

            # Strictly enforce the exact purchased volume and expiry.
            expected_limit = 0 if unlimited else int(float(gb) * GB)
            expected_expire = int(time.time()) + int(days) * 86400
            async with session.get(f"{panel_url}/api/user/{username}", headers=headers) as r:
                verify = await _json(r)
                if r.status != 200:
                    raise RuntimeError(f"Marzban verification HTTP {r.status}: {verify}")
            got_limit = verify.get("data_limit") if isinstance(verify, dict) else None
            got_expire = verify.get("expire") if isinstance(verify, dict) else None
            if int(got_limit or -1) != expected_limit or got_expire is None or abs(int(got_expire) - expected_expire) > 120:
                print(f"⚠️ SILVER MISMATCH: limit={got_limit}/{expected_limit}, expire={got_expire}/{expected_expire}")
                update_payload = {"data_limit": expected_limit, "expire": expected_expire, "status": "active"}
                async with session.put(f"{panel_url}/api/user/{username}", headers=headers, json=update_payload) as r:
                    update_data = await _json(r)
                    print(f"🛠️ SILVER EXACT LIMIT UPDATE HTTP {r.status}: {update_data}")
                    if r.status not in (200, 201):
                        raise RuntimeError(f"Marzban exact limit update HTTP {r.status}: {update_data}")
                async with session.get(f"{panel_url}/api/user/{username}", headers=headers) as r:
                    verify = await _json(r)
                    if r.status != 200:
                        raise RuntimeError(f"Marzban re-verification HTTP {r.status}: {verify}")
                got_limit = verify.get("data_limit") if isinstance(verify, dict) else None
                got_expire = verify.get("expire") if isinstance(verify, dict) else None
                if int(got_limit or -1) != expected_limit or got_expire is None or abs(int(got_expire) - expected_expire) > 120:
                    raise RuntimeError(f"Marzban rejected exact limits: limit={got_limit}/{expected_limit}, expire={got_expire}/{expected_expire}")
            merged["verified_user"] = verify
            merged["data_limit"] = got_limit
            merged["expire"] = got_expire

            merged["subscription_url"] = connection
            merged["protocol_used"] = ",".join(selected_map.keys())
            merged["inbounds_used"] = selected_map

            return {
                "ok": True,
                "data": merged,
                "username": str(username).strip(),
                "subscription_url": connection,
                "connection_details": connection,
                "config": connection,
            }

        except Exception as exc:
            print(f"❌ SILVER EXCEPTION: {exc!r}")

            return {
                "ok": False,
                "data": {"error": str(exc)},
                "subscription_url": "",
                "connection_details": "",
                "config": "",
            }


async def extend_customer(username, days=30):
    """Extend an existing Marzban user from its current expiry date."""
    panel_url, _, _ = _config()
    timeout = aiohttp.ClientTimeout(total=60, connect=12, sock_connect=12, sock_read=35)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            token = await _login(session, panel_url)
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
            async with session.get(f"{panel_url}/api/user/{username}", headers=headers) as r:
                print(f"📊 SILVER USER RAW RESPONSE: {data}")
                current = await _json(r)
                if r.status != 200:
                    raise RuntimeError(f"Marzban get user HTTP {r.status}: {current}")

            old_expire = current.get("expire") if isinstance(current, dict) else None
            now = int(time.time())
            if old_expire is None:
                new_expire = now + int(days) * 86400
            else:
                try:
                    old_expire = int(old_expire)
                except (TypeError, ValueError):
                    old_expire = now
                new_expire = max(old_expire, now) + int(days) * 86400

            payload = {"expire": new_expire, "status": "active"}
            async with session.put(f"{panel_url}/api/user/{username}", headers=headers, json=payload) as r:
                data = await _json(r)
                print(f"🥈 SILVER EXTEND HTTP {r.status}: {data}")
                if r.status not in (200, 201):
                    raise RuntimeError(f"Marzban modify user HTTP {r.status}: {data}")

            connection = _first_url(data) or _first_url(current)
            return {"ok": True, "data": data, "subscription_url": connection,
                    "connection_details": connection, "config": connection, "expire": new_expire}
        except Exception as exc:
            print(f"❌ SILVER EXTEND EXCEPTION: {exc!r}")
            return {"ok": False, "data": {"error": str(exc)}, "subscription_url": "", "connection_details": "", "config": ""}


async def get_customer_info(username):
    panel_url, _, _ = _config()
    timeout = aiohttp.ClientTimeout(total=40, connect=10, sock_connect=10, sock_read=25)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            token = await _login(session, panel_url)
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
            username = str(username).strip()
            async with session.get(f"{panel_url}/api/user/{username}", headers=headers) as r:
                data = await _json(r)
                if r.status != 200:
                    return {"ok": False, "error": f"Marzban get user HTTP {r.status}: {data}"}
            connection = _first_url(data)
            return {"ok": True, "user": data, "subscription_url": connection, "expire": data.get("expire") if isinstance(data, dict) else None, "data_limit": data.get("data_limit") if isinstance(data, dict) else None,
                "used_traffic": data.get("used_traffic") if isinstance(data, dict) else None,
                "status": data.get("status") if isinstance(data, dict) else None}
        except Exception as exc:
            print(f"❌ SILVER USER INFO EXCEPTION: {exc!r}")
            return {"ok": False, "error": str(exc)}
