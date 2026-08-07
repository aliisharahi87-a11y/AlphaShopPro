from flask import Flask
import threading
import traceback
import asyncio
import time
import os

app = Flask(__name__)


@app.route("/")
def home():
    return "AlphaShopPro Bot Running ✅"


def start_bot():
    while True:
        try:
            print("🚀 Starting bot thread...")

            # ساخت Event Loop مخصوص این Thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            print("✅ Event loop created")

            import bot

            print("✅ Bot module imported")
            print("🚀 Starting Telegram bot...")

            bot.run_bot()

            print("⚠️ bot.run_bot() stopped unexpectedly")

        except Exception:
            print("❌❌❌ BOT CRASHED ❌❌❌")
            traceback.print_exc()
            print("🔄 Restarting bot in 10 seconds...")

        finally:
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    loop.close()
            except Exception:
                pass

        time.sleep(10)


if __name__ == "__main__":

    print("🌐 Starting AlphaShopPro Web Service...")

    bot_thread = threading.Thread(
        target=start_bot,
        name="start_bot",
        daemon=True
    )

    bot_thread.start()

    print("✅ Bot thread started")

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False,
        use_reloader=False
    )
