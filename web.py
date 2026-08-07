from flask import Flask
import threading
import traceback
import os
import time

app = Flask(__name__)


@app.route("/")
def home():
    return "AlphaShopPro Bot Running ✅"


def start_bot():
    while True:
        try:
            print("Starting Telegram bot...")

            import bot

            print("Bot imported successfully")
            bot.run_bot()

            print("⚠️ bot.run_bot() stopped! Restarting in 5 seconds...")

        except Exception:
            print("❌ BOT CRASHED:")
            traceback.print_exc()

        time.sleep(5)


if __name__ == "__main__":
    bot_thread = threading.Thread(
        target=start_bot,
        daemon=True,
    )

    bot_thread.start()

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False,
        use_reloader=False,
    )
