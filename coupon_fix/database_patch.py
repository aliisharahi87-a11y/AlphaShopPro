# Add these functions to database.py (after use_coupon or near the coupon functions)

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

        # Only validate the coupon here. Do not consume it yet.
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