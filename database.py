import sqlite3
import threading
import time

from config import DATABASE_FILE

LOCK = threading.Lock()


def conn():
    c = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            referrer INTEGER,
            lang TEXT DEFAULT 'fa',
            blocked INTEGER DEFAULT 0,
            created_at INTEGER,
            trial_used INTEGER DEFAULT 0,
            trial_gold_used INTEGER DEFAULT 0,
            trial_silver_used INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS plans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_fa TEXT NOT NULL,
            title_en TEXT NOT NULL,
            gb INTEGER,
            price INTEGER DEFAULT 0,
            unlimited INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            service TEXT DEFAULT 'gold'
        );

        CREATE TABLE IF NOT EXISTS deposits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            receipt TEXT,
            status TEXT DEFAULT 'pending',
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_id INTEGER,
            gb INTEGER,
            price INTEGER,
            status TEXT DEFAULT 'pending',
            panel_username TEXT,
            config TEXT,
            created_at INTEGER,
            service TEXT DEFAULT 'gold'
        );

        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            kind TEXT,
            amount INTEGER,
            description TEXT,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS coupons(
            code TEXT PRIMARY KEY,
            percent INTEGER DEFAULT 0,
            amount INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 0,
            used INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS coupon_uses(
            code TEXT,
            user_id INTEGER,
            created_at INTEGER,
            PRIMARY KEY(code, user_id)
        );

        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)

        for stmt in (
            "ALTER TABLE users ADD COLUMN trial_gold_used INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN trial_silver_used INTEGER DEFAULT 0",
            "ALTER TABLE plans ADD COLUMN service TEXT DEFAULT 'gold'",
            "ALTER TABLE orders ADD COLUMN service TEXT DEFAULT 'gold'",
        ):
            try:
                c.execute(stmt)
            except sqlite3.OperationalError:
                pass

        # Existing plans are the Gold service.
        c.execute("UPDATE plans SET service='gold' WHERE service IS NULL OR service=''" )

        if c.execute("SELECT COUNT(*) FROM plans").fetchone()[0] == 0:
            c.executemany(
                """INSERT INTO plans
                (title_fa,title_en,gb,price,unlimited,active,sort_order,service)
                VALUES(?,?,?,?,?,?,?,?)""",
                [
                    ("۵ گیگ", "5 GB", 5, 20000, 0, 1, 1, "gold"),
                    ("۱۰ گیگ", "10 GB", 10, 40000, 0, 1, 2, "gold"),
                    ("۲۰ گیگ", "20 GB", 20, 80000, 0, 1, 3, "gold"),
                    ("۴۰ گیگ", "40 GB", 40, 160000, 0, 1, 4, "gold"),
                    ("نامحدود", "Unlimited", None, 0, 1, 0, 5, "gold"),
                ],
            )

        # Add Silver plans once, using the same volumes at 2,000 Toman/GB.
        if c.execute("SELECT COUNT(*) FROM plans WHERE service='silver'").fetchone()[0] == 0:
            c.executemany(
                """INSERT INTO plans
                (title_fa,title_en,gb,price,unlimited,active,sort_order,service)
                VALUES(?,?,?,?,?,?,?,?)""",
                [
                    ("۵ گیگ سیلور", "5 GB Silver", 5, 10000, 0, 1, 1, "silver"),
                    ("۱۰ گیگ سیلور", "10 GB Silver", 10, 20000, 0, 1, 2, "silver"),
                    ("۲۰ گیگ سیلور", "20 GB Silver", 20, 40000, 0, 1, 3, "silver"),
                    ("۴۰ گیگ سیلور", "40 GB Silver", 40, 80000, 0, 1, 4, "silver"),
                ],
            )


def upsert_user(u, referrer=None):
    with conn() as c:
        existing = c.execute("SELECT referrer FROM users WHERE id=?", (u.id,)).fetchone()
        if existing and existing["referrer"]:
            referrer = existing["referrer"]
        c.execute(
            """INSERT INTO users(id,username,first_name,referrer,created_at)
               VALUES(?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
               username=excluded.username,
               first_name=excluded.first_name""",
            (u.id, u.username, u.first_name, referrer, int(time.time())),
        )


def get_user(uid):
    with conn() as c:
        return c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def set_lang(uid, lang):
    with conn() as c:
        c.execute("UPDATE users SET lang=? WHERE id=?", (lang, uid))


