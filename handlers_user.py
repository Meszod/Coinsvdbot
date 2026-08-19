from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery

import database as db
from config import REF_BONUS_COINS, START_COINS, ENERGY_REGEN_HOURS, ENERGY_REGEN_MAX, STAR_PACKAGES
from keyboards import main_menu_kb, video_reaction_kb, subscribe_kb, star_packages_kb, invite_kb
from utils import check_subscriptions

router = Router()


async def send_random_video(bot: Bot, chat_id: int, user_id: int):
    video = await db.get_random_unseen_video(user_id)
    if not video:
        await bot.send_message(
            chat_id,
            "😔 Hozircha sizga ko'rsatiladigan yangi video qolmadi. Keyinroq qayta urinib ko'ring.",
        )
        return
    # file_id orqali YANGI xabar sifatida yuboriladi -> qaysi kanaldan olinganligi bilinmaydi,
    # forward emas, caption yo'q (textsiz)
    await bot.send_video(
        chat_id=chat_id,
        video=video["file_id"],
        reply_markup=video_reaction_kb(video["id"], video["likes"], video["dislikes"]),
    )
    await db.mark_video_sent(user_id, video["id"])


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_candidate = int(args[1].replace("ref_", ""))
            if ref_candidate != user_id:
                referrer_id = ref_candidate
        except ValueError:
            pass

    is_new = await db.create_user_if_not_exists(
        user_id,
        referrer_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    if is_new and referrer_id:
        referrer = await db.get_user(referrer_id)
        if referrer:
            await db.add_coins(referrer_id, REF_BONUS_COINS)
            await db.increment_ref_count(referrer_id)
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 Sizning taklifingiz bilan yangi foydalanuvchi qo'shildi!\n"
                    f"+{REF_BONUS_COINS} coin qo'shildi.",
                )
            except Exception:
                pass

            # Bosqichli referral bonusni tekshiramiz (masalan 5, 10, 20 do'st...)
            tier_result = await db.check_referral_tier_bonus(referrer_id)
            if tier_result:
                threshold, bonus = tier_result
                try:
                    await bot.send_message(
                        referrer_id,
                        f"🏆 Tabriklaymiz! Siz <b>{threshold}</b> ta do'st taklif qildingiz!\n"
                        f"🎁 Bonus sifatida qo'shimcha <b>+{bonus} coin</b> berildi!",
                    )
                except Exception:
                    pass

    await message.answer(
        "👋 Assalomu alaykum!\n\n"
        f"Botga xush kelibsiz. Sizga {START_COINS} ta boshlang'ich coin berildi.\n"
        "Har bir coin evaziga 1 ta qiziqarli video olishingiz mumkin.\n\n"
        "💡 Coin ko'paytirish yo'llari:\n"
        f"• ⏳ Har {ENERGY_REGEN_HOURS} soatda avtomatik 1 coin tiklanadi\n"
        "• 🎁 Har kuni botga kirib kunlik bonus oling\n"
        "• 👥 Do'st taklif qiling - qancha ko'p taklif qilsangiz, shuncha katta bonus!",
        reply_markup=main_menu_kb(),
    )


@router.message(F.text == "💰 Coinlarim")
async def my_coins(message: Message):
    user_id = message.from_user.id
    # ko'rsatishdan oldin energy-regen coinlarni tekshirib/qo'shib qo'yamiz
    added = await db.apply_energy_regen(user_id)

    user = await db.get_user(user_id)
    coins = user["coins"] if user else 0
    ref_count = user["ref_count"] if user else 0

    text = (
        f"💰 Sizda hozir: <b>{coins}</b> ta coin bor.\n"
        f"👥 Siz <b>{ref_count}</b> ta do'st taklif qilgansiz.\n\n"
        f"⏳ Har {ENERGY_REGEN_HOURS} soatda avtomatik 1 coin tiklanadi "
        f"(maksimal {ENERGY_REGEN_MAX} tagacha)."
    )
    if added:
        text = f"⚡️ Avtomatik tiklanish orqali +{added} coin qo'shildi!\n\n" + text

    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🎁 Kunlik bonus")
async def daily_bonus(message: Message):
    user_id = message.from_user.id
    claimed = await db.claim_daily_bonus(user_id)
    if claimed:
        from config import DAILY_BONUS_COINS
        await message.answer(
            f"🎁 Kunlik bonusingiz olindi: +{DAILY_BONUS_COINS} coin!\n"
            "Ertaga qayta kiring va yana bonus oling 😊"
        )
    else:
        await message.answer(
            "😅 Siz bugungi bonusingizni allaqachon olib bo'lgansiz.\n"
            "Ertaga qayta urinib ko'ring!"
        )


@router.message(F.text == "👥 Do'st taklif qilish")
async def invite_friend(message: Message, bot: Bot):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    user = await db.get_user(user_id)
    ref_count = user["ref_count"] if user else 0

    await message.answer(
        "👥 <b>Do'stlaringizni taklif qiling va coin ishlang!</b>\n\n"
        f"Har bir taklif qilingan do'stingiz uchun +{REF_BONUS_COINS} coin olasiz.\n"
        f"Hozircha siz <b>{ref_count}</b> ta do'st taklif qilgansiz.\n\n"
        "Quyidagi tugma orqali bir bosishda do'stlaringizga yuboring 👇",
        reply_markup=invite_kb(link),
    )


