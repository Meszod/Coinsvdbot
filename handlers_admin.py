import asyncio

from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import database as db
from config import ADMIN_IDS, MIN_VIDEO_DURATION
from keyboards import admin_panel_kb

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class AdminStates(StatesGroup):
    waiting_mand_channel = State()
    waiting_mand_channel_del = State()
    waiting_src_channel = State()
    waiting_src_channel_del = State()
    waiting_broadcast = State()
    waiting_ban_user = State()
    waiting_unban_user = State()


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 Admin panel:", reply_markup=admin_panel_kb())


@router.callback_query(F.data == "adm_stats")
async def adm_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    users_count = await db.count_users()
    videos_count = await db.count_videos()
    new_today = await db.stats_today_new_users()

    text = (
        f"📊 Statistika:\n\n"
        f"👤 Jami foydalanuvchilar: {users_count}\n"
        f"🆕 Bugun qo'shilganlar: {new_today}\n"
        f"🎬 Videolar bazasi: {videos_count}\n"
    )

    top_liked = await db.top_videos(order_by="likes", limit=5)
    if top_liked:
        text += "\n🔥 Eng ko'p like olgan videolar:\n"
        for v in top_liked:
            text += f"  • #{v['id']}: {v['likes']}👍 / {v['dislikes']}👎\n"

    top_disliked = await db.top_videos(order_by="dislikes", limit=5)
    if top_disliked:
        text += "\n👎 Eng ko'p dislike olgan videolar:\n"
        for v in top_disliked:
            text += f"  • #{v['id']}: {v['likes']}👍 / {v['dislikes']}👎\n"

    active_users = await db.most_active_users(limit=5)
    if active_users:
        text += "\n⚡️ Eng faol foydalanuvchilar (ko'rilgan video soni bo'yicha):\n"
        for u in active_users:
            text += f"  • ID {u['user_id']}: {u['cnt']} ta video\n"

    await call.message.answer(text)
    await call.answer()


# ---------------- MAJBURIY KANALLAR ----------------

