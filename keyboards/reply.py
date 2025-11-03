"""Reply клавиатуры"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура (не исчезает при уведомлениях)"""
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="📋 Мои профили"),
        KeyboardButton(text="➕ Добавить профиль")
    )
    builder.row(
        KeyboardButton(text="ℹ️ Помощь")
    )

    return builder.as_markup(resize_keyboard=True)


def remove_keyboard() -> ReplyKeyboardMarkup:
    """Удалить клавиатуру"""
    return ReplyKeyboardRemove()
