from flask import Flask
import threading
import traceback
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "AlphaShopPro Bot Running ✅"

def start_bot():
    try:
        print("Starting bot...")
        import bot
        print("Bot imported")
        bot.run_bot()
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    threading.Thread(target=start_bot, daemon=True).start()

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False,
        use_reloader=False
    )
