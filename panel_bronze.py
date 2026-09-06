"""Bronze service - isolated Pasargard implementation."""
from panel_pasargard import create_pasargard_customer

async def create_customer(username, gb, unlimited=False, days=30, group_ids=None, note=""):
    return await create_pasargard_customer(
        username, gb, unlimited, days, group_ids, note, service="bronze"
    )
