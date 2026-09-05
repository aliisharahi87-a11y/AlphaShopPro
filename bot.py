import os, asyncio, aiohttp, asyncpg
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

load_dotenv()
TOKEN=os.getenv("BOT_TOKEN","")
DSN=os.getenv("DATABASE_URL","")
ADMINS={int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()}
CHANNEL=os.getenv("REQUIRED_CHANNEL","@alphashopss")
SUPPORT=os.getenv("SUPPORT_USERNAME","@AlphaShopSupport")
CARD=os.getenv("CARD_NUMBER","")
HOLDER=os.getenv("CARD_HOLDER","")
RATE=int(os.getenv("CUSTOM_PRICE_PER_GB","4000"))
REF=int(os.getenv("REFERRAL_PERCENT","10"))
PANEL=os.getenv("PANEL_URL","").rstrip("/")
PANEL_USER=os.getenv("PANEL_USERNAME","")
PANEL_PASS=os.getenv("PANEL_PASSWORD","")
API_KEY=os.getenv("PANEL_API_KEY","")
API_TOKEN=os.getenv("PANEL_API_TOKEN","")
CREATE_PATH=os.getenv("PANEL_API_CREATE_USER_PATH","")

db=None
router=Router()

class Deposit(StatesGroup):
    amount=State()
    receipt=State()

class Custom(StatesGroup):
    gb=State()

def menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛒 خرید سرویس"),KeyboardButton(text="💰 کیف پول")],
        [KeyboardButton(text="👥 زیرمجموعه‌گیری"),KeyboardButton(text="📦 سفارش‌های من")],
        [KeyboardButton(text="📞 پشتیبانی"),KeyboardButton(text="ℹ️ حساب من")]
    ],resize_keyboard=True)

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 شارژهای در انتظار",callback_data="adm_deps")],
        [InlineKeyboardButton(text="📦 پلن‌ها",callback_data="adm_plans")],
        [InlineKeyboardButton(text="📊 آمار",callback_data="adm_stats")]
    ])

async def init_db():
    global db
    db=await asyncpg.create_pool(DSN,min_size=1,max_size=8)
    async with db.acquire() as c:
        await c.execute("""
        CREATE TABLE IF NOT EXISTS users(
          id BIGINT PRIMARY KEY, username TEXT, first_name TEXT,
          balance BIGINT NOT NULL DEFAULT 0, referrer_id BIGINT,
          created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS products(
          id SERIAL PRIMARY KEY,title TEXT,gb INTEGER,price BIGINT,
          unlimited BOOLEAN DEFAULT FALSE,active BOOLEAN DEFAULT TRUE,sort_order INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS deposits(
          id BIGSERIAL PRIMARY KEY,user_id BIGINT REFERENCES users(id),
          amount BIGINT,receipt TEXT,status TEXT DEFAULT 'pending',
          created_at TIMESTAMPTZ DEFAULT NOW(),reviewed_at TIMESTAMPTZ
        );
        CREATE TABLE IF NOT EXISTS transactions(
          id BIGSERIAL PRIMARY KEY,user_id BIGINT REFERENCES users(id),
          kind TEXT,amount BIGINT,description TEXT,created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS orders(
          id BIGSERIAL PRIMARY KEY,user_id BIGINT REFERENCES users(id),
          product_id INTEGER,gb INTEGER,price BIGINT,status TEXT DEFAULT 'pending',
          panel_username TEXT,config TEXT,created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """)
        if await c.fetchval("SELECT COUNT(*) FROM products")==0:
            await c.executemany(
                "INSERT INTO products(title,gb,price,unlimited,active,sort_order) VALUES($1,$2,$3,$4,$5,$6)",
                [("۵ گیگ",5,20000,False,True,1),("۱۰ گیگ",10,40000,False,True,2),
                 ("۲۰ گیگ",20,80000,False,True,3),("۴۰ گیگ",40,160000,False,True,4),
                 ("نامحدود",None,0,True,False,5)])

async def user(uid):
    return await db.fetchrow("SELECT * FROM users WHERE id=$1",uid)

async def ensure(m,ref=None):
    await db.execute("""INSERT INTO users(id,username,first_name,referrer_id)
    VALUES($1,$2,$3,$4) ON CONFLICT(id) DO UPDATE
    SET username=EXCLUDED.username,first_name=EXCLUDED.first_name""",
    m.from_user.id,m.from_user.username,m.from_user.first_name,ref)