def set_balance(uid, amount):
    with conn() as c:
        c.execute("UPDATE users SET balance=? WHERE id=?", (amount, uid))


def plans(service=None, include_inactive=False):
    with conn() as c:
        q = "SELECT * FROM plans"
        clauses = []
        params = []
        if not include_inactive:
            clauses.append("active=1")
        if service:
            clauses.append("service=?")
            params.append(service)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY sort_order,id"
        return c.execute(q, params).fetchall()


def get_plan(pid):
    with conn() as c:
        return c.execute("SELECT * FROM plans WHERE id=?", (pid,)).fetchone()


def update_plan(pid, price=None, active=None, title_fa=None, title_en=None):
    fields, vals = [], []
    if price is not None:
        fields.append("price=?")
        vals.append(price)
    if active is not None:
        fields.append("active=?")
        vals.append(active)
    if title_fa is not None:
        fields.append("title_fa=?")
        vals.append(title_fa)
    if title_en is not None:
        fields.append("title_en=?")
        vals.append(title_en)
    if not fields:
        return
    vals.append(pid)
    with conn() as c:
        c.execute(f"UPDATE plans SET {','.join(fields)} WHERE id=?", vals)


def add_deposit(uid, amount, receipt):
    with conn() as c:
        return c.execute(
            """INSERT INTO deposits(user_id,amount,receipt,created_at)
               VALUES(?,?,?,?)""",
            (uid, amount, receipt, int(time.time())),
        ).lastrowid


def get_deposit(did):
    with conn() as c:
        return c.execute("SELECT * FROM deposits WHERE id=?", (did,)).fetchone()


def pending_deposits():
    with conn() as c:
        return c.execute(
            """SELECT d.*,u.username,u.first_name
               FROM deposits d JOIN users u ON u.id=d.user_id
               WHERE d.status='pending' ORDER BY d.id DESC"""
        ).fetchall()


def review_deposit(did, approved):
    with LOCK, conn() as c:
        d = c.execute("SELECT * FROM deposits WHERE id=?", (did,)).fetchone()
        if not d or d["status"] != "pending":
            return None
        status = "approved" if approved else "rejected"
        c.execute("UPDATE deposits SET status=? WHERE id=?", (status, did))
        if approved:
            c.execute(
                "UPDATE users SET balance=balance+? WHERE id=?",
                (d["amount"], d["user_id"]),
            )
            c.execute(
                """INSERT INTO transactions
                   (user_id,kind,amount,description,created_at)
                   VALUES(?,?,?,?,?)""",
                (
                    d["user_id"],
                    "deposit",
                    d["amount"],
                    f"Deposit #{did}",
                    int(time.time()),
                ),
            )
        return d


def create_order(uid, plan_id, gb, price, service="gold"):
    with LOCK, conn() as c:
        u = c.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()
        if not u or u["balance"] < price:
            return None
        oid = c.execute(
            """INSERT INTO orders(user_id,plan_id,gb,price,created_at,service)
               VALUES(?,?,?,?,?,?)""",
            (uid, plan_id, gb, price, int(time.time()), service),
        ).lastrowid
        c.execute("UPDATE users SET balance=balance-? WHERE id=?", (price, uid))
        c.execute(
            """INSERT INTO transactions
               (user_id,kind,amount,description,created_at)
               VALUES(?,?,?,?,?)""",
            (uid, "purchase", -price, f"Order #{oid}", int(time.time())),
        )
        return oid


def complete_order(oid, username, config_text):
    with conn() as c:
        c.execute(
            """UPDATE orders
               SET status='completed',panel_username=?,config=?
               WHERE id=?""",
            (username, config_text, oid),
        )


def refund(oid, uid, price):
    with conn() as c:
        c.execute("UPDATE users SET balance=balance+? WHERE id=?", (price, uid))
        c.execute("UPDATE orders SET status='refunded' WHERE id=?", (oid,))


def user_orders(uid):
    with conn() as c:
        return c.execute(
            """SELECT * FROM orders WHERE user_id=?
               ORDER BY id DESC LIMIT 30""",
            (uid,),
        ).fetchall()


def referrals(uid):
    with conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM users WHERE referrer=?", (uid,)
        ).fetchone()[0]


