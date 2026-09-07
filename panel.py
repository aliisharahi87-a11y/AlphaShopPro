from panel_gold import create_customer as create_gold_customer, extend_customer as extend_gold_customer, get_customer_info as get_gold_customer_info
from panel_silver import create_customer as create_silver_customer, extend_customer as extend_silver_customer, get_customer_info as get_silver_customer_info
from panel_bronze import create_customer as create_bronze_customer, extend_customer as extend_bronze_customer, get_customer_info as get_bronze_customer_info

async def create_customer(username, gb, unlimited=False, days=30, group_ids=None, note="", service="gold"):
    service = str(service or "gold").strip().lower()
    if service == "gold":
        return await create_gold_customer(username, gb, unlimited, days, group_ids, note)
    if service == "silver":
        result = await create_silver_customer(username, gb, unlimited, days, group_ids, note)
        if result.get("subscription_url") and not result["subscription_url"].startswith(("http://", "https://")):
            result["subscription_url"] = "https://" + result["subscription_url"]
        return result
    if service == "bronze":
        return await create_bronze_customer(username, gb, unlimited, days, group_ids, note)
    return {"ok": False, "data": {"error": f"Unknown service: {service}"}, "subscription_url":"", "connection_details":"", "config":""}

async def extend_customer(username, days=30, service="gold"):
    service = str(service or "gold").strip().lower()
    if service == "gold": return await extend_gold_customer(username, days)
    if service == "silver": return await extend_silver_customer(username, days)
    if service == "bronze": return await extend_bronze_customer(username, days)
    return {"ok": False, "data": {"error": f"Unknown service: {service}"}}


async def get_customer_info(username, service="gold"):
    service = str(service or "gold").strip().lower()
    if service == "gold": return await get_gold_customer_info(username)
    if service == "silver": return await get_silver_customer_info(username)
    if service == "bronze": return await get_bronze_customer_info(username)
    return {"ok": False, "error": f"Unknown service: {service}"}
