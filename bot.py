import json
import asyncio
import html
import io
import os
from pathlib import Path

import aiohttp

import qrcode
from PIL import Image

from telegram import ReactionTypeEmoji, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, CopyTextButton
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
import ai_router
from panel import create_customer, extend_customer, get_customer_info
import secrets


DEP_AMOUNT, DEP_RECEIPT, CUSTOM_GB, COUPON_INPUT = range(4)

TEXT = {
    "fa": {
        "welcome": "🌹 سلام {name} عزیز!\n\nبه آلفا شاپ خوش اومدی ❤️\nاز منوی زیر می‌تونی سرویس، کیف پول و حساب کاربری خودت رو مدیریت کنی.",
        "need": "🔒 برای استفاده از خدمات آلفا شاپ، ابتدا باید در کانال ما عضو بشی.",
        "joined": "✅ عضویتت با موفقیت تأیید شد. خوش اومدی 🌹",
        "join": "📢 عضویت در کانال",
        "check": "✅ بررسی عضویت",
        "buy": "🛒 خرید سرویس",
        "renew": "🔄 تمدید سرویس",
        "trial": "🎁 تست رایگان",
        "renew_choose": "🔄 سرویس موردنظر برای تمدید را انتخاب کنید:",
        "renew_none": "❌ سرویس فعالی برای تمدید پیدا نشد.",
        "renew_confirm": "🔄 <b>تمدید سرویس</b>\n\n🧾 سفارش: #{oid}\n🔌 سرویس: {service}\n📦 سرویس: {gb}\n💰 هزینه تمدید: {price:,} تومان\n📅 مدت تمدید: {days} روز\n\nبرای ادامه روی تأیید بزنید.",
        "renew_ok": "✅ سرویس شما با موفقیت {days} روز تمدید شد.",
        "renew_error": "❌ تمدید سرویس انجام نشد و مبلغی از کیف پول شما کسر نشد.",
        "wallet": "💰 کیف پول",
        "profile": "👤 پروفایل",
        "refs": "👥 زیرمجموعه‌گیری",
        "orders": "🟣 سفارش‌های فعال",
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
        "payment_info": "💳 <b>شارژ کیف پول | Alpha Shop</b>\n\n💰 <b>مبلغ قابل پرداخت:</b>\n<code>{amount:,} تومان</code>\n\n🏦 <b>شماره کارت:</b>\n<code>{card}</code>\n\n👤 <b>صاحب حساب:</b>\n<b>{holder}</b>\n\n📌 <b>مراحل پرداخت:</b>\n1️⃣ مبلغ بالا را دقیقاً به کارت اعلام‌شده واریز کنید.\n2️⃣ پس از پرداخت، تصویر واضح رسید را همین‌جا ارسال کنید.\n3️⃣ پس از بررسی و تأیید، مبلغ به کیف پول شما اضافه می‌شود.\n\n⚠️ لطفاً مبلغ و شماره کارت را قبل از انتقال بررسی کنید.",
        "receipt_only": "📸 لطفاً تصویر رسید پرداخت را ارسال کنید.",
        "receipt_saved": "✅ رسید شما با موفقیت ثبت شد.\n\nشماره پیگیری: #{rid}\nپس از بررسی ادمین، موجودی کیف پول شما افزایش پیدا می‌کند. 🌹",
        "plans": "🛒 یکی از سرویس‌های زیر را انتخاب کنید:",
        "choose_service": "🔌 سرویس موردنظر را انتخاب کنید:",
        "gold": "🥇 سرویس Gold",
        "silver": "🥈 سرویس Silver",
        "bronze": "🥉 سرویس Bronze",
        "trial_choose": "🎁 نوع تست رایگان را انتخاب کنید:",
        "custom": "✏️ حجم دلخواه",
        "custom_prompt": "✏️ حجم موردنظر را به GB وارد کنید.\n\n💰 قیمت هر گیگ: {price:,} تومان",
        "invalid_gb": "❌ حجم باید یک عدد صحیح بزرگ‌تر از صفر باشد.",
        "not_enough": "❌ موجودی کیف پول کافی نیست.\n\nموجودی: {balance:,} تومان\nقیمت: {price:,} تومان\n\nابتدا کیف پول خود را شارژ کنید.",
        "order_success": "🎉 <b>سفارش با موفقیت ثبت شد!</b>\n\n🧾 شماره سفارش: #{oid}\n📦 سرویس: {gb}\n💰 مبلغ: {price:,} تومان\n👤 نام کاربری: {username}\n\n🔗 اطلاعات اتصال:\n<code>{config}</code>",
        "panel_error": "⚠️ سفارش ثبت شد اما اتصال به پنل با موفقیت انجام نشد؛ مبلغ سفارش به کیف پول شما برگشت داده شد.\n\nلطفاً با پشتیبانی تماس بگیرید.",
        "ref": "👥 تعداد زیرمجموعه‌های شما: {count}\n🎁 درصد پاداش فعلی: {percent}%\n\n🔗 لینک دعوت شما:\n{link}",
        "no_orders": "📦 هنوز سفارشی ثبت نکرده‌اید.",
        "support_text": "🛟 <b>مرکز پشتیبانی آلفا شاپ</b>\n━━━━━━━━━━━━━━\n🌟 <b>چطور می‌توانیم کمکتان کنیم؟</b>\n\n📚 ابتدا سؤال متداول خود را انتخاب کنید.\n👨‍💻 برای مشکل اختصاصی با پشتیبانی در ارتباط باشید.\n🤖 برای پاسخ فوری با هوش مصنوعی گفتگو کنید.\n\n🟢 <b>پشتیبانی انسانی</b> برای مشکلات تخصصی\n🔵 <b>هوش مصنوعی</b> برای راهنمایی سریع\n━━━━━━━━━━━━━━\n💙 <i>اعتماد شما ، اعتبار ماست .</i>",
        "faq_1": "💳 شارژ کیف پول",
        "faq_2": "🛒 خرید سرویس",
        "faq_3": "🔗 اتصال اشتراک",
        "faq_4": "🛠️ مشکل اتصال",
        "faq_5": "📦 حجم و مصرف",
        "faq_6": "🔄 تمدید سرویس",
        "faq_7": "🎁 تست رایگان",
        "faq_8": "💬 زمان پاسخگویی",
        "faq_a1": "💳 <b>شارژ کیف پول</b>\n\n1️⃣ وارد بخش «کیف پول» شوید.\n2️⃣ گزینه «افزایش موجودی» را بزنید.\n3️⃣ مبلغ موردنظر را وارد کنید.\n4️⃣ مبلغ را به کارت اعلام‌شده واریز کنید.\n5️⃣ تصویر واضح رسید را ارسال کنید.\n\nپس از بررسی و تأیید، موجودی کیف پول شما افزایش پیدا می‌کند.",
        "faq_a2": "🛒 <b>خرید سرویس</b>\n\nاز «خرید سرویس» وارد بخش سرویس‌ها شوید، سرویس موردنظر را انتخاب کنید، حجم را مشخص کنید و با موجودی کیف پول پرداخت را تأیید کنید.\n\nبعد از ایجاد موفق سرویس، اطلاعات اتصال برای شما ارسال می‌شود.",
        "faq_a3": "🔗 <b>اتصال اشتراک</b>\n\nلینک اشتراک را می‌توانید در برنامه‌هایی مثل <b>V2Box، Hiddify، Happ و Streisand</b> وارد کنید.\n\nاگر روش اتصال برنامه خود را نمی‌دانید، از بخش «راهنما» آموزش مربوطه را ببینید.",
        "faq_a4": "🛠️ <b>مشکل اتصال</b>\n\nابتدا اینترنت را بررسی کنید، سپس برنامه را باز کنید و Subscription را Update کنید. اگر مشکل ادامه داشت، یک‌بار برنامه را ببندید و دوباره باز کنید.\n\nاگر همچنان مشکل وجود داشت، با پشتیبانی انسانی تماس بگیرید و در صورت امکان تصویر خطا را ارسال کنید.",
        "faq_a5": "📦 <b>حجم و مصرف</b>\n\nحجم سرویس بر اساس پلنی است که هنگام خرید انتخاب کرده‌اید. مصرف اینترنت از حجم سرویس کم می‌شود و میزان باقی‌مانده را می‌توانید از اطلاعات سرویس بررسی کنید.\n\nاگر درباره مصرف غیرعادی سؤال دارید، مشخصات سرویس و تصویر صفحه مصرف را برای پشتیبانی ارسال کنید.",
        "faq_a6": "🔄 <b>تمدید سرویس</b>\n\nاگر سرویس فعال داشته باشید، از بخش «تمدید سرویس» می‌توانید سرویس موردنظر را انتخاب و تمدید کنید. قبل از تأیید، مبلغ و مدت تمدید نمایش داده می‌شود.",
        "faq_a7": "🎁 <b>تست رایگان</b>\n\nدر صورت فعال بودن تست رایگان، می‌توانید از بخش «تست رایگان» سرویس آزمایشی دریافت کنید. محدودیت و شرایط تست توسط سیستم اعمال می‌شود و معمولاً هر کاربر فقط یک‌بار می‌تواند از آن استفاده کند.",
        "faq_a8": "💬 <b>پشتیبانی</b>\n\nبرای پاسخ سریع‌تر، ابتدا سؤال متداول مربوط به مشکل را بررسی کنید.\n\nاگر پاسخ کافی نبود، گزینه «ارتباط با پشتیبانی» را بزنید. همچنین می‌توانید از «هوش مصنوعی» برای راهنمایی فوری استفاده کنید.",
        "support_human": "👨‍💻 ارتباط با پشتیبانی",
        "support_ai": "🤖 هوش مصنوعی",
        "support_ai_intro": "🤖 <b>پشتیبانی هوش مصنوعی آلفا</b>\n\nسؤالت را همین‌جا بفرست. درباره خرید، کیف پول، اشتراک و مشکلات اتصال راهنمایی‌ات می‌کنم.\n\nبرای خروج از چت، یکی از گزینه‌های منوی اصلی را انتخاب کن.",
        "support_ai_no_key": "⚠️ بخش هوش مصنوعی هنوز روی سرور تنظیم نشده است. فعلاً با پشتیبانی انسانی در ارتباط باشید.",
        "support_ai_error": "⚠️ در ارتباط با هوش مصنوعی مشکلی پیش آمد. لطفاً دوباره تلاش کنید یا با پشتیبانی انسانی ارتباط بگیرید.",
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
        "broadcast_start": "📢 پیام همگانی\n\nپیامی که می‌خواهید برای همه کاربران ارسال شود را همین‌جا بفرستید.\nبرای لغو /cancelbroadcast را بزنید.",
        "broadcast_done": "✅ پیام همگانی ارسال شد.\n\nموفق: {ok}\nناموفق: {fail}",
        "trial": "🎁 تست رایگان",
        "renew_choose": "🔄 سرویس موردنظر برای تمدید را انتخاب کنید:",
        "renew_none": "❌ سرویس فعالی برای تمدید پیدا نشد.",
        "renew_confirm": "🔄 <b>تمدید سرویس</b>\n\n🧾 سفارش: #{oid}\n🔌 سرویس: {service}\n📦 سرویس: {gb}\n💰 هزینه تمدید: {price:,} تومان\n📅 مدت تمدید: {days} روز\n\nبرای ادامه روی تأیید بزنید.",
        "renew_ok": "✅ سرویس شما با موفقیت {days} روز تمدید شد.",
        "renew_error": "❌ تمدید سرویس انجام نشد و مبلغی از کیف پول شما کسر نشد.",
        "trial_used": "❌ شما قبلاً از تست رایگان استفاده کرده‌اید.",
        "trial_success": "🎉 تست رایگان {service} شما فعال شد.\n\n📦 سرویس: ۱۵۰ مگابایت\n📅 اعتبار: ۱ روز\n\n🔗 لینک اشتراک:\n<code>{config}</code>",
        "trial_error": "❌ ساخت تست رایگان با خطا مواجه شد.",
    },
    "en": {
        "welcome": "🌹 Hello {name}!\n\nWelcome to Alpha Shop ❤️\nUse the menu below to manage your services, wallet and account.",
        "need": "🔒 Please join our channel before using Alpha Shop.",
        "joined": "✅ Your membership has been verified. Welcome! 🌹",
        "join": "📢 Join Channel",
        "check": "✅ Check Membership",
        "buy": "🛒 Buy Service",
        "renew": "🔄 Renew Service",
        "trial": "🎁 Free Trial",
        "renew_choose": "🔄 Choose the service to renew:",
        "renew_none": "❌ No completed service is available for renewal.",
        "renew_confirm": "🔄 <b>Service Renewal</b>\n\n🧾 Order: #{oid}\n🔌 Service: {service}\n📦 Volume: {gb}\n💰 Renewal cost: {price:,} Toman\n📅 Renewal period: {days} days\n\nTap confirm to continue.",
        "renew_ok": "✅ Your service was renewed for {days} days.",
        "renew_error": "❌ Renewal failed. No amount was deducted from your wallet.",
        "wallet": "💰 Wallet",
        "profile": "👤 Profile",
        "refs": "👥 Referrals",
        "orders": "🟣 Active Services",
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
        "payment_info": "💳 <b>Wallet Deposit | Alpha Shop</b>\n\n💰 <b>Amount to pay:</b>\n<code>{amount:,} Toman</code>\n\n🏦 <b>Card number:</b>\n<code>{card}</code>\n\n👤 <b>Card holder:</b>\n<b>{holder}</b>\n\n📌 <b>Payment steps:</b>\n1️⃣ Transfer the exact amount shown above.\n2️⃣ After payment, send a clear screenshot/photo of the receipt here.\n3️⃣ Your wallet will be credited after admin review and approval.\n\n⚠️ Please verify the amount and card number before making the transfer.",
        "receipt_only": "📸 Please send the payment receipt image.",
        "receipt_saved": "✅ Your receipt has been submitted.\n\nTracking ID: #{rid}\nYour wallet will be credited after admin review. 🌹",
        "plans": "🛒 Choose one of the services below:",
        "choose_service": "🔌 Choose your service:",
        "gold": "🥇 Gold Service",
        "silver": "🥈 Silver Service",
        "bronze": "🥉 Bronze Service",
        "trial_choose": "🎁 Choose your free trial:",
        "custom": "✏️ Custom Volume",
        "custom_prompt": "✏️ Enter the desired volume in GB.\n\n💰 Price per GB: {price:,} Toman",
        "invalid_gb": "❌ Volume must be a whole number greater than zero.",
        "not_enough": "❌ Insufficient wallet balance.\n\nBalance: {balance:,} Toman\nPrice: {price:,} Toman\n\nPlease add balance first.",
        "order_success": "🎉 Your order was completed successfully!\n\n🧾 Order: #{oid}\n📦 Volume: {gb}\n💰 Amount: {price:,} Toman\n👤 Username: {username}\n\n🔗 Connection information:\n<code>{config}</code>",
        "panel_error": "⚠️ The order could not be provisioned through the panel. Your payment was refunded to your wallet.\n\nPlease contact support.",
        "ref": "👥 Your referrals: {count}\n🎁 Current reward: {percent}%\n\n🔗 Your referral link:\n{link}",
        "no_orders": "📦 You have no orders yet.",
        "support_text": "🛟 <b>Alpha Shop Support Center</b>\n━━━━━━━━━━━━━━\n🌟 <b>How can we help you?</b>\n\n📚 Choose a frequently asked question first.\n👨‍💻 Contact human support for specific issues.\n🤖 Chat with AI for quick guidance.\n\n🟢 <b>Human Support</b> for specialized help\n🔵 <b>AI Support</b> for instant guidance\n━━━━━━━━━━━━━━\n💙 <i>Your trust, our reputation.</i>",
        "faq_1": "💳 Wallet Balance",
        "faq_2": "🛒 Buy a Service",
        "faq_3": "🔗 Add Subscription",
        "faq_4": "🛠️ Connection Issue",
        "faq_5": "📦 Traffic Usage",
        "faq_6": "🔄 Renew Service",
        "faq_7": "🎁 Free Trial",
        "faq_8": "💬 Support Response",
        "faq_a1": "💳 <b>Wallet Balance</b>\n\n1️⃣ Open Wallet.\n2️⃣ Tap Add Balance.\n3️⃣ Enter the amount.\n4️⃣ Transfer the amount to the displayed card.\n5️⃣ Send a clear payment receipt.\n\nYour balance will be added after admin review and approval.",
        "faq_a2": "🛒 <b>Buying a Service</b>\n\nOpen Buy Service, choose the service, select your desired volume and confirm the payment from your wallet.\n\nAfter successful provisioning, your connection information will be sent to you.",
        "faq_a3": "🔗 <b>Adding a Subscription</b>\n\nYou can add the subscription link in apps such as <b>V2Box, Hiddify, Happ and Streisand</b>.\n\nIf you need help with a specific app, check the Guide section.",
        "faq_a4": "🛠️ <b>Connection Issue</b>\n\nFirst check your internet connection, then open your VPN app and update the subscription. If the issue continues, restart the app.\n\nIf it still does not work, contact Human Support and send a screenshot of the error if possible.",
        "faq_a5": "📦 <b>Traffic Usage</b>\n\nYour traffic limit depends on the plan you purchased. Internet usage is deducted from your service traffic.\n\nIf you notice unusual usage, send your service details and a screenshot to support.",
        "faq_a6": "🔄 <b>Renewing a Service</b>\n\nIf you have an active service, open Renew Service and select the service you want to renew. The renewal price and duration are shown before confirmation.",
        "faq_a7": "🎁 <b>Free Trial</b>\n\nIf a free trial is available, open Free Trial to request it. Trial availability and limits are controlled by the system and are normally limited to one use per user.",
        "faq_a8": "💬 <b>Support</b>\n\nFor a faster solution, check the relevant FAQ first.\n\nIf it does not solve your problem, use Contact Support. You can also use Alpha AI for instant guidance.",
        "support_human": "👨‍💻 Contact Support",
        "support_ai": "🤖 AI Support",
        "support_ai_intro": "🤖 <b>Alpha AI Support</b>\n\nSend your question here. I can help with purchases, wallet, subscriptions and basic connection issues.\n\nTo leave AI chat, choose any main-menu button.",
        "support_ai_no_key": "⚠️ AI support is not configured on the server yet. Please contact human support for now.",
        "support_ai_error": "⚠️ Something went wrong while contacting AI. Please try again or contact human support.",
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
        "broadcast_start": "📢 Broadcast\n\nSend the message you want to deliver to all users here.\nUse /cancelbroadcast to cancel.",
        "broadcast_done": "✅ Broadcast completed.\n\nSuccessful: {ok}\nFailed: {fail}",
        "trial": "🎁 Free Trial",
        "trial_used": "❌ You have already used your free trial.",
        "trial_success": "🎉 Your {service} free trial has been activated.\n\n📦 Volume: 150 MB\n📅 Validity: 1 day\n\n🔗 Subscription:\n<code>{config}</code>",
        "trial_error": "❌ Failed to create free trial.",
    },
}



