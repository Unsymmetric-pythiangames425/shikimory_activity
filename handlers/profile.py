"""Обработчики для управления профилями"""
from aiogram import Router, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from services import parser, tracker
from keyboards import (
    profiles_list_keyboard,
    profile_menu_keyboard,
    confirm_delete_keyboard,
    cancel_keyboard,
    main_menu_keyboard
)

router = Router()


class AddProfileStates(StatesGroup):
    """Состояния добавления профиля"""
    waiting_username = State()


@router.callback_query(F.data == 'add_profile')
async def start_add_profile(callback: CallbackQuery, state: FSMContext):
    """Начать добавление профиля"""
    text = (
        "➕ <b>Добавление профиля</b>\n\n"
        "Отправьте никнейм пользователя на Shikimori\n\n"
        "Примеры:\n"
        "• <code>Bubassaka</code>\n"
        "• <code>YourNickname</code>\n\n"
        "Или полную ссылку:\n"
        "• <code>https://shikimori.one/Bubassaka</code>"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )
    await state.set_state(AddProfileStates.waiting_username)
    await callback.answer()


@router.message(AddProfileStates.waiting_username)
async def process_username(message: Message, state: FSMContext):
    """Обработать введённый никнейм"""
    username = message.text.strip()

    # Извлекаем никнейм из ссылки если была отправлена ссылка
    if 'shikimori.one/' in username:
        parts = username.split('shikimori.one/')
        if len(parts) > 1:
            username = parts[1].strip('/').split('/')[0]

    # Проверяем валидность никнейма
    if not username or len(username) < 2:
        await message.answer("❌ Никнейм слишком короткий. Попробуйте ещё раз:")
        return

    # Показываем процесс
    status_msg = await message.answer("🔄 Проверяю профиль...")

    # Проверяем существование профиля на Shikimori
    data = await parser.get_profile_data(username)

    if not data or not data.get('success'):
        await status_msg.edit_text(
            f"❌ Профиль <b>{username}</b> не найден на Shikimori\n\n"
            "Проверьте правильность написания и попробуйте снова:",
            parse_mode='HTML'
        )
        return

    # Проверяем, не добавлен ли уже этот профиль
    profile_info = data.get('profile_info', {})
    shikimori_user_id = profile_info.get('user_id')

    # Проверяем существование в БД
    existing_profiles = await db.get_user_profiles(message.from_user.id)
    for existing in existing_profiles:
        # Проверяем по ID или по username
        if (shikimori_user_id and existing.shikimori_user_id == shikimori_user_id) or \
           (existing.shikimori_username.lower() == username.lower()):
            await status_msg.edit_text(
                f"ℹ️ <b>Профиль уже добавлен</b>\n\n"
                f"Пользователь <b>{username}</b> уже находится в вашем списке отслеживания.\n\n"
                f"Вы можете настроить уведомления в меню профиля.",
                reply_markup=profile_menu_keyboard(existing.id),
                parse_mode='HTML'
            )
            await state.clear()
            return

    # Добавляем профиль в БД
    try:
        profile = await db.add_tracked_profile(
            user_id=message.from_user.id,
            shikimori_username=username,
            shikimori_user_id=shikimori_user_id
        )

        online_status = data.get('online_status', {})

        text = (
            f"✅ <b>Профиль добавлен!</b>\n\n"
            f"👤 Пользователь: <b>{username}</b>\n"
            f"🔗 <a href='https://shikimori.one/{username}'>Открыть профиль</a>\n\n"
            f"📊 Статус: {online_status.get('status_text', 'Неизвестно')}\n\n"
            "Вы будете получать уведомления об изменениях в истории просмотров.\n"
            "Настроить уведомления можно в меню профиля."
        )

        await status_msg.edit_text(
            text=text,
            reply_markup=profile_menu_keyboard(profile.id),
            parse_mode='HTML'
        )
        await state.clear()

    except Exception as e:
        await status_msg.edit_text(
            f"❌ Ошибка добавления профиля: {e}\n\n"
            "Попробуйте позже или обратитесь к разработчику.",
            reply_markup=main_menu_keyboard()
        )
        await state.clear()


@router.callback_query(F.data == 'my_profiles')
async def show_my_profiles(callback: CallbackQuery):
    """Показать список профилей"""
    profiles = await db.get_user_profiles(callback.from_user.id)

    if not profiles:
        text = (
            "📋 <b>Ваши профили</b>\n\n"
            "У вас пока нет отслеживаемых профилей.\n"
            "Добавьте первый профиль для начала работы!"
        )
        # Создаем клавиатуру с кнопкой добавления
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="➕ Добавить профиль",
                                 callback_data="add_profile")
        )
        builder.row(
            InlineKeyboardButton(text="🏠 Главное меню",
                                 callback_data="main_menu")
        )

        await callback.message.edit_text(
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode='HTML'
        )
    else:
        text = (
            f"📋 <b>Ваши профили</b> ({len(profiles)})\n\n"
            "Выберите профиль для управления:"
        )
        await callback.message.edit_text(
            text=text,
            reply_markup=profiles_list_keyboard(profiles, page=0),
            parse_mode='HTML'
        )

    await callback.answer()


