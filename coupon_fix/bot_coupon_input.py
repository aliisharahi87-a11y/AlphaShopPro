async def coupon_input(update, context):
    uid = update.effective_user.id
    code = update.message.text.strip().upper()

    coupon = db.get_coupon(code)

    if not coupon:
        await update.message.reply_text(
            tr(uid, "coupon_bad")
            + "\n\n🔄 لطفاً یک کد تخفیف معتبر وارد کنید."
        )
        return COUPON_INPUT

    if coupon["max_uses"] and coupon["used"] >= coupon["max_uses"]:
        await update.message.reply_text(
            tr(uid, "coupon_bad")
            + "\n\n🔄 لطفاً یک کد تخفیف دیگر وارد کنید."
        )
        return COUPON_INPUT

    if db.has_coupon_used(code, uid):
        await update.message.reply_text(
            "❌ شما قبلاً از این کد تخفیف استفاده کرده‌اید.\n\n"
            "هر کد تخفیف فقط یک بار برای هر کاربر قابل استفاده است.\n\n"
            "🔄 لطفاً کد دیگری وارد کنید."
        )
        return COUPON_INPUT

    used_coupon = db.use_coupon(code, uid)

    if not used_coupon:
        await update.message.reply_text(
            tr(uid, "coupon_bad")
            + "\n\n🔄 لطفاً یک کد تخفیف دیگر وارد کنید."
        )
        return COUPON_INPUT

    context.user_data["coupon"] = dict(used_coupon)
    context.user_data["coupon_code"] = code

    percent = used_coupon["percent"] or 0
    amount = used_coupon["amount"] or 0

    if percent:
        discount_text = f"🎁 میزان تخفیف: {percent}%"
    else:
        discount_text = f"🎁 میزان تخفیف: {amount:,} تومان"

    await update.message.reply_text(
        "✅ کد تخفیف با موفقیت فعال شد!\n\n"
        f"🎟 کد: {code}\n"
        f"{discount_text}\n\n"
        "این تخفیف هنگام خرید اعمال خواهد شد. 🌹",
        reply_markup=menu(uid),
    )

    return ConversationHandler.END