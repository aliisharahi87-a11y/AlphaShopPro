from flask import Flask
import threading
import traceback
import os
import sys

app = Flask(__name__)

@app.route("/")
def home():
    return "AlphaShopPro Bot Running"

def start_bot():
    print(">>> Bot thread started", flush=True)
    try:
        import bot
        print(">>> bot.py imported", flush=True)
        bot.run_bot()
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()

if __name__ == "__main__":
    threading.Thread(target=start_bot, daemon=True).start()

    print(">>> Starting Flask", flush=True)

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False,
        use_reloader=False,
    )
