import aiosqlite
from datetime import datetime, timedelta, date
from config import (
    DB_PATH,
    START_COINS,
    REFERRAL_TIERS,
    DAILY_BONUS_COINS,
    ENERGY_REGEN_HOURS,
    ENERGY_REGEN_MAX,
)

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0,
    referrer_id INTEGER,
    ref_count INTEGER DEFAULT 0,
    last_daily TEXT,
    last_regen TEXT,
    claimed_tiers TEXT DEFAULT '',
    banned INTEGER DEFAULT 0,
    username TEXT,
    first_name TEXT,
    joined_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT UNIQUE NOT NULL,
    duration INTEGER,
    likes INTEGER DEFAULT 0,
    dislikes INTEGER DEFAULT 0,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sent_videos (
    user_id INTEGER NOT NULL,
    video_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, video_id)
);

CREATE TABLE IF NOT EXISTS video_reactions (
    user_id INTEGER NOT NULL,
    video_id INTEGER NOT NULL,
    reaction TEXT NOT NULL,   -- 'like' yoki 'dislike'
    PRIMARY KEY (user_id, video_id)
);

CREATE TABLE IF NOT EXISTS mandatory_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL UNIQUE,   -- @username yoki -100... id
    title TEXT,
    invite_link TEXT                -- username bo'lmagan kanallar uchun taklif havolasi
);

CREATE TABLE IF NOT EXISTS source_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL UNIQUE,  -- video olinadigan kanal (-100...)
    title TEXT
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES_SQL)
        # Eski (oldin yaratilgan) bazalar uchun migratsiya - yangi ustunlarni qo'shib qo'yadi
        for col_def in [
            "last_daily TEXT",
            "last_regen TEXT",
            "claimed_tiers TEXT DEFAULT ''",
            "banned INTEGER DEFAULT 0",
            "username TEXT",
            "first_name TEXT",
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col_def}")
            except Exception:
                pass  # ustun allaqachon mavjud
        try:
            await db.execute("ALTER TABLE mandatory_channels ADD COLUMN invite_link TEXT")
        except Exception:
            pass
        await db.commit()


# ---------------- USERS ----------------

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return await cur.fetchone()


async def create_user_if_not_exists(
    user_id: int,
    referrer_id: int | None = None,
    username: str | None = None,
    first_name: str | None = None,
):
    user = await get_user(user_id)
    if user:
        return False  # allaqachon bor
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, coins, referrer_id, username, first_name) VALUES (?, ?, ?, ?, ?)",
            (user_id, START_COINS, referrer_id, username, first_name),
        )
        await db.commit()
    return True  # yangi foydalanuvchi


async def add_coins(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, user_id)
        )
        await db.commit()


async def take_coin(user_id: int) -> bool:
    """1 ta coin yechadi, agar yetarli bo'lmasa False qaytaradi"""
    user = await get_user(user_id)
    if not user or user["coins"] <= 0:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET coins = coins - 1 WHERE user_id=?", (user_id,)
        )
        await db.commit()
    return True


async def increment_ref_count(referrer_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET ref_count = ref_count + 1 WHERE user_id=?",
            (referrer_id,),
        )
        await db.commit()


async def check_referral_tier_bonus(user_id: int):
    """
    Foydalanuvchining ref_count'i yangi bosqichga (masalan 5, 10, 20...) yetgan bo'lsa,
    mos bonus coinni qo'shadi va (bosqich, bonus) qaytaradi. Aks holda None.
    Har bir bosqich uchun bonus faqat 1 marta beriladi.
    """
    user = await get_user(user_id)
    if not user:
        return None
    ref_count = user["ref_count"]
    claimed_raw = user["claimed_tiers"] or ""
    claimed = set(x for x in claimed_raw.split(",") if x)

    for threshold in sorted(REFERRAL_TIERS.keys()):
        if ref_count >= threshold and str(threshold) not in claimed:
            bonus = REFERRAL_TIERS[threshold]
            claimed.add(str(threshold))
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE users SET coins = coins + ?, claimed_tiers=? WHERE user_id=?",
                    (bonus, ",".join(sorted(claimed, key=int)), user_id),
                )
                await db.commit()
            return threshold, bonus
    return None


async def claim_daily_bonus(user_id: int) -> bool:
    """Kunlik bonusni beradi. Agar bugun allaqachon olingan bo'lsa False qaytaradi."""
    user = await get_user(user_id)
    if not user:
        return False
    today = date.today().isoformat()
    if user["last_daily"] == today:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET coins = coins + ?, last_daily=? WHERE user_id=?",
            (DAILY_BONUS_COINS, today, user_id),
        )
        await db.commit()
    return True


async def apply_energy_regen(user_id: int) -> int:
    """
    'Energy' tizimi: har ENERGY_REGEN_HOURS soatda 1 coin avtomatik qo'shiladi,
    lekin coin soni ENERGY_REGEN_MAX dan oshmaydi. Qo'shilgan coin sonini qaytaradi.
    """
    user = await get_user(user_id)
    if not user:
        return 0

    now = datetime.utcnow()
    last_regen_str = user["last_regen"] or user["joined_at"]
    try:
        last_regen = datetime.fromisoformat(str(last_regen_str))
    except Exception:
        last_regen = now

    elapsed_hours = (now - last_regen).total_seconds() / 3600
    regen_count = int(elapsed_hours // ENERGY_REGEN_HOURS)

    if regen_count <= 0:
        return 0

    current_coins = user["coins"]
    if current_coins >= ENERGY_REGEN_MAX:
        # Coin allaqachon chegarada - faqat vaqtni yangilaymiz (keyin portlab ketmasligi uchun)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET last_regen=? WHERE user_id=?",
                (now.isoformat(), user_id),
            )
            await db.commit()
        return 0

    add_amount = min(regen_count, ENERGY_REGEN_MAX - current_coins)
    new_last_regen = last_regen + timedelta(hours=add_amount * ENERGY_REGEN_HOURS)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET coins = coins + ?, last_regen=? WHERE user_id=?",
            (add_amount, new_last_regen.isoformat(), user_id),
        )
        await db.commit()
    return add_amount