@router.callback_query(F.data == "adm_add_mand")
async def adm_add_mand(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.answer(
        "Kanal username (@kanal) yoki ID sini yuboring.\n"
        "Eslatma: bot shu kanalda ADMIN bo'lishi kerak (obunani tekshirish uchun)."
    )
    await state.set_state(AdminStates.waiting_mand_channel)
    await call.answer()


@router.message(AdminStates.waiting_mand_channel)
async def save_mand_channel(message: Message, state: FSMContext, bot: Bot):
    chat_id_input = message.text.strip()
    try:
        chat = await bot.get_chat(chat_id_input)
    except Exception:
        await message.answer("❌ Kanal topilmadi. Bot shu kanalda admin ekanligiga ishonch hosil qiling.")
        await state.clear()
        return

    title = chat.title or chat_id_input
    invite_link = None

    if chat.username:
        # ochiq kanal - username orqali oddiy https://t.me/username link ishlatiladi
        real_id = f"@{chat.username}"
    else:
        # yopiq (username'siz) kanal - t.me/<raqam> ishlamaydi, taklif havolasi kerak
        real_id = str(chat.id)
        try:
            invite_link = await bot.export_chat_invite_link(chat.id)
        except Exception:
            await message.answer(
                "⚠️ Kanal username'ga ega emas va bot taklif havolasini yarata olmadi.\n"
                "Bot shu kanalda 'Foydalanuvchilarni taklif qilish orqali havola yaratish' "
                "huquqiga ega ADMIN ekanligini tekshiring."
            )
            await state.clear()
            return

    ok = await db.add_mandatory_channel(real_id, title, invite_link)
    if ok:
        await message.answer(f"✅ Majburiy kanal qo'shildi: {title}")
    else:
        await message.answer("⚠️ Bu kanal allaqachon ro'yxatda bor.")
    await state.clear()


@router.callback_query(F.data == "adm_list_mand")
async def adm_list_mand(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    channels = await db.get_mandatory_channels()
    if not channels:
        await call.message.answer("📋 Majburiy kanallar ro'yxati bo'sh.")
    else:
        text = "📋 Majburiy kanallar:\n\n" + "\n".join(
            f"• {c['title']} ({c['chat_id']})" for c in channels
        )
        await call.message.answer(text)
    await call.answer()


@router.callback_query(F.data == "adm_del_mand")
async def adm_del_mand(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.answer("O'chirmoqchi bo'lgan kanalning chat_id sini yuboring (ro'yxatni ko'rish uchun 📋 tugmasidan foydalaning).")
    await state.set_state(AdminStates.waiting_mand_channel_del)
    await call.answer()


@router.message(AdminStates.waiting_mand_channel_del)
async def del_mand_channel(message: Message, state: FSMContext):
    await db.remove_mandatory_channel(message.text.strip())
    await message.answer("✅ O'chirildi (agar mavjud bo'lsa).")
    await state.clear()


# ---------------- VIDEO MANBA KANALLAR ----------------

@router.callback_query(F.data == "adm_add_src")
async def adm_add_src(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.answer(
        "Video olinadigan kanal username (@kanal) yoki ID sini yuboring.\n\n"
        "ℹ️ Bu ro'yxat faqat kelajakda o'sha kanalga tushadigan YANGI videolarni "
        "avtomatik ushlab olish uchun (buning uchun bot kanalda admin bo'lishi kerak).\n\n"
        "⚠️ Kanaldagi ESKI (arxiv) videolarni bu ro'yxat OLIB BERMAYDI — "
        "Bot API kanal tarixini o'qiy olmaydi. Eski videolarni qo'shish uchun "
        f"ularni birma-bir shu botga FORWARD qiling (kanalda videoni tanlang → Forward → botga yuboring). "
        f"Bot avtomatik ({MIN_VIDEO_DURATION} soniyadan uzun bo'lsa) saqlab oladi — "
        "buning uchun bot admin bo'lishi shart emas."
    )
    await state.set_state(AdminStates.waiting_src_channel)
    await call.answer()


@router.message(AdminStates.waiting_src_channel)
async def save_src_channel(message: Message, state: FSMContext, bot: Bot):
    chat_id_input = message.text.strip()
    try:
        chat = await bot.get_chat(chat_id_input)
    except Exception:
        await message.answer("❌ Kanal topilmadi.")
        await state.clear()
        return

    ok = await db.add_source_channel(chat.id, chat.title or chat_id_input)
    if ok:
        await message.answer(f"✅ Manba kanal qo'shildi: {chat.title}")
    else:
        await message.answer("⚠️ Bu kanal allaqachon ro'yxatda bor.")
    await state.clear()


@router.callback_query(F.data == "adm_list_src")
async def adm_list_src(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    channels = await db.get_source_channels()
    if not channels:
        await call.message.answer("📋 Manba kanallar ro'yxati bo'sh.")
    else:
        text = "📋 Manba kanallar:\n\n" + "\n".join(
            f"• {c['title']} ({c['chat_id']})" for c in channels
        )
        await call.message.answer(text)
    await call.answer()


@router.callback_query(F.data == "adm_del_src")
async def adm_del_src(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.answer("O'chirmoqchi bo'lgan manba kanalning chat_id (raqam) sini yuboring.")
    await state.set_state(AdminStates.waiting_src_channel_del)
    await call.answer()


@router.message(AdminStates.waiting_src_channel_del)
async def del_src_channel(message: Message, state: FSMContext):
    try:
        chat_id = int(message.text.strip())
        await db.remove_source_channel(chat_id)
        await message.answer("✅ O'chirildi (agar mavjud bo'lsa).")
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Raqam (masalan -1001234567890) yuboring.")
    await state.clear()


# ---------------- ADMIN FORWARD ORQALI ESKI VIDEOLARNI YIG'ISH ----------------

@router.message(F.video, F.forward_origin, StateFilter(None))
async def collect_forwarded_video(message: Message):
    """Admin botga kanaldan video forward qilsa, bot uni (manba ko'rinmagan holda) bazaga saqlaydi."""
    if not is_admin(message.from_user.id):
        return

    duration = message.video.duration or 0
    if duration < MIN_VIDEO_DURATION:
        await message.answer(f"⏭ O'tkazib yuborildi: video {duration} soniya (kamida {MIN_VIDEO_DURATION} kerak).")
        return

    added = await db.add_video(message.video.file_id, duration)
    if added:
        await message.answer(f"✅ Video bazaga qo'shildi. (Davomiyligi: {duration}s)")
    else:
        await message.answer("⚠️ Bu video allaqachon bazada bor.")


# ---------------- OMMAVIY XABAR YUBORISH (BROADCAST) ----------------

@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.answer(
        "📨 Barcha foydalanuvchilarga yuborilishi kerak bo'lgan xabarni yuboring "
        "(matn, rasm, video - istalgani bo'lishi mumkin)."
    )
    await state.set_state(AdminStates.waiting_broadcast)
    await call.answer()


@router.message(AdminStates.waiting_broadcast)
async def do_broadcast(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_ids = await db.get_all_user_ids()
    await message.answer(f"⏳ Yuborish boshlandi... ({len(user_ids)} foydalanuvchi)")

    success, failed = 0, 0
    for user_id in user_ids:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # flood-limitga tushib qolmaslik uchun

    await message.answer(f"✅ Yuborildi: {success} ta\n❌ Yuborilmadi: {failed} ta")


# ---------------- FOYDALANUVCHINI BLOKLASH / BLOKDAN CHIQARISH ----------------

@router.callback_query(F.data == "adm_ban")
async def adm_ban(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.answer("Bloklamoqchi bo'lgan foydalanuvchining Telegram ID sini yuboring.")
    await state.set_state(AdminStates.waiting_ban_user)
    await call.answer()


@router.message(AdminStates.waiting_ban_user)
async def do_ban(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await db.ban_user(user_id)
        await message.answer(f"🚫 Foydalanuvchi {user_id} bloklandi.")
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Raqam (Telegram ID) yuboring.")
    await state.clear()


@router.callback_query(F.data == "adm_unban")
async def adm_unban(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.answer("Blokdan chiqarmoqchi bo'lgan foydalanuvchining Telegram ID sini yuboring.")
    await state.set_state(AdminStates.waiting_unban_user)
    await call.answer()


@router.message(AdminStates.waiting_unban_user)
async def do_unban(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await db.unban_user(user_id)
        await message.answer(f"✅ Foydalanuvchi {user_id} blokdan chiqarildi.")
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Raqam (Telegram ID) yuboring.")
    await state.clear()