async def channel_ok(bot,uid):
    if not CHANNEL:return True
    try:return (await bot.get_chat_member(CHANNEL,uid)).status in ("member","administrator","creator")
    except:return False

async def panel_create(username,gb,unlimited=False):
    if not PANEL or not CREATE_PATH:return {"ok":False,"error":"API_NOT_CONFIGURED"}
    headers={"Accept":"application/json","Content-Type":"application/json"}
    if API_TOKEN:headers["Authorization"]="Bearer "+API_TOKEN
    elif API_KEY:headers["X-API-Key"]=API_KEY
    auth=aiohttp.BasicAuth(PANEL_USER,PANEL_PASS) if PANEL_USER and PANEL_PASS else None
    payload={"username":username,"traffic_gb":gb,"unlimited":unlimited}
    try:
        async with aiohttp.ClientSession(auth=auth) as s:
            async with s.post(PANEL+"/"+CREATE_PATH.lstrip("/"),json=payload,headers=headers,timeout=30) as r:
                data=await r.json(content_type=None)
                return {"ok":r.status<400,"data":data,"status":r.status}
    except Exception as e:return {"ok":False,"error":str(e)}

@router.message(F.text=="/start")
async def start(m:Message,state:FSMContext,bot:Bot):
    await state.clear()
    parts=m.text.split(maxsplit=1); ref=None
    if len(parts)==2 and parts[1].isdigit() and int(parts[1])!=m.from_user.id:ref=int(parts[1])
    await ensure(m,ref)
    if not await channel_ok(bot,m.from_user.id):
        k=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 عضویت در کانال",url="https://t.me/"+CHANNEL.lstrip("@"))],
            [InlineKeyboardButton(text="✅ بررسی عضویت",callback_data="check_channel")]])
        await m.answer("🌷 سلام و خوش اومدی!\n\nبرای استفاده از امکانات آلفا شاپ، لطفاً ابتدا در کانال ما عضو شو. ❤️",reply_markup=k);return
    await m.answer(f"🌷 سلام {m.from_user.first_name or ''} عزیز!\n\nبه آلفا شاپ خوش اومدی. ❤️\nاز منوی زیر می‌تونی سرویس بخری، کیف پولت رو شارژ کنی و سفارش‌هات رو ببینی.",reply_markup=menu())

@router.callback_query(F.data=="check_channel")
async def check(c:CallbackQuery,bot:Bot):
    if await channel_ok(bot,c.from_user.id):
        await c.message.edit_text("✅ عضویتت با موفقیت تأیید شد. ❤️")
        await c.message.answer("منوی اصلی:",reply_markup=menu())
    else:await c.answer("❌ هنوز عضو کانال نشده‌ای.",show_alert=True)

@router.message(F.text=="💰 کیف پول")
async def wallet(m:Message):
    u=await user(m.from_user.id)
    k=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ افزایش موجودی",callback_data="deposit")]])
    await m.answer(f"💰 موجودی کیف پول شما: {u['balance']:,} تومان\n\nمی‌تونی با این موجودی سرویس موردنظرت رو تهیه کنی. ❤️",reply_markup=k)

@router.callback_query(F.data=="deposit")
async def deposit(c:CallbackQuery,state:FSMContext):
    await state.set_state(Deposit.amount)
    await c.message.answer("💳 افزایش موجودی کیف پول\n\nمبلغ موردنظر را به تومان وارد کن.\nمثال: 100000")

@router.message(Deposit.amount)
async def dep_amount(m:Message,state:FSMContext):
    try:
        n=int(m.text.replace(",","").replace("٬","").strip())
        if n<1000:raise ValueError
    except:
        await m.answer("❌ لطفاً مبلغ معتبر و حداقل ۱,۰۰۰ تومان وارد کن.");return
    await state.update_data(amount=n);await state.set_state(Deposit.receipt)
    await m.answer(f"💳 مبلغ شارژ: {n:,} تومان\n\nشماره کارت:\n{CARD or 'تنظیم نشده'}\n\nبه نام:\n{HOLDER or 'تنظیم نشده'}\n\nبعد از انتقال وجه، تصویر رسید را همین‌جا ارسال کن. 📸\nپس از تأیید ادمین، مبلغ به کیف پولت اضافه می‌شود. ❤️")