async def count_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        row = await cur.fetchone()
        return row[0]


async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE banned=0")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
        await db.commit()


async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
        await db.commit()


async def is_banned(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user["banned"]) if user else False


async def stats_today_new_users():
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM users WHERE date(joined_at)=?", (today,)
        )
        row = await cur.fetchone()
        return row[0]


async def top_videos(order_by: str = "likes", limit: int = 5):
    field = "likes" if order_by == "likes" else "dislikes"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            f"SELECT id, likes, dislikes FROM videos ORDER BY {field} DESC LIMIT ?",
            (limit,),
        )
        return await cur.fetchall()


async def most_active_users(limit: int = 5):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT user_id, COUNT(*) as cnt FROM sent_videos
            GROUP BY user_id ORDER BY cnt DESC LIMIT ?
            """,
            (limit,),
        )
        return await cur.fetchall()


async def get_referred_users(referrer_id: int, limit: int = 20):
    """Foydalanuvchi taklif qilgan do'stlar ro'yxatini qaytaradi (eng oxirgisi birinchi)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT user_id, username, first_name, joined_at FROM users
            WHERE referrer_id = ?
            ORDER BY joined_at DESC LIMIT ?
            """,
            (referrer_id, limit),
        )
        return await cur.fetchall()


# ---------------- VIDEOS ----------------

async def add_video(file_id: str, duration: int):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO videos (file_id, duration) VALUES (?, ?)",
                (file_id, duration),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False  # bu video allaqachon bazada bor


async def count_videos():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM videos")
        row = await cur.fetchone()
        return row[0]


async def get_random_unseen_video(user_id: int):
    """Foydalanuvchi hali ko'rmagan tasodifiy videoni qaytaradi"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM videos
            WHERE id NOT IN (SELECT video_id FROM sent_videos WHERE user_id=?)
            ORDER BY RANDOM() LIMIT 1
            """,
            (user_id,),
        )
        return await cur.fetchone()


async def mark_video_sent(user_id: int, video_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO sent_videos (user_id, video_id) VALUES (?, ?)",
            (user_id, video_id),
        )
        await db.commit()


async def add_reaction(video_id: int, liked: bool):
    field = "likes" if liked else "dislikes"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE videos SET {field} = {field} + 1 WHERE id=?", (video_id,)
        )
        await db.commit()


async def set_reaction(user_id: int, video_id: int, liked: bool):
    """
    Foydalanuvchining videoga reaksiyasini saqlaydi (1 kishi = 1 ovoz).
    Agar oldin qarama-qarshi reaksiya bosilgan bo'lsa - avtomatik almashtiradi.
    Yangilangan (likes, dislikes) sonlarini qaytaradi.
    """
    reaction = "like" if liked else "dislike"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT reaction FROM video_reactions WHERE user_id=? AND video_id=?",
            (user_id, video_id),
        )
        existing = await cur.fetchone()

        if existing is None:
            await db.execute(
                "INSERT INTO video_reactions (user_id, video_id, reaction) VALUES (?, ?, ?)",
                (user_id, video_id, reaction),
            )
            field = "likes" if liked else "dislikes"
            await db.execute(
                f"UPDATE videos SET {field} = {field} + 1 WHERE id=?", (video_id,)
            )
        elif existing["reaction"] != reaction:
            old_field = "likes" if existing["reaction"] == "like" else "dislikes"
            new_field = "likes" if liked else "dislikes"
            await db.execute(
                f"UPDATE videos SET {old_field} = {old_field} - 1, {new_field} = {new_field} + 1 WHERE id=?",
                (video_id,),
            )
            await db.execute(
                "UPDATE video_reactions SET reaction=? WHERE user_id=? AND video_id=?",
                (reaction, user_id, video_id),
            )
        # aks holda: xuddi shu reaksiya qayta bosilgan - o'zgarish yo'q

        await db.commit()
        cur2 = await db.execute("SELECT likes, dislikes FROM videos WHERE id=?", (video_id,))
        row = await cur2.fetchone()
        return (row["likes"], row["dislikes"]) if row else (0, 0)


# ---------------- MANDATORY CHANNELS ----------------

async def add_mandatory_channel(chat_id: str, title: str = "", invite_link: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO mandatory_channels (chat_id, title, invite_link) VALUES (?, ?, ?)",
                (chat_id, title, invite_link),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_mandatory_channel(chat_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM mandatory_channels WHERE chat_id=?", (chat_id,))
        await db.commit()


async def get_mandatory_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM mandatory_channels")
        return await cur.fetchall()


# ---------------- SOURCE CHANNELS (videolar olinadigan kanal) ----------------

async def add_source_channel(chat_id: int, title: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO source_channels (chat_id, title) VALUES (?, ?)",
                (chat_id, title),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_source_channel(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM source_channels WHERE chat_id=?", (chat_id,))
        await db.commit()


async def get_source_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM source_channels")
        return await cur.fetchall()


async def is_source_channel(chat_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM source_channels WHERE chat_id=?", (chat_id,)
        )
        return await cur.fetchone() is not None
