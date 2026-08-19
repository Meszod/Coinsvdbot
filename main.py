import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
import handlers_user
import handlers_admin
import handlers_channel


async def main():
    logging.basicConfig(level=logging.INFO)

    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Diqqat: admin va channel routerlarini user routeridan OLDIN ulash kerak,
    # aks holda forward video xabarlari umumiy handlerga tushib qolishi mumkin
    dp.include_router(handlers_admin.router)
    dp.include_router(handlers_channel.router)
    dp.include_router(handlers_user.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
