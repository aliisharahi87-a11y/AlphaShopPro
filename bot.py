import asyncio

from database import has_used_trial, set_trial_used
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import *
import database as db
from panel import create_customer


DEP_AMOUNT, DEP_RECEIPT, CUSTOM_GB, COUPON_INPUT = range(4)

TEXT = {
    "fa": {
        "welcome": "🌹 سلام {name} عزیز!\n\nبه آلفا شاپ خوش اومدی ❤️\nاز منوی زیر می‌تونی سرویس، کیف پول و حساب کاربری خودت رو مدیریت کنی.",
        "need": "🔒 برای استفاده از خدمات آلفا شاپ، ابتدا باید در کانال ما عضو بشی.",
        "joined": "✅ عضویتت با موفقیت تأیید شد. خوش اومدی 🌹",
        "join": "📢 عضویت در کانال",
        "check": "✅ بررسی عضویت",
        "buy": "🛒 خرید سرویس",
        "trial": "🎁 تست رایگان",
        "wallet": "💰 کیف پول",
        "refs": "👥 زیرمجموعه‌گیری",
        "orders": "📦 سفارش‌های من",
        "support": "📞 پشتیبانی",
        "settings": "⚙️ تنظیمات",
        "guide": "📚 راهنما",
        "lang": "🌐 تغییر زبان",
        "back": "🔙 بازگشت",
        "deposit": "➕ افزایش موجودی",
        "coupon": "🎟 کد تخفیف",
        "balance": "💰 موجودی کیف پول شما: {amount:,} تومان",
        "deposit_amount": "💳 مبلغ موردنظر برای افزایش موجودی را به تومان وارد کنید:",
        "min_deposit": "❌ حداقل مبلغ افزایش موجودی ۱,۰۰۰ تومان است.",
        "invalid_amount": "❌ لطفاً یک مبلغ معتبر وارد کنید.",
        "payment_info": "💳 اطلاعات پرداخت\n\nشماره کارت:\n{card}\n\nنام صاحب کارت:\n{holder}\n\nمبلغ: {amount:,} تومان\n\n📸 پس از پرداخت، تصویر رسید را همین‌جا ارسال کنید.",
        "receipt_only": "📸 لطفاً تصویر رسید پرداخت را ارسال کنید.",
        "receipt_saved": "✅ رسید شما با موفقیت ثبت شد.\n\nشماره پیگیری: #{rid}\nپس از بررسی ادمین، موجودی کیف پول شما افزایش پیدا می‌کند. 🌹",
        "plans": "🛒 یکی از سرویس‌های زیر را انتخاب کنید:",
        "custom": "✏️ حجم دلخواه",
        "custom_prompt": "✏️ حجم موردنظر را به GB وارد کنید.\n\n💰 قیمت هر گیگ: {price:,} تومان",
        "invalid_gb": "❌ حجم باید یک عدد صحیح بزرگ‌تر از صفر باشد.",
        "not_enough": "❌ موجودی کیف پول کافی نیست.\n\nموجودی: {balance:,} تومان\nقیمت: {price:,} تومان\n\nابتدا کیف پول خود را شارژ کنید.",
        "order_success": "🎉 سفارش شما با موفقیت ثبت شد!\n\n🧾 شماره سفارش: #{oid}\n📦 حجم: {gb}\n💰 مبلغ: {price:,} تومان\n👤 نام کاربری: {username}\n\n🔗 اطلاعات اتصال:\n{config}",
        "panel_error": "⚠️ سفارش ثبت شد اما اتصال به پنل با موفقیت انجام نشد؛ مبلغ سفارش به کیف پول شما برگشت داده شد.\n\nلطفاً با پشتیبانی تماس بگیرید.",
        "ref": "👥 تعداد زیرمجموعه‌های شما: {count}\n🎁 درصد پاداش فعلی: {percent}%\n\n🔗 لینک دعوت شما:\n{link}",
        "no_orders": "📦 هنوز سفارشی ثبت نکرده‌اید.",
        "support_text": "📞 پشتیبانی آلفا شاپ\n\nبرای ارتباط با پشتیبانی از آیدی زیر استفاده کنید:\n{support}",
        "account": "👤 حساب کاربری\n\n🆔 شناسه: {id}\n💰 موجودی: {balance:,} تومان\n🌐 زبان: فارسی",
        "settings_text": "⚙️ تنظیمات حساب\n\nاز دکمه‌های زیر می‌توانید زبان حساب را تغییر دهید.",
        "language_changed": "🇮🇷 زبان حساب روی فارسی تنظیم شد.",
        "coupon_prompt": "🎟 کد تخفیف خود را ارسال کنید:",
        "coupon_ok": "✅ کد تخفیف معتبر است. هنگام خرید قابل استفاده خواهد بود.",
        "coupon_bad": "❌ کد تخفیف نامعتبر، منقضی یا قبلاً استفاده شده است.",
        "guide_text": "📚 راهنمای آلفا شاپ\n\n"
                      "1️⃣ ابتدا عضو کانال شوید و روی «بررسی عضویت» بزنید.\n"
                      "2️⃣ از بخش «کیف پول» موجودی خود را افزایش دهید.\n"
                      "3️⃣ مبلغ را به کارت اعلام‌شده واریز کنید و رسید را ارسال کنید.\n"
                      "4️⃣ پس از تأیید ادمین، موجودی به کیف پول شما اضافه می‌شود.\n"
                      "5️⃣ از «خرید سرویس» حجم دلخواه خود را انتخاب کنید.\n"
                      "6️⃣ پرداخت از موجودی کیف پول انجام می‌شود.\n"
                      "7️⃣ در صورت فعال بودن API پنل، سرویس به‌صورت خودکار ساخته و اطلاعات اتصال ارسال می‌شود.\n\n"
                      "💡 در صورت هرگونه مشکل، با پشتیبانی در ارتباط باشید.",
        "admin_only": "⛔ این بخش فقط برای مدیران است.",
        "trial": "🎁 تست رایگان",
        "trial_used": "❌ شما قبلاً از تست رایگان استفاده کرده‌اید.",
        "trial_success": "🎉 تست رایگان شما فعال شد.\n\n📦 حجم: ۲۰۰ مگابایت\n📅 اعتبار: ۱ روز\n\n🔗 لینک اشتراک:\n{config}",
        "trial_error": "❌ ساخت تست رایگان با خطا مواجه شد.",
    },
    "en": {
        "welcome": "🌹 Hello {name}!\n\nWelcome to Alpha Shop ❤️\nUse the menu below to manage your services, wallet and account.",
        "need": "🔒 Please join our channel before using Alpha Shop.",
        "joined": "✅ Your membership has been verified. Welcome! 🌹",
        "join": "📢 Join Channel",
        "check": "✅ Check Membership",
        "buy": "🛒 Buy Service",
        "trial": "🎁 Free Trial",
        "wallet": "💰 Wallet",
        "refs": "👥 Referrals",
        "orders": "📦 My Orders",
        "support": "📞 Support",
        "settings": "⚙️ Settings",
        "guide": "📚 Guide",
        "lang": "🌐 Change Language",
        "back": "🔙 Back",
        "deposit": "➕ Add Balance",
        "coupon": "🎟 Coupon Code",
        "balance": "💰 Your wallet balance: {amount:,} Toman",
        "deposit_amount": "💳 Enter the amount you want to add in Toman:",
        "min_deposit": "❌ Minimum deposit is 1,000 Toman.",
        "invalid_amount": "❌ Please enter a valid amount.",
        "payment_info": "💳 Payment Information\n\nCard number:\n{card}\n\nCard holder:\n{holder}\n\nAmount: {amount:,} Toman\n\n📸 After payment, send the receipt image here.",
        "receipt_only": "📸 Please send the payment receipt image.",
        "receipt_saved": "✅ Your receipt has been submitted.\n\nTracking ID: #{rid}\nYour wallet will be credited after admin review. 🌹",
        "plans": "🛒 Choose one of the services below:",
        "custom": "✏️ Custom Volume",
        "custom_prompt": "✏️ Enter the desired volume in GB.\n\n💰 Price per GB: {price:,} Toman",
        "invalid_gb": "❌ Volume must be a whole number greater than zero.",
        "not_enough": "❌ Insufficient wallet balance.\n\nBalance: {balance:,} Toman\nPrice: {price:,} Toman\n\nPlease add balance first.",
        "order_success": "🎉 Your order was completed successfully!\n\n🧾 Order: #{oid}\n📦 Volume: {gb}\n💰 Amount: {price:,} Toman\n👤 Username: {username}\n\n🔗 Connection information:\n{config}",
        "panel_error": "⚠️ The order could not be provisioned through the panel. Your payment was refunded to your wallet.\n\nPlease contact support.",
        "ref": "👥 Your referrals: {count}\n🎁 Current reward: {percent}%\n\n🔗 Your referral link:\n{link}",
        "no_orders": "📦 You have no orders yet.",
        "support_text": "📞 Alpha Shop Support\n\nContact us using:\n{support}",
        "account": "👤 Account\n\n🆔 ID: {id}\n💰 Balance: {balance:,} Toman\n🌐 Language: English",
        "settings_text": "⚙️ Account Settings\n\nUse the buttons below to change your language.",
        "language_changed": "🇬🇧 Account language changed to English.",
        "coupon_prompt": "🎟 Send your coupon code:",
        "coupon_ok": "✅ Coupon is valid and can be used during a purchase.",
        "coupon_bad": "❌ Coupon is invalid, expired or already used.",
        "guide_text": "📚 Alpha Shop Guide\n\n"
                      "1️⃣ Join the required channel and tap Check Membership.\n"
                      "2️⃣ Open Wallet and add balance.\n"
                      "3️⃣ Transfer the amount to the displayed card and send the receipt.\n"
                      "4️⃣ After admin approval, the amount is added to your wallet.\n"
                      "5️⃣ Open Buy Service and choose your volume.\n"
                      "6️⃣ The purchase is paid from your wallet.\n"
                      "7️⃣ If the panel API is configured, the customer is created automatically and connection details are sent.\n\n"
                      "💡 Contact support if you need help.",
        "admin_only": "⛔ This section is for administrators only.",
        "trial": "🎁 Free Trial",
        "trial_used": "❌ You have already used your free trial.",
        "trial_success": "🎉 Your free trial has been activated.\n\n📦 Volume: 200 MB\n📅 Validity: 1 day\n\n🔗 Subscription:\n{config}",
        "trial_error": "❌ Failed to create free trial.",
    },
}


