"""
AlphaShopPro - AI Tools
Safe read-only tools for the professional AI support system.
"""

import database as db


def get_wallet_balance(user_id):
    user_id = int(user_id)

    user = db.get_user(user_id)

    if not user:
        return {
            "ok": False,
            "error": "user_not_found",
        }

    return {
        "ok": True,
        "balance": int(user["balance"] or 0),
        "currency": "Toman",
    }


def get_alpha_coins(user_id):
    user_id = int(user_id)

    user = db.get_user(user_id)

    if not user:
        return {
            "ok": False,
            "error": "user_not_found",
        }

    coins = db.get_alpha_coins(user_id)

    return {
        "ok": True,
        "alpha_coins": int(coins),
        "value_toman": int(coins) * 100,
    }


def get_referrals(user_id):
    user_id = int(user_id)

    try:
        count = db.referrals(user_id)
    except Exception:
        count = 0

    return {
        "ok": True,
        "count": int(count or 0),
    }


def get_order_history(user_id, limit=10):
    user_id = int(user_id)
    limit = max(1, min(int(limit), 20))

    rows = db.user_orders(user_id)

    result = []

    for row in rows[:limit]:
        result.append({
            "id": int(row["id"]),
            "status": str(row["status"] or ""),
            "service": str(row["service"] or ""),
            "price": int(row["price"] or 0),
            "username": str(row["panel_username"] or ""),
        })

    return {
        "ok": True,
        "orders": result,
    }


def get_active_services(user_id):
    user_id = int(user_id)

    rows = db.user_orders(user_id)

    services = []

    for row in rows:
        if str(row["status"] or "").lower() != "completed":
            continue

        services.append({
            "order_id": int(row["id"]),
            "service": str(row["service"] or ""),
            "username": str(row["panel_username"] or ""),
            "gb": row["gb"],
            "config": bool(row["config"]),
        })

    return {
        "ok": True,
        "count": len(services),
        "services": services,
    }


def get_user_summary(user_id):
    user_id = int(user_id)

    return {
        "ok": True,
        "wallet": get_wallet_balance(user_id),
        "alpha_coin": get_alpha_coins(user_id),
        "referrals": get_referrals(user_id),
        "active_services": get_active_services(user_id),
        "orders": get_order_history(user_id, 10),
    }
