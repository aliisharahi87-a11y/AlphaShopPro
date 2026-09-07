import os
from dotenv import load_dotenv

load_dotenv()

def _s(name, default=""):
    return os.getenv(name, default).strip()

def _i(name, default):
    try:
        return int(_s(name, str(default)))
    except ValueError:
        return default

def _f(name, default):
    try:
        return float(_s(name, str(default)))
    except ValueError:
        return default

BOT_TOKEN = _s("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in _s("ADMIN_IDS").split(",") if x.strip().isdigit()]
REQUIRED_CHANNEL = _s("REQUIRED_CHANNEL")
SUPPORT_USERNAME = _s("SUPPORT_USERNAME")
CARD_NUMBER = _s("CARD_NUMBER")
CARD_HOLDER = _s("CARD_HOLDER")
CUSTOM_PRICE_PER_GB = _i("CUSTOM_PRICE_PER_GB", 4000)
REFERRAL_PERCENT = _i("REFERRAL_PERCENT", 10)
DATABASE_FILE = _s("DATABASE_FILE", "alphashop.db")

# Legacy/default Pasargard panel. Kept for backward compatibility.
PANEL_URL = _s("PANEL_URL").rstrip("/")
PANEL_USERNAME = _s("PANEL_USERNAME")
PANEL_PASSWORD = _s("PANEL_PASSWORD")
PANEL_API_TOKEN = _s("PANEL_API_TOKEN")

# Gold = Pasargard
GOLD_PANEL_URL = _s("GOLD_PANEL_URL", PANEL_URL).rstrip("/")
GOLD_PANEL_USERNAME = _s("GOLD_PANEL_USERNAME", PANEL_USERNAME)
GOLD_PANEL_PASSWORD = _s("GOLD_PANEL_PASSWORD", PANEL_PASSWORD)
GOLD_PRICE_PER_GB = _i("GOLD_PRICE_PER_GB", 5000)

# Silver = Marzban
SILVER_PANEL_URL = _s("SILVER_PANEL_URL", "https://pan.linkesubs.com").rstrip("/")
SILVER_PANEL_USERNAME = _s("SILVER_PANEL_USERNAME")
SILVER_PANEL_PASSWORD = _s("SILVER_PANEL_PASSWORD")
SILVER_PANEL_API_TOKEN = _s("SILVER_PANEL_API_TOKEN")
SILVER_PRICE_PER_GB = _i("SILVER_PRICE_PER_GB", 3000)
SILVER_INBOUND_NAME = _s("SILVER_INBOUND_NAME")
SILVER_PROTOCOL = _s("SILVER_PROTOCOL", "vless").lower()
SILVER_VLESS_FLOW = _s("SILVER_VLESS_FLOW")
SILVER_SHADOWSOCKS_METHOD = _s("SILVER_SHADOWSOCKS_METHOD", "chacha20-ietf-poly1305")

# Bronze = old Pasargard / old Silver panel
BRONZE_PANEL_URL = _s("BRONZE_PANEL_URL").rstrip("/")
BRONZE_PANEL_USERNAME = _s("BRONZE_PANEL_USERNAME")
BRONZE_PANEL_PASSWORD = _s("BRONZE_PANEL_PASSWORD")
BRONZE_PRICE_PER_GB = _i("BRONZE_PRICE_PER_GB", 1000)

FREE_TEST_ENABLED = _s("FREE_TEST_ENABLED", "True").lower() == "true"
FREE_TEST_GB = _f("FREE_TEST_GB", 0.15)
FREE_TEST_DAYS = _i("FREE_TEST_DAYS", 1)
RENEW_DAYS = _i("RENEW_DAYS", 30)
FREE_TEST_GROUP_ID = _i("FREE_TEST_GROUP_ID", 1)
DEFAULT_GROUP_ID = _i("DEFAULT_GROUP_ID", 1)
DEFAULT_HWID_LIMIT = _i("DEFAULT_HWID_LIMIT", 0)
DEFAULT_STATUS = _s("DEFAULT_STATUS", "active") or "active"
SHADOWSOCKS_METHOD = _s("SHADOWSOCKS_METHOD", "chacha20-ietf-poly1305")
LOG_LEVEL = _s("LOG_LEVEL", "INFO")

# Guide tutorial videos. Local files are included in the final package;
# these can also be overridden with Telegram file_id values in .env.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GUIDE_VIDEO_V2BOX = _s("GUIDE_VIDEO_V2BOX", os.path.join(_BASE_DIR, "tutorial_videos", "V2Box.mp4"))
GUIDE_VIDEO_HAPP = _s("GUIDE_VIDEO_HAPP", os.path.join(_BASE_DIR, "tutorial_videos", "Happ.mp4"))
GUIDE_VIDEO_HIDDIFY = _s("GUIDE_VIDEO_HIDDIFY", os.path.join(_BASE_DIR, "tutorial_videos", "Hiddify.mp4"))
GUIDE_VIDEO_STREISAND = _s("GUIDE_VIDEO_STREISAND", os.path.join(_BASE_DIR, "tutorial_videos", "Streisand.mp4"))