def lang(uid):
    u = db.get_user(uid)
    return u["lang"] if u and u["lang"] in TEXT else "fa"


def tr(uid, key, **kwargs):
    return TEXT[lang(uid)][key].format(**kwargs)


def menu(uid):
    return ReplyKeyboardMarkup(
        [
            [tr(uid, "buy")],
            [tr(uid, "trial"), tr(uid, "wallet")],
            [tr(uid, "refs"), tr(uid, "orders")],
            [tr(uid, "support"), tr(uid, "settings")],
            [tr(uid, "guide")],
        ],
        resize_keyboard=True,
    )


def force_keyboard(uid):
    l = lang(uid)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    TEXT[l]["join"],
                    url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}",
                )
            ],
            [InlineKeyboardButton(TEXT[l]["check"], callback_data="check")],
        ]
    )


async def is_member(bot, uid):
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, uid)
        if member.status in ("member", "administrator", "creator"):
            return True
        if member.status == "restricted" and getattr(member, "is_member", False):
            return True
        return False
    except Exception:
        return False


async def gate(update, context):
    uid = update.effective_user.id
    user = update.effective_user

    # اطمینان از وجود کاربر در دیتابیس
    u = db.get_user(uid)

    if u is None:
        db.upsert_user(user)
        u = db.get_user(uid)

    if u is None:
        await update.effective_message.reply_text(
            "⚠️ خطایی در ساخت حساب کاربری رخ داد. لطفاً دوباره /start را بزنید."
        )
        return False

    if u["blocked"]:
        await update.effective_message.reply_text(
            "⛔ حساب شما مسدود است."
        )
        return False

    if await is_member(context.bot, uid):
        return True

    await update.effective_message.reply_text(
        tr(uid, "need"),
        reply_markup=force_keyboard(uid),
    )

    return False
