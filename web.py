from flask import Flask
import threading
import traceback
import os
import asyncio
import time

app = Flask(__name__)


@app.route("/")
def home():
    return "AlphaShopPro Bot Running ✅"


def start_bot():
    while True:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            print("✅ Event loop created")

            import bot

            print("✅ Bot imported")

            bot.run_bot()

            print("⚠️ Bot stopped")

            loop.close()

        except Exception:
            print("❌ BOT ERROR:")
            traceback.print_exc()

        time.sleep(5)


if __name__ == "__main__":
    bot_thread = threading.Thread(
        target=start_bot,
        daemon=True,
        name="start_bot",
    )

    bot_thread.start()

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False,
        use_reloader=False,
    )