@router.callback_query(F.data.startswith('profiles_page:'))
async def profiles_pagination(callback: CallbackQuery):
    """Обработка пагинации профилей"""
    page = int(callback.data.split(':')[1])

    profiles = await db.get_user_profiles(callback.from_user.id)

    text = (
        f"📋 <b>Ваши профили</b> ({len(profiles)})\n\n"
        "Выберите профиль для управления:"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=profiles_list_keyboard(profiles, page=page),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == 'noop')
async def noop_callback(callback: CallbackQuery):
    """Пустой callback для индикатора страницы"""
    await callback.answer()


@router.callback_query(F.data.startswith('profile:'))
async def show_profile_menu(callback: CallbackQuery):
    """Показать меню профиля"""
    profile_id = int(callback.data.split(':')[1])

    # Получаем профиль
    profiles = await db.get_user_profiles(callback.from_user.id)
    profile = next((p for p in profiles if p.id == profile_id), None)

    if not profile:
        await callback.answer("❌ Профиль не найден", show_alert=True)
        return

    text = (
        f"👤 <b>Профиль: {profile.shikimori_username}</b>\n\n"
        f"🔗 <a href='https://shikimori.one/{profile.shikimori_username}'>Открыть на Shikimori</a>\n\n"
        f"📊 Последний статус:\n{profile.last_online_status or 'Неизвестно'}\n\n"
        f"📅 Добавлен: {profile.created_at.strftime('%d.%m.%Y %H:%M')}\n"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=profile_menu_keyboard(profile_id),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data.startswith('status:'))
async def check_profile_status(callback: CallbackQuery):
    """Проверить текущий статус профиля"""
    profile_id = int(callback.data.split(':')[1])

    # Получаем профиль
    profiles = await db.get_user_profiles(callback.from_user.id)
    profile = next((p for p in profiles if p.id == profile_id), None)

    if not profile:
        await callback.answer("❌ Профиль не найден", show_alert=True)
        return

    await callback.answer("🔄 Проверяю статус...")

    # Получаем данные
    data = await parser.get_profile_data(profile.shikimori_username)

    if not data or not data.get('success'):
        await callback.answer(
            "❌ Не удалось получить данные профиля",
            show_alert=True
        )
        return

    online_status = data.get('online_status', {})
    profile_info = data.get('profile_info', {})
    history = data.get('history', [])

    status_icon = "🟢" if online_status.get('is_online') else "⚫"

    text = (
        f"📊 <b>Статус профиля {profile.shikimori_username}</b>\n\n"
        f"{status_icon} {online_status.get('status_text', 'Неизвестно')}\n\n"
    )

    # Статистика аниме
    if profile_info.get('anime_stats'):
        text += "📺 <b>Аниме:</b>\n"
        for stat, count in profile_info['anime_stats'].items():
            text += f"   • {stat}: {count}\n"
        text += "\n"

    # Последняя активность
    if history:
        text += "📝 <b>Последняя активность:</b>\n"
        last_entry = history[0]
        text += f"   {last_entry['anime_name']}\n"
        text += f"   {last_entry['action']}\n"
        text += f"   ⏰ {last_entry['timestamp']}\n"

    await callback.message.edit_text(
        text=text,
        reply_markup=profile_menu_keyboard(profile_id),
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith('delete:'))
async def confirm_profile_deletion(callback: CallbackQuery):
    """Подтверждение удаления профиля"""
    profile_id = int(callback.data.split(':')[1])

    profiles = await db.get_user_profiles(callback.from_user.id)
    profile = next((p for p in profiles if p.id == profile_id), None)

    if not profile:
        await callback.answer("❌ Профиль не найден", show_alert=True)
        return

    text = (
        f"🗑 <b>Удаление профиля</b>\n\n"
        f"Вы уверены, что хотите удалить профиль\n"
        f"<b>{profile.shikimori_username}</b>?\n\n"
        "Это действие нельзя отменить."
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=confirm_delete_keyboard(profile_id),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data.startswith('confirm_delete:'))
async def delete_profile(callback: CallbackQuery):
    """Удалить профиль"""
    profile_id = int(callback.data.split(':')[1])

    profiles = await db.get_user_profiles(callback.from_user.id)
    profile = next((p for p in profiles if p.id == profile_id), None)

    if not profile:
        await callback.answer("❌ Профиль не найден", show_alert=True)
        return

    username = profile.shikimori_username
    await db.remove_profile(profile_id)

    text = (
        f"✅ <b>Профиль удалён</b>\n\n"
        f"Профиль <b>{username}</b> больше не отслеживается.\n"
        "Вы не будете получать уведомления."
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=main_menu_keyboard(),
        parse_mode='HTML'
    )
    await callback.answer("Профиль удалён")
