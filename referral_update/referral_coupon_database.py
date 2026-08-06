import sqlite3
import time
from threading import RLock

DB_PATH = "alphashop.db"
LOCK = RLock()

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_referral_coupon_tables():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS coupons(
            code TEXT PRIMARY KEY, percent INTEGER DEFAULT 0,
            amount INTEGER DEFAULT 0, max_uses INTEGER DEFAULT 0,
            used INTEGER DEFAULT 0, active INTEGER DEFAULT 1)""")
        c.execute("""CREATE TABLE IF NOT EXISTS coupon_uses(
            code TEXT NOT NULL, user_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL, PRIMARY KEY(code,user_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS referral_rewards(
            referred_user_id INTEGER PRIMARY KEY, referrer_id INTEGER NOT NULL,
            coupon_code TEXT NOT NULL, created_at INTEGER NOT NULL)""")

def coupon_available(code, uid):
    code = code.strip().upper()
    with conn() as c:
        cp = c.execute(
            "SELECT * FROM coupons WHERE code=? AND active=1", (code,)
        ).fetchone()
        if not cp:
            return None
        if cp["max_uses"] and cp["used"] >= cp["max_uses"]:
            return None
        if c.execute(
            "SELECT 1 FROM coupon_uses WHERE code=? AND user_id=?",
            (code, uid)
        ).fetchone():
            return None
        return cp

def consume_coupon(code, uid):
    code = code.strip().upper()
    with LOCK, conn() as c:
        cp = c.execute(
            "SELECT * FROM coupons WHERE code=? AND active=1", (code,)
        ).fetchone()
        if not cp or (cp["max_uses"] and cp["used"] >= cp["max_uses"]):
            return False
        if c.execute(
            "SELECT 1 FROM coupon_uses WHERE code=? AND user_id=?",
            (code, uid)
        ).fetchone():
            return False
        c.execute(
            "INSERT INTO coupon_uses(code,user_id,created_at) VALUES(?,?,?)",
            (code, uid, int(time.time()))
        )
        c.execute("UPDATE coupons SET used=used+1 WHERE code=?", (code,))
        return True

def create_referral_reward(referred_uid, referrer_uid):
    if not referrer_uid or referred_uid == referrer_uid:
        return None
    with LOCK, conn() as c:
        old = c.execute(
            "SELECT coupon_code FROM referral_rewards WHERE referred_user_id=?",
            (referred_uid,)
        ).fetchone()
        if old:
            return old["coupon_code"]
        code = f"REF5_{referrer_uid}_{referred_uid}_{int(time.time())}"
        c.execute(
            """INSERT INTO coupons(code,percent,amount,max_uses,used,active)
               VALUES(?,5,0,1,0,1)""", (code,)
        )
        c.execute(
            """INSERT INTO referral_rewards
               (referred_user_id,referrer_id,coupon_code,created_at)
               VALUES(?,?,?,?)""",
            (referred_uid, referrer_uid, code, int(time.time()))
        )
        return code
