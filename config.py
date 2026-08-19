import os

# Bot tokenini @BotFather dan oling
BOT_TOKEN = os.getenv("BOT_TOKEN", "8682859580:AAE_Xuf30lK4mwDCXNWganbLfAuYKAKeReo")

# Admin(lar) Telegram user ID lari (bir nechta bo'lishi mumkin)
ADMIN_IDS = [
    8350947035,  # <- shu yerga o'zingizning Telegram ID raqamingizni yozing
]

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

DB_PATH = "bot.db"
