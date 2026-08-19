import os
from dotenv import load_dotenv

load_dotenv()  # lokalda ishlatilganda .env faylini o'qiydi (Railway'da bunga hojat yo'q)

# Bot tokenini @BotFather dan oling. Token faqat .env faylida yoki
# Railway "Variables" bo'limida saqlanishi kerak - kodga yozmang!
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi! .env faylga BOT_TOKEN=... qo'shing "
        "yoki Railway Variables bo'limiga kiriting."
    )

# Admin(lar) Telegram user ID lari (vergul bilan ajratib bir nechtasini yozish mumkin)
# .env da: ADMIN_IDS=8350947035,123456789
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip()]

# Yangi foydalanuvchiga beriladigan boshlang'ich coinlar soni
START_COINS = 3

# Do'st taklif qilganda referrer ga beriladigan coin soni
REF_BONUS_COINS = 1

# Video minimal davomiyligi (sekundlarda) - shundan uzun videolar saqlanadi
MIN_VIDEO_DURATION = 60

# --- Bosqichli referral bonuslari: {necha do'st: qo'shimcha bonus coin} ---
REFERRAL_TIERS = {
    5: 2,
    10: 5,
    20: 12,
    50: 35,
    100: 80,
}

# --- Kunlik bonus ---
DAILY_BONUS_COINS = 1

# --- "Energy" tizimi: har necha soatda 1 coin avtomatik tiklanadi ---
ENERGY_REGEN_HOURS = 4      # necha soatda 1 coin qo'shiladi
ENERGY_REGEN_MAX = 5        # avtomatik tiklanish orqali coin shu chegaragacha to'ladi

# --- Telegram Stars orqali sotib olinadigan coin paketlari: {stars: coin} ---
STAR_PACKAGES = {
    50: 10,
    100: 22,
    250: 60,
    500: 130,
}

DB_PATH = "bot.db"
