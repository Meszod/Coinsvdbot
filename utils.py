from aiogram import Bot
from database import get_mandatory_channels


async def check_subscriptions(bot: Bot, user_id: int) -> list:
    """
    Foydalanuvchi obuna bo'lmagan majburiy kanallar ro'yxatini qaytaradi.
    Bo'sh ro'yxat = hammasiga obuna bo'lgan.
    """
    channels = await get_mandatory_channels()
    not_subscribed = []
    for ch in channels:
        chat_id = ch["chat_id"]
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ("left", "kicked"):
                not_subscribed.append(ch)
        except Exception:
            # bot kanalda admin emas yoki kanal topilmadi -> xavfsizlik uchun majburiy deb hisoblaymiz
            not_subscribed.append(ch)
    return not_subscribed
