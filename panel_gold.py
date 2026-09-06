"""Panel router for Alpha Shop.

The three service implementations remain isolated:
- Gold   -> panel_gold.py (Pasargard)
- Silver -> panel_silver.py (Marzban)
- Bronze -> panel_bronze.py (Pasargard)
"""



async def create_customer(username, gb, unlimited=False, days=30, group_ids=None, note="", service="gold"):
    service = str(service or "gold").strip().lower()
    if service == "gold":
        return await create_gold_customer(username, gb, unlimited, days, group_ids, note)
    if service == "silver":
        return await create_silver_customer(username, gb, unlimited, days, group_ids, note)
    if service == "bronze":
        return await create_bronze_customer(username, gb, unlimited, days, group_ids, note)
    return {
        "ok": False,
        "data": {"error": f"Unknown service: {service}"},
        "subscription_url": "",
        "connection_details": "",
        "config": "",
    }
