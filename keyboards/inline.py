"""Inline клавиатуры"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List
from database.models import TrackedProfile


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить профиль",
                             callback_data="add_profile")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Мои профили", callback_data="my_profiles")
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")
    )
    return builder.as_markup()


def profiles_list_keyboard(profiles: List[TrackedProfile], page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Список профилей с пагинацией"""
    builder = InlineKeyboardBuilder()

    # Вычисляем диапазон профилей для текущей страницы
    start_idx = page * per_page
    end_idx = start_idx + per_page
    total_pages = (len(profiles) + per_page - 1) // per_page

    # Профили на текущей странице
    page_profiles = profiles[start_idx:end_idx]

    for profile in page_profiles:
        builder.row(
            InlineKeyboardButton(
                text=f"👤 {profile.shikimori_username}",
                callback_data=f"profile:{profile.id}"
            )
        )

    # Кнопки пагинации
    pagination_buttons = []

    if page > 0:
        pagination_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Назад", callback_data=f"profiles_page:{page-1}")
        )

    if total_pages > 1:
        pagination_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {page+1}/{total_pages}", callback_data="noop")
        )

    if page < total_pages - 1:
        pagination_buttons.append(
            InlineKeyboardButton(
                text="Вперёд ➡️", callback_data=f"profiles_page:{page+1}")
        )

    if pagination_buttons:
        builder.row(*pagination_buttons)

    # Кнопки действий
    builder.row(
        InlineKeyboardButton(text="➕ Добавить профиль",
                             callback_data="add_profile")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )

    return builder.as_markup()


def profile_menu_keyboard(profile_id: int) -> InlineKeyboardMarkup:
    """Меню профиля"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки",
                             callback_data=f"settings:{profile_id}")
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Статус", callback_data=f"status:{profile_id}")
    )
    builder.row(
        InlineKeyboardButton(
            text="🗑 Удалить", callback_data=f"delete:{profile_id}")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="my_profiles")
    )

    return builder.as_markup()


def settings_keyboard(profile: TrackedProfile) -> InlineKeyboardMarkup:
    """Настройки уведомлений"""
    builder = InlineKeyboardBuilder()

    # История
    history_icon = "✅" if profile.notify_history else "❌"
    builder.row(
        InlineKeyboardButton(
            text=f"{history_icon} История просмотров",
            callback_data=f"toggle:history:{profile.id}"
        )
    )

    # Онлайн
    online_icon = "✅" if profile.notify_online else "❌"
    builder.row(
        InlineKeyboardButton(
            text=f"{online_icon} Пользователь в сети",
            callback_data=f"toggle:online:{profile.id}"
        )
    )

    # Оффлайн
    offline_icon = "✅" if profile.notify_offline else "❌"
    builder.row(
        InlineKeyboardButton(
            text=f"{offline_icon} Пользователь вышел",
            callback_data=f"toggle:offline:{profile.id}"
        )
    )

    # Достижения
    achievements_icon = "✅" if profile.notify_achievements else "❌"
    builder.row(
        InlineKeyboardButton(
            text=f"{achievements_icon} Достижения (скоро)",
            callback_data=f"toggle:achievements:{profile.id}"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад", callback_data=f"profile:{profile.id}")
    )

    return builder.as_markup()


def confirm_delete_keyboard(profile_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить",
                             callback_data=f"confirm_delete:{profile_id}"),
        InlineKeyboardButton(
            text="❌ Отмена", callback_data=f"profile:{profile_id}")
    )

    return builder.as_markup()


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")
    )
    return builder.as_markup()
