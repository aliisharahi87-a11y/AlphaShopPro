این بسته دو ماژول مستقل برای اضافه‌کردن به نسخه فعلی AlphaShop است.

۱) referral_coupon_database.py
- ساخت جداول coupon_uses و referral_rewards
- اعتبارسنجی کد بدون مصرف‌کردن آن
- مصرف کد فقط بعد از خرید موفق
- ساخت کد ۵٪ و یک‌بارمصرف برای هر دعوت موفق

۲) referral_coupon.py
- محاسبه تخفیف
- پیام کامل فارسی/انگلیسی زیرمجموعه
- پیام نمایش مبلغ اصلی، مقدار تخفیف و مبلغ نهایی

اتصال به نسخه فعلی:
در /start، پس از تشخیص کاربر جدید و referrer معتبر:
code = create_referral_reward(new_user_id, referrer_id)
سپس referral_message(user, code, english=...) را برای دعوت‌کننده ارسال کنید.

هنگام ورود کد:
coupon = coupon_available(code, user_id)
و coupon را در context.user_data نگه دارید؛ هنوز consume نکنید.

پس از موفقیت کامل خرید:
final_price, discount = calculate_discount(original_price, coupon)
و بعد از موفقیت سفارش:
consume_coupon(coupon["code"], user_id)

برای نمایش قیمت از purchase_discount_message(...) استفاده کنید.