async def notify_referrer(update, context, referrer_id, new_user):
    """
    وقتی کاربر جدید با لینک دعوت وارد می‌شود:
    - یک کد تخفیف 5 درصدی برای معرف می‌سازد.
    - کد را در دیتابیس ذخیره می‌کند.
    - پیام کامل و صمیمانه برای معرف ارسال می‌کند.
    """
    try:
        # ساخت کد اختصاصی برای معرف
        code = f"REF5_{referrer_id}_{new_user.id}"

        # جلوگیری از ساخت دوباره همان کد
        existing = db.get_coupon(code)
        if existing:
            return

        # ساخت کد تخفیف 5 درصدی
        db.create_coupon(
            code,
            percent=5,
            max_uses=1,
        )

        name = new_user.first_name or "یک کاربر جدید"

        if lang(referrer_id) == "fa":
            message = (
                "🎉 <b>تبریک! یک زیرمجموعه جدید به شما اضافه شد</b> 🌹\n\n"
                f"👤 کاربر جدید: <b>{name}</b>\n"
                f"🆔 شناسه: <code>{new_user.id}</code>\n\n"
                "🎁 به پاس دعوت موفق شما، یک کد تخفیف <b>۵٪</b> برایتان فعال شد.\n\n"
                f"🎟 کد تخفیف شما:\n"
                f"<code>{code}</code>\n\n"
                "💡 این کد برای یک بار قابل استفاده است و می‌توانید "
                "هنگام خرید سرویس از آن استفاده کنید.\n\n"
                "🙏 ممنون که آلفا شاپ را به دوستانتان معرفی می‌کنید ❤️"
            )
        else:
            message = (
                "🎉 <b>Congratulations! You got a new referral</b> 🌹\n\n"
                f"👤 New user: <b>{name}</b>\n"
                f"🆔 User ID: <code>{new_user.id}</code>\n\n"
                "🎁 As a reward for your successful referral, "
                "you received a <b>5% discount coupon</b>.\n\n"
                f"🎟 Your coupon code:\n"
                f"<code>{code}</code>\n\n"
                "💡 This coupon can be used once when purchasing a service.\n\n"
                "🙏 Thank you for recommending Alpha Shop to your friends ❤️"
            )

        await context.bot.send_message(
            chat_id=referrer_id,
            text=message,
            parse_mode="HTML",
        )

    except Exception as e:
        print(f"Referral notification error: {e}")

