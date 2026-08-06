import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip()
]

REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "").strip()
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "").strip()

CARD_NUMBER = os.getenv("CARD_NUMBER", "").strip()
CARD_HOLDER = os.getenv("CARD_HOLDER", "").strip()

CUSTOM_PRICE_PER_GB = int(os.getenv("CUSTOM_PRICE_PER_GB", "4000"))
REFERRAL_PERCENT = int(os.getenv("REFERRAL_PERCENT", "10"))

DATABASE_FILE = os.getenv("DATABASE_FILE", "alphashop.db")

# ==========================
# Pasargard / Remnawave
# ==========================

PANEL_URL = os.getenv("PANEL_URL", "").rstrip("/")

PANEL_USERNAME = os.getenv("PANEL_USERNAME", "").strip()

PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "").strip()

PANEL_API_TOKEN = os.getenv("PANEL_API_TOKEN", "").strip()

# ==========================
# Free Test
# ==========================

FREE_TEST_ENABLED = os.getenv(
    "FREE_TEST_ENABLED",
    "True"
).lower() == "true"

FREE_TEST_GB = float(
    os.getenv(
        "FREE_TEST_GB",
        "0.2"
    )
)

FREE_TEST_DAYS = int(
    os.getenv(
        "FREE_TEST_DAYS",
        "1"
    )
)

FREE_TEST_GROUP_ID = int(
    os.getenv(
        "FREE_TEST_GROUP_ID",
        "1"
    )
)

DEFAULT_GROUP_ID = int(
    os.getenv(
        "DEFAULT_GROUP_ID",
        "1"
    )
)

DEFAULT_HWID_LIMIT = int(
    os.getenv(
        "DEFAULT_HWID_LIMIT",
        "0"
    )
)

DEFAULT_STATUS = os.getenv(
    "DEFAULT_STATUS",
    "active"
)

SHADOWSOCKS_METHOD = os.getenv(
    "SHADOWSOCKS_METHOD",
    "chacha20-ietf-poly1305"
)

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO"
)
