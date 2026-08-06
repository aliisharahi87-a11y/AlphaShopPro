#!/usr/bin/env python3
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent
BOT = ROOT / "bot.py"
BACKUP = ROOT / "bot.py.backup"

if not BOT.exists():
    raise SystemExit("bot.py پیدا نشد. این فایل را داخل پوشه AlphaShopPro قرار بده.")

src = BOT.read_text(encoding="utf-8")
shutil.copy2(BOT, BACKUP)

def replace_function(text, name, new_code):
    pattern = re.compile(
        rf"(?ms)^async def {re.escape(name)}\(.*?(?=^async def |^def |^if __name__|\Z)"
    )
    m = pattern.search(text)
    if not m:
        raise RuntimeError(f"تابع {name} در bot.py پیدا نشد.")
    return text[:m.start()] + new_code.rstrip() + "\n\n" + text[m.end():]

def remove_all_functions(text, names):
    for name in names:
        pattern = re.compile(
            rf"(?ms)^async def {re.escape(name)}\(.*?(?=^async def |^def |^if __name__|\Z)"
        )
        text = pattern.sub("", text)
    return text

BUY = r'''async def buy(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    try:
        pid = int(query.data.split(":")[1])
    except (ValueError, IndexError):
        await query.message.reply_text("❌ سرویس نامعتبر است.")
        return

    p = db.get_plan(pid)
    if not p or not p["active"]:
        await query.message.reply_text("❌ این سرویس در دسترس نیست.")
        return

    coupon = context.user_data.get("coupon")
    original_price = int(p["price"])
    final_price = apply_discount(original_price, coupon)

    discount_text = ""
    if coupon:
        percent = int(coupon["percent"] or 0)
        amount = int(coupon["amount"] or 0)
        saved = original_price - final_price
        code = context.user_data.get("coupon_code", "فعال")
        if percent:
            discount_text = (
                f"\n🎟 کد تخفیف: <code>{code}</code>"
                f"\n🎁 تخفیف: <b>{percent}%</b>"
                f"\n💸 مقدار تخفیف: <b>{saved:,} تومان</b>"
            )
        elif amount:
            discount_text = (
                f"\n🎟 کد تخفیف: <code>{code}</code>"
                f"\n🎁 تخفیف: <b>{saved:,} تومان</b>"
            )

    title = p["title_fa"] if lang(uid) == "fa" else p["title_en"]

    if lang(uid) == "fa":
        text = (
            "🛒 <b>تأیید خرید سرویس</b>\n\n"
            f"📦 سرویس: <b>{title}</b>\n"
            "⏳ مدت: <b>۱ ماه</b>\n"
            "👤 کاربران: <b>نامحدود</b>\n"
            f"💰 قیمت اصلی: <b>{original_price:,} تومان</b>"
            f"{discount_text}\n"
            f"\n💳 <b>قیمت نهایی: {final_price:,} تومان</b>\n\n"
            "اگر اطلاعات بالا درست است، روی «✅ تأیید پرداخت» بزنید."
        )
        confirm_text = "✅ تأیید پرداخت"
        cancel_text = "❌ لغو خرید"
    else:
        text = (
            "🛒 <b>Confirm Service Purchase</b>\n\n"
            f"📦 Service: <b>{title}</b>\n"
            "⏳ Duration: <b>1 month</b>\n"
            "👤 Users: <b>Unlimited</b>\n"
            f"💰 Original price: <b>{original_price:,} Toman</b>"
            f"{discount_text}\n"
            f"\n💳 <b>Final price: {final_price:,} Toman</b>\n\n"
            "If everything is correct, tap «✅ Confirm Payment»."
        )
        confirm_text = "✅ Confirm Payment"
        cancel_text = "❌ Cancel Purchase"

    context.user_data["pending_purchase"] = {
        "plan_id": int(p["id"]),
        "gb": p["gb"],
        "unlimited": bool(p["unlimited"]),
        "original_price": original_price,
        "price": final_price,
        "title": title,
    }

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            confirm_text,
            callback_data=f"confirm_buy:{p['id']}"
        )],
        [InlineKeyboardButton(
            cancel_text,
            callback_data="cancel_buy"
        )],
    ])

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )
'''