async def start(update, context):
    user = update.effective_user

    # بررسی اینکه آیا کاربر قبلاً ثبت شده است
    existing_user = db.get_user(user.id)

    ref = None

    # فقط برای کاربر جدید، لینک دعوت بررسی شود
    if existing_user is None:
        if context.args and context.args[0].isdigit():
            candidate = int(context.args[0])

            if candidate != user.id and db.get_user(candidate):
                ref = candidate

    # ساخت یا بروزرسانی کاربر
    db.upsert_user(user, ref)

    # اگر کاربر جدید از طریق لینک دعوت وارد شده،
    # به معرف جایزه بده
    if existing_user is None and ref:
        await notify_referrer(
            update,
            context,
            ref,
            user,
        )

    if not await gate(update, context):
        return

    await update.message.reply_text(
        tr(
            user.id,
            "welcome",
            name=user.first_name or "دوست عزیز",
        ),
        reply_markup=menu(user.id),
    )

    await update.message.reply_text(
        tr(user.id, "welcome", name=user.first_name or "دوست عزیز"),
        reply_markup=menu(user.id),
    )


async def check_membership(update, context):
    query = update.callback_query
    await query.answer()

    if await is_member(context.bot, query.from_user.id):
        await query.message.edit_text(tr(query.from_user.id, "joined"))
        await query.message.reply_text(
            tr(query.from_user.id, "welcome", name=query.from_user.first_name or ""),
            reply_markup=menu(query.from_user.id),
        )
    else:
        await query.answer(
            tr(query.from_user.id, "need"),
            show_alert=True,
        )


async def settings(update, context):
    if not await gate(update, context):
        return
    uid = update.effective_user.id
    l = lang(uid)
    other = "English" if l == "fa" else "فارسی"
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"🌐 {other}", callback_data="toggle_lang")],
            [InlineKeyboardButton(tr(uid, "back"), callback_data="back_menu")],
        ]
    )
    await update.message.reply_text(tr(uid, "settings_text"), reply_markup=keyboard)


