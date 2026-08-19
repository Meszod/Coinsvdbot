from aiogram import Router, F, Bot
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER

import database as db
from config import MIN_VIDEO_DURATION

router = Router()


@router.channel_post(F.video)
async def new_channel_video(message: Message):
    """
    Bot admin qilib qo'shilgan 'manba kanal'larga yangi video post qilinganda
    avtomatik ravishda (1 daqiqadan uzun bo'lsa) bazaga saqlab boradi.
    """
    if not await db.is_source_channel(message.chat.id):
        return

    duration = message.video.duration or 0
    if duration < MIN_VIDEO_DURATION:
        return

    await db.add_video(message.video.file_id, duration)


async def _is_mandatory_channel(chat) -> bool:
    """Berilgan chat majburiy kanallar ro'yxatida bormi - tekshiradi."""
    channels = await db.get_mandatory_channels()
    stored_ids = {str(ch["chat_id"]) for ch in channels}
    if str(chat.id) in stored_ids:
        return True
    if chat.username and f"@{chat.username}" in stored_ids:
        return True
    return False


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_MEMBER >> IS_NOT_MEMBER))
async def user_left_mandatory_channel(event: ChatMemberUpdated, bot: Bot):
    """
    Foydalanuvchi majburiy (obuna talab qilinadigan) kanallardan birini
    tark etsa (chiqib ketsa yoki botdan/kanaldan chetlatilsa), unga shaxsiy
    xabar yuborib qayta obuna bo'lishini so'raymiz.

    Eslatma: bu ishlashi uchun bot mazkur kanalda ADMIN bo'lishi shart -
    aks holda Telegram bunday yangilanishlarni botga yubormaydi.
    """
    if not await _is_mandatory_channel(event.chat):
        return

    user = event.new_chat_member.user
    if user.is_bot:
        return

    channel_title = event.chat.title or (
        f"@{event.chat.username}" if event.chat.username else str(event.chat.id)
    )

    try:
        await bot.send_message(
            user.id,
            f"⚠️ Siz <b>{channel_title}</b> kanalidan chiqib ketdingiz.\n"
            "Botdan foydalanishni davom ettirish uchun qaytadan obuna bo'ling 🙏",
        )
    except Exception:
        # Foydalanuvchi botni bloklagan yoki hali botga /start bosmagan bo'lishi mumkin
        pass
