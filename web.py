from flask import Flask
import threading
import os
import bot

app = Flask(__name__)

@app.route("/")
def home():
    return "AlphaShopPro Bot is Running ✅"

def run_bot():
    bot.run_bot()

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
