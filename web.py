from flask import Flask
import threading
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

if __name__ == "__main__":
    # Flask در Thread فرعی
    threading.Thread(target=run_web, daemon=True).start()

    # بات در Thread اصلی
    import bot
    bot.run_bot()