async def toggle_language(update, context):
    query = update.callback_query
    uid = query.from_user.id
    new_lang = "en" if lang(uid) == "fa" else "fa"
    db.set_lang(uid, new_lang)
    await query.answer()
    await query.message.edit_text(TEXT[new_lang]["language_changed"])
    await query.message.reply_text(
        TEXT[new_lang]["welcome"].format(name=query.from_user.first_name or ""),
        reply_markup=menu(uid),
    )


async def back_menu(update, context):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await query.message.chat.send_message(
        tr(query.from_user.id, "welcome", name=query.from_user.first_name or ""),
        reply_markup=menu(query.from_user.id),
    )


async def wallet(update, context):
    if not await gate(update, context):
        return
    uid = update.effective_user.id
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(tr(uid, "deposit"), callback_data="deposit")],
            [InlineKeyboardButton(tr(uid, "coupon"), callback_data="coupon")],
        ]
    )
    u = db.get_user(uid)
    await update.message.reply_text(
        tr(uid, "balance", amount=u["balance"]),
        reply_markup=keyboard,
    )


async def deposit_start(update, context):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(tr(query.from_user.id, "deposit_amount"))
    return DEP_AMOUNT


async def deposit_amount(update, context):
    uid = update.effective_user.id
    try:
        amount = int(update.message.text.replace(",", "").replace("٬", "").strip())
    except ValueError:
        await update.message.reply_text(tr(uid, "invalid_amount"))
        return DEP_AMOUNT

    if amount < 1000:
        await update.message.reply_text(tr(uid, "min_deposit"))
        return DEP_AMOUNT

    context.user_data["deposit_amount"] = amount
    await update.message.reply_text(
        tr(
            uid,
            "payment_info",
            card=CARD_NUMBER or "Not configured",
            holder=CARD_HOLDER or "Not configured",
            amount=amount,
        )
    )
    return DEP_RECEIPT


async def deposit_receipt(update, context):
    uid = update.effective_user.id
    if not update.message.photo:
        await update.message.reply_text(tr(uid, "receipt_only"))
        return DEP_RECEIPT

    amount = context.user_data.get("deposit_amount")
    if not amount:
        await update.message.reply_text(tr(uid, "invalid_amount"))
        return ConversationHandler.END

    receipt = update.message.photo[-1].file_id
    rid = db.add_deposit(uid, amount, receipt)
    context.user_data.clear()

    await update.message.reply_text(
        tr(uid, "receipt_saved", rid=rid),
        reply_markup=menu(uid),
    )

    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ تأیید / Approve", callback_data=f"dep:1:{rid}"),
            InlineKeyboardButton("❌ رد / Reject", callback_data=f"dep:0:{rid}"),
        ]]
    )

    caption = (
        f"💳 Deposit #{rid}\n"
        f"👤 {update.effective_user.full_name}\n"
        f"🆔 {uid}\n"
        f"💰 {amount:,} Toman"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                admin_id,
                receipt,
                caption=caption,
                reply_markup=buttons,
            )
        except Exception:
            pass

    return ConversationHandler.END


async def shop(update, context):
    if not await gate(update, context):
        return

    uid = update.effective_user.id
    l = lang(uid)
    rows = []

    for p in db.plans():
        title = p["title_fa"] if l == "fa" else p["title_en"]
        price = "نامحدود" if p["unlimited"] else f"{p['price']:,} تومان"
        rows.append([
            InlineKeyboardButton(
                f"{title} — {price}",
                callback_data=f"buy:{p['id']}",
            )
        ])

    rows.append([
        InlineKeyboardButton(tr(uid, "custom"), callback_data="custom")
    ])

    await update.message.reply_text(
        tr(uid, "plans"),
        reply_markup=InlineKeyboardMarkup(rows),
    )


def apply_discount(price, coupon):
    if not coupon:
        return price
    if coupon["percent"]:
        return max(0, int(price * (100 - coupon["percent"]) / 100))
    return max(0, price - coupon["amount"])


async def buy(update, context):
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