@router.message(Deposit.receipt,F.photo)
async def receipt(m:Message,state:FSMContext,bot:Bot):
    d=await state.get_data()
    did=await db.fetchval("INSERT INTO deposits(user_id,amount,receipt) VALUES($1,$2,$3) RETURNING id",m.from_user.id,d["amount"],m.photo[-1].file_id)
    await state.clear()
    await m.answer(f"✅ رسید شما ثبت شد.\n\nشماره درخواست: #{did}\nپس از بررسی ادمین نتیجه به شما اطلاع داده می‌شود. ❤️")
    k=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ تأیید",callback_data=f"review:1:{did}"),InlineKeyboardButton(text="❌ رد",callback_data=f"review:0:{did}")]])
    for a in ADMINS:
        await bot.send_photo(a,m.photo[-1].file_id,caption=f"💳 درخواست شارژ #{did}\n👤 {m.from_user.full_name}\n🆔 {m.from_user.id}\n💰 {d['amount']:,} تومان",reply_markup=k)

@router.message(Deposit.receipt)
async def bad_receipt(m):await m.answer("📸 لطفاً تصویر رسید پرداخت را ارسال کن.")

@router.message(F.text=="🛒 خرید سرویس")
async def shop(m:Message):
    ps=await db.fetch("SELECT * FROM products WHERE active=true ORDER BY sort_order,id")
    rows=[]
    for p in ps:
        rows.append([InlineKeyboardButton(text=f"{'♾️' if p['unlimited'] else '📦'} {p['title']} — {p['price']:,} تومان",callback_data=f"buy:{p['id']}")])
    rows.append([InlineKeyboardButton(text="✏️ حجم دلخواه",callback_data="custom")])
    await m.answer("🛒 انتخاب سرویس\n\nیکی از گزینه‌های زیر را انتخاب کن. 🌷",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data=="custom")
async def custom(c,state):
    await state.set_state(Custom.gb)
    await c.message.answer(f"✏️ حجم دلخواه\n\nحجم را به گیگابایت وارد کن.\n💰 قیمت هر گیگابایت: {RATE:,} تومان")

@router.message(Custom.gb)
async def custom_value(m,state):
    try:
        gb=int(m.text.strip())
        if gb<1 or gb>100000:raise ValueError
    except:
        await m.answer("❌ لطفاً یک عدد معتبر وارد کن؛ مثلاً 25");return
    await state.clear()
    await buy_now(m,m.from_user.id,None,gb,gb*RATE,f"{gb} گیگ سفارشی")

@router.callback_query(F.data.startswith("buy:"))
async def buy(c):
    p=await db.fetchrow("SELECT * FROM products WHERE id=$1 AND active=true",int(c.data.split(":")[1]))
    if not p:return await c.answer("❌ این پلن فعال نیست.",show_alert=True)
    await buy_now(c.message,c.from_user.id,p["id"],p["gb"],p["price"],p["title"])