CUSTOM_GB = r'''async def custom_gb(update, context):
    uid = update.effective_user.id

    try:
        gb = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(tr(uid, "invalid_gb"))
        return CUSTOM_GB

    if gb < 1:
        await update.message.reply_text(tr(uid, "invalid_gb"))
        return CUSTOM_GB

    original_price = gb * CUSTOM_PRICE_PER_GB
    coupon = context.user_data.get("coupon")
    final_price = apply_discount(original_price, coupon)

    discount_text = ""
    if coupon:
        percent = int(coupon["percent"] or 0)
        amount = int(coupon["amount"] or 0)
        saved = original_price - final_price
        code = context.user_data.get("coupon_code", "فعال")
        if percent:
            discount_text = (
                f"\n🎟 کد تخفیف: <code>{code}</code>"
                f"\n🎁 تخفیف: <b>{percent}%</b>"
                f"\n💸 مقدار تخفیف: <b>{saved:,} تومان</b>"
            )
        elif amount:
            discount_text = (
                f"\n🎟 کد تخفیف: <code>{code}</code>"
                f"\n🎁 تخفیف: <b>{saved:,} تومان</b>"
            )

    if lang(uid) == "fa":
        text = (
            "🛒 <b>تأیید خرید حجم دلخواه</b>\n\n"
            f"📦 حجم: <b>{gb} GB</b>\n"
            "⏳ مدت: <b>۱ ماه</b>\n"
            "👤 کاربران: <b>نامحدود</b>\n"
            f"💰 قیمت اصلی: <b>{original_price:,} تومان</b>"
            f"{discount_text}\n"
            f"\n💳 <b>قیمت نهایی: {final_price:,} تومان</b>\n\n"
            "اگر اطلاعات بالا درست است، روی «✅ تأیید پرداخت» بزنید."
        )
        confirm_text = "✅ تأیید پرداخت"
        cancel_text = "❌ لغو خرید"
    else:
        text = (
            "🛒 <b>Confirm Custom Purchase</b>\n\n"
            f"📦 Volume: <b>{gb} GB</b>\n"
            "⏳ Duration: <b>1 month</b>\n"
            "👤 Users: <b>Unlimited</b>\n"
            f"💰 Original price: <b>{original_price:,} Toman</b>"
            f"{discount_text}\n"
            f"\n💳 <b>Final price: {final_price:,} Toman</b>\n\n"
            "If everything is correct, tap «✅ Confirm Payment»."
        )
        confirm_text = "✅ Confirm Payment"
        cancel_text = "❌ Cancel Purchase"

    context.user_data["pending_purchase"] = {
        "plan_id": None,
        "gb": gb,
        "unlimited": False,
        "original_price": original_price,
        "price": final_price,
        "title": f"{gb} GB",
    }

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(confirm_text, callback_data="confirm_custom")],
        [InlineKeyboardButton(cancel_text, callback_data="cancel_buy")],
    ])

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )

    return ConversationHandler.END
'''

