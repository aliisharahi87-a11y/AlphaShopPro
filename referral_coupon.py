REFERRAL_PERCENT = 5

def calculate_discount(price, coupon):
    if not coupon:
        return price, 0
    discount = int(price * coupon["percent"] / 100) if coupon["percent"] else int(coupon["amount"])
    discount = max(0, min(discount, price))
    return price - discount, discount

def referral_message(user, code, english=False):
    identity = f"@{user.username}" if getattr(user, "username", None) else f"ID: {user.id}"
    if english:
        return (f"🎉 <b>New referral!</b>\n\n"
                f"👤 <b>{identity}</b> joined using your personal referral link.\n\n"
                f"🎁 Your reward is a <b>one-time 5% discount</b>.\n\n"
                f"🏷 Code: <code>{code}</code>\n\n"
                "The code is consumed only after a successful purchase. ❤️")
    return (f"🎉 <b>زیرمجموعه جدید با موفقیت ثبت شد!</b>\n\n"
            f"👤 شخص <b>{identity}</b> با لینک اختصاصی شما وارد بات شد.\n\n"
            f"🎁 به پاس دعوت شما، یک <b>کد تخفیف ۵٪ یک‌بارمصرف</b> برایتان ساخته شد.\n\n"
            f"🏷 کد تخفیف شما: <code>{code}</code>\n\n"
            "این کد فقط یک‌بار قابل استفاده است و تنها پس از خرید موفق مصرف می‌شود. ❤️")

def purchase_discount_message(original, discount, final, code=None, english=False):
    if english:
        s = f"💰 Original price: <b>{original:,} تومان</b>\n"
        if code:
            s += f"🎟 Coupon: <code>{code}</code>\n💸 Discount: <b>{discount:,} تومان</b>\n"
        return s + f"💵 Final price: <b>{final:,} تومان</b>"
    s = f"💰 مبلغ اصلی: <b>{original:,} تومان</b>\n"
    if code:
        s += f"🎟 کد تخفیف: <code>{code}</code>\n💸 مقدار کم‌شده: <b>{discount:,} تومان</b>\n"
    return s + f"💵 مبلغ نهایی: <b>{final:,} تومان</b>"