async def buy_now(m,uid,pid,gb,price,title):
    u=await user(uid)
    if u["balance"]<price:
        k=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💰 افزایش موجودی",callback_data="deposit")]])
        await m.answer(f"💳 موجودی کافی نیست.\n\n📦 {title}\n💰 قیمت: {price:,} تومان\n💵 موجودی فعلی: {u['balance']:,} تومان\n➕ مبلغ موردنیاز: {price-u['balance']:,} تومان",reply_markup=k);return
    async with db.acquire() as c:
        async with c.transaction():
            locked=await c.fetchrow("SELECT balance,referrer_id FROM users WHERE id=$1 FOR UPDATE",uid)
            if locked["balance"]<price:return await m.answer("❌ موجودی برای این خرید کافی نیست.")
            oid=await c.fetchval("INSERT INTO orders(user_id,product_id,gb,price) VALUES($1,$2,$3,$4) RETURNING id",uid,pid,gb,price)
            await c.execute("UPDATE users SET balance=balance-$1 WHERE id=$2",price,uid)
            await c.execute("INSERT INTO transactions(user_id,kind,amount,description) VALUES($1,'purchase',$2,$3)",uid,-price,f"خرید {title} #{oid}")
    result=await panel_create(f"alpha_{uid}_{oid}",gb,gb is None)
    if not result["ok"]:
        await db.execute("UPDATE users SET balance=balance+$1 WHERE id=$2",price,uid)
        await db.execute("INSERT INTO transactions(user_id,kind,amount,description) VALUES($1,'refund',$2,$3)",uid,price,f"بازگشت سفارش #{oid}")
        await db.execute("UPDATE orders SET status='panel_pending' WHERE id=$1",oid)
        await m.answer("⚠️ اتصال پنل فروش هنوز تنظیم نشده یا پاسخ موفقی دریافت نکرده است. مبلغ سفارش به کیف پولت برگشت داده شد. ❤️");return
    data=result.get("data") or {}
    pu=data.get("username",f"alpha_{uid}_{oid}")
    conf=data.get("config") or data.get("subscription") or data.get("link") or ""
    await db.execute("UPDATE orders SET status='completed',panel_username=$1,config=$2 WHERE id=$3",pu,str(conf),oid)
    referrer=u["referrer_id"]
    if referrer and REF>0:
        bonus=price*REF//100
        if bonus:
            await db.execute("UPDATE users SET balance=balance+$1 WHERE id=$2",bonus,referrer)
            await db.execute("INSERT INTO transactions(user_id,kind,amount,description) VALUES($1,'referral',$2,$3)",referrer,bonus,f"پاداش سفارش #{oid}")
            try:await m.bot.send_message(referrer,f"🎁 پاداش زیرمجموعه‌گیری\n\nاز خرید زیرمجموعه‌ات {bonus:,} تومان پاداش به کیف پولت اضافه شد. ❤️")
            except:pass
    await m.answer(f"🎉 سفارش شما با موفقیت تکمیل شد!\n\n📦 سرویس: {title}\n💰 مبلغ: {price:,} تومان\n🧾 شماره سفارش: #{oid}\n\n👤 نام کاربری: {pu}\n🔗 کانفیگ/لینک اشتراک:\n{conf or 'اطلاعات کانفیگ از پنل دریافت نشد.'}\n\nممنون که آلفا شاپ را انتخاب کردی. ❤️")

@router.message(F.text=="👥 زیرمجموعه‌گیری")
async def referrals(m:Message,bot:Bot):
    me=await bot.get_me()
    n=await db.fetchval("SELECT COUNT(*) FROM users WHERE referrer_id=$1",m.from_user.id)
    await m.answer(f"👥 زیرمجموعه‌گیری آلفا شاپ\n\n🎁 پاداش: {REF}% از خرید زیرمجموعه\n👤 تعداد زیرمجموعه‌ها: {n}\n\n🔗 لینک اختصاصی شما:\nhttps://t.me/{me.username}?start={m.from_user.id}\n\nلینک را برای دوستانت بفرست. ❤️")

@router.message(F.text=="📞 پشتیبانی")
async def support(m):await m.answer(f"📞 پشتیبانی آلفا شاپ:\n{SUPPORT}\n\nبا خیال راحت پیام بده. ❤️")

@router.message(F.text=="ℹ️ حساب من")
async def account(m):
    u=await user(m.from_user.id);await m.answer(f"👤 حساب شما\n\n🆔 {m.from_user.id}\n💰 موجودی: {u['balance']:,} تومان")

@router.message(F.text=="📦 سفارش‌های من")
async def orders(m):
    rs=await db.fetch("SELECT * FROM orders WHERE user_id=$1 ORDER BY id DESC LIMIT 15",m.from_user.id)
    if not rs:return await m.answer("📦 هنوز سفارشی ثبت نکرده‌ای.")
    await m.answer("📦 آخرین سفارش‌ها:\n\n"+"\n".join(f"🧾 #{x['id']} | {x['gb'] or 'نامحدود'} | {x['price']:,} تومان | {x['status']}" for x in rs))

@router.message(F.text=="/admin")
async def admin(m):
    if m.from_user.id in ADMINS:await m.answer("🛠 پنل مدیریت آلفا شاپ\n\nبخش موردنظر را انتخاب کن:",reply_markup=admin_menu())

@router.callback_query(F.data=="adm_stats")
async def adm_stats(c):
    if c.from_user.id not in ADMINS:return
    s=await db.fetchrow("SELECT (SELECT COUNT(*) FROM users) users,(SELECT COALESCE(SUM(balance),0) FROM users) bal,(SELECT COUNT(*) FROM orders) orders,(SELECT COUNT(*) FROM deposits WHERE status='pending') pending")
    await c.message.answer(f"📊 آمار\n\n👤 کاربران: {s['users']:,}\n💰 مجموع موجودی: {s['bal']:,} تومان\n🛒 سفارش‌ها: {s['orders']:,}\n💳 شارژهای در انتظار: {s['pending']:,}")