async def custom_start(update, context):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        tr(
            query.from_user.id,
            "custom_prompt",
            price=CUSTOM_PRICE_PER_GB,
        )
    )
    return CUSTOM_GB


async def custom_gb(update, context):
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

async def coupon_start(update, context):
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

async def _complete_pending_purchase(update, context):
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
        result.get("config")
        or data.get("config")
        or data.get("subscription")
        or data.get("subscription_url")
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
async def referrals(update, context):
    if not await gate(update, context):
        return
    uid = update.effective_user.id
    me = await context.bot.get_me()
    count = db.referrals(uid)
    link = f"https://t.me/{me.username}?start={uid}"
    await update.message.reply_text(
        tr(uid, "ref", count=count, percent=REFERRAL_PERCENT, link=link)
    )


async def orders(update, context):
    if not await gate(update, context):
        return
    uid = update.effective_user.id
    rows = db.user_orders(uid)
    if not rows:
        await update.message.reply_text(tr(uid, "no_orders"))
        return

    lines = []
    for row in rows:
        gb = "Unlimited" if row["gb"] is None else f"{row['gb']} GB"
        lines.append(
            f"🧾 #{row['id']} | {gb} | {row['price']:,} Toman | {row['status']}"
        )
    await update.message.reply_text("\n".join(lines))


async def support(update, context):
    if not await gate(update, context):
        return
    await update.message.reply_text(
        tr(update.effective_user.id, "support_text", support=SUPPORT_USERNAME)
    )


async def account(update, context):
    if not await gate(update, context):
        return
    uid = update.effective_user.id
    u = db.get_user(uid)
    await update.message.reply_text(
        tr(uid, "account", id=uid, balance=u["balance"])
    )


async def guide(update, context):
    if not await gate(update, context):
        return
    await update.message.reply_text(tr(update.effective_user.id, "guide_text"))


async def admin_panel(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(tr(update.effective_user.id, "admin_only"))
        return

    s = db.stats()
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💳 شارژهای در انتظار", callback_data="admin_deposits"),
                InlineKeyboardButton("📊 آمار", callback_data="admin_stats"),
            ],
            [
                InlineKeyboardButton("📦 مدیریت پلن‌ها", callback_data="admin_plans"),
                InlineKeyboardButton("🎟 کدهای تخفیف", callback_data="admin_coupons"),
            ],
            [
                InlineKeyboardButton("👥 کاربران", callback_data="admin_users"),
                InlineKeyboardButton("➕ افزایش موجودی", callback_data="admin_balance"),
            ],
        ]
    )

    await update.message.reply_text(
        f"🛠 پنل مدیریت آلفا شاپ\n\n"
        f"👤 کاربران: {s['users']}\n"
        f"📦 سفارش‌ها: {s['orders']}\n"
        f"💳 شارژهای در انتظار: {s['pending']}\n"
        f"💰 مجموع موجودی: {s['balance']:,} تومان\n"
        f"📈 فروش تکمیل‌شده: {s['sales']:,} تومان",
        reply_markup=keyboard,
    )