def create_coupon(code, percent=0, amount=0, max_uses=0):
    with conn() as c:
        c.execute(
            """INSERT OR REPLACE INTO coupons
               (code,percent,amount,max_uses,used,active)
               VALUES(?,?,?,?,0,1)""",
            (code.upper(), percent, amount, max_uses),
        )


def get_coupon(code):
    with conn() as c:
        return c.execute(
            "SELECT * FROM coupons WHERE code=? AND active=1",
            (code.upper(),),
        ).fetchone()


def has_coupon_used(code, uid):
    code = code.upper()

    with conn() as c:
        row = c.execute(
            "SELECT 1 FROM coupon_uses WHERE code=? AND user_id=?",
            (code, uid),
        ).fetchone()

        return row is not None


def use_coupon(code, uid):
    code = code.upper()

    with conn() as c:
        cp = c.execute(
            "SELECT * FROM coupons WHERE code=? AND active=1",
            (code,),
        ).fetchone()

        if not cp:
            return None

        if cp["max_uses"] and cp["used"] >= cp["max_uses"]:
            return None

        if c.execute(
            "SELECT 1 FROM coupon_uses WHERE code=? AND user_id=?",
            (code, uid),
        ).fetchone():
            return None

        # فقط اعتبار کد را بررسی می‌کنیم.
        # مصرف واقعی بعد از خرید انجام می‌شود.
        return cp


def consume_coupon(code, uid):
    code = code.upper()

    with LOCK, conn() as c:
        cp = c.execute(
            "SELECT * FROM coupons WHERE code=? AND active=1",
            (code,),
        ).fetchone()

        if not cp:
            return False

        if cp["max_uses"] and cp["used"] >= cp["max_uses"]:
            return False

        if c.execute(
            "SELECT 1 FROM coupon_uses WHERE code=? AND user_id=?",
            (code, uid),
        ).fetchone():
            return False

        c.execute(
            """
            INSERT INTO coupon_uses(code,user_id,created_at)
            VALUES(?,?,?)
            """,
            (code, uid, int(time.time())),
        )

        c.execute(
            "UPDATE coupons SET used=used+1 WHERE code=?",
            (code,),
        )

        return True

def coupons():
    with conn() as c:
        return c.execute("SELECT * FROM coupons ORDER BY code").fetchall()


def stats():
    with conn() as c:
        return {
            "users": c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "orders": c.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            "pending": c.execute(
                "SELECT COUNT(*) FROM deposits WHERE status='pending'"
            ).fetchone()[0],
            "balance": c.execute(
                "SELECT COALESCE(SUM(balance),0) FROM users"
            ).fetchone()[0],
            "sales": c.execute(
                "SELECT COALESCE(SUM(price),0) FROM orders WHERE status='completed'"
            ).fetchone()[0],
        }


def recent_users(limit=15):
    with conn() as c:
        return c.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()


def all_users(limit=1000):
    with conn() as c:
        return c.execute(
            "SELECT * FROM users ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


def set_blocked(uid, blocked):
    with conn() as c:
        c.execute("UPDATE users SET blocked=? WHERE id=?", (blocked, uid))


def add_balance(uid, amount, description="Admin balance"):
    with LOCK, conn() as c:
        c.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, uid))
        c.execute(
            """INSERT INTO transactions
               (user_id,kind,amount,description,created_at)
               VALUES(?,?,?,?,?)""",
            (uid, "admin", amount, description, int(time.time())),
        )

def has_used_trial(uid, service="gold"):
    column = "trial_silver_used" if service == "silver" else "trial_gold_used"
    with conn() as c:
        row = c.execute(f"SELECT {column}, trial_used FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            return False
        return bool(row[column] or (service == "gold" and row["trial_used"]))


def set_trial_used(uid, service="gold"):
    column = "trial_silver_used" if service == "silver" else "trial_gold_used"
    with conn() as c:
        c.execute(f"UPDATE users SET {column}=1 WHERE id=?", (uid,))
        if service == "gold":
            c.execute("UPDATE users SET trial_used=1 WHERE id=?", (uid,))


def reset_trial(uid):
    with conn() as c:
        c.execute(
            "UPDATE users SET trial_used=0, trial_gold_used=0, trial_silver_used=0 WHERE id=?",
            (uid,),
        )
