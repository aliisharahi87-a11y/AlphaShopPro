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
            trial_silver_used INTEGER DEFAULT 0,
            trial_bronze_used INTEGER DEFAULT 0,
            alpha_coins INTEGER DEFAULT 0
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

        CREATE TABLE IF NOT EXISTS alpha_coin_ledger(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_id INTEGER,
            kind TEXT NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT,
            created_at INTEGER
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_alpha_coin_order_reward
        ON alpha_coin_ledger(user_id, order_id, kind)
        WHERE order_id IS NOT NULL;
        """)

        for stmt in (
            "ALTER TABLE users ADD COLUMN alpha_coins INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN trial_gold_used INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN trial_silver_used INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN trial_bronze_used INTEGER DEFAULT 0",
            "ALTER TABLE plans ADD COLUMN service TEXT DEFAULT 'gold'",
            "ALTER TABLE orders ADD COLUMN service TEXT DEFAULT 'gold'",
        ):
            try:
                c.execute(stmt)
            except sqlite3.OperationalError:
                pass

        # Keep existing data, but normalize service plans for the three-service setup.
        c.execute("UPDATE plans SET service='gold' WHERE service IS NULL OR service=''")

        # No Unlimited plan in the new shop.
        c.execute("UPDATE plans SET active=0 WHERE unlimited=1")

        def ensure_service(service, price_per_gb, fa_suffix, en_suffix):
            rows = c.execute("SELECT id,gb FROM plans WHERE service=? AND unlimited=0", (service,)).fetchall()
            existing_gb = {int(r['gb']) for r in rows if r['gb'] is not None}
            plans_to_add = []
            for order, gb in enumerate((5, 10, 20, 40), 1):
                if gb not in existing_gb:
                    plans_to_add.append((f"{gb} گیگ {fa_suffix}".strip(), f"{gb} GB {en_suffix}".strip(), gb, gb * price_per_gb, 0, 1, order, service))
            if plans_to_add:
                c.executemany(
                    """INSERT INTO plans(title_fa,title_en,gb,price,unlimited,active,sort_order,service)
                       VALUES(?,?,?,?,?,?,?,?)""", plans_to_add
                )
            for gb in (5, 10, 20, 40):
                c.execute(
                    "UPDATE plans SET price=?, active=1 WHERE service=? AND gb=? AND unlimited=0",
                    (gb * price_per_gb, service, gb),
                )

        # Existing Gold plans are retained but their prices are normalized to 5,000/GB.
        ensure_service('gold', 5000, 'Gold', 'Gold')
        ensure_service('silver', 3000, 'Silver', 'Silver')
        ensure_service('bronze', 1000, 'Bronze', 'Bronze')



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


def get_order(uid, oid):
    with conn() as c:
        return c.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, uid)).fetchone()


def charge_renewal(uid, oid, amount):
    """Atomically charge the wallet for a renewal of an existing completed order."""
    with LOCK, conn() as c:
        row = c.execute("SELECT id,status FROM orders WHERE id=? AND user_id=?", (oid, uid)).fetchone()
        u = c.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()
        if not row or row["status"] != "completed" or not u or u["balance"] < amount:
            return False
        c.execute("UPDATE users SET balance=balance-? WHERE id=?", (amount, uid))
        c.execute(
            "INSERT INTO transactions(user_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)",
            (uid, "renewal", -amount, f"Renewal #{oid}", int(time.time())),
        )
        return True


def record_renewal_success(uid, oid, amount):
    """Record a successfully completed renewal for mission tracking."""
    with LOCK, conn() as c:
        c.execute(
            "INSERT INTO transactions(user_id,kind,amount,description,created_at) "
            "VALUES(?,?,?,?,?)",
            (
                uid,
                "renewal_success",
                -int(amount),
                f"Renewal success #{oid}",
                int(time.time()),
            ),
        )
        return True


def refund_renewal(uid, amount, oid):
    with LOCK, conn() as c:
        c.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, uid))
        c.execute(
            "INSERT INTO transactions(user_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)",
            (uid, "renewal_refund", amount, f"Renewal refund #{oid}", int(time.time())),
        )


def user_orders(uid):
    with conn() as c:
        return c.execute(
            """SELECT * FROM orders WHERE user_id=?
               ORDER BY id DESC LIMIT 30""",
            (uid,),
        ).fetchall()



def get_alpha_coins(uid):
    with conn() as c:
        row = c.execute(
            "SELECT COALESCE(alpha_coins,0) AS alpha_coins FROM users WHERE id=?",
            (uid,),
        ).fetchone()
        return int(row["alpha_coins"] or 0) if row else 0


def add_alpha_coins(uid, amount, kind, order_id=None, description=""):
    amount = int(amount or 0)
    if amount <= 0:
        return False

    with LOCK, conn() as c:
        if order_id is not None:
            existing = c.execute(
                """SELECT 1 FROM alpha_coin_ledger
                   WHERE user_id=? AND order_id=? AND kind=?""",
                (uid, order_id, kind),
            ).fetchone()

            if existing:
                return False

        cur = c.execute(
            "UPDATE users SET alpha_coins=COALESCE(alpha_coins,0)+? WHERE id=?",
            (amount, uid),
        )

        # Do not create a Coin ledger entry for a non-existent user.
        if cur.rowcount == 0:
            return False

        c.execute(
            """INSERT INTO alpha_coin_ledger
               (user_id,order_id,kind,amount,description,created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                uid,
                order_id,
                kind,
                amount,
                description,
                int(time.time()),
            ),
        )

        return True


