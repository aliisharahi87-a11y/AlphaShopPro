from flask import Flask
import threading
import traceback
import time
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "AlphaShopPro Bot Running ✅"

def run_web():
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False,
        use_reloader=False,
    )

def run_bot_forever():
    while True:
        try:
            import bot
            print("Starting Telegram Bot...", flush=True)
            bot.run_bot()
        except Exception:
            traceback.print_exc()
            print("Bot crashed. Restarting in 5 seconds...", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    run_bot_forever()
