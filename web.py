from flask import Flask
import threading
import traceback
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "AlphaShopPro Bot is Running"

def start_bot():
    try:
        import bot
        bot.run_bot()
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    threading.Thread(target=start_bot, daemon=True).start()

    print("Starting Flask on port", os.environ.get("PORT"))

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False,
        use_reloader=False,
    )
