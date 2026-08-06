import time
import traceback

def start_bot():
    while True:
        try:
            import bot
            print("Starting Telegram bot...")
            bot.run_bot()
        except Exception:
            traceback.print_exc()
            print("Bot crashed. Restarting in 5 seconds...")
            time.sleep(5)