@router.callback_query(F.data == "ref_list")
async def ref_list_callback(call: CallbackQuery):
    user_id = call.from_user.id
    friends = await db.get_referred_users(user_id, limit=20)

    if not friends:
        await call.answer("😔 Siz hali hech kimni taklif qilmagansiz.", show_alert=True)
        return

    text = f"👥 <b>Siz taklif qilgan do'stlar ({len(friends)} ta ko'rsatilmoqda):</b>\n\n"
    for i, f in enumerate(friends, start=1):
        name = f["first_name"] or "Foydalanuvchi"
        username = f"@{f['username']}" if f["username"] else f"ID: {f['user_id']}"
        text += f"{i}. {name} ({username})\n"

    await call.answer()
    await call.message.answer(text, parse_mode="HTML")


@router.message(F.text == "🎬 Video olish")
async def get_video(message: Message, bot: Bot):
    user_id = message.from_user.id

    if await db.is_banned(user_id):
        await message.answer("🚫 Siz botdan foydalanish huquqidan mahrum qilingansiz.")
        return

    not_subscribed = await check_subscriptions(bot, user_id)
    if not_subscribed:
        await message.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=subscribe_kb(not_subscribed),
        )
        return

    # coin tugagan bo'lsa, avtomatik tiklanishni tekshiramiz
    await db.apply_energy_regen(user_id)

    user = await db.get_user(user_id)
    if not user or user["coins"] <= 0:
        await message.answer(
            "😔 Sizda coin qolmadi.\n"
            f"⏳ Coin har {ENERGY_REGEN_HOURS} soatda avtomatik tiklanadi, "
            "yoki do'stlaringizni taklif qilib tezroq coin ishlang 👇",
        )
        await invite_friend(message, bot)
        return

    ok = await db.take_coin(user_id)
    if not ok:
        await message.answer("😔 Sizda coin qolmadi.")
        return

    await send_random_video(bot, message.chat.id, user_id)


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery, bot: Bot):
    not_subscribed = await check_subscriptions(bot, call.from_user.id)
    if not_subscribed:
        await call.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
        return
    await call.message.delete()
    await call.message.answer("✅ Rahmat! Endi botdan to'liq foydalanishingiz mumkin.", reply_markup=main_menu_kb())


@router.callback_query(F.data.startswith("like:"))
async def like_video(call: CallbackQuery):
    video_id = int(call.data.split(":")[1])
    likes, dislikes = await db.set_reaction(call.from_user.id, video_id, liked=True)
    try:
        await call.message.edit_reply_markup(
            reply_markup=video_reaction_kb(video_id, likes, dislikes)
        )
    except Exception:
        pass
    await call.answer("🔥 Ovozingiz qabul qilindi!")


@router.callback_query(F.data.startswith("dislike:"))
async def dislike_video(call: CallbackQuery):
    video_id = int(call.data.split(":")[1])
    likes, dislikes = await db.set_reaction(call.from_user.id, video_id, liked=False)
    try:
        await call.message.edit_reply_markup(
            reply_markup=video_reaction_kb(video_id, likes, dislikes)
        )
    except Exception:
        pass
    await call.answer("👎 Fikringiz uchun rahmat!")


@router.callback_query(F.data == "new_video")
async def new_video_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id

    if await db.is_banned(user_id):
        await call.answer("🚫 Siz botdan foydalanish huquqidan mahrum qilingansiz.", show_alert=True)
        return

    not_subscribed = await check_subscriptions(bot, user_id)
    if not_subscribed:
        await call.answer("⚠️ Avval majburiy kanallarga obuna bo'ling!", show_alert=True)
        await call.message.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=subscribe_kb(not_subscribed),
        )
        return

    await db.apply_energy_regen(user_id)

    user = await db.get_user(user_id)
    if not user or user["coins"] <= 0:
        await call.answer(
            f"😔 Sizda coin qolmadi! Har {ENERGY_REGEN_HOURS} soatda avtomatik tiklanadi, "
            "yoki do'st taklif qiling.",
            show_alert=True,
        )
        return

    ok = await db.take_coin(user_id)
    if not ok:
        await call.answer("😔 Sizda coin qolmadi!", show_alert=True)
        return

    await call.answer()
    await send_random_video(bot, call.message.chat.id, user_id)


@router.callback_query(F.data == "share")
async def share_callback(call: CallbackQuery, bot: Bot):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{call.from_user.id}"
    share_text = (
        "🎬 Bu botda qiziqarli videolar bor, coin yig'ib bepul tomosha qilsa bo'ladi!\n\n"
        f"👉 {link}"
    )
    await call.answer()
    await call.message.answer(
        "📤 Quyidagi matnni do'stlaringizga yuboring:\n\n" + share_text
    )


# ---------------- TELEGRAM STARS ORQALI COIN SOTIB OLISH ----------------

@router.message(F.text == "⭐️ Coin sotib olish")
async def buy_coins_menu(message: Message):
    await message.answer(
        "⭐️ Telegram Stars orqali coin sotib olishingiz mumkin.\n"
        "Kerakli paketni tanlang:",
        reply_markup=star_packages_kb(STAR_PACKAGES),
    )


@router.callback_query(F.data.startswith("buy:"))
async def buy_package_callback(call: CallbackQuery, bot: Bot):
    _, stars, coins = call.data.split(":")
    stars, coins = int(stars), int(coins)

    await call.answer()
    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"{coins} ta coin",
        description=f"Botda video olish uchun {coins} ta coin sotib olasiz.",
        payload=f"coins:{coins}",
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label=f"{coins} coin", amount=stars)],
        provider_token="",  # Stars uchun bo'sh qoldiriladi
    )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    payload = message.successful_payment.invoice_payload  # "coins:35" kabi
    try:
        coins = int(payload.split(":")[1])
    except (IndexError, ValueError):
        coins = 0

    if coins > 0:
        await db.add_coins(message.from_user.id, coins)
        await message.answer(
            f"✅ To'lov muvaffaqiyatli o'tdi! +{coins} coin hisobingizga qo'shildi.\n"
            "Rahmat! 🎬"
        )