def spend_alpha_coins(uid, amount, description=""):
    amount = int(amount or 0)

    if amount <= 0:
        return False

    with LOCK, conn() as c:
        row = c.execute(
            "SELECT COALESCE(alpha_coins,0) AS alpha_coins FROM users WHERE id=?",
            (uid,),
        ).fetchone()

        if not row or int(row["alpha_coins"] or 0) < amount:
            return False

        c.execute(
            "UPDATE users SET alpha_coins=alpha_coins-? WHERE id=?",
            (amount, uid),
        )

        c.execute(
            """INSERT INTO alpha_coin_ledger
               (user_id,order_id,kind,amount,description,created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                uid,
                None,
                "spend",
                -amount,
                description,
                int(time.time()),
            ),
        )

        return True


def alpha_coin_history(uid, limit=20):
    with conn() as c:
        return c.execute(
            """SELECT * FROM alpha_coin_ledger
               WHERE user_id=?
               ORDER BY id DESC
               LIMIT ?""",
            (uid, int(limit)),
        ).fetchall()


def award_purchase_alpha_coins(order_id, buyer_id, paid_amount):
    paid_amount = int(paid_amount or 0)

    if paid_amount <= 0:
        return {"buyer": 0, "referrer": 0}

    # Buyer: 5% of paid amount.
    # 1 ALC = 100 toman.
    buyer_coins = paid_amount // 2000

    # Referrer: 2.5% of paid amount.
    referrer_coins = paid_amount // 4000

    result = {
        "buyer": 0,
        "referrer": 0,
    }

    if buyer_coins > 0:
        if add_alpha_coins(
            buyer_id,
            buyer_coins,
            "purchase_reward",
            order_id,
            f"5% purchase reward for Order #{order_id}",
        ):
            result["buyer"] = buyer_coins

    with conn() as c:
        row = c.execute(
            "SELECT referrer FROM users WHERE id=?",
            (buyer_id,),
        ).fetchone()

    referrer_id = (
        int(row["referrer"])
        if row and row["referrer"]
        else None
    )

    if (
        referrer_id
        and referrer_id != buyer_id
        and referrer_coins > 0
    ):
        if add_alpha_coins(
            referrer_id,
            referrer_coins,
            "referral_reward",
            order_id,
            f"2.5% referral reward for Order #{order_id}",
        ):
            result["referrer"] = referrer_coins

    return result


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
    column = {"gold":"trial_gold_used", "silver":"trial_silver_used", "bronze":"trial_bronze_used"}.get(service, "trial_gold_used")
    with conn() as c:
        row = c.execute(f"SELECT {column}, trial_used FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            return False
        return bool(row[column] or (service == "gold" and row["trial_used"]))


def set_trial_used(uid, service="gold"):
    column = {"gold":"trial_gold_used", "silver":"trial_silver_used", "bronze":"trial_bronze_used"}.get(service, "trial_gold_used")
    with conn() as c:
        c.execute(f"UPDATE users SET {column}=1 WHERE id=?", (uid,))
        if service == "gold":
            c.execute("UPDATE users SET trial_used=1 WHERE id=?", (uid,))


def reset_trial(uid):
    with conn() as c:
        c.execute(
            "UPDATE users SET trial_used=0, trial_gold_used=0, trial_silver_used=0, trial_bronze_used=0 WHERE id=?",
            (uid,),
        )


# ============================================================
# ALPHA SHOP — MISSION SYSTEM
# ============================================================

def init_mission_db():
    with LOCK, conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS mission_stages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage_key TEXT UNIQUE NOT NULL,
            title_fa TEXT NOT NULL,
            title_en TEXT NOT NULL,
            reward_alc INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS missions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage_id INTEGER NOT NULL,
            mission_key TEXT UNIQUE NOT NULL,
            title_fa TEXT NOT NULL,
            title_en TEXT NOT NULL,
            mission_type TEXT NOT NULL,
            target INTEGER NOT NULL DEFAULT 1,
            active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(stage_id) REFERENCES mission_stages(id)
        );

        CREATE TABLE IF NOT EXISTS mission_stage_claims(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            stage_id INTEGER NOT NULL,
            claimed_at INTEGER NOT NULL,
            UNIQUE(user_id, stage_id)
        );
        """)

        stages = [
            ("start", "🟢 شروع", "🟢 Start", 50, 1, 1),
            ("active", "🔵 فعال", "🔵 Active", 250, 1, 2),
            ("pro", "🟣 حرفه‌ای", "🟣 Professional", 450, 1, 3),
            ("special", "🔥 ویژه", "🔥 Special", 500, 1, 4),
        ]

        for stage in stages:
            c.execute(
                """
                INSERT OR IGNORE INTO mission_stages
                (stage_key,title_fa,title_en,reward_alc,active,sort_order)
                VALUES(?,?,?,?,?,?)
                """,
                stage,
            )

        stage_rows = {
            row["stage_key"]: row["id"]
            for row in c.execute(
                "SELECT id,stage_key FROM mission_stages"
            ).fetchall()
        }

        missions = [
            (
                stage_rows["start"],
                "start_purchase",
                "🛒 یک خرید موفق",
                "🛒 One successful purchase",
                "purchases",
                1,
                1,
                1,
            ),
            (
                stage_rows["start"],
                "start_deposit",
                "💳 یک بار شارژ کیف پول",
                "💳 One wallet deposit",
                "deposits",
                1,
                1,
                2,
            ),
            (
                stage_rows["start"],
                "start_referral",
                "👥 یک زیرمجموعه موفق",
                "👥 One successful referral",
                "referrals",
                1,
                1,
                3,
            ),

            (
                stage_rows["active"],
                "active_purchase",
                "🛒 سه خرید موفق",
                "🛒 Three successful purchases",
                "purchases",
                3,
                1,
                1,
            ),
            (
                stage_rows["active"],
                "active_renewal",
                "🔄 دو تمدید موفق",
                "🔄 Two successful renewals",
                "renewals",
                2,
                1,
                2,
            ),
            (
                stage_rows["active"],
                "active_referral",
                "👥 دو زیرمجموعه موفق",
                "👥 Two successful referrals",
                "referrals",
                2,
                1,
                3,
            ),

            (
                stage_rows["pro"],
                "pro_purchase",
                "🛒 پنج خرید موفق",
                "🛒 Five successful purchases",
                "purchases",
                5,
                1,
                1,
            ),
            (
                stage_rows["pro"],
                "pro_renewal",
                "🔄 پنج تمدید موفق",
                "🔄 Five successful renewals",
                "renewals",
                5,
                1,
                2,
            ),
            (
                stage_rows["pro"],
                "pro_referral",
                "👥 پنج زیرمجموعه موفق",
                "👥 Five successful referrals",
                "referrals",
                5,
                1,
                3,
            ),
            (
                stage_rows["pro"],
                "pro_deposit",
                "💳 سه بار شارژ کیف پول",
                "💳 Three wallet deposits",
                "deposits",
                3,
                1,
                4,
            ),
        ]

        for mission in missions:
            c.execute(
                """
                INSERT OR IGNORE INTO missions
                (stage_id,mission_key,title_fa,title_en,mission_type,target,active,sort_order)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                mission,
            )

        c.commit()


def mission_stages():
    with conn() as c:
        return c.execute(
            """
            SELECT *
            FROM mission_stages
            WHERE active=1
            ORDER BY sort_order,id
            """
        ).fetchall()


def stage_missions(stage_id):
    with conn() as c:
        return c.execute(
            """
            SELECT *
            FROM missions
            WHERE stage_id=? AND active=1
            ORDER BY sort_order,id
            """,
            (stage_id,),
        ).fetchall()


def mission_claimed(uid, stage_id):
    with conn() as c:
        row = c.execute(
            """
            SELECT 1
            FROM mission_stage_claims
            WHERE user_id=? AND stage_id=?
            """,
            (uid, stage_id),
        ).fetchone()
    return bool(row)


def claim_mission_stage(uid, stage_id, reward):
    with LOCK, conn() as c:
        exists = c.execute(
            """
            SELECT 1
            FROM mission_stage_claims
            WHERE user_id=? AND stage_id=?
            """,
            (uid, stage_id),
        ).fetchone()

        if exists:
            return False

        c.execute(
            """
            INSERT INTO mission_stage_claims
            (user_id,stage_id,claimed_at)
            VALUES(?,?,?)
            """,
            (uid, stage_id, int(time.time())),
        )

        return True


def mission_progress(uid, mission_type):
    with conn() as c:
        if mission_type == "purchases":
            row = c.execute(
                """
                SELECT COUNT(*) AS n
                FROM orders
                WHERE user_id=? AND status='completed'
                """,
                (uid,),
            ).fetchone()
            return int(row["n"] or 0)

        if mission_type == "renewals":
            row = c.execute(
                """
                SELECT COUNT(*) AS n
                FROM transactions
                WHERE user_id=? AND kind='renewal_success'
                """,
                (uid,),
            ).fetchone()
            return int(row["n"] or 0)

        if mission_type == "deposits":
            row = c.execute(
                """
                SELECT COUNT(*) AS n
                FROM transactions
                WHERE user_id=? AND kind='deposit'
                """,
                (uid,),
            ).fetchone()
            return int(row["n"] or 0)

        if mission_type == "referrals":
            row = c.execute(
                """
                SELECT COUNT(*) AS n
                FROM users
                WHERE referrer=?
                """,
                (uid,),
            ).fetchone()
            return int(row["n"] or 0)

    return 0

def claim_mission_stage_reward(uid, stage_id, reward, description=""):
    uid = int(uid)
    stage_id = int(stage_id)
    reward = int(reward or 0)

    if reward <= 0:
        return False

    with LOCK, conn() as c:
        # Already claimed?
        existing = c.execute(
            """
            SELECT 1
            FROM mission_stage_claims
            WHERE user_id=? AND stage_id=?
            """,
            (uid, stage_id),
        ).fetchone()

        if existing:
            return False

        # Make sure the user exists.
        user = c.execute(
            "SELECT id FROM users WHERE id=?",
            (uid,),
        ).fetchone()

        if not user:
            return False

        now = int(time.time())

        # Record the claim first inside the same transaction.
        c.execute(
            """
            INSERT INTO mission_stage_claims
            (user_id, stage_id, claimed_at)
            VALUES (?, ?, ?)
            """,
            (uid, stage_id, now),
        )

        # Award coins.
        c.execute(
            """
            UPDATE users
            SET alpha_coins=COALESCE(alpha_coins,0)+?
            WHERE id=?
            """,
            (reward, uid),
        )

        # Record the reward in the Alpha Coin ledger.
        c.execute(
            """
            INSERT INTO alpha_coin_ledger
            (user_id, order_id, kind, amount, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                None,
                "mission_stage_reward",
                reward,
                description or f"Mission stage #{stage_id} reward",
                now,
            ),
        )

        return True

def mission_stage_unlocked(uid, stage_id):
    uid = int(uid)
    stage_id = int(stage_id)

    stages = mission_stages()

    current_index = None

    for i, stage in enumerate(stages):
        if int(stage["id"]) == stage_id:
            current_index = i
            break

    if current_index is None:
        return False

    # First stage is always unlocked.
    if current_index == 0:
        return True

    previous_stage = stages[current_index - 1]
    previous_id = int(previous_stage["id"])

    # The previous stage must have been claimed.
    return mission_claimed(uid, previous_id)
