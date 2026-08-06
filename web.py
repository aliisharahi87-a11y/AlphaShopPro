from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "AlphaShopPro Bot Running ✅"

def start_bot():
    import bot
    bot.run_bot()

threading.Thread(target=start_bot, daemon=True).start()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False,
        use_reloader=False
    )