async def admin_callback(update, context):
    q = update.callback_query
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔ Access denied", show_alert=True)
        return

    await q.answer()

    if q.data == "admin_stats":
        s = db.stats()
        await q.message.reply_text(
            f"📊 آمار کامل\n\n"
            f"👤 کاربران: {s['users']}\n"
            f"📦 سفارش‌ها: {s['orders']}\n"
            f"💳 در انتظار: {s['pending']}\n"
            f"💰 موجودی کاربران: {s['balance']:,}\n"
            f"📈 فروش: {s['sales']:,}"
        )

    elif q.data == "admin_deposits":
        rows = db.pending_deposits()
        if not rows:
            await q.message.reply_text("✅ هیچ شارژ در انتظاری وجود ندارد.")
            return
        for d in rows:
            keyboard = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton(
                        "✅ تأیید",
                        callback_data=f"dep:1:{d['id']}"
                    ),
                    InlineKeyboardButton(
                        "❌ رد",
                        callback_data=f"dep:0:{d['id']}"
                    ),
                ]]
            )
            await q.message.reply_text(
                f"💳 شارژ #{d['id']}\n"
                f"👤 {d['first_name'] or ''} @{d['username'] or '-'}\n"
                f"🆔 {d['user_id']}\n"
                f"💰 {d['amount']:,} تومان",
                reply_markup=keyboard,
            )

    elif q.data == "admin_plans":
        rows = db.plans(include_inactive=True)
        text = ["📦 پلن‌ها:"]
        for p in rows:
            state = "فعال" if p["active"] else "غیرفعال"
            price = f"{p['price']:,}" if not p["unlimited"] else "نامحدود"
            text.append(f"#{p['id']} | {p['title_fa']} | {price} | {state}")
        text.append("\nبرای تغییر قیمت: /setprice ID PRICE")
        text.append("برای فعال/غیرفعال کردن: /toggleplan ID")
        await q.message.reply_text("\n".join(text))

    elif q.data == "admin_coupons":
        rows = db.coupons()
        if not rows:
            await q.message.reply_text(
                "🎟 کدی ثبت نشده.\nفرمت ساخت:\n/addcoupon CODE PERCENT MAXUSES"
            )
            return
        text = ["🎟 کدهای تخفیف:"]
        for c in rows:
            value = f"{c['percent']}%" if c["percent"] else f"{c['amount']:,} تومان"
            text.append(f"{c['code']} | {value} | {c['used']}/{c['max_uses'] or '∞'}")
        await q.message.reply_text("\n".join(text))

    elif q.data == "admin_users":
        rows = db.recent_users(20)
        if not rows:
            await q.message.reply_text("👥 کاربری ثبت نشده.")
            return
        text = ["👥 آخرین کاربران:"]
        for u in rows:
            text.append(
                f"{u['id']} | @{u['username'] or '-'} | {u['balance']:,} تومان"
            )
        await q.message.reply_text("\n".join(text))

    elif q.data == "admin_balance":
        await q.message.reply_text(
            "➕ افزایش موجودی دستی\n\nفرمت:\n/addbalance USER_ID AMOUNT"
        )


async def review_deposit_callback(update, context):
    q = update.callback_query
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔ Access denied", show_alert=True)
        return

    await q.answer()
    _, ok, did = q.data.split(":")
    deposit = db.review_deposit(int(did), ok == "1")
    if not deposit:
        await q.message.reply_text("⚠️ این درخواست قبلاً بررسی شده است.")
        return

    await q.edit_message_reply_markup(reply_markup=None)

    uid = deposit["user_id"]
    if ok == "1":
        await context.bot.send_message(
            uid,
            "🎉 شارژ شما تأیید شد و موجودی کیف پول‌تان افزایش یافت."
            if lang(uid) == "fa"
            else "🎉 Your deposit was approved and added to your wallet.",
        )
    else:
        await context.bot.send_message(
            uid,
            "❌ رسید شما توسط ادمین رد شد. در صورت نیاز با پشتیبانی تماس بگیرید."
            if lang(uid) == "fa"
            else "❌ Your receipt was rejected. Please contact support if needed.",
        )


async def add_balance_cmd(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) != 2:
        await update.message.reply_text("فرمت: /addbalance USER_ID AMOUNT")
        return
    try:
        uid, amount = int(context.args[0]), int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ مقادیر نامعتبر.")
        return
    if not db.get_user(uid):
        await update.message.reply_text("❌ کاربر پیدا نشد.")
        return
    db.add_balance(uid, amount, "Admin manual balance")
    await update.message.reply_text("✅ موجودی با موفقیت تغییر کرد.")


async def set_price_cmd(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) != 2:
        await update.message.reply_text("فرمت: /setprice PLAN_ID PRICE")
        return
    try:
        pid, price = int(context.args[0]), int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ مقدار نامعتبر.")
        return
    db.update_plan(pid, price=price)
    await update.message.reply_text("✅ قیمت پلن تغییر کرد.")


async def toggle_plan_cmd(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) != 1:
        await update.message.reply_text("فرمت: /toggleplan PLAN_ID")
        return
    try:
        pid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ شناسه نامعتبر.")
        return
    p = db.get_plan(pid)
    if not p:
        await update.message.reply_text("❌ پلن پیدا نشد.")
        return
    db.update_plan(pid, active=0 if p["active"] else 1)
    await update.message.reply_text("✅ وضعیت پلن تغییر کرد.")