@router.callback_query(F.data=="adm_deps")
async def adm_deps(c):
    if c.from_user.id not in ADMINS:return
    rs=await db.fetch("SELECT d.*,u.username,u.first_name FROM deposits d JOIN users u ON u.id=d.user_id WHERE d.status='pending' ORDER BY d.id")
    if not rs:return await c.message.answer("✅ درخواست شارژ در انتظاری وجود ندارد.")
    for d in rs:
        k=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ تأیید",callback_data=f"review:1:{d['id']}"),InlineKeyboardButton(text="❌ رد",callback_data=f"review:0:{d['id']}")]])
        await c.message.answer(f"💳 درخواست #{d['id']}\n👤 {d['first_name'] or ''} @{d['username'] or '-'}\n🆔 {d['user_id']}\n💰 {d['amount']:,} تومان",reply_markup=k)

@router.callback_query(F.data.startswith("review:"))
async def review(c):
    if c.from_user.id not in ADMINS:return
    _,ok,did=c.data.split(":")
    async with db.acquire() as x:
        async with x.transaction():
            d=await x.fetchrow("SELECT * FROM deposits WHERE id=$1 FOR UPDATE",int(did))
            if not d or d["status"]!="pending":return await c.answer("این درخواست قبلاً بررسی شده.",show_alert=True)
            await x.execute("UPDATE deposits SET status=$1,reviewed_at=NOW() WHERE id=$2",("approved" if ok=="1" else "rejected"),int(did))
            if ok=="1":
                await x.execute("UPDATE users SET balance=balance+$1 WHERE id=$2",d["amount"],d["user_id"])
                await x.execute("INSERT INTO transactions(user_id,kind,amount,description) VALUES($1,'deposit',$2,$3)",d["user_id"],d["amount"],f"تأیید شارژ #{did}")
    if ok=="1":
        await c.message.answer(f"✅ شارژ #{did} تأیید شد.")
        await c.bot.send_message(d["user_id"],f"🎉 شارژ شما تأیید شد و {d['amount']:,} تومان به کیف پولت اضافه شد. ❤️")
    else:
        await c.message.answer(f"❌ شارژ #{did} رد شد.")
        await c.bot.send_message(d["user_id"],f"❌ درخواست شارژ #{did} رد شد.\nبرای پیگیری با پشتیبانی تماس بگیر.")

@router.callback_query(F.data=="adm_plans")
async def adm_plans(c):
    if c.from_user.id not in ADMINS:return
    rs=await db.fetch("SELECT * FROM products ORDER BY sort_order,id")
    await c.message.answer("📦 مدیریت پلن‌ها\n\n"+"\n".join(f"#{x['id']} | {x['title']} | {x['price']:,} تومان | {'فعال' if x['active'] else 'غیرفعال'}" for x in rs)+
                           "\n\nدستورات:\n/setprice ID PRICE\n/activate ID\n/deactivate ID")

@router.message(F.text.startswith("/setprice "))
async def setprice(m):
    if m.from_user.id not in ADMINS:return
    try:
        _,pid,price=m.text.split()
        await db.execute("UPDATE products SET price=$1 WHERE id=$2",int(price),int(pid))
        await m.answer("✅ قیمت پلن با موفقیت تغییر کرد.")
    except:await m.answer("فرمت صحیح: /setprice ID PRICE")

@router.message(F.text.startswith("/activate "))
async def activate(m):
    if m.from_user.id not in ADMINS:return
    try:await db.execute("UPDATE products SET active=true WHERE id=$1",int(m.text.split()[1]));await m.answer("✅ پلن فعال شد.")
    except:await m.answer("فرمت صحیح: /activate ID")

@router.message(F.text.startswith("/deactivate "))
async def deactivate(m):
    if m.from_user.id not in ADMINS:
        return
    try:
        await db.execute("UPDATE products SET active=false WHERE id=$1", int(m.text.split()[1]))
        await m.answer("✅ پلن غیرفعال شد.")
    except:
        await m.answer("فرمت صحیح: /deactivate ID")

async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")
    if not DSN:
        raise RuntimeError("DATABASE_URL is missing")
    await init_db()
    bot=Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp=Dispatcher()
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()

def run_bot():
    asyncio.run(main())

if __name__=="__main__":
    asyncio.run(main())