CONFIRM_FUNCTIONS = r'''async def _complete_pending_purchase(update, context):
    query = update.callback_query
    uid = query.from_user.id
    pending = context.user_data.get("pending_purchase")

    if not pending:
        await query.answer("❌ سفارش منقضی شده است.", show_alert=True)
        return

    await query.answer()

    u = db.get_user(uid)
    if not u:
        await query.message.reply_text("❌ حساب کاربری پیدا نشد.")
        context.user_data.pop("pending_purchase", None)
        return

    price = int(pending["price"])
    gb = pending["gb"]
    unlimited = bool(pending["unlimited"])
    plan_id = pending["plan_id"]

    if u["balance"] < price:
        await query.message.reply_text(
            tr(uid, "not_enough", balance=u["balance"], price=price),
            reply_markup=menu(uid),
        )
        return

    oid = db.create_order(uid, plan_id, gb, price)
    if not oid:
        await query.message.reply_text(
            tr(uid, "not_enough", balance=u["balance"], price=price),
            reply_markup=menu(uid),
        )
        return

    username = f"alpha_{uid}_{oid}"
    result = await create_customer(username, gb, unlimited)

    if not result["ok"]:
        db.refund(oid, uid, price)
        context.user_data.pop("pending_purchase", None)
        await query.message.reply_text(
            tr(uid, "panel_error"),
            reply_markup=menu(uid),
        )
        return

    data = result.get("data") or {}
    config = (
        data.get("config")
        or data.get("subscription")
        or data.get("link")
        or data.get("url")
        or ""
    )
    final_username = data.get("username", username)

    db.complete_order(oid, final_username, str(config))

    # Only clear coupon after successful purchase.
    context.user_data.pop("pending_purchase", None)
    context.user_data.pop("coupon", None)
    context.user_data.pop("coupon_code", None)

    await query.message.reply_text(
        tr(
            uid,
            "order_success",
            oid=oid,
            gb="Unlimited" if unlimited else f"{gb} GB",
            price=price,
            username=final_username,
            config=config or "Panel API did not return connection details.",
        ),
        reply_markup=menu(uid),
    )


async def confirm_buy(update, context):
    query = update.callback_query
    try:
        pid = int(query.data.split(":")[1])
    except (ValueError, IndexError):
        await query.answer("❌ سفارش نامعتبر است.", show_alert=True)
        return

    pending = context.user_data.get("pending_purchase")
    if not pending or pending.get("plan_id") != pid:
        await query.answer("❌ سفارش پیدا نشد.", show_alert=True)
        return

    await _complete_pending_purchase(update, context)


async def confirm_custom(update, context):
    pending = context.user_data.get("pending_purchase")
    if not pending or pending.get("plan_id") is not None:
        await update.callback_query.answer(
            "❌ سفارش پیدا نشد.",
            show_alert=True,
        )
        return

    await _complete_pending_purchase(update, context)


async def cancel_buy(update, context):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    # IMPORTANT: cancel removes only the pending purchase.
    # The coupon remains active.
    context.user_data.pop("pending_purchase", None)

    if lang(uid) == "fa":
        text = (
            "❌ <b>خرید لغو شد.</b>\n\n"
            "کد تخفیف شما حذف نشده و همچنان فعال است. 🎟️\n"
            "می‌توانید سرویس دیگری انتخاب کنید و از همان کد استفاده کنید."
        )
    else:
        text = (
            "❌ <b>Purchase cancelled.</b>\n\n"
            "Your coupon has NOT been removed and is still active. 🎟️\n"
            "You can choose another service and use the same coupon."
        )

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=menu(uid),
    )
'''

COUPON_FUNCTIONS = r'''async def coupon_start(update, context):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    context.user_data.pop("coupon", None)
    context.user_data.pop("coupon_code", None)

    if lang(uid) == "fa":
        text = (
            "🎟 <b>کد تخفیف</b>\n\n"
            "کد تخفیف خود را ارسال کنید.\n"
            "برای برگشت، یکی از دکمه‌های منو را انتخاب کنید."
        )
    else:
        text = (
            "🎟 <b>Coupon Code</b>\n\n"
            "Send your coupon code.\n"
            "To leave this section, use one of the menu buttons."
        )

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=menu(uid),
    )
    return COUPON_INPUT


async def coupon_input(update, context):
    uid = update.effective_user.id
    code = update.message.text.strip().upper()

    menu_values = {
        "🏠 منوی اصلی", "🛒 فروشگاه", "💰 کیف پول",
        "👤 حساب کاربری", "👥 زیرمجموعه‌گیری", "📞 پشتیبانی",
        "⚙️ تنظیمات", "📚 راهنما", "🛒 خرید سرویس", "📦 سفارش‌های من",
        "🏠 MAIN MENU", "🛒 SHOP", "💰 WALLET",
        "👤 ACCOUNT", "👥 REFERRALS", "📞 SUPPORT",
        "⚙️ SETTINGS", "📚 GUIDE", "🛒 BUY SERVICE", "📦 MY ORDERS",
    }

    if code in menu_values:
        await update.message.reply_text(
            tr(uid, "welcome", name=update.effective_user.first_name or ""),
            reply_markup=menu(uid),
        )
        return ConversationHandler.END

    if not code:
        await update.message.reply_text(
            tr(uid, "coupon_bad"),
            reply_markup=menu(uid),
        )
        return COUPON_INPUT

    coupon = db.get_coupon(code)
    if not coupon:
        await update.message.reply_text(
            tr(uid, "coupon_bad") +
            "\n\n🔄 لطفاً یک کد تخفیف معتبر وارد کنید.",
            reply_markup=menu(uid),
        )
        return COUPON_INPUT

    if coupon["max_uses"] and coupon["used"] >= coupon["max_uses"]:
        await update.message.reply_text(
            tr(uid, "coupon_bad") +
            "\n\n🔄 ظرفیت استفاده از این کد تمام شده است.",
            reply_markup=menu(uid),
        )
        return COUPON_INPUT

    has_used = getattr(db, "has_coupon_used", None)
    if has_used and has_used(code, uid):
        await update.message.reply_text(
            "❌ شما قبلاً از این کد تخفیف استفاده کرده‌اید.\n\n"
            "🔄 لطفاً کد دیگری وارد کنید.",
            reply_markup=menu(uid),
        )
        return COUPON_INPUT

    # IMPORTANT: do not call use_coupon here.
    # The coupon is consumed only after successful purchase.
    context.user_data["coupon"] = dict(coupon)
    context.user_data["coupon_code"] = code

    percent = int(coupon["percent"] or 0)
    amount = int(coupon["amount"] or 0)
    discount_text = f"{percent}%" if percent else f"{amount:,} تومان"

    if lang(uid) == "fa":
        message = (
            "✅ <b>کد تخفیف فعال شد!</b>\n\n"
            f"🎟 کد: <code>{code}</code>\n"
            f"🎁 میزان تخفیف: <b>{discount_text}</b>\n\n"
            "این کد تا زمان خرید در حساب شما باقی می‌ماند.\n"
            "اگر خرید را لغو کنید، کد تخفیف حذف نمی‌شود. 🌹"
        )
    else:
        message = (
            "✅ <b>Coupon activated!</b>\n\n"
            f"🎟 Code: <code>{code}</code>\n"
            f"🎁 Discount: <b>{discount_text}</b>\n\n"
            "The coupon remains active until a successful purchase.\n"
            "If you cancel the purchase, it will not be removed. 🌹"
        )

    await update.message.reply_text(
        message,
        parse_mode="HTML",
        reply_markup=menu(uid),
    )
    return ConversationHandler.END
'''