async def add_coupon_cmd(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) != 3:
        await update.message.reply_text(
            "فرمت: /addcoupon CODE PERCENT MAXUSES\nمثال: /addcoupon ALPHA20 20 100"
        )
        return
    code = context.args[0].upper()
    try:
        percent, max_uses = int(context.args[1]), int(context.args[2])
    except ValueError:
        await update.message.reply_text("❌ مقدار نامعتبر.")
        return
    if percent < 1 or percent > 100:
        await update.message.reply_text("❌ درصد باید بین 1 تا 100 باشد.")
        return
    db.create_coupon(code, percent=percent, max_uses=max_uses)
    await update.message.reply_text("✅ کد تخفیف ساخته شد.")


async def free_trial(update, context):
    uid = update.effective_user.id

    if db.has_used_trial(uid):
        await update.message.reply_text(
            tr(uid, "trial_used"),
            reply_markup=menu(uid),
        )
        return

    username = f"trial_{uid}"

    result = await create_customer(
        username=username,
        gb=0.2,
        days=1,
    )

    if not result["ok"]:
        await update.message.reply_text(
            tr(uid, "trial_error"),
            reply_markup=menu(uid),
        )
        return

    data = result.get("data") or {}

    config = (
        result.get("config")
        or data.get("config")
        or data.get("subscription")
        or data.get("subscription_url")
        or data.get("link")
        or data.get("url")
        or ""
    )

    db.set_trial_used(uid)

    await update.message.reply_text(
        tr(uid, "trial_success", config=config),
        reply_markup=menu(uid),
    )

def run_bot():
    import asyncio

    print("🚀 run_bot() started")

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing in .env/config.py")

    # اطمینان از وجود Event Loop
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    print("✅ Event loop ready")

    db.init_db()

    print("✅ Database initialized")

    app = Application.builder().token(BOT_TOKEN).build()

    print("✅ Telegram Application created")

    deposit_conv = ConversationHandler(
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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("deposits", admin_panel))
    app.add_handler(CommandHandler("addbalance", add_balance_cmd))
    app.add_handler(CommandHandler("setprice", set_price_cmd))
    app.add_handler(CommandHandler("toggleplan", toggle_plan_cmd))
    app.add_handler(CommandHandler("addcoupon", add_coupon_cmd))

    # Conversations
    app.add_handler(deposit_conv)
    app.add_handler(custom_conv)
    app.add_handler(coupon_conv)
    app.add_handler(
        CallbackQueryHandler(confirm_buy, pattern=r"^confirm_buy:")
    )
    app.add_handler(
        CallbackQueryHandler(confirm_custom, pattern=r"^confirm_custom$")
    )
    app.add_handler(
        CallbackQueryHandler(cancel_buy, pattern=r"^cancel_buy$")
    )

    # Callback queries
    app.add_handler(
        CallbackQueryHandler(
            check_membership,
            pattern=r"^check$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            toggle_language,
            pattern=r"^toggle_lang$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            back_menu,
            pattern=r"^back_menu$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            buy,
            pattern=r"^buy:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            review_deposit_callback,
            pattern=r"^dep:",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_callback,
            pattern=r"^admin_",
        )
    )

    # Reply keyboard handlers
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(🛒 خرید سرویس|🛒 Buy Service)$"),
            shop,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(🎁 تست رایگان|🎁 Free Trial)$"),
            free_trial,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(💰 کیف پول|💰 Wallet)$"),
            wallet,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(👥 زیرمجموعه‌گیری|👥 Referrals)$"),
            referrals,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(📦 سفارش‌های من|📦 My Orders)$"),
            orders,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(📞 پشتیبانی|📞 Support)$"),
            support,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(⚙️ تنظیمات|⚙️ Settings)$"),
            settings,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(📚 راهنما|📚 Guide)$"),
            guide,
        )
    )

    print("🌹 AlphaShop Pro Bot Running...")


    app.run_polling(
        drop_pending_updates=True,
        close_loop=False,
        stop_signals=None,
    )


if __name__ == "__main__":
    run_bot()