QR_TEMPLATE = Path(__file__).resolve().parent / "assets" / "connection_qr_template.jpeg"


def build_connection_image(connection):
    """Create the customer card using the supplied template and place only the QR in the white panel."""
    if not connection:
        return None
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(str(connection))
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    base = Image.open(QR_TEMPLATE).convert("RGB")
    # The white panel in the 1536x1536 Alpha Shop template is centered around this area.
    target = 610
    qr_img = qr_img.resize((target, target), Image.Resampling.LANCZOS)
    x = (base.width - qr_img.width) // 2
    y = 330
    base.paste(qr_img, (x, y))
    out = io.BytesIO()
    out.name = "alpha_shop_connection.jpg"
    base.save(out, format="JPEG", quality=95, subsampling=0)
    out.seek(0)
    return out


def connection_caption(uid, title, connection, extra_lines=None):
    lines = [str(title)]

    if extra_lines:
        lines.extend(html.escape(str(x)) for x in extra_lines)

    lines.extend([
        "",
        ui(uid, "🔗 اطلاعات اتصال:", "🔗 Connection information:"),
        f"<code>{html.escape(str(connection))}</code>",
    ])

    return "\n".join(lines)


async def send_connection_card(message, uid, title, connection, extra_lines=None, reply_markup=None):
    if not connection:
        await message.reply_text(
            title + "\n\n" + ui(
                uid,
                "❌ اطلاعات اتصال از پنل دریافت نشد.",
                "❌ Connection information could not be retrieved from the panel."
            ),
            reply_markup=reply_markup
        )
        return

    connection = str(connection).strip()

    image = build_connection_image(connection)
    caption = connection_caption(uid, title, connection, extra_lines)

    if len(caption) > 1024:
        caption = (
            html.escape(str(title))
            + "\n\n"
            + ui(
                uid,
                "🔗 اطلاعات اتصال:",
                "🔗 Connection information:"
            )
            + "\n\n"
            + html.escape(connection)
        )

    copy_button = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                ui(uid, "📋 کپی لینک", "📋 Copy Link"),
                copy_text=CopyTextButton(text=connection)
            )
        ]
    ])

    await message.reply_photo(
        photo=image,
        caption=caption,
        parse_mode="HTML",
        reply_markup=copy_button,
    )

def lang(uid):
    u = db.get_user(uid)
    return u["lang"] if u and u["lang"] in TEXT else "fa"


def tr(uid, key, **kwargs):
    return TEXT[lang(uid)][key].format(**kwargs)


def ui(uid, fa_text, en_text):
    return fa_text if lang(uid) == "fa" else en_text


