from aiogram import Router, F
from aiogram.types import Message

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
