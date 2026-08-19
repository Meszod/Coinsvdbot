from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎬 Video olish")],
            [KeyboardButton(text="👥 Do'st taklif qilish"), KeyboardButton(text="💰 Coinlarim")],
            [KeyboardButton(text="🎁 Kunlik bonus"), KeyboardButton(text="⭐️ Coin sotib olish")],
        ],
        resize_keyboard=True,
    )


def video_reaction_kb(video_id: int, likes: int = 0, dislikes: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"🔥 Zo'r ({likes})", callback_data=f"like:{video_id}"),
                InlineKeyboardButton(text=f"👎 Yoqmadi ({dislikes})", callback_data=f"dislike:{video_id}"),
            ],
            [InlineKeyboardButton(text="📤 Do'stlarga ulashish", callback_data="share")],
            [InlineKeyboardButton(text="🎥 Yangi video", callback_data="new_video")],
        ]
    )


def subscribe_kb(channels) -> InlineKeyboardMarkup:
    """Kanallarni 2 tadan qilib, rasmdagidek grid ko'rinishida chiqaradi."""
    buttons = []
    for i, ch in enumerate(channels, start=1):
        chat_id = ch["chat_id"]
        invite_link = ch["invite_link"] if "invite_link" in ch.keys() else None

        if invite_link:
            url = invite_link
        elif str(chat_id).startswith("@"):
            url = f"https://t.me/{str(chat_id)[1:]}"
        else:
            url = f"https://t.me/{chat_id}"

        buttons.append(InlineKeyboardButton(text=f"➕ Obuna bo'lish #{i}", url=url))

    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Majburiy kanal qo'shish", callback_data="adm_add_mand")],
            [InlineKeyboardButton(text="➖ Majburiy kanal o'chirish", callback_data="adm_del_mand")],
            [InlineKeyboardButton(text="📋 Majburiy kanallar ro'yxati", callback_data="adm_list_mand")],
            [InlineKeyboardButton(text="➕ Video manba kanal qo'shish", callback_data="adm_add_src")],
            [InlineKeyboardButton(text="➖ Video manba kanal o'chirish", callback_data="adm_del_src")],
            [InlineKeyboardButton(text="📋 Manba kanallar ro'yxati", callback_data="adm_list_src")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats")],
            [InlineKeyboardButton(text="📨 Ommaviy xabar yuborish", callback_data="adm_broadcast")],
            [InlineKeyboardButton(text="🚫 Foydalanuvchini bloklash", callback_data="adm_ban")],
            [InlineKeyboardButton(text="✅ Blokdan chiqarish", callback_data="adm_unban")],
        ]
    )


def invite_kb(link: str) -> InlineKeyboardMarkup:
    """
    Bosilganda Telegram'ning o'zining 'kimga yuborish' oynasini ochadi -
    foydalanuvchi shunchaki kontaktini tanlaydi, matn qo'lda forward qilinmaydi.
    """
    share_text = "🎬 Bu botda qiziqarli videolar bor, coin yig'ib bepul tomosha qil!"
    share_url = f"https://t.me/share/url?url={link}&text={share_text}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Do'stga yuborish", url=share_url)],
            [InlineKeyboardButton(text="👥 Taklif qilganlarim ro'yxati", callback_data="ref_list")],
        ]
    )


def star_packages_kb(packages: dict) -> InlineKeyboardMarkup:
    rows = []
    for stars, coins in sorted(packages.items()):
        rows.append([
            InlineKeyboardButton(
                text=f"⭐️ {stars} Stars — {coins} coin",
                callback_data=f"buy:{stars}:{coins}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