def menu(uid):
    # Telegram supports colored reply-keyboard buttons on recent clients.
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(tr(uid, "buy"), style="danger")],
            [KeyboardButton(tr(uid, "renew"), style="danger"), KeyboardButton(tr(uid, "trial"), style="success")],
            [KeyboardButton(tr(uid, "wallet"), style="primary")],
            [KeyboardButton(tr(uid, "refs"), style="primary"), KeyboardButton(tr(uid, "orders"), style="success")],
            [KeyboardButton(tr(uid, "support"), style="primary"), KeyboardButton(tr(uid, "settings"), style="primary")],
            [KeyboardButton(tr(uid, "profile"), style="primary"), KeyboardButton(tr(uid, "guide"), style="primary")],
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
                    style="primary",
                )
            ],
            [InlineKeyboardButton(TEXT[l]["check"], callback_data="check", style="success")],
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
    New referral:
    - New user receives a one-time 5% coupon.
    - Referrer receives Alpha Coin only after successful purchases.
    """
    try:
        code = f"REF5_{new_user.id}"

        if not db.get_coupon(code):
            db.create_coupon(
                code,
                percent=5,
                max_uses=1,
            )

        name = new_user.first_name or "دوست جدید"

        try:
            if lang(new_user.id) == "fa":
                new_user_message = (
                    "🎉 <b>خوش آمدید به آلفا شاپ!</b> 🌹\n\n"
                    "🎁 به دلیل ورود از لینک دعوت، "
                    "<b>۵٪ تخفیف</b> برای شما فعال شد.\n\n"
                    f"🎟 کد تخفیف:\n<code>{code}</code>\n\n"
                    "💡 این کد یک‌بار قابل استفاده است."
                )
            else:
                new_user_message = (
                    "🎉 <b>Welcome to Alpha Shop!</b> 🌹\n\n"
                    "🎁 You received a "
                    "<b>5% discount</b> because you joined "
                    "through a referral link.\n\n"
                    f"🎟 Coupon:\n<code>{code}</code>\n\n"
                    "💡 This coupon can be used once."
                )

            await context.bot.send_message(
                chat_id=new_user.id,
                text=new_user_message,
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"Referral new-user message error: {e}")

        if lang(referrer_id) == "fa":
            message = (
                "🎉 <b>یک زیرمجموعه جدید به شما اضافه شد!</b> 🌹\n\n"
                f"👤 کاربر: <b>{name}</b>\n"
                f"🆔 شناسه: <code>{new_user.id}</code>\n\n"
                "🪙 از خریدهای موفق این کاربر، "
                "<b>۲.۵٪ مبلغ پرداختی</b> به صورت Alpha Coin "
                "برای شما ثبت می‌شود."
            )
        else:
            message = (
                "🎉 <b>You got a new referral!</b> 🌹\n\n"
                f"👤 User: <b>{name}</b>\n"
                f"🆔 ID: <code>{new_user.id}</code>\n\n"
                "🪙 You receive <b>2.5%</b> of their "
                "successful purchases as Alpha Coin."
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

        try:
            await check_and_reward_missions(ref, context)
        except Exception as mission_error:
            print(
                f"⚠️ Mission reward check failed after referral: "
                f"{type(mission_error).__name__}: {mission_error}"
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
            [InlineKeyboardButton(f"🌐 {other}", callback_data="toggle_lang", style="primary")],
            [InlineKeyboardButton(tr(uid, "back"), callback_data="back_menu", style="danger")],
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
    uid = update.effective_user.id

    if not await gate(update, context):
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                tr(uid, "deposit"),
                callback_data="deposit",
                style="success",
            )
        ],
        [
            InlineKeyboardButton(
                "🪙 Alpha Coin",
                callback_data="alpha_coin",
                style="primary",
            ),
            InlineKeyboardButton(
                tr(uid, "coupon"),
                callback_data="coupon",
                style="primary",
            ),
        ],
    ])

    u = db.get_user(uid)
    coins = db.get_alpha_coins(uid)

    if lang(uid) == "fa":
        text = (
            "💰 <b>کیف پول شما</b>\n\n"
            f"💵 موجودی تومان: <b>{u['balance']:,} تومان</b>\n"
            f"🪙 سکه آلفا: <b>{coins:,} سکه</b>"
        )
    else:
        text = (
            "💰 <b>Your Wallet</b>\n\n"
            f"💵 Toman Balance: <b>{u['balance']:,}</b>\n"
            f"🪙 Alpha Coin: <b>{coins:,} ALC</b>"
        )

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )






async def check_and_reward_missions(uid, context):
    """
    Check all mission stages and automatically reward completed
    unlocked stages exactly once.
    """
    uid = int(uid)

    try:
        stages = db.mission_stages()

        for stage in stages:
            stage_id = int(stage["id"])

            # Already rewarded.
            if db.mission_claimed(uid, stage_id):
                continue

            # Previous stage must be claimed first.
            if not db.mission_stage_unlocked(uid, stage_id):
                continue

            missions = db.stage_missions(stage_id)

            # A stage with no missions is not automatically completed.
            if not missions:
                continue

            all_completed = True

            for mission in missions:
                progress = db.mission_progress(
                    uid,
                    mission["mission_type"],
                )
                target = int(mission["target"])

                if progress < target:
                    all_completed = False
                    break

            if not all_completed:
                continue

            reward = int(stage["reward_alc"])

            title = (
                stage["title_fa"]
                if lang(uid) == "fa"
                else stage["title_en"]
            )

            if lang(uid) == "fa":
                description = f"پاداش تکمیل مرحله {title}"
            else:
                description = f"Mission stage completion reward: {title}"

            success = db.claim_mission_stage_reward(
                uid,
                stage_id,
                reward,
                description,
            )

            if not success:
                continue

            new_balance = db.get_alpha_coins(uid)

            if lang(uid) == "fa":
                text = (
                    f"🎉 <b>مرحله {title} تکمیل شد!</b>\n\n"
                    f"🏆 تمام مأموریت‌های این مرحله انجام شدند.\n"
                    f"🪙 <b>{reward:,} ALC</b> به شما تعلق گرفت.\n\n"
                    f"💰 موجودی Alpha Coin: "
                    f"<b>{new_balance:,} ALC</b>"
                )
            else:
                text = (
                    f"🎉 <b>{title} completed!</b>\n\n"
                    f"🏆 All missions in this stage are complete.\n"
                    f"🪙 <b>{reward:,} ALC</b> has been added.\n\n"
                    f"💰 Alpha Coin balance: "
                    f"<b>{new_balance:,} ALC</b>"
                )

            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=text,
                    parse_mode="HTML",
                )
            except Exception as e:
                print(
                    f"⚠️ Mission reward notification failed "
                    f"for {uid}: {type(e).__name__}: {e}"
                )

    except Exception as e:
        print(
            f"⚠️ Mission check failed for {uid}: "
            f"{type(e).__name__}: {e}"
        )

async def mission_claim_callback(update, context):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    try:
        stage_id = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        return

    stages = db.mission_stages()
    stage = next(
        (x for x in stages if int(x["id"]) == stage_id),
        None,
    )

    if not stage:
        await query.answer(
            "❌ مرحله پیدا نشد.",
            show_alert=True,
        )
        return

    # The stage must be unlocked before claiming.
    if not db.mission_stage_unlocked(uid, stage_id):
        await query.answer(
            "🔒 این مرحله هنوز قفل است.",
            show_alert=True,
        )
        return

    missions = db.stage_missions(stage_id)

    # Every mission must be completed.
    if not missions:
        await query.answer(
            "⏳ این مرحله هنوز آماده دریافت نیست.",
            show_alert=True,
        )
        return

    for mission in missions:
        progress = db.mission_progress(
            uid,
            mission["mission_type"],
        )
        target = int(mission["target"])

        if progress < target:
            await query.answer(
                "⏳ هنوز همه مأموریت‌ها کامل نشده‌اند.",
                show_alert=True,
            )
            return

    reward = int(stage["reward_alc"])

    title = (
        stage["title_fa"]
        if lang(uid) == "fa"
        else stage["title_en"]
    )

    if lang(uid) == "fa":
        description = f"پاداش تکمیل مرحله {title}"
    else:
        description = f"Mission stage completion reward: {title}"

    success = db.claim_mission_stage_reward(
        uid,
        stage_id,
        reward,
        description,
    )

    if not success:
        await query.answer(
            "✅ این پاداش قبلاً دریافت شده است.",
            show_alert=True,
        )
        return

    # Find the next stage.
    next_stage_id = stage_id + 1
    next_stage = next(
        (
            x for x in stages
            if int(x["id"]) == next_stage_id
        ),
        None,
    )

    new_balance = db.get_alpha_coins(uid)

    if lang(uid) == "fa":
        if next_stage:
            next_title = next_stage["title_fa"]

            text = (
                f"🎉 <b>مرحله {title} با موفقیت تکمیل شد!</b>\n\n"
                f"🪙 <b>{reward:,} ALC</b> به موجودی شما اضافه شد.\n\n"
                f"💰 موجودی جدید: <b>{new_balance:,} ALC</b>\n\n"
                f"🔓 <b>مرحله بعدی باز شد!</b>\n"
                f"🎯 {next_title}\n\n"
                "🚀 حالا می‌توانید مأموریت‌های مرحله بعد را شروع کنید."
            )

            next_button = InlineKeyboardButton(
                f"🎯 مشاهده {next_title}",
                callback_data=f"mission_stage:{next_stage_id}",
                style="primary",
            )
        else:
            text = (
                f"🎉 <b>مرحله {title} با موفقیت تکمیل شد!</b>\n\n"
                f"🪙 <b>{reward:,} ALC</b> به موجودی شما اضافه شد.\n\n"
                f"💰 موجودی جدید: <b>{new_balance:,} ALC</b>\n\n"
                "🏆 <b>تبریک! تمام مراحل موجود را تکمیل کردید.</b>"
            )
            next_button = None

        back_text = "🎯 بازگشت به مأموریت‌ها"

    else:
        if next_stage:
            next_title = next_stage["title_en"]

            text = (
                f"🎉 <b>{title} completed successfully!</b>\n\n"
                f"🪙 <b>{reward:,} ALC</b> has been added to your balance.\n\n"
                f"💰 New balance: <b>{new_balance:,} ALC</b>\n\n"
                f"🔓 <b>Next stage unlocked!</b>\n"
                f"🎯 {next_title}\n\n"
                "🚀 You can now start the missions of the next stage."
            )

            next_button = InlineKeyboardButton(
                f"🎯 View {next_title}",
                callback_data=f"mission_stage:{next_stage_id}",
                style="primary",
            )
        else:
            text = (
                f"🎉 <b>{title} completed successfully!</b>\n\n"
                f"🪙 <b>{reward:,} ALC</b> has been added to your balance.\n\n"
                f"💰 New balance: <b>{new_balance:,} ALC</b>\n\n"
                "🏆 <b>Congratulations! You completed all available stages.</b>"
            )
            next_button = None

        back_text = "🎯 Back to Missions"

    buttons = []

    if next_button:
        buttons.append([next_button])

    buttons.append([
        InlineKeyboardButton(
            back_text,
            callback_data="missions",
            style="success",
        )
    ])

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

async def mission_stage_callback(update, context):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    try:
        stage_id = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        return

    stages = db.mission_stages()
    stage = next(
        (x for x in stages if int(x["id"]) == stage_id),
        None,
    )

    if not stage:
        await query.answer(
            "❌ مرحله پیدا نشد.",
            show_alert=True,
        )
        return

    # Check stage lock.
    if not db.mission_stage_unlocked(uid, stage_id):
        previous_stage_id = stage_id - 1
        previous_stage = next(
            (
                x for x in stages
                if int(x["id"]) == previous_stage_id
            ),
            None,
        )

        if lang(uid) == "fa":
            previous_title = (
                previous_stage["title_fa"]
                if previous_stage
                else "مرحله قبلی"
            )

            await query.answer()

            await query.message.reply_text(
                "🔒 <b>این مرحله هنوز قفل است</b>\n\n"
                f"برای باز شدن این مرحله، ابتدا باید "
                f"تمام مأموریت‌های <b>{previous_title}</b> را "
                "تکمیل کنید.\n\n"
                "🎯 بعد از تکمیل مرحله قبلی، این مرحله "
                "به‌صورت خودکار برای شما باز می‌شود. 🔓",
                parse_mode="HTML",
            )
        else:
            previous_title = (
                previous_stage["title_en"]
                if previous_stage
                else "Previous Stage"
            )

            await query.answer()

            await query.message.reply_text(
                "🔒 <b>This stage is locked</b>\n\n"
                f"First complete all missions in "
                f"<b>{previous_title}</b> to unlock this stage.\n\n"
                "🎯 Once the previous stage is completed, "
                "this stage will automatically unlock. 🔓",
                parse_mode="HTML",
            )

        return

    missions = db.stage_missions(stage_id)
    claimed = db.mission_claimed(uid, stage_id)

    all_completed = bool(missions)
    lines = []

    for mission in missions:
        progress = db.mission_progress(
            uid,
            mission["mission_type"],
        )

        target = int(mission["target"])
        shown_progress = min(progress, target)

        if progress >= target:
            icon = "✅"
        elif progress > 0:
            icon = "🔄"
        else:
            icon = "⬜"

        title = (
            mission["title_fa"]
            if lang(uid) == "fa"
            else mission["title_en"]
        )

        lines.append(
            f"{icon} {title}\n"
            f"   📊 {shown_progress}/{target}"
        )

        if progress < target:
            all_completed = False

    reward = int(stage["reward_alc"])

    if lang(uid) == "fa":
        title = stage["title_fa"]

        if claimed:
            status = "✅ پاداش این مرحله قبلاً دریافت شده است."
        elif all_completed:
            status = "🎁 تمام مأموریت‌ها تکمیل شده‌اند!"
        else:
            status = "🔄 مأموریت‌ها را تکمیل کنید."

        text = (
            f"🎯 <b>{title}</b>\n\n"
            "📋 <b>مأموریت‌ها:</b>\n\n"
            + "\n\n".join(lines)
            + f"\n\n🏆 پاداش مرحله: <b>{reward:,} ALC</b>"
            + f"\n\n{status}"
        )

        buttons = []

        if claimed:
            buttons.append([
                InlineKeyboardButton(
                    "✅ پاداش دریافت شده",
                    callback_data="missions",
                    style="success",
                )
            ])
        elif all_completed:
            buttons.append([
                InlineKeyboardButton(
                    f"🎁 دریافت {reward:,} ALC",
                    callback_data=f"mission_claim:{stage_id}",
                    style="success",
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                "🔙 بازگشت به مأموریت‌ها",
                callback_data="missions",
                style="primary",
            )
        ])

    else:
        title = stage["title_en"]

        if claimed:
            status = "✅ This stage reward has already been claimed."
        elif all_completed:
            status = "🎁 All missions completed!"
        else:
            status = "🔄 Complete the missions to unlock the reward."

        text = (
            f"🎯 <b>{title}</b>\n\n"
            "📋 <b>Missions:</b>\n\n"
            + "\n\n".join(lines)
            + f"\n\n🏆 Stage reward: <b>{reward:,} ALC</b>"
            + f"\n\n{status}"
        )

        buttons = []

        if claimed:
            buttons.append([
                InlineKeyboardButton(
                    "✅ Reward claimed",
                    callback_data="missions",
                    style="success",
                )
            ])
        elif all_completed:
            buttons.append([
                InlineKeyboardButton(
                    f"🎁 Claim {reward:,} ALC",
                    callback_data=f"mission_claim:{stage_id}",
                    style="success",
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                "🔙 Back to Missions",
                callback_data="missions",
                style="primary",
            )
        ])

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

async def missions_callback(update, context):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    stages = db.mission_stages()

    keyboard = []

    for index, stage in enumerate(stages):
        stage_id = int(stage["id"])
        missions = db.stage_missions(stage_id)

        unlocked = db.mission_stage_unlocked(uid, stage_id)
        claimed = db.mission_claimed(uid, stage_id)

        completed = bool(missions)
        has_progress = False

        if not missions:
            completed = False

        for mission in missions:
            progress = db.mission_progress(
                uid,
                mission["mission_type"],
            )
            target = int(mission["target"])

            if progress > 0:
                has_progress = True

            if progress < target:
                completed = False

        title = (
            stage["title_fa"]
            if lang(uid) == "fa"
            else stage["title_en"]
        )

        if not unlocked:
            icon = "🔒"
            style = "primary"
        elif claimed:
            icon = "✅"
            style = "success"
        elif completed:
            icon = "🎁"
            style = "success"
        elif has_progress:
            icon = "🔄"
            style = "primary"
        else:
            icon = "⬜"
            style = "primary"

        keyboard.append([
            InlineKeyboardButton(
                f"{icon} {title}",
                callback_data=f"mission_stage:{stage_id}",
                style=style,
            )
        ])

    if lang(uid) == "fa":
        text = (
            "🎯 <b>مأموریت‌ها</b>\n\n"
            "با انجام مأموریت‌ها Alpha Coin دریافت کنید.\n\n"
            "وضعیت‌ها:\n"
            "⬜ شروع نشده\n"
            "🔄 در حال انجام\n"
            "🎁 آماده دریافت\n"
            "✅ دریافت شده\n"
            "🔒 قفل"
        )
        back_text = "🔙 بازگشت"
    else:
        text = (
            "🎯 <b>Missions</b>\n\n"
            "Complete missions and earn Alpha Coins.\n\n"
            "Statuses:\n"
            "⬜ Not started\n"
            "🔄 In progress\n"
            "🎁 Ready to claim\n"
            "✅ Claimed\n"
            "🔒 Locked"
        )
        back_text = "🔙 Back"

    keyboard.append([
        InlineKeyboardButton(
            back_text,
            callback_data="alpha_coin",
            style="primary",
        )
    ])

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def alpha_coin_history_callback(update, context):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    coins = db.get_alpha_coins(uid)
    rows = db.alpha_coin_history(uid, 20)

    if lang(uid) == "fa":
        text = (
            "📜 <b>تاریخچه Alpha Coin</b>\n\n"
            f"💰 موجودی فعلی: <b>{coins:,} ALC</b>\n"
        )

        if not rows:
            text += "\nهنوز تراکنشی ثبت نشده است."
        else:
            for row in rows:
                amount = int(row["amount"])
                sign = "+" if amount > 0 else ""
                text += (
                    f"\n{sign}{amount:,} ALC — "
                    f"{row['description'] or row['kind']}"
                )

        back_text = "🔙 بازگشت"
    else:
        text = (
            "📜 <b>Alpha Coin History</b>\n\n"
            f"💰 Current balance: <b>{coins:,} ALC</b>\n"
        )

        if not rows:
            text += "\nNo transactions yet."
        else:
            for row in rows:
                amount = int(row["amount"])
                sign = "+" if amount > 0 else ""
                text += (
                    f"\n{sign}{amount:,} ALC — "
                    f"{row['description'] or row['kind']}"
                )

        back_text = "🔙 Back"

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    back_text,
                    callback_data="alpha_coin",
                    style="primary",
                )
            ]
        ]),
    )

async def alpha_coin_callback(update, context):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    coins = db.get_alpha_coins(uid)

    if lang(uid) == "fa":
        text = (
            "🪙 <b>Alpha Coin</b>\n\n"
            f"💰 موجودی: <b>{coins:,} ALC</b>\n"
            f"💎 ارزش: <b>{coins * 100:,} تومان</b>\n\n"
            "یکی از گزینه‌های زیر را انتخاب کنید:"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🎯 مأموریت‌ها",
                    callback_data="missions",
                    style="success",
                )
            ],
            [
                InlineKeyboardButton(
                    "📜 تاریخچه سکه‌ها",
                    callback_data="alpha_coin_history",
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="back_menu",
                    style="primary",
                )
            ],
        ])
    else:
        text = (
            "🪙 <b>Alpha Coin</b>\n\n"
            f"💰 Balance: <b>{coins:,} ALC</b>\n"
            f"💎 Value: <b>{coins * 100:,} Toman</b>\n\n"
            "Choose an option:"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🎯 Missions",
                    callback_data="missions",
                    style="success",
                )
            ],
            [
                InlineKeyboardButton(
                    "📜 Coin History",
                    callback_data="alpha_coin_history",
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="back_menu",
                    style="primary",
                )
            ],
        ])

    await query.message.reply_text(
        text,
        parse_mode="HTML",
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
        ),
        parse_mode="HTML",
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

    try:
        await context.bot.set_message_reaction(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
            reaction=[ReactionTypeEmoji(emoji="❤")],
        )
    except Exception as e:
        print(f"❌ Receipt reaction failed: {e}")

    context.user_data.clear()

    await update.message.reply_text(
        tr(uid, "receipt_saved", rid=rid),
        reply_markup=menu(uid),
    )

    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ تأیید / Approve", callback_data=f"dep:1:{rid}", style="success"),
            InlineKeyboardButton("❌ رد / Reject", callback_data=f"dep:0:{rid}", style="danger"),
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
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(TEXT[l]["gold"], callback_data="shop_service:gold", style="success")],
        [InlineKeyboardButton(TEXT[l]["silver"], callback_data="shop_service:silver", style="primary")],
        [InlineKeyboardButton(TEXT[l]["bronze"], callback_data="shop_service:bronze", style="danger")],
    ])
    await update.message.reply_text(tr(uid, "choose_service"), reply_markup=keyboard)


async def shop_service(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    service = q.data.split(":", 1)[1]
    rows = []
    for p in db.plans(service=service):
        title = (f"{int(p['gb'])} GB" if p["gb"] is not None else "نامحدود") if lang(uid) == "fa" else (f"{int(p['gb'])} GB" if p["gb"] is not None else "Unlimited")
        price = "" if p["unlimited"] else (f"{p['price']:,} Toman" if lang(uid) == "en" else f"{p['price']:,} تومان")
        rows.append([InlineKeyboardButton(
            f"{title} — {price}",
            callback_data=f"buy:{service}:{p['id']}",
            style={"gold":"success", "silver":"primary", "bronze":"danger"}.get(service, "primary"),
        )])
    rows.append([InlineKeyboardButton(tr(uid, "custom"), callback_data=f"custom:{service}", style="primary")])
    await q.message.reply_text(
        f"{TEXT[lang(uid)][service]}\n\n{tr(uid, 'plans')}",
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

    parts = query.data.split(":")
    try:
        if len(parts) == 3:
            service, pid = parts[1], int(parts[2])
        else:
            service, pid = "gold", int(parts[1])
    except (ValueError, IndexError):
        await query.message.reply_text(ui(uid, "❌ سرویس نامعتبر است.", "❌ Invalid service."))
        return

    p = db.get_plan(pid)
    if not p or not p["active"] or p["service"] != service:
        await query.message.reply_text(ui(uid, "❌ این سرویس در دسترس نیست.", "❌ This service is unavailable."))
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

    # Show the Alpha Coin that can be used before confirmation.
    # 1 ALC = 100 Toman, maximum 30% of the discounted price.
    available_coins = int(db.get_alpha_coins(uid) or 0)
    max_coin_by_order = (final_price * 30 // 100) // 100
    usable_coins = min(available_coins, max_coin_by_order)
    usable_coin_value = usable_coins * 100
    payable_after_coin = final_price - usable_coin_value

    if usable_coins > 0:
        coin_fa = (
            f"\n🪙 سکه آلفا: <b>{usable_coins} سکه</b>"
            f" (<b>{usable_coin_value:,} تومان</b>)"
            f"\n💵 مبلغ قابل پرداخت: <b>{payable_after_coin:,} تومان</b>"
        )
    else:
        coin_fa = (
            f"\n💵 مبلغ قابل پرداخت: <b>{final_price:,} تومان</b>"
        )

    if lang(uid) == "fa":
        if coupon:
            price_section = (
                f"💰 مبلغ اصلی: <b>{original_price:,} تومان</b>"
                f"{discount_text}\n"
                f"💳 مبلغ پس از تخفیف: <b>{final_price:,} تومان</b>"
            )
        else:
            price_section = (
                f"💳 مبلغ: <b>{final_price:,} تومان</b>"
            )

        text = (
            "🛒 <b>تأیید خرید</b>\n\n"
            f"📦 سرویس: <b>{title}</b>\n"
            "⏳ مدت: <b>۱ ماه</b>\n"
            "👤 کاربران: <b>نامحدود</b>\n\n"
            f"{price_section}"
            f"{coin_fa}\n\n"
            "اگر اطلاعات درست است، روی «✅ تأیید پرداخت» بزنید."
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
            f"\n💳 <b>Final price: {final_price:,} Toman</b>"
            f"{coin_en}\n\n"
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
        "service": service,
    }

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            confirm_text,
            callback_data=f"confirm_buy:{service}:{p['id']}",
            style="success"
        )],
        [InlineKeyboardButton(
            cancel_text,
            callback_data="cancel_buy",
            style="danger"
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
    service = query.data.split(":", 1)[1] if ":" in query.data else "gold"
    context.user_data["custom_service"] = service
    price_per_gb = {"gold": GOLD_PRICE_PER_GB, "silver": SILVER_PRICE_PER_GB, "bronze": BRONZE_PRICE_PER_GB}.get(service, GOLD_PRICE_PER_GB)
    await query.message.reply_text(
        tr(query.from_user.id, "custom_prompt", price=price_per_gb)
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

    service = context.user_data.get("custom_service", "gold")
    price_per_gb = {"gold": GOLD_PRICE_PER_GB, "silver": SILVER_PRICE_PER_GB, "bronze": BRONZE_PRICE_PER_GB}.get(service, GOLD_PRICE_PER_GB)
    original_price = gb * price_per_gb
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
            f"📦 سرویس: <b>{gb} GB</b>\n"
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
        "service": service,
    }

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(confirm_text, callback_data="confirm_custom", style="success")],
        [InlineKeyboardButton(cancel_text, callback_data="cancel_buy", style="danger")],
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
        "⚙️ تنظیمات", "📚 راهنما", "🛒 خرید سرویس",
        "🟣 سفارش‌های فعال", "🎁 تست رایگان",
        "🏠 MAIN MENU", "🛒 SHOP", "💰 WALLET",
        "👤 ACCOUNT", "👥 REFERRALS", "📞 SUPPORT",
        "⚙️ SETTINGS", "📚 GUIDE", "🛒 BUY SERVICE",
        "📦 MY ORDERS", "🎁 FREE TRIAL",
    }

    if code in menu_values:
        if code in {"🎁 تست رایگان", "🎁 FREE TRIAL"}:
            await free_trial(update, context)
            return ConversationHandler.END

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
            ui(uid, "\n\n🔄 لطفاً یک کد تخفیف معتبر وارد کنید.", "\n\n🔄 Please enter a valid coupon code."),
            reply_markup=menu(uid),
        )
        return COUPON_INPUT

    if coupon["max_uses"] and coupon["used"] >= coupon["max_uses"]:
        await update.message.reply_text(
            tr(uid, "coupon_bad") +
            ui(uid, "\n\n🔄 ظرفیت استفاده از این کد تمام شده است.", "\n\n🔄 This coupon has reached its usage limit."),
            reply_markup=menu(uid),
        )
        return COUPON_INPUT

    has_used = getattr(db, "has_coupon_used", None)
    if has_used and has_used(code, uid):
        await update.message.reply_text(
            ui(uid, "❌ شما قبلاً از این کد تخفیف استفاده کرده‌اید.\n\n🔄 لطفاً کد دیگری وارد کنید.", "❌ You have already used this coupon.\n\n🔄 Please use another coupon."),
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
        await query.answer(
            ui(uid, "❌ سفارش منقضی شده است.", "❌ This order has expired."),
            show_alert=True,
        )
        return

    await query.answer()

    u = db.get_user(uid)
    if not u:
        await query.message.reply_text(
            ui(uid, "❌ حساب کاربری پیدا نشد.", "❌ User account not found.")
        )
        context.user_data.pop("pending_purchase", None)
        return

    # Price after coupon/discount, before Alpha Coin
    price_before_coin = int(pending["price"])
    gb = pending["gb"]
    unlimited = bool(pending["unlimited"])
    plan_id = pending["plan_id"]
    service = pending.get("service", "gold")

    # Alpha Coin:
    # 1 ALC = 100 Toman
    # Maximum usable Coin = 30% of the order price
    available_coins = int(db.get_alpha_coins(uid) or 0)
    max_coin_by_order = (price_before_coin * 30 // 100) // 100
    coin_amount = min(available_coins, max_coin_by_order)
    coin_value = coin_amount * 100

    # Actual Toman paid after Alpha Coin
    price = price_before_coin - coin_value

    if u["balance"] < price:
        await query.message.reply_text(
            tr(uid, "not_enough", balance=u["balance"], price=price),
            reply_markup=menu(uid),
        )
        return

    # Create order using the actual cash amount.
    # create_order() deducts this amount from the Toman wallet.
    oid = db.create_order(uid, plan_id, gb, price, service)

    if not oid:
        await query.message.reply_text(
            tr(uid, "not_enough", balance=u["balance"], price=price),
            reply_markup=menu(uid),
        )
        return

    # Spend Alpha Coin only after the order exists, so the spend can
    # be tied to the real order ID through the description.
    if coin_amount > 0:
        spent = db.spend_alpha_coins(
            uid,
            coin_amount,
            f"Used for Order #{oid}",
        )

        if not spent:
            # Coin balance changed between calculation and purchase.
            # Return the Toman that was already deducted.
            db.refund(oid, uid, price)

            await query.message.reply_text(
                ui(
                    uid,
                    "⚠️ موجودی Alpha Coin شما تغییر کرده است. لطفاً دوباره خرید را انجام دهید.",
                    "⚠️ Your Alpha Coin balance changed. Please try the purchase again.",
                ),
                reply_markup=menu(uid),
            )
            return

    username = f"alpha_{uid}_{oid}_{secrets.token_hex(3)}"
    result = await create_customer(
        username,
        gb,
        unlimited,
        service=service,
    )

    if not result["ok"]:
        # Refund the actual Toman payment.
        db.refund(oid, uid, price)

        # Refund the Alpha Coin that was spent.
        if coin_amount > 0:
            db.add_alpha_coins(
                uid,
                coin_amount,
                "spend_refund",
                oid,
                f"Refunded Alpha Coin for failed Order #{oid}",
            )

        context.user_data.pop("pending_purchase", None)

        await query.message.reply_text(
            tr(uid, "panel_error"),
            reply_markup=menu(uid),
        )
        return

    data = result.get("data") or {}

    config = (
        result.get("connection_details")
        or result.get("subscription_url")
        or result.get("config")
        or data.get("subscription_url")
        or data.get("subscriptionUrl")
        or data.get("config")
        or data.get("link")
        or data.get("url")
        or ""
    )

    final_username = data.get("username", username)

    db.complete_order(
        oid,
        final_username,
        str(config),
    )

    # Check and automatically reward completed mission stages
    try:
        await check_and_reward_missions(uid, context)
    except Exception as mission_error:
        print(
            f"⚠️ Mission reward check failed after purchase: "
            f"{type(mission_error).__name__}: {mission_error}"
        )

    # Alpha Coin rewards are calculated from the actual Toman paid
    # after discount AND after Alpha Coin usage.
    coin_rewards = {
        "buyer": 0,
        "referrer": 0,
    }

    try:
        coin_rewards = db.award_purchase_alpha_coins(
            oid,
            uid,
            price,
        )

        print(
            f"🪙 Alpha Coin awarded for order #{oid}: "
            f"buyer={coin_rewards.get('buyer', 0)} ALC, "
            f"referrer={coin_rewards.get('referrer', 0)} ALC"
        )
    except Exception as coin_error:
        print(
            f"⚠️ Alpha Coin reward failed for order #{oid}: "
            f"{type(coin_error).__name__}: {coin_error}"
        )

    service_label = TEXT[lang(uid)].get(
        service,
        service.title(),
    )

    user = db.get_user(uid)

    admin_text = (
        "🟢 <b>سفارش جدید با موفقیت ساخته شد</b>\n\n"
        f"🧾 سفارش: <code>#{oid}</code>\n"
        f"🔌 سرویس: <b>{service_label}</b>\n"
        f"📦 سرویس: <b>{'Unlimited' if unlimited else str(gb) + ' GB'}</b>\n"
        f"💰 قیمت پس از تخفیف: <b>{price_before_coin:,} تومان</b>\n"
        f"🪙 سکه آلفا مصرف‌شده: <b>{coin_amount} ALC</b>"
        f" ({coin_value:,} تومان)\n"
        f"💳 مبلغ پرداختی نهایی: <b>{price:,} تومان</b>\n"
        f"👤 کاربر: <b>{query.from_user.full_name}</b>\n"
        f"🆔 Telegram ID: <code>{uid}</code>\n"
        f"📛 Username: @{query.from_user.username or '-'}\n"
        f"🔑 Panel Username: <code>{final_username}</code>\n"
        f"🔗 Connection: {config or '-'}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                admin_text,
                parse_mode="HTML",
            )
        except Exception as exc:
            print(
                "Admin notification failed:",
                admin_id,
                repr(exc),
            )

    # Only clear purchase/coupon state after successful purchase.
    context.user_data.pop("pending_purchase", None)
    context.user_data.pop("custom_service", None)
    context.user_data.pop("coupon", None)
    context.user_data.pop("coupon_code", None)

    buyer_coin = int(coin_rewards.get("buyer", 0))

    title = (
        f"🎉 <b>سفارش با موفقیت ثبت شد!</b>\n\n"
        f"🧾 شماره سفارش: #{oid}\n"
        f"📦 سرویس: {'Unlimited' if unlimited else str(gb) + ' GB'}\n"
        f"💵 مبلغ پرداختی: {price:,} تومان\n"
        f"🪙 سکه آلفا مصرف‌شده: {coin_amount} ALC"
        f" ({coin_value:,} تومان)\n"
        f"🎁 پاداش سکه آلفا: {buyer_coin} ALC\n"
        f"👤 نام کاربری: <code>{final_username}</code>"
    ) if lang(uid) == "fa" else (
        f"🎉 Your order was completed successfully!\n\n"
        f"🧾 Order: #{oid}\n"
        f"📦 Volume: {'Unlimited' if unlimited else str(gb) + ' GB'}\n"
        f"💰 Amount paid: {price:,} Toman\n"
        f"🪙 Alpha Coin used: {coin_amount} ALC"
        f" ({coin_value:,} Toman)\n"
        f"🪙 Alpha Coin reward: {buyer_coin} ALC\n"
        f"👤 Username: <code>{final_username}</code>"
    )

    await send_connection_card(
        query.message,
        uid,
        title,
        config,
        reply_markup=menu(uid),
    )

async def confirm_buy(update, context):
    query = update.callback_query
    parts = query.data.split(":")
    try:
        if len(parts) == 3:
            service, pid = parts[1], int(parts[2])
        else:
            service, pid = "gold", int(parts[1])
    except (ValueError, IndexError):
        await query.answer(ui(uid, "❌ سفارش نامعتبر است.", "❌ Invalid order."), show_alert=True)
        return
    pending = context.user_data.get("pending_purchase")
    if not pending or pending.get("plan_id") != pid or pending.get("service", "gold") != service:
        await query.answer(ui(uid, "❌ سفارش پیدا نشد.", "❌ Order not found."), show_alert=True)
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
    coins = db.get_alpha_coins(uid)

    if lang(uid) == "fa":
        text = (
            "👥 <b>زیرمجموعه‌گیری آلفا شاپ</b>\n\n"
            f"👤 تعداد زیرمجموعه‌ها: <b>{count} نفر</b>\n"
            f"🪙 موجودی سکه آلفا: <b>{coins:,} سکه</b>\n\n"
            "🎁 <b>پاداش دعوت</b>\n"
            "هر کاربر جدیدی که با لینک دعوت شما وارد شود،\n"
            "یک کد تخفیف <b>۵٪</b> یک‌بارمصرف دریافت می‌کنید.\n\n"
            "🪙 <b>پاداش خرید</b>\n"
            "از هر خرید موفق زیرمجموعه‌های شما،\n"
            "<b>۲٫۵٪</b> مبلغ پرداختی را به صورت سکه آلفا دریافت می‌کنید.\n\n"
            f"🔗 <b>لینک دعوت شما:</b>\n"
            f"{link}"
        )
    else:
        text = (
            "👥 <b>Alpha Shop Referrals</b>\n\n"
            f"👤 Referrals: <b>{count}</b>\n"
            f"🪙 Alpha Coin: <b>{coins:,} ALC</b>\n\n"
            "🎁 New users joining through your link receive a "
            "<b>5% one-time discount</b>.\n"
            "🪙 You receive <b>2.5%</b> of every successful purchase "
            "as Alpha Coin.\n\n"
            f"🔗 Your referral link:\n{link}"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=menu(uid),
    )

async def orders(update, context):
    if not await gate(update, context):
        return
    uid = update.effective_user.id
    rows = [r for r in db.user_orders(uid) if r["status"] == "completed" and r["panel_username"]]
    active = []
    now = int(__import__("time").time())
    for row in rows[:30]:
        info = await get_customer_info(row["panel_username"], row["service"] or "gold")
        if not info.get("ok"):
            continue
        expire = info.get("expire")
        if isinstance(expire, str):
            try:
                expire = int(float(expire))
            except ValueError:
                try:
                    from datetime import datetime
                    expire = int(datetime.fromisoformat(expire.replace("Z", "+00:00")).timestamp())
                except Exception:
                    expire = None
        if expire is None or int(expire) <= now:
            continue
        active.append((row, info, int(expire)))
    if not active:
        await update.message.reply_text(ui(uid, "🟣 هنوز سرویس فعالی ندارید.", "🟣 You have no active services."), reply_markup=menu(uid))
        return
    buttons = []
    for row, info, expire in active[:20]:
        gb = ui(uid, "نامحدود", "Unlimited") if row["gb"] is None else f"{row['gb']} GB"
        service = str(row["service"] or "gold").upper()
        buttons.append([InlineKeyboardButton(f"🟣 #{row['id']} | {service} | {gb}", callback_data=f"active_order:{row['id']}", style="primary")])
    await update.message.reply_text(ui(uid, "🟣 <b>سفارش‌های فعال شما:</b>\n\nیکی از سرویس‌ها را انتخاب کنید:", "🟣 <b>Your active services:</b>\n\nChoose a service:"), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))


async def active_order_detail(update, context):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()

    try:
        oid = int(q.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await q.message.reply_text(
            ui(uid, "❌ سفارش نامعتبر است.", "❌ Invalid order."),
            reply_markup=menu(uid),
        )
        return

    row = db.get_order(uid, oid)

    if not row or row["status"] != "completed" or not row["panel_username"]:
        await q.message.reply_text(
            ui(uid, "❌ سرویس فعال پیدا نشد.", "❌ Active service not found."),
            reply_markup=menu(uid),
        )
        return

    info = await get_customer_info(
        row["panel_username"],
        row["service"] or "gold",
    )

    if not info.get("ok"):
        await q.message.reply_text(
            ui(
                uid,
                "❌ دریافت اطلاعات سرویس از پنل انجام نشد. لطفاً بعداً دوباره تلاش کنید.",
                "❌ Could not retrieve service information from the panel. Please try again later.",
            ),
            reply_markup=menu(uid),
        )
        return

    expire = info.get("expire")

    if isinstance(expire, str):
        try:
            expire = int(float(expire))
        except ValueError:
            try:
                from datetime import datetime
                expire = int(
                    datetime.fromisoformat(
                        expire.replace("Z", "+00:00")
                    ).timestamp()
                )
            except Exception:
                expire = None

    now = int(__import__("time").time())

    if not expire or expire <= now:
        await q.message.reply_text(
            ui(
                uid,
                "⛔ این سرویس منقضی شده است.",
                "⛔ This service has expired.",
            ),
            reply_markup=menu(uid),
        )
        return

    remaining_seconds = int(expire) - now
    days_left = max(1, (remaining_seconds + 86399) // 86400)

    gb = (
        ui(uid, "نامحدود", "Unlimited")
        if row["gb"] is None
        else f"{row['gb']} GB"
    )

    connection = info.get("subscription_url") or row["config"] or ""

    service_label = TEXT[lang(uid)].get(
        str(row["service"]),
        str(row["service"]).title(),
    )

    # Expiry warning
    if days_left <= 1:
        expiry_warning = ui(
            uid,
            "🔴 <b>هشدار انقضا:</b>\nاین سرویس کمتر از ۱ روز اعتبار دارد. برای جلوگیری از قطع سرویس، آن را تمدید کنید.",
            "🔴 <b>Expiry warning:</b>\nThis service has less than 1 day remaining. Renew it to avoid interruption.",
        )
    elif days_left <= 3:
        expiry_warning = ui(
            uid,
            "🟠 <b>هشدار انقضا:</b>\nاین سرویس به‌زودی منقضی می‌شود. بهتر است قبل از پایان اعتبار آن را تمدید کنید.",
            "🟠 <b>Expiry warning:</b>\nThis service will expire soon. Consider renewing it before the expiration date.",
        )
    elif days_left <= 7:
        expiry_warning = ui(
            uid,
            "🟡 <b>یادآوری:</b>\nکمتر از ۷ روز تا پایان اعتبار سرویس باقی مانده است.",
            "🟡 <b>Reminder:</b>\nLess than 7 days remain before this service expires.",
        )
    else:
        expiry_warning = ""

    if lang(uid) == "fa":
        text = (
            f"🟣 <b>سرویس فعال شما</b>\n\n"
            f"🧾 سفارش: #{oid}\n"
            f"🔌 سرویس: {service_label}\n"
            f"📦 حجم: {gb}\n"
            f"⏳ روز باقی‌مانده: <b>{days_left} روز</b>\n"
            f"👤 نام کاربری: <code>{html.escape(str(row['panel_username']))}</code>\n"
        )

        if expiry_warning:
            text += f"\n{expiry_warning}\n"

        text += (
            f"\n🔗 لینک اشتراک:\n"
            f"{html.escape(str(connection))}"
        )

    else:
        text = (
            f"🟣 <b>Your Active Service</b>\n\n"
            f"🧾 Order: #{oid}\n"
            f"🔌 Service: {service_label}\n"
            f"📦 Volume: {gb}\n"
            f"⏳ Days remaining: <b>{days_left} days</b>\n"
            f"👤 Username: <code>{html.escape(str(row['panel_username']))}</code>\n"
        )

        if expiry_warning:
            text += f"\n{expiry_warning}\n"

        text += (
            f"\n🔗 Subscription:\n"
            f"{html.escape(str(connection))}"
        )

    await q.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=menu(uid),
    )


async def renew_service(update, context):
    if not await gate(update, context):
        return
    uid = update.effective_user.id
    rows = [r for r in db.user_orders(uid) if r["status"] == "completed" and r["panel_username"]]
    if not rows:
        await update.message.reply_text(tr(uid, "renew_none"), reply_markup=menu(uid))
        return
    buttons = []
    for row in rows[:20]:
        service = str(row["service"] or "gold").upper()
        gb = "Unlimited" if row["gb"] is None else f"{row['gb']} GB"
        buttons.append([InlineKeyboardButton(f"🔄 #{row['id']} | {service} | {gb}", callback_data=f"renew:{row['id']}", style="primary")])
    await update.message.reply_text(tr(uid, "renew_choose"), reply_markup=InlineKeyboardMarkup(buttons))


async def renew_confirm(update, context):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()
    try:
        oid = int(q.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await q.message.reply_text(ui(uid, "❌ سفارش نامعتبر است.", "❌ Invalid order."))
        return
    row = db.get_order(uid, oid)
    if not row or row["status"] != "completed" or not row["panel_username"]:
        await q.message.reply_text(tr(uid, "renew_error"), reply_markup=menu(uid))
        return
    plan = db.get_plan(row["plan_id"]) if row["plan_id"] else None
    price = int(plan["price"]) if plan and plan["active"] else int(row["price"])
    gb = "Unlimited" if row["gb"] is None else f"{row['gb']} GB"
    service_label = TEXT[lang(uid)].get(str(row["service"]), str(row["service"]).title())
    await q.message.reply_text(
        tr(uid, "renew_confirm", oid=oid, service=service_label, gb=gb, price=price, days=RENEW_DAYS),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ تأیید تمدید" if lang(uid) == "fa" else "✅ Confirm Renewal", callback_data=f"renew_confirm:{oid}", style="success"),
            InlineKeyboardButton("❌ لغو" if lang(uid) == "fa" else "❌ Cancel", callback_data="renew_cancel", style="danger"),
        ]]),
    )


async def renew_execute(update, context):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()
    try:
        oid = int(q.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await q.message.reply_text(ui(uid, "❌ سفارش نامعتبر است.", "❌ Invalid order."))
        return
    row = db.get_order(uid, oid)
    if not row or row["status"] != "completed" or not row["panel_username"]:
        await q.message.reply_text(tr(uid, "renew_error"), reply_markup=menu(uid))
        return
    plan = db.get_plan(row["plan_id"]) if row["plan_id"] else None
    price = int(plan["price"]) if plan and plan["active"] else int(row["price"])
    if not db.charge_renewal(uid, oid, price):
        await q.message.reply_text(tr(uid, "not_enough", balance=db.get_user(uid)["balance"], price=price), reply_markup=menu(uid))
        return
    result = await extend_customer(row["panel_username"], RENEW_DAYS, service=row["service"] or "gold")
    if not result.get("ok"):
        db.refund_renewal(uid, price, oid)
        await q.message.reply_text(tr(uid, "renew_error"), reply_markup=menu(uid))
        return
    try:
        db.record_renewal_success(uid, oid, price)
    except Exception as renewal_error:
        print(
            f"⚠️ Failed to record successful renewal #{oid}: "
            f"{type(renewal_error).__name__}: {renewal_error}"
        )

    try:
        await check_and_reward_missions(uid, context)
    except Exception as mission_error:
        print(
            f"⚠️ Mission reward check failed after renewal: "
            f"{type(mission_error).__name__}: {mission_error}"
        )

    config = result.get("connection_details") or result.get("subscription_url") or result.get("config") or row["config"] or ""
    if config:
        db.complete_order(oid, row["panel_username"], str(config))
    await send_connection_card(
        q.message, uid,
        tr(uid, "renew_ok", days=RENEW_DAYS),
        config,
        extra_lines=[f"🧾 {ui(uid, 'سفارش', 'Order')}: #{oid}", f"📅 {ui(uid, 'تمدید', 'Renewal')}: {RENEW_DAYS} {ui(uid, 'روز', 'days')}"],
        reply_markup=menu(uid),
    )


async def renew_cancel(update, context):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("❌ لغو شد." if lang(q.from_user.id) == "fa" else "❌ Cancelled.", reply_markup=menu(q.from_user.id))

def support_keyboard(uid):
    l = lang(uid)
    if l == "fa":
        faq_title = "📚 سؤالات متداول"
        human_title = "👨‍💻 ارتباط با پشتیبانی"
        ai_title = "🤖 گفت‌وگو با هوش مصنوعی"
        channel_title = "📢 کانال آلفا شاپ"
        back_title = "🏠 منوی اصلی"
    else:
        faq_title = "📚 Frequently Asked Questions"
        human_title = "👨‍💻 Contact Human Support"
        ai_title = "🤖 Chat with AI"
        channel_title = "📢 Alpha Shop Channel"
        back_title = "🏠 Main Menu"

    rows = [
        [InlineKeyboardButton(faq_title, callback_data="support_faq_title", style="primary")],
    ]
    for i in range(1, 9, 2):
        rows.append([
            InlineKeyboardButton(TEXT[l][f"faq_{i}"], callback_data=f"support_faq:{i}", style="primary"),
            InlineKeyboardButton(TEXT[l][f"faq_{i+1}"], callback_data=f"support_faq:{i+1}", style="primary"),
        ])
    rows += [
        [InlineKeyboardButton(human_title, callback_data="support_human", style="success")],
        [InlineKeyboardButton(ai_title, callback_data="support_ai", style="primary")],
        [
            InlineKeyboardButton(channel_title, url="https://t.me/alphashopss", style="primary"),
            InlineKeyboardButton(back_title, callback_data="support_main_menu", style="danger"),
        ],
    ]
    return InlineKeyboardMarkup(rows)

async def support(update, context):
    if not await gate(update, context):
        return
    uid = update.effective_user.id
    context.user_data.pop("support_ai_mode", None)
    context.user_data.pop("support_ai_history", None)
    await update.message.reply_text(
        tr(uid, "support_text"),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=support_keyboard(uid),
    )

async def support_faq_callback(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    key = q.data.split(":", 1)[1]
    l = lang(uid)
    await q.message.reply_text(TEXT[l][f"faq_a{key}"], parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به مرکز پشتیبانی" if l == "fa" else "🔙 Back to Support Center", callback_data="support_back", style="primary")]
    ]))

async def support_back_callback(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    await q.message.reply_text(
        tr(uid, "support_text"),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=support_keyboard(uid),
    )

async def support_faq_title_callback(update, context):
    q = update.callback_query
    await q.answer()

async def support_main_menu_callback(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    context.user_data.pop("support_ai_mode", None)
    context.user_data.pop("support_ai_history", None)
    await q.message.reply_text(ui(uid, "🏠 به منوی اصلی برگشتید.", "🏠 Back to the main menu."), reply_markup=menu(uid))

async def support_human_callback(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    context.user_data.pop("support_ai_mode", None)
    context.user_data.pop("support_ai_history", None)
    support = SUPPORT_USERNAME or "@AlphaShopSupport"
    await q.message.reply_text(ui(uid, f"👨‍💻 ارتباط با پشتیبانی انسانی:\n{support}", f"👨‍💻 Human support:\n{support}"), reply_markup=menu(uid))

async def support_ai_callback(update, context):
    print("🔥 AI CALLBACK CALLED", flush=True)
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    print(f"🔥 AI CALLBACK USER: {uid}", flush=True)
    if not GEMINI_API_KEY:
        await q.message.reply_text(tr(uid, "support_ai_no_key"), reply_markup=menu(uid))
        return
    context.user_data["support_ai_mode"] = True
    context.user_data["support_ai_history"] = []
    print(f"🟢 AI MODE SET: {context.user_data.get('support_ai_mode')}", flush=True)
    print(f"🟢 AI HISTORY SET: {context.user_data.get('support_ai_history')}", flush=True)
    await q.message.reply_text(
        "🤖 <b>گفت‌وگو با هوش مصنوعی Alpha Shop فعال شد!</b>\n\n"
        "💬 پیام خودت را همین‌جا بفرست تا راهنماییت کنم.\n\n"
        "✨ می‌تونی درباره خرید سرویس، کیف پول، سفارش‌ها، "
        "تمدید، مشکلات اتصال و سوالات مربوط به سرویس‌ها ازم بپرسی.\n\n"
        "🚪 <b>برای خروج از گفت‌وگو با هوش مصنوعی، "
        "فقط یکی از دکمه‌های منوی پایین را انتخاب کن.</b>",
        parse_mode="HTML",
        reply_markup=menu(uid),
    )

async def ai_support_message(update, context):
    print("🔥 PROFESSIONAL AI HANDLER CALLED", flush=True)

    if not context.user_data.get("support_ai_mode"):
        print("⚠️ AI SUPPORT MODE IS OFF", flush=True)
        return

    if not update.message:
        return

    uid = update.effective_user.id
    text = (update.message.text or "").strip()

    if not text:
        return

    if not GEMINI_API_KEY:
        await update.message.reply_text(
            tr(uid, "support_ai_no_key")
        )
        return

    thinking_message = await update.message.reply_text(
        "🤔 در حال بررسی..."
    )

    history = context.user_data.setdefault(
        "support_ai_history",
        [],
    )

    try:
        model = (
            GEMINI_MODEL or "gemini-3.6-flash"
        ).strip()

        result = await ai_router.professional_ai(
            api_key=GEMINI_API_KEY,
            model=model,
            user_id=uid,
            user_text=text,
            history=history,
        )

        new_history = result.get("history")

        if isinstance(new_history, list):
            context.user_data["support_ai_history"] = (
                new_history[-8:]
            )

        if not result.get("ok"):
            answer = result.get(
                "answer",
                tr(uid, "support_ai_error"),
            )
        else:
            answer = (
                result.get("answer")
                or tr(uid, "support_ai_error")
            )

        # Convert common Markdown formatting from AI
        # to Telegram HTML formatting.
        import re
        import html

        def format_ai_answer(text):
            text = str(text or "").strip()

            # Escape HTML first so AI output cannot inject markup.
            text = html.escape(text)

            # **bold** -> <b>bold</b>
            text = re.sub(
                r"\*\*(.+?)\*\*",
                r"<b>\1</b>",
                text,
            )

            # *italic* -> <i>italic</i>
            text = re.sub(
                r"(?<!\*)\*([^*\n]+?)\*(?!\*)",
                r"<i>\1</i>",
                text,
            )

            return text

        formatted_answer = format_ai_answer(answer)

        try:
            await thinking_message.edit_text(
                formatted_answer,
                parse_mode="HTML",
            )
        except Exception as edit_error:
            print(
                "⚠️ PROFESSIONAL AI EDIT FAILED: "
                f"{type(edit_error).__name__}: "
                f"{edit_error}",
                flush=True,
            )

            try:
                await update.message.reply_text(
                    formatted_answer,
                    parse_mode="HTML",
                )
            except Exception as reply_error:
                print(
                    "⚠️ PROFESSIONAL AI REPLY FAILED: "
                    f"{type(reply_error).__name__}: "
                    f"{reply_error}",
                    flush=True,
                )

    except Exception as e:
        print(
            "❌ Professional AI error: "
            f"{type(e).__name__}: {e}",
            flush=True,
        )

        error_message = (
            "⚠️ فعلاً هوش مصنوعی در دسترس نیست.\n\n"
            "لطفاً چند ثانیه بعد دوباره امتحان کن.\n"
            "اگر مشکل ادامه داشت، با پشتیبانی تماس بگیر:\n"
            "@AlphaShopSupport"
        )

        try:
            await thinking_message.edit_text(
                error_message
            )
        except Exception as final_error:
            print(
                "⚠️ FINAL AI MESSAGE FAILED: "
                f"{type(final_error).__name__}: "
                f"{final_error}",
                flush=True,
            )

async def end_ai_mode(update, context):
    if context.user_data.get("support_ai_mode"):
        context.user_data.pop("support_ai_mode", None)
        context.user_data.pop("support_ai_history", None)


async def account(update, context):
    if not await gate(update, context):
        return

    uid = update.effective_user.id
    stats = db.profile_stats(uid)

    if not stats:
        return

    lang_code = stats.get("lang", "fa")

    username = stats.get("username") or "-"
    username_display = (
        f"@{username}"
        if username != "-"
        else "-"
    )

    from datetime import datetime

    created_at = stats.get("created_at") or 0

    if created_at:
        joined_date = datetime.fromtimestamp(
            created_at
        ).strftime("%Y/%m/%d")
    else:
        joined_date = "-"

    coin_value = stats["alpha_coins"] * 100

    mission = db.mission_summary(uid)
    mission_stage = mission.get("stage", 1)
    mission_progress = f"{mission.get('progress', 0)}/{mission.get('total', 0)}"

    if lang_code == "en":
        text = (
            "👤 <b>User Profile | Alpha Shop</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            "🪪 <b>Account Information</b>\n\n"

            f"🆔 <b>User ID:</b> "
            f"<code>{uid}</code>\n"
            f"👤 <b>Username:</b> "
            f"{username_display}\n"
            f"🌐 <b>Language:</b> "
            f"English\n"
            f"📅 <b>Join Date:</b> "
            f"{joined_date}\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "💰 <b>Wallet & Credits</b>\n\n"

            f"💳 <b>Wallet Balance:</b> "
            f"{stats['balance']:,} Toman\n"
            f"🪙 <b>Alpha Coins:</b> "
            f"{stats['alpha_coins']:,} ALC\n"
            f"💎 <b>Alpha Coin Value:</b> "
            f"{coin_value:,} Toman\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "📊 <b>Activity Statistics</b>\n\n"

            f"🛒 <b>Successful Purchases:</b> "
            f"{stats['purchases']} orders\n"
            f"🔄 <b>Successful Renewals:</b> "
            f"{stats['renewals']} times\n"
            f"🟢 <b>Active Services:</b> "
            f"{stats['active_services']} services\n"
            f"👥 <b>Successful Referrals:</b> "
            f"{stats['referrals']} users\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🎁 <b>Rewards</b>\n\n"
            f"🏆 <b>Current Mission Stage:</b> {mission_stage}\n"
            f"📈 <b>Mission Progress:</b> {mission_progress}\n"
            f"🪙 <b>Total Alpha Coins Earned:</b> "
            f"{stats['total_coins_earned']:,} ALC\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🔐 <b>Account Status</b>\n\n"
            "✅ Your account is active\n"
            "🛡️ Your account information is protected\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "💙 <i>Your trust, our credibility.</i>"
        )
    else:
        text = (
            "👤 <b>پروفایل کاربری | Alpha Shop</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            "🪪 <b>اطلاعات حساب</b>\n\n"

            f"🆔 <b>شناسه کاربری:</b> "
            f"<code>{uid}</code>\n"
            f"👤 <b>نام کاربری:</b> "
            f"{username_display}\n"
            f"🌐 <b>زبان حساب:</b> "
            f"فارسی\n"
            f"📅 <b>تاریخ عضویت:</b> "
            f"{joined_date}\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "💰 <b>کیف پول و اعتبار</b>\n\n"

            f"💳 <b>موجودی کیف پول:</b> "
            f"{stats['balance']:,} تومان\n"
            f"🪙 <b>آلفا کوین:</b> "
            f"{stats['alpha_coins']:,} ALC\n"
            f"💎 <b>ارزش آلفا کوین:</b> "
            f"{coin_value:,} تومان\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "📊 <b>آمار فعالیت</b>\n\n"

            f"🛒 <b>خریدهای موفق:</b> "
            f"{stats['purchases']} سفارش\n"
            f"🔄 <b>تمدیدهای موفق:</b> "
            f"{stats['renewals']} بار\n"
            f"🟢 <b>سرویس‌های فعال:</b> "
            f"{stats['active_services']} سرویس\n"
            f"👥 <b>زیرمجموعه‌های موفق:</b> "
            f"{stats['referrals']} نفر\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🎁 <b>پاداش‌ها</b>\n\n"
            f"🏆 <b>مرحله فعلی:</b> {mission_stage}\n"
            f"📈 <b>پیشرفت مأموریت:</b> {mission_progress}\n"
            f"🪙 <b>مجموع آلفا کوین دریافتی:</b> "
            f"{stats['total_coins_earned']:,} ALC\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "🔐 <b>وضعیت حساب</b>\n\n"
            "✅ حساب شما فعال است\n"
            "🛡️ اطلاعات حساب شما محفوظ است\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "💙 <i>اعتماد شما ، اعتبار ماست .</i>"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
    )


GUIDE_APPS = {
    "v2box": {
        "name": "V2Box",
        "video": GUIDE_VIDEO_V2BOX,
        "play": "https://play.google.com/store/apps/details?id=dev.hexasoftware.v2box",
        "ios": "https://apps.apple.com/us/app/v2box-v2ray-client/id6446814690",
        "text": "V2Box tutorial: add the subscription link, update the subscription, and connect.",
    },
    "happ": {
        "name": "Happ",
        "video": GUIDE_VIDEO_HAPP,
        "play": "https://play.google.com/store/apps/details?id=com.happproxy",
        "ios": "https://apps.apple.com/us/app/happ-proxy-utility/id6504287215",
        "text": "Happ tutorial: add the subscription link, update the subscription, and connect.",
    },
    "hiddify": {
        "name": "Hiddify",
        "video": GUIDE_VIDEO_HIDDIFY,
        "play": "https://play.google.com/store/apps/details?id=app.hiddify.com",
        "ios": "https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532",
        "text": "Hiddify tutorial: add the subscription link, update the profile, and connect.",
    },
    "streisand": {
        "name": "Streisand",
        "video": GUIDE_VIDEO_STREISAND,
        "play": "",
        "ios": "https://apps.apple.com/us/app/streisand/id6450534064",
        "text": "Streisand tutorial: add the subscription link, update it, and connect.",
    },
}


def guide_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟣 Hiddify", callback_data="guide_app:hiddify", style="primary")],
        [InlineKeyboardButton("🟣 V2Box", callback_data="guide_app:v2box", style="primary")],
        [InlineKeyboardButton("🟣 Streisand", callback_data="guide_app:streisand", style="primary")],
        [InlineKeyboardButton("🟣 Happ", callback_data="guide_app:happ", style="primary")],
    ])


async def guide(update, context):
    if not await gate(update, context):
        return
    uid = update.effective_user.id
    if lang(uid) == "fa":
        text = (
            "📚 <b>راهنمای استفاده از آلفا شاپ</b>\n\n"
            "بعد از خرید سرویس، <b>لینک اشتراک</b> و QR Code برای شما ارسال می‌شود. "
            "برنامه موردنظر خود را انتخاب کنید تا آموزش ویدیویی همان برنامه را ببینید.\n\n"
            "در آموزش‌ها نحوه اضافه کردن لینک اشتراک، به‌روزرسانی اشتراک و اتصال به سرویس توضیح داده شده است.\n\n"
            "🆘 اگر بعد از وارد کردن لینک سرورها نمایش داده نشدند، ابتدا Subscription را Update کنید و یک سرور دیگر را امتحان کنید. "
            "اگر مشکل برطرف نشد، از بخش 📞 پشتیبانی با ما در ارتباط باشید.\n\n"
            "👇 <b>برنامه موردنظر را انتخاب کنید:</b>"
        )
    else:
        text = (
            "📚 <b>Alpha Shop Guide</b>\n\n"
            "After purchasing a service, you will receive a <b>subscription link</b> and QR Code. "
            "Choose your client below to watch its tutorial.\n\n"
            "The tutorials explain how to add the subscription link, update the subscription, and connect.\n\n"
            "🆘 If servers do not appear, update the subscription first and try another server. "
            "If the problem continues, contact 📞 Support.\n\n"
            "👇 <b>Choose your app:</b>"
        )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=guide_keyboard())


async def guide_app(update, context):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()
    key = q.data.split(":", 1)[1]
    app_info = GUIDE_APPS.get(key)
    if not app_info:
        return

    buttons = []
    if app_info["play"]:
        buttons.append(InlineKeyboardButton("🤖 Google Play", url=app_info["play"], style="primary"))
    if app_info["ios"]:
        buttons.append(InlineKeyboardButton("🍎 App Store", url=app_info["ios"], style="primary"))
    markup = InlineKeyboardMarkup([buttons] if buttons else [])

    captions = {
        "hiddify": ui(uid, "🎥 آموزش Hiddify\n\nوارد کردن لینک اشتراک، به‌روزرسانی پروفایل و اتصال به سرویس.", "🎥 Hiddify Tutorial\n\nAdd the subscription link, update the profile, and connect."),
        "v2box": ui(uid, "🎥 آموزش V2Box\n\nاضافه کردن لینک اشتراک، به‌روزرسانی Subscription و اتصال به سرویس.", "🎥 V2Box Tutorial\n\nAdd the subscription link, update the subscription, and connect."),
        "streisand": ui(uid, "🎥 آموزش Streisand\n\nاضافه کردن لینک اشتراک، به‌روزرسانی و اتصال به سرویس.", "🎥 Streisand Tutorial\n\nAdd the subscription link, update it, and connect."),
        "happ": ui(uid, "🎥 آموزش Happ\n\nاضافه کردن لینک اشتراک، به‌روزرسانی و اتصال به سرویس.", "🎥 Happ Tutorial\n\nAdd the subscription link, update it, and connect."),
    }
    caption = captions.get(key, f"🟣 <b>{app_info['name']}</b>") + "\n\n" + ui(uid, "📥 لینک نصب برنامه:", "📥 Install the app:")
    video = app_info["video"]

    # A video can be either a Telegram file_id from .env or a bundled local MP4.
    if video and os.path.isfile(video):
        with open(video, "rb") as video_file:
            await q.message.reply_video(video=video_file, caption=caption, parse_mode="HTML", reply_markup=markup)
    elif video:
        await q.message.reply_video(video=video, caption=caption, parse_mode="HTML", reply_markup=markup)
    else:
        await q.message.reply_text(
            caption + "\n\n" + ui(uid, "🎬 ویدیوی این بخش هنوز تنظیم نشده است.", "🎬 The tutorial video for this section has not been configured yet."),
            parse_mode="HTML",
            reply_markup=markup,
        )



BROADCAST_MESSAGE = 10


async def admin_broadcast_start(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.callback_query.answer("⛔ Access denied", show_alert=True)
        return ConversationHandler.END
    await update.callback_query.answer()
    context.user_data["broadcast_active"] = True
    await update.callback_query.message.reply_text(tr(update.effective_user.id, "broadcast_start"))
    return BROADCAST_MESSAGE


async def broadcast_receive(update, context):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return ConversationHandler.END
    users = db.all_users(limit=100000)
    ok = 0
    fail = 0
    for user in users:
        target = int(user["id"])
        if int(user["blocked"] or 0):
            continue
        try:
            await context.bot.copy_message(
                chat_id=target,
                from_chat_id=update.effective_chat.id,
                message_id=update.effective_message.message_id,
            )
            ok += 1
        except Exception as exc:
            fail += 1
            print("Broadcast failed:", target, repr(exc))
        await asyncio.sleep(0.03)
    context.user_data.pop("broadcast_active", None)
    await update.effective_message.reply_text(tr(uid, "broadcast_done", ok=ok, fail=fail))
    return ConversationHandler.END


async def broadcast_cancel(update, context):
    context.user_data.pop("broadcast_active", None)
    await update.message.reply_text("❌ پیام همگانی لغو شد.")
    return ConversationHandler.END

async def admin_panel(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(tr(update.effective_user.id, "admin_only"))
        return

    s = db.stats()
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💳 شارژهای در انتظار", callback_data="admin_deposits", style="success"),
                InlineKeyboardButton("📊 آمار", callback_data="admin_stats", style="primary"),
            ],
            [
                InlineKeyboardButton("📦 مدیریت پلن‌ها", callback_data="admin_plans", style="primary"),
                InlineKeyboardButton("🎟 کدهای تخفیف", callback_data="admin_coupons", style="primary"),
            ],
            [
                InlineKeyboardButton("👥 کاربران", callback_data="admin_users", style="primary"),
                InlineKeyboardButton("➕ افزایش موجودی", callback_data="admin_balance", style="success"),
                InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast", style="primary"),
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
                        callback_data=f"dep:1:{d['id']}",
                        style="success"
                    ),
                    InlineKeyboardButton(
                        "❌ رد",
                        callback_data=f"dep:0:{d['id']}",
                        style="danger"
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
            text.append(f"#{p['id']} | {p['service'].upper()} | {p['title_fa']} | {price} | {state}")
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

    elif q.data == "admin_broadcast":
        await q.message.reply_text("📢 برای شروع ارسال پیام همگانی، دکمه ورود به حالت ارسال را بزنید.")
        await q.message.reply_text("👇", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 شروع پیام همگانی", callback_data="start_broadcast", style="primary")]]))

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
        try:
            await check_and_reward_missions(uid, context)
        except Exception as mission_error:
            print(
                f"⚠️ Mission reward check failed after deposit: "
                f"{type(mission_error).__name__}: {mission_error}"
            )

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
    if not await gate(update, context):
        return
    uid = update.effective_user.id
    l = lang(uid)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(TEXT[l]["gold"], callback_data="trial:gold", style="success")],
        [InlineKeyboardButton(TEXT[l]["silver"], callback_data="trial:silver", style="primary")],
        [InlineKeyboardButton(TEXT[l]["bronze"], callback_data="trial:bronze", style="danger")],
    ])
    await update.message.reply_text(tr(uid, "trial_choose"), reply_markup=keyboard)


async def trial_service(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    service = q.data.split(":", 1)[1]
    if db.has_used_trial(uid, service):
        await q.message.reply_text(tr(uid, "trial_used"), reply_markup=menu(uid))
        return
    username = f"{service}_trial_{uid}"
    result = await create_customer(username=username, gb=FREE_TEST_GB, days=FREE_TEST_DAYS, service=service)
    if not result["ok"]:
        await q.message.reply_text(tr(uid, "trial_error"), reply_markup=menu(uid))
        return
    data = result.get("data") or {}
    config = (
        result.get("connection_details")
        or result.get("subscription_url")
        or result.get("config")
        or data.get("subscription_url")
        or data.get("subscriptionUrl")
        or data.get("config")
        or data.get("link")
        or data.get("url")
        or ""
    )
    db.set_trial_used(uid, service)
    title = (
        f"🎉 تست رایگان {TEXT[lang(uid)][service]} شما فعال شد." if lang(uid) == "fa"
        else f"🎉 Your {TEXT[lang(uid)][service]} free trial has been activated."
    )
    extra = ["📦 سرویس: ۱۵۰ مگابایت", "📅 اعتبار: ۱ روز"] if lang(uid) == "fa" else ["📦 Volume: 150 MB", "📅 Validity: 1 day"]
    await send_connection_card(q.message, uid, title, config, extra_lines=extra, reply_markup=menu(uid))


async def copytest(update, context):
    await update.message.reply_text(
        "🔗 لینک تست:\n\nhttps://example.com/test",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📋 کپی لینک",
                    copy_text=CopyTextButton(
                        text="https://example.com/test"
                    )
                )
            ]
        ]),
        disable_web_page_preview=True,
    )




async def automatic_expiry_warning_job(context):
    """
    بررسی خودکار انقضا و حجم سرویس‌ها.
    وضعیت هشدارها داخل SQLite ذخیره می‌شود
    تا بعد از Restart دوباره ارسال نشوند.
    """

    import sqlite3
    import time

    db_file = os.getenv("DATABASE_FILE", "alphashop.db")

    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS service_warning_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                warning_type TEXT NOT NULL,
                sent_at INTEGER NOT NULL,
                UNIQUE(order_id, warning_type)
            )
            """
        )

        conn.commit()

        rows = conn.execute(
            """
            SELECT id, user_id, panel_username, service
            FROM orders
            WHERE status = 'completed'
              AND panel_username IS NOT NULL
              AND panel_username != ''
            ORDER BY id DESC
            """
        ).fetchall()

    except Exception as exc:
        print(f"❌ AUTO WARNING DB ERROR: {exc!r}")
        return

    now = int(time.time())

    async def already_sent(order_id, warning_type):
        try:
            row = conn.execute(
                """
                SELECT 1
                FROM service_warning_log
                WHERE order_id = ?
                  AND warning_type = ?
                LIMIT 1
                """,
                (order_id, warning_type),
            ).fetchone()

            return row is not None

        except Exception as exc:
            print(f"⚠️ WARNING LOG READ ERROR: {exc!r}")
            return True

    async def mark_sent(order_id, warning_type):
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO service_warning_log
                    (order_id, warning_type, sent_at)
                VALUES (?, ?, ?)
                """,
                (order_id, warning_type, int(time.time())),
            )
            conn.commit()

        except Exception as exc:
            print(f"⚠️ WARNING LOG WRITE ERROR: {exc!r}")

    try:
        for row in rows:
            try:
                oid = int(row["id"])
                uid = int(row["user_id"])
                username = str(row["panel_username"]).strip()
                service = str(row["service"] or "gold")

                info = await get_customer_info(
                    username,
                    service,
                )

                if not info.get("ok"):
                    continue

                # =================================================
                # EXPIRY
                # =================================================

                expire = info.get("expire")

                if isinstance(expire, str):
                    try:
                        expire = int(float(expire))
                    except ValueError:
                        try:
                            from datetime import datetime

                            expire = int(
                                datetime.fromisoformat(
                                    expire.replace("Z", "+00:00")
                                ).timestamp()
                            )

                        except Exception:
                            expire = None

                if expire:
                    expire = int(expire)

                    if expire > now:
                        remaining = expire - now
                        days_left = max(
                            1,
                            (remaining + 86399) // 86400
                        )

                        if days_left <= 1:
                            warning_type = "expire_1d"

                        elif days_left <= 3:
                            warning_type = "expire_3d"

                        elif days_left <= 7:
                            warning_type = "expire_7d"

                        else:
                            warning_type = None

                        if warning_type and not await already_sent(
                            oid,
                            warning_type,
                        ):

                            if lang(uid) == "fa":

                                if warning_type == "expire_1d":
                                    message = (
                                        "🔴 <b>هشدار مهم انقضا</b>\n\n"
                                        f"🧾 سفارش: #{oid}\n"
                                        f"🔌 سرویس: {service.upper()}\n"
                                        "⏳ کمتر از ۱ روز تا پایان اعتبار "
                                        "سرویس شما باقی مانده است.\n\n"
                                        "برای جلوگیری از قطع سرویس، "
                                        "سرویس خود را تمدید کنید."
                                    )

                                elif warning_type == "expire_3d":
                                    message = (
                                        "🟠 <b>هشدار انقضای سرویس</b>\n\n"
                                        f"🧾 سفارش: #{oid}\n"
                                        f"🔌 سرویس: {service.upper()}\n"
                                        f"⏳ حدود {days_left} روز تا پایان "
                                        "اعتبار باقی مانده است.\n\n"
                                        "می‌توانید سرویس خود را تمدید کنید."
                                    )

                                else:
                                    message = (
                                        "🟡 <b>یادآوری انقضای سرویس</b>\n\n"
                                        f"🧾 سفارش: #{oid}\n"
                                        f"🔌 سرویس: {service.upper()}\n"
                                        f"⏳ {days_left} روز تا پایان "
                                        "اعتبار باقی مانده است."
                                    )

                            else:

                                if warning_type == "expire_1d":
                                    message = (
                                        "🔴 <b>Important Expiry Warning</b>\n\n"
                                        f"🧾 Order: #{oid}\n"
                                        f"🔌 Service: {service.upper()}\n"
                                        "⏳ Less than 1 day remains "
                                        "before expiration.\n\n"
                                        "Please renew your service."
                                    )

                                elif warning_type == "expire_3d":
                                    message = (
                                        "🟠 <b>Service Expiry Warning</b>\n\n"
                                        f"🧾 Order: #{oid}\n"
                                        f"🔌 Service: {service.upper()}\n"
                                        f"⏳ About {days_left} days remain "
                                        "before expiration."
                                    )

                                else:
                                    message = (
                                        "🟡 <b>Service Expiry Reminder</b>\n\n"
                                        f"🧾 Order: #{oid}\n"
                                        f"🔌 Service: {service.upper()}\n"
                                        f"⏳ {days_left} days remain "
                                        "before expiration."
                                    )

                            try:
                                await context.bot.send_message(
                                    chat_id=uid,
                                    text=message,
                                    parse_mode="HTML",
                                    reply_markup=menu(uid),
                                )

                                await mark_sent(
                                    oid,
                                    warning_type,
                                )

                                print(
                                    f"✅ EXPIRY WARNING SENT "
                                    f"user={uid} order={oid} "
                                    f"type={warning_type}"
                                )

                            except Exception as exc:
                                print(
                                    f"⚠️ EXPIRY MESSAGE FAILED "
                                    f"user={uid} order={oid}: {exc!r}"
                                )

                # =================================================
                # VOLUME
                # =================================================

                data_limit = info.get("data_limit")
                used_traffic = info.get("used_traffic")

                try:
                    data_limit = int(float(data_limit or 0))
                except (ValueError, TypeError):
                    data_limit = 0

                try:
                    used_traffic = int(float(used_traffic or 0))
                except (ValueError, TypeError):
                    used_traffic = 0

                # 0 = unlimited
                if data_limit <= 0:
                    continue

                used_traffic = max(0, used_traffic)

                usage_percent = (
                    used_traffic / data_limit
                ) * 100

                if usage_percent >= 90:
                    volume_warning = "volume_90"

                elif usage_percent >= 80:
                    volume_warning = "volume_80"

                elif usage_percent >= 70:
                    volume_warning = "volume_70"

                else:
                    volume_warning = None

                if not volume_warning:
                    continue

                if await already_sent(
                    oid,
                    volume_warning,
                ):
                    continue

                usage_display = min(
                    100,
                    usage_percent,
                )

                if lang(uid) == "fa":

                    if volume_warning == "volume_90":
                        message = (
                            "🔴 <b>هشدار مصرف حجم</b>\n\n"
                            f"🧾 سفارش: #{oid}\n"
                            f"🔌 سرویس: {service.upper()}\n"
                            f"📊 میزان مصرف: "
                            f"<b>{usage_display:.0f}%</b>\n\n"
                            "بیش از ۹۰٪ حجم سرویس شما مصرف شده است.\n"
                            "برای جلوگیری از قطع سرویس، "
                            "تمدید را در نظر بگیرید."
                        )

                    elif volume_warning == "volume_80":
                        message = (
                            "🟠 <b>هشدار مصرف حجم</b>\n\n"
                            f"🧾 سفارش: #{oid}\n"
                            f"🔌 سرویس: {service.upper()}\n"
                            f"📊 میزان مصرف: "
                            f"<b>{usage_display:.0f}%</b>\n\n"
                            "بخش زیادی از حجم سرویس شما مصرف شده است."
                        )

                    else:
                        message = (
                            "🟡 <b>یادآوری مصرف حجم</b>\n\n"
                            f"🧾 سفارش: #{oid}\n"
                            f"🔌 سرویس: {service.upper()}\n"
                            f"📊 میزان مصرف: "
                            f"<b>{usage_display:.0f}%</b>\n\n"
                            "حدود ۷۰٪ از حجم سرویس شما مصرف شده است."
                        )

                else:

                    if volume_warning == "volume_90":
                        message = (
                            "🔴 <b>Traffic Usage Warning</b>\n\n"
                            f"🧾 Order: #{oid}\n"
                            f"🔌 Service: {service.upper()}\n"
                            f"📊 Usage: "
                            f"<b>{usage_display:.0f}%</b>\n\n"
                            "More than 90% of your traffic has been used."
                        )

                    elif volume_warning == "volume_80":
                        message = (
                            "🟠 <b>Traffic Usage Warning</b>\n\n"
                            f"🧾 Order: #{oid}\n"
                            f"🔌 Service: {service.upper()}\n"
                            f"📊 Usage: "
                            f"<b>{usage_display:.0f}%</b>\n\n"
                            "A large portion of your traffic has been used."
                        )

                    else:
                        message = (
                            "🟡 <b>Traffic Usage Reminder</b>\n\n"
                            f"🧾 Order: #{oid}\n"
                            f"🔌 Service: {service.upper()}\n"
                            f"📊 Usage: "
                            f"<b>{usage_display:.0f}%</b>\n\n"
                            "About 70% of your traffic has been used."
                        )

                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=message,
                        parse_mode="HTML",
                        reply_markup=menu(uid),
                    )

                    await mark_sent(
                        oid,
                        volume_warning,
                    )

                    print(
                        f"✅ VOLUME WARNING SENT "
                        f"user={uid} order={oid} "
                        f"type={volume_warning} "
                        f"usage={usage_display:.1f}%"
                    )

                except Exception as exc:
                    print(
                        f"⚠️ VOLUME MESSAGE FAILED "
                        f"user={uid} order={oid}: {exc!r}"
                    )

            except Exception as exc:
                print(
                    f"⚠️ AUTO SERVICE CHECK FAILED "
                    f"order={row['id']}: {exc!r}"
                )

    finally:
        conn.close()


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
    db.init_mission_db()
    print("✅ Mission database initialized")

    print("✅ Database initialized")

    app = Application.builder().token(BOT_TOKEN).build()

    # Automatic service expiry / volume warnings
    app.job_queue.run_repeating(
        automatic_expiry_warning_job,
        interval=300,
        first=30,
    )

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
            CallbackQueryHandler(custom_start, pattern=r"^custom:(gold|silver|bronze)$")
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
                        r"⚙️ تنظیمات|📚 راهنما|🛒 خرید سرویس|🔄 تمدید سرویس|🟣 سفارش‌های فعال|"
                        r"🏠 Main Menu|🛒 Shop|💰 Wallet|"
                        r"👤 Account|👥 Referrals|📞 Support|"
                        r"⚙️ Settings|📚 Guide|🛒 Buy Service|🔄 Renew Service|🟣 Active Services)$"
                    ),
                    coupon_input,
                ),
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
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern=r"^start_broadcast$")],
        states={BROADCAST_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_receive)]},
        fallbacks=[CommandHandler("cancelbroadcast", broadcast_cancel)],
        allow_reentry=True,
    )

    app.add_handler(deposit_conv)
    app.add_handler(broadcast_conv)
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

    # Support callbacks
    app.add_handler(CallbackQueryHandler(support_faq_callback, pattern=r"^support_faq:\d+$"))
    app.add_handler(CallbackQueryHandler(support_back_callback, pattern=r"^support_back$"))
    app.add_handler(CallbackQueryHandler(support_human_callback, pattern=r"^support_human$"))
    app.add_handler(CallbackQueryHandler(support_ai_callback, pattern=r"^support_ai$"))
    app.add_handler(
        CallbackQueryHandler(
            alpha_coin_callback,
            pattern=r"^alpha_coin$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            alpha_coin_history_callback,
            pattern=r"^alpha_coin_history$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            missions_callback,
            pattern=r"^missions$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            mission_stage_callback,
            pattern=r"^mission_stage:\d+$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            mission_claim_callback,
            pattern=r"^mission_claim:\d+$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            alpha_coin_history_callback,
            pattern=r"^alpha_coin_history$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            missions_callback,
            pattern=r"^missions$",
        )
    )

    app.add_handler(MessageHandler(filters.Regex(r"^(🛒 خرید سرویس|🔄 تمدید سرویس|🎁 تست رایگان|💰 کیف پول|👥 زیرمجموعه‌گیری|🟣 سفارش‌های فعال|📞 پشتیبانی|⚙️ تنظیمات|📚 راهنما|🛒 Buy Service|🔄 Renew Service|🎁 Free Trial|💰 Wallet|👥 Referrals|🟣 Active Services|📞 Support|⚙️ Settings|📚 Guide)$"), end_ai_mode), group=-1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_support_message), group=1)

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

    app.add_handler(CallbackQueryHandler(shop_service, pattern=r"^shop_service:(gold|silver|bronze)$"))
    app.add_handler(CallbackQueryHandler(trial_service, pattern=r"^trial:(gold|silver|bronze)$"))
    app.add_handler(CallbackQueryHandler(active_order_detail, pattern=r"^active_order:\d+$"))
    app.add_handler(CallbackQueryHandler(renew_confirm, pattern=r"^renew:\d+$"))
    app.add_handler(CallbackQueryHandler(renew_execute, pattern=r"^renew_confirm:\d+$"))
    app.add_handler(CallbackQueryHandler(renew_cancel, pattern=r"^renew_cancel$"))

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
            filters.Regex(r"^(🔄 تمدید سرویس|🔄 Renew Service)$"),
            renew_service,
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
            filters.Regex(r"^(👤 پروفایل|👤 Profile)$"),
            account,
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
            filters.Regex(r"^(🟣 سفارش‌های فعال|🟣 Active Services)$"),
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

    app.add_handler(CallbackQueryHandler(guide_app, pattern=r"^guide_app:(v2box|happ|hiddify|streisand)$"))

    print("🌹 AlphaShop Pro Bot Running...")


    app.add_handler(CommandHandler("copytest", copytest))
    app.run_polling(
        drop_pending_updates=True,
        close_loop=False,
        stop_signals=None,
    )


if __name__ == "__main__":
    run_bot()
