from flask import Flask
import threading
import os
import traceback

app = Flask(__name__)

@app.route("/")
def home():
    return "AlphaShopPro Bot Running ✅"

def start_bot():
    try:
        import asyncio
        import bot

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        bot.run_bot()

    except Exception:
        traceback.print_exc()

thread = threading.Thread(target=start_bot)
thread.daemon = True
thread.start()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False,
        use_reloader=False,
    )
