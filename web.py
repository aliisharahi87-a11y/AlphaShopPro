def start_bot():
    import traceback
    try:
        import bot
        print("BOT IMPORTED")
        bot.run_bot()
    except Exception:
        traceback.print_exc()
