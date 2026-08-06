AlphaShopPro - Coupon Fix
=========================

این بسته برای رفع مشکل کد تخفیف است.

فایل‌ها:
1. database_patch.py
   توابع جدید:
   - has_coupon_used
   - use_coupon
   - consume_coupon

2. bot_coupon_input.py
   تابع جدید coupon_input

مهم:
این بسته کد کامل bot.py و database.py نیست؛ فقط قسمت‌های لازم برای تغییر است.

مراحل:
1. از bot.py و database.py بکاپ بگیر.
2. تابع coupon_input فعلی را در bot.py پیدا کن و با محتوای bot_coupon_input.py جایگزین کن.
3. توابع database_patch.py را در database.py اضافه کن.
4. برای اینکه کد فقط بعد از خرید موفق مصرف شود، در مسیر خرید موفق باید:
       db.consume_coupon(code, uid)
   اجرا شود.
   کد باید بعد از موفق شدن سفارش و قبل/همزمان با نهایی‌کردن سفارش اجرا شود.
5. سپس:
       python -m py_compile bot.py database.py
   اگر خطایی نداد:
       python bot.py

توجه:
اگر نسخه فعلی bot.py شما با نسخه‌ای که این تغییر برای آن نوشته شده متفاوت است، قبل از جایگزینی بخش‌های خرید، نسخه فعلی را بررسی کن.