src = replace_function(src, "buy", BUY)
src = replace_function(src, "custom_gb", CUSTOM_GB)

src = remove_all_functions(
    src,
    ["coupon_start", "coupon_input",
     "_complete_pending_purchase", "confirm_buy",
     "confirm_custom", "cancel_buy"]
)

marker = "\nasync def referrals("
if marker not in src:
    raise RuntimeError("محل درج توابع جدید پیدا نشد.")

src = src.replace(
    marker,
    "\n" + COUPON_FUNCTIONS.rstrip()
    + "\n\n" + CONFIRM_FUNCTIONS.rstrip()
    + marker,
    1,
)

handler_start = src.find("    deposit_conv = ConversationHandler(")
handler_end = src.find(
    '    app.add_handler(CommandHandler("start", start))',
    handler_start,
)
if handler_start == -1 or handler_end == -1:
    raise RuntimeError("بخش ConversationHandler در run_bot پیدا نشد.")

HANDLERS = r'''    deposit_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(deposit_start, pattern=r"^deposit$")
        ],
        states={
            DEP_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    deposit_amount,
                )
            ],
            DEP_RECEIPT: [
                MessageHandler(
                    filters.PHOTO,
                    deposit_receipt,
                )
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    custom_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(custom_start, pattern=r"^custom$")
        ],
        states={
            CUSTOM_GB: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    custom_gb,
                )
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    coupon_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(coupon_start, pattern=r"^coupon$")
        ],
        states={
            COUPON_INPUT: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND
                    & ~filters.Regex(
                        r"^(🏠 منوی اصلی|🛒 فروشگاه|💰 کیف پول|"
                        r"👤 حساب کاربری|👥 زیرمجموعه‌گیری|📞 پشتیبانی|"
                        r"⚙️ تنظیمات|📚 راهنما|🛒 خرید سرویس|📦 سفارش‌های من|"
                        r"🏠 Main Menu|🛒 Shop|💰 Wallet|"
                        r"👤 Account|👥 Referrals|📞 Support|"
                        r"⚙️ Settings|📚 Guide|🛒 Buy Service|📦 My Orders)$"
                    ),
                    coupon_input,
                )
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

'''
src = src[:handler_start] + HANDLERS + src[handler_end:]

needle = "    app.add_handler(coupon_conv)\n"
if needle not in src:
    raise RuntimeError("coupon_conv در run_bot پیدا نشد.")

extra = '''    app.add_handler(
        CallbackQueryHandler(confirm_buy, pattern=r"^confirm_buy:")
    )
    app.add_handler(
        CallbackQueryHandler(confirm_custom, pattern=r"^confirm_custom$")
    )
    app.add_handler(
        CallbackQueryHandler(cancel_buy, pattern=r"^cancel_buy$")
    )
'''
src = src.replace(needle, needle + extra, 1)

BOT.write_text(src, encoding="utf-8")
print("✅ bot.py با موفقیت اصلاح شد.")
print("📦 backup: bot.py.backup")
print("➡️ حالا اجرا کن: python -m py_compile bot.py")